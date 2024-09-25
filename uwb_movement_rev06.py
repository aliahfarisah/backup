import threading
import time
import pylops
import signal
import serial
import math
from pid_controller import PID
import pandas as pd
import numpy as np

from datetime import datetime
from uwb_usb import UwbUsbReader
from HiwonderSDK import mecanum, Board
############################################
#Global var
pos_x, pos_y, pos_z, timestamp = 0, 0, 0, 0
timestamp_list, pos_x_list, pos_y_list, pos_z_list = [], [], [], []
uwb_is_connected = False

############################################
stop_requested = False
# Smoothing operator (Sop)
points = np.zeros((10, 2))

# Pylops 1D smoothing
N = 10
nsmooth = 7
Sop = pylops.Smoothing1D(nsmooth=nsmooth, dims=[N], dtype="float32")
chassis = mecanum.MecanumChassis()

data_ready_event = threading.Event()
##########################################################################
def get_current_timestamp():
    # Get the current time
    now = datetime.now()

    # Format hours, minutes, and seconds
    time_str = now.strftime("%H%M%S")

    # Get milliseconds (fraction of a second)
    milliseconds = int(time.time() * 1000) % 1000

    # Format milliseconds as three digits
    milliseconds_str = f"{milliseconds:03}"

    # Combine the time string with milliseconds
    timestamp = f"{time_str}.{milliseconds_str}"
    return timestamp
##########################################################################
def read_uwb():
    global pos_x, pos_y, pos_z, timestamp_list, pos_x_list, pos_y_list, pos_z_list, timestamp, uwb_is_connected
    serial_port = "/dev/ttyACM0"
    baud_rate = 115200
    
    print("Thread UWB starting...")
    reader = UwbUsbReader(serial_port)
    # Wait a moment for the connection to be established
    time.sleep(2)
    print(f"Connected to {serial_port} at baud rate {baud_rate}")
    
    Board.setBuzzer(1)
    time.sleep(0.2)
    Board.setBuzzer(0)
    Board.RGB.setPixelColor(1, Board.PixelColor(0, 255, 0))
    Board.RGB.show()
        
    #print(reader.serial_connection.is_open)
    #Activates shell mode
    reader.activate_shell_mode()
    time.sleep(1)
    
    uwb_is_connected = True
    
    while True:
        data = reader.read_data()
        # Get timestamp
        timestamp = get_current_timestamp()

        if data == "dwm>":
            reader.request_lec()
        elif data is None:
            continue

        #print("data:", data)
        data_split = data.split(",")
        if data_split[0] == "DIST":
            #print("Data:", data_split)
            # Check if 'POS' exists in the data list
            if 'POS' in data_split:
                # Find the index of 'POS'
                pos_index = data_split.index('POS')
                #print("Index:", pos_index)
                
                # Extract position data: X, Y, Z, and quality
                pos_x = float(data_split[pos_index + 1])
                pos_y = float(data_split[pos_index + 2])
                pos_z = float(data_split[pos_index + 3])
            else:
                pass
        
        #print(f"Timestamp: {timestamp}, X: {pos_x} meters, Y: {pos_y} meters, Z: {pos_z} meters")
        # Append the data to respective lists
        timestamp_list.append(timestamp)
        pos_x_list.append(pos_x)
        pos_y_list.append(pos_y)
        pos_z_list.append(pos_z)
            
##########################################################################
def signal_handler(signum, frame):
    global stop_requested
    stop_requested = True
    print("Stop requested")
    chassis.set_velocity(0,0,0)
##########################################################################
def read_csv_and_loop_by_row(file_path):
    df = pd.read_csv(file_path)
    df.rename(columns={'x [m]': 'xs', 'y [m]': 'ys', 'z [m]': 'zs'}, inplace=True)
    #df = calculate_angles(df)
    
    return df
##########################################################################
def angle_between_points(p1, p2):
    # Delta
    delta_x = p2[0] - p1[0]
    delta_y = p2[1] - p1[1]
    #print(delta_x)
    #print(delta_y)
    
    # Calculate the angle in radians
    angle_rad = math.atan2(delta_y, delta_x)
    
    #Convert to degrees
    angle_deg = math.degrees(angle_rad)
    #print(angle_deg)
    
    return angle_deg
##########################################################################
def execute_movement(theta_xy, R, G, B, speed):                   
    #Move rover
    chassis.set_velocity(speed, theta_xy, 0)
    # Set LED color based on CSV data
    Board.RGB.setPixelColor(0, Board.PixelColor(R, G, B))
    Board.RGB.setPixelColor(1, Board.PixelColor(R, G, B))
    Board.RGB.show()
        
##########################################################################
def calculate_distance(p1, p2):
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

##########################################################################
def start_movement(id_rover):
    global stop_requested, pos_x, pos_y, pos_z, timestamp_list, pos_x_list, pos_y_list, pos_z_list, timestamp
    global uwb_is_connected, df
    file_path = "Drone 2.csv"
    df = read_csv_and_loop_by_row(file_path)
    
    # Initialize the PID controller for steering adjustments
    steering_pid = PID(P=0.2, I=0.05, D=0.1)  # Adjust these values for fine-tuning
    steering_pid.setWindup(10)  # Set the windup guard to avoid integral windup
    distance_pid = PID(P=1.0, I=0.1, D=0.05)  # PID for distance correction
    distance_pid.setWindup(10)
    
    df['timestamp'] = None
    df['xr'] = None
    df['yr'] = None
    df['zr'] = None
    df['xsr'] = None
    df['ysr'] = None
    df['zsr'] = None
    df['theta_xy'] = None
    #print("df:", df)
    # Get the number of rows in the DataFrame
    num_rows = df.shape[0]
       
    #signal.signal(signal.SIGINT, signal_handler)
    #signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        #ser = serial.Serial(serial_port, baud_rate, timeout=1)       
        #reader = read_uwb()
        #uwb_thread = threading.Thread(target=read_uwb)
        #uwb_thread.daemon = True
        #uwb_thread.start()
                
        while True:
            if uwb_is_connected:
                time.sleep(5)
                Board.setBuzzer(1)
                time.sleep(0.3)
                Board.setBuzzer(0)
                time.sleep(0.05)
                Board.setBuzzer(1)
                time.sleep(0.3)
                Board.setBuzzer(0)
                
                time.sleep(1)
#                 if wait_for_input:
#                     # If the client sends the wait_for_input flag, the server waits for the client’s signal.
#                     print(f"Rover {id_rover} is ready and waiting for client input to start.")
#                     return  # Don't proceed until the client sends another signal
# 
#                 # Proceed with the movement logic after receiving the input signal from the client
#                 print(f"Starting movement for Rover {id_rover}.")
                                
                Board.setBuzzer(1)
                time.sleep(0.3)
                Board.setBuzzer(0)
                
                #print(f"Timestamp: {timestamp}, X: {pos_x} meters, Y: {pos_y} meters, Z: {pos_z} meters")
                for index, row in df.iterrows():      
                    df.at[index, 'timestamp'] = timestamp
                    df.at[index, 'xr'] = pos_x
                    df.at[index, 'yr'] = pos_y
                    df.at[index, 'zr'] = pos_z
                    if index != (num_rows - 1):
                        df.at[index, 'xsr'] = df.at[0, 'xr'] + df.at[index + 1, 'xs']
                        df.at[index, 'ysr'] = df.at[0, 'yr'] + df.at[index + 1, 'ys']
                        df.at[index, 'zsr'] = df.at[0, 'zr'] + df.at[index + 1, 'zs']
                        
                        point_1 = (pos_x, pos_y)
                        point_2 = (df.at[index, 'xsr'], df.at[index, 'ysr'])
                        #print(point_1)
                        #print(point_2)
                        theta_xy = angle_between_points(point_1, point_2)
                        df.at[index, 'theta_xy'] = theta_xy
                        
                        # Set the desired angle for the PID controller
                        steering_pid.SetPoint = theta_xy
                        
                        # Update the PID controller with current feedback (actual theta)
                        steering_pid.update(theta_xy)
                        
                        # Get the corrected theta from the PID output
                        corrected_theta = steering_pid.output
                        
                        # Calculate distance error
                        desired_distance = calculate_distance(point_1, point_2)
                        actual_distance = 0
                        distance_pid.SetPoint = desired_distance
                        distance_pid.update(actual_distance)
                        speed_correction = distance_pid.output

                        # Adjust speed based on distance correction
                        adjusted_speed = 50 + speed_correction
                        adjusted_speed = max(0, min(100, adjusted_speed))
                        
                        execute_movement(corrected_theta, row['Red'], row['Green'], row['Blue'], adjusted_speed)
                    
                    print(df)
                    time.sleep(0.25)
                    
                break
    except KeyboardInterrupt:
        print("Keyboard intterupt.")
    
    except Exception as e:
        print(f"Error connecting to serial port: {e}")
        
    finally:
        chassis.set_velocity(0, 0, 0)   
       
        # Create a DataFrame from the lists
        uwb_df = pd.DataFrame({
            'Timestamp': timestamp_list,
            'Pos_X': pos_x_list,
            'Pos_Y': pos_y_list,
            'Pos_Z': pos_z_list
        })
        # Optionally, save the DataFrame to a CSV file
        uwb_df.to_csv(f'data_with_{timestamp}.csv', index=False)
        df.to_csv("movement_record_" + str(timestamp) + ".csv")
        
        # Turn off all lights
        Board.RGB.setPixelColor(0, Board.PixelColor(0, 0, 0))
        Board.RGB.setPixelColor(1, Board.PixelColor(0, 0, 0))
        Board.RGB.show()
        Board.setBuzzer(0)
        print('All lights & buzzers are turned off')
        
##########################################################################
def start_rover(id_rover):
    Board.setBuzzer(1)
    time.sleep(0.2)
    Board.setBuzzer(0)
    Board.RGB.setPixelColor(0, Board.PixelColor(0, 255, 0))
    Board.RGB.show()
    time.sleep(1)
    
    try:
        uwb_thread = threading.Thread(target=read_uwb)
        uwb_thread.daemon = True
        uwb_thread.start()
        
    except KeyboardInterrupt:
        print("Keyboard intterupt.")
    
    except Exception as e:
        print(f"Error connecting to serial port: {e}")
    
    finally:
        start_movement(id_rover)

##########################################################################   

if __name__ == "__main__":
    
    start_rover()
#     Board.setBuzzer(1)
#     time.sleep(0.2)
#     Board.setBuzzer(0)
#     Board.RGB.setPixelColor(0, Board.PixelColor(0, 255, 0))
#     Board.RGB.show()
#     time.sleep(1)
#     
#     try:
#         uwb_thread = threading.Thread(target=read_uwb)
#         uwb_thread.daemon = True
#         uwb_thread.start()
#         
#     except KeyboardInterrupt:
#         print("Keyboard intterupt.")
#     
#     except Exception as e:
#         print(f"Error connecting to serial port: {e}")
#     
#     finally:
#         start_movement(2)