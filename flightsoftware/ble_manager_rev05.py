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
        
class MovingAverage:
    def __init__(self, window_size, outlier_threshold=3):
        self.window_size = window_size
        self.data_x = deque(maxlen=window_size)
        self.data_y = deque(maxlen=window_size)
        self.outlier_threshold = outlier_threshold
    
    def add(self, x_value, y_value):
        # Add new values to the window
        self.data_x.append(x_value)
        self.data_y.append(y_value)
        
        # Convert the deque to numpy arrays for easier calculations
        window_data_x = np.array(self.data_x)
        window_data_y = np.array(self.data_y)
        
        # Calculate the mean and standard deviation for the window
        mean_x = window_data_x.mean()
        std_x = window_data_x.std()
        mean_y = window_data_y.mean()
        std_y = window_data_y.std()
        
        # Calculate Z-scores using the mean and standard deviation
        z_x, z_y = 0, 0  # Initialize Z-scores
        
        if std_x != 0:  # Prevent division by zero
            z_x = (x_value - mean_x) / std_x
        if std_y != 0:  # Prevent division by zero
            z_y = (y_value - mean_y) / std_y
        
        # Check if the latest value is an outlier
        is_outlier = abs(z_x) > self.outlier_threshold or abs(z_y) > self.outlier_threshold
        
        if is_outlier:
            # If it's an outlier, ignore this value
            return None, None
        
        # Return the average of the current window
        return window_data_x.mean(), window_data_y.mean()
        

class KalmanFilterWrapper:
    def __init__(self):
        self.kf = KalmanFilter(dim_x=2, dim_z=1)
        self.kf.F = np.array([[1, 1], [0, 1]])  # State transition matrix
        self.kf.H = np.array([[1, 0]])  # Measurement function
        self.kf.P *= 1000.0  # Covariance matrix
        self.kf.R = 5  # Measurement noise
        self.kf.Q = np.array([[1, 0], [0, 1]])  # Process noise

    def update(self, measurement):
        self.kf.predict()
        self.kf.update(measurement)
        return self.kf.x[0]
    
class ExponentialMovingAverage:
    def __init__(self, alpha):
        self.alpha = alpha
        self.ema = None
    
    def update(self, value):
        if self.ema is None:
            self.ema = value
        else:
            self.ema = self.alpha * value + (1 - self.alpha) * self.ema
        return self.ema
    
class LowPassFilter:
    def __init__(self, alpha):
        self.alpha = alpha
        self.filtered_value = None
    
    def update(self, value):
        if self.filtered_value is None:
            self.filtered_value = value
        else:
            self.filtered_value = self.alpha * value + (1 - self.alpha) * self.filtered_value
        return self.filtered_value

class ButterworthLowPassFilter:
    def __init__(self, cutoff_freq, fs, order=4):
        self.cutoff_freq = cutoff_freq
        self.fs = fs
        self.order = order
        self.b, self.a = butter(order, cutoff_freq / (0.5 * fs), btype='low')
        self.prev_data = np.zeros(1)  # Initialize previous data
    
    def update(self, value):
        filtered_value = filtfilt(self.b, self.a, [value], padlen=0)[0]
        return filtered_value
    
class SavitzkyGolayFilter:
    def __init__(self, window_size, poly_order):
        self.window_size = window_size
        self.poly_order = poly_order

    def update(self, data):
        if len(data) < self.window_size:
            # Not enough data points to apply the filter
            return data
        return savgol_filter(data, self.window_size, self.poly_order)
    
class ExtendedKalmanFilter:
    def __init__(self, dt):
        self.dt = dt
        self.x = np.array([0., 0.])  # Initial state (position, velocity)
        self.P = np.eye(2) * 0.1  # Initial state covariance
        self.Q = np.eye(2) * 0.1  # Process noise covariance
        self.R = np.array([[0.1]])  # Measurement noise covariance
        self.F = np.eye(2)
        self.H = np.array([[1, 0],
                           [0, 1]])  # Measurement matrix

    def predict(self):
        # Predict the next state
        self.x = np.dot(self.F, self.x)
        # Predict the next covariance matrix
        self.P = np.dot(self.F, np.dot(self.P, self.F.T)) + self.Q

    def update(self, z):
        # Measurement residual
        y = z - np.dot(self.H, self.x)
        # Residual covariance
        S = np.dot(self.H, np.dot(self.P, self.H.T)) + self.R
        # Kalman Gain
        K = np.dot(self.P, np.dot(self.H.T, np.linalg.inv(S)))
        # Update the state estimate
        self.x = self.x + np.dot(K, y)
        # Update the covariance matrix
        self.P = self.P - np.dot(K, np.dot(self.H, self.P))
        
def run_pygame_visualization(ble_manager):
    pygame.init()
    screen = pygame.display.set_mode((1500, 750))
    pygame.display.set_caption("BLE Rover Coordinates")
    
    real_width = 1500
    real_height = 750
    
    # Initialize filters and moving averages
    x_kf = KalmanFilterWrapper()
    y_kf = KalmanFilterWrapper()
    moving_avg_10 = MovingAverage(window_size=10)
    moving_avg_15 = MovingAverage(window_size=15)
    
    alpha = 0.1  # Example smoothing factor for EMA
    cutoff_freq = 0.1  # Example cutoff frequency for Butterworth filter
    fs = 10  # Example sampling frequency in Hz

    x_ema = ExponentialMovingAverage(alpha)
    y_ema = ExponentialMovingAverage(alpha)
    x_lp = LowPassFilter(alpha)
    y_lp = LowPassFilter(alpha)
    x_blp = ButterworthLowPassFilter(cutoff_freq, fs)
    y_blp = ButterworthLowPassFilter(cutoff_freq, fs)
    sg_filter = SavitzkyGolayFilter(window_size=11, poly_order=2)
    
    dt = 1.0  # Example time step
    ekf = ExtendedKalmanFilter(dt)
    
    red = (255, 0, 0)
    green = (0, 255, 0)
    blue = (0, 0, 255)
    teal = (0, 255, 255)
    olive = (128, 128, 0)
    black = (0, 0, 0)
    magenta = (255, 0, 255)
    orange = (255, 165, 0)
    gray = (128, 128, 128)
    purple = (128, 0, 128)
    brown = (165, 42, 42)
    dark_green = (0, 100, 0)
    font = pygame.font.Font(None, 36)
    
    columns = ['Time', 'Raw X', 'Raw Y', 'Avg X (10)', 'Avg Y (10)', 'Avg X (15)', 'Avg Y (15)', 'Kalman X (10)', 'Kalman Y (10)', 'Kalman X (15)',
               'Kalman Y (15)', 'EMA X', 'EMA Y', 'Low Pass X', 'Low Pass Y', 'Butterworth Low Pass X', 'Butterworth Low Pass Y',
               'Savitzky-Golay_Low Pass X', 'Savitzky-Golay_Low Pass Y', 'EMA Savitzky-Golay_Low Pass X', 'EMA Savitzky-Golay_Low Pass Y',
               'Kalman EMA Savitzky-Golay_Low Pass X', 'Kalman EMA Savitzky-Golay_Low Pass Y', 'EKF X', 'EKF Y']
    df = pd.DataFrame(columns=columns)
    
    x_data_buffer = []
    y_data_buffer = []

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((255, 255, 255))  # Clear the screen with black

        connected, device_info = ble_manager.is_connected()
        if connected:
            x = device_info['X'].values[0] if not math.isnan(device_info['X'].values[0]) else None
            y = device_info['Y'].values[0] if not math.isnan(device_info['Y'].values[0]) else None
            time = device_info['Time'].values[0] if not math.isnan(device_info['Y'].values[0]) else None
            
            if x is not None and y is not None and isinstance(x, (int, float)) and isinstance(y, (int, float)):
                if not math.isnan(x) and not math.isnan(y):
                    
                    # Update Kalman Filter and Moving Average
                    avg_x_10, avg_y_10 = moving_avg_10.add(x, y)
                    avg_x_15, avg_y_15 = moving_avg_15.add(x, y)
                    
                    if avg_x_10 is None or avg_y_10 is None or avg_x_15 is None or avg_y_15 is None:
                        continue
                    
                    kalman_x_10 = x_kf.update(avg_x_10)
                    kalman_y_10 = y_kf.update(avg_y_10)
                    kalman_x_15 = x_kf.update(avg_x_15)
                    kalman_y_15 = y_kf.update(avg_y_15)
                    ema_x = x_ema.update(x)
                    ema_y = y_ema.update(y)
                    lp_x = x_lp.update(x)
                    lp_y = y_lp.update(y)
                    blp_x = x_blp.update(x)
                    blp_y = y_blp.update(y)
                    
                    measurement = np.array([x, y])
                    # Predict the next state
                    ekf.predict()
                    # Update with the new measurement
                    ekf.update(measurement)  # Update with only the position measurement
                    ekf_x = ekf.x[0]
                    ekf_y = ekf.x[1]
                    
                    # Buffer the data
                    x_data_buffer.append(lp_x)
                    y_data_buffer.append(lp_y)

                    # Apply Savitzky-Golay Filter if enough data points
                    if len(x_data_buffer) > sg_filter.window_size:
                        sg_x = sg_filter.update(x_data_buffer)
                        sg_y = sg_filter.update(y_data_buffer)
                        
                        ema_sg_x = x_ema.update(sg_x[-1])
                        ema_sg_y = y_ema.update(sg_y[-1])
                        
                        kalman_ema_sg_x = x_kf.update(ema_sg_x)
                        kalman_ema_sg_y = y_kf.update(ema_sg_y)
                    
                        # Convert coordinates to screen space
                        screen_x = int(x % real_width)
                        screen_y = int(y % real_height)
                        kalman_x_10_screen = int(kalman_x_10 % real_width)
                        kalman_y_10_screen = int(kalman_y_10 % real_height)
                        kalman_x_15_screen = int(kalman_x_15 % real_width)
                        kalman_y_15_screen = int(kalman_y_15 % real_height)
                        avg_x_10_screen = int(avg_x_10 % real_width)
                        avg_y_10_screen = int(avg_y_10 % real_height)
                        avg_x_15_screen = int(avg_x_15 % real_width)
                        avg_y_15_screen = int(avg_y_15 % real_height)
                        ema_x_screen = int(ema_x % real_width)
                        ema_y_screen = int(ema_y % real_height)
                        lp_x_screen = int(lp_x % real_width)
                        lp_y_screen = int(lp_y % real_height)
                        blp_x_screen = int(blp_x % real_width)
                        blp_y_screen = int(blp_y % real_height)
                        
                        # Use the latest smoothed data point
                        sg_x_screen = int(sg_x[-1] % real_width)
                        sg_y_screen = int(sg_y[-1] % real_height)
                        ema_sg_x_screen = int(ema_sg_x % real_width)
                        ema_sg_y_screen = int(ema_sg_y % real_height)
                        kalman_ema_sg_x_screen = int(kalman_ema_sg_x % real_width)
                        kalman_ema_sg_y_screen = int(kalman_ema_sg_y % real_height)
                        ekf_x_screen = int(ekf_x % real_width)
                        ekf_y_screen = int(ekf_y % real_height)


                        # Draw the rover as a circle
                        pygame.draw.circle(screen, red, (screen_x, screen_y), 10)
                        pygame.draw.circle(screen, blue, (kalman_x_10_screen, kalman_y_10_screen), 10)
                        pygame.draw.circle(screen, olive, (kalman_x_15_screen, kalman_y_15_screen), 10)
                        pygame.draw.circle(screen, green, (avg_x_10_screen, avg_y_10_screen), 10)
                        pygame.draw.circle(screen, teal, (avg_x_15_screen, avg_y_15_screen), 10)
                        pygame.draw.circle(screen, black, (ema_x_screen, ema_y_screen), 10)
                        pygame.draw.circle(screen, magenta, (lp_x_screen, lp_y_screen), 10)
                        pygame.draw.circle(screen, orange, (blp_x_screen, blp_y_screen), 10)
                        pygame.draw.circle(screen, gray, (sg_x_screen, sg_y_screen), 10)
                        pygame.draw.circle(screen, purple, (ema_sg_x_screen, ema_sg_y_screen), 10)
                        pygame.draw.circle(screen, brown, (kalman_ema_sg_x_screen, kalman_ema_sg_y_screen), 10)
                        pygame.draw.circle(screen, dark_green, (ekf_x_screen, ekf_y_screen), 10)

                        # Render the text for the raw data
                        #raw_text = font.render("Raw", True, black)
                        #raw_pos = raw_text.get_rect(center=(screen_x, screen_y + 20))
                        #screen.blit(raw_text, raw_pos)

                        # Render the text for the Kalman filter data
                        #kalman_text = font.render("Kalman", True, black)
                        #kalman_pos = kalman_text.get_rect(center=(kalman_x_screen, kalman_y_screen + 20))
                        #screen.blit(kalman_text, kalman_pos)

                        # Render the text for the moving average data
                        #avg_text = font.render("Avg", True, black)
                        #avg_pos = avg_text.get_rect(center=(avg_x_screen, avg_y_screen + 20))
                        #screen.blit(avg_text, avg_pos)

                        # Render coordinates text
                        coords_text = font.render(f"Raw: ({int(x)}, {int(y)})", True, red)
                        #coords_pos = coords_text.get_rect(center=(screen_x, screen_y + 40))
                        screen.blit(coords_text, (10, 10))
                        
                        kalman_10_coords_text = font.render(f"Kalman_10: ({int(kalman_x_10)}, {int(kalman_y_10)})", True, blue)
                        #kalman_coords_pos = kalman_coords_text.get_rect(center=(kalman_x_screen, kalman_y_screen + 40))
                        screen.blit(kalman_10_coords_text, (10, 130))

                        # Render Kalman coordinates text
                        kalman_15_coords_text = font.render(f"Kalman_15: ({int(kalman_x_15)}, {int(kalman_y_15)})", True, olive)
                        #kalman_coords_pos = kalman_coords_text.get_rect(center=(kalman_x_screen, kalman_y_screen + 40))
                        screen.blit(kalman_15_coords_text, (10, 170))

                        # Render Moving Average coordinates text
                        avg_10_coords_text = font.render(f"Avg_10: ({int(avg_x_10)}, {int(avg_y_10)})", True, green)
                        #avg_coords_pos = avg_coords_text.get_rect(center=(avg_x_screen, avg_y_screen + 40))
                        screen.blit(avg_10_coords_text, (10, 50))
                        
                        avg_15_coords_text = font.render(f"Avg_15: ({int(avg_x_15)}, {int(avg_y_15)})", True, teal)
                        screen.blit(avg_15_coords_text, (10, 90))
                        
                        ema_coords_text = font.render(f"EMA: ({int(ema_x)}, {int(ema_y)})", True, black)
                        screen.blit(ema_coords_text, (10, 210))
                        
                        lp_coords_text = font.render(f"Lp: ({int(lp_x)}, {int(lp_y)})", True, magenta)
                        screen.blit(lp_coords_text, (10, 250))
                        
                        blp_coords_text = font.render(f"Blp: ({int(blp_x)}, {int(blp_y)})", True, orange)
                        screen.blit(blp_coords_text, (10, 290))
                        
                        sg_coords_text = font.render(f"Sg_lp: ({int(sg_x[-1])}, {int(sg_y[-1])})", True, gray)
                        screen.blit(sg_coords_text, (10, 330))
                        
                        ema_sg_coords_text = font.render(f"Ema_Sg_lp: ({int(ema_sg_x)}, {int(ema_sg_y)})", True, purple)
                        screen.blit(ema_sg_coords_text, (10, 370))
                        
                        kalman_ema_sg_coords_text = font.render(f"Kalman_Ema_Sg_lp: ({int(kalman_ema_sg_x)}, {int(kalman_ema_sg_y)})", True, brown)
                        screen.blit(kalman_ema_sg_coords_text, (10, 410))
                        
                        ekf_coords_text = font.render(f"Ekf: ({int(ekf_x)}, {int(ekf_x)})", True, dark_green)
                        screen.blit(ekf_coords_text, (10, 450))

                        # Append data to DataFrame
                        df = df.append({
                            'Time': time,
                            'Raw X': x,
                            'Raw Y': y,
                            'Avg X (10)': avg_x_10,
                            'Avg Y (10)': avg_y_10,
                            'Avg X (15)': avg_x_15,
                            'Avg Y (15)': avg_y_15,
                            'Kalman X (10)': kalman_x_10,
                            'Kalman Y (10)': kalman_y_10,
                            'Kalman X (15)': kalman_x_15,
                            'Kalman Y (15)': kalman_y_15,
                            'EMA X': ema_x,
                            'EMA Y': ema_y,
                            'Low Pass X': lp_x,
                            'Low Pass Y': lp_y,
                            'Butterworth Low Pass X': blp_x,
                            'Butterworth Low Pass Y': blp_y,
                            'Savitzky-Golay_Low Pass X': sg_x[-1],
                            'Savitzky-Golay_Low Pass Y': sg_y[-1],
                            'EMA Savitzky-Golay_Low Pass X': ema_sg_x,
                            'EMA Savitzky-Golay_Low Pass Y': ema_sg_y,
                            'Kalman EMA Savitzky-Golay_Low Pass X': kalman_ema_sg_x,
                            'Kalman EMA Savitzky-Golay_Low Pass Y': kalman_ema_sg_y,
                            'EKF X': ekf_x,
                            'EKF Y': ekf_y
                            
                        }, ignore_index=True)

        pygame.display.update()

    pygame.quit()
    
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Save DataFrame to CSV
    df.to_csv(f'coordinates_data_{timestamp}.csv', index=False)
    print(f"Data saved to coordinates_data_{timestamp}.csv")

if __name__ == "__main__":
    ble_manager = BLEDeviceManager()

    # Start BLE connection in a separate thread to avoid blocking the main thread
    ble_thread = threading.Thread(target=ble_manager.start_connection(id_rover=3))
    ble_thread.start()

    # Run the Pygame visualization
    run_pygame_visualization(ble_manager)