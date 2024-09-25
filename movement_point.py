import pandas as pd
import numpy as np
import threading
import time
import datetime
from HiwonderSDK import mecanum, Board
from ble_manager_rev03 import BLEDeviceManager

def read_csv_and_loop_by_row(file_path):
    df = pd.read_csv(file_path)
    df.rename(columns={'x [m]': 'xs', 'y [m]': 'ys'}, inplace=True)
    return df

def calculate_angles(df):
    df['dXs'] = df['xs'].diff()
    df['dYs'] = df['ys'].diff()
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
                except ValueError:
                    print(f"Error converting rover data for Rover {id_rover}")
                    return None, None, None

                if np.isnan(xr) or np.isnan(yr):
                    print(f"Invalid coordinates received: X={xr}, Y={yr}")
                    return None, None, None
                
                return xr, yr, t_tag
        time.sleep(1)
    return None, None, None

def extract_target_points(df, indices):
    # Ensure the indices are within the DataFrame range
    target_points = []
    for idx in indices:
        if idx < len(df):
            target_x = df.loc[idx, 'xs']
            target_y = df.loc[idx, 'ys']
            target_points.append((target_x, target_y))
        else:
            raise IndexError(f"Index {idx} is out of bounds for the DataFrame.")
    return target_points

def execute_movement(id_rover, file_path, target_indices):
    df = read_csv_and_loop_by_row(file_path)
    print("CSV read and processed.")

    df = calculate_angles(df)
    print("Angles calculated.")

    device_manager = BLEDeviceManager()
    device_manager.stop_event = threading.Event()

    connection_thread = threading.Thread(target=device_manager.start_connection, args=(id_rover,))
    connection_thread.start()

    print(f"Executing movement for Rover {id_rover}")
    chassis = mecanum.MecanumChassis()

    # Extract target points based on specified indices
    target_points = extract_target_points(df, target_indices)

    for target_x, target_y in target_points:
        while True:
            xr, yr, timestamp = update_coordinates(device_manager, id_rover)
            if xr is not None and yr is not None:
                # Calculate distance to target point
                distance = np.sqrt((target_x - xr / 1000)**2 + (target_y - yr / 1000)**2)
                if distance < 0.1:  # Threshold distance to consider as reached
                    break

                # Calculate the angle to the target point
                angle_to_target = np.degrees(np.arctan2(target_y - yr / 1000, target_x - xr / 1000))
                
                # Move rover towards the target point
                chassis.set_velocity(50, angle_to_target, 0)
                Board.RGB.setPixelColor(0, Board.PixelColor(255, 0, 0))
                Board.RGB.setPixelColor(1, Board.PixelColor(255, 0, 0))
                Board.RGB.show()
                time.sleep(0.25)

    Board.RGB.setPixelColor(0, Board.PixelColor(0, 0, 0))
    Board.RGB.setPixelColor(1, Board.PixelColor(0, 0, 0))
    Board.RGB.show()

    chassis.set_velocity(0, 0, 0)
    
    device_manager.stop_event.set()
    device_manager.stop_connection()
    device_manager.save_to_csv('device_info.csv')
    
    df = calculate_angles_for_xr(df)

    # Calculate time differences in seconds
    df['Time_Diff [sec]'] = df['BLE_Time [msec]'].diff().dt.total_seconds() * 1000
    df['Time_Diff [sec]'].fillna(0, inplace=True)
    df['BLE_Time [msec]'] = pd.to_datetime(df['BLE_Time [msec]'], format='%Y%m%d%H%M%S.%f').dt.strftime('%Y%m%d%H%M%S.%f').str[:-3]

    # Save the main DataFrame
    df_main = df[['Time [msec]', 'xs', 'xr', 'ys', 'yr', 'BLE_Time [msec]', 'Time_Diff [sec]', 'Red', 'Green', 'Blue', 'dXs', 'dYs', 'dXr', 'dYr', 'dX', 'dY', 'dTime', 'Angle_s (deg)', 'Angle_r (deg)', 'Distance_s (m)', 'Distance_r (m)']]
    df_main.to_csv('updated_movement.csv', index=False)
    print(f"Saved updated DataFrame to 'updated_movement.csv'")

    # Create and save the additional DataFrame
    df_ble = df[['BLE_Time [msec]', 'xr', 'yr', 'Angle_r (deg)', 'Distance_r (m)']]
    df_ble.to_csv('ble_data.csv', index=False)
    print(f"Saved additional DataFrame to 'ble_data.csv'")

def start_movement(id_rover):
    file_path = "Drone 3.csv"
    target_indices = [12, 23, 33]  # Specify the indices of the target points
    execute_movement(id_rover, file_path, target_indices)

if __name__ == "__main__":
    start_movement(2)
