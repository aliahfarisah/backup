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
    
    def add(self, value):
        self.data.append(value)
        return np.mean(self.data)

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
            avg_x = x_moving_avg.add(rover_x)
            avg_y = y_moving_avg.add(rover_y)

            calc_x_avg = int(((screen_width - (2 * padx)) * avg_x) / real_width)
            calc_y_avg = int(((screen_height - (2 * pady)) * avg_y) / real_height)
            drawx_avg = calc_x_avg + padx
            drawy_avg = screen_height - calc_y_avg - pady

            calc_x_raw = int(((screen_width - (2 * padx)) * rover_x) / real_width)
            calc_y_raw = int(((screen_height - (2 * pady)) * rover_y) / real_height)
            drawx_raw = calc_x_raw + padx
            drawy_raw = screen_height - calc_y_raw - pady

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
