# voiphandset — Linux driver for HP Internet Handset (G9)

User-space driver for the Hewlett-Packard Internet Handset (USB
`03f0:1c07`). Turns this circa-2007 USB phone into a useful Linux
peripheral: the **base unit's 1W speaker** is exposed as a system audio
output, and the device rings on incoming Rambox calls (WhatsApp /
Messenger).

## What it does

- **`HP Handset (Speakerphone)`** appears as a regular audio output in
  your GNOME sound menu. Selecting it routes audio to the base unit's
  1W speaker instead of the handset earpiece.
- **Auto-route by cradle position** for IDLE state: handset in cradle
  ⇒ audio plays from the base speaker, handset lifted ⇒ audio plays
  from the earpiece.
- **Rings on incoming calls** from Rambox: WhatsApp calls trigger a
  classic US dual-tone ring (440+480 Hz, 2 s on / 4 s off); Messenger
  calls use a UK trill pattern.
- **Phone-like call state machine**: lift to answer, cradle to hang up;
  press HOLD then cradle for hands-free; big-N off-cradle to end a
  hands-free call.

## Install

Build deps:

```sh
sudo apt-get install -y debhelper dh-python pybuild-plugin-pyproject \
  python3-hid python3-dbus python3-gi python3-setuptools \
  libhidapi-hidraw0 pulseaudio-utils
```

Build and install:

```sh
dpkg-buildpackage -us -uc -b -d
sudo dpkg -i ../voiphandset_0.2.2-1_all.deb
```

Activate (per user):

```sh
sudo usermod -aG plugdev $USER          # one time; log out + in after
systemctl --user daemon-reload
systemctl --user enable --now handset-daemon.service
systemctl --user restart pipewire pipewire-pulse wireplumber   # picks up the speakerphone virtual sink
```

## Use

CLI:

```sh
handset state                      # show daemon state
handset ring [us|uk|bell] [cycles] # play a ring through the base speaker
handset stop-ring                  # cancel an in-progress ring
handset speakerphone on|off|toggle # force base-speaker mode for system audio
handset reset                      # clear all LEDs and reset audio route
```

Audio menu: pick **"HP Handset (Speakerphone)"** as your output to send
system audio to the base speaker.

## Architecture

- `voiphandset.device` — HID wrapper. Feature-report bits:
  - bit 0 (`0x01`) — audio route (1 = base speaker, 0 = handset earpiece)
  - bit 4 (`0x10`) — blue handset LED
  - bit 6 (`0x40`) — blue mute button LED
- `voiphandset.ring` — dual-tone ring generator + playback via PipeWire
- `voiphandset.routing` — call-state machine + route arbitration
- `voiphandset.pipewire_monitor` — polls `pw-dump` for streams attached to
  the `handset_speakerphone` virtual sink and flips the route bit
- `voiphandset.daemon` — runs the above plus a D-Bus notification listener
  for incoming-call detection; exposes `com.arkygeek.Handset` IPC for the CLI

## Files installed

| Path | Purpose |
|---|---|
| `/usr/bin/handset` | CLI |
| `/usr/lib/python3/dist-packages/voiphandset/` | Python package |
| `/usr/lib/systemd/user/handset-daemon.service` | systemd user service |
| `/usr/share/pipewire/pipewire.conf.d/60-handset-speakerphone.conf` | PipeWire virtual sink |
| `/lib/udev/rules.d/99-hp-handset.rules` | hidraw access for `plugdev` |
