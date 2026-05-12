"""Ring tone generation and playback."""
from __future__ import annotations

import logging
import math
import struct
import subprocess
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from voiphandset.device import Device

log = logging.getLogger("voiphandset.ring")

# Play through PulseAudio/PipeWire because the kernel ALSA device is held
# exclusively by the PipeWire loopback module. paplay accepts the sink name
# directly. We send to the underlying HP Handset sink (not our own virtual
# speakerphone sink) so the bit-0 route the ring engine sets is the only
# input to the routing decision.
PA_DEVICE = "alsa_output.usb-Hewlett-Packard_HP_Internet_Handset_0000000001-00.iec958-stereo"
RING_TIMEOUT_SEC = 30


@dataclass
class RingPattern:
    name: str
    freq_a: int
    freq_b: int
    on_off: list[tuple[float, float]]


PATTERNS: dict[str, RingPattern] = {
    "us":   RingPattern("us",   440, 480, [(2.0, 4.0)]),
    "uk":   RingPattern("uk",   400, 450, [(0.4, 0.2), (0.4, 2.0)]),
    "bell": RingPattern("bell", 540, 660, [(1.0, 1.0)]),
}


def _gen_dual_tone_wav(path: Path, freq_a: int, freq_b: int, duration: float,
                       sample_rate: int = 48000, gain: float = 0.4):
    n = int(sample_rate * duration)
    fade = int(sample_rate * 0.04)
    buf = bytearray(n * 4)
    for i in range(n):
        t = i / sample_rate
        env = 1.0
        if i < fade:
            env = i / fade
        elif i >= n - fade:
            env = (n - i) / fade
        s = (math.sin(2 * math.pi * freq_a * t) + math.sin(2 * math.pi * freq_b * t)) * env * gain
        v = max(-1.0, min(1.0, s))
        sample = int(v * 32767)
        struct.pack_into("<hh", buf, i * 4, sample, sample)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(bytes(buf))


class RingEngine:
    """Plays a ring pattern through the base speaker. start()/stop() are thread-safe."""

    def __init__(self, device: Device, on_finished=None):
        self.device = device
        self.on_finished = on_finished
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._tone_cache: dict[tuple[int, int, float], Path] = {}

    def is_ringing(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def _get_tone(self, freq_a: int, freq_b: int, duration: float) -> Path:
        key = (freq_a, freq_b, round(duration, 2))
        if key in self._tone_cache:
            return self._tone_cache[key]
        tmp = Path(tempfile.gettempdir()) / f"voiphandset_tone_{freq_a}_{freq_b}_{duration:.2f}.wav"
        if not tmp.exists():
            _gen_dual_tone_wav(tmp, freq_a, freq_b, duration)
        self._tone_cache[key] = tmp
        return tmp

    def start(self, pattern: RingPattern, max_duration: float = RING_TIMEOUT_SEC):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                log.debug("already ringing, ignoring new start")
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, args=(pattern, max_duration),
                daemon=True, name="ring-engine",
            )
            self._thread.start()

    def stop(self, reason: str = ""):
        with self._lock:
            if self._thread is None:
                return
            log.info("stop ring (%s)", reason)
            self._stop.set()
            t = self._thread
        t.join(timeout=3)
        with self._lock:
            self._thread = None

    def _run(self, pattern: RingPattern, max_duration: float):
        log.info("ring start: pattern=%s timeout=%ss", pattern.name, max_duration)
        deadline = time.time() + max_duration
        try:
            while not self._stop.is_set() and time.time() < deadline:
                for on_secs, off_secs in pattern.on_off:
                    if self._stop.is_set() or time.time() >= deadline:
                        break
                    self.device.set_speaker_route(True)
                    time.sleep(0.05)
                    tone = self._get_tone(pattern.freq_a, pattern.freq_b, on_secs)
                    proc = subprocess.Popen(
                        ["paplay", "--device", PA_DEVICE, str(tone)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    while proc.poll() is None:
                        if self._stop.is_set():
                            proc.terminate()
                            break
                        time.sleep(0.05)
                    self.device.set_speaker_route(False)
                    off_end = time.time() + off_secs
                    while time.time() < off_end and not self._stop.is_set():
                        time.sleep(0.1)
        finally:
            self.device.set_speaker_route(False)
            log.info("ring end")
            if self.on_finished:
                try:
                    self.on_finished()
                except Exception as e:
                    log.exception("on_finished callback error: %s", e)
