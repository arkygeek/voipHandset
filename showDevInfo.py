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
  0x00 : "",
  0x03 : "1",
  0x09 : "2",
  0x0f : "3",
  0x04 : "4",
  0x0a : "5",
  0x10 : "6",
  0x05 : "7",
  0x0b : "8",
  0x11 : "9",
  0x06 : "*",
  0x0c : "0",
  0x12 : "#",
  0x02 : "yes",
  0x08 : "S",
  0x0e : "no",
  0x01 : "left",
  0x13 : "up",
  0x16 : "down",
  0x0d : "right",
  0x19 : "vol+",
  0x1c : "vol-",
  0x1b : "mute",
}

# Read data
while True:
    data = h.read(64)  # Read 64 bytes
    print(data)
    time.sleep(0.1)  # Wait for a bit to avoid spamming the output
# Close the device
h.close()
