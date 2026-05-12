"""HP Internet Handset (G9) user-space driver and daemon.

Exposes:
    voiphandset.device  — HID device wrapper (button events, feature report)
    voiphandset.ring    — Ring tone generation (dual-tone WAV)
    voiphandset.routing — Audio routing manager (handset earpiece vs base speaker)
    voiphandset.daemon  — Long-running daemon with D-Bus IPC
    voiphandset.cli     — Command-line interface (`handset` script)
"""

__version__ = "0.2.0"
VID = 0x03F0
PID = 0x1C07
DBUS_NAME = "com.arkygeek.Handset"
DBUS_PATH = "/com/arkygeek/Handset"
DBUS_IFACE = "com.arkygeek.Handset"
