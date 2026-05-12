"""Main daemon: HID listener + notification matcher + ring engine + PipeWire monitor + D-Bus IPC."""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from voiphandset import DBUS_NAME, DBUS_PATH, DBUS_IFACE
from voiphandset.device import Device
from voiphandset.ring import RingEngine, PATTERNS
from voiphandset.routing import Router, CallState
from voiphandset.pipewire_monitor import PipeWireMonitor

log = logging.getLogger("voiphandset.daemon")

MESSENGER_BURST_COUNT = 3
MESSENGER_BURST_WINDOW_SEC = 10


# ============================================================================
# HID input listener (thread)
# ============================================================================

class HIDListener(threading.Thread):
    def __init__(self, device: Device, on_event):
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
                code = self.device.read_event(timeout_ms=500)
            except Exception as e:
                log.warning("HID read error: %s", e)
                time.sleep(1)
                continue
            if code is None or code == 0x00:
                continue
            try:
                self.on_event(code)
            except Exception as e:
                log.exception("HID handler error: %s", e)
        log.info("HID listener stopped")


# ============================================================================
# Notification matcher
# ============================================================================

class NotificationMatcher:
    """Matches D-Bus desktop notifications against per-service ring rules."""

    def __init__(self, ring: RingEngine, router: Router):
        self.ring = ring
        self.router = router
        self.messenger_history: deque[float] = deque()
        self._recent: deque[tuple] = deque(maxlen=20)

        self._wa_any_call = re.compile(r"(incoming|missed).*(voice|video) call", re.I)
        self._wa_missed = re.compile(r"missed (voice|video) call", re.I)

    def handle(self, app_name: str, summary: str, body: str, ts: float):
        key = (app_name, summary, body, round(ts, 1))
        if key in self._recent:
            return
        self._recent.append(key)

        log.info("notif: app=%r summary=%r body=%r", app_name, summary, body)

        # Auto-stop ring on missed-call notifications
        if app_name.lower() == "rambox" and self._wa_missed.search(body):
            self.ring.stop("missed-call notification")
            self.router.on_ring_stop()
            return

        # WhatsApp incoming call
        if app_name.lower() == "rambox" and self._wa_any_call.search(body):
            log.info("match: WhatsApp call -> US ring")
            self.router.on_ring_start()
            self.ring.start(PATTERNS["us"])
            return

        # Messenger burst heuristic
        if app_name.lower() == "rambox" and summary == "Messenger":
            now = ts
            self.messenger_history.append(now)
            while self.messenger_history and now - self.messenger_history[0] > MESSENGER_BURST_WINDOW_SEC:
                self.messenger_history.popleft()
            if len(self.messenger_history) >= MESSENGER_BURST_COUNT:
                self.messenger_history.clear()
                log.info("match: Messenger burst -> UK ring")
                self.router.on_ring_start()
                self.ring.start(PATTERNS["uk"])


# ============================================================================
# D-Bus listener for notifications
# ============================================================================

class NotificationListener:
    def __init__(self, on_notification):
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
            log.warning("BecomeMonitor failed (%s); using eavesdrop match rule", e)
            bus.add_match_string(
                "eavesdrop=true,interface='org.freedesktop.Notifications',member='Notify'"
            )
        bus.add_message_filter(self._on_msg)

    def _on_msg(self, _bus, message):
        if message.get_member() != "Notify":
            return
        if message.get_interface() != "org.freedesktop.Notifications":
            return
        args = message.get_args_list()
        if len(args) < 5:
            return
        self.on_notification(str(args[0]), str(args[3]), str(args[4]), time.time())


# ============================================================================
# D-Bus IPC interface (so CLI can talk to running daemon)
# ============================================================================

class HandsetService(dbus.service.Object):
    def __init__(self, bus, daemon: "Daemon"):
        super().__init__(bus, DBUS_PATH)
        self.daemon = daemon

    @dbus.service.method(DBUS_IFACE, in_signature="b", out_signature="")
    def SetSpeakerphone(self, on):
        self.daemon.router.set_user_speakerphone(bool(on))

    @dbus.service.method(DBUS_IFACE, in_signature="", out_signature="b")
    def GetSpeakerphone(self):
        return self.daemon.router.get_state()["user_speakerphone"]

    @dbus.service.method(DBUS_IFACE, in_signature="", out_signature="a{sv}")
    def GetState(self):
        s = self.daemon.router.get_state()
        return {k: dbus.Boolean(v) if isinstance(v, bool) else dbus.String(str(v))
                for k, v in s.items()}

    @dbus.service.method(DBUS_IFACE, in_signature="sn", out_signature="")
    def Ring(self, pattern, cycles):
        p = PATTERNS.get(str(pattern), PATTERNS["us"])
        self.daemon.router.on_ring_start()
        self.daemon.ring.start(p, max_duration=int(cycles) * 6 if int(cycles) > 0 else 30)

    @dbus.service.method(DBUS_IFACE, in_signature="", out_signature="")
    def StopRing(self):
        self.daemon.ring.stop("D-Bus StopRing")
        self.daemon.router.on_ring_stop()

    @dbus.service.method(DBUS_IFACE, in_signature="", out_signature="")
    def Reset(self):
        self.daemon.device.reset()


# ============================================================================
# Main daemon
# ============================================================================

class Daemon:
    def __init__(self):
        self.device = Device()
        self.ring = RingEngine(self.device, on_finished=self._on_ring_finished)
        self.router = Router(self.device, on_state_change=self._on_state_change)
        self.matcher = NotificationMatcher(self.ring, self.router)

    def _on_ring_finished(self):
        # Ring ended naturally — tell router so call state leaves RINGING
        self.router.on_ring_stop()

    def _on_state_change(self, new_state: CallState):
        # Stop the ring when leaving RINGING for any reason
        if new_state != CallState.RINGING and self.ring.is_ringing():
            self.ring.stop(f"state -> {new_state.value}")

    def _hid_event(self, code: int):
        # Stop ring on lift / hangup
        if code in {0x41, 0x3D, 0x43} and self.ring.is_ringing():
            self.ring.stop(f"HID 0x{code:02x}")
        self.router.on_hid_event(code)

    def run(self):
        log.info("Opened HID device %s — %s", self.device.manufacturer, self.device.product)
        self.device.reset()

        DBusGMainLoop(set_as_default=True)

        # IMPORTANT: BecomeMonitor() puts a bus connection into read-only
        # mode, so we need a SEPARATE connection for serving our own
        # interface. Use private connections (not the cached singleton).
        self._service_bus = dbus.SessionBus(private=True)
        self._bus_name = dbus.service.BusName(
            DBUS_NAME, self._service_bus, do_not_queue=True
        )
        self._service = HandsetService(self._service_bus, self)
        log.info("D-Bus service %s registered on %s",
                 DBUS_NAME, self._service_bus.get_unique_name())

        # Separate connection for notification monitoring (becomes monitor)
        self._monitor_bus = dbus.SessionBus(private=True)
        NotificationListener(self.matcher.handle).install(self._monitor_bus)

        # HID listener
        hid_listener = HIDListener(self.device, self._hid_event)
        hid_listener.start()

        # PipeWire monitor
        pw_monitor = PipeWireMonitor(self.router.set_pipewire_active)
        pw_monitor.start()

        log.info("Daemon running. Ctrl-C to exit.")
        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            log.info("shutdown")
        finally:
            self.ring.stop("shutdown")
            hid_listener.stop()
            pw_monitor.stop()
            self.device.close()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    Daemon().run()


if __name__ == "__main__":
    main()
