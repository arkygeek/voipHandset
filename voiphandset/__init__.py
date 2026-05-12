"""HP Internet Handset (G9) user-space driver and daemon.

Exposes:
    voiphandset.device  — HID device wrapper (button events, feature report)
    voiphandset.ring    — Ring tone generation (dual-tone WAV)
    voiphandset.routing — Audio routing manager (handset earpiece vs base speaker)
    voiphandset.daemon  — Long-running daemon with D-Bus IPC
    voiphandset.cli     — Command-line interface (`handset` script)

Copyright (C) 2026 Jason Jorgenson <jjorgenson@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version. See LICENSE for full details.
"""

__version__ = "0.2.0"
VID = 0x03F0
PID = 0x1C07
DBUS_NAME = "com.arkygeek.Handset"
DBUS_PATH = "/com/arkygeek/Handset"
DBUS_IFACE = "com.arkygeek.Handset"
