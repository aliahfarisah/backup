import threading
import time
import Pyro5.api
import csv
import numpy as np
import serial
import pylops
from datetime import datetime

# Global variables for shared data and locking
latest_data = {}
latest_data_lock = threading.Lock()
points = np.zeros((10, 2))

# Pylops 1D smoothing
N = 10
nsmooth = 7
Sop = pylops.Smoothing1D(nsmooth=nsmooth, dims=[N], dtype="float32")

# Define the server class
@Pyro5.api.expose
class RoverServer:
    def __init__(self, rover_id):
        self.rover_id = rover_id

    # Method to get the latest smoothed coordinates
    def get_coordinates(self):
        with latest_data_lock:
            if latest_data:
                # Convert numpy arrays to lists for serialization
                x_smooth_list = latest_data.get('x_smooth', []).tolist()
                y_smooth_list = latest_data.get('y_smooth', []).tolist()
                
                return {
                    'raw_x': latest_data.get('raw_x'),
                    'raw_y': latest_data.get('raw_y'),
                    'x_smooth': x_smooth_list,
                    'y_smooth': y_smooth_list,
                    'xr': latest_data.get('xr'),
                    'yr': latest_data.get('yr'),
                    'time': latest_data.get('time'),
                }
            else:
                return "No data available"

# Function to start the Pyro5 server
def start_server(rover_id, server_port):
    rover_server = RoverServer(rover_id)
    daemon = Pyro5.server.Daemon(host="192.168.50.251", port=server_port)
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
            xr = data.get('xr', None)
            yr = data.get('yr', None)
            timestamp = data.get('time', None)

            # Optionally convert lists back to numpy arrays
            if 'x_smooth' in data:
                x_smooth = np.array(data['x_smooth'])
            else:
                x_smooth = None

            if 'y_smooth' in data:
                y_smooth = np.array(data['y_smooth'])
            else:
                y_smooth = None

            # Handle the case where some values may be None
            if xr is None or yr is None:
                print("Received data, but 'xr' or 'yr' is None, indicating no recent data.")
            else:
                print(f"Received data: xr={xr}, yr={yr}, time={timestamp}")
            
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
                    print(f"Rover {rover_id} received coordinates: xr={xr}, yr={yr}, time={timestamp}")
                else:
                    print(f"Rover {rover_id}: No valid data from Rover {other_rover['ID']}")
                    
            except Exception as e:
                print(f"Rover {rover_id} failed to get coordinates from Rover {other_rover['ID']}: {e}")
        
        time.sleep(5)  # Interval between requests

# Function to update coordinates from serial data
def update_coordinates_from_serial(ser):
    global points
    while True:
        if ser.inWaiting() > 0:
            response = ser.readline().decode('utf-8').strip().split(',')
            print(f"Received data: {response}")
            
            try:
                idx_pos = response.index("POS")
                if idx_pos != -1:
                    pos_x = float(response[idx_pos + 1]) * 1000  # Convert to mm
                    pos_y = float(response[idx_pos + 2]) * 1000  # Convert to mm

                    # Update the points array and apply smoothing
                    points = np.roll(points, -1, axis=0)
                    points[-1] = [pos_x, pos_y]

                    # Apply smoothing operator
                    x_smooth = Sop @ points[:, 0]
                    y_smooth = Sop @ points[:, 1]

                    # Calculate smoothed maximum values
                    xr = int(max(x_smooth))  # Smoothed x-coordinate
                    yr = int(max(y_smooth))  # Smoothed y-coordinate
                    
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S.%f')[:-3]

                    with latest_data_lock:
                        latest_data.update({
                           'raw_x': pos_x,
                           'raw_y': pos_y,
                           'x_smooth': x_smooth,
                           'y_smooth': y_smooth,
                           'xr': xr,
                           'yr': yr,
                           'time': timestamp
                        })
                    print(f"xr: {xr}")
            except (ValueError, IndexError):
                print(f"Error parsing serial data: {response}")
        time.sleep(0.1)

# Function to read configuration from CSV
def read_config(file_path, rover_id):
    other_rovers = []
    my_config = None
    with open(file_path, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if row["ID"] == rover_id:
                my_config = row
            else:
                other_rovers.append(row)
    return my_config, other_rovers

if __name__ == "__main__":
    rover_id = "3"  # Change this for each rover
    config_file = "rovers.csv"

    # Read configuration from CSV
    my_config, other_rovers = read_config(config_file, rover_id)
    if not my_config:
        print(f"Configuration for Rover {rover_id} not found in {config_file}")
        exit(1)

    # Connect to the serial port
    serial_port = "/dev/ttyACM0"  # Replace with actual serial port
    baud_rate = 115200
    try:
        ser = serial.Serial(serial_port, baud_rate, timeout=1)
        print(f"Connected to {serial_port} at baud rate {baud_rate}")
        time.sleep(2)  # Wait for the serial connection to stabilize
    except serial.SerialException as e:
        print(f"Failed to connect to {serial_port}: {e}")
        exit(1)

    # Start the server in a separate thread
    server_thread = threading.Thread(target=start_server, args=(my_config["ID"], int(my_config["Port"])))
    server_thread.start()

    # Start updating coordinates from serial data
    serial_thread = threading.Thread(target=update_coordinates_from_serial, args=(ser,))
    serial_thread.start()
    
    # Start the client task in the main thread
    client_task(my_config["ID"], other_rovers)
