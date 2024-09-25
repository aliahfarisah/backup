import pygame
import asyncio
import datetime
import Pyro5.api
import numpy as np
import pandas as pd
from collections import deque
import math
from filterpy.kalman import KalmanFilter

class Sprite(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, color):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface([width, height])
        self.image.fill(color)
        self.rect = self.image.get_rect(center=(x, y))

def fetch_device_info(uri):
    with Pyro5.api.Proxy(uri) as proxy:
        try:
            name, x, y, z, t_tag, status = proxy.get_coordinates()
            print(f"Fetched data: Name={name}, X={x}, Y={y}, Z={z}, T_Tag={t_tag}, Status={status}")  # Debug output
            return name, x, y, z, t_tag, status
        except Exception as e:
            print(f"Error fetching data from server: {e}")
            return None, None, None, None, None, None

class MovingAverage:
    def __init__(self, window_size):
        self.window_size = window_size
        self.data = deque(maxlen=window_size)
    
    def add(self, value):
        self.data.append(value)
        return np.mean(self.data)

def initialize_kalman_filter(initial_x, initial_y):
    kf = KalmanFilter(dim_x=2, dim_z=2)
    
    # Initial state (x, y)
    kf.x = np.array([initial_x, initial_y])
    
    # State transition matrix
    dt = 1  # Time step
    kf.F = np.eye(2)
    
    # Measurement matrix
    kf.H = np.eye(2)
    
    # Process noise covariance
    kf.Q = np.eye(2)
    
    # Measurement noise covariance
    kf.R = np.array([
        [10, 0],
        [0, 10]
    ])
    
    # Initial uncertainty
    kf.P = np.eye(2) * 1000
    
    return kf

def save_to_csv(filename, df):
    df.to_csv(filename, mode='a', header=False, index=False)

async def main():
    pygame.init()
    
    rover_id = 2
    uri = f"PYRO:uwb@192.168.50.251:9091"

    grey = (150, 150, 150)
    black = (0, 0, 0)
    rover_color = (153, 0, 0)  # Circle color for smoothed data
    raw_color = (0, 0, 255)    # Circle color for raw data
    rover2_color = (153, 150, 0) # Another rover circle color
    a = str(datetime.datetime.now())
    pygame.display.set_caption(a)

    rover_positions = {}
    screen_height, screen_width = 750, 1500
    padx, pady = 50, 50
    screen = pygame.display.set_mode((screen_width, screen_height))
    screen.fill((255, 255, 255))

    font = pygame.font.Font('freesansbold.ttf', 16)
    ratio_memo = font.render('1mm : 1px', True, black)
    
    running = True
    real_width = 1500
    real_height = 750
    
    # CSV filename
    csv_filename = 'rover_data.csv'
    
    # DataFrame to store data
    df = pd.DataFrame(columns=['Timestamp', 'Rover Name', 'Raw X', 'Raw Y'])

    
    
    # Initialize Kalman Filters
    kf_raw = initialize_kalman_filter()
    kf_avg = initialize_kalman_filter()
    
    x_moving_avg = MovingAverage(window_size=10)
    y_moving_avg = MovingAverage(window_size=10)
    
    window_size = 10

    with Pyro5.api.Proxy(uri) as proxy:
        proxy.start_connection(rover_id)

    while running:
        screen.fill((255, 255, 255))
        
        rover_name, rover_x, rover_y, rover_z, rover_t_tag, rover_status = fetch_device_info(uri)

        if isinstance(rover_x, list):
            rover_x = rover_x[0] if rover_x else 0
        if isinstance(rover_y, list):
            rover_y = rover_y[0] if rover_y else 0
        if isinstance(rover_z, list):
            rover_z = rover_z[0] if rover_z else 0
        if isinstance(rover_name, list):
            rover_name = rover_name[0] if rover_name else "Unknown"

        rover_x = float(rover_x) if isinstance(rover_x, (int, float)) else float('nan')
        rover_y = float(rover_y) if isinstance(rover_y, (int, float)) else float('nan')

        print(f"Rover data: {rover_name}, X: {rover_x}, Y: {rover_y}, Width: {real_width}, Height: {real_height}")

        if not math.isnan(rover_x) and not math.isnan(rover_y):
            # Add the new data to the DataFrame
            new_data = {
                'Timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                'Rover Name': rover_name,
                'Raw X': rover_x,
                'Raw Y': rover_y,
                'Avg X': df['Avg X'].iloc[-1],
                'Avg Y': df['Avg Y'].iloc[-1],
                'Kalman X': kf_raw.x[0],
                'Kalman Y': kf_raw.x[1]
            }

            df = df.append(new_data, ignore_index=True)

            # Save latest row to CSV
            save_to_csv(csv_filename, index=False)
                        
            # Apply Kalman Filter to Raw Data
            kf_raw.predict()
            measurement_raw = np.array([rover_x, rover_y])
            kf_raw.update(measurement_raw)
            df['Kalman X'] = kf_raw.x[0]
            df['Kalman Y'] = kf_raw.x[1]
            
            # Calculate Moving Average for raw data (instead of filtered data)
            df['Avg X'] = df['Raw X'].rolling(window=window_size).mean()
            df['Avg Y'] = df['Raw Y'].rolling(window=window_size).mean()
            
            # Apply Kalman Filter to Moving Average Data
            kf_avg.predict()
            measurement_avg = np.array([df['Avg X'].iloc[-1], df['Avg Y'].iloc[-1]])
            kf_avg.update(measurement_avg)
            filtered_x_avg, filtered_y_avg = kf_avg.x

            calc_x_avg = int(((screen_width - (2 * padx)) * filtered_x_avg) / real_width)
            calc_y_avg = int(((screen_height - (2 * pady)) * filtered_y_avg) / real_height)
            drawx_avg = calc_x_avg + padx
            drawy_avg = screen_height - calc_y_avg - pady

            calc_x_raw = int(((screen_width - (2 * padx)) * df['Kalman X'].iloc[-1]) / real_width)
            calc_y_raw = int(((screen_height - (2 * pady)) * df['Kalman Y'].iloc[-1]) / real_height)
            drawx_raw = calc_x_raw + padx
            drawy_raw = calc_y_raw - pady

            if rover_name != "Unknown":
                rover_positions[rover_name] = (drawx_avg, drawy_avg)
        
        if len(rover_positions) < 1:
            error_pos = (50, 150)
            error_message = font.render('! Error: No Rover detected', True, (255, 0, 0))
            screen.blit(error_message, error_pos)
        else:
            error_pos = (50, 150)
            error_message = font.render(f'Rover detected: {len(rover_positions)}', True, (255, 0, 0))
            screen.blit(error_message, error_pos)
            for position in rover_positions.values():
                pygame.draw.circle(screen, rover_color, position, 10)  # Smoothed data

            # Draw the raw data circle
            pygame.draw.circle(screen, raw_color, (drawx_raw, drawy_raw), 10)  # Raw data circle

            # Render and display the raw data name and coordinates
            if rover_name != "Unknown":
                coord_text_raw = f"Raw: ({int(rover_x)}, {int(rover_y)})"
                coord_surface_raw = font.render(coord_text_raw, True, black)
                coord_rect_raw = coord_surface_raw.get_rect()
                coord_rect_raw.midtop = (drawx_raw, drawy_raw - 20)
                screen.blit(coord_surface_raw, coord_rect_raw)

                name_surface = font.render(rover_name, True, black)
                name_rect = name_surface.get_rect()
                name_rect.midtop = (drawx_raw, drawy_raw - 40)
                screen.blit(name_surface, name_rect)

            for name, position in rover_positions.items():
                coord_text_avg = f"Avg: ({int(filtered_x_avg)}, {int(filtered_y_avg)})"
                coord_surface_avg = font.render(coord_text_avg, True, black)
                coord_rect_avg = coord_surface_avg.get_rect()
                coord_rect_avg.midtop = (position[0], position[1] - 20)
                screen.blit(coord_surface_avg, coord_rect_avg)
                
                text_surface = font.render(name, True, black)
                text_rect = text_surface.get_rect()
                text_rect.midtop = (position[0], position[1] - 40)
                screen.blit(text_surface, text_rect)
        
        memo_pos = (screen_width - ratio_memo.get_width() - 10, screen_height - ratio_memo.get_height() - 10)
        screen.blit(ratio_memo, memo_pos)
        
        pygame.display.update()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())
