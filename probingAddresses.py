import usb.core
import usb.util
import sys

# find the device
device = usb.core.find(idVendor=0x03f0, idProduct=0x1c07)

# choose the first configuration
device.set_configuration()

for config in device:
    for interface in config:
        if interface.bInterfaceClass == 3:  # HID class code
            # This is the HID interface
            print("Found HID interface:", interface.bInterfaceNumber)

# get an endpoint instance
configuration = device.get_active_configuration()
interface = configuration[(3,0)]  # use interface 3

# Detach the HID interface from the system's HID driver
if device.is_kernel_driver_active(interface.bInterfaceNumber):
    try:
        device.detach_kernel_driver(interface.bInterfaceNumber)
    except usb.core.USBError as e:
        sys.exit("Could not detach kernel driver: %s" % str(e))


in_endpoint = usb.util.find_descriptor(
    interface,
    # match the first IN endpoint with address 3
    custom_match = \
    lambda endpoint: \
        usb.util.endpoint_direction(endpoint.bEndpointAddress) == \
        usb.util.ENDPOINT_IN and \
        usb.util.endpoint_address(endpoint.bEndpointAddress) == 3)



assert in_endpoint is not None

# read the data
data = in_endpoint.read(64, timeout=5000)  # replace 64 with the actual size of the data you want to read

print(data)