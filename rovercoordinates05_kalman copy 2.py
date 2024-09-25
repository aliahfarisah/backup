import pygame
import asyncio
import datetime
import Pyro5.api
import numpy as np
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
            name, x, y, z, t_tag = proxy.get_coordinates()
            print(f"Fetched data: Name={name}, X={x}, Y={y}, Z={z}, T_Tag={t_tag}")  # Debug output
            return name, x, y, z, t_tag
        except Exception as e:
            print(f"Error fetching data from server: {e}")
            return None, None, None, None, None

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

async def main():
    pygame.init()
    
    rover_id = 3
    uri = f"PYRO:rover_server@192.168.50.8:9091"

    grey = (150, 150, 150)
    black = (0, 0, 0)
    raw_color = (0, 0, 255)    # Circle color for raw data (Blue)
    raw_avg_color = (255, 255, 0)  # Circle color for raw data average (Yellow)
    kalman_color = (255, 0, 0)  # Circle color for Kalman-filtered data (Red)
    kalman_avg_color = (0, 255, 0)  # Circle color for Kalman-filtered average data (Green)
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

    x_moving_avg = MovingAverage(window_size=10)
    y_moving_avg = MovingAverage(window_size=10)
    
    x_kf = KalmanFilterWrapper()
    y_kf = KalmanFilterWrapper()
    
    avg_x_kf = KalmanFilterWrapper()  # Kalman filter for moving average results
    avg_y_kf = KalmanFilterWrapper()  # Kalman filter for moving average results
    
    with Pyro5.api.Proxy(uri) as proxy:
        proxy.start_connection(rover_id)

    while running:
        screen.fill((255, 255, 255))
        
        rover_name, rover_x, rover_y, rover_z, rover_t_tag = fetch_device_info(uri)

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

        # Filter and moving average
        if not math.isnan(rover_x) and not math.isnan(rover_y):
            # Kalman filter
            kalman_x = x_kf.update(rover_x)
            kalman_y = y_kf.update(rover_y)

            # Moving average without Kalman filter
            avg_x = x_moving_avg.add(rover_x)
            avg_y = y_moving_avg.add(rover_y)

            # Apply Kalman filter to moving average results
            kalman_avg_x = avg_x_kf.update(avg_x)
            kalman_avg_y = avg_y_kf.update(avg_y)

            # Convert coordinates to pixel space for raw data
            calc_x_raw = int(((screen_width - (2 * padx)) * rover_x) / real_width)
            calc_y_raw = int(((screen_height - (2 * pady)) * rover_y) / real_height)
            drawx_raw = calc_x_raw + padx
            drawy_raw = screen_height - calc_y_raw - pady

            # Convert coordinates to pixel space for raw moving average
            calc_x_raw_avg = int(((screen_width - (2 * padx)) * avg_x) / real_width)
            calc_y_raw_avg = int(((screen_height - (2 * pady)) * avg_y) / real_height)
            drawx_raw_avg = calc_x_raw_avg + padx
            drawy_raw_avg = screen_height - calc_y_raw_avg - pady

            # Convert coordinates to pixel space for Kalman-filtered data
            calc_x_kalman = int(((screen_width - (2 * padx)) * kalman_x) / real_width)
            calc_y_kalman = int(((screen_height - (2 * pady)) * kalman_y) / real_height)
            drawx_kalman = calc_x_kalman + padx
            drawy_kalman = screen_height - calc_y_kalman - pady

            # Convert coordinates to pixel space for Kalman-filtered moving average
            calc_x_kalman_avg = int(((screen_width - (2 * padx)) * kalman_avg_x) / real_width)
            calc_y_kalman_avg = int(((screen_height - (2 * pady)) * kalman_avg_y) / real_height)
            drawx_kalman_avg = calc_x_kalman_avg + padx
            drawy_kalman_avg = screen_height - calc_y_kalman_avg - pady

            if rover_name != "Unknown":
                rover_positions[rover_name] = (drawx_raw_avg, drawy_raw_avg)
        
        if len(rover_positions) < 1:
            error_pos = (50, 150)
            error_message = font.render('! Error: No Rover detected', True, (255, 0, 0))
            screen.blit(error_message, error_pos)
        else:
            error_pos = (50, 150)
            error_message = font.render(f'Rover detected: {len(rover_positions)}', True, (255, 0, 0))
            screen.blit(error_message, error_pos)
            for position in rover_positions.values():
                pygame.draw.circle(screen, raw_avg_color, position, 10)  # Raw data moving average
                
            pygame.draw.circle(screen, raw_color, (drawx_raw, drawy_raw), 10)  # Raw data circle
                
            # Draw the Kalman-filtered data circle
            pygame.draw.circle(screen, kalman_color, (drawx_kalman, drawy_kalman), 10)  # Kalman-filtered data circle
            
            # Draw the Kalman-filtered moving average circle
            pygame.draw.circle(screen, kalman_avg_color, (drawx_kalman_avg, drawy_kalman_avg), 10)  # Kalman-filtered average data circle
            
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

                coord_text_avg = f"Avg: ({int(avg_x)}, {int(avg_y)})"
                coord_surface_avg = font.render(coord_text_avg, True, black)
                coord_rect_avg = coord_surface_avg.get_rect()
                coord_rect_avg.midtop = (drawx_raw_avg, drawy_raw_avg - 20)
                screen.blit(coord_surface_avg, coord_rect_avg)

                coord_text_kalman = f"Kalman: ({int(kalman_x)}, {int(kalman_y)})"
                coord_surface_kalman = font.render(coord_text_kalman, True, black)
                coord_rect_kalman = coord_surface_kalman.get_rect()
                coord_rect_kalman.midtop = (drawx_kalman, drawy_kalman - 20)
                screen.blit(coord_surface_kalman, coord_rect_kalman)

                coord_text_kalman_avg = f"Kalman Avg: ({int(kalman_avg_x)}, {int(kalman_avg_y)})"
                coord_surface_kalman_avg = font.render(coord_text_kalman_avg, True, black)
                coord_rect_kalman_avg = coord_surface_kalman_avg.get_rect()
                coord_rect_kalman_avg.midtop = (drawx_kalman_avg, drawy_kalman_avg - 20)
                screen.blit(coord_surface_kalman_avg, coord_rect_kalman_avg)

        screen.blit(ratio_memo, (screen_width - 100, screen_height - 50))

        pygame.display.flip()
        await asyncio.sleep(0.25)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())
