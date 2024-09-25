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
                    t_tag = rover_data.iloc[0]['T_tag']
                    
                    if pd.isna(xr) or pd.isna(yr):
                        print(f"Invalid coordinates received: X={xr}, Y={yr}")
                        return None, None, None
                    
                    return xr, yr, t_tag
                except ValueError:
                    print(f"Error converting rover data for Rover {id_rover}")
                    return None, None, None
        time.sleep(1)
    return None, None, None

def calculate_distance(x1, y1, x2, y2):
    return np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

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
        transform_x_scale = (rover_pos[0] * 90 / width) - 45
        transform_y_scale = (rover_pos[1] * 90 / height) - 45

        target_position = np.array([target_x_scale, 0.03, target_y_scale]).astype(np.float32)
        transform_position = np.array([transform_x_scale, 0.03, transform_y_scale]).astype(np.float32)
        transform_vel = np.array([0.0, 0.0]).astype(np.float32)
        boundary_min = np.array([-45, 0.0, -45]).astype(np.float32)
        boundary_max = np.array([45, 0.0, 45]).astype(np.float32)
        
        csv_file = 'rover_data.csv'
        csv_columns = ['timestamp', 'cont_action_x', 'cont_action_y', 'angle',
                       'target_x', 'target_y', 'rover_x', 'rover_y',
                       'transform_vel_x', 'transform_vel_y',
                       'boundary_min_x', 'boundary_min_y', 'boundary_min_z',
                       'boundary_max_x', 'boundary_max_y', 'boundary_max_z']
        with open(csv_file, 'w') as file:
            file.write(','.join(csv_columns) + '\n')

        while not device_manager.stop_event.is_set():
            xr, yr, t_tag = update_coordinates(device_manager, id_rover)
            avg_x = x_moving_avg.add(xr)
            avg_y = y_moving_avg.add(yr)

            kalman_avg_x = avg_x_kf.update(avg_x)
            kalman_avg_y = avg_y_kf.update(avg_y)

            rover_pos = [kalman_avg_x, kalman_avg_y]
            transform_x_scale = (rover_pos[0] * 90 / width) - 45
            transform_y_scale = (rover_pos[1] * 90 / height) - 45
            transform_position = np.array([transform_x_scale, 0.03, transform_y_scale]).astype(np.float32) 

            input_array = np.concatenate((target_position, transform_position, transform_vel, boundary_min, boundary_max))
            input_array = np.array([input_array])

            start_time = time.time()
            output = model.infer(input_array)
            end_time = time.time()

            cont_actions = output[4][0]
            cont_action_x = cont_actions[0]
            cont_action_y = cont_actions[1]
            
            angle = np.degrees(np.arctan2(cont_action_x, cont_action_y))
                        
            inference_time = end_time - start_time
            start_time = end_time
            transform_vel[0] = abs(cont_actions[0] / inference_time)
            transform_vel[1] = abs(cont_actions[1] / inference_time)
            
            distance_to_target = calculate_distance(rover_pos[0], rover_pos[1], target_pos[0], target_pos[1])
            if distance_to_target < 10:  # Stop if within 10 cm
                print("Target reached. Stopping rover.")
                chassis.set_velocity(0, 0, 0)
                break
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(csv_file, 'a') as file:
                file.write(f"{timestamp},{cont_action_x},{cont_action_y},{angle},"
                               f"{target_pos[0]},{target_pos[1]},"
                               f"{rover_pos[0]},{rover_pos[1]},"
                               f"{transform_vel[0]},{transform_vel[1]},"
                               f"{boundary_min[0]},{boundary_min[1]},{boundary_min[2]},"
                               f"{boundary_max[0]},{boundary_max[1]},{boundary_max[2]}\n")
            
            chassis.set_velocity(50, angle, 0)
            Board.RGB.setPixelColor(0, Board.PixelColor(0, 255, 0))
            Board.RGB.setPixelColor(1, Board.PixelColor(0, 255, 0))
            Board.RGB.show()

            time.sleep(0.25)

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        device_manager.stop_event.set()
        device_manager.stop_connection()
        connection_thread.join()

if __name__ == "__main__":
    execute_movement(3)
