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

def execute_movement(id_rover, file_path, keypoint_indices):
    df = read_csv_and_loop_by_row(file_path)
    df = calculate_angles(df)
    
    # Extract key points based on specified indices
    key_points = [(df.at[idx, 'xs'], df.at[idx, 'ys']) for idx in keypoint_indices]

    device_manager = BLEDeviceManager()
    device_manager.stop_event = threading.Event()

    connection_thread = threading.Thread(target=device_manager.start_connection, args=(id_rover,))
    connection_thread.start()

    print(f"Executing movement for Rover {id_rover}")
    chassis = mecanum.MecanumChassis()

    for index, (xs, ys) in enumerate(key_points):
        xr, yr, t_tag = update_coordinates(device_manager, id_rover)
        if xr is not None and yr is not None:
            try:
                xr = float(xr) 
                yr = float(yr) 
                df.at[keypoint_indices[index], 'xr'] = xr
                df.at[keypoint_indices[index], 'yr'] = yr
                df.at[keypoint_indices[index], 'T_tag'] = t_tag
                df.at[keypoint_indices[index], 'T_rover'] = datetime.datetime.now()

                # Set LED color based on CSV data
                row = df.loc[keypoint_indices[index]]
                Board.RGB.setPixelColor(0, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
                Board.RGB.setPixelColor(1, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
                Board.RGB.show()

                if index == 0:
                    df.at[keypoint_indices[index], 'Angle_c (deg)'] = df.at[keypoint_indices[index], 'Angle_s (deg)']
                else:
                    dX = xs - xr
                    dY = ys - yr
                    angle_c = np.degrees(np.arctan2(dY, dX))
                    distance = np.sqrt(dX**2 + dY**2)

                    df.at[keypoint_indices[index], 'dX'] = dX
                    df.at[keypoint_indices[index], 'dY'] = dY
                    df.at[keypoint_indices[index], 'Angle_c (deg)'] = angle_c
                    df.at[keypoint_indices[index], 'Distance_s (m)'] = distance

                    while distance > 0.05:  # Continue moving until within 5cm of the target
                        chassis.set_velocity(50, angle_c, 0)
                        time.sleep(0.25)
                        xr, yr, _ = update_coordinates(device_manager, id_rover)
                        dX = xs - xr
                        dY = ys - yr
                        distance = np.sqrt(dX**2 + dY**2)
                        print(f"Moving to point {index+1}: Distance to target: {distance:.2f} meters")

                    chassis.set_velocity(0, 0, 0)
                    print(f"Reached point {index+1}")

            except ValueError:
                print(f"Skipping point {index} due to invalid data: X={xr}, Y={yr}")

    # Turn off the LEDs and stop the chassis after the loop
    Board.RGB.setPixelColor(0, Board.PixelColor(0, 0, 0))
    Board.RGB.setPixelColor(1, Board.PixelColor(0, 0, 0))
    Board.RGB.show()

    chassis.set_velocity(0, 0, 0)

    device_manager.stop_event.set()
    device_manager.stop_connection()
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    device_manager.save_to_csv(f'device_info_{timestamp}.csv')
        
    df.to_csv(f'movement_{timestamp}.csv', index=False)
    print(f"Saved updated DataFrame to movement_{timestamp}.csv")

def start_movement(id_rover):
    file_path = "Drone 2.csv"
    keypoint_indices = [14, 25, 35]  # Specify the indices of the key points here
    execute_movement(id_rover, file_path, keypoint_indices)

if __name__ == "__main__":
    start_movement(2)
