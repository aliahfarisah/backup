import pygame
import asyncio
import threading
import pandas as pd
import datetime
import Pyro5.api
import math
import numpy as np

class Sprite(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, color):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface([width, height])
        self.image.fill(color)
        self.rect = self.image.get_rect(center=(x, y))

def start_connection_for_rover(rover_id, ip_address, result_dict, lock):
    uri = f"PYRO:rover_server@{ip_address}:9091"
    try:
        print(f"Starting connection for rover {rover_id} at {uri}")
        with Pyro5.api.Proxy(uri) as proxy:
            proxy.start_connection(rover_id)
            threading.Event().wait(1)
            fetch_device_info(uri, result_dict, lock)
    except ConnectionRefusedError:
        print(f"Connection refused for rover {rover_id} at {uri}\n")
    except Exception as e:
        print(f"General error connecting to rover {rover_id} at {uri}: {e}\n")

def fetch_device_info(uri, result_dict, lock):
    try:
        print(f"Connecting to {uri}")
        with Pyro5.api.Proxy(uri) as proxy:
            print(f"Proxy created for {uri}")
            name, x, y, z, t_tag = proxy.get_coordinates()
            print(f"Data fetched from {uri}: {name}, {x}, {y}, {z}, {t_tag}")
            with lock:
                result_dict[uri] = (name, x, y, z, t_tag)
    except Exception as e:
        print(f"Error fetching data from server {uri}: {e}")
        with lock:
            result_dict[uri] = (None, None, None, None, None)

def calculate_moving_averages(x_values, y_values, window_size=10):
    df = pd.DataFrame({'X': x_values, 'Y': y_values})
    
    # Define the bounds
    x_min, x_max = 0, 1.5
    y_min, y_max = 0, 0.75
    
    # Filter out-of-bounds values
    df = df[(df['X'] > x_min) & (df['X'] < x_max) & (df['Y'] > y_min) & (df['Y'] < y_max)]
    
    # Calculate moving averages
    df['avg_x'] = df['X'].rolling(window=window_size, min_periods=1).mean()
    df['avg_y'] = df['Y'].rolling(window=window_size, min_periods=1).mean()
    
    return df['avg_x'].values, df['avg_y'].values

async def main():
    pygame.init()

    grey = (150, 150, 150)
    black = (0, 0, 0)
    rover_color = (153, 0, 0)
    a = str(datetime.datetime.now())
    pygame.display.set_caption(a)

    # Dictionaries to store sprite positions
    rover_positions = {}
    screen_height, screen_width = 750, 1500
    padx, pady = 50, 50
    screen = pygame.display.set_mode((screen_width, screen_height))
    screen.fill((255, 255, 255))

    # Create font object
    font = pygame.font.Font('freesansbold.ttf', 16)
    ratio_memo = font.render('1mm : 1px', True, black)
    
    running = True
    real_width = 0
    real_height = 0
    
    result_dict = {}
    lock = threading.Lock()
    
    # Lists to store raw data for moving average calculation
    x_values = []
    y_values = []
    
    # Load rover data from CSV
    df = pd.read_csv('ip.csv')

    # Start threads for each rover
    threads = []
    for index, row in df.iterrows():
        rover_id = row['ID']
        ip_address = row['IP']
        thread = threading.Thread(target=start_connection_for_rover, args=(rover_id, ip_address, result_dict, lock))
        threads.append(thread)
        thread.start()

    # Main loop
    while running:
        screen.fill((255, 255, 255))
        
        rover_x = rover_y = None
        
        with lock:
            for uri, rover_data in result_dict.items():
                rover_name, rover_x, rover_y, rover_z, rover_t_tag = rover_data

                # Convert x, y, z, and name to single values if they are lists
                rover_x = rover_x[0] if isinstance(rover_x, list) and rover_x else 0
                rover_y = rover_y[0] if isinstance(rover_y, list) and rover_y else 0
                rover_z = rover_z[0] if isinstance(rover_z, list) and rover_z else 0
                rover_name = rover_name[0] if isinstance(rover_name, list) and rover_name else "Unknown"

                rover_x = float(rover_x) if isinstance(rover_x, (int, float)) else 0
                rover_y = float(rover_y) if isinstance(rover_y, (int, float)) else 0
                rover_z = float(rover_z) if isinstance(rover_z, (int, float)) else 0

                print(f"Rover data: {rover_name}, X: {rover_x}, Y: {rover_y}, Width: {real_width}, Height: {real_height}")

        # Append new data to the lists
        x_values.append(rover_x)
        y_values.append(rover_y)
        
        # Calculate moving averages
        avg_x, avg_y = calculate_moving_averages(x_values, y_values)
        
        # Use the latest moving average values
        if len(avg_x) > 0:
            moving_avg_x = avg_x[-1]
            moving_avg_y = avg_y[-1]
        else:
            moving_avg_x = rover_x
            moving_avg_y = rover_y
        
        # Convert and store rover position in pixels
        if moving_avg_x is not None and moving_avg_y is not None:
            # Ensure real_width and real_height are positive values
            if real_width <= 0 or math.isnan(real_width):
                real_width = 1500  # Example default value

            if real_height <= 0 or math.isnan(real_height):
                real_height = 750  # Example default value

            # Ensure moving_avg_x and moving_avg_y are valid numbers
            if not math.isnan(moving_avg_x) and not math.isnan(moving_avg_y):
                # Calculate screen position
                if isinstance(real_width, (int, float)) and isinstance(real_height, (int, float)):
                    calc_x = int(((screen_width - (2 * padx)) * moving_avg_x) / real_width)
                    calc_y = int(((screen_height - (2 * pady)) * moving_avg_y) / real_height)
                    drawx = calc_x + padx
                    drawy = screen_height - calc_y - pady
                    rover_positions[rover_name] = (drawx, drawy)
            else:
                print(f"Invalid rover coordinates: X={moving_avg_x}, Y={moving_avg_y}")

        # Display messages and rovers only if rovers are detected
        if len(rover_positions.values()) < 1:
            error_pos = (50, 150)
            error_message = font.render('! Error: No Rover detected', True, (255, 0, 0))
            screen.blit(error_message, error_pos)
        else:
            error_pos = (50, 150)
            error_message = font.render(f'Rover detected: {len(rover_positions.values())}', True, (255, 0, 0))
            screen.blit(error_message, error_pos)
            for position in rover_positions.values():
                pygame.draw.circle(screen, rover_color, position, 10)  # Draw a circle at each position

            for name, position in rover_positions.items():
                coord_text = f"({int(moving_avg_x)}, {int(moving_avg_y)})" if not math.isnan(moving_avg_x) and not math.isnan(moving_avg_y) else "(Invalid coordinates)"
                coord_surface = font.render(coord_text, True, black)
                coord_rect = coord_surface.get_rect()
                coord_rect.midtop = (position[0], position[1] - 20)
                screen.blit(coord_surface, coord_rect)
                
                # Render and display the name of the rover
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
