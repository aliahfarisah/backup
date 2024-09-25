import pygame
import asyncio
import datetime
import Pyro5.api
import numpy as np
from collections import deque
import math

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
    
    def add(self, x, y):
        self.data.append((x, y))
        if len(self.data) == self.window_size:
            avg_x = np.mean([point[0] for point in self.data])
            avg_y = np.mean([point[1] for point in self.data])
            return avg_x, avg_y
        else:
            return x, y

class KalmanFilter:
    def __init__(self, process_variance, measurement_variance):
        self.process_variance = process_variance
        self.measurement_variance = measurement_variance
        self.estimate = 0.0
        self.estimate_variance = 1.0
    
    def update(self, measurement):
        # Prediction step
        self.estimate_variance += self.process_variance
        
        # Measurement update step
        kalman_gain = self.estimate_variance / (self.estimate_variance + self.measurement_variance)
        self.estimate += kalman_gain * (measurement - self.estimate)
        self.estimate_variance *= (1 - kalman_gain)
        
        return self.estimate

async def main():
    pygame.init()
    
    rover_id = 2
    uri = f"PYRO:rover_server@192.168.50.121:9091"

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

    x_moving_avg = MovingAverage(window_size=10)
    y_moving_avg = MovingAverage(window_size=10)

    x_kalman_filter = KalmanFilter(process_variance=1e-5, measurement_variance=1e-1)
    y_kalman_filter = KalmanFilter(process_variance=1e-5, measurement_variance=1e-1)
    
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

        print(f"Rover data: {rover_name}, X: {rover_x}, Y: {rover_y}, Width: {real_width}, Height: {real_height}")

        if not math.isnan(rover_x) and not math.isnan(rover_y):
            avg_x, avg_y = x_moving_avg.add(rover_x, rover_y)
            filtered_x = x_kalman_filter.update(rover_x)
            filtered_y = y_kalman_filter.update(rover_y)

            # Compute positions for display
            calc_x_avg = int(((screen_width - (2 * padx)) * avg_x) / real_width)
            calc_y_avg = int(((screen_height - (2 * pady)) * avg_y) / real_height)
            drawx_avg = calc_x_avg + padx
            drawy_avg = screen_height - calc_y_avg - pady

            calc_x_raw = int(((screen_width - (2 * padx)) * filtered_x) / real_width)
            calc_y_raw = int(((screen_height - (2 * pady)) * filtered_y) / real_height)
            drawx_raw = calc_x_raw + padx
            drawy_raw = screen_height - calc_y_raw - pady

            print(f"Smoothed data position: ({drawx_avg}, {drawy_avg})")
            print(f"Raw data position: ({drawx_raw}, {drawy_raw})")

            if rover_name != "Unknown":
                rover_positions[rover_name] = (drawx_avg, drawy_avg)

                # Draw the smoothed data
                pygame.draw.circle(screen, rover_color, (drawx_avg, drawy_avg), 10)

                # Draw the raw data
                pygame.draw.circle(screen, raw_color, (drawx_raw, drawy_raw), 10)

                # Render and display the raw data name and coordinates
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
                coord_text_avg = f"Avg: ({int(avg_x)}, {int(avg_y)})"
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
