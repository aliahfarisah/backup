import pygame
import asyncio
import threading
import datetime
import Pyro5.api
import numpy as np
import math
import pandas as pd

class RoverVisualization:
    def __init__(self):
        self.grey = (150, 150, 150)
        self.black = (0, 0, 0)
        self.blue = (0, 0, 255)
        self.red = (255, 0, 0)
        self.radius = 10
        self.screen_height, self.screen_width = 750, 1500
        self.padx, self.pady = 50, 50
        self.real_width = 1500  # Set default real-world dimensions
        self.real_height = 750
        self.rover_positions = {}
        self.result_dict = {}
        self.lock = threading.Lock()
        self.target_pos = [1300, 205]

        # Initialize Pygame and set up the screen
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        self.font = pygame.font.Font('freesansbold.ttf', 16)
        self.ratio_memo = self.font.render('1mm : 1px', True, self.black)
        pygame.display.set_caption(str(datetime.datetime.now()))

    def fetch_device_info(self, uri):
        try:
            with Pyro5.api.Proxy(uri) as proxy:
                while True:
                    name, x, y, z, t_tag, status = proxy.get_coordinates()
                    print(f"Data fetched from {uri}: {name}, {status}, {x}, {y}, {z}, {t_tag}")
                    with self.lock:
                        self.result_dict[uri] = (name, x, y, z, t_tag, status)
        except Exception as e:
            print(f"Error fetching data from server {uri}: {e}")
            with self.lock:
                self.result_dict[uri] = (None, None, None, None, None, None)

    def start_rover_threads(self):
        df = pd.read_csv('ip.csv')  
        threads = []
        for index, row in df.iterrows():
            rover_id = row['ID']
            ip_address = row['IP']
            uri = f"PYRO:uwb@{ip_address}:9091"
            print(f"Starting thread for {rover_id} with URI {uri}")
            thread = threading.Thread(target=self.fetch_device_info, args=(uri,))
            threads.append(thread)
            thread.daemon = True
            thread.start()

    def update_screen(self):
        self.screen.fill((255, 255, 255))
        
        with self.lock:
            for uri, rover_data in list(self.result_dict.items()):
                rover_name, rover_x, rover_y, rover_z, rover_t_tag, rover_status = rover_data
                rover_x = rover_x[0] if isinstance(rover_x, list) and rover_x else 0
                rover_y = rover_y[0] if isinstance(rover_y, list) and rover_y else 0
                rover_name = rover_name[0] if isinstance(rover_name, list) and rover_name else "Unknown"

                rover_x = float(rover_x) if isinstance(rover_x, (int, float)) else 0
                rover_y = float(rover_y) if isinstance(rover_y, (int, float)) else 0

                if not math.isnan(rover_x) and not math.isnan(rover_y):
                    if rover_name != "Unknown":
                        drawx = int(rover_x)  
                        drawy = int(rover_y)
                        self.rover_positions[rover_name] = (drawx, drawy)

        if len(self.rover_positions) < 1:
            error_pos = (50, 150)
            error_message = self.font.render('! Error: No Rover detected', True, self.red)
            self.screen.blit(error_message, error_pos)
        else:
            self.draw_rover_info()

        self.draw_rovers()
        self.draw_target()
        self.draw_ratio_memo()

        pygame.display.update()

    def draw_rover_info(self):
        message = f'Rover detected: {len(self.rover_positions)}'
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

        pygame.draw.rect(self.screen, dark_blue, pygame.Rect(tab_x + offset_x, tab_y + offset_y, tab_width + border_width, tab_height + border_height))
        pygame.draw.rect(self.screen, light_blue, pygame.Rect(tab_x + offset_x + border_width // 2, tab_y + offset_y + border_height // 2, tab_width, tab_height))

        message_surface = self.font.render(message, True, message_color)
        message_rect = message_surface.get_rect()
        message_rect.center = (tab_x + offset_x + (tab_width // 2) + border_width // 2, 
                               tab_y + offset_y + (tab_height // 2) + border_height // 2)
        self.screen.blit(message_surface, message_rect)

    def draw_rovers(self):
        for name, position in self.rover_positions.items():
            if 0 <= position[0] <= self.screen_width and 0 <= position[1] <= self.screen_height:
                pygame.draw.circle(self.screen, self.blue, position, self.radius)

                matching_data = [
                    rover_data for uri, rover_data in self.result_dict.items()
                    if rover_data and rover_data[0] and rover_data[0][0] == name
                ]

                rover_status = matching_data[0][5][0] if matching_data and matching_data[0][5] else 'Unknown'

                if rover_status == 'Disconnected':
                    small_red_circle_pos = (position[0], position[1] - self.radius + 10)
                    if 0 <= small_red_circle_pos[0] <= self.screen_width and 0 <= small_red_circle_pos[1] <= self.screen_height:
                        pygame.draw.circle(self.screen, self.red, small_red_circle_pos, 5)
                    
                coord_text = f"({position[0]}, {position[1]})"
                coord_surface = self.font.render(coord_text, True, self.black)
                coord_rect = coord_surface.get_rect()
                coord_rect.midtop = (position[0], position[1] + 20)
                self.screen.blit(coord_surface, coord_rect)
                
                text_surface = self.font.render(name, True, self.black)
                text_rect = text_surface.get_rect()
                text_rect.midtop = (position[0], position[1] - 35)
                self.screen.blit(text_surface, text_rect)
            else:
                print(f"Position {position} is out of screen bounds.")  # Debug print
                
    def draw_target(self):
        pygame.draw.circle(self.screen, self.red, self.target_pos, self.radius)
        target_label = self.font.render("Target", True, self.black)
        target_coords = self.font.render(f"({self.target_pos[0]}, {self.target_pos[1]})", True, self.black)
        self.screen.blit(target_label, (self.target_pos[0] - target_label.get_width() // 2, self.target_pos[1] - 35))
        self.screen.blit(target_coords, (self.target_pos[0] - target_coords.get_width() // 2, self.target_pos[1] + 20))

    def draw_ratio_memo(self):
        memo_pos = (self.screen_width - 100, self.screen_height - 20)
        self.screen.blit(self.ratio_memo, memo_pos)

    def run(self):
        self.start_rover_threads()

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    
                if event.type == pygame.MOUSEBUTTONDOWN:
                    target_pos = event.pos
                    target_x_scale = (target_pos[0] * 90 / self.real_width) - 45
                    target_y_scale = (target_pos[1] * 90 / self.real_height) - 45
                    target_position = np.array([target_x_scale, 0.03, target_y_scale]).astype(np.float32)

            self.update_screen()

        pygame.quit()

def main():
    pygame.init()
    visualization = RoverVisualization()
    visualization.run()

if __name__ == '__main__':
    main()

