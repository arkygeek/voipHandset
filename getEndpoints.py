import usb.core
import usb.util

# find the device
dev = usb.core.find(idVendor=0x03f0, idProduct=0x1c07)

# iterate over all configurations, interfaces, and endpoints
for config in dev:
    for iface in config:
        # check if this is an AudioStreaming interface
        if iface.bInterfaceClass == 1 and iface.bInterfaceSubClass == 2:
            print(f"Found AudioStreaming interface: {iface.bInterfaceNumber}")
            # iterate over all endpoints
            for endpoint in iface.endpoints():
                # check if this is an OUT endpoint
                if usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                    print(f"  Found OUT endpoint: {endpoint.bEndpointAddress} with config value: {config.bConfigurationValue} and alternate setting:{iface.bAlternateSetting}")