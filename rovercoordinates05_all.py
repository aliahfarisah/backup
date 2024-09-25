import pygame
import asyncio
import datetime
import Pyro5.api
import numpy as np
import pandas as pd
import threading
from collections import deque
import math

class Sprite(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, color):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface([width, height])
        self.image.fill(color)
        self.rect = self.image.get_rect(center=(x, y))

def start_connection_for_rover(uri, rover_id, ip_address, result_dict, lock, df):
    try:
        print(f"Starting connection for rover {rover_id} at {uri}")
        with Pyro5.api.Proxy(uri) as proxy:
            proxy.start_connection(rover_id)
            while True:  # Loop to fetch data periodically
                fetch_device_info(uri, result_dict, lock)
    except ConnectionRefusedError:
        print(f"Connection refused for rover {rover_id} at {uri}\n")
    except Exception as e:
        print(f"General error connecting to rover {rover_id} at {uri}: {e}\n")

def fetch_device_info(uri, result_dict, lock):
    try:
        #print(f"Connecting to {uri}")
        with Pyro5.api.Proxy(uri) as proxy:
            #print(f"Proxy created for {uri}")
            name, x, y, z, t_tag, status = proxy.get_coordinates()
            print(f"Data fetched from {uri}: {name}, {x}, {y}, {z}, {t_tag}, {status}")
            with lock:
                result_dict[uri] = (name, x, y, z, t_tag, status)
    except Exception as e:
        print(f"Error fetching data from server {uri}: {e}\n")
        with lock:
            result_dict[uri] = (None, None, None, None, None, None)

async def main():
    pygame.init()

    grey = (150, 150, 150)
    black = (0, 0, 0)
    blue = (0, 0, 255)
    red = (255, 0, 0)
    radius = 10
    a = str(datetime.datetime.now())
    pygame.display.set_caption(a)

    rover_positions = {}
    screen_height, screen_width = 750, 1500
    padx, pady = 50, 50
    screen = pygame.display.set_mode((screen_width, screen_height))
    screen.fill((255, 255, 255))

    font = pygame.font.Font('freesansbold.ttf', 16)
    ratio_memo = font.render('1mm : 1px', True, black)
    target_pos = [1300, 205]

    # Load rover details from CSV
    df = pd.read_csv('ip.csv')  
    
    running = True
    real_width = 1500
    real_height = 750
    
    result_dict = {}
    lock = threading.Lock()

    # Start threads for each rover
    threads = []
    for index, row in df.iterrows():
        rover_id = row['ID']
        ip_address = row['IP']
        thread = threading.Thread(target=start_connection_for_rover, args=(rover_id, ip_address, rover_positions, lock))
        threads.append(thread)
        thread.start()
        
    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    while running:
        screen.fill((255, 255, 255))
        
        for rover_data in result_dict.items():
            rover_name, rover_x, rover_y, rover_z, rover_t_tag = rover_data

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
                drawx = int(rover_x)  
                drawy = int(rover_y)
                if rover_name != "Unknown":
                    rover_positions[rover_name] = (drawx, drawy)
            else:
                print(f"Invalid rover coordinates: X={rover_x}, Y={rover_y}")
               
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
                if isinstance(position, tuple) and len(position) == 2 and all(isinstance(i, (int, float)) for i in position):
                    pygame.draw.circle(screen, blue, position, radius)  # Draw a circle at each position
                    
                    coord_text = f"({int(rover_x)}, {int(rover_y)})"
                    coord_surface = font.render(coord_text, True, black)
                    coord_rect = coord_surface.get_rect()
                    coord_rect.midtop = (drawx, drawy + 20)
                    screen.blit(coord_surface, coord_rect)
                    
                    text_surface = font.render(rover_name, True, black)
                    text_rect = text_surface.get_rect()
                    text_rect.midtop = (drawx, drawy - 35)
                    screen.blit(text_surface, text_rect)

        memo_pos = (screen_width - ratio_memo.get_width() - 10, screen_height - ratio_memo.get_height() - 10)
        screen.blit(ratio_memo, memo_pos)
        
        # Draw the "Target" circle
        pygame.draw.circle(screen, red, target_pos, radius)
        target_label = font.render("Target", True, black)
        target_coords = font.render(f"({target_pos[0]}, {target_pos[1]})", True, black)
        screen.blit(target_label, (target_pos[0] - target_label.get_width() // 2, target_pos[1] - 35))
        screen.blit(target_coords, (target_pos[0] - target_coords.get_width() // 2, target_pos[1] + 20))
        
        pygame.display.update()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # Check for mouse click
            if event.type == pygame.MOUSEBUTTONDOWN:
                target_pos = event.pos  # Store the position where the mouse was clicked
                target_x_scale = (target_pos[0] * 90 / real_width) - 45
                target_y_scale = (target_pos[1] * 90 / real_height) - 45
                target_position = np.array([target_x_scale, 0.03, target_y_scale]).astype(np.float32)

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())
