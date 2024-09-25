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
import base64
import re
from rover09 import Rover

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
        self.ble_services = {}  
        self.lock = threading.Lock()

        # Load the image
        logo_img = Image.open("G7_logo.jpg")
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
        self.circle_positions = [(130, 120), (308, 120), (486, 120), (664, 120), (842, 120)]
        self.circles = []
        self.small_circles = []
        self.circle_texts = []
        self.server_file_combobox = None  # Initialize your combobox properly
        self.metadata_texts = []  # List to store references to created text objects
        self.time_labels = []

        for i, pos in enumerate(self.circle_positions):
            x, y = pos
            circle = self.canvas.create_oval(x - self.circle_radius, y - self.circle_radius,
                                             x + self.circle_radius, y + self.circle_radius,
                                             fill='#4D4E6D')
            self.circles.append(circle)
            self.canvas.create_text(x, y, text=str(i + 1), fill='white', font=('Times', 20))
            
            # Add labels below each circle
            self.canvas.create_text(x - 15, y + 60, text="Animation :", fill='black', font=('Times', 12))
            self.canvas.create_text(x - 37, y + 100, text="Filename :", fill='black', font=('Times', 12))
            self.canvas.create_text(x - 25, y + 130, text="Date :", fill='black', font=('Times', 12))
            self.canvas.create_text(x - 25, y + 160, text="Time :", fill='black', font=('Times', 12))
            self.canvas.create_text(x - 40, y + 195, text="Select File :", fill='black', font=('Times', 12))

            # Add button to upload file
            upload_btn = ttk.Button(root, text="Transfer CSV", command=lambda index=i: self.transfer_data(index))
            self.canvas.create_window(x + 10, y + 250, window=upload_btn)
            
            download_btn = tk.Button(root, text="Download", command=lambda index=i: self.download_selected_file(index))
            self.canvas.create_window(x + 10, y + 280, window=download_btn)
        
        for i, pos in enumerate(self.circle_positions):
            x, y = pos
            
            # Create a label to display server time
            time_label = ttk.Label(root, text=f"Time: --:--:--", font=("Times", 14))
            time_label.place(x=x-35, y=y + 115)

            self.time_labels.append(time_label)
            #print(f"Time label created at ({x}, {y})")
            self.update_time_from_server(i)
        
        # Small circle above main circle for time status
        for i, pos in enumerate(self.circle_positions):
            x, y = pos
            small_circle = self.canvas.create_oval(x - 30, y + 300, x - 10, y + 320, fill='red')
            self.small_circles.append(small_circle)
            
            # Text beside the small circle
            time_text = self.canvas.create_text(x + 20, y + 310, text="Time", fill='black', font=('Times', 12))
            self.circle_texts.append(time_text)
    
        self.client_file_comboboxes = []
        self.server_file_comboboxes = []

        for i, pos in enumerate(self.circle_positions):
            x, y = pos
            # Create server_file_combobox for each circle
            server_combobox = ttk.Combobox(root, width=10, state="readonly")
            server_combobox.place(x=x + 30, y=y + 287)
            server_combobox.bind("<<ComboboxSelected>>", lambda event, index=i: self.display_metadata(event, index))
            self.server_file_comboboxes.append(server_combobox)

            # Create client_file_combobox for each circle
            client_combobox = ttk.Combobox(root, width=10, state="readonly")
            client_combobox.place(x=x + 30, y=y + 382)
            self.client_file_comboboxes.append(client_combobox)

        for i, pos in enumerate(self.circle_positions):
            x, y = pos
            refresh_button = tk.Button(root, text="Refresh", command=lambda index=i: self.refresh_file_list_for_rover(index))
            refresh_button.place(x=x + 60, y=y + 250)  # Adjust position as needed
            
            # start_button = ttk.Button(root, text="Start", command=lambda index=i: self.start_ble_manager(index))
            # start_button.place(x=x + 60, y=y + 50)
        
            # stop_button = ttk.Button(root, text="Stop", command=lambda index=i: self.stop_ble_manager(index))
            # stop_button.place(x=x + 60, y=y + 80)

        # Fetch initial file list and display
        #self.refresh_file_list()

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
        
        self.disconnect_btn = ttk.Button(root, text="Disconnect", style='W.TButton', command=self.stop_stream)
        self.disconnect_btn.place(x=1200, y=580, width=150, height=50)

        self.execute_btn = ttk.Button(root, text="Execute", style='W.TButton', bootstyle='dark', command=self.start_execution)
        self.execute_btn.place(x=1200, y=480, width=150, height=50)
        
        # Label to display messages
        self.message_label = tk.Label(root, text="", font=("Times", 10), fg="red", bg='white')
        self.message_label.place(x=120, y=650)

        # Bind the close event to a handler
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.update_time_label()
        self.file_service = None  # Initialize as None until IP is fetched
        
    def update_time_label(self):
        current_time = datetime.datetime.now().time().strftime("%H:%M:%S %p")
        self.time_stamp.config(text=f"Time: {current_time}")

        self.time_stamp.after(1000, self.update_time_label)  # Update every second
        
    def get_ip_address_for_rover(self, circle_index):
        # Implement logic to fetch IP address for the given circle_index
        try:
            df = pd.read_csv('ip.csv')
            if circle_index < len(df):
                return df.loc[circle_index, 'IP']
            else:
                print(f"Rover {circle_index} is out of range.")
                return None
        except FileNotFoundError:
            print("Error: ip.csv file not found.")
            return None
        except Exception as e:
            print(f"Error fetching IP address for rover {circle_index}: {e}")
            return None
            
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
                    self.refresh_file_list_for_rover(0)
                else:
                    print("No IP address entered")
                    
    def update_time_from_server(self, circle_index):
        try:
            rover_id = circle_index + 1
            ip_address = self.get_ip_address_for_rover(circle_index)
            if ip_address:
                #print(f"Connecting to time service on {ip_address}...")
                # Start a thread to continuously fetch and update time
                thread = threading.Thread(target=self.fetch_time, args=(circle_index, ip_address, rover_id))
                thread.daemon = True
                thread.start()
            else:
                print(f"No IP address found for Rover {rover_id}.")
        except Exception as e:
            print(f"Error connecting to time service for Rover {rover_id}: {str(e)}")

    def fetch_time(self, circle_index, ip_address, rover_id):
        try:
            # Create a new proxy inside the thread
            time_service = Pyro5.api.Proxy(f"PYRO:rover@{ip_address}:9090")
            #print(f"Connected to time service on {ip_address}.")
            
            while True:
                # Fetch the server time from the rover
                server_time = time_service.get_server_time()
                current_time = datetime.datetime.now().strftime("%H:%M:%S %p")

                # Update the time label with the server time
                self.time_labels[circle_index].config(text=f"Time: {server_time}")

                # Convert both times to datetime objects for comparison
                current_time_obj = datetime.datetime.strptime(current_time, "%H:%M:%S %p")
                server_time_obj = datetime.datetime.strptime(server_time, "%H:%M:%S %p")

                # Compare hours and minutes (seconds can be ignored for exact match)
                #if current_time_obj.hour == server_time_obj.hour and current_time_obj.minute == server_time_obj.minute:
                if current_time_obj == server_time_obj:
                    self.canvas.itemconfig(self.small_circles[circle_index], fill='green')
                else:
                    self.canvas.itemconfig(self.small_circles[circle_index], fill='red')

                time.sleep(1)
        except Pyro5.errors.CommunicationError as ce:
            print(f"Communication error with time service for Rover {rover_id}: {str(ce)}")
        except Exception as e:
            print(f"Error fetching time for Rover {rover_id}: {str(e)}")

    def connect_rover(self, rover_id, ip_address, index):
        rover = Rover(rover_id, ip_address, self.update_circle_status)
        self.rovers[rover_id] = rover
        rover.start_connection()
        
        self.rover_ids[index] = rover_id

    def update_circle_status(self, rover_id, color):
        index = self.rover_ids.get(rover_id)
        if index is not None:
            self.canvas.itemconfig(self.circles[index], fill=color)
            
    def refresh_file_list_for_rover(self, circle_index):
        try:
            rover_id = circle_index + 1
            # Get the IP address for the specific circle index
            ip_address = self.get_ip_address_for_rover(circle_index)
            if ip_address:
                # Create proxy for FileService
                file_service = Pyro5.api.Proxy(f"PYRO:rover@{ip_address}:9090")
                print(f"fetching file list for Rover {rover_id}")
                
                # Get file list from server
                files = file_service.get_file_list()
                self.server_file_comboboxes[circle_index]["values"] = files
                
                # Fetch file list from client directory (if needed)
                client_files = os.listdir(".")  # Adjust path as needed
                self.client_file_comboboxes[circle_index]["values"] = client_files
            else:
                print(f"No IP address found for Rover {rover_id}.")
                # Clear comboboxes or handle error state
                
        except Exception as e:
            print(f"Error fetching file list for Rover {rover_id}: {e}")

    def transfer_data(self, circle_index):
        try:
            source_file = self.client_file_comboboxes[circle_index].get()
            if not source_file:
                self.message_label.config(text="Please select a file.")
                return
            
            self.message_label.config(text="")
            
            file_path = os.path.join('.', source_file)
            with open(file_path, 'rb') as f:
                data = f.read()
                                
            # Serialize the column data using pickle
            serialized_data = pickle.dumps(data)
            
            rover_id = circle_index + 1
            # Get the IP address for the specific circle index
            ip_address = self.get_ip_address_for_rover(circle_index)
            if ip_address:
                # Send the serialized data to the server
                filename = os.path.basename(file_path)
                file_service = Pyro5.api.Proxy(f"PYRO:rover@{ip_address}:9090")
                result = file_service.upload_file(filename, serialized_data)
                    
                # Optionally print or log the result
                print(result)
                
                # Show success message
                success_message = f"{filename} successfully uploaded to Rover {rover_id}."
                print(success_message)  # Optionally print the message
                self.message_label.config(text=success_message)
                # Move the message label to the left
                self.message_label.place(x=100, y=650)  # Adjust x coordinate as needed
            else:
                print(f"No IP address found for Rover {rover_id}.")
                self.message_label.config(text=f"No IP address found for Rover {rover_id}.")

        except FileNotFoundError:
            print("File is not found.")
            self.message_label.config(text="File is not found.")
        except Exception as e:
            print(f"Error: {str(e)}")
            self.message_label.config(text=f"Error: {str(e)}")
            
    def display_metadata(self, event=None, circle_index=None):
        try:
            if circle_index is None:
                # If circle_index is not provided, iterate through all circles
                for circle_index in range(len(self.server_file_comboboxes)):
                    self.update_metadata_for_rover(circle_index)
            else:
                # Display metadata for a specific circle index
                self.update_metadata_for_rover(circle_index)

        except Exception as e:
            print(f"Error: {str(e)}")

    def update_metadata_for_rover(self, circle_index):
        try:
            selected_file = self.server_file_comboboxes[circle_index].get()
            
            # Ensure metadata_texts has enough elements for circle_index
            while len(self.metadata_texts) <= circle_index:
                self.metadata_texts.append([])  # Append empty list if needed
            
            rover_id = circle_index + 1
            # Get the IP address for the specific circle index
            ip_address = self.get_ip_address_for_rover(circle_index)
            if ip_address:
                # Get file metadata from the server
                file_service = Pyro5.api.Proxy(f"PYRO:rover@{ip_address}:9090")
                metadata = file_service.get_file_metadata(selected_file)
                if "error" in metadata:
                    print(metadata["error"])
                    return

                file_date = metadata["date"]
                file_time = metadata["time"]

                # Clear existing metadata texts for the current circle index
                for text_obj in self.metadata_texts[circle_index]:
                    self.canvas.delete(text_obj)
                self.metadata_texts[circle_index].clear()

                # Update metadata labels below the corresponding circle
                x, y = self.circle_positions[circle_index]
                date_text = self.canvas.create_text(x + 40, y + 130, text=f"{file_date}", fill='black', font=('Times', 12))
                time_text = self.canvas.create_text(x + 40, y + 160, text=f"{file_time}", fill='black', font=('Times', 12))

                # Store references to created text objects for the current circle index
                self.metadata_texts[circle_index].extend([date_text, time_text])
            else:
                print(f"No IP address found for circle index {rover_id}.")

        except Exception as e:
            print(f"Error: {str(e)}")
            
    def download_selected_file(self, circle_index):
        try:
            # Get selected file from the combobox
            selected_file = self.server_file_comboboxes[circle_index].get()
            if not selected_file:
                self.message_label.config(text="No file selected.")
                return
            
            # Get the IP address (example)
            ip_address = self.get_ip_address_for_rover(circle_index)
            if ip_address:
                # Create proxy for FileService
                file_service = Pyro5.api.Proxy(f"PYRO:rover@{ip_address}:9090")
                
                # Request the file content
                response = file_service.download_file(selected_file)
                
                if "error" in response:
                    self.message_label.config(text=f"Error downloading file: {response['error']}")
                else:
                    # Decode the file content
                    decoded_data = base64.b64decode(response['data'])
                    file_data = pickle.loads(decoded_data)
                    
                    # Sanitize the filename to remove invalid characters
                    sanitized_filename = re.sub(r'[\\/*?:"<>|]', "_", selected_file)

                    # Save the file locally
                    with open(sanitized_filename, 'wb') as f:
                        f.write(file_data)
                    self.message_label.config(text=f"File '{sanitized_filename}' downloaded and saved successfully.")
            else:
                self.message_label.config(text="IP address not found for selected Rover.")
                
        except Exception as e:
            self.message_label.config(text=f"Error downloading file: {e}")

    # def start_ble_manager_thread(self, circle_index):
    #     print(f"Starting BLE manager thread for circle_index: {circle_index}")
    #     thread = threading.Thread(target=self.start_ble_manager, args=(circle_index,))
    #     thread.daemon = True
    #     thread.start()

    # def start_ble_manager(self, circle_index):
    #     try:
    #         rover_id = circle_index + 1  # This should match with how you store and retrieve services
    #         print(f"Starting BLE manager for Rover: {rover_id}")
    #         ip_address = self.get_ip_address_for_rover(circle_index)
    #         print(f"Retrieved IP address for Rover {rover_id}: {ip_address}")
    #         if ip_address:
    #             ble_service = Pyro5.api.Proxy(f"PYRO:ble@{ip_address}:9093")
    #             asyncio.run(ble_service.start(rover_id))
    #             with self.lock:
    #                 self.ble_services[rover_id] = ble_service  # Store by rover_id
    #             print("Started BLEDeviceManagerServer...")
    #         else:
    #             print(f"No IP address found for Rover {rover_id}.")
    #     except Exception as e:
    #         print(f"Failed to start BLEDeviceManagerServer: {e}")

    # def stop_ble_manager(self, circle_index):
    #     try:
    #         rover_id = circle_index + 1  # This should match with how you start services
    #         print(f"Stopping BLE manager for Rover: {rover_id}")
    #         ip_address = self.get_ip_address_for_rover(circle_index)
    #         if ip_address:
    #             ble_service = Pyro5.api.Proxy(f"PYRO:ble@{ip_address}:9093")
    #             asyncio.run(ble_service.stop(rover_id))
    #             with self.lock:
    #                 del self.ble_services[rover_id]
    #             print("Stopped BLEDeviceManagerServer...")
    #         else:
    #             print(f"Server proxy for Rover {rover_id} is not initialized.")
    #     except Exception as e:
    #         print(f"Failed to stop BLEDeviceManagerServer: {e}")

    def start_execution(self):
        threads = []
        for rover in self.rovers.values():
            thread = threading.Thread(target=rover.execute_movement)
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
