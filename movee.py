import pandas as pd
import numpy as np
import threading
import time
import datetime
from HiwonderSDK import mecanum, Board
from ble_manager import BLEDeviceManager

def read_csv_and_loop_by_row(file_path):
    df = pd.read_csv(file_path)
    df.rename(columns={'x [m]': 'xs', 'y [m]': 'ys'}, inplace=True)
    df['xr'] = np.nan
    df['yr'] = np.nan
    df['BLE_Time [msec]'] = np.nan
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
    last_update_time = None
    while not device_manager.stop_event.is_set():
        if device_manager.is_connected():
            print("Fetching device info...")
            device_info = device_manager.get_device_info()
            rover_data = device_info[device_info['Name'] == f'Rov{id_rover}']
            if not rover_data.empty:
                current_time_msec = int(datetime.datetime.now().timestamp() * 1000)
                if last_update_time is not None:
                    interval = current_time_msec - last_update_time
                    print(f"Interval between BLE updates: {interval} milliseconds")
                last_update_time = current_time_msec
                print(f"Coordinates: X={rover_data.iloc[0]['X']}, Y={rover_data.iloc[0]['Y']}")
                return rover_data.iloc[0]['X'], rover_data.iloc[0]['Y'], current_time_msec
        time.sleep(1)
    return None, None, None

def execute_movement(id_rover, file_path):
    df = read_csv_and_loop_by_row(file_path)
    print("CSV read and processed.")

    df = calculate_angles(df)
    print("Angles calculated.")


    device_manager = BLEDeviceManager()
    device_manager.stop_event = threading.Event()

    scan_thread = threading.Thread(target=device_manager.scan_for_devices, args=(5.0, [f'Rov{id_rover}']))
    scan_thread.start()
    scan_thread.join()

    connection_thread = threading.Thread(target=device_manager.start_connection, args=(id_rover,))
    connection_thread.start()

    print(f"Executing movement for Rover {id_rover}")
    chassis = mecanum.MecanumChassis()

    # Initialize timestamps
    last_update_time = None
    xr, yr, timestamp = update_coordinates(device_manager, id_rover)
    print(f"Initial coordinates: X={xr}, Y={yr}")
    
    if xr is not None and yr is not None:
        df.at[0, 'xr'] = xr / 1000
        df.at[0, 'yr'] = yr / 1000
        df.at[0, 'BLE_Time [msec]'] = 0
        last_update_time = timestamp  # Initialize last_update_time

    for index in range(1, len(df)):
        xr, yr, timestamp = update_coordinates(device_manager, id_rover)
        if xr is not None and yr is not None:
            df.at[index, 'xr'] = xr / 1000
            df.at[index, 'yr'] = yr / 1000
            interval = timestamp - last_update_time
            print(f"Interval for row {index}: {interval} milliseconds")

            df.at[index, 'BLE_Time [msec]'] = df.at[index -1, 'BLE_Time [msec]'] + interval

            print(f"Updated BLE_time for row {index}: {df.at[index -1, 'BLE_Time [msec]']}")
            last_update_time = timestamp  # Update last_update_time

        else:
            print(f"No data received from BLE for Rover {id_rover}. Skipping update for row {index}.")

        row = df.iloc[index]
        chassis.set_velocity(50, row['Angle_s (deg)'], 0)
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

    # Save the main DataFrame
    df_main = df[['Time [msec]', 'xs', 'xr', 'ys', 'yr', 'BLE_Time [msec]', 'Red', 'Green', 'Blue', 'dXs', 'dYs', 'dXr', 'dYr', 'dTime', 'Angle_s (deg)', 'Angle_r (deg)', 'Distance_s (m)', 'Distance_r (m)']]
    df_main.to_csv('updated_movement.csv', index=False)
    print(f"Saved updated DataFrame to 'updated_movement.csv'")

    # Create and save the additional DataFrame
    df_ble = df[['BLE_Time [msec]', 'xr', 'yr', 'Angle_r (deg)', 'Distance_r (m)']]
    df_ble.to_csv('ble_data.csv', index=False)
    print(f"Saved additional DataFrame to 'ble_data.csv'")

def start_movement(id_rover):
    file_path = "Drone 2.csv"
    execute_movement(id_rover, file_path)

if __name__ == "__main__":
    start_movement(2)
