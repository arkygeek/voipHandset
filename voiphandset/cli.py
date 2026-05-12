"""Command-line interface: `handset` script.

Subcommands:
    handset ring [pattern] [cycles]    # play a ring pattern (us | uk | bell)
    handset speakerphone on|off|toggle # toggle base-speaker mode for system audio
    handset state                      # show current daemon state
    handset stop-ring                  # stop a ring in progress
    handset daemon                     # run the daemon in the foreground
    handset reset                      # reset all device LEDs / route
"""
from __future__ import annotations

import argparse
import sys

import dbus

from voiphandset import DBUS_NAME, DBUS_PATH, DBUS_IFACE


def _proxy():
    bus = dbus.SessionBus()
    try:
        obj = bus.get_object(DBUS_NAME, DBUS_PATH)
    except dbus.exceptions.DBusException as e:
        sys.exit(f"error: daemon not reachable on D-Bus ({e}). Is handset-daemon running?")
    return dbus.Interface(obj, DBUS_IFACE)


def cmd_ring(args):
    p = _proxy()
    p.Ring(args.pattern, args.cycles)


def cmd_stop_ring(args):
    _proxy().StopRing()


def cmd_speakerphone(args):
    p = _proxy()
    if args.mode == "on":
        p.SetSpeakerphone(True)
    elif args.mode == "off":
        p.SetSpeakerphone(False)
    elif args.mode == "toggle":
        current = bool(p.GetSpeakerphone())
        p.SetSpeakerphone(not current)
    print("speakerphone:", "on" if p.GetSpeakerphone() else "off")


def cmd_state(args):
    s = _proxy().GetState()
    for k, v in s.items():
        print(f"  {k}: {v}")


def cmd_daemon(args):
    # Run the daemon directly (used by systemd unit)
    from voiphandset import daemon as d
    d.main()


def cmd_reset(args):
    _proxy().Reset()


def main():
    p = argparse.ArgumentParser(prog="handset", description="HP Internet Handset control")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("ring", help="play a ring pattern through the base speaker")
    r.add_argument("pattern", nargs="?", default="us", choices=["us", "uk", "bell"])
    r.add_argument("cycles", nargs="?", type=int, default=3)
    r.set_defaults(func=cmd_ring)

    sub.add_parser("stop-ring", help="stop a ring in progress").set_defaults(func=cmd_stop_ring)

    sp = sub.add_parser("speakerphone", help="toggle base-speaker as system audio")
    sp.add_argument("mode", choices=["on", "off", "toggle"])
    sp.set_defaults(func=cmd_speakerphone)

    sub.add_parser("state", help="show current daemon state").set_defaults(func=cmd_state)
    sub.add_parser("daemon", help="run the daemon (foreground)").set_defaults(func=cmd_daemon)
    sub.add_parser("reset", help="reset device LEDs and audio route").set_defaults(func=cmd_reset)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
