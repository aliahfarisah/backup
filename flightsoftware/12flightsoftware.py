import tkinter as tk
from tkinter import filedialog
import os
import ttkbootstrap as ttk
from ttkbootstrap import Style
from PIL import Image, ImageTk
import pandas as pd
import threading
import time
import datetime
import pickle
import Pyro5.api
from rover08 import Rover

class MainApp:
    def __init__(self, root, window_title):
        self.window = root
        self.window.title(window_title)
        self.style = ttk.Style("litera")
        self.is_streaming = False
        self.rovers = {}  # Dictionary to keep track of rover connections by ID
        self.rover_ids = {}  # Dictionary to store rover IDs and their corresponding circle indices
        self.file_service = None
        self.time_service = None
        
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
        logo_label.place(x=50, y=30)

        # Create a Canvas for the box and circles below the logo
        self.canvas = tk.Canvas(root, width=1100, height=600, bg='white')
        self.canvas.place(x=30, y=200)

        # Draw the box
        self.canvas.create_rectangle(0, 0, 1000, 500, outline='black')

        # Draw and label circles inside the box
        self.circle_radius = 40
        self.circle_positions = [(140, 140), (318, 140), (496, 140), (674, 140), (852, 140)]
        self.circles = []
        self.small_circles = []
        self.circle_texts = []
        self.server_file_combobox = None  # Initialize your combobox properly
        self.metadata_texts = []  # List to store references to created text objects

        for i, pos in enumerate(self.circle_positions):
            x, y = pos
            circle = self.canvas.create_oval(x - self.circle_radius, y - self.circle_radius,
                                             x + self.circle_radius, y + self.circle_radius,
                                             fill='#4D4E6D')
            self.circles.append(circle)
            self.canvas.create_text(x, y, text=str(i + 1), fill='white', font=('Times', 20))
            
            # Add labels below each circle
            self.canvas.create_text(x, y + 70, text="Animation :", fill='black', font=('Times', 12))
            self.canvas.create_text(x - 37, y + 100, text="Filename :", fill='black', font=('Times', 12))
            self.canvas.create_text(x - 25, y + 130, text="Date :", fill='black', font=('Times', 12))
            self.canvas.create_text(x - 25, y + 160, text="Time :", fill='black', font=('Times', 12))
            self.canvas.create_text(x - 40, y + 195, text="Select File :", fill='black', font=('Times', 12))

            # Add button to upload file
            upload_btn = ttk.Button(root, text="Transfer CSV", command=self.transfer_data)
            self.canvas.create_window(x, y + 250, window=upload_btn)
            
        # Small circle above main circle for time status
        for i, pos in enumerate(self.circle_positions):
            x, y = pos
            small_circle = self.canvas.create_oval(x - 30, y + 280, x - 10, y + 300, fill='red')
            self.small_circles.append(small_circle)
            
            # Text beside the small circle
            time_text = self.canvas.create_text(x + 20, y + 290, text="Time", fill='black', font=('Times', 12))
            self.circle_texts.append(time_text)
    
        # Combobox to display existing CSV files
        self.server_file_combobox = ttk.Combobox(root, width=10, state="readonly")
        self.server_file_combobox.place(x=170, y=430)
        self.server_file_combobox.bind("<<ComboboxSelected>>", self.display_metadata)

        # Combobox to select files from client for transfer
        self.client_file_combobox = ttk.Combobox(root, width=10, state="readonly")
        self.client_file_combobox.place(x=170, y=523)

        # Refresh button to update file list
        self.refresh_button = tk.Button(root, text="Refresh List", command=self.refresh_file_list)
        self.refresh_button.place(x=1100, y=520)

        # Fetch initial file list and display
        self.refresh_file_list()

        style = ttk.Style()
        style.configure('TCombobox', font=("Times", 15))
        style.configure('TEntry', font=("Times", 15))

        # Add a combobox to choose between fixed IP and manual IP entry
        self.ip_choice_var = tk.StringVar()
        self.ip_choice_var.set("Use Fixed IP")  # Default to "Use Fixed IP"
        self.ip_choice = ttk.Combobox(root, textvariable=self.ip_choice_var,
                                      values=["Use Fixed IP", "Enter IP Manually"],
                                      state="readonly", width=20, style='TCombobox')
        self.ip_choice.place(x=1200, y=260)

        # Add an entry for manual IP entry
        self.ip_entry_var = tk.StringVar()
        self.ip_entry = ttk.Entry(root, textvariable=self.ip_entry_var, width=20, style='TEntry')
        self.ip_entry.place(x=1205, y=300)

        self.software_title = tk.Label(root, text="Aerial Light Show", font="Times 30 bold", bg='white')
        self.software_title.place(x=600, y=60)
        
        self.time_stamp = tk.Label(root, text="Time: 16:46:51 PM", font="Times 17 bold", bg='white')
        self.time_stamp.place(x=1200, y=70)

        style1 = Style()
        style1.configure('W.TButton', font=('Times', 15))

        self.connect_btn = ttk.Button(root, text="Connect", style='W.TButton', command=self.connect_to_ip)
        self.connect_btn.place(x=1200, y=380, width=150, height=50)
        
        self.stop_btn = ttk.Button(root, text="Stop", style='W.TButton', command=self.stop_stream)
        self.stop_btn.place(x=1200, y=580, width=150, height=50)

        self.execute_btn = ttk.Button(root, text="Execute", style='W.TButton', bootstyle='dark', command=self.start_execution)
        self.execute_btn.place(x=1200, y=480, width=150, height=50)
        
        # Label to display messages
        self.message_label = tk.Label(root, text="", font=("Times", 12), fg="red", bg='white')
        self.message_label.place(x=120, y=650)

        # Bind the close event to a handler
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.update_time_label()
        
        self.update_time_from_server()

        self.file_service = None  # Initialize as None until IP is fetched
        
    def update_time_label(self):
        current_time = datetime.datetime.now().time().strftime("%H:%M:%S %p")
        self.time_stamp.config(text=f"Time: {current_time}")

        self.time_stamp.after(1000, self.update_time_label)  # Update every second
            
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

            # Fetch the IP address from the first entry in ip.csv for self.file_service
            try:
                df = pd.read_csv('ip.csv')
                self.ip_address = df.loc[0, 'IP']  # Assuming IP is in the first row
                # Create proxy for FileService
                self.file_service = Pyro5.api.Proxy(f"PYRO:file@{self.ip_address}:9091")
                
                # Create proxy for TimeService
                self.time_service = Pyro5.api.Proxy(f"PYRO:time@{self.ip_address}:9092")
                # Example: Call get_server_time on file_service
                server_time = self.time_service.get_server_time()
                print(f"Server time retrieved: {server_time}")
                
            except FileNotFoundError:
                print("Error: ip.csv file is not found")
            except Exception as e:
                print(f"Error setting up file_service: {e}")
                
    def update_time_from_server(self):
        current_time = datetime.datetime.now().strftime("%H:%M:%S %p")
        if self.time_service:
            try:
                server_time = self.time_service.get_server_time()  # Example method to fetch server time
                print(f"Current time: {current_time}, Server time: {server_time}")

                # Convert both times to datetime objects for comparison
                current_time_obj = datetime.datetime.strptime(current_time, "%H:%M:%S %p")
                server_time_obj = datetime.datetime.strptime(server_time, "%H:%M:%S %p")
                
                # Compare hours and minutes (seconds can be ignored for exact match)
                #if current_time_obj.hour == server_time_obj.hour and current_time_obj.minute == server_time_obj.minute:
                if current_time_obj == server_time_obj:
                    self.canvas.itemconfig(self.small_circles[0], fill='green')
                else:
                    self.canvas.itemconfig(self.small_circles[0], fill='red')
            except Exception as e:
                print(f"Error fetching server time: {e}")

        # Call this function again after 1000 ms (1 second)
        self.window.after(1000, self.update_time_from_server)
                
    def connect_rover(self, rover_id, ip_address, index):
        rover = Rover(rover_id, ip_address, self.update_circle_status)
        self.rovers[rover_id] = rover
        rover.start_connection()

    def update_circle_status(self, rover_id, color):
        index = self.rover_ids.get(rover_id)
        if index is not None:
            self.canvas.itemconfig(self.circles[index], fill=color)
            
    def refresh_file_list(self):
        try:
            if self.file_service:
                files = self.file_service.get_file_list()
                self.server_file_combobox["values"] = files
            else:
                print("Error: file_service is not initialized.")

            # Fetch file list from client directory
            client_files = os.listdir(".")  # Adjust path as needed
            self.client_file_combobox["values"] = client_files

        except Exception as e:
            print(f"Error fetching file list: {e}")
    
    def transfer_data(self):
        source_file = self.client_file_combobox.get()
        if not source_file:
            self.message_label.config(text="Please select a file.")
            return
        
        self.message_label.config(text="")
        
        try:
            file_path = os.path.join('.', source_file)
            with open(file_path, 'rb') as f:
                data = f.read()
                                
            # Serialize the column data using pickle
            serialized_data = pickle.dumps(data)
                
            # Send the serialized data to the server
            filename = os.path.basename(file_path)
            result = self.file_service.upload_file(filename, serialized_data)
                
            # Optionally print or log the result
            print(result)
                
            # Update selected file label
            #self.selected_file_label.config(text=f"Selected File: {filename}")
        
        except FileNotFoundError:
            print("File is not found.")
        except Exception as e:
            print(f"Error: {str(e)}")
            
    def display_metadata(self, event):
        selected_file = self.server_file_combobox.get()
        
        try:
            # Get file metadata from the server
            metadata = self.file_service.get_file_metadata(selected_file)
            if "error" in metadata:
                print(metadata["error"])
                return

            file_date = metadata["date"]
            file_time = metadata["time"]

            # Clear existing metadata texts
            for text_obj in self.metadata_texts:
                self.canvas.delete(text_obj)
            self.metadata_texts.clear()

            # Update metadata labels below the corresponding circle
            circle_index = 0  # Adjust this index based on your logic for circle selection
            if circle_index < len(self.circle_positions):
                date = self.canvas.create_text(self.circle_positions[circle_index][0] + 40, self.circle_positions[circle_index][1] + 130, text=f"{file_date}", fill='black', font=('Times', 12))
                time = self.canvas.create_text(self.circle_positions[circle_index][0] + 40, self.circle_positions[circle_index][1] + 160, text=f"{file_time}", fill='black', font=('Times', 12))
                
                # Store references to created text objects
                self.metadata_texts.extend([date, time])

        except Exception as e:
            print(f"Error: {str(e)}")
        
    def adjust_time(self, hours, minutes, seconds):
        # If seconds are 60 or more, convert them to minutes
        if seconds >= 60:
            minutes += seconds // 60
            seconds = seconds % 60

        # If minutes are 60 or more, convert them to hours
        if minutes >= 60:
            hours += minutes // 60
            minutes = minutes % 60

        # If hours are 24 or more, wrap around
        if hours >= 24:
            hours = hours % 24

        return hours, minutes, seconds

    def start_execution(self):
        t_click = datetime.datetime.now().time()
        print(f"t_click = {t_click}")
        current_hour = t_click.hour
        current_minute = t_click.minute
        current_second = t_click.second
        #print(f"current_hour: {current_hour}")
        #print(f"current_minute: {current_minute}")
        #print(f"current_second: {current_second}")
        
        delay = 5  # Adjust the delay time as needed
        t_execute_second = current_second + delay
        
        # Adjust the time to handle overflow
        adjusted_hour, adjusted_minute, adjusted_second = self.adjust_time(current_hour, current_minute, t_execute_second)
        
        print(f"t_execute: {adjusted_hour}:{adjusted_minute}:{adjusted_second}")
        self.execute_btn.config(state=tk.NORMAL)
        
        threads = []
        for rover in self.rovers.values():
            thread = threading.Thread(target=rover.execute_movement, args=(adjusted_hour, adjusted_minute, adjusted_second))
            threads.append(thread)
            thread.start()
            
    def stop_stream(self):
        self.is_streaming = False
        self.connect_btn.config(state=tk.NORMAL)
        self.execute_btn.config(state=tk.NORMAL)
        for rover in self.rovers.values():
            rover.stop_connection()
        self.rovers.clear()
        self.rover_ids.clear()
            
    def on_closing(self):
        self.stop_stream()
        self.window.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root, "Aerial Light Show")
    root.mainloop()
