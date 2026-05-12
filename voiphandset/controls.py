"""Volume and mic-mute controls.

Drives PulseAudio (via `pactl`) for sink volume and source mute. Sink/
source names are discovered at runtime by grepping `pactl list short`
for "Handset" so we don't hard-code the device's serial-number-bearing
node name.

The mute LED on the device (HID feature-report bit 6, `0x40`) is kept
in sync with mute state.
"""
from __future__ import annotations

import logging
import re
import subprocess
import threading

from voiphandset.device import Device

log = logging.getLogger("voiphandset.controls")

VOLUME_STEP = "5%"


def _pactl(*args) -> tuple[int, str]:
    """Run pactl with given args. Returns (returncode, stdout)."""
    try:
        r = subprocess.run(
            ["pactl", *args], capture_output=True, text=True, timeout=4
        )
        return r.returncode, r.stdout
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        log.warning("pactl %s failed: %s", " ".join(args), e)
        return -1, ""


def _find_handset_sink() -> str | None:
    """Find the underlying HP Handset ALSA sink name.

    We deliberately skip our own `handset_speakerphone` virtual sink —
    volume changes should hit the device's actual sink so they apply
    regardless of which route bit 0 has selected.
    """
    rc, out = _pactl("list", "short", "sinks")
    if rc != 0:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            name = parts[1]
            if "Handset" in name and "speakerphone" not in name.lower():
                return name
    return None


def _find_handset_source() -> str | None:
    """Find the HP Handset ALSA input source name."""
    rc, out = _pactl("list", "short", "sources")
    if rc != 0:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            name = parts[1]
            # Want the actual mic input, not the sink's monitor source
            if "Handset" in name and ".monitor" not in name and "alsa_input" in name:
                return name
    return None


def _get_source_mute(source_name: str) -> bool | None:
    rc, out = _pactl("get-source-mute", source_name)
    if rc != 0:
        return None
    m = re.search(r"Mute:\s+(yes|no)", out, re.I)
    if not m:
        return None
    return m.group(1).lower() == "yes"


class Controls:
    def __init__(self, device: Device):
        self.device = device
        self._lock = threading.Lock()
        # Optimistic cache of mute state so the LED can react instantly;
        # corrected on next pactl query.
        self._muted: bool | None = None
        self._sync_mute_from_device()

    def _sync_mute_from_device(self):
        src = _find_handset_source()
        if src is None:
            return
        muted = _get_source_mute(src)
        if muted is None:
            return
        with self._lock:
            self._muted = muted
        self.device.set_mute_led(muted)
        log.info("mic mute state synced from PulseAudio: %s",
                 "MUTED" if muted else "live")

    def volume_up(self):
        sink = _find_handset_sink()
        if sink is None:
            log.warning("volume_up: no handset sink found")
            return
        _pactl("set-sink-volume", sink, f"+{VOLUME_STEP}")
        log.info("volume up on %s", sink)

    def volume_down(self):
        sink = _find_handset_sink()
        if sink is None:
            log.warning("volume_down: no handset sink found")
            return
        _pactl("set-sink-volume", sink, f"-{VOLUME_STEP}")
        log.info("volume down on %s", sink)

    def toggle_mute(self):
        src = _find_handset_source()
        if src is None:
            log.warning("toggle_mute: no handset source found")
            return
        _pactl("set-source-mute", src, "toggle")
        # Re-read the new state to update LED
        muted = _get_source_mute(src)
        if muted is None:
            return
        with self._lock:
            self._muted = muted
        self.device.set_mute_led(muted)
        log.info("mute toggled: now %s", "MUTED" if muted else "LIVE")

    def is_muted(self) -> bool:
        with self._lock:
            return bool(self._muted)
