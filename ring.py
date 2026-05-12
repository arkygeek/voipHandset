"""HP Internet Handset — ring the base unit speaker with real audio.

The HID Feature Report (Usage 4) is a bitfield where bit 0 routes the
USB audio stream to the base unit's 1W speaker. With bit 0 set, any
audio played to the device's ALSA card (USB Audio Class) comes out of
the base speaker at full ringer volume. With bit 0 clear, audio goes
to the handset earpiece (normal mode).

Other feature report bits:
    bit 0 (0x01) — routes USB audio to base speaker (speakerphone/ringer mode)
    bit 4 (0x10) — blue handset LED
    bit 6 (0x40) — blue mute button LED
"""
import hid
import subprocess
import tempfile
import time
import wave
import math
import struct

VID = 0x03F0
PID = 0x1C07
ALSA_DEVICE = "plughw:3,0"  # ALSA device for the HP Internet Handset


def open_device():
    return hid.Device(VID, PID)


def set_speaker_route(device, enable):
    """Route USB audio to base speaker (True) or handset earpiece (False)."""
    device.send_feature_report(bytes([0x00, 0x01 if enable else 0x00]))


def _gen_dual_tone(freq_a, freq_b, duration, sample_rate=48000, gain=0.4):
    n = int(sample_rate * duration)
    fade = int(sample_rate * 0.04)
    out = bytearray()
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
        # stereo
        out += struct.pack("<hh", sample, sample)
    return bytes(out), sample_rate


def _write_wav(filename, pcm_bytes, sample_rate, channels=2):
    with wave.open(filename, "wb") as f:
        f.setnchannels(channels)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(pcm_bytes)


def ring(device, pattern="us", cycles=3, freqs=None):
    """Ring the base speaker with a real dual-tone ring.

    Patterns (frequency pair, on-seconds, off-seconds):
        us   — 440+480 Hz, 2 s on, 4 s off
        uk   — 400+450 Hz, (0.4, 0.2, 0.4, 2.0) trill
        bell — 540+660 Hz, 1 s on, 1 s off

    `freqs` lets the caller override the (freq_a, freq_b) pair.
    """
    if pattern == "us":
        fa, fb = 440, 480
        on_off = [(2.0, 4.0)]
    elif pattern == "uk":
        fa, fb = 400, 450
        on_off = [(0.4, 0.2), (0.4, 2.0)]
    elif pattern == "bell":
        fa, fb = 540, 660
        on_off = [(1.0, 1.0)]
    else:
        raise ValueError(f"unknown pattern: {pattern}")

    if freqs:
        fa, fb = freqs

    # Generate the longest on-tone once and reuse
    max_on = max(on for on, _ in on_off)
    pcm, sr = _gen_dual_tone(fa, fb, max_on)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    _write_wav(tmp.name, pcm, sr)
    tmp.close()

    try:
        for _ in range(cycles):
            for on_secs, off_secs in on_off:
                set_speaker_route(device, True)
                time.sleep(0.05)  # let the routing switch settle
                if abs(on_secs - max_on) < 0.01:
                    subprocess.run(["aplay", "-q", "-D", ALSA_DEVICE, tmp.name],
                                   check=False)
                else:
                    # generate shorter tone for shorter on-period
                    pcm2, _ = _gen_dual_tone(fa, fb, on_secs)
                    tmp2 = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                    _write_wav(tmp2.name, pcm2, sr)
                    tmp2.close()
                    subprocess.run(["aplay", "-q", "-D", ALSA_DEVICE, tmp2.name],
                                   check=False)
                    import os as _os
                    _os.unlink(tmp2.name)
                set_speaker_route(device, False)
                time.sleep(off_secs)
    finally:
        import os as _os
        _os.unlink(tmp.name)
        set_speaker_route(device, False)


if __name__ == "__main__":
    import sys
    pattern = sys.argv[1] if len(sys.argv) > 1 else "us"
    cycles = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    d = open_device()
    try:
        ring(d, pattern, cycles)
    finally:
        set_speaker_route(d, False)
        d.close()
