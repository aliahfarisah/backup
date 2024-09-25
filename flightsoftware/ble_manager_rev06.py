import asyncio
import threading
import time
import pandas as pd
import numpy as np
import datetime
import pygame
import math
from bleak import BleakClient, BleakScanner
from collections import deque
from filterpy.kalman import KalmanFilter
from scipy.signal import butter, filtfilt, savgol_filter

class BLEDeviceManager:
    def __init__(self):
        self.filtered_devices = []
        self.device_info = pd.DataFrame(columns=['Name', 'Status', 'X', 'Y', 'Z', 'Time'])
        self.num_connected = 0
        self.lock = threading.Lock()
        self.connected = False
        self.xr = 0
        self.yr = 0

    async def scan_for_devices(self, scan_time=5.0, name_filters=''):
        print("Scanning for devices...")
        scanner = BleakScanner()

        await scanner.start()
        await asyncio.sleep(scan_time)
        await scanner.stop()

        devices = scanner.discovered_devices_and_advertisement_data
        for info, advertisement_data in devices.items():
            device = advertisement_data[0]
            if device.name and any(name_filter in device.name for name_filter in name_filters):
                print(f"Found device: {device.name} ({device.address})")
                self.filtered_devices.append(device)
               
                return True
               
        print("=" * 50)

    async def read_characteristic(self, device_address, device_name, characteristic_uuid, locData_uuid):
        while True:
            client = BleakClient(device_address)
            try:
                await client.connect(timeout=60.0)
                print(f"Connected to {device_name} at {device_address}")

                with self.lock:
                    if device_name not in self.device_info['Name'].values:
                        self.device_info.loc[self.num_connected, 'Name'] = device_name
                        self.num_connected += 1
                    self.device_info.loc[self.device_info['Name'] == device_name, 'Status'] = 'Connected'
                   
                self.connected = True

                while client.is_connected:
                    try:
                        value = bytes(await client.read_gatt_char(locData_uuid))
                        hex_values = [f'{byte:02x}' for byte in value]
                        x_coord = '0x' + str(hex_values[2]) + str(hex_values[1])
                        y_coord = '0x' + str(hex_values[6]) + str(hex_values[5])
                        z_coord = '0x' + str(hex_values[10]) + str(hex_values[9])

                        x_dec = int(x_coord, 16)
                        y_dec = int(y_coord, 16)
                        z_dec = int(z_coord, 16)
                       
                        self.xr = x_dec
                        self.yr = y_dec
                        #print("xr", self.xr)
                        #print("yr", self.yr)
                       
                        with self.lock:
                            self.device_info.loc[self.device_info['Name'] == device_name, 'X'] = x_dec
                            self.device_info.loc[self.device_info['Name'] == device_name, 'Y'] = y_dec
                            self.device_info.loc[self.device_info['Name'] == device_name, 'Z'] = z_dec
                            self.device_info.loc[self.device_info['Name'] == device_name, 'Time'] = datetime.datetime.now()

                        print(f"Updated device_info:\n{self.device_info}")

                        await asyncio.sleep(0.05)

                    except Exception as e:
                        print(f"Error reading from {device_name}: {e}")
                        break

            except Exception as e:
                print(f"Failed to connect to {device_name} at {device_address}: {e}")

            finally:
                await client.disconnect()
                print(f"Disconnected from {device_name} at {device_address}")
                with self.lock:
                    self.device_info.loc[self.device_info['Name'] == device_name, 'Status'] = 'Disconnected'

            await asyncio.sleep(10)

    def start_connection(self, id_rover):
        async def inner():
            #name_filters = ["Anc", "Rov"]
            rover_id = "Rov" + str(id_rover)
            print("Searching for", rover_id)
            name_filters = [rover_id]
            isFound = False
            while not isFound:
                isFound = await self.scan_for_devices(name_filters=name_filters)

            characteristic_uuid = '680c21d9-c946-4c1f-9c11-baa1c21329e7'
            locData_uuid = '003bbdf2-c634-4b3d-ab56-7ec889b89a37'
            data_threads = []

            for device in self.filtered_devices:
                device_name = device.name
                device_address = device.address
               
                data_thread = threading.Thread(target=lambda: asyncio.run(
                    self.read_characteristic(device_address, device_name, characteristic_uuid, locData_uuid)), daemon=True)
                data_threads.append(data_thread)
                data_thread.start()

        asyncio.run(inner())

    def get_device_info(self):
        with self.lock:
            return self.device_info.copy()

    def is_connected(self):
        with self.lock:
            return self.connected, self.device_info.copy()
        
import serial
import struct
import time

class SerialReader:
    def __init__(self, port="COM6", baud_rate=115200):
        self.port = port
        self.baud_rate = baud_rate
        self.ser = serial.Serial(self.port, self.baud_rate, timeout=1)
        print(f"Connected to {self.port} at baud rate {self.baud_rate}")
        time.sleep(2)  # Give time to establish the connection
        self.pos_x_value = 0
        self.pos_y_value = 0

    def send_command(self, command):
        """ Send a command to the serial device. """
        command_array = bytes(command)
        self.ser.write(command_array)
        response = self.ser.readline()
        return response

    def get_latest_data(self):
        """ Retrieve the latest X, Y coordinates from the serial device. """
        # Send the loc_get command to get position
        command_array = bytes([0x0C, 0x00])
        self.ser.write(command_array)

        # Read the response
        response = self.ser.readline()

        if len(response) >= 17:  # Ensure the response has enough data
            try:
                # Extract position data from the response
                pos_x = response[5:9]
                pos_y = response[9:13]
                # Convert byte array to integers (little-endian)
                self.pos_x_value = struct.unpack('<I', pos_x)[0]
                self.pos_y_value = struct.unpack('<I', pos_y)[0]
            except struct.error:
                print("Error unpacking data")
        else:
            print("Incomplete data received")

        # Return the X, Y position as a dictionary
        return {'X': self.pos_x_value, 'Y': self.pos_y_value}

        
        
def run_pygame_visualization(ble_manager):
    pygame.init()
    screen = pygame.display.set_mode((1500, 750))
    pygame.display.set_caption("BLE Rover Coordinates")
    
    real_width = 1500
    real_height = 750
    
    red = (255, 0, 0)
    font = pygame.font.Font(None, 36)


    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((255, 255, 255))  # Clear the screen with black

        connected, device_info = ble_manager.is_connected()
        
        if connected:
            # Display BLE data if connected
            x = device_info['X'].values[0] if not math.isnan(device_info['X'].values[0]) else None
            y = device_info['Y'].values[0] if not math.isnan(device_info['Y'].values[0]) else None
            
            if x is not None and y is not None and isinstance(x, (int, float)) and isinstance(y, (int, float)):
                if not math.isnan(x) and not math.isnan(y):
                    # Convert BLE coordinates to screen space
                    screen_x = int(x % real_width)
                    screen_y = int(y % real_height)
                    
                    # Draw the rover as a circle
                    pygame.draw.circle(screen, red, (screen_x, screen_y), 10)
                    
                    # Render BLE coordinates text
                    coords_text = font.render(f"BLE: ({int(x)}, {int(y)})", True, red)
                    screen.blit(coords_text, (10, 10))
        else:
            # If not connected to BLE, use Serial data
            serial_data = serial_reader.get_latest_data()  # Get the latest data from the SerialReader
            if serial_data:
                x = serial_data['X']
                y = serial_data['Y']
                
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    # Convert Serial coordinates to screen space
                    screen_x = int(x % real_width)
                    screen_y = int(y % real_height)
                    
                    # Draw the rover as a circle (use a different color for Serial data)
                    pygame.draw.circle(screen, blue, (screen_x, screen_y), 10)
                    
                    # Render Serial coordinates text
                    coords_text = font.render(f"Serial: ({int(x)}, {int(y)})", True, blue)
                    screen.blit(coords_text, (10, 10))
                        
        pygame.display.update()

    pygame.quit()
    
    
if __name__ == "__main__":
    ble_manager = BLEDeviceManager()

    # Start BLE connection in a separate thread to avoid blocking the main thread
    ble_thread = threading.Thread(target=ble_manager.start_connection(id_rover=3))
    ble_thread.start()

    # Run the Pygame visualization
    run_pygame_visualization(ble_manager)