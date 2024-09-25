import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap import Style
from PIL import Image, ImageTk
import pandas as pd
from rover01 import Rover  # Import the Rover class from rover.py

class MainApp:
    def __init__(self, root, window_title):
        self.window = root
        self.window.title(window_title)
        self.style = ttk.Style("litera")
        self.is_streaming = False
        self.rovers = {}
        self.rovers_ids = {}

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

        self.execute_btn = ttk.Button(root, text="Execute", style='W.TButton', bootstyle='dark')
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
                    for i, pos in enumerate(self.circle_positions):
                        csv_filename = f"rover{i + 1}.csv"
                        df = pd.read_csv('csv_filename')
                        
                        rover_id = df.iloc[0]['ID']
                        ip_address = df.iloc[0]['IP']
                        
                        print(f"Rover {rover_id} is connecting using fixed IP: {ip_address}\n")
                        self.connect_rover(rover_id, ip_address, i)
                        
                        self.rovers_ids[rover_id] = i
                        
                except FileNotFoundError:
                    print(f"Error: {csv_filename} file is not found")

            elif ip_choice == "Enter IP Manually":
                ip_address = self.ip_entry.get().strip()
                if ip_address:
                    print(f"Rover 1 is connecting using manual IP: {ip_address}\n")
                    self.connect_rover(0, ip_address)
                else:
                    print("No IP address entered")

    def connect_rover(self, rover_id, ip_address, circle_index):
        rover = Rover(rover_id, ip_address, self.update_status)
        self.rovers[rover_id] = rover
        rover.start_connection()
        
        self.canvas.itemconfig(self.circles[circle_index], fill='yellow')


    def update_status(self, rover_id, status):
        circle_index = self.rovers_ids[rover_id]
        
        if circle_index is not None:
            
            if status:
                ip_data = pd.read_csv('ip.csv')
                matching_id = ip_data.iloc[circle_index]['ID']
                    
                if rover_id == matching_id:
                    print(f"Rover {rover_id} is successfully connected.\n")
                    self.canvas.itemconfig(self.circles[circle_index], fill='green')
                else:
                    print(f"Rover {rover_id} is failed to connect with it's ID")
                    self.canvas.itemconfig(self.circles[circle_index], fill='blue')
                    
            elif status == 'red':
                print(f"Rover {rover_id} is successfully disconnected.\n")
                self.canvas.itemconfig(self.circles[circle_index], fill='red')
            else:
                print(f"Rover {rover_id} failed to connect.\n")
                self.canvas.itemconfig(self.circles[circle_index], fill='#4D4E6D')

    def stop_stream(self):
        if self.is_streaming:
            self.is_streaming = False
            
            for rover in self.rovers:
                if rover:
                    rover.stop_connection()

            self.connect_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

    def on_closing(self):
        self.stop_stream()
        self.window.destroy()

root = tk.Tk()
app = MainApp(root, "Aerial Light Show")
root.mainloop()
