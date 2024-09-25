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

def get_coordinates():
    ble_manager = BLEDeviceManager()
    connected, device_info = ble_manager.is_connected()
    #while not device_manager.stop_event.is_set():
    if connected:
        #if device_manager.is_connected():
        device_info = device_manager.get_device_info()
            
            # Debugging: print device_info to understand its structure
        print("Device Info received from BLE:")
        print(device_info)
            
            # Assuming device_info is a DataFrame or similar structure
        rover_data = device_info.loc[device_info['Name'].str.strip() == f'Rov{id_rover}']
            
        if not rover_data.empty:
            
            current_time = datetime.datetime.now()

            try:
                xr = pd.to_numeric(rover_data.iloc[0]['X'], errors='coerce')
                yr = pd.to_numeric(rover_data.iloc[0]['Y'], errors='coerce')
            except ValueError:
                print(f"Error converting rover data for Rover {id_rover}")
                return None, None, None

            if np.isnan(xr) or np.isnan(yr):
                print(f"Invalid coordinates received: X={xr}, Y={yr}")
                return None, None, None

            return xr, yr, current_time
        
        time.sleep(1)
    
    return None, None, None


def execute_movement(id_rover, file_path):
    df = read_csv_and_loop_by_row(file_path)
    print("CSV read and processed.")

    df = calculate_angles(df)
    print("Angles calculated.")
    
    ble_manager = BLEDeviceManager()
    #device_manager = BLEDeviceManager()
    #device_manager.stop_event = threading.Event()

    # Assume BLEManager is already connected at this point
    print(f"Executing movement for Rover {id_rover}")
    chassis = mecanum.MecanumChassis()

    #xr, yr, timestamp = update_coordinates(device_manager, id_rover)
    #print(f"Initial coordinates: X={xr}, Y={yr}")

    #if xr is not None and yr is not None:
        #df.at[0, 'xr'] = xr / 1000
        #df.at[0, 'yr'] = yr / 1000
        #df.at[0, 'BLE_Time [msec]'] = timestamp
            
    #df['BLE_Time [msec]'] = pd.to_datetime(df['BLE_Time [msec]'], format='%Y%m%d %H%M%S.%f', errors='coerce')

    for index, row in df.iterrows():
        if index > 0:
            xr, yr, timestamp = get_coordinates()
            if xr is not None and yr is not None:
                try:
                    xr = float(xr) / 1000
                    yr = float(yr) / 1000
                    df.at[index, 'xr'] = xr
                    df.at[index, 'yr'] = yr
                    df.at[index, 'BLE_Time [msec]'] = timestamp
                except ValueError:
                    print(f"Skipping row {index} due to invalid data: X={xr}, Y={yr}")

                print(f"Updated BLE_time for row {index}: {timestamp}")

            chassis.set_velocity(50, row['Angle_s (deg)'], 0)
            Board.RGB.setPixelColor(0, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
            Board.RGB.setPixelColor(1, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
            Board.RGB.show()
            time.sleep(0.25)

    Board.RGB.setPixelColor(0, Board.PixelColor(0, 0, 0))
    Board.RGB.setPixelColor(1, Board.PixelColor(0, 0, 0))
    Board.RGB.show()

    chassis.set_velocity(0, 0, 0)
    
    ble_manager.stop_event.set()
    ble_manager.save_to_csv('device_info.csv')
        
    df = calculate_angles_for_xr(df)

    # Calculate time differences in seconds
    df['Time_Diff [sec]'] = df['BLE_Time [msec]'].diff().dt.total_seconds() * 1000
        
    df['Time_Diff [sec]'].fillna(0, inplace=True)
        
    df['BLE_Time [msec]'] = pd.to_datetime(df['BLE_Time [msec]'], format='%Y%m%d %H%M%S.%f').dt.strftime('%Y%m%d %H%M%S.%f').str[:-3]

    # Save the main DataFrame
    df_main = df[['Time [msec]', 'xs', 'xr', 'ys', 'yr', 'BLE_Time [msec]', 'Time_Diff [sec]', 'Red', 'Green', 'Blue', 'dXs', 'dYs', 'dXr', 'dYr', 'dTime', 'Angle_s (deg)', 'Angle_r (deg)', 'Distance_s (m)', 'Distance_r (m)']]
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
