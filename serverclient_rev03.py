import csv
import time
from datetime import datetime
import threading
import Pyro5.api
from uwb_usb import UwbUsbReader


# Global variables
pos_x, pos_y, pos_z = 0.0, 0.0, 0.0
timestamp = None
uwb_is_connected = False
other_rovers = []  # This should be populated with data from other rovers

# Function to read rover info from CSV file
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

# Define the server class for Pyro5
@Pyro5.api.expose
class RoverServer:
    def __init__(self, rover_id):
        self.rover_id = rover_id

    # Method to get the latest smoothed coordinates
    def get_coordinates(self):
        return {
            'x': pos_x,
            'y': pos_y,
            'z': pos_z,
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
            x = data.get('x', None)
            y = data.get('y', None)
            z = data.get('z', None)

#             # Handle the case where some values may be None
#             if x is None or y is None:
#                 print("Received data, but 'x' or 'y' is None, indicating no recent data.")
#             else:
#                 print(f"Received data: x={x}, y={y}, time={timestamp}")
#                 return x, y, timestamp

            # Return only x, y, and timestamp
            return x, y, z
        else:
            print(f"Unexpected response type: {type(data)}. Data: {data}")
            return None, None, None  # Return None if the data is not as expected

# Function to get other rovers' coordinates
# def get_other_rover_coordinates():
#     global other_rovers  # Assuming you have `other_rovers` already initialized somewhere
#     all_other_coords = []
    
#     for rover in other_rovers:
#         try:
#             # Create the URI using the IP and Port of the rover
#             other_rover_uri = f"PYRO:coordinates@{rover['IP']}:{rover['Port']}"
#             x, y, z, timestamp = get_coordinates(other_rover_uri)

#             # If coordinates are valid, append the rover's data
#             if x is not None and y is not None:
#                 # Add the rover name and its position
#                 all_other_coords.extend([rover['ID'], 'POS', f"{x}", f"{y}", f"{z}"])
        
#         except Exception as e:
#             print(f"Error fetching data from Rover {rover['ID']}: {e}")
    
#     return all_other_coords

# Function to read UWB data
def read_uwb():
    global pos_x, pos_y, pos_z, timestamp, uwb_is_connected
    serial_port = "/dev/ttyACM0"
    
    print("Thread UWB starting...")
    reader = UwbUsbReader(serial_port)
    time.sleep(2)
    print(f"Connected to {serial_port}")
    
    reader.activate_shell_mode()
    time.sleep(1)
    
    while True:
        data = reader.read_data()
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S.%f')[:-3]

        if data == "dwm>":
            reader.request_lec()
        elif data is None:
            continue

        data_split = data.split(",")

        # Initialize list for formatted output
        uwb_data = ['CORD']

        if data_split[0] == "DIST":
            num_anchors = min(int(data_split[1]), 4)
            uwb_data.append(str(num_anchors))
            #uwb_data.extend(data_split[2:2 + 4 * num_anchors])

            if 'POS' in data_split:
                try:
                    pos_index = data_split.index('POS')
                    pos_x_str = data_split[pos_index + 1]
                    pos_y_str = data_split[pos_index + 2]
                    pos_z_str = data_split[pos_index + 3]

                    pos_x = float(pos_x_str)
                    pos_y = float(pos_y_str)
                    pos_z = float(pos_z_str)

                    uwb_data.extend([f"Rov{rover_id}", f"{pos_x}", f"{pos_y}", f"{pos_z}"])
                except (IndexError, ValueError) as e:
                    print(f"Error processing POS data: {e}")
                    continue

        # Add other rover coordinates
        for other_rover in other_rovers:
            try:
                other_rover_uri = f"PYRO:coordinates@{other_rover['IP']}:{other_rover['Port']}"
                x, y, z = get_coordinates(other_rover_uri)

                if x is not None and y is not None:
                    uwb_data.extend([f"Rov{other_rover['ID']}", f"{x}", f"{y}", f"{z}"])
                    
            except Exception as e:
                print(f"Error fetching data from Rover {other_rover['ID']}: {e}")

        # Print or store the final uwb_data including other rover coordinates
        print(f"UWB Data: {uwb_data}")

        time.sleep(0.1)
        
# def client_task(rover_id, other_rovers):
#     while True:
#         for other_rover in other_rovers:
#             try:
#                 other_rover_uri = f"PYRO:coordinates@{other_rover['IP']}:{other_rover['Port']}"
#                 x, y, z, timestamp = get_coordinates(other_rover_uri)

# #                 # Check if coordinates are valid and safely access values
# #                 if x is not None and y is not None:
# #                     print(f"Rover {rover_id} received coordinates from Rover {other_rover['ID']}: x={x}, y={y}, time={timestamp}")
# #                 else:
# #                     print(f"Rover {rover_id}: No valid data from Rover {other_rover['ID']}")
                    
#             except Exception as e:
#                 print(f"Rover {rover_id} failed to get coordinates from Rover {other_rover['ID']}: {e}\n")
        
#         time.sleep(5)  # Interval between requests


if __name__ == "__main__":
    rover_id = "4"

    # Read rover info from CSV and get other rovers' data
    rover_data, other_rovers = read_rover_info("rovers.csv", rover_id)
    
     # Initialize UwbUsbReader
    serial_port = "/dev/ttyACM0"  # Replace with actual serial port
    uwb_reader = UwbUsbReader(serial_port)

     # Start the server in a separate thread
    server_thread = threading.Thread(target=start_server, args=(rover_data["ID"], int(rover_data["Port"])))
    server_thread.start()

    uwb_thread = threading.Thread(target=read_uwb)
    uwb_thread.start()
    
    # Start the client task in the main thread
    #client_task(rover_data["ID"], other_rovers)