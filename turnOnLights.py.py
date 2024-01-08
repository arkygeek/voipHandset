import hid

# Define your device's Vendor ID and Product ID
vendor_id = 0x03F0  # Replace with your actual Vendor ID
product_id = 0x1C07  # Replace with your actual Product ID

# Find the device
device_info = None
for d in hid.enumerate():
    if d['vendor_id'] == vendor_id and d['product_id'] == product_id:
        device_info = d
        break

if device_info is None:
    print("Device not found.")
    exit()

# Open the device
device = hid.device()
device.open(vendor_id, product_id)

# Define the report ID and LED control command
mute_button_report_id =  3 # Replace with the actual report ID for your device
led_control_command = b'\x01\x02\x03'  # Replace with the actual LED control command

# Send the command to control the LED
device.write([mute_button_report_id] + list(led_control_command))

# Close the device
device.close()
