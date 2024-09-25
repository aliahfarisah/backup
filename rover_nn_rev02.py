import os
import time
import numpy as np
import threading
from collections import deque
import pandas as pd
from HiwonderSDK import mecanum, Board
from ble_manager_rev03 import BLEDeviceManager
import onnxruntime as ort
from nn_infer import ONNXModel
from filterpy.kalman import KalmanFilter
from datetime import datetime

class MovingAverage:
    def __init__(self, window_size):
        self.window_size = window_size
        self.data = deque(maxlen=window_size)
    
    def add(self, value):
        self.data.append(value)
        return np.mean(self.data)

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

def update_coordinates(device_manager, id_rover):
    while not device_manager.stop_event.is_set():
        if device_manager.is_connected():
            device_info = device_manager.get_device_info()
            rover_data = device_info[device_info['Name'] == f'Rov{id_rover}']
            if not rover_data.empty:
                try:
                    xr = pd.to_numeric(rover_data.iloc[0]['X'], errors='coerce')
                    yr = pd.to_numeric(rover_data.iloc[0]['Y'], errors='coerce')
                    
                    if pd.isna(xr) or pd.isna(yr):
                        print(f"Invalid coordinates received: X={xr}, Y={yr}")
                        return None, None, None
                    
                    return xr, yr
                except ValueError:
                    print(f"Error converting rover data for Rover {id_rover}")
                    return None, None, None
        time.sleep(1)
    return None, None, None

def execute_movement(id_rover):
    try:
        model_folder = 'nn_models'
        model_path = os.path.join(model_folder, 'Rover_02_01.onnx')
        model = ONNXModel(model_path)

        device_manager = BLEDeviceManager()
        device_manager.stop_event = threading.Event()

        connection_thread = threading.Thread(target=device_manager.start_connection, args=(id_rover,))
        connection_thread.start()

        x_moving_avg = MovingAverage(window_size=10)
        y_moving_avg = MovingAverage(window_size=10)

        avg_x_kf = KalmanFilterWrapper()
        avg_y_kf = KalmanFilterWrapper()

        print(f"Executing movement for Rover {id_rover}")
        chassis = mecanum.MecanumChassis()

        width, height = 1500, 750
        rover_pos = [0, 0]  # Initialize rover position
        target_pos = [1300, 205]  # Target position

        # Scale target and rover positions
        target_x_scale = (target_pos[0] * 90 / width) - 45
        target_y_scale = (target_pos[1] * 90 / height) - 45

        target_position = np.array([target_x_scale, 0.03, target_y_scale]).astype(np.float32)
        transform_vel = np.array([0.0, 0.0]).astype(np.float32)
        boundary_min = np.array([-45, 0.0, -45]).astype(np.float32)
        boundary_max = np.array([45, 0.0, 45]).astype(np.float32)
        
        csv_file = 'rover_data.csv'
        csv_columns = ['timestamp', 'cont_action_x', 'cont_action_y', 'angle',
                       'target_x', 'target_y', 'rover_x', 'rover_y', 'delta_x',
                       'delta_y', 'transform_vel_x', 'transform_vel_y',
                       'boundary_min_x', 'boundary_min_y', 'boundary_min_z',
                       'boundary_max_x', 'boundary_max_y', 'boundary_max_z']
        with open(csv_file, 'w') as file:
            file.write(','.join(csv_columns) + '\n')
            
        x_pos = pd.DataFrame(columns=['x'])
        y_pos = pd.DataFrame(columns=['y'])
        start_time = time.time()

        while not device_manager.stop_event.is_set():
            
            
            xr, yr = update_coordinates(device_manager, id_rover)
            avg_x = x_moving_avg.add(xr)
            avg_y = y_moving_avg.add(yr)

            kalman_avg_x = avg_x_kf.update(avg_x)
            kalman_avg_y = avg_y_kf.update(avg_y)
            #print("kalman x:", kalman_avg_x)
            kalman_avg_x = kalman_avg_x[0]
            kalman_avg_y = kalman_avg_y[0]
            #print("kalman x:", kalman_avg_x)

            x_new_position = pd.DataFrame({'x': [kalman_avg_x]})
            y_new_position = pd.DataFrame({'y': [kalman_avg_y]})
            
            x_pos = pd.concat([x_pos, x_new_position], ignore_index=True)
            y_pos = pd.concat([y_pos, y_new_position], ignore_index=True)

            rover_pos = [kalman_avg_x, kalman_avg_y]
            print("Rover position:", rover_pos)
            
            transform_x_scale = (rover_pos[0] * 90 / width) - 45
            transform_y_scale = (rover_pos[1] * 90 / height) - 45
            transform_position = np.array([transform_x_scale, 0.03, transform_y_scale]).astype(np.float32)
            # Calculate delta_x and delta_y using diff()
            if len(x_pos) > 1:
                delta_x = x_pos['x'].diff().iloc[-1]
                delta_y = y_pos['y'].diff().iloc[-1]
            else:
                delta_x, delta_y = 0, 0

            input_array = np.concatenate((target_position, transform_position, transform_vel, boundary_min, boundary_max))
            print("Input array:", input_array)
            input_array = np.array([input_array])

            
            output = model.infer(input_array)
            

            cont_actions = output[4][0]
            cont_action_x = cont_actions[0]
            cont_action_y = cont_actions[1]
            
                      
            angle = np.degrees(np.arctan2(cont_action_y, cont_action_x))
            
            if rover_pos[0] > (width - 10) or rover_pos[0] < 10 or rover_pos[1] > (height - 10) or rover_pos[1] < 10: # Stop if within 10 cm
                print(f"Rover_pos_x : {rover_pos[0]}, Rover_pos_y : {rover_pos[1]}")
                print("Boundary reached. Stopping rover.")
                chassis.set_velocity(0, 0, 0)
                break
            
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S.%f')[:-3]
            
            with open(csv_file, 'a') as file:
                file.write(f"{timestamp},{cont_action_x},{cont_action_y},{angle},"
                               f"{target_x_scale},{target_y_scale},"
                               f"{transform_x_scale},{transform_y_scale},{delta_x},"
                               f"{delta_y},{transform_vel[0]},{transform_vel[1]},"
                               f"{boundary_min[0]},{boundary_min[1]},{boundary_min[2]},"
                               f"{boundary_max[0]},{boundary_max[1]},{boundary_max[2]}\n")
            
            chassis.set_velocity(50, angle, 0)
            Board.RGB.setPixelColor(0, Board.PixelColor(0, 255, 0))
            Board.RGB.setPixelColor(1, Board.PixelColor(0, 255, 0))
            Board.RGB.show()

            time.sleep(0.25)
            
            end_time = time.time()
            inference_time = end_time - start_time
            print("Inference time:", inference_time)
            print("Delta x:", delta_x)
            print("Delta y:", delta_y)
            transform_vel[0] = abs(delta_x / inference_time)
            transform_vel[1] = abs(delta_y / inference_time)
            print("Vel x:", transform_vel[0])
            print("Vel y:", transform_vel[1])
            
            start_time = end_time

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        device_manager.stop_event.set()
        device_manager.stop_connection()
        connection_thread.join()
        
if __name__ == "__main__":
    execute_movement(3)
