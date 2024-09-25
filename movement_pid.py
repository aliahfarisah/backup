import pandas as pd
import numpy as np
import threading
import time
from HiwonderSDK import mecanum, Board
from ble_manager import BLEDeviceManager

class PIDController:
    def __init__(self, Kp, Ki, Kd):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.setpoint = 0
        self.integral = 0
        self.previous_error = 0

    def compute(self, current_value, dt):
        error = self.setpoint - current_value
        self.integral += error * dt
        derivative = error - self.previous_error / dt if dt > 0 else 0
        self.previous_error = error
        return self.Kp * error + self.Ki * self.integral + self.Kd * derivative

def read_csv_and_loop_by_row(file_path):
    df = pd.read_csv(file_path)
    df.rename(columns={'x [m]': 'xs', 'y [m]': 'ys'}, inplace=True)
    df['xr'] = np.nan
    df['yr'] = np.nan
    df['Angle_c (deg)'] = np.nan  # Add new column for controlled angle
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
    while not device_manager.stop_event.is_set():
        if device_manager.is_connected():
            device_info = device_manager.get_device_info()
            rover_data = device_info[device_info['Name'] == f'Rov{id_rover}']
            if not rover_data.empty:
                return rover_data.iloc[0]['X'], rover_data.iloc[0]['Y']
        time.sleep(1)
    return None, None

def execute_movement(id_rover, file_path):
    df = read_csv_and_loop_by_row(file_path)
    df = calculate_angles(df)

    device_manager = BLEDeviceManager()
    device_manager.stop_event = threading.Event()

    scan_thread = threading.Thread(target=device_manager.scan_for_devices, args=(5.0, [f'Rov{id_rover}']))
    scan_thread.start()
    scan_thread.join()

    connection_thread = threading.Thread(target=device_manager.start_connection, args=(id_rover,))
    connection_thread.start()

    print(f"Executing movement for Rover {id_rover}")
    chassis = mecanum.MecanumChassis()

    xr, yr = None, None
    #xr, yr = update_coordinates(device_manager, id_rover)
    while xr is None and yr is None:
        xr, yr = update_coordinates(device_manager, id_rover)

    df.at[0, 'xr'] = xr/1000
    df.at[0, 'yr'] = yr/1000

    pid_angle = PIDController(Kp=1.0, Ki=0.1, Kd=0.05)  # Adjust Kp, Ki, Kd as needed
    
    start_time = time.time()


    for index, row in df.iterrows():
        if index > 0:
            xr, yr = update_coordinates(device_manager, id_rover)
            if xr is not None and yr is not None:
                df.at[index, 'xr'] = xr/1000
                df.at[index, 'yr'] = yr/1000
                
                # Calculate angles for xr and yr dynamically
                df.at[index, 'dXr'] = df.at[index, 'xr'] - df.at[index - 1, 'xr']
                df.at[index, 'dYr'] = df.at[index, 'yr'] - df.at[index - 1, 'yr']
                df.at[index, 'Angle_r (rad)'] = np.arctan2(df.at[index, 'dYr'], df.at[index, 'dXr'])
                df.at[index, 'Angle_r (deg)'] = np.degrees(df.at[index, 'Angle_r (rad)'])
                df.at[index, 'Distance_r (m)'] = np.sqrt(df.at[index, 'dXr']**2 + df.at[index, 'dYr']**2)
            else:
                print(f"No data received from BLE for Rover {id_rover}. Skipping update for this row.")

            # Compute PID control for angle
            dt = time.time() - start_time
            start_time = time.time()

            # Set the setpoint as the next angle_s
            pid_angle.setpoint = df.at[index, 'Angle_s (deg)']
            current_angle = df.at[index - 1, 'Angle_r (deg)'] if index > 0 else 0
            
            if pd.notna(current_angle) and pd.notna(pid_angle.setpoint):
                control_signal = pid_angle.compute(current_angle, dt)  # This is the control signal
                df.at[index, 'Control_signal'] = control_signal
                adjusted_angle = control_signal + current_angle  # Calculate the adjusted angle
                df.at[index, 'Angle_c (deg)'] = adjusted_angle  # Save PID-adjusted angle
                
                print(f"Row {index}: Setpoint={pid_angle.setpoint}, Current Angle={current_angle}, Control Signal={control_signal}, Adjusted Angle={adjusted_angle}")
            
                # Set the velocity with PID control signal
                chassis.set_velocity(50, adjusted_angle, 0)
                Board.RGB.setPixelColor(0, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
                Board.RGB.setPixelColor(1, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
                Board.RGB.show()
            time.sleep(0.25)

    Board.RGB.setPixelColor(0, Board.PixelColor(0, 0, 0))
    Board.RGB.setPixelColor(1, Board.PixelColor(0, 0, 0))
    Board.RGB.show()

    chassis.set_velocity(0, 0, 0)  

    device_manager.stop_event.set()
    connection_thread.join()
    
    df = calculate_angles_for_xr(df)
    
    df = df[['Time [msec]', 'xs', 'xr', 'ys', 'yr', 'Red', 'Green', 'Blue', 'dXs', 'dYs', 'dTime', 'dXr', 'dYr', 'Angle_s (deg)', 'Angle_r (deg)', 'Angle_c (deg)', 'Distance_s (m)', 'Distance_r (m)']]
    df.to_csv('updated_movement4.csv', index=False)
    print(f"Saved updated DataFrame to 'updated_movement4.csv'")

def start_movement(id_rover):
    file_path = "Drone 4.csv"
    execute_movement(id_rover, file_path)

if __name__ == "__main__":
    start_movement(4)

