import pygame
import asyncio
import threading
import datetime
import Pyro5.api
import numpy as np
import math
import pandas as pd

class Stride(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, color):
        super().__init__()
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.image = pygame.Surface([width, height])
        self.image.fill(color)
        self.rect = self.image.get_rect(center=(x, y))

def fetch_device_info(uri, result_dict, lock):
    try:
        #print(f"Connecting to {uri}")
        with Pyro5.api.Proxy(uri) as proxy:
            while True:
            #print(f"Proxy created for {uri}")
                name, x, y, z, t_tag, status = proxy.get_coordinates()
                print(f"Data fetched from {uri}: {name}, {status}, {x}, {y}, {z}, {t_tag}")
                with lock:
                    #print(result_dict)
                    result_dict[uri] = (name, x, y, z, t_tag, status)
    except Exception as e:
        print(f"Error fetching data from server {uri}: {e}")
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

    #rover_sprite = pygame.image.load(r"C:\G7\rover\resources\rover.png")
    
    font = pygame.font.Font('freesansbold.ttf', 16)
    ratio_memo = font.render('1mm : 1px', True, black)
    
    running = True
    real_width = 1500  # Set default real-world dimensions
    real_height = 750

    # Load rover details from CSV
    df = pd.read_csv('ip.csv')  
    target_pos = [1000, 200]

    # Define a result dictionary and a lock for thread-safe access
    result_dict = {}
    lock = threading.Lock()

    # Start threads for each rover
    threads = []
    for index, row in df.iterrows():
        rover_id = row['ID']
        ip_address = row['IP']
        uri = f"PYRO:uwb@{ip_address}:9091"
        print(f"Starting thread for {rover_id} with URI {uri}")
        thread = threading.Thread(target=fetch_device_info, args=(uri, result_dict, lock))
        threads.append(thread)
        thread.daemon = True
        thread.start()

    # Main loop
    # Inside the main loop

    while running:
        screen.fill((255, 255, 255))
        
        with lock:
            for uri, rover_data in list(result_dict.items()):
                rover_name, rover_x, rover_y, rover_z, rover_t_tag, rover_status = rover_data
                rover_x = rover_x[0] if isinstance(rover_x, list) and rover_x else 0
                rover_y = rover_y[0] if isinstance(rover_y, list) and rover_y else 0
                rover_z = rover_z[0] if isinstance(rover_z, list) and rover_z else 0
                rover_name = rover_name[0] if isinstance(rover_name, list) and rover_name else "Unknown"

                rover_x = float(rover_x) if isinstance(rover_x, (int, float)) else 0
                rover_y = float(rover_y) if isinstance(rover_y, (int, float)) else 0

                if not math.isnan(rover_x) and not math.isnan(rover_y):
                    if rover_name != "Unknown":
                        drawx = int(rover_x)  
                        drawy = int(rover_y)
                        #print(f"Drawing rover '{rover_name}' at ({drawx}, {drawy})")  # Debug print
                        rover_positions[rover_name] = (drawx, drawy)

        if len(rover_positions) < 1:
            error_pos = (50, 150)
            error_message = font.render('! Error: No Rover detected', True, (255, 0, 0))
            screen.blit(error_message, error_pos)
        else:
            message = f'Rover detected: {len(rover_positions)}'
            message_color = (0, 255, 0)

            light_blue = (255, 232, 197)
            dark_blue = (255, 162, 127)

            tab_width = 200
            tab_height = 30
            tab_x = 30
            tab_y = 150
            
            offset_x = 10
            offset_y = 520
            border_width = 30
            border_height = 25

            pygame.draw.rect(screen, dark_blue, pygame.Rect(tab_x + offset_x, tab_y + offset_y, tab_width + border_width, tab_height + border_height))
            pygame.draw.rect(screen, light_blue, pygame.Rect(tab_x + offset_x + border_width // 2, tab_y + offset_y + border_height // 2, tab_width, tab_height))

            message_surface = font.render(message, True, message_color)
            message_rect = message_surface.get_rect()
            message_rect.center = (tab_x + offset_x + (tab_width // 2) + border_width // 2, 
                                    tab_y + offset_y + (tab_height // 2) + border_height // 2)
            screen.blit(message_surface, message_rect)
        
        for name, position in rover_positions.items():
            if 0 <= position[0] <= screen_width and 0 <= position[1] <= screen_height:
                # Draw the main rover circle
                pygame.draw.circle(screen, blue, position, radius)

                # Retrieve the rover status directly by matching the rover name
                matching_data = [
                    rover_data for uri, rover_data in result_dict.items()
                    if rover_data and rover_data[0] and rover_data[0][0] == name
                ]

                # Check if matching_data is not empty
                if matching_data and matching_data[0][5]:
                    rover_status = matching_data[0][5][0]  # Access the first match
                else:
                    rover_status = 'Unknown'

                #print("Rover status:", rover_status)

                # Draw the small red circle if status is 'Disconnect'
                if rover_status == 'Disconnected':
                    small_red_circle_pos = (position[0], position[1] - radius + 10)
                    if 0 <= small_red_circle_pos[0] <= screen_width and 0 <= small_red_circle_pos[1] <= screen_height:
                        pygame.draw.circle(screen, red, small_red_circle_pos, 5)
                    
                coord_text = f"({position[0]}, {position[1]})"
                coord_surface = font.render(coord_text, True, black)
                coord_rect = coord_surface.get_rect()
                coord_rect.midtop = (position[0], position[1] + 20)
                screen.blit(coord_surface, coord_rect)
                
                text_surface = font.render(name, True, black)
                text_rect = text_surface.get_rect()
                text_rect.midtop = (position[0], position[1] - 35)
                screen.blit(text_surface, text_rect)
            else:
                print(f"Position {position} is out of screen bounds.")  # Debug print

        memo_pos = (screen_width - ratio_memo.get_width() - 10, screen_height - ratio_memo.get_height() - 10)
        screen.blit(ratio_memo, memo_pos)
        
        pygame.draw.circle(screen, red, target_pos, radius)
        target_label = font.render("Target", True, black)
        target_coords = font.render(f"({target_pos[0]}, {target_pos[1]})", True, black)
        screen.blit(target_label, (target_pos[0] - target_label.get_width() // 2, target_pos[1] - 35))
        screen.blit(target_coords, (target_pos[0] - target_coords.get_width() // 2, target_pos[1] + 20))
        
        pygame.display.update()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                    
            if event.type == pygame.MOUSEBUTTONDOWN:
                target_pos = event.pos
                target_x_scale = (target_pos[0] * 90 / real_width) - 45
                target_y_scale = (target_pos[1] * 90 / real_height) - 45
                target_position = np.array([target_x_scale, 0.03, target_y_scale]).astype(np.float32)

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
