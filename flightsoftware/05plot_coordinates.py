import pygame
import pandas as pd
import numpy as np

# Load your data
df = pd.read_csv('movement.csv')

# Assuming you've initialized Pygame screen
screen_width = 800
screen_height = 600
pygame.init()
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption('Pygame Plot')

# Example scaling factor
scale_factor = 10

# Example loop to draw points
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((255, 255, 255))  # Clear screen

    # Example drawing xr and yr values
    for index, row in df.iterrows():
        # Check for NaN values
        if np.isnan(row['xr']) or np.isnan(row['yr']):
            continue  # Skip this iteration if NaN
        
        # Scale and convert to screen coordinates
        screen_x = int(row['xr'] / scale_factor)
        screen_y = int(row['yr'] / scale_factor)
        
        # Draw a point (adjust as needed for your visualization)
        pygame.draw.circle(screen, (255, 0, 0), (screen_x, screen_y), 3)
    
    pygame.display.flip()

pygame.quit()