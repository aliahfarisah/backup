import time
import threading
import numpy as np
import pandas as pd
from HiwonderSDK import mecanum, Board
from ble_manager import BLEDeviceManager  # Ensure you have BLEDeviceManager implemented

def update_coordinates(device_manager, id_rover):
    while not device_manager.stop_event.is_set():
        if device_manager.is_connected():
            device_info = device_manager.get_device_info()
            rover_data = device_info[device_info['Name'] == f'Rov{id_rover}']
            if not rover_data.empty:
                return rover_data.iloc[0]['X'], rover_data.iloc[0]['Y']
        time.sleep(1)
    return None, None

def execute_movement(id_rover, duration=1):
    # Initialize device manager and start scanning and connection threads
    device_manager = BLEDeviceManager()
    device_manager.stop_event = threading.Event()

    scan_thread = threading.Thread(target=device_manager.scan_for_devices, args=(5.0, [f'Rov{id_rover}']))
    scan_thread.start()
    scan_thread.join()

    connection_thread = threading.Thread(target=device_manager.start_connection, args=(id_rover,))
    connection_thread.start()

    print(f"Executing movement for Rover {id_rover}")
    chassis = mecanum.MecanumChassis()

    # Initialize the DataFrame to store coordinates
    columns = ['time', 'x', 'y', 'dXr', 'dYr', 'distance']
    df = pd.DataFrame(columns=columns)

    # Wait until coordinates are available
    xr, yr = None, None
    while xr is None and yr is None:
        xr, yr = update_coordinates(device_manager, id_rover)
        print(f"Initial coordinates: x={xr}, y={yr}")

    start_time = time.time()
    prev_x, prev_y = xr / 1000, yr / 1000  # Convert to meters

    # Movement loop
    update_interval = 0.1  # Example: 100ms update rate
    end_time = start_time + duration

    while time.time() < end_time:
        loop_start_time = time.time()
        
        xr, yr = update_coordinates(device_manager, id_rover)
        if xr is not None and yr is not None:
            xr = xr / 1000  # Convert to meters
            yr = yr / 1000  # Convert to meters

            # Calculate distance
            dXr = xr - prev_x
            dYr = yr - prev_y
            distance_m = np.sqrt(dXr**2 + dYr**2)

            # Save the coordinates and distance to the DataFrame
            current_time = loop_start_time - start_time
            new_row = {
                'time': current_time, 
                'x': xr, 
                'y': yr,
                'dXr': dXr,
                'dYr': dYr,
                'distance': distance_m
            }
            df = df.append(new_row, ignore_index=True)
            print(f"Time: {current_time:.2f}s, x={xr:.3f}, y={yr:.3f}, distance={distance_m:.3f}")

            # Update previous coordinates
            prev_x, prev_y = xr, yr

            # Set the rover's velocity and direction at a fixed angle of 90 degrees
            chassis.set_velocity(100, 90, 0)

            # Example of setting RGB LEDs (adjust as needed)
            Board.RGB.setPixelColor(0, Board.PixelColor(255, 0, 0))  # Red color
            Board.RGB.setPixelColor(1, Board.PixelColor(0, 255, 0))  # Green color
            Board.RGB.show()

        else:
            print(f"No data received from BLE for Rover {id_rover}. Stopping movement.")
            break

        # Ensure loop runs at a consistent rate
        elapsed_time = time.time() - loop_start_time
        sleep_time = max(0, update_interval - elapsed_time)
        time.sleep(sleep_time)

    # Final sleep to ensure the total duration is exactly 1 second
    remaining_time = end_time - time.time()
    if remaining_time > 0:
        time.sleep(remaining_time)

    # Stop the robot and close RGB show
    chassis.set_velocity(0, 0, 0)
    Board.RGB.setPixelColor(0, Board.PixelColor(0, 0, 0))  # Turn off LEDs
    Board.RGB.setPixelColor(1, Board.PixelColor(0, 0, 0))  # Turn off LEDs
    Board.RGB.show()

    # Remove the first row if it has a NaN time value
    df = df.dropna(subset=['time']).reset_index(drop=True)

    # Save the DataFrame to CSV
    csv_filename = f'rover_{id_rover}_coordinates_100.csv'  # Hardcoded filename based on rover ID
    df.to_csv(csv_filename, index=False)
    print(f"Data saved to {csv_filename}")

if __name__ == "__main__":
    id_rover = 3  # Replace with your rover's ID
    execute_movement(id_rover, duration=1)  # Set duration to 1 second
