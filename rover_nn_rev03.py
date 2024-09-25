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
        if value <= 40000:
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
        
        with device_manager.lock:
            if not device_manager.is_connected():
                print("Rover is not connected...")
                connection_thread = threading.Thread(target=device_manager.start_connection, args=(id_rover,))
                connection_thread.start()
                connection_thread.join()

        x_moving_avg = MovingAverage(window_size=10)
        y_moving_avg = MovingAverage(window_size=10)

        avg_x_kf = KalmanFilterWrapper()
        avg_y_kf = KalmanFilterWrapper()

        print(f"Executing movement for Rover {id_rover}")
        chassis = mecanum.MecanumChassis()

        width, height = 1500, 750
        rover_pos = [0, 0]  # Initialize rover position
        target_pos = [1000, 250]  # Target position

        # Scale target and rover positions
        target_x_scale = (target_pos[0] * 90 / width) - 45
        target_y_scale = (target_pos[1] * 90 / height) - 45

        target_position = np.array([target_x_scale, 0.03, target_y_scale]).astype(np.float32)
        transform_vel = np.array([0.0, 0.0]).astype(np.float32)
        boundary_min = np.array([-45, 0.0, -45]).astype(np.float32)
        boundary_max = np.array([45, 0.0, 45]).astype(np.float32)
        
        csv_file = 'rover_data.csv'
        csv_columns = ['timestamp',
                       'target_x', 'target_y','target_x_scale', 'target_y_scale',
                       'rover_x', 'rover_y','rover_x_scale', 'rover_y_scale',
                       'transform_vel_x', 'transform_vel_y',
                       'cont_action_x', 'cont_action_y',
                       'angle', 'flipped_angle', 'delta_x', 'delta_y','time_difference', 'distance_to_target']
        rover_database = pd.DataFrame(columns=csv_columns)
        
        # Initial previous values
        prev_rover_pos = None
        prev_time = None
        distance_to_target = None
        detection_tolerance = 50 #unit mm
        
        while not device_manager.stop_event.is_set():
            print("Waiting for the device to connect...")
            current_time = datetime.now().strftime('%Y%m%d%H%M%S.%f')[:-3]
            #Retrieve actual rover coord from UWB
            xr, yr = update_coordinates(device_manager, id_rover)
            #Compute MVA
            avg_x = x_moving_avg.add(xr)
            avg_y = y_moving_avg.add(yr)
            #Perform Kalman Filter
            kalman_avg_x = avg_x_kf.update(avg_x)
            kalman_avg_y = avg_y_kf.update(avg_y)
            #Convert array to single value
            kalman_avg_x = kalman_avg_x[0]
            kalman_avg_y = kalman_avg_y[0]
            rover_pos = [kalman_avg_x, kalman_avg_y]
            #print("Rover position:", rover_pos)
            #Scale factor
            transform_x_scale = (rover_pos[0] * 90 / width) - 45
            transform_y_scale = (rover_pos[1] * 90 / height) - 45
            transform_position = np.array([transform_x_scale, 0.03, transform_y_scale]).astype(np.float32)
            
            #Combine all input array
            input_array = np.concatenate((target_position, transform_position, transform_vel, boundary_min, boundary_max))
            print("Input array:", input_array)
            input_array = np.array([input_array])

            #Perform inference
            output = model.infer(input_array)
            
            #Retrive output
            cont_actions = output[4][0]
            cont_action_x = cont_actions[0]
            cont_action_y = cont_actions[1]
            
            #Calculate angle
            angle = np.degrees(np.arctan2(cont_action_y, cont_action_x))
            #Flipped angle for origin is top left
            angle_flip = angle * -1
            
            # Calculate time difference and distance moved
            if prev_rover_pos is not None and prev_time is not None:
                prev_time_obj = datetime.strptime(prev_time, '%Y%m%d%H%M%S.%f')
                current_time_obj = datetime.strptime(current_time, '%Y%m%d%H%M%S.%f')
                delta_t = (current_time_obj - prev_time_obj).total_seconds()
                print("Time differences:", delta_t)
                delta_x = kalman_avg_x - prev_rover_pos[0]
                print("delta_x:", delta_x)
                delta_y = kalman_avg_y - prev_rover_pos[1]
                print("delta_y:", delta_y)

                transform_vel_x = abs(delta_x / delta_t)
                print("transform_vel_x:", transform_vel_x)
                transform_vel_y = abs(delta_y / delta_t)
                print("transform_vel_y:", transform_vel_y)
            else:
                delta_x = 0.0
                delta_y = 0.0
                delta_t = 0.0
                transform_vel_x = 0.0
                transform_vel_y = 0.0

            # Update previous values
            prev_rover_pos = rover_pos
            prev_time = current_time
            
            # Append new entries to the all_device_info DataFrame
            new_entry = pd.DataFrame({
                                'timestamp': [current_time],
                                'target_x' : [target_pos[0]],
                                'target_y' : [target_pos[1]],
                                'target_x_scale' : [target_x_scale],
                                'target_y_scale' : [target_y_scale],
                                'rover_x' : [rover_pos[0]],
                                'rover_y' : [rover_pos[1]],
                                'rover_x_scale' : [transform_x_scale],
                                'rover_y_scale' : [transform_y_scale],
                                'transform_vel_x' : [transform_vel_x],
                                'transform_vel_y' : [transform_vel_y],
                                'cont_action_x' : [cont_action_x],
                                'cont_action_y' : [cont_action_y],
                                'angle' : [angle],
                                'flipped_angle' : [angle_flip],
                                'delta_x' : [delta_x],
                                'delta_y' : [delta_y],
                                'time_difference' : [delta_t],
                                'distance_to_target' : [distance_to_target]
                                
                            })
            rover_database = pd.concat([rover_database, new_entry], ignore_index=True)
            #print("Rover database:", rover_database)
            rover_database.to_csv(csv_file)
            print(f"Saved data to {csv_file}")
            
            distance_to_target = np.sqrt((rover_pos[0] - target_pos[0])**2 + (rover_pos[1] - target_pos[1])**2)
            print(f"Distance to target. {distance_to_target:} cm.")
   
            if distance_to_target < detection_tolerance:  # Adjust the threshold as needed
                print("Rover reached the target. Stopping rover.")
                chassis.set_velocity(0, 0, 0)
                break
            
            
            #Stop when reach boundary
            if rover_pos[0] > (width - 10) or rover_pos[0] < 10 or rover_pos[1] > (height - 10) or rover_pos[1] < 10: # Stop if within 10 cm
                print(f"Rover_pos_x : {rover_pos[0]}, Rover_pos_y : {rover_pos[1]}")
                print("Boundary reached. Stopping rover.")
                chassis.set_velocity(0, 0, 0)
                break
                               
            chassis.set_velocity(50, angle_flip, 0)
            Board.RGB.setPixelColor(0, Board.PixelColor(0, 255, 0))
            Board.RGB.setPixelColor(1, Board.PixelColor(0, 255, 0))
            Board.RGB.show()

            time.sleep(0.25)

        chassis.set_velocity(0, 0, 0)
        device_manager.stop_event.set()
        print("Rover movement completed")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        
if __name__ == "__main__":
    execute_movement(3)
