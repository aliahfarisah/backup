import csv
import time
from datetime import datetime
import threading
import Pyro5.api
from uwb_usb import UwbUsbReader

# Global variables
pos_x, pos_y, pos_z = 0.0, 0.0, 0.0
timestamp = None
other_rovers = []  # This should be populated with data from other rovers
num_anchors = 0  # Number of anchors initialized

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

    # Method to get the latest coordinates
    def get_coordinates(self):
        return {
            'x': pos_x,
            'y': pos_y,
            'z': pos_z,
        }
        
    def get_uwb_data(self):
        global latest_uwb_data
        return latest_uwb_data

# Function to start the Pyro5 server
def start_server(rover_id, server_port):
    rover_server = RoverServer(rover_id)
    daemon = Pyro5.server.Daemon(host="192.168.50.215", port=server_port)
    uri = daemon.register(rover_server, "coordinates")
    print(f"Server started for Rover {rover_id} with URI: {uri}")
    daemon.requestLoop()

# Function to get coordinates from another rover
def get_coordinates(server_uri):
    with Pyro5.api.Proxy(server_uri) as rover_server:
        rover_server._pyroTimeout = 2.0
        try:
            data = rover_server.get_coordinates()

            if isinstance(data, str):
                print(f"No data available from the server: {data}")
                return None, None, None
            
            if isinstance(data, dict):
                x = data.get('x', None)
                y = data.get('y', None)
                z = data.get('z', None)
                return x, y, z
            else:
                print(f"Unexpected response type: {type(data)}. Data: {data}")
                return None, None, None
        except Pyro5.errors.TimeoutError:
            print(f"Timeout: Unable to reach the rover at {server_uri}")
            return None, None, None
        except Pyro5.errors.CommunicationError as e:
            print(f"Communication Error: {e}")
            return None, None, None

# Function to read UWB data
def read_uwb():
    global pos_x, pos_y, pos_z, timestamp, num_anchors
    serial_port = "/dev/ttyACM0"
    
    #print("Thread UWB starting...")
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

        if data_split[0] == "DIST":
            num_anchors = min(int(data_split[1]), 4)

            if 'POS' in data_split:
                try:
                    pos_index = data_split.index('POS')
                    pos_x = float(data_split[pos_index + 1])
                    pos_y = float(data_split[pos_index + 2])
                    pos_z = float(data_split[pos_index + 3])

                except (IndexError, ValueError) as e:
                    print(f"Error processing POS data: {e}")
                    continue

        time.sleep(0.1)

# Function to fetch other rovers' coordinates in a thread
def fetch_other_rovers_coordinates(rover_id):
    global other_rovers, latest_uwb_data
    while True:
        uwb_data = ['CORD']  # Start with UWB data
        
        fetched_rover_count = 0

        # Include own coordinates first
        uwb_data.extend([
            f"{num_anchors}",
            f"{fetched_rover_count}", 
            f"Rov{rover_id}",
            f"{pos_x}",
            f"{pos_y}",
            f"{pos_z}"
        ])

        for other_rover in other_rovers:
            try:
                other_rover_uri = f"PYRO:coordinates@{other_rover['IP']}:{other_rover['Port']}"
                x, y, z = get_coordinates(other_rover_uri)

                if x is not None and y is not None:
                    fetched_rover_count += 1  # Increment the count
                    uwb_data.extend([
                        f"Rov{other_rover['ID']}",
                        f"{x}",
                        f"{y}",
                        f"{z}"
                    ])

            except Exception as e:
                print(f"Error fetching data from Rover {other_rover['ID']}: {e}")

        # Update the fetched rover count
        uwb_data[2] = f"{fetched_rover_count}"
        
        latest_uwb_data = uwb_data

        # Print or store the final uwb_data including others and self coordinates
        print(f"UWB Data: {uwb_data}")
        time.sleep(0.2)  # Adjust the interval as needed


if __name__ == "__main__":
    rover_id = "2"

    # Read rover info from CSV and get other rovers' data
    rover_data, other_rovers = read_rover_info("rovers.csv", rover_id)
    
    # Start the server in a separate thread
    server_thread = threading.Thread(target=start_server, args=(rover_data["ID"], int(rover_data["Port"])))
    server_thread.start()

    # Start the UWB reader in a separate thread
    uwb_thread = threading.Thread(target=read_uwb)
    uwb_thread.start()

    # Start the thread to fetch coordinates from other rovers
    fetch_thread = threading.Thread(target=fetch_other_rovers_coordinates, args=(rover_data["ID"],))
    fetch_thread.start()
    