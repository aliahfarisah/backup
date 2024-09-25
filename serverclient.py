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

# UwbUsbReader class for handling serial data
class UwbUsbReader:
    def __init__(self, port, baudrate=115200, timeout=1):
        """
        Initializes the serial connection.
        Args:
            port (str): The port to connect to (e.g., '/dev/ttyACM0').
            baudrate (int): The baud rate for the serial connection.
            timeout (int): Timeout for the serial connection.
        """
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        print(f"Connected to {port} at baud rate {baudrate}")
        time.sleep(2)  # Wait for the serial connection to stabilize

    def read_data(self):
        """
        Reads data from the serial port and processes it.
        """
        if self.ser.inWaiting() > 0:
            data = self.ser.readline().decode('utf-8').strip()
            
            if data == "dwm>":
                self.request_lec()
            elif data:
                data_split = data.split(",")
                if data_split[0] == "DIST":
                    print("Data:", data_split)
                    # Check if 'POS' exists in the data list
                    if 'POS' in data_split:
                        # Find the index of 'POS'
                        pos_index = data_split.index('POS')
                        pos_x = float(data_split[pos_index + 1]) * 1000  # Convert to mm
                        pos_y = float(data_split[pos_index + 2]) * 1000  # Convert to mm
                        return pos_x, pos_y
            return None, None
        return None, None

    def request_lec(self):
        """
        Sends a request for LEC (assuming it's a command to the device).
        """
        self.ser.write(b'LEC\n')

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
        
# Function to update coordinates from serial data
def update_coordinates_from_serial(uwb_reader):
    global points
    while True:
        pos_x, pos_y = uwb_reader.read_data()
        if pos_x is not None and pos_y is not None:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S.%f')[:-3]

            with latest_data_lock:
                latest_data.update({
                   'raw_x': pos_x,
                   'raw_y': pos_y,
                   'time': timestamp
                })
#             print(f"xr: {xr}, yr: {yr}")
        time.sleep(0.1)

# Define the server class
@Pyro5.api.expose
class RoverServer:
    def __init__(self, rover_id):
        self.rover_id = rover_id

    # Method to get the latest smoothed coordinates
    def get_coordinates(self):
        with latest_data_lock:
            if latest_data:
                return {
                    'raw_x': latest_data.get('raw_x'),
                    'raw_y': latest_data.get('raw_y'),
                    'time': latest_data.get('time'),
                }
            else:
                return "No data available"

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

    # Start updating coordinates from serial data
    serial_thread = threading.Thread(target=update_coordinates_from_serial, args=(uwb_reader,))
    serial_thread.start()
    
    # Start the client task in the main thread
    client_task(rover_data["ID"], other_rovers)
    
Data: ['DIST', '4', 'AN0', 'DC1A', '0.00', '0.00', '0.00', '0.00', 'AN1', 'D32D', '1.50', '0.00', '0.00', '1.43', 'AN2', 'DD84', '0.00', '0.75', '0.00', '0.63', 'AN3', '19AB', '1.50', '0.75', '0.00', '1.27', 'POS', '0.19', '-0.19', '-0.15', '70']
Data: ['DIST', '4', 'AN0', 'DC1A', '0.00', '0.00', '0.00', '0.00', 'AN1', 'D32D', '1.50', '0.00', '0.00', '1.42', 'AN2', 'DD84', '0.00', '0.75', '0.00', '0.64', 'AN3', '19AB', '1.50', '0.75', '0.00', '1.27', 'POS', '0.2DIST', '4', 'AN0', 'DC1A', '0.00', '0.00', '0.00', '0.00', 'AN1', 'D32D', '1.50', '0.00', '0.00', '1.47', 'AN2', 'DD84', '0.00', '0.75', '0.00', '0.67', 'AN3', '19AB', '1.50', '0.75', '0.00', '1.29', 'POS', '0.18', '-0.15', '-0.11', '79']
Exception in thread Thread-2:
Traceback (most recent call last):
  File "/usr/lib/python3.9/threading.py", line 954, in _bootstrap_inner
    self.run()
  File "/usr/lib/python3.9/threading.py", line 892, in run
    self._target(*self._args, **self._kwargs)
  File "/home/pi/Desktop/lightShow/ssw.py", line 81, in update_coordinates_from_serial
    pos_x, pos_y = uwb_reader.read_data()
  File "/home/pi/Desktop/lightShow/ssw.py", line 51, in read_data
    pos_x = float(data_split[pos_index + 1]) * 1000  # Convert to mm
ValueError: could not convert string to float: '0.2DIST'