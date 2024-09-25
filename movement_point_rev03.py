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

def sound_buzzer():
    # Configure the buzzer to sound for a short duration
    Board.setBuzzer(1)  # Activate the buzzer
    time.sleep(0.1)  # Keep the buzzer on for 0.5 seconds
    Board.setBuzzer(0)  # Deactivate the buzzer

def execute_movement(id_rover, file_path):
    df = read_csv_and_loop_by_row(file_path)
    df = calculate_angles(df)
    
    df.rename(columns={'Time [msec]': 'T_sky [msec]'}, inplace=True)
    df['T_sky [msec]'] =  df['T_sky [msec]'] / 1000

    device_manager = BLEDeviceManager()
    device_manager.stop_event = threading.Event()

    connection_thread = threading.Thread(target=device_manager.start_connection, args=(id_rover,))
    connection_thread.start()

    print(f"Executing movement for Rover {id_rover}")
    chassis = mecanum.MecanumChassis()

    previous_angle_c = None
    angle_change_threshold = 5.0  # Define a threshold for angle change (in degrees)
    key_points = []

    for index, row in df.iterrows():
        xr, yr, t_tag = update_coordinates(device_manager, id_rover)
        if xr is not None and yr is not None:
            try:
                xr = float(xr) 
                yr = float(yr) 
                df.at[index, 'xr'] = xr
                df.at[index, 'yr'] = yr
                df.at[index, 'T_tag'] = t_tag
                df.at[index, 'T_rover'] = datetime.datetime.now()

                offset_x = df.at[0, 'xr'] - df.at[0, 'xs']
                offset_y = df.at[0, 'yr'] - df.at[0, 'ys']

                df['xsr'] = df['xs'] + offset_x
                df['ysr'] = df['ys'] + offset_y
                
                df.at[index, 'xsr'] = row['xs'] + offset_x
                df.at[index, 'ysr'] = row['ys'] + offset_y

                if index == 0:
                    df.at[index, 'Angle_c (deg)'] = df.at[index, 'Angle_s (deg)']
                else:
                    if index < len(df) - 1:
                        df.at[index, 'dX'] = df.at[index + 1, 'xsr'] - xr
                        df.at[index, 'dY'] = df.at[index + 1, 'ysr'] - yr
                        df.at[index, 'Angle_c (deg)'] = np.degrees(np.arctan2(df.at[index, 'dY'], df.at[index, 'dX']))

                # Detect key points based on angle change
                current_angle_c = df.at[index, 'Angle_c (deg)']
                if previous_angle_c is not None and abs(current_angle_c - previous_angle_c) > angle_change_threshold:
                    key_points.append({
                        'Index': index,
                        'Angle_c (deg)': current_angle_c,
                        'X': xr,
                        'Y': yr,
                        'xs': row['xs'],
                        'ys': row['ys'],
                        'T_sky [msec]': row['T_sky [msec]'],
                        'T_rover': df.at[index, 'T_rover']
                    })
                    sound_buzzer()  # Sound the buzzer at key points

                previous_angle_c = current_angle_c

            except ValueError:
                print(f"Skipping row {index} due to invalid data: X={xr}, Y={yr}")

            if pd.notna(df.at[index, 'Angle_s (deg)']) and pd.notna(df.at[index, 'Angle_c (deg)']):
                chassis.set_velocity(50, df.at[index, 'Angle_c (deg)'], 0)
            else:
                print(f"Skipping row {index} due to Nan in Angle_s or Angle_c")

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
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    device_manager.save_to_csv(f'device_info_{timestamp}.csv')

    df = calculate_angles_for_xr(df)
    
    df['T_diff_rover [msec]'] = df['T_rover'].diff().dt.total_seconds() * 1000
    df['T_diff_rover [msec]'].fillna(0, inplace=True)
        
    df['T_rover'] = pd.to_datetime(df['T_rover'], format='%Y%m%d%H%M%S.%f').dt.strftime('%Y%m%d%H%M%S.%f').str[:-3]

    df_main = df[['T_sky [msec]', 'T_tag', 'T_rover', 'T_diff_rover [msec]', 'xs', 'xr', 'ys', 'yr', 'xsr', 'ysr', 'Red', 'Green', 'Blue', 'dXs', 'dYs', 'dXr', 'dYr', 'dX', 'dY', 'dTime', 'Angle_s (deg)', 'Angle_r (deg)', 'Angle_c (deg)', 'Distance_s (m)', 'Distance_r (m)']]    
    df_main.to_csv(f'movement_{timestamp}.csv', index=False)
    print(f"Saved updated DataFrame to movement_{timestamp}.csv")

    key_points_df = pd.DataFrame(key_points)
    if not key_points_df.empty:
        key_points_df.to_csv(f'key_points_{timestamp}.csv', index=False)
        print(f"Saved key points to key_points_{timestamp}.csv")
        
    print(f"Movement completed for Rover {id_rover}")

def start_movement(id_rover):
    file_path = "Drone 3.csv"
    execute_movement(id_rover, file_path)

if __name__ == "__main__":
    start_movement(2)
