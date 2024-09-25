import asyncio
import threading
import time
import pandas as pd
import datetime
from bleak import BleakClient, BleakScanner

class BLEDeviceManager:
    def __init__(self):
        self.filtered_devices = []
        self.device_info = pd.DataFrame(columns=['Name', 'Status', 'X', 'Y', 'Z', 'Time (msec)'])
        self.all_device_info = pd.DataFrame(columns=['Time (msec)', 'X', 'Y', 'Z'])
        self.num_connected = 0
        self.lock = threading.Lock()
        self.connected = False
        self.xr = 0
        self.yr = 0
        self.last_update_time = {}
        self.total_elapsed_time = {}

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
                        
                        current_time = datetime.datetime.now()
                        current_time_msec = int(current_time.timestamp() * 1000)
                        
                        if device_name in self.last_update_time:
                            elapsed_time = (current_time - self.last_update_time[device_name]).total_seconds() * 1000
                        else:
                            elapsed_time = 0

                        if device_name not in self.total_elapsed_time:
                            self.total_elapsed_time[device_name] = 0
                        
                        self.total_elapsed_time[device_name] += elapsed_time

                        print(f"Updating time for {device_name}: {int(self.total_elapsed_time[device_name])}ms (Elapsed: {int(elapsed_time)}ms)")

                        with self.lock:
                            self.device_info.loc[self.device_info['Name'] == device_name, 'X'] = x_dec
                            self.device_info.loc[self.device_info['Name'] == device_name, 'Y'] = y_dec
                            self.device_info.loc[self.device_info['Name'] == device_name, 'Z'] = z_dec
                            self.device_info.loc[self.device_info['Name'] == device_name, 'Time (msec)'] = int(self.total_elapsed_time[device_name])
                            
                            print(f"Updated device info:\n{self.device_info}")

                            # Append new entries to the all_device_info DataFrame
                            new_entry = pd.DataFrame({
                                'Time (msec)': [int(self.total_elapsed_time[device_name])],
                                'X': [x_dec],
                                'Y': [y_dec],
                                'Z': [z_dec]
                            })
                            self.all_device_info = pd.concat([self.all_device_info, new_entry], ignore_index=True)

                        csv_file_path = 'device_info.csv'
                        self.save_to_csv(csv_file_path)

                        self.last_update_time[device_name] = current_time

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

    def save_to_csv(self, file_path):
        with self.lock:
            self.device_info.to_csv(file_path, index=False)
