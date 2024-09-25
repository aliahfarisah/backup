import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap import Style
from PIL import Image, ImageTk
import pandas as pd
from rover04 import Rover  # Import the Rover class from rover01.py

class MainApp:
    def __init__(self, root, window_title):
        self.window = root
        self.window.title(window_title)
        self.style = ttk.Style("litera")
        self.is_streaming = False
        self.rovers = {}  # Dictionary to keep track of rover connections by ID
        self.rover_ids = {}  # Dictionary to store rover IDs and their corresponding circle indices

        # Load the image
        logo_img = Image.open("g7-aerospace-logo-blue-1-411x291.png")
        logo_img = logo_img.resize((200, 100))
        self.logo = ImageTk.PhotoImage(logo_img)

        # Get the screen width and height
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()

        # Set the window geometry to the screen size
        self.window.geometry(f"{screen_width}x{screen_height}")

        # Create a label to display the image in the left frame
        logo_label = ttk.Label(root, image=self.logo)
        logo_label.place(x=30, y=30)

        # Create a Canvas for the box and circles below the logo
        self.canvas = tk.Canvas(root, width=820, height=520, bg='white')
        self.canvas.place(x=30, y=200)

        # Draw the box
        self.canvas.create_rectangle(0, 0, 800, 500, outline='black')

        # Draw and label circles inside the box
        self.circle_radius = 40
        self.circle_positions = [(140, 250), (260, 250), (380, 250), (500, 250), (620, 250)]
        self.circles = []
        self.circle_texts = []

        for i, pos in enumerate(self.circle_positions):
            x, y = pos
            circle = self.canvas.create_oval(x - self.circle_radius, y - self.circle_radius,
                                             x + self.circle_radius, y + self.circle_radius,
                                             fill='#4D4E6D')
            self.circles.append(circle)
            self.canvas.create_text(x, y, text=str(i + 1), fill='white', font=('Times', 20))

        style = ttk.Style()
        style.configure('TCombobox', font=("Times", 15))
        style.configure('TEntry', font=("Times", 15))

        # Add a combobox to choose between fixed IP and manual IP entry
        self.ip_choice_var = tk.StringVar()
        self.ip_choice_var.set("Use Fixed IP")  # Default to "Use Fixed IP"
        self.ip_choice = ttk.Combobox(root, textvariable=self.ip_choice_var,
                                      values=["Use Fixed IP", "Enter IP Manually"],
                                      state="readonly", width=20, style='TCombobox')
        self.ip_choice.place(x=1100, y=260)

        # Add an entry for manual IP entry
        self.ip_entry_var = tk.StringVar()
        self.ip_entry = ttk.Entry(root, textvariable=self.ip_entry_var, width=20, style='TEntry')
        self.ip_entry.place(x=1110, y=300)

        self.software_title = tk.Label(root, text="Aerial Light Show", font="Times 30 bold", bg='white')
        self.software_title.place(x=600, y=60)

        style1 = Style()
        style1.configure('W.TButton', font=('Times', 15))

        self.connect_btn = ttk.Button(root, text="Connect", style='W.TButton', command=self.connect_to_ip)
        self.connect_btn.place(x=1000, y=380, width=150, height=50)
        
        self.stop_btn = ttk.Button(root, text="Stop", style='W.TButton', command=self.stop_stream)
        self.stop_btn.place(x=1200, y=380, width=150, height=50)

        self.execute_btn = ttk.Button(root, text="Execute", style='W.TButton', bootstyle='dark', command=self.execute_movement)
        self.execute_btn.place(x=1100, y=480, width=150, height=50)

        # Bind the close event to a handler
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def connect_to_ip(self):
        if not self.is_streaming:
            self.is_streaming = True

            self.connect_btn.config(state=tk.DISABLED)
            self.execute_btn.config(state=tk.NORMAL)

            ip_choice = self.ip_choice_var.get()

            if ip_choice == "Use Fixed IP":
                try:
                    df = pd.read_csv('ip.csv')
                    if len(df) != len(self.circle_positions):
                        print("Error: Number of IP addresses in the file does not match with the number of circles")
                        return

                    for i, row in df.iterrows():
                        id_database = str(row['ID'])
                        ip_address = row['IP']

                        print(f"Rover {id_database} is connecting using fixed IP: {ip_address}")
                        self.connect_rover(id_database, ip_address, i)  # Pass circle index

                        # Store rover ID and circle index for later use
                        self.rover_ids[id_database] = i
                except FileNotFoundError:
                    print("Error: ip.csv file is not found")

            elif ip_choice == "Enter IP Manually":
                ip_address = self.ip_entry.get().strip()
                if ip_address:
                    id_database = "1"  # Example ID for manual entry
                    print(f"Rover {id_database} is connecting using manual IP: {ip_address}")
                    self.connect_rover(id_database, ip_address, 0)
                    self.rover_ids[id_database] = 0
                else:
                    print("No IP address entered")

    def connect_rover(self, rover_id, ip_address, index):
        rover = Rover(rover_id, ip_address, self.update_circle_status)
        self.rovers[rover_id] = rover
        rover.start_connection()

    def update_circle_status(self, rover_id, color):
        index = self.rover_ids.get(rover_id)
        if index is not None:
            self.canvas.itemconfig(self.circles[index], fill=color)

    def stop_stream(self):
        self.is_streaming = False
        self.connect_btn.config(state=tk.NORMAL)
        self.execute_btn.config(state=tk.DISABLED)
        for rover in self.rovers.values():
            rover.stop_connection()
        self.rovers.clear()
        self.rover_ids.clear()
        
    def execute_movement(self):
        for rover in self.rovers.values():
            rover.execute_movement()

    def on_closing(self):
        self.stop_stream()
        self.window.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root, "Aerial Light Show")
    root.mainloop()
