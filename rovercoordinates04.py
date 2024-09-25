import pygame
import asyncio
import threading
import pandas as pd
import datetime
import Pyro5.api
from deviceManager_BLEv4 import BLEDeviceManager

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
            return name, x, y, z, t_tag
        except Exception as e:
            print(f"Error fetching data from server: {e}")
            return None, None, None, None, None

def print_rover_info(name, x, y, z, t_tag):
    data = {
        'Name': name,
        'X': x,
        'Y': y,
        'Z': z,
        'Time': t_tag
    }
    df = pd.DataFrame([data])
    print(df.to_string(index=False))

async def main():
    pygame.init()
    
    # Assuming you want to visualize the rover with ID 2
    rover_id = 2
    uri = f"PYRO:rover_server@192.168.50.116:9091"
    
    dm = BLEDeviceManager()
    
    threading.Thread(target=dm.start_connection, args=()).start()
    grey = (150, 150, 150)
    black = (0, 0, 0)
    
    anchor_positions = {}
    rover_positions = {}
    screen_height, screen_width = 750, 1500
    padx, pady = 30, 30
    anchor_list = [
        (padx, pady),  # Top-left corner
        (padx, screen_height - pady),  # Bottom-left corner
        (screen_width - padx, screen_height - pady),  # Bottom-right corner
        (screen_width - padx, pady)  # Top-right corner
    ]
    screen = pygame.display.set_mode((screen_width, screen_height))
    screen.fill((255, 255, 255))

    # Load rover sprite
    rover_sprite = pygame.image.load(r"C:\G7\rover\resources\rover.png")

    # Create font object
    font = pygame.font.Font('freesansbold.ttf', 16)
    titlefont = pygame.font.Font('freesansbold.ttf', 21)

    # Render texts
    text_surfaces = {
        'AncOne': font.render('AncOne', True, black),
        'AncTwo': font.render('AncTwo', True, black),
        'AncThr': font.render('AncThr', True, black),
        'AncFou': font.render('AncFou', True, black)
    }
    ratio_memo = font.render('1mm : 1px', True, black)

    running = True
    real_width = 0
    real_height = 0

    with Pyro5.api.Proxy(uri) as proxy:
        proxy.start_connection(rover_id)
    
    while running:

        screen.fill((255, 255, 255))
        
        # Fetch rover data
        rover_name, rover_x, rover_y, rover_z, rover_t_tag = fetch_device_info(uri)

        # Convert x, y, z, and name to single values if they are lists
        if isinstance(rover_x, list):
            rover_x = rover_x[0] if rover_x else 0  # Use 0 if list is empty
        if isinstance(rover_y, list):
            rover_y = rover_y[0] if rover_y else 0  # Use 0 if list is empty
        if isinstance(rover_z, list):
            rover_z = rover_z[0] if rover_z else 0  # Use 0 if list is empty
        if isinstance(rover_name, list):
            rover_name = rover_name[0] if rover_name else "Unknown"

        # Ensure rover_x and rover_y are floats
        rover_x = float(rover_x) if isinstance(rover_x, (int, float)) else 0
        rover_y = float(rover_y) if isinstance(rover_y, (int, float)) else 0
        rover_z = float(rover_z) if isinstance(rover_z, (int, float)) else 0

        # Debugging: Check the types of rover_x, rover_y, real_width, and real_height
        print(f"Rover data: {rover_name}, X: {rover_x}, Y: {rover_y}, Width: {real_width}, Height: {real_height}")

        if rover_x is not None and rover_y is not None:
            #print_rover_info(rover_name, rover_x, rover_y, rover_z, rover_t_tag)
            # Convert and store rover position in pixels
            if isinstance(real_width, (int, float)) and isinstance(real_height, (int, float)) and real_width > 0 and real_height > 0:
                calc_x = int(((screen_width - (2 * padx)) * rover_x) / real_width)
                calc_y = int(((screen_height - (2 * pady)) * rover_y) / real_height)
                drawx = calc_x + padx
                drawy = screen_height - calc_y - pady
                rover_positions[rover_name] = (drawx, drawy)
        
        
        # Iterate through BLE device info
        for index, row in dm.device_info.iterrows():
            name = row['Name']
            if pd.notnull(row['X']) and pd.notnull(row['Y']):
                x = row['X']
                y = row['Y']
                if name == 'AncTwo' or name == 'AncThr':
                    real_width = y
                elif name == 'AncFou':
                    real_height = x

                if real_width > 1 and real_height > 1:
                    if name == 'AncOne':
                        anchor_positions[name] = anchor_list[0]
                    elif name == 'AncTwo':
                        anchor_positions[name] = anchor_list[1]
                    elif name == 'AncThr':
                        anchor_positions[name] = anchor_list[2]
                    elif name == 'AncFou':
                        anchor_positions[name] = anchor_list[3]
                        
        if len(rover_positions.values()) < 1:
            error_pos = (50, 150)
            error_message = font.render('! Error: No Rover detected', True, (255, 0, 0))
            screen.blit(error_message, error_pos)
        else:
            error_pos = (50, 150)
            error_message = font.render(f'Rover detected: {len(rover_positions.values())}', True, (255, 0, 0))
            screen.blit(error_message, error_pos)
            for position in rover_positions.values():
                centered_position = (position[0] - rover_sprite.get_width() // 2, position[1] - rover_sprite.get_height() // 2)
                screen.blit(rover_sprite, centered_position)

        # Draw lines between anchors
        # connected_anchors = [anchor for anchor in ['AncOne', 'AncTwo', 'AncThr', 'AncFou'] if anchor in anchor_positions]
        # for i in range(len(connected_anchors)):
        #     start_pos = anchor_positions[connected_anchors[i]]
        #     end_pos = anchor_positions[connected_anchors[(i + 1) % len(connected_anchors)]]
        #     pygame.draw.line(screen, (255, 0, 0), start_pos, end_pos, 3)

        # # Blit texts for anchors
        # text_offset = 5
        # for key, text_surface in text_surfaces.items():
        #     if key in anchor_positions:
        #         pos = (anchor_positions[key][0] + text_offset, anchor_positions[key][1] - text_offset)
        #         screen.blit(text_surface, pos)
        
        for name, position in rover_positions.items():
            centered_position = (position[0] - rover_sprite.get_width() // 2, position[1] - rover_sprite.get_height() // 2)
            screen.blit(rover_sprite, centered_position)
            
            coord_text = f"({int(rover_x)}, {int(rover_y)})"
            coord_surface = font.render(coord_text, True, black)
            coord_rect = coord_surface.get_rect()
            coord_rect.midtop = (position[0], position[1] - rover_sprite.get_height() // 2 - 20)
            screen.blit(coord_surface, coord_rect)
            
            # Render and display the name of the rover
            text_surface = font.render(name, True, black)
            text_rect = text_surface.get_rect()
            text_rect.midtop = (position[0], position[1] - 40 - rover_sprite.get_height() // 2)
            screen.blit(text_surface, text_rect)
        
        # Display the ratio memo at the bottom-right corner
        memo_pos = (screen_width - ratio_memo.get_width() - 10, screen_height - ratio_memo.get_height() - 10)
        screen.blit(ratio_memo, memo_pos)
        
        pygame.display.update()  # Adjust the delay as needed
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())
