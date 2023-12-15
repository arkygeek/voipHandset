import usb.core
import usb.util
import numpy as np
import usb.backend.libusb1

try:
    # set the backend to libusb1
    be = usb.backend.libusb1.get_backend(find_library=lambda x: "/usr/local/lib/libusb-1.0.dylib")

    # find the device
    dev = usb.core.find(idVendor=0x03f0, idProduct=0x1c07, backend=be)

    # set the active configuration
    dev.set_configuration()

    # get the active configuration
    config = dev.get_active_configuration()

    # iterate over all interfaces
    # for interface in config:
    #     print(f'Interface {interface.bInterfaceNumber}:')

    #     # iterate over all endpoints in the interface
    #     for endpoint in interface:
    #         print(f'  Endpoint {endpoint.bEndpointAddress}:')
    #         print(f'    Direction: {"IN" if usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT"}')
    #         print(f'    Type: {usb.util.endpoint_type(endpoint.bmAttributes)}')

    # get the interface
    interface = usb.util.find_descriptor(
        dev.get_active_configuration(),
        bInterfaceNumber=1
    )

    # set the alternate setting
    dev.set_interface_altsetting(interface.bInterfaceNumber, 1)



    # # find the endpoint
    # endpoint = usb.util.find_descriptor(
    #     interface,
    #     custom_match = \
    #     lambda e: \
    #         usb.util.endpoint_direction(e.bEndpointAddress) == \
    #         usb.util.ENDPOINT_OUT
    # )

    # ... generate and send audio data as before ...
    # open the file in binary mode and read its contents
    with open('beep.pcm', 'rb') as f:
        data = f.read()

    # find the OUT endpoint
    endpoint = usb.util.find_descriptor(
        dev.get_interface_altsetting(),   # get the active interface
        custom_match = \
        lambda e: \
            usb.util.endpoint_direction(e.bEndpointAddress) == \
            usb.util.ENDPOINT_OUT)

    # write the data to the endpoint
    endpoint.write(data)
    # Set the parameters
    sample_rate = 44100  # samples per second
    tone_freq = 440.0    # frequency of the tone (Hz)
    duration = 2.0       # duration of the tone (seconds)

    # Generate the time values for each sample
    t = np.linspace(0, duration, int(sample_rate * duration), False)

    # Generate the audio signal
    note = np.sin(tone_freq * t * 2 * np.pi)

    # Ensure that highest value is in 16-bit range
    audio = note * (2**15 - 1) / np.max(np.abs(note))
    audio = audio.astype(np.int16)

    # write the audio data to the endpoint
    endpoint.write(audio.tobytes())

except usb.core.USBError as e:
    print(f'USBError: {str(e)}')
    # Handle the exception here
