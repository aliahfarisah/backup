import tkinter as tk
from tkinter import messagebox, StringVar
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
import pygame
import numpy as np
import math
from rover09 import Rover

class MainApp:
    def __init__(self, root, window_title):
        self.window = root
        self.window.title(window_title)
        self.style = ttk.Style("litera")
        self.is_streaming = False
        self.rovers = {}  # Dictionary to keep track of rover connections by ID
        self.rover_ids = {} 

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

        self.software_title = tk.Label(root, text="Swarm Application", font="Times 30 bold", bg='white')
        self.software_title.place(x=600, y=60)

        self.date_stamp = tk.Label(root, text="Date: Wednesday", font="Times 17 bold", bg='white')
        self.date_stamp.place(x=1145, y=50)

        self.time_stamp = tk.Label(root, text="Time: 16:46:51 PM", font="Times 17 bold", bg='white')
        self.time_stamp.place(x=1200, y=90)

        style1 = Style()
        style1.configure('W.TButton', font=('Times', 15))

        self.connect_btn = ttk.Button(root, text="Connect", style='W.TButton', command=self.connect_to_ip)
        self.connect_btn.place(x=70, y=625, width=150, height=50)

        self.confirm_btn = ttk.Button(root, text="Confirm", style='W.TButton', command=self.connect)
        self.confirm_btn.place(x=70, y=565, width=150, height=50)
        
        self.reset_btn = ttk.Button(root, text="Reset", style='W.TButton', command=self.reset)
        self.reset_btn.place(x=70, y=685, width=150, height=50)

        self.swarm_label = tk.Label(root, text="Swarm:", font="Times 17 bold", bg='white')
        self.swarm_label.place(x=100, y=210)
        
        # Label to display messages
        self.message_label = tk.Label(root, text="", font=("Times", 10), fg="red", bg='white')
        self.message_label.place(x=120, y=150)

        # Create an entry widget for size input with validation
        self.size_label = ttk.Label(root, text="Size:", font="Times 15 bold")
        self.size_label.place(x=90, y=260)

        self.size_var = StringVar()

        # Define validation command
        self.validate_command = root.register(self.validate_number)

        self.size_entry = ttk.Entry(root, textvariable=self.size_var, validate='key',
                                   validatecommand=(self.validate_command, '%P'))
        self.size_entry.place(x=140, y=260, width=50, height=30)

        self.mode_label = tk.Label(root, text="Mode:", font="Times 17 bold", bg='white')
        self.mode_label.place(x=100, y=310)

        # Create radio buttons for Lightshow and Stride with increased font size
        self.mode_var = tk.StringVar(value="Lightshow")  # Default selection

        # Apply a custom style with larger font for the radio buttons
        style = ttk.Style()
        style.configure("Custom.TRadiobutton", font=("Times", 15))

        self.lightshow_rb = ttk.Radiobutton(root, text="Lightshow", variable=self.mode_var, value="Lightshow",
                                            style="Custom.TRadiobutton")
        self.lightshow_rb.place(x=90, y=360)

        self.stride_rb = ttk.Radiobutton(root, text="Stride", variable=self.mode_var, value="Stride",
                                         style="Custom.TRadiobutton")
        self.stride_rb.place(x=90, y=400)

        # Create a frame for the scrollable canvas
        self.scroll_frame = tk.Frame(root, bg='black', bd=2, relief='solid')
        self.scroll_frame.place(x=300, y=200, width=1200, height=550)

        # Create a canvas widget for drawing circles
        self.canvas = tk.Canvas(self.scroll_frame, bg='white')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create vertical and horizontal scrollbars
        self.v_scroll = tk.Scrollbar(self.scroll_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.h_scroll = tk.Scrollbar(self.scroll_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.width_entry = tk.Entry(root)
        self.height_entry = tk.Entry(root)
        
        # Create and pack widgets
        self.width_label = tk.Label(root, text="Width:", font="Times 14 bold")
        self.width_label.place(x=90, y=445)
        self.width_entry.insert(0, "1500")
        self.width_entry.place(x=160, y=445, width=50, height=30)

        self.height_label = tk.Label(root, text="Height:", font="Times 14 bold")
        self.height_label.place(x=90, y=490)
        self.height_entry.insert(0, "750")
        self.height_entry.place(x=160, y=490, width=50, height=30)

        self.apply_button = tk.Button(root, text="Apply", command=self.apply_dimensions)
        self.apply_button.place(x=130, y=530)


        self.circle_radius = 40
        self.circle_positions = []
        self.circles = []
        self.metadata_texts = []
        self.time_labels = []
        self.small_circles = []
        self.circle_texts = []
        self.client_file_comboboxes = []
        self.server_file_comboboxes = []
        self.rover_visualization = None

        # Bind the close event to a handler
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.update_time_and_date_label()
        
        self.maximize_window()
        
    def maximize_window(self):
        self.window.state('zoomed')

    def validate_number(self, new_value):
        if new_value == "" or new_value.isdigit():
            return True
        else:
            # Show an error message if the input is not a number
            messagebox.showerror("Invalid Input", "Please enter a valid number.")
            return False

    def connect(self):
        selected_mode = self.mode_var.get()

        if selected_mode == "Lightshow":
            # Retrieve the size from the entry widget
            size = self.size_var.get()

            # Display the size and selected mode (or handle them as needed)
            print(f"Size entered: {size}")
            print(f"Selected mode: {selected_mode}")

            # Disable the size entry widget and radio buttons
            self.size_entry.config(state='disabled')
            self.lightshow_rb.config(state='disabled')
            self.stride_rb.config(state='disabled')

            # Optionally, disable the "Connect" button after it's clicked
            self.confirm_btn.config(state='disabled')

            self.update_circles(int(size))
        else:
            # Handle "Stride" mode or any other mode if needed
            print(f"Selected mode: {selected_mode}")
            
    def update_ui_for_mode(self):
        selected_mode = self.mode_var.get()
        if selected_mode == "Lightshow":
            # Show the circles and related UI
            self.scroll_frame.pack(fill=tk.BOTH, expand=True)
        else:
            # Hide or disable the UI elements for other modes
            self.scroll_frame.pack_forget()
        
    def update_circles(self, num_circles):
        # Clear existing circles and related widgets
        self.canvas.delete("all")

        # Clear lists
        self.circle_positions = []
        self.circles = []
        self.metadata_texts = []
        self.time_labels = []
        self.small_circles = []
        self.circle_texts = []
        self.client_file_comboboxes = []
        self.server_file_comboboxes = []

        # Calculate circle positions based on the number of circles
        self.circle_positions = [(130 + i * 178, 120) for i in range(num_circles)]

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
            upload_btn = ttk.Button(self.window, text="Transfer CSV", command=lambda index=i: self.transfer_data(index))
            self.canvas.create_window(x + 10, y + 250, window=upload_btn)

            download_btn = tk.Button(self.window, text="Download", command=lambda index=i: self.download_selected_file(index))
            self.canvas.create_window(x + 10, y + 280, window=download_btn)
            
            # Refresh button
            refresh_button = tk.Button(self.window, text="Refresh", command=lambda index=i: self.refresh_file_list_for_rover(index))
            self.canvas.create_window(x + 55, y + 60, window=refresh_button)

            # Create a label to display server time, aligned with the circle
            time_label = ttk.Label(self.window, text=f"Time: --:--:--", font=("Times", 14))
            self.canvas.create_window(x + 5, y - 70, window=time_label)  # Adjust position
            self.time_labels.append(time_label)
            # Update time from server (assuming you have a method for this)
            self.update_time_from_server(i)

            # Small circle above main circle for time status
            small_circle = self.canvas.create_oval(x - 30, y + 300, x - 10, y + 320, fill='red')
            self.small_circles.append(small_circle)

            # Text beside the small circle
            time_text = self.canvas.create_text(x + 20, y + 310, text="Time", fill='black', font=('Times', 12))
            self.circle_texts.append(time_text)

            # Create server_file_combobox for each circle, aligned with the circle
            server_combobox = ttk.Combobox(self.window, width=10, state="readonly")
            self.canvas.create_window(x + 45, y + 102, window=server_combobox)  # Adjust position
            server_combobox.bind("<<ComboboxSelected>>", lambda event, index=i: self.display_metadata(event, index))
            self.server_file_comboboxes.append(server_combobox)

            # Create client_file_combobox for each circle, aligned with the circle
            client_combobox = ttk.Combobox(self.window, width=10, state="readonly")
            self.canvas.create_window(x + 45, y + 198, window=client_combobox)  # Adjust position
            self.client_file_comboboxes.append(client_combobox)
            
        # Add a button to switch to the "Stride" mode
        switch_to_stride_btn = ttk.Button(self.window, text="Switch to Stride", command=self.switch_to_stride)
        self.canvas.create_window(x + 20, y + 360, window=switch_to_stride_btn)
        
    def get_width_and_height(self):
        try:
            # Get dimensions from entry widgets
            new_width = int(self.width_entry.get())
            new_height = int(self.height_entry.get())

            # Validate dimensions
            if new_width <= 0 or new_height <= 0:
                raise ValueError("Width and Height must be positive integers.")

            return new_width, new_height
        except ValueError as e:
            print(f"Error: {e}")
            return None, None

    def apply_dimensions(self):
        # Get dimensions from entry widgets
        real_width, real_height = self.get_width_and_height()
        if real_width is None or real_height is None:
            return  # Exit if invalid dimensions

        # Update RoverVisualization with new dimensions
        if self.rover_visualization:
            self.rover_visualization.real_width = real_width
            self.rover_visualization.real_height = real_height

    def switch_to_stride(self):
        # Clear the canvas for the new mode
        self.canvas.delete("all")
        
        # Set mode to Stride
        self.mode_var.set("Stride")
        self.update_ui_for_mode()
        
        # Get the dimensions from the entry widgets
        real_width, real_height = self.get_width_and_height()
        if real_width is None or real_height is None:
            return  # Exit if invalid dimensions

        self.handle_stride_mode_updates(real_width, real_height)

    def handle_stride_mode_updates(self, real_width, real_height):
        # Remove scroll bars if present
        self.v_scroll.pack_forget()
        self.h_scroll.pack_forget()

        # Start Pygame loop in a separate thread with new dimensions
        self.rover_visualization = RoverVisualization(self.canvas, real_width, real_height)
        self.rover_visualization.pygame_thread = threading.Thread(target=self.rover_visualization.run_pygame)
        self.rover_visualization.pygame_thread.start()
        
    def reset_ui_elements(self):
        # Remove all circles and related elements
        self.canvas.delete("all")
        
        def remove_widgets(widget_list):
            for widget in widget_list:
                widget.destroy()
            widget_list.clear()

        # Remove comboboxes and time labels
        remove_widgets(self.server_file_comboboxes)
        remove_widgets(self.client_file_comboboxes)
        remove_widgets(self.time_labels)

    def reset(self):
        self.is_streaming = False
        
        self.rovers.clear()  # Dictionary to keep track of rover connections by ID
        self.rover_ids.clear()
        # Clear or reset all widgets and variables as needed
        self.size_var.set("")
        self.size_entry.config(state='normal')
        self.lightshow_rb.config(state='normal')
        self.stride_rb.config(state='normal')
        self.connect_btn.config(state='normal')
        self.confirm_btn.config(state='normal')


        # Hide the scroll frame
        self.scroll_frame.pack_forget()  # Hide scroll frame
        
        # Stop Pygame thread if running
        if self.rover_visualization is not None:
            if hasattr(self.rover_visualization, 'pygame_thread') and self.rover_visualization.pygame_thread.is_alive():
                self.rover_visualization.stop_pygame()  # Gracefully stop the Pygame loop
            del self.rover_visualization
            self.rover_visualization = None
        else:
            print("Rover visualization is not initialized or has already been cleared.")

        self.reset_ui_elements()
        print("Reset completed.")

    def update_time_and_date_label(self):
        current_time = datetime.datetime.now().time().strftime("%H:%M:%S %p")
        self.time_stamp.config(text=f"Time: {current_time}")
        self.time_stamp.after(1000, self.update_time_and_date_label)  # Update every second
        
        current_date = datetime.datetime.now().date().strftime("%A, %Y-%m-%d")
        self.date_stamp.config(text=f"Date: {current_date}")
        
    def get_ip_address_for_rover(self, circle_index):
        try:
            df = pd.read_csv('ip.csv')
            if circle_index < len(df):
                ip_address = df.loc[circle_index, 'IP']
                if not pd.isna(ip_address) and ip_address.strip():
                    return ip_address
            else:
                print(f"Rover {str(circle_index + 1)} is out of range.")
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

            try:
                df = pd.read_csv('ip.csv')
                num_circles = len(self.circle_positions)
                # Ensure num_circles doesn't exceed the number of rows in df
                num_circles = min(num_circles, len(df))
                for i in range(num_circles):
                    if i < len(df):
                        row = df.iloc[i]
                        id_database = str(row['ID'])
                        ip_address = row['IP']
                        
                        if pd.isna(ip_address) or not ip_address.strip():
                            # IP address is missing or empty
                            print(f"No IP address found for Rover {i + 1}.")
                            self.update_circle_status(str(i + 1), 'red')
                        else:
                            # Connect to rover if IP is found
                            print(f"Rover {id_database} is connecting using IP: {ip_address}")
                            self.connect_rover(id_database, ip_address, i)
                            self.rover_ids[id_database] = i
                    else:
                        # Rover is out of range
                        print(f"Rover {i + 1} is out of range.")
                    
            except FileNotFoundError:
                print("Error: ip.csv file is not found")
                        
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
            time_service = Pyro5.api.Proxy(f"PYRO:server@{ip_address}:9090")
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
                file_service = Pyro5.api.Proxy(f"PYRO:server@{ip_address}:9090")
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
                file_service = Pyro5.api.Proxy(f"PYRO:server@{ip_address}:9090")
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
                file_service = Pyro5.api.Proxy(f"PYRO:server@{ip_address}:9090")
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
                file_service = Pyro5.api.Proxy(f"PYRO:server@{ip_address}:9090")
                
                # Request the file content
                response = file_service.download_file(selected_file)
                
                if "error" in response:
                    self.message_label.config(text=f"Error downloading file: {response['error']}")
                else:
                    # Decode the file content
                    decoded_data = base64.b64decode(response['data'])
                    file_data = pickle.loads(decoded_data)

                    # Save the file locally
                    with open(selected_file, 'wb') as f:
                        f.write(file_data)
                    self.message_label.config(text=f"File '{selected_file}' downloaded and saved successfully.")
            else:
                self.message_label.config(text="IP address not found for selected Rover.")
                
        except Exception as e:
            self.message_label.config(text=f"Error downloading file: {e}")

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
        self.window.destroy()
        
class RoverVisualization:
    def __init__(self, canvas, real_width=1500, real_height=750):
        self.grey = (150, 150, 150)
        self.black = (0, 0, 0)
        self.blue = (0, 0, 255)
        self.red = (255, 0, 0)
        self.radius = 10
        self.screen_height, self.screen_width = 550, 1200
        self.real_width = real_width
        self.real_height = real_height
        self.rover_positions = {}
        self.result_dict = {}
        self.lock = threading.Lock()
        self.target_pos = [1000, 200]
        self.canvas = canvas
        self.stop_event = threading.Event()

        # Initialize Pygame and set up the screen
        pygame.init()
        self.surface = pygame.Surface((self.screen_width, self.screen_height))
        self.font = pygame.font.Font(None, 36)
        pygame.display.set_caption(str(datetime.datetime.now()))
        
        self.running = True

    def fetch_device_info(self, uri):
        try:
            with Pyro5.api.Proxy(uri) as proxy:
                while not self.stop_event.is_set():
                    name, x, y, z, t_tag, status = proxy.get_coordinates()
                    print(f"Data fetched from {uri}: {name}, {status}, {x}, {y}, {z}, {t_tag}")
                    with self.lock:
                        self.result_dict[uri] = (name, x, y, z, t_tag, status)
        except Exception as e:
            print(f"Error fetching data from server {uri}: {e}")
            with self.lock:
                self.result_dict[uri] = (None, None, None, None, None, None)

    def start_rover_threads(self):
        df = pd.read_csv('ip.csv')  
        threads = []
        for index, row in df.iterrows():
            rover_id = row['ID']
            ip_address = row['IP']
            uri = f"PYRO:uwb@{ip_address}:9091"
            print(f"Starting thread for {rover_id} with URI {uri}")
            thread = threading.Thread(target=self.fetch_device_info, args=(uri,))
            threads.append(thread)
            thread.daemon = True
            thread.start()
            
    def run_pygame(self):
        self.start_rover_threads()
        while self.running:
            self.update_screen()
            pygame.time.wait(100)  # Adjust the wait time if needed

    def update_screen(self):
        self.surface.fill((255, 255, 255))
        
        with self.lock:
            for uri, rover_data in list(self.result_dict.items()):
                rover_name, rover_x, rover_y, rover_z, rover_t_tag, rover_status = rover_data
                rover_x = rover_x[0] if isinstance(rover_x, list) and rover_x else 0
                rover_y = rover_y[0] if isinstance(rover_y, list) and rover_y else 0
                rover_name = rover_name[0] if isinstance(rover_name, list) and rover_name else "Unknown"

                rover_x = float(rover_x) if isinstance(rover_x, (int, float)) else 0
                rover_y = float(rover_y) if isinstance(rover_y, (int, float)) else 0

                if not math.isnan(rover_x) and not math.isnan(rover_y):
                    if rover_name != "Unknown":
                        calc_x = int(((self.screen_width - 2) * rover_x) / self.real_width)
                        calc_y = int(((self.screen_height - 2) * rover_y) / self.real_height)
                        drawx = calc_x 
                        drawy = calc_y

                        self.rover_positions[rover_name] = (drawx, drawy)

        if len(self.rover_positions) < 1:
            error_pos = (50, 80)
            error_message = self.font.render('! Error: No Rover detected', True, self.red)
            self.surface.blit(error_message, error_pos)
        else:
            self.draw_rover_info()

        self.draw_rovers()
        self.draw_target()
        
        self.update_canvas()
        
    def draw_rover_info(self):
        message = f'Rover detected: {len(self.rover_positions)}'
        message_color = (0, 255, 0)
        light_blue = (255, 232, 197)
        dark_blue = (255, 162, 127)

        tab_width = 200
        tab_height = 30
        tab_x = 30
        tab_y = 150
        
        offset_x = 10
        offset_y = 520
        border_width = 30
        border_height = 25

        pygame.draw.rect(self.surface, dark_blue, pygame.Rect(tab_x + offset_x, tab_y + offset_y, tab_width + border_width, tab_height + border_height))
        pygame.draw.rect(self.surface, light_blue, pygame.Rect(tab_x + offset_x + border_width // 2, tab_y + offset_y + border_height // 2, tab_width, tab_height))

        message_surface = self.font.render(message, True, message_color)
        message_rect = message_surface.get_rect()
        message_rect.center = (tab_x + offset_x + (tab_width // 2) + border_width // 2, 
                               tab_y + offset_y + (tab_height // 2) + border_height // 2)
        self.surface.blit(message_surface, message_rect)

    def draw_rovers(self):
        for name, position in self.rover_positions.items():
            if 0 <= position[0] <= self.screen_width and 0 <= position[1] <= self.screen_height:
                pygame.draw.circle(self.surface, self.blue, position, self.radius)

                matching_data = [
                    rover_data for uri, rover_data in self.result_dict.items()
                    if rover_data and rover_data[0] and rover_data[0][0] == name
                ]

                rover_status = matching_data[0][5][0] if matching_data and matching_data[0][5] else 'Unknown'

                if rover_status == 'Disconnected':
                    small_red_circle_pos = (position[0], position[1] - self.radius + 10)
                    if 0 <= small_red_circle_pos[0] <= self.screen_width and 0 <= small_red_circle_pos[1] <= self.screen_height:
                        pygame.draw.circle(self.surface, self.red, small_red_circle_pos, 5)
                    
                coord_text = f"({position[0]}, {position[1]})"
                coord_surface = self.font.render(coord_text, True, self.black)
                coord_rect = coord_surface.get_rect()
                coord_rect.midtop = (position[0], position[1] + 20)
                self.surface.blit(coord_surface, coord_rect)
                
                text_surface = self.font.render(name, True, self.black)
                text_rect = text_surface.get_rect()
                text_rect.midtop = (position[0], position[1] - 40)
                self.surface.blit(text_surface, text_rect)
            else:
                print(f"Position {position} is out of screen bounds.")  # Debug print
                
    def draw_target(self):
        # Scale factors
        calc_x = int(((self.screen_width - 2) * self.target_pos[0]) / self.real_width)
        calc_y = int(((self.screen_height - 2) * self.target_pos[1]) / self.real_height)
        draw_target_x = calc_x 
        draw_target_y = calc_y

        # Debugging prints
        # print(f"Real target position: {self.target_pos}")
        # print(f"Scale factors - X: {scale_x}, Y: {scale_y}")
        # print(f"Scaled target position before flipping - X: {target_x}, Y: {target_y}")
        # print(f"Final target position on screen - X: {draw_target_x}, Y: {draw_target_y}")

        # Draw the target circle
        pygame.draw.circle(self.surface, self.red, (draw_target_x, draw_target_y), self.radius)

        # Draw the target label and coordinates
        target_label = self.font.render("Target", True, self.black)
        target_coords = self.font.render(f"({self.target_pos[0]}, {self.target_pos[1]})", True, self.black)

        self.surface.blit(target_label, (draw_target_x - target_label.get_width() // 2, draw_target_y - 40))
        self.surface.blit(target_coords, (draw_target_x - target_coords.get_width() // 2, draw_target_y + 20))

    def update_canvas(self):
            
        # Convert Pygame surface to Tkinter PhotoImage
        pygame_image = pygame.surfarray.array3d(self.surface)
        pygame_image = np.transpose(pygame_image, (1, 0, 2))  # Convert to (width, height, channels)
        pygame_image = Image.fromarray(pygame_image)
        tk_image = ImageTk.PhotoImage(image=pygame_image)

        # Update the Tkinter canvas with the new image
        self.canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)
        self.canvas.image = tk_image  # Keep a reference to avoid garbage collection
        
    def stop_pygame(self):
        self.running = False
        self.stop_event.set()
        
def main():
    pygame.init()
    visualization = RoverVisualization()
    visualization.run()

if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root, "Swarm Application")
    root.mainloop()
