"""HP Internet Handset — drive the base unit ringer.

The base unit has a piezo speaker driven by bit 0 of the HID Feature
Report (Usage 4). Each transition of bit 0 produces one click. Rapid
toggling produces an audible buzz.

Other feature report bits:
    bit 0 (0x01) — base unit piezo ringer
    bit 4 (0x10) — blue handset LED
    bit 6 (0x40) — blue mute button LED
"""
import hid
import time

VID = 0x03F0
PID = 0x1C07


def open_device():
    return hid.Device(VID, PID)


def buzz(device, duration, buzz_hz=40):
    """Drive the piezo for `duration` seconds at `buzz_hz`."""
    half = 1.0 / (buzz_hz * 2)
    end = time.time() + duration
    while time.time() < end:
        device.send_feature_report(bytes([0x00, 0x01]))
        time.sleep(half)
        device.send_feature_report(bytes([0x00, 0x00]))
        time.sleep(half)
    device.send_feature_report(bytes([0x00, 0x00]))


def ring(device, pattern="classic", cycles=3):
    """Ring with a named pattern.

    Patterns:
        classic — 2s buzz, 4s silence (North American)
        uk      — 0.4s buzz, 0.2s gap, 0.4s buzz, 2s silence
        short   — 1s buzz, 1s silence
    """
    if pattern == "classic":
        on_off = [(2.0, 4.0)]
    elif pattern == "uk":
        on_off = [(0.4, 0.2), (0.4, 2.0)]
    elif pattern == "short":
        on_off = [(1.0, 1.0)]
    else:
        raise ValueError(f"unknown pattern: {pattern}")

    for _ in range(cycles):
        for on_secs, off_secs in on_off:
            buzz(device, on_secs)
            time.sleep(off_secs)


if __name__ == "__main__":
    import sys
    pattern = sys.argv[1] if len(sys.argv) > 1 else "classic"
    cycles = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    d = open_device()
    try:
        ring(d, pattern, cycles)
    finally:
        d.send_feature_report(bytes([0x00, 0x00]))
        d.close()
