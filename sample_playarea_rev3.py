'''
rev 01 - Raw movement
rev 02 - Scaled movement
rev 03 - Target by mouse click
'''

import pygame
import sys
import os
import time

import numpy as np

from nn_infer import ONNXModel

# Initialize Pygame
pygame.init()

# Set up the display
width, height = 1500, 750
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption("Rover and Target")

#Load AI model
model_folder = 'nn_models'
model_path = r"C:\G7\rover\Rover_02_01.onnx"
model = ONNXModel(os.path.join(model_folder, model_path))

# Colors
white = (255, 255, 255)
black = (0, 0, 0)
red = (255, 0, 0)
radius = 10

# Fonts
font = pygame.font.Font(None, 36)

# Circle positions
rover_pos = [100, 175 ] # Centered on left side
target_pos = [1300, 205]  # Centered on right side
rover_moveSpeed = 0.5

#Scale position per training param
target_x_scale = (target_pos[0] * 90 / width) - 45
target_y_scale = (target_pos[1] * 90 / height) - 45
transform_x_scale = (rover_pos[0] * 90 / width) - 45
transform_y_scale = (rover_pos[1] * 90 / height) - 45

#Init model input
target_position = np.array([target_x_scale, 0.03, target_y_scale]).astype(np.float32)
transform_position = np.array([transform_x_scale, 0.03, transform_y_scale]).astype(np.float32)
transform_vel = np.array([0.0, 0.0]).astype(np.float32)
boundary_min = np.array([-45, 0.0, -45]).astype(np.float32)
boundary_max = np.array([45, 0.0, 45]).astype(np.float32)

# Measure inference time
start_time = time.time()

# Main loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # Check for mouse click
        if event.type == pygame.MOUSEBUTTONDOWN:
            target_pos = event.pos  # Store the position where the mouse was clicked
            target_x_scale = (target_pos[0] * 90 / width) - 45
            target_y_scale = (target_pos[1] * 90 / height) - 45
            target_position = np.array([target_x_scale, 0.03, target_y_scale]).astype(np.float32)

    # Update the Rover's position
    input_array = np.concatenate((target_position, transform_position, transform_vel, boundary_min, boundary_max))
    # Transform to 2D array
    input_array = np.array([input_array])
    print("Input array:", input_array)
    # Perform inference
    output = model.infer(input_array)
    #print("Output: ", model.model.graph.output)
    #print("Inference result:", output)
    cont_actions = output[4][0]
    cont_actions = cont_actions * rover_moveSpeed
    print("Actions:", cont_actions)
 
    transform_position[0] += cont_actions[0]
    transform_position[2] += cont_actions[1]

    rover_pos[0] = ((transform_position[0] + 45) * width / 90)
    rover_pos[1] = ((transform_position[2] + 45) * height / 90)

    end_time = time.time()

    inference_time = end_time - start_time
    start_time = end_time
    transform_vel[0] = abs(cont_actions[0] / inference_time)
    transform_vel[1] = abs(cont_actions[1] / inference_time)

    # Fill the screen with white
    screen.fill(white)

    # Draw the "Rover" circle
    pygame.draw.circle(screen, black, rover_pos, radius)
    rover_label = font.render("Rover", True, black)
    rover_coords = font.render(f"({rover_pos[0]}, {rover_pos[1]})", True, black)
    screen.blit(rover_label, (rover_pos[0] - rover_label.get_width() // 2, rover_pos[1] - 35))
    screen.blit(rover_coords, (rover_pos[0] - rover_coords.get_width() // 2, rover_pos[1] + 20))

    # Draw the "Target" circle
    pygame.draw.circle(screen, red, target_pos, radius)
    target_label = font.render("Target", True, black)
    target_coords = font.render(f"({target_pos[0]}, {target_pos[1]})", True, black)
    screen.blit(target_label, (target_pos[0] - target_label.get_width() // 2, target_pos[1] - 35))
    screen.blit(target_coords, (target_pos[0] - target_coords.get_width() // 2, target_pos[1] + 20))

    # Update the display
    pygame.display.flip()

    # Control the frame rate
    pygame.time.delay(10)

# Clean up
pygame.quit()
sys.exit()
