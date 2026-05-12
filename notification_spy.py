"""Capture all desktop notifications going through D-Bus.

Run this, then trigger test calls from each service (WhatsApp, Messenger,
etc.) while it's running. It writes one JSON object per notification to
notifications.jsonl, which we then read to build matching rules for the
handset ring daemon.

Uses the D-Bus BecomeMonitor API (modern replacement for eavesdrop=true).
Stop with Ctrl-C.
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

LOG_PATH = Path(__file__).resolve().parent / "notifications.jsonl"


def decode(value):
    if isinstance(value, dbus.String):
        return str(value)
    if isinstance(value, (dbus.Int16, dbus.Int32, dbus.Int64,
                          dbus.UInt16, dbus.UInt32, dbus.UInt64,
                          dbus.Byte, dbus.Boolean)):
        return int(value) if not isinstance(value, dbus.Boolean) else bool(value)
    if isinstance(value, dbus.Double):
        return float(value)
    if isinstance(value, dbus.Array):
        return [decode(v) for v in value]
    if isinstance(value, dbus.Dictionary):
        return {str(k): decode(v) for k, v in value.items()}
    if isinstance(value, dbus.Struct):
        return [decode(v) for v in value]
    return str(value)


def on_message(_bus, message):
    if message.get_member() != "Notify":
        return
    if message.get_interface() != "org.freedesktop.Notifications":
        return
    args = message.get_args_list()
    if len(args) < 8:
        return
    # Notify signature: susssasa{sv}i
    # (app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout)
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "sender": message.get_sender(),
        "app_name": str(args[0]),
        "replaces_id": int(args[1]),
        "app_icon": str(args[2]),
        "summary": str(args[3]),
        "body": str(args[4]),
        "actions": [str(a) for a in args[5]],
        "hints": decode(args[6]),
        "expire_timeout": int(args[7]),
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    # Brief console summary
    print(f"  [{record['ts']}] {record['app_name']!r} | {record['summary']!r} | {record['body'][:60]!r}",
          flush=True)


def main():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    bus_proxy = bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus")
    monitor_iface = dbus.Interface(bus_proxy, "org.freedesktop.DBus.Monitoring")
    try:
        monitor_iface.BecomeMonitor(
            ["interface='org.freedesktop.Notifications',member='Notify'"],
            dbus.UInt32(0),
        )
    except dbus.exceptions.DBusException as e:
        print(f"BecomeMonitor failed: {e}", file=sys.stderr)
        print("Falling back to eavesdrop match rule (may require permissive D-Bus policy)",
              file=sys.stderr)
        bus.add_match_string(
            "eavesdrop=true,interface='org.freedesktop.Notifications',member='Notify'"
        )

    bus.add_message_filter(on_message)

    print(f"Listening for desktop notifications. Logging to {LOG_PATH}", flush=True)
    print("Trigger test calls now — press Ctrl-C when done.", flush=True)
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
