# voiphandset

A user-space Linux driver for the **HP Internet Handset (G9)** — a USB
phone Hewlett-Packard sold around 2007 to plug into Windows-only
Skype. Turns it into a useful peripheral on modern Linux:

- the **base unit's 1 W speaker** appears in your audio menu as a regular system output
- the device **rings on incoming Rambox calls** (WhatsApp & Messenger)
- buttons, hold, hangup, and the big-N speakerphone gesture all do what they would on a real phone

Tested on **Ubuntu 24.10 / Wayland / PipeWire**. The device shows up in
USB as `03f0:1c07` and identifies as `G9 v1.0.0.0`.

---

## Status

| Subsystem | Works | Notes |
|---|---|---|
| Button input (all keys, hold, hangup, big-N, cradle events) | ✅ | Full HID map verified live |
| Audio out to handset earpiece | ✅ | Standard USB Audio Class |
| Audio out to base unit speaker (the 1 W ringer) | ✅ | Routed via HID bit 0 |
| "HP Handset (Speakerphone)" as system audio sink | ✅ | PipeWire loopback + daemon |
| Ring on incoming Rambox WhatsApp calls | ✅ | Body match on "Incoming voice/video call" |
| Ring on incoming Messenger calls | ⚠️ | Heuristic only (3 notifs in 10 s) — Messenger doesn't distinguish calls from messages |
| Cradle-aware default routing (cradled → base, lifted → earpiece) | ✅ | |
| Lift to answer / cradle to hang up / HOLD-then-cradle for hands-free | ✅ | Call-state machine in `routing.py` |
| Microphone input | ⚠️ | Works as an ALSA capture but not wired into a softphone yet |
| Voicemail LED (third LED per HP data sheet) | ❌ | Not located in the feature-report bitmap |
| Programmatic call answering in Rambox | ❌ | Rambox has no IPC for this; calls still need to be answered in the Rambox UI |

---

## Install

### From the prebuilt `.deb` (recommended)

```sh
sudo dpkg -i voiphandset_0.2.2-1_all.deb
sudo usermod -aG plugdev $USER          # one time only; log out + back in
systemctl --user daemon-reload
systemctl --user enable --now handset-daemon.service
systemctl --user restart pipewire pipewire-pulse wireplumber
```

After that, plug the handset in. The base speaker appears in
`Settings → Sound → Output` as **"HP Handset (Speakerphone)"**.

### Building the `.deb` from source

```sh
sudo apt-get install -y debhelper dh-python pybuild-plugin-pyproject \
  python3-hid python3-dbus python3-gi python3-setuptools \
  libhidapi-hidraw0 pulseaudio-utils
git clone https://github.com/arkygeek/voipHandset.git
cd voipHandset/voipHandset
dpkg-buildpackage -us -uc -b -d
sudo dpkg -i ../voiphandset_*.deb
```

### Without packaging (pip install)

The Python package is also usable standalone:

```sh
pip install --user .
sudo cp conf/99-hp-handset.rules /etc/udev/rules.d/
sudo cp conf/60-handset-speakerphone.conf /usr/share/pipewire/pipewire.conf.d/
mkdir -p ~/.config/systemd/user
cp conf/handset-daemon.service ~/.config/systemd/user/
sudo udevadm control --reload-rules && sudo udevadm trigger
systemctl --user daemon-reload
systemctl --user enable --now handset-daemon.service
systemctl --user restart pipewire pipewire-pulse wireplumber
```

---

## Use

### CLI

```
handset state                          # show current daemon state
handset ring [us|uk|bell] [cycles]     # play a ring pattern through the base speaker
handset stop-ring                      # cancel an in-progress ring
handset speakerphone on|off|toggle     # force/release the base-speaker route
handset reset                          # clear all LEDs + reset audio route
handset daemon                         # run the daemon (foreground — used by systemd)
```

State output looks like:

```
$ handset state
  call_state: idle
  user_speakerphone: 0
  pipewire_active: 0
  handset_lifted: 0
  effective_base: 1
```

`effective_base: 1` means audio is currently routed to the base
speaker. `call_state` is the high-level phone state — `idle`,
`ringing`, `handset`, `holding`, or `speakerphone`.

### Audio menu

Pick **"HP Handset (Speakerphone)"** in your GNOME sound menu to send
system audio (music, YouTube, anything) to the base unit's 1 W speaker.

When the daemon sees a stream attach to that sink, it sets the route
bit so audio actually reaches the base. When the stream goes away the
route returns to the default.

### Call behaviour

The daemon implements a phone state machine that tries to feel natural:

| Situation | Gesture | Effect |
|---|---|---|
| Phone rings | Lift the handset | Ring stops; you're on the earpiece |
| On a call (earpiece) | Cradle the handset | Call ends (hang-up) |
| On a call (earpiece) | Press HOLD, then cradle | Call switches to hands-free via base speaker |
| On a hands-free call | Press the big-N (off-cradle) button | Call ends |
| Idle (no call) | Cradle the handset | System audio routes to base speaker |
| Idle (no call) | Lift the handset | System audio routes to earpiece |

### Logs

```sh
journalctl --user -u handset-daemon.service -f
```

---

## How it works

### The discovery

The device's USB descriptor presents:

- Interface 0 — Audio Control
- Interface 1 — Audio Streaming OUT (handset earpiece or base speaker, depending on bit 0 of feature report — see below)
- Interface 2 — Audio Streaming IN (microphone)
- Interface 3 — HID (buttons, cradle events, LED/route control)

The interesting bit took some digging. The base unit's speaker is
*not* a separate audio device — the USB audio output goes to whichever
physical speaker the device's hardware route bit selects. That bit
lives in the 1-byte HID Feature Report (Usage 4 in the report descriptor):

| Bit | Mask | Function |
|---|---|---|
| 0 | `0x01` | Audio route — **1 = base speaker, 0 = handset earpiece** |
| 4 | `0x10` | Blue handset LED |
| 6 | `0x40` | Blue mute-button LED |
| 1, 2, 3, 5, 7 | — | No observable effect |

The 64-byte feature read (`get_feature_report(0, 64)`) returns a full
state dump. `byte[2]` is a status flag: `0x00` cradled, `0x01` lifted,
`0x02` big-N pressed.

Originally we assumed bit 0 drove a piezo because rapid toggles
produced loud clicks. The breakthrough was a control test that
recorded the base unit's microphone-coupled output (a headset mic
placed near the base speaker) while audio played at the same time as
bit 0 was held high: peak amplitude jumped from ~10 to ~3800. That
ruled in the routing-switch theory and ruled out the piezo one.

### Architecture

```
                   ┌────────────────────────┐
                   │   Rambox (WhatsApp,    │
                   │   Messenger via web)   │
                   └───────────┬────────────┘
                               │ org.freedesktop.Notifications
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │  handset-daemon (systemd --user)                       │
   │                                                        │
   │    NotificationListener  ──►  Matcher  ──►  RingEngine │
   │    (BecomeMonitor)            (rules)       (paplay)   │
   │                                                        │
   │    PipeWireMonitor       ──►  Router    ──►  Device    │
   │    (poll pw-dump 1 Hz)        (state    │   (HID write │
   │                                machine) │    bit 0)    │
   │    HIDListener           ──►  ─────────┘               │
   │    (HID input reports)                                 │
   │                                                        │
   │    D-Bus service: com.arkygeek.Handset                 │
   └─────────────────────┬─────────────────────┬────────────┘
                         │                     │
                         ▼                     ▼
              ┌─────────────────────┐  ┌────────────────────┐
              │ HP Internet Handset │  │  handset CLI       │
              │  HID + USB audio    │  │  (other apps)      │
              └─────────────────────┘  └────────────────────┘
```

The PipeWire loopback config registers a virtual sink named
`handset_speakerphone` whose downstream target is the handset's
underlying ALSA output. The daemon polls `pw-dump` once a second to
see whether any streams are attached to that sink, and if so, asserts
bit 0 of the feature report so audio actually arrives at the base
speaker. The CLI talks to the running daemon over D-Bus
(`com.arkygeek.Handset`) to avoid HID-device contention.

### Package layout

```
voiphandset/
├── voiphandset/
│   ├── __init__.py            # version + D-Bus constants
│   ├── device.py              # HID device wrapper, feature-report bits
│   ├── ring.py                # Dual-tone WAV gen, playback via PipeWire
│   ├── routing.py             # Call-state machine + route arbitration
│   ├── pipewire_monitor.py    # Polls pw-dump for streams on virtual sink
│   ├── daemon.py              # Long-running daemon + D-Bus service
│   └── cli.py                 # `handset` command implementation
├── conf/
│   ├── 60-handset-speakerphone.conf   # PipeWire loopback config
│   ├── 99-hp-handset.rules            # udev rule for plugdev access
│   └── handset-daemon.service         # systemd user unit
├── debian/                            # Debian packaging
├── supportDocs/                       # HP G9 user guide + data sheet
├── notification_spy.py                # D-Bus notification logger (dev tool)
├── pyproject.toml
└── README.md  (you are here)
```

---

## Hardware

| | |
|---|---|
| Manufacturer | Hewlett-Packard |
| Product name | HP Internet Handset |
| Firmware label | `G9 v1.0.0.0` |
| USB VID:PID | `03f0:1c07` |
| Ringer | 1 W, >70 dBA SPL |
| LEDs (per data sheet) | Voicemail, Ringing, Mute (we've identified Ringing and Mute) |
| Audio | USB Audio Class 1.0, S16_LE, 1–2 ch, 6400–48000 Hz |
| Buttons | 0–9, *, #, green dial, red hangup, mute, hold, vol±, contacts, big-N, plus cradle in/out events |

### Reference docs

The `supportDocs/` directory has HP's archived datasheet and user
guide for the device. They're useful for confirming hardware specs but
contain nothing about the USB protocol — that all had to be reverse
engineered from device behaviour.

---

## Development

### Notification spy

If you want to add ring rules for other Rambox services (Telegram,
Slack, Discord, …), use the notification spy to capture what each
service actually sends through D-Bus:

```sh
python3 notification_spy.py
# trigger a test notification from the service
# Ctrl-C when done
cat notifications.jsonl
```

Then add a rule in `voiphandset/daemon.py` (search for `NotificationMatcher._build_rules`).

### Mic-feedback testing

The reverse-engineering relied on a HyperX headset mic placed against
the base speaker so we could detect base-speaker output autonomously.
The pattern is:

```python
def record(action, duration_sec):
    rec = subprocess.Popen(['arecord','-D','pulse','-f','S16_LE',
                            '-r','48000','-c','1',
                            '-d',str(int(duration_sec)),'/tmp/r.wav'])
    time.sleep(0.3)         # let arecord stabilise
    action()                # do the candidate HID write / audio play
    rec.communicate()
    # then load /tmp/r.wav, compute peak/RMS/FFT, compare to baseline
```

`arecord` only accepts integer durations.

Capture via `-D pulse` (PipeWire's PA layer); the kernel `plughw:` is
exclusive-locked by PipeWire.

### Rebuilding after changes

```sh
# Bump version in pyproject.toml + add a debian/changelog entry
dpkg-buildpackage -us -uc -b -d
sudo dpkg -i ../voiphandset_*.deb
systemctl --user restart handset-daemon.service
```

---

## License

GPL-3.0-or-later. See `debian/copyright`.

## Acknowledgements

- HP's archived support docs (`supportDocs/`) confirmed the device's
  hardware capabilities (the 1 W ringer rating that triggered the
  search for the route bit).
- The reverse engineering was done in collaboration with Claude
  Sonnet 4.6, with mic-feedback testing as the breakthrough
  technique. Full session notes live in the
  `ai-project-history/voip-handset/` submodule.
