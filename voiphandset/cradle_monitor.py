"""Poll the device's `byte[2]` cradle-state flag.

The HID interrupt endpoint only reports cradle events in some
sequences (e.g. `0x40` only after red-hangup was pressed). To detect
simple put-the-handset-back-in-the-cradle without any prior button
press, we periodically read the 64-byte feature report and watch
`byte[2]` (the cradle/big-N flag byte):

    0x00 — handset in cradle
    0x01 — handset off cradle
    0x02 — big-N currently pressed

Bit 0 of byte[2] is the cradle indicator, so we mask with `0x01`.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable

from voiphandset.device import Device

log = logging.getLogger("voiphandset.cradle")

POLL_INTERVAL_SEC = 0.5


class CradleMonitor(threading.Thread):
    def __init__(self, device: Device, on_change: Callable[[bool], None]):
        super().__init__(daemon=True, name="cradle-monitor")
        self.device = device
        self.on_change = on_change
        self._stop = threading.Event()
        self._last_lifted: bool | None = None

    def stop(self):
        self._stop.set()

    def run(self):
        log.info("cradle monitor started (polling every %.1fs)", POLL_INTERVAL_SEC)
        while not self._stop.is_set():
            try:
                state = self.device.get_state_dump()
                if len(state) >= 3:
                    lifted = bool(state[2] & 0x01)
                    if lifted != self._last_lifted:
                        self._last_lifted = lifted
                        log.info("cradle state changed: %s",
                                 "lifted" if lifted else "cradled")
                        try:
                            self.on_change(lifted)
                        except Exception as e:
                            log.exception("on_change handler failed: %s", e)
            except Exception as e:
                # USB control transfer can race with HID reads; just retry next tick
                log.debug("cradle poll error: %s", e)
            self._stop.wait(POLL_INTERVAL_SEC)
        log.info("cradle monitor stopped")
