import usb.core
import usb.util

# Find the device
dev = usb.core.find(idVendor=0x03f0, idProduct=0x1c07)

# Detach from kernel driver if necessary
if dev.is_kernel_driver_active(0):
    dev.detach_kernel_driver(0)

# Set the configuration
dev.set_configuration()

# Print out all the endpoints
for config in dev:
    for iface in config:
        for endpoint in iface:
            print(endpoint)