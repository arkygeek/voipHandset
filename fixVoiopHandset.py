import time
import hid

# Enumerate all HID devices
for d in hid.enumerate():
    keys = list(d.keys())
    keys.sort()
    for key in keys:
        print("%s : %s" % (key, d[key]))
    print()

# Open a specific device
h = hid.device()
h.open(0x03f0, 0x1c07)  # Vendor ID and Product ID

# Define the keys
keys = {
  0x00 : "- unknown -",  # 0
  0x01 : "- unknown -",  # 1
  0x02 : "- unknown -",  # 2
  0x03 : "- unknown -",  # 3
  0x04 : "- hangup after pressing and releasing 1 -",  # 4
  0x05 : "1 (1 released, or handset lifted when last button released was 1)",  # 5
  0x06 : "- unknown -",  # 6
  0x07 : "1 (pressed)",  # 7
  0x08 : "- hangup after pressing and releasing 2 -",  # 8
  0x09 : "2 (2 released, or handset lifted when last button released was 2)",  # 9
  0x0a : "- unknown -",  # 10
  0x0b : "2 (pressed)",  # 11
  0x0c : "- hangup after pressing and releasing 3 -",  # 12
  0x0d : "3 (3 released, or handset lifted when last button released was 3)",  # 13
  0x0e : "- unknown -",  # 14
  0x0f : "3 (pressed)",  # 15
  0x10 : "- hangup after pressing and releasing 4 -",  # 16
  0x11 : "4 (4 released, or handset lifted when last button released was 4)",  # 17
  0x12 : "- unknown -",  # 18
  0x13 : "4 (pressed)",  # 19
  0x14 : "- hangup after pressing and releasing 5 -",  # 20
  0x15 : "5 (5 released, or handset lifted when last button released was 5)",  # 21
  0x16 : "- unknown -",  # 22
  0x17 : "5 (pressed)",  # 23
  0x18 : "- hangup after pressing and releasing 6 -",  # 24
  0x19 : "6 (6 released, or handset lifted when last button released was 6)",  # 25
  0x1a : "- unknown -",  # 26
  0x1b : "6 (pressed)",  # 27
  0x1c : "- hangup after pressing and releasing 7 -",  # 28
  0x1d : "7 (7 released, or handset lifted when last button released was 7)",  # 29
  0x1e : "- unknown -",  # 30
  0x1f : "7 (pressed)",  # 31
  0x20 : "- hangup after pressing and releasing 8 -",  # 32
  0x21 : "8 (8 released, or handset lifted when last button released was 8)",  # 33
  0x22 : "- unknown -",  # 34
  0x23 : "8 (pressed)",  # 35
  0x24 : "- hangup after pressing and releasing 9 -",  # 36
  0x25 : "9 (9 released, or handset lifted when last button released was 9)",  # 37
  0x26 : "- unknown -",  # 38
  0x27 : "9 (pressed)",  # 39
  0x28 : "- hangup after pressing and releasing * -",  # 40
  0x29 : "* (* released, or handset lifted when last button released was *)",  # 41
  0x2a : "- unknown -",  # 42
  0x2b : "* (pressed)",  # 43
  0x2c : "- hangup after pressing and releasing 0 -",  # 44
  0x2d : "0 (0 released, or handset lifted when last button released was 0)",  # 45
  0x2e : "- unknown -",  # 46
  0x2f : "0 (pressed)",  # 47
  0x30 : "- hangup after pressing and releasing # -",  # 48
  0x31 : "# (# released, or handset lifted when last button released was #)",  # 49
  0x32 : "- unknown -",  # 50
  0x33 : "# (pressed)",  # 51
  0x34 : "- hangup after pressing and releasing green dial button -",  # 52
  0x35 : "green dial (green dial button released, or handset lifted when last button released was green dial button)",  # 53
  0x36 : "- unknown -",  # 54
  0x37 : "green dial (pressed)",  # 55
  0x38 : "- volume up released, or handset lifted when last button released was volume up -",  # 56
  0x39 : "- volume up released -",  # 57
  0x3a : "- unknown -",  # 58
  0x3b : "- volume up pressed -",  # 59
  0x3c : "big handset N button (handset down) (released)",  # 60
  0x3d : "big handset N button (handset lifted off cradle) (big handset N button released, or handset lifted off cradle when last button released was big handset N button)",  # 61
  0x3e : "big handset N button (handset down) (pressed)",  # 62
  0x3f : "big handset N button (handset off cradle) (pressed)",  # 63
  0x40 : "handset is placed into cradle after red hang up button pressed and released",  # 64
  0x41 : "red hangup (released) - or handset was removed from cradle",  # 65
  0x42 : "- unknown -",  # 66
  0x43 : "red hangup (pressed)",  # 67
  0x44 : "- unknown -",  # 68
  0x45 : "mute (released)",  # 69
  0x46 : "- unknown -",  # 70
  0x47 : "mute (pressed)",  # 71
  0x48 : "- hang up after hold button pressed and released -",  # 72
  0x49 : "handset up inner hold button (released)",  # 73
  0x4a : "- unknown 74 -",  # 74
  0x4b : "handset up inner hold button (pressed)",  # 75
  0x4c : "- handset is placed into cradle after (vol-) button pressed and released -",  # 76
  0x4d : "- vol- released or handset lifted when last button released was volume down (vol-) -",  # 77
  0x4e : "- unknown 78 -",  # 78
  0x4f : "- vol- pressed -",  # 79
  0x50 : "- unknown 80 -",  # 80
  0x51 : "- unknown 81 -",  # 81
  0x52 : "- unknown 82 -",  # 82
  0x53 : "- unknown 83 -"  #83
  # I might need more
}

def getKey():
  buf = h.read(8)
  return f'({hex(buf[1])})  {keys[buf[1]]}'

while ( 1 ):
  k = getKey();
  print(k)
h.close

# Read data
while True:
    data = h.read(64)  # Read 64 bytes
    print(data)
    time.sleep(0.1)  # Wait for a bit to avoid spamming the output
# Close the device
h.close()

"""
  here are the very verbose details of the handset:

  Bus 020 Device 044: ID 03f0:1c07
  Device Descriptor:
    bLength                18
    bDescriptorType         1
    bcdUSB               2.00
    bDeviceClass            0 [unknown]
    bDeviceSubClass         0 [unknown]
    bDeviceProtocol         0
    bMaxPacketSize0         8
    idVendor           0x03f0
    idProduct          0x1c07
    bcdDevice            0.09
    iManufacturer           1
    iProduct                2
    iSerial                 4
    bNumConfigurations      1
    Configuration Descriptor:
      bLength                 9
      bDescriptorType         2
      wTotalLength       0x012e
      bNumInterfaces          4
      bConfigurationValue     1
      iConfiguration          3 G9 v1.0.0.0
      bmAttributes         0x80
        (Bus Powered)
      MaxPower              200mA
      Interface Descriptor:
        bLength                 9
        bDescriptorType         4
        bInterfaceNumber        0
        bAlternateSetting       0
        bNumEndpoints           0
        bInterfaceClass         1 [unknown]
        bInterfaceSubClass      1 [unknown]
        bInterfaceProtocol      0
        iInterface              0
        AudioControl Interface Descriptor:
          bLength                10
          bDescriptorType        36
          bDescriptorSubtype      1 (HEADER)
          bcdADC               1.00
          wTotalLength       0x0067
          bInCollection           2
          baInterfaceNr(0)        1
          baInterfaceNr(1)        2
        AudioControl Interface Descriptor:
          bLength                12
          bDescriptorType        36
          bDescriptorSubtype      2 (INPUT_TERMINAL)
          bTerminalID            13
          wTerminalType      0x0201 Microphone
          bAssocTerminal          0
          bNrChannels             1
          wChannelConfig     0x0000
          iChannelNames           0
          iTerminal               0
        AudioControl Interface Descriptor:
          bLength                 9
          bDescriptorType        36
          bDescriptorSubtype      6 (FEATURE_UNIT)
          bUnitID                 6
          bSourceID              13
          bControlSize            1
          bmaControls(0)       0x03
            Mute Control
            Volume Control
          bmaControls(1)       0x00
          iFeature                0
        AudioControl Interface Descriptor:
          bLength                12
          bDescriptorType        36
          bDescriptorSubtype      2 (INPUT_TERMINAL)
          bTerminalID            12
          wTerminalType      0x0101 USB Streaming
          bAssocTerminal          0
          bNrChannels             2
          wChannelConfig     0x0003
            Left Front (L)
            Right Front (R)
          iChannelNames           0
          iTerminal               0
        AudioControl Interface Descriptor:
          bLength                13
          bDescriptorType        36
          bDescriptorSubtype      4 (MIXER_UNIT)
          bUnitID                 9
          bNrInPins               2
          baSourceID(0)          12
          baSourceID(1)           6
          bNrChannels             2
          wChannelConfig     0x0003
            Left Front (L)
            Right Front (R)
          iChannelNames           0
          bmControls(0)        0x00
          iMixer                  0
        AudioControl Interface Descriptor:
          bLength                13
          bDescriptorType        36
          bDescriptorSubtype      6 (FEATURE_UNIT)
          bUnitID                 1
          bSourceID               9
          bControlSize            2
          bmaControls(0)     0x0155
            Mute Control
            Bass Control
            Treble Control
            Automatic Gain Control
            Bass Boost Control
          bmaControls(1)     0x0002
            Volume Control
          bmaControls(2)     0x0002
            Volume Control
          iFeature                0
        AudioControl Interface Descriptor:
          bLength                 9
          bDescriptorType        36
          bDescriptorSubtype      3 (OUTPUT_TERMINAL)
          bTerminalID            14
          wTerminalType      0x0301 Speaker
          bAssocTerminal          0
          bSourceID               1
          iTerminal               0
        AudioControl Interface Descriptor:
          bLength                 9
          bDescriptorType        36
          bDescriptorSubtype      6 (FEATURE_UNIT)
          bUnitID                 2
          bSourceID              13
          bControlSize            1
          bmaControls(0)       0x03
            Mute Control
            Volume Control
          bmaControls(1)       0x00
          iFeature                0
        AudioControl Interface Descriptor:
          bLength                 7
          bDescriptorType        36
          bDescriptorSubtype      5 (SELECTOR_UNIT)
          bUnitID                 8
          bNrInPins               1
          baSourceID(0)           2
          iSelector               0
        AudioControl Interface Descriptor:
          bLength                 9
          bDescriptorType        36
          bDescriptorSubtype      3 (OUTPUT_TERMINAL)
          bTerminalID            10
          wTerminalType      0x0101 USB Streaming
          bAssocTerminal          0
          bSourceID               8
          iTerminal               0
      Interface Descriptor:
        bLength                 9
        bDescriptorType         4
        bInterfaceNumber        1
        bAlternateSetting       0
        bNumEndpoints           0
        bInterfaceClass         1 [unknown]
        bInterfaceSubClass      2 [unknown]
        bInterfaceProtocol      0
        iInterface              0
      Interface Descriptor:
        bLength                 9
        bDescriptorType         4
        bInterfaceNumber        1
        bAlternateSetting       1
        bNumEndpoints           1
        bInterfaceClass         1 [unknown]
        bInterfaceSubClass      2 [unknown]
        bInterfaceProtocol      0
        iInterface              0
        AudioStreaming Interface Descriptor:
          bLength                 7
          bDescriptorType        36
          bDescriptorSubtype      1 (AS_GENERAL)
          bTerminalLink          12
          bDelay                  0 frames
          wFormatTag         0x0001 PCM
        AudioStreaming Interface Descriptor:
          bLength                14
          bDescriptorType        36
          bDescriptorSubtype      2 (FORMAT_TYPE)
          bFormatType             1 (FORMAT_TYPE_I)
          bNrChannels             2
          bSubframeSize           2
          bBitResolution         16
          bSamFreqType            0 Continuous
          tLowerSamFreq        6400
          tUpperSamFreq       48000
        Endpoint Descriptor:
          bLength                 9
          bDescriptorType         5
          bEndpointAddress     0x01  EP 1 OUT
          bmAttributes           13
            Transfer Type            Isochronous
            Synch Type               Synchronous
            Usage Type               Data
          wMaxPacketSize     0x00c0  1x 192 bytes
          bInterval               1
          bRefresh                0
          bSynchAddress           0
          AudioStreaming Endpoint Descriptor:
            bLength                 7
            bDescriptorType        37
            bDescriptorSubtype      1 (EP_GENERAL)
            bmAttributes         0x01
              Sampling Frequency
            bLockDelayUnits         2 Decoded PCM samples
            wLockDelay         0x0001
      Interface Descriptor:
        bLength                 9
        bDescriptorType         4
        bInterfaceNumber        1
        bAlternateSetting       2
        bNumEndpoints           1
        bInterfaceClass         1 [unknown]
        bInterfaceSubClass      2 [unknown]
        bInterfaceProtocol      0
        iInterface              0
        AudioStreaming Interface Descriptor:
          bLength                 7
          bDescriptorType        36
          bDescriptorSubtype      1 (AS_GENERAL)
          bTerminalLink          12
          bDelay                  0 frames
          wFormatTag         0x0001 PCM
        AudioStreaming Interface Descriptor:
          bLength                14
          bDescriptorType        36
          bDescriptorSubtype      2 (FORMAT_TYPE)
          bFormatType             1 (FORMAT_TYPE_I)
          bNrChannels             1
          bSubframeSize           2
          bBitResolution         16
          bSamFreqType            0 Continuous
          tLowerSamFreq        6400
          tUpperSamFreq       48000
        Endpoint Descriptor:
          bLength                 9
          bDescriptorType         5
          bEndpointAddress     0x01  EP 1 OUT
          bmAttributes           13
            Transfer Type            Isochronous
            Synch Type               Synchronous
            Usage Type               Data
          wMaxPacketSize     0x0060  1x 96 bytes
          bInterval               1
          bRefresh                0
          bSynchAddress           0
          AudioStreaming Endpoint Descriptor:
            bLength                 7
            bDescriptorType        37
            bDescriptorSubtype      1 (EP_GENERAL)
            bmAttributes         0x01
              Sampling Frequency
            bLockDelayUnits         2 Decoded PCM samples
            wLockDelay         0x0001
      Interface Descriptor:
        bLength                 9
        bDescriptorType         4
        bInterfaceNumber        2
        bAlternateSetting       0
        bNumEndpoints           0
        bInterfaceClass         1 [unknown]
        bInterfaceSubClass      2 [unknown]
        bInterfaceProtocol      0
        iInterface              0
      Interface Descriptor:
        bLength                 9
        bDescriptorType         4
        bInterfaceNumber        2
        bAlternateSetting       1
        bNumEndpoints           1
        bInterfaceClass         1 [unknown]
        bInterfaceSubClass      2 [unknown]
        bInterfaceProtocol      0
        iInterface              0
        AudioStreaming Interface Descriptor:
          bLength                 7
          bDescriptorType        36
          bDescriptorSubtype      1 (AS_GENERAL)
          bTerminalLink          10
          bDelay                  0 frames
          wFormatTag         0x0001 PCM
        AudioStreaming Interface Descriptor:
          bLength                14
          bDescriptorType        36
          bDescriptorSubtype      2 (FORMAT_TYPE)
          bFormatType             1 (FORMAT_TYPE_I)
          bNrChannels             1
          bSubframeSize           2
          bBitResolution         16
          bSamFreqType            0 Continuous
          tLowerSamFreq        6400
          tUpperSamFreq       48000
        Endpoint Descriptor:
          bLength                 9
          bDescriptorType         5
          bEndpointAddress     0x84  EP 4 IN
          bmAttributes           13
            Transfer Type            Isochronous
            Synch Type               Synchronous
            Usage Type               Data
          wMaxPacketSize     0x0060  1x 96 bytes
          bInterval               1
          bRefresh                0
          bSynchAddress           0
          AudioStreaming Endpoint Descriptor:
            bLength                 7
            bDescriptorType        37
            bDescriptorSubtype      1 (EP_GENERAL)
            bmAttributes         0x01
              Sampling Frequency
            bLockDelayUnits         2 Decoded PCM samples
            wLockDelay         0x0001
      Interface Descriptor:
        bLength                 9
        bDescriptorType         4
        bInterfaceNumber        3
        bAlternateSetting       0
        bNumEndpoints           1
        bInterfaceClass         3 [unknown]
        bInterfaceSubClass      0 [unknown]
        bInterfaceProtocol      0
        iInterface              0
          HID Device Descriptor:
            bLength                 9
            bDescriptorType        33
            bcdHID               1.00
            bCountryCode            0 Not supported
            bNumDescriptors         1
            bDescriptorType        34 Report
            wDescriptorLength      59
            Report Descriptors:
              ** UNAVAILABLE **
        Endpoint Descriptor:
          bLength                 7
          bDescriptorType         5
          bEndpointAddress     0x83  EP 3 IN
          bmAttributes            3
            Transfer Type            Interrupt
            Synch Type               None
            Usage Type               Data
          wMaxPacketSize     0x0002  1x 2 bytes
          bInterval               8
  can't get device qualifier: Operation timed out
  can't get debug descriptor: Operation timed out
  Device Status:     0x0000
    (Bus Powered)



"""