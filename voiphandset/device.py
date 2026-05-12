"""HID device wrapper and feature-report helpers.

The 1-byte HID Feature Report (Usage 4) is a bitfield:
    bit 0 (0x01) — audio route: 1=base speaker, 0=handset earpiece
    bit 4 (0x10) — blue handset LED
    bit 6 (0x40) — blue mute button LED
"""
from __future__ import annotations

import logging
import threading

import hid

from voiphandset import VID, PID

log = logging.getLogger("voiphandset.device")

BIT_SPEAKER_ROUTE = 0x01
BIT_HANDSET_LED = 0x10
BIT_MUTE_LED = 0x40

# HID input report codes (byte[1] of the 2-byte report) — most-used events
HID_HANDSET_REMOVED = 0x41
HID_BIG_N_LIFTED = 0x3D
HID_RED_HANGUP_PRESSED = 0x43
HID_HANDSET_INTO_CRADLE = 0x40
HID_BIG_N_PRESSED_CRADLE = 0x3E
HID_HANDSET_LIFTED_CODES = {HID_HANDSET_REMOVED, HID_BIG_N_LIFTED}

# Volume + mute (on the base unit / handset)
HID_VOL_UP_PRESSED = 0x3B       # auto-repeats while held
HID_VOL_UP_RELEASED = 0x39
HID_VOL_DOWN_PRESSED = 0x4F     # auto-repeats while held
HID_VOL_DOWN_RELEASED = 0x4D
HID_MUTE_PRESSED = 0x47
HID_MUTE_RELEASED = 0x45


class Device:
    """Thread-safe HID Feature-Report manager."""

    def __init__(self):
        self._hid = hid.Device(VID, PID)
        self._lock = threading.Lock()
        self._feature_byte = 0x00

    def close(self):
        self.reset()
        try:
            self._hid.close()
        except Exception:
            pass

    @property
    def manufacturer(self) -> str:
        return self._hid.manufacturer or "?"

    @property
    def product(self) -> str:
        return self._hid.product or "?"

    def read_event(self, timeout_ms: int = 500) -> int | None:
        """Read one HID input report. Returns byte[1] of the report (the event code) or None."""
        buf = self._hid.read(8, timeout=timeout_ms)
        if not buf:
            return None
        return buf[1]

    def get_feature_byte(self) -> int:
        with self._lock:
            return self._feature_byte

    def _write_feature(self):
        try:
            self._hid.send_feature_report(bytes([0x00, self._feature_byte]))
        except Exception as e:
            log.warning("feature write failed: %s", e)

    def set_bit(self, mask: int, on: bool, force_write: bool = False):
        with self._lock:
            new = (self._feature_byte | mask) if on else (self._feature_byte & ~mask)
            if new == self._feature_byte and not force_write:
                return
            self._feature_byte = new
            self._write_feature()

    def set_speaker_route(self, base: bool, force: bool = False):
        """True = USB audio routes to base speaker; False = handset earpiece.

        Pass force=True to write even if our cached feature byte already has
        the bit in the desired state — useful when the device's actual state
        may have drifted from ours (e.g., after a USB reset or external write).
        """
        self.set_bit(BIT_SPEAKER_ROUTE, base, force_write=force)

    def set_handset_led(self, on: bool):
        self.set_bit(BIT_HANDSET_LED, on)

    def set_mute_led(self, on: bool):
        self.set_bit(BIT_MUTE_LED, on)

    def reset(self):
        with self._lock:
            self._feature_byte = 0x00
            self._write_feature()

    def get_state_dump(self) -> bytes:
        """Read the 64-byte device state for debugging."""
        return bytes(self._hid.get_feature_report(0, 64))
