"""Audio routing coordinator and call-state machine.

Routing decision priority (highest first):
    1. Active call on handset (HANDSET state) -> earpiece
    2. Active call on speakerphone (SPEAKERPHONE) -> base
    3. Ring playing (RINGING) -> base
    4. PipeWire stream on speakerphone virtual sink -> base
    5. User-set speakerphone preference -> base
    6. Default (IDLE) -> follows cradle: cradled=base, lifted=earpiece

Call state transitions (events come from HID + ring engine):
    IDLE --ring start--> RINGING
    RINGING --ring stop / missed--> IDLE
    RINGING --handset lifted--> HANDSET
    HANDSET --hold pressed--> HOLDING
    HOLDING --handset cradled--> SPEAKERPHONE
    HOLDING --hold pressed again / timeout--> HANDSET
    HANDSET --cradled (no hold)--> IDLE (hang up)
    HANDSET --red hangup--> IDLE
    SPEAKERPHONE --big-N off-cradle pressed--> IDLE (hang up)
    SPEAKERPHONE --handset lifted--> HANDSET
"""
from __future__ import annotations

import enum
import logging
import threading
import time
from typing import Callable

from voiphandset.device import (
    Device,
    HID_HANDSET_REMOVED,
    HID_BIG_N_LIFTED,
    HID_RED_HANGUP_PRESSED,
    HID_HANDSET_INTO_CRADLE,
)

log = logging.getLogger("voiphandset.routing")

HID_HOLD_PRESSED = 0x4B
HID_BIG_N_OFF_CRADLE_PRESSED = 0x3F
HID_GREEN_DIAL_PRESSED = 0x37

HOLD_INTENT_TIMEOUT_SEC = 5.0  # hold-then-cradle window


class CallState(enum.Enum):
    IDLE = "idle"
    RINGING = "ringing"
    HANDSET = "handset"
    HOLDING = "holding"
    SPEAKERPHONE = "speakerphone"


class Router:
    def __init__(self, device: Device,
                 on_state_change: Callable[[CallState], None] | None = None):
        self.device = device
        self._lock = threading.RLock()

        # External preference flags
        self._user_speakerphone = False
        self._pipewire_active = False

        # Call state machine
        self._state = CallState.IDLE

        # Physical state from HID
        self._handset_lifted = False
        self._hold_pressed_at: float | None = None

        self._on_state_change = on_state_change

    # ------------------------------------------------------------------ inputs

    def set_user_speakerphone(self, on: bool):
        with self._lock:
            if self._user_speakerphone == on:
                return
            log.info("user speakerphone %s", "ON" if on else "OFF")
            self._user_speakerphone = on
            self._apply()

    def set_pipewire_active(self, on: bool):
        with self._lock:
            if self._pipewire_active == on:
                return
            log.info("pipewire stream %s", "active" if on else "idle")
            self._pipewire_active = on
            self._apply()

    def on_ring_start(self):
        with self._lock:
            if self._state == CallState.IDLE:
                self._transition(CallState.RINGING)

    def on_ring_stop(self):
        with self._lock:
            if self._state == CallState.RINGING:
                self._transition(CallState.IDLE)

    def on_hid_event(self, code: int):
        with self._lock:
            if code in (HID_HANDSET_REMOVED, HID_BIG_N_LIFTED):
                self._handset_lifted = True
                log.debug("HID: handset lifted")
                if self._state == CallState.RINGING:
                    self._transition(CallState.HANDSET)
                elif self._state == CallState.SPEAKERPHONE:
                    self._transition(CallState.HANDSET)
                self._apply()
            elif code == HID_HANDSET_INTO_CRADLE:
                self._handset_lifted = False
                log.debug("HID: handset docked")
                if self._state == CallState.HOLDING:
                    self._transition(CallState.SPEAKERPHONE)
                elif self._state == CallState.HANDSET:
                    # Cradled without hold -> hang up
                    self._transition(CallState.IDLE)
                self._apply()
            elif code == HID_HOLD_PRESSED:
                if self._state in (CallState.HANDSET, CallState.HOLDING):
                    log.debug("HID: hold pressed -> HOLDING")
                    self._hold_pressed_at = time.time()
                    self._transition(CallState.HOLDING)
                    self._apply()
            elif code == HID_RED_HANGUP_PRESSED:
                if self._state in (CallState.HANDSET, CallState.HOLDING, CallState.SPEAKERPHONE):
                    log.debug("HID: red hangup")
                    self._transition(CallState.IDLE)
                    self._apply()
            elif code == HID_BIG_N_OFF_CRADLE_PRESSED:
                if self._state == CallState.SPEAKERPHONE:
                    log.debug("HID: big-N -> end speakerphone call")
                    self._transition(CallState.IDLE)
                    self._apply()
            elif code == HID_GREEN_DIAL_PRESSED:
                if self._state == CallState.IDLE:
                    log.debug("HID: green dial -> outgoing call (assumed)")
                    self._transition(CallState.HANDSET)
                    self._apply()

    # ------------------------------------------------------------------ output

    def set_handset_lifted_initial(self, lifted: bool):
        """Seed the initial physical state on daemon startup."""
        with self._lock:
            self._handset_lifted = lifted
            self._apply()

    def on_cradle_change(self, lifted: bool):
        """Authoritative cradle-state update from polling.

        Does the same call-state transitions that the HID input event
        handlers would do — but driven by polled byte[2] instead of
        the unreliable HID 0x40 / 0x41 / 0x3D / 0x3F events. Without
        this, a handset that got into HANDSET state (e.g. via a green-dial
        press) would never transition back to IDLE on cradle-down,
        leaving the route stuck on earpiece.
        """
        with self._lock:
            if lifted == self._handset_lifted:
                return  # no change
            self._handset_lifted = lifted
            log.info("cradle: %s (poll)", "lifted" if lifted else "cradled")

            if lifted:
                # Lifting during ringing answers; lifting from speakerphone
                # returns the call to the earpiece.
                if self._state in (CallState.RINGING, CallState.SPEAKERPHONE):
                    self._transition(CallState.HANDSET)
            else:
                # Cradling: HOLDING → SPEAKERPHONE (hands-free), HANDSET → IDLE (hang up)
                if self._state == CallState.HOLDING:
                    self._transition(CallState.SPEAKERPHONE)
                elif self._state == CallState.HANDSET:
                    self._transition(CallState.IDLE)

            self._apply()

    def get_state(self) -> dict:
        with self._lock:
            return {
                "call_state": self._state.value,
                "user_speakerphone": self._user_speakerphone,
                "pipewire_active": self._pipewire_active,
                "handset_lifted": self._handset_lifted,
                "effective_base": self._compute_route(),
            }

    # ------------------------------------------------------------------ internal

    def _compute_route(self) -> bool:
        """Decide whether bit 0 (base speaker) should be on."""
        if self._state == CallState.HANDSET:
            return False
        if self._state == CallState.HOLDING:
            return False
        if self._state == CallState.SPEAKERPHONE:
            return True
        if self._state == CallState.RINGING:
            return True
        # IDLE
        if self._user_speakerphone:
            return True
        if self._pipewire_active:
            return True
        # Default in IDLE: follow cradle (cradled = base, lifted = earpiece)
        return not self._handset_lifted

    def _apply(self):
        route_to_base = self._compute_route()
        # force=True: always write to device. The optimisation that
        # skipped no-op writes was hiding a real cache/device divergence
        # bug where re-cradle wouldn't actually flip bit 0 back to 1.
        self.device.set_speaker_route(route_to_base, force=True)

    def _transition(self, new_state: CallState):
        if new_state == self._state:
            return
        log.info("call state: %s -> %s", self._state.value, new_state.value)
        self._state = new_state
        if new_state != CallState.HOLDING:
            self._hold_pressed_at = None
        if self._on_state_change:
            try:
                self._on_state_change(new_state)
            except Exception as e:
                log.exception("state change callback failed: %s", e)
