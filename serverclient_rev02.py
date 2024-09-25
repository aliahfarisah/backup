import threading
import time
import Pyro5.api
import csv
import numpy as np
import serial
import pylops
from datetime import datetime
from uwb_usb import UwbUsbReader


# Global variables
pos_x, pos_y, pos_z, timestamp = 0, 0, 0, 0
timestamp_list, pos_x_list, pos_y_list, pos_z_list = [], [], [], []
uwb_is_connected = False


def read_uwb():
    global pos_x, pos_y, pos_z, timestamp
    serial_port = "/dev/ttyACM0"
    baud_rate = 115200
    
    print("Thread UWB starting...")
    reader = UwbUsbReader(serial_port)
    # Wait a moment for the connection to be established
    time.sleep(2)
    print(f"Connected to {serial_port} at baud rate {baud_rate}")
    
    #print(reader.serial_connection.is_open)
    #Activates shell mode
    reader.activate_shell_mode()
    time.sleep(1)
    
    uwb_is_connected = True
    
    while True:
        data = reader.read_data()
        # Get timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S.%f')[:-3]

        if data == "dwm>":
            reader.request_lec()
        elif data is None:
            continue

        #print("data:", data)
        data_split = data.split(",")
        if data_split[0] == "DIST":
            #print("Data:", data_split)
            # Check if 'POS' exists in the data list
            if 'POS' in data_split:
                # Find the index of 'POS'
                pos_index = data_split.index('POS')
                #print("Index:", pos_index)
                
                # Extract position data: X, Y, Z, and quality
                pos_x = float(data_split[pos_index + 1])
                pos_y = float(data_split[pos_index + 2])
                pos_z = float(data_split[pos_index + 3])
            else:
                pass
        
        #print(f"Timestamp: {timestamp}, X: {pos_x} meters, Y: {pos_y} meters, Z: {pos_z} meters")

# Function to read rover info from CSV

def read_rover_info(file_path, rover_id):
    other_rovers = []
    rover_data = None
    with open(file_path, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if row["ID"] == rover_id:
                rover_data = row
            else:
                other_rovers.append(row)
    return rover_data, other_rovers


# Define the server class
@Pyro5.api.expose
class RoverServer:
    def __init__(self, rover_id):
        self.rover_id = rover_id

    # Method to get the latest smoothed coordinates
    def get_coordinates(self):
        return {
            'raw_x': pos_x,
            'raw_y': pos_y,
            'time': timestamp,
        }
   

# Function to start the Pyro5 server
def start_server(rover_id, server_port):
    rover_server = RoverServer(rover_id)
    daemon = Pyro5.server.Daemon(host="192.168.50.52", port=server_port)
    uri = daemon.register(rover_server, "coordinates")
    print(f"Server started for Rover {rover_id} with URI: {uri}")
    daemon.requestLoop()

# Function to get coordinates from another rover
def get_coordinates(server_uri):
    with Pyro5.api.Proxy(server_uri) as rover_server:
        data = rover_server.get_coordinates()

        # Check if data is a string, meaning no data is available
        if isinstance(data, str):
            print(f"No data available from the server: {data}")
            return None, None, None
        
        # Otherwise, assume it's a dictionary and extract the needed values
        if isinstance(data, dict):
            xr = data.get('raw_x', None)
            yr = data.get('raw_y', None)
            timestamp = data.get('time', None)

            # Handle the case where some values may be None
            if xr is None or yr is None:
                print("Received data, but 'xr' or 'yr' is None, indicating no recent data.")
            else:
                print(f"Received data: xr={xr}, yr={yr}, time={timestamp}")
                return xr, yr, timestamp
            
            # Return only xr, yr, and timestamp
            return xr, yr, timestamp
        else:
            print(f"Unexpected response type: {type(data)}. Data: {data}")
            return None, None, None  # Return None if the data is not as expected

# Function to run the client task
def client_task(rover_id, other_rovers):
    while True:
        for other_rover in other_rovers:
            try:
                other_rover_uri = f"PYRO:coordinates@{other_rover['IP']}:{other_rover['Port']}"
                xr, yr, timestamp = get_coordinates(other_rover_uri)

                # Check if coordinates are valid and safely access values
                if xr is not None and yr is not None:
                    print(f"Rover {rover_id} received coordinates from Rover {other_rover['ID']}: xr={xr}, yr={yr}, time={timestamp}")
                else:
                    print(f"Rover {rover_id}: No valid data from Rover {other_rover['ID']}")
                    
            except Exception as e:
                print(f"Rover {rover_id} failed to get coordinates from Rover {other_rover['ID']}: {e}")
        
        time.sleep(5)  # Interval between requests


if __name__ == "__main__":
    rover_id = "4"  # Change this for each rover
    filename = "rovers.csv"

    # Read rover info from CSV
    rover_data, other_rovers = read_rover_info(filename, rover_id)
    if not rover_data:
        print(f"Configuration for Rover {rover_id} not found in {filename}")
        exit(1)

    # Initialize UwbUsbReader
    serial_port = "/dev/ttyACM0"  # Replace with actual serial port
    uwb_reader = UwbUsbReader(serial_port)

    # Start the server in a separate thread
    server_thread = threading.Thread(target=start_server, args=(rover_data["ID"], int(rover_data["Port"])))
    server_thread.start()

    uwb_thread = threading.Thread(target=read_uwb)
    uwb_thread.start()
    
    # Start the client task in the main thread
    client_task(rover_data["ID"], other_rovers)
    