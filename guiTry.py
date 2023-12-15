from tkinter import Tk, Label, Entry, Button, messagebox

class WhatsAppApp:
    """
    Class to create a simple WhatsApp GUI application.

    Attributes:
    - root: Tk
        The main window of the application.
    - target_label: Label
        Label to display the target contact.
    - message_entry: Entry
        Entry field to input the message.
    - send_button: Button
        Button to send the message.
    - receive_button: Button
        Button to receive messages.
    """

    def __init__(self):
        """
        Constructor to instantiate the WhatsAppApp class and create the GUI.
        """

        # Creating the main window
        self.root = Tk()
        self.root.title("WhatsApp App")

        # Creating the target label
        self.target_label = Label(self.root, text="Target Contact:")
        self.target_label.pack()

        # Creating the message entry field
        self.message_entry = Entry(self.root, width=50)
        self.message_entry.pack()

        # Creating the send button
        self.send_button = Button(self.root, text="Send", command=self.send_message)
        self.send_button.pack()

        # Creating the receive button
        self.receive_button = Button(self.root, text="Receive", command=self.receive_message)
        self.receive_button.pack()

    def send_message(self):
        """
        Function to send a message to the target contact.
        """

        # Get the message from the entry field
        message = self.message_entry.get()

        # Check if the message is empty
        if message == "":
            messagebox.showerror("Error", "Message cannot be empty.")
        else:
            # Send the message (implementation not shown)
            # You can replace this with your own implementation to send the message
            messagebox.showinfo("Success", f"Message sent: {message}")

    def receive_message(self):
        """
        Function to receive messages from the target contact.
        """

        # Receive the messages (implementation not shown)
        # You can replace this with your own implementation to receive messages
        messagebox.showinfo("Success", "Messages received.")

    def run(self):
        """
        Function to run the WhatsAppApp GUI application.
        """

        self.root.mainloop()

# Create an instance of the WhatsAppApp class
app = WhatsAppApp()

# Run the WhatsAppApp GUI application
app.run()