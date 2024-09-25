import pandas as pd
import numpy as np
import threading
import time
from datetime import datetime
import pylops
import signal
from HiwonderSDK import mecanum, Board
import serial

stop_requested = False
# Smoothing operator (Sop)
points = np.zeros((10, 2))

# Pylops 1D smoothing
N = 10
nsmooth = 7
Sop = pylops.Smoothing1D(nsmooth=nsmooth, dims=[N], dtype="float32")
chassis = mecanum.MecanumChassis()

def signal_handler(signum, frame):
    global stop_requested
    stop_requested = True
    print("Stop requested")
    chassis.set_velocity(0,0,0)

def read_csv_and_loop_by_row(file_path):
    df = pd.read_csv(file_path)
    df.rename(columns={'x [m]': 'xs', 'y [m]': 'ys'}, inplace=True)
    return df

def calculate_angles(df):
    df['dXs'] = df['xs'].diff()
    df['dYs'] = df['ys'].diff()
    df['dXs'] = df['dXs'].shift(-1)
    df['dYs'] = df['dYs'].shift(-1)
    df['dTime'] = df['Time [msec]'].diff() / 1000
    df['dTime'] = df['dTime'].shift(-1)
    df['Angle_s (rad)'] = np.arctan2(df['dYs'], df['dXs'])
    df['Angle_s (deg)'] = np.degrees(df['Angle_s (rad)'])
    df['Distance_s (m)'] = np.sqrt(df['dXs']**2 + df['dYs']**2)
    return df

def calculate_angles_for_xr(df):
    df['dXr'] = df['xr'].diff()
    df['dYr'] = df['yr'].diff()
    df['dXr'] = df['dXr'].shift(-1)
    df['dYr'] = df['dYr'].shift(-1)
    df['Angle_r (rad)'] = np.arctan2(df['dYr'], df['dXr'])
    df['Angle_r (deg)'] = np.degrees(df['Angle_r (rad)'])
    df['Distance_r (m)'] = np.sqrt(df['dXr']**2 + df['dYr']**2)
    return df

def update_coordinates_from_serial(ser):
    global points  # Use global points array for smoothing

    while not stop_requested:
        if ser.inWaiting() > 0:
            response = ser.readline().decode('utf-8').strip().split(',')
            #print(f"Received data: {response}")
            try:
                idx_pos = response.index("POS")
                if idx_pos != -1:
                    pos_x = float(response[idx_pos + 1]) * 1000  # Convert to mm
                    pos_y = float(response[idx_pos + 2]) * 1000  # Convert to mm

                    # Update the points array and apply smoothing
                    points = np.roll(points, -1, axis=0)
                    points[-1] = [pos_x, pos_y]

                    # Apply smoothing operator
                    x_smooth = Sop * points[:, 0]
                    y_smooth = Sop * points[:, 1]

                    # Calculate smoothed maximum values
                    xr = int(max(x_smooth))  # Smoothed x-coordinate
                    yr = int(max(y_smooth))  # Smoothed y-coordinate
                    
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S.%f')[:-3]
                    
                    return pos_x, pos_y, x_smooth, y_smooth, xr, yr, timestamp
        
            except (ValueError, IndexError):
                print(f"Error parsing serial data: {response}")
                return None, None, None, None, None
            
    time.sleep(0.1)

def execute_movement(id_rover, file_path, ser):
    df = read_csv_and_loop_by_row(file_path)
    df = calculate_angles(df)
    df.rename(columns={'Time [msec]': 'T_sky [msec]'}, inplace=True)
    df['T_sky [msec]'] = df['T_sky [msec]'] / 1000
    
    df['xs'] = df['xs'] * 1000
    df['ys'] = df['ys'] * 1000

    print(f"Executing movement for Rover {id_rover}")
    chassis = mecanum.MecanumChassis()
    
    offset_x = None
    offset_y = None
    
    data_df = pd.DataFrame(columns=['Time', 'xr_raw', 'yr_raw', 'xr_smooth', 'yr_smooth'])
    
    try:
        
        for index, row in df.iterrows():
            if stop_requested:
                print("Stopping movement as requested")
                break
            
            #print(f"Processing row {index}")
            raw_x, raw_y, x_smooth, y_smooth, xr, yr, time_data = update_coordinates_from_serial(ser)
            #print(f"Raw X: {raw_x}, Raw Y: {raw_y}, Smoothed X: {x_smooth}, Smoothed Y: {y_smooth}, Time: {time}")
            
            #print(f"xr: {xr}, yr: {yr}")
            if raw_x is not None and raw_y is not None and xr is not None and yr is not None:
                try:
                    data_df = data_df.append({
                        'Time': time_data,
                        'xr_raw': raw_x,
                        'yr_raw': raw_y,
                        'xr_smooth': x_smooth,
                        'yr_smooth': y_smooth
                    }, ignore_index=True)
                    
                    df.at[index, 'xr'] = xr
                    df.at[index, 'yr'] = yr
                    df.at[index, 'T_rover'] = datetime.now()
                    
                    if offset_x is None and offset_y is None:
                        # Calculate offsets based on the first row
                        offset_x = df.at[0, 'xr'] - df.at[0, 'xs']
                        offset_y = df.at[0, 'yr'] - df.at[0, 'ys']
                        print("offset_x:", offset_x)
                        print("offset_y:", offset_y)

                    df['xsr'] = df['xs'] + offset_x
                    df['ysr'] = df['ys'] + offset_y
                    
                    # Update xsr and ysr for the current row
                    df.at[index, 'xsr'] = row['xs'] + offset_x
                    df.at[index, 'ysr'] = row['ys'] + offset_y

                    if index == 0:
                        df.at[index, 'Angle_c (deg)'] = df.at[index, 'Angle_s (deg)']
                    else:
                        
                         # Calculate dX, dY, and angle_c if index > 0
                        df.at[index, 'dX'] = df.at[index + 1, 'xsr'] - xr
                        df.at[index, 'dY'] = df.at[index + 1, 'ysr'] - yr
                        #print(f"xsr : {df.at[index + 1, 'xsr']}, ysr : {df.at[index + 1, 'ysr']}")
                        Angle_c = np.degrees(np.arctan2(df.at[index, 'dY'], df.at[index, 'dX']))
                        #print(f"dX: {df.at[index, 'dX']}, dY: {df.at[index, 'dY']}")
                        df.at[index, 'Angle_c (deg)'] = Angle_c
                        #print("Angle_c:", Angle_c)

                except ValueError:
                    print(f"Skipping row {index} due to invalid data: X={xr}, Y={yr}")

                if pd.notna(df.at[index, 'Angle_s (deg)']) and pd.notna(df.at[index, 'Angle_c (deg)']):
                    chassis.set_velocity(0, df.at[index, 'Angle_s (deg)'], 0)
                else:
                    print(f"Skipping row {index} due to NaN in Angle_s or Angle_c")

                # Set LED color based on CSV data
                Board.RGB.setPixelColor(0, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
                Board.RGB.setPixelColor(1, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
                Board.RGB.show()

                time.sleep(0.25)
                
            if stop_requested:
                print("Stopping movement as requested")
                break

    except Exception as e:
        print(f"Error during movement execution {e}")
        
    finally:
         # Turn off the LEDs and stop the chassis after the loop
        Board.RGB.setPixelColor(0, Board.PixelColor(0, 0, 0))
        Board.RGB.setPixelColor(1, Board.PixelColor(0, 0, 0))
        Board.RGB.show()

        chassis.set_velocity(0, 0, 0)

        try:
            df = calculate_angles_for_xr(df)
            df['T_diff_rover [msec]'] = df['T_rover'].diff().dt.total_seconds() * 1000
            df['T_diff_rover [msec]'].fillna(0, inplace=True)
            df['T_rover'] = pd.to_datetime(df['T_rover'], format='%Y%m%d%H%M%S.%f').dt.strftime('%Y%m%d%H%M%S.%f').str[:-3]
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            df_main = df[['T_sky [msec]', 'T_rover', 'T_diff_rover [msec]', 'xs', 'xr', 'ys', 'yr', 'xsr', 'ysr', 'Red', 'Green', 'Blue', 'dXs', 'dYs', 'dXr', 'dYr', 'dX', 'dY', 'dTime', 'Angle_s (deg)', 'Angle_r (deg)', 'Angle_c (deg)', 'Distance_s (m)', 'Distance_r (m)']]
            df_main.to_csv(f'movement_{timestamp}.csv', index=False)
            print(f"Saved updated DataFrame to movement_{timestamp}.csv")
            
            data_df.to_csv(f'data_{timestamp}.csv', index=False)
            print(f"Saved data to data_{timestamp}.csv")
            
        except Exception as e:
            print(f"Error saving CSV: {e}")
        
def start_movement(id_rover):
    global stop_requested
    file_path = "Drone 2.csv"
    serial_port = "/dev/ttyACM0"
    baud_rate = 115200
    df = read_csv_and_loop_by_row(file_path)
    
    #signal.signal(signal.SIGINT, signal_handler)
    #signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        ser = serial.Serial(serial_port, baud_rate, timeout=1)
        print(f"Connected to {serial_port} at baud rate {baud_rate}")
        time.sleep(2)  # Wait for the serial connection to stabilize
            
        execute_movement(id_rover, file_path, ser)
    except KeyboardInterrupt:
        print("Keyboard intterupt.")
    
    except Exception as e:
        print(f"Error connecting to serial port: {e}")
        
    finally:
        if ser:
            print("Close serial connection")
            ser.close()
        chassis.set_velocity(0, 0, 0)
        
if __name__ == "__main__":
    start_movement(2)