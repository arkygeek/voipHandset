"""HP Internet Handset daemon: ring on incoming Rambox calls.

Listens for desktop notifications via D-Bus and rings the handset's
base speaker with a chosen pattern when a call notification matches.
Lifting the handset off the cradle or pressing red-hangup stops the
ring. Rings stop automatically when a "Missed call" notification
arrives or after RING_TIMEOUT_SEC.

Rules (compiled in at the top of this file — edit to taste):
  - WhatsApp call:   app=rambox, body matches voice/video call patterns -> US ring
  - WhatsApp missed: body contains "Missed" -> immediately stop any ring
  - Messenger heuristic: 3+ "Messenger / You have a new message" within 10s -> UK ring

Run with:  python3 handset_daemon.py
Or via the systemd user service (see handset-daemon.service).
"""
from __future__ import annotations

import logging
import re
import subprocess
import tempfile
import threading
import time
import wave
import math
import struct
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import hid

VID = 0x03F0
PID = 0x1C07
ALSA_DEVICE = "plughw:3,0"

RING_TIMEOUT_SEC = 30
MESSENGER_BURST_COUNT = 3
MESSENGER_BURST_WINDOW_SEC = 10

# HID input report bytes (second byte of the 2-byte report)
HID_HANDSET_LIFTED = {0x41, 0x3D}   # 0x41 = removed from cradle, 0x3D = big-N lifted
HID_RED_HANGUP_PRESSED = {0x43}

log = logging.getLogger("handset")


# ---------------------------------------------------------------------------
# Ring engine
# ---------------------------------------------------------------------------

@dataclass
class RingPattern:
    name: str
    freq_a: int
    freq_b: int
    on_off: list[tuple[float, float]]  # list of (on_seconds, off_seconds)


PATTERNS = {
    "us":   RingPattern("us",   440, 480, [(2.0, 4.0)]),
    "uk":   RingPattern("uk",   400, 450, [(0.4, 0.2), (0.4, 2.0)]),
    "bell": RingPattern("bell", 540, 660, [(1.0, 1.0)]),
}


def _gen_dual_tone_wav(path: Path, freq_a: int, freq_b: int, duration: float,
                      sample_rate: int = 48000, gain: float = 0.4):
    n = int(sample_rate * duration)
    fade = int(sample_rate * 0.04)
    buf = bytearray(n * 4)  # 2 channels * 2 bytes
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
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(sample_rate)
        f.writeframes(bytes(buf))


class RingEngine:
    """Plays ring patterns on the base speaker. Thread-safe stop()."""

    def __init__(self, device):
        self.device = device
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._tone_cache: dict[tuple[int, int, float], Path] = {}

    def _route_to_base(self, enable: bool):
        # bit 0 of feature report = audio route (1=base speaker, 0=handset earpiece)
        try:
            self.device.send_feature_report(bytes([0x00, 0x01 if enable else 0x00]))
        except Exception as e:
            log.warning("HID feature write failed: %s", e)

    def _get_tone(self, freq_a: int, freq_b: int, duration: float) -> Path:
        key = (freq_a, freq_b, round(duration, 2))
        if key in self._tone_cache:
            return self._tone_cache[key]
        tmp = Path(tempfile.gettempdir()) / f"handset_tone_{freq_a}_{freq_b}_{duration:.2f}.wav"
        if not tmp.exists():
            _gen_dual_tone_wav(tmp, freq_a, freq_b, duration)
        self._tone_cache[key] = tmp
        return tmp

    def is_ringing(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self, pattern: RingPattern, max_duration: float = RING_TIMEOUT_SEC):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                log.debug("already ringing, ignoring new start")
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, args=(pattern, max_duration), daemon=True)
            self._thread.start()

    def stop(self, reason: str = ""):
        with self._lock:
            if self._thread is None:
                return
            log.info("stop ring (%s)", reason)
            self._stop.set()
            t = self._thread
        # join outside lock
        t.join(timeout=3)
        with self._lock:
            self._thread = None
        self._route_to_base(False)

    def _run(self, pattern: RingPattern, max_duration: float):
        log.info("ring start: pattern=%s timeout=%ss", pattern.name, max_duration)
        deadline = time.time() + max_duration
        try:
            while not self._stop.is_set() and time.time() < deadline:
                for on_secs, off_secs in pattern.on_off:
                    if self._stop.is_set() or time.time() >= deadline:
                        break
                    self._route_to_base(True)
                    time.sleep(0.05)
                    tone = self._get_tone(pattern.freq_a, pattern.freq_b, on_secs)
                    # play via aplay; check stop frequently
                    proc = subprocess.Popen(
                        ["aplay", "-q", "-D", ALSA_DEVICE, str(tone)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    while proc.poll() is None:
                        if self._stop.is_set():
                            proc.terminate()
                            break
                        time.sleep(0.05)
                    self._route_to_base(False)
                    # off period — check stop frequently
                    off_end = time.time() + off_secs
                    while time.time() < off_end and not self._stop.is_set():
                        time.sleep(0.1)
        finally:
            self._route_to_base(False)
            log.info("ring end")


# ---------------------------------------------------------------------------
# HID listener
# ---------------------------------------------------------------------------

class HIDListener(threading.Thread):
    """Reads HID events; calls on_event(code) for every non-idle event."""

    def __init__(self, device, on_event: Callable[[int], None]):
        super().__init__(daemon=True, name="hid-listener")
        self.device = device
        self.on_event = on_event
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        log.info("HID listener started")
        while not self._stop.is_set():
            try:
                buf = self.device.read(8, timeout=500)
            except Exception as e:
                log.warning("HID read error: %s — retrying", e)
                time.sleep(1)
                continue
            if not buf:
                continue
            code = buf[1]
            if code == 0x00:
                continue
            try:
                self.on_event(code)
            except Exception as e:
                log.exception("HID handler error: %s", e)
        log.info("HID listener stopped")


# ---------------------------------------------------------------------------
# Rule matcher
# ---------------------------------------------------------------------------

@dataclass
class Notification:
    app_name: str
    summary: str
    body: str
    ts: float


@dataclass
class Rule:
    name: str
    pattern: RingPattern
    match: Callable[[Notification], bool]


class Matcher:
    """Holds rules and message history for burst-detection rules."""

    def __init__(self, ring: RingEngine):
        self.ring = ring
        self.messenger_history: deque[float] = deque()
        # Dedup: D-Bus shell relays make us see each notification twice
        self._recent_keys: deque[tuple[str, str, str, float]] = deque(maxlen=20)
        self.rules: list[Rule] = self._build_rules()

    def _build_rules(self) -> list[Rule]:
        whatsapp_call_re = re.compile(r"(incoming|missed).*(voice|video) call", re.I)
        whatsapp_missed_re = re.compile(r"missed (voice|video) call", re.I)

        def is_whatsapp_call(n: Notification) -> bool:
            return n.app_name.lower() == "rambox" and whatsapp_call_re.search(n.body or "") is not None

        def is_messenger_burst(n: Notification) -> bool:
            if n.app_name.lower() != "rambox":
                return False
            if n.summary != "Messenger":
                return False
            now = n.ts
            self.messenger_history.append(now)
            # drop entries outside the window
            while self.messenger_history and now - self.messenger_history[0] > MESSENGER_BURST_WINDOW_SEC:
                self.messenger_history.popleft()
            if len(self.messenger_history) >= MESSENGER_BURST_COUNT:
                self.messenger_history.clear()
                return True
            return False

        return [
            Rule("WhatsApp call", PATTERNS["us"], is_whatsapp_call),
            Rule("Messenger burst", PATTERNS["uk"], is_messenger_burst),
        ]

    def is_call_ended_notification(self, n: Notification) -> bool:
        # Auto-stop on missed-call (no need to keep ringing)
        if n.app_name.lower() == "rambox" and re.search(r"missed (voice|video) call", n.body or "", re.I):
            return True
        return False

    def handle(self, n: Notification):
        key = (n.app_name, n.summary, n.body, round(n.ts, 1))
        if key in self._recent_keys:
            return  # already handled (dup from shell relay)
        self._recent_keys.append(key)

        log.info("notif: app=%r summary=%r body=%r", n.app_name, n.summary, n.body)

        if self.is_call_ended_notification(n):
            self.ring.stop("missed-call notification")
            return

        for rule in self.rules:
            if rule.match(n):
                log.info("match: %s -> pattern %s", rule.name, rule.pattern.name)
                self.ring.start(rule.pattern)
                return


# ---------------------------------------------------------------------------
# D-Bus listener
# ---------------------------------------------------------------------------

class DBusNotificationListener:
    def __init__(self, on_notification: Callable[[Notification], None]):
        self.on_notification = on_notification

    def install(self, bus):
        bus_proxy = bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus")
        monitor_iface = dbus.Interface(bus_proxy, "org.freedesktop.DBus.Monitoring")
        try:
            monitor_iface.BecomeMonitor(
                ["interface='org.freedesktop.Notifications',member='Notify'"],
                dbus.UInt32(0),
            )
        except dbus.exceptions.DBusException as e:
            log.warning("BecomeMonitor failed: %s — falling back to eavesdrop", e)
            bus.add_match_string(
                "eavesdrop=true,interface='org.freedesktop.Notifications',member='Notify'"
            )
        bus.add_message_filter(self._on_message)

    def _on_message(self, _bus, message):
        if message.get_member() != "Notify":
            return
        if message.get_interface() != "org.freedesktop.Notifications":
            return
        args = message.get_args_list()
        if len(args) < 5:
            return
        n = Notification(
            app_name=str(args[0]),
            summary=str(args[3]),
            body=str(args[4]),
            ts=time.time(),
        )
        try:
            self.on_notification(n)
        except Exception as e:
            log.exception("notification handler error: %s", e)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    device = hid.Device(VID, PID)
    log.info("Opened HID device %s — %s", device.manufacturer, device.product)

    ring = RingEngine(device)
    matcher = Matcher(ring)

    def on_hid(code: int):
        if code in HID_HANDSET_LIFTED:
            if ring.is_ringing():
                ring.stop("handset lifted")
        elif code in HID_RED_HANGUP_PRESSED:
            if ring.is_ringing():
                ring.stop("red-hangup pressed")

    hid_listener = HIDListener(device, on_hid)
    hid_listener.start()

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    listener = DBusNotificationListener(matcher.handle)
    listener.install(bus)

    log.info("Daemon running. Ctrl-C to exit.")
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        log.info("Shutdown")
    finally:
        ring.stop("shutdown")
        hid_listener.stop()
        device.close()


if __name__ == "__main__":
    main()
