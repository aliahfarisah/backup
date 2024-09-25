import pygame
import asyncio
import threading
import pandas as pd
import datetime
import Pyro5.api
import numpy as np
import math

class Sprite(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, color):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface([width, height])
        self.image.fill(color)
        self.rect = self.image.get_rect(center=(x, y))

def start_connection_for_rover(rover_id, ip_address, rover_positions, lock):
    uri = f"PYRO:rover_server@{ip_address}:9091"
    try:
        print(f"Starting connection for rover {rover_id} at {uri}")
        with Pyro5.api.Proxy(uri) as proxy:
            proxy.start_connection(rover_id)
            threading.Event().wait(1)
            fetch_device_info(uri, rover_positions, lock)
    except ConnectionRefusedError:
        print(f"Connection refused for rover {rover_id} at {uri}\n")
    except Exception as e:
        print(f"General error connecting to rover {rover_id} at {uri}: {e}\n")

def fetch_device_info(uri, rover_positions, lock):
    try:
        print(f"Connecting to {uri}")
        with Pyro5.api.Proxy(uri) as proxy:
            print(f"Proxy created for {uri}")
            name, x, y, z, t_tag = proxy.get_coordinates()
            print(f"Data fetched from {uri}: {name}, {x}, {y}, {z}, {t_tag}\n")
            with lock:
                rover_x = x[0] if isinstance(x, list) and x else 0
                rover_y = y[0] if isinstance(y, list) and y else 0
                rover_z = z[0] if isinstance(z, list) and z else 0
                rover_name = name[0] if isinstance(name, list) and name else "Unknown"
                rover_positions[uri] = (rover_name, rover_x, rover_y, rover_z, t_tag)
    except Exception as e:
        print(f"Error fetching data from server {uri}: {e}\n")
        with lock:
            rover_positions[uri] = ("Unknown", 0, 0, 0, None)

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
    
    running = True
    width = 1500  # Set default real-world dimensions
    height = 750

    # Load rover details from CSV
    df = pd.read_csv('ip.csv')  
    target_pos = [1300, 205]

    # Define a lock for thread-safe access
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

    # Main loop
    while running:
        screen.fill((255, 255, 255))
        
        with lock:
        # Iterate over a copy of the dictionary items to avoid RuntimeError
            for uri, rover_data in list(rover_positions.items()):
                print(f"Debug: {rover_data}")
                rover_name, rover_x, rover_y, rover_z, rover_t_tag = rover_data

                # Convert x, y, z, and name to single values if they are lists
                rover_x = float(rover_x)
                rover_y = float(rover_y)

                print(f"Rover data: {rover_name}, X: {rover_x}, Y: {rover_y}, Width: {width}, Height: {height}")

                if rover_x is not None and rover_y is not None:
                    if width > 0 and height > 0:
                        calc_x = int(((screen_width - (2 * padx)) * rover_x) / width)
                        calc_y = int(((screen_height - (2 * pady)) * rover_y) / height)
                        drawx = calc_x + padx
                        drawy = screen_height - calc_y - pady
                        rover_positions[rover_name] = (drawx, drawy)

        if len(rover_positions) < 1:
            error_pos = (50, 150)
            error_message = font.render('! Error: No Rover detected', True, (255, 0, 0))
            screen.blit(error_message, error_pos)
        else:
            for name, position in rover_positions.items():
                if isinstance(position, (tuple, list)) and len(position) == 2 and all(isinstance(i, (int, float)) for i in position):
                    pygame.draw.circle(screen, blue, position, radius)
                else:
                    print(f"Invalid position data for {name}: {position}")
                    continue

                coord_text = f"({int(rover_x)}, {int(rover_y)})" if rover_x is not None and rover_y is not None else "(Invalid coordinates)"
                coord_surface = font.render(coord_text, True, black)
                coord_rect = coord_surface.get_rect()
                coord_rect.midtop = (position[0], position[1] + 20)
                screen.blit(coord_surface, coord_rect)
                
                text_surface = font.render(name, True, black)
                text_rect = text_surface.get_rect()
                text_rect.midtop = (position[0], position[1] - 35)
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
                target_x_scale = (target_pos[0] * 90 / width) - 45
                target_y_scale = (target_pos[1] * 90 / height) - 45
                target_position = np.array([target_x_scale, 0.03, target_y_scale]).astype(np.float32)

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())
