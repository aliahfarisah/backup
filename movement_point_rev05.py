import pandas as pd
import numpy as np
import time
import datetime
from HiwonderSDK import mecanum, Board
import threading
from ble_manager_rev03 import BLEDeviceManager
from scipy.signal import savgol_filter
from filterpy.kalman import KalmanFilter

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

class SavitzkyGolayFilter:
    def __init__(self, window_size, poly_order):
        self.window_size = window_size
        self.poly_order = poly_order

    def update(self, data):
        if len(data) < self.window_size:
            # Not enough data points to apply the filter
            return data
        return savgol_filter(data, self.window_size, self.poly_order)

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

def read_csv_and_loop_by_row(file_path):
    df = pd.read_csv(file_path)
    df.rename(columns={'x [m]': 'xs', 'y [m]': 'ys'}, inplace=True)
    return df

def calculate_angles(df):
    df['dXs'] = df['xs'].diff()
    df['dYs'] = df['ys'].diff()
    df['dTime'] = df['Time [msec]'].diff() / 1000
    df['Angle_s (rad)'] = np.arctan2(df['dYs'], df['dXs'])
    df['Angle_s (deg)'] = np.degrees(df['Angle_s (rad)'])
    df['Distance_s (m)'] = np.sqrt(df['dXs']**2 + df['dYs']**2)
    return df

def calculate_angles_for_xr(df):
    df['dXr'] = df['xr'].diff()
    df['dYr'] = df['yr'].diff()
    df['Angle_r (rad)'] = np.arctan2(df['dYr'], df['dXr'])
    df['Angle_r (deg)'] = np.degrees(df['Angle_r (rad)'])
    df['Distance_r (m)'] = np.sqrt(df['dXr']**2 + df['dYr']**2)
    return df

def update_coordinates(device_manager, id_rover):
    previous_t_tag = None
    
    while not device_manager.stop_event.is_set():
        if device_manager.is_connected():
            device_info = device_manager.get_device_info()
            rover_data = device_info[device_info['Name'] == f'Rov{id_rover}']
            if not rover_data.empty:
                try:
                    xr = pd.to_numeric(rover_data.iloc[0]['X'], errors='coerce')
                    yr = pd.to_numeric(rover_data.iloc[0]['Y'], errors='coerce')
                    t_tag = rover_data.iloc[0]['T_tag']
                    
                    #if previous_t_tag is not None:
                        #prev_time = datetime.datetime.strptime(previous_t_tag, '%Y%m%d%H%M%S.%f')
                        #current_time = datetime.datetime.strptime(t_tag, '%Y%m%d%H%M%S.%f')
                        #T_diff_tag = (current_time - prev_time).total_seconds() * 1000
                    #else:
                        #T_diff_tag = None
                        #previous_t_tag = t_tag
                    
                except ValueError:
                    print(f"Error converting rover data for Rover {id_rover}")
                    return None, None, None

                if np.isnan(xr) or np.isnan(yr):
                    print(f"Invalid coordinates received: X={xr}, Y={yr}")
                    return None, None, None
                
                return xr, yr, t_tag
        time.sleep(1)
    return None, None, None

def execute_movement(id_rover, file_path):
    df = read_csv_and_loop_by_row(file_path)
    print("CSV read and processed.")

    df = calculate_angles(df)
    print("Angles calculated.")
    
    df.rename(columns={'Time [msec]': 'T_sky [msec]'}, inplace=True)
    df['T_sky [msec]'] =  df['T_sky [msec]'] / 1000

    device_manager = BLEDeviceManager()
    device_manager.stop_event = threading.Event()

    connection_thread = threading.Thread(target=device_manager.start_connection, args=(id_rover,))
    connection_thread.start()

    print(f"Executing movement for Rover {id_rover}")
    chassis = mecanum.MecanumChassis()
    
    # Initialize filters
    alpha = 0.1  # You can adjust this value as needed
    x_kf = KalmanFilterWrapper()
    y_kf = KalmanFilterWrapper()
    x_ema = ExponentialMovingAverage(alpha)
    y_ema = ExponentialMovingAverage(alpha)
    x_lp = LowPassFilter(alpha)
    y_lp = LowPassFilter(alpha)
    sg_filter = SavitzkyGolayFilter(window_size=11, poly_order=2)
    x_data_buffer = []
    y_data_buffer = []


    for index, row in df.iterrows():
        xr, yr, t_tag = update_coordinates(device_manager, id_rover)
        if xr is not None and yr is not None:
            try:
                # Apply filtering
                lp_x = x_lp.update(float(xr))
                lp_y = y_lp.update(float(yr))

                # Buffer the data
                x_data_buffer.append(lp_x)
                y_data_buffer.append(lp_y)

                # Apply Savitzky-Golay Filter if enough data points
                if len(x_data_buffer) > sg_filter.window_size:
                    sg_x = sg_filter.update(x_data_buffer)
                    sg_y = sg_filter.update(y_data_buffer)
                    ema_sg_x = x_ema.update(sg_x[-1])
                    ema_sg_y = y_ema.update(sg_y[-1])

                    # Apply Kalman filter
                    kalman_ema_sg_x = x_kf.update(ema_sg_x)
                    kalman_ema_sg_y = y_kf.update(ema_sg_y)

                    xr = kalman_ema_sg_x
                    yr = kalman_ema_sg_y
                else:
                    # If not enough data points, just use the low-pass filter output
                    xr = lp_x
                    yr = lp_y
                    
                df.at[index, 'xr'] = xr
                df.at[index, 'yr'] = yr
                df.at[index, 'T_tag'] = t_tag
                df.at[index, 'T_rover'] = datetime.datetime.now()

            except ValueError:
                print(f"Skipping row {index} due to invalid data: X={xr}, Y={yr}")

            if pd.notna(row['Angle_s (deg)']):
                chassis.set_velocity(50, row['Angle_s (deg)'], 0)
            else:
                print(f"Skipping row {index} due to NaN in Angle_s")
        
            Board.RGB.setPixelColor(0, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
            Board.RGB.setPixelColor(1, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
            Board.RGB.show()
            time.sleep(0.25)

        Board.RGB.setPixelColor(0, Board.PixelColor(0, 0, 0))
        Board.RGB.setPixelColor(1, Board.PixelColor(0, 0, 0))
        Board.RGB.show()

        chassis.set_velocity(0, 0, 0)
    
        device_manager.stop_event.set()
        device_manager.stop_connection()
        device_manager.save_to_csv('device_info.csv')
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

        df = calculate_angles_for_xr(df)
        df['T_diff_rover [msec]'] = df['T_rover'].diff().dt.total_seconds() * 1000
        df['T_diff_rover [msec]'].fillna(0, inplace=True)
            
        df['T_rover'] = pd.to_datetime(df['T_rover'], format='%Y%m%d%H%M%S.%f').dt.strftime('%Y%m%d%H%M%S.%f').str[:-3]

        df_main = df[['T_sky [msec]', 'T_tag', 'T_rover', 'T_diff_rover [msec]', 'xs', 'xr', 'ys', 'yr', 'Red', 'Green', 'Blue', 'dXs', 'dYs', 'dXr', 'dYr', 'Angle_s (deg)', 'Angle_r (deg)', 'Distance_s (m)', 'Distance_r (m)']]    
        df_main.to_csv(f'movement_{timestamp}.csv', index=False)
        print(f"Saved updated DataFrame to movement_{timestamp}.csv")


def start_movement(id_rover):
    file_path = "Drone 2.csv"
    execute_movement(id_rover, file_path)

if __name__ == "__main__":
    id_rover = 2  # You can change this as needed
    start_movement(id_rover)
