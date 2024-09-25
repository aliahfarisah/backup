import serial
import pynmea2
import pygame
from filterpy.kalman import KalmanFilter

def get_gps_data():
    port = "/dev/ttyAMA0"
    ser = serial.Serial(port, baudrate=9600, timeout=0.5)
    dataout = pynmea2.NMEAStreamReader()

    while True:
        newdata = ser.readline().decode('ascii', errors='replace')
        
        if newdata.startswith("$GPRMC"):
            try:
                newmsg = pynmea2.parse(newdata)
                lat = newmsg.latitude
                lng = newmsg.longitude
                gps_data = {"latitude": lat, "longitude": lng}
                return gps_data
            except pynmea2.ParseError:
                print("Failed to parse GPS data.")
                continue

def lat_lon_to_pixel(lat, lon, width, height, min_lat, max_lat, min_lon, max_lon, zoom_factor):
    x_pixel = int(((lon - min_lon) / (max_lon - min_lon)) * width * zoom_factor)
    y_pixel = int(((max_lat - lat) / (max_lat - min_lat)) * height * zoom_factor)  # Inverted for Pygame
    return x_pixel, y_pixel

# Initialize Kalman Filter
def setup_kalman_filter():
    kf = KalmanFilter(dim_x=4, dim_z=2)
    kf.x = [0, 0, 0, 0]  # Initial state (x position, y position, x velocity, y velocity)
    kf.P *= 1000.  # Initial uncertainty
    kf.F = [[1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1]]  # State transition matrix
    kf.H = [[1, 0, 0, 0],
            [0, 1, 0, 0]]  # Measurement function
    kf.R = [[10, 0],
            [0, 10]]  # Measurement uncertainty
    kf.Q = [[1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]]  # Process uncertainty
    return kf

def apply_kalman_filter(kf, lat, lon):
    # Predict
    kf.predict()
    # Update
    kf.update([lat, lon])
    return kf.x[0], kf.x[1]

# Pygame setup
pygame.init()
screen = pygame.display.set_mode((1500, 700))
pygame.font.init()  # Initialize Pygame font module

# Define bounding box around your data
min_lat = 2.1490
max_lat = 2.1500
min_lon = 102.3665
max_lon = 102.3675

# Start with a moderate zoom factor and adjust as needed
zoom_factor = 5000

# Set up font
font = pygame.font.SysFont(None, 36)

# Set up Kalman Filter
kf = setup_kalman_filter()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Get GPS coordinates 
    gps_data = get_gps_data()
    lat = gps_data['latitude']
    lon = gps_data['longitude']
    
    print(f"Latitude: {lat}, Longitude: {lon}")  # For debugging
    x, y = lat_lon_to_pixel(lat, lon, 1500, 700, min_lat, max_lat, min_lon, max_lon, zoom_factor)
    
    # Apply Kalman Filter to get filtered coordinates
    kalman_lat, kalman_lon = apply_kalman_filter(kf, lat, lon)
    x_kf, y_kf = lat_lon_to_pixel(kalman_lat, kalman_lon, 1500, 700, min_lat, max_lat, min_lon, max_lon, zoom_factor)
    
    if x is not None and y is not None:  # Check if the values are valid
        # Clamp the coordinates to be within the screen bounds
        x = min(max(x, 0), 1500)
        y = min(max(y, 0), 700)
        x_kf = min(max(x_kf, 0), 1500)
        y_kf = min(max(y_kf, 0), 700)

        # Draw rover position
        screen.fill((255, 255, 255))  # Clear screen (white background)
        pygame.draw.circle(screen, (255, 0, 0), (x, y), 10)  # Draw red circle for the raw position
        pygame.draw.circle(screen, (0, 0, 255), (x_kf, y_kf), 10)  # Draw blue circle for the filtered position

        # Render coordinates text
        lat_text = font.render(f'Latitude: {lat}', True, (0, 0, 0))
        lon_text = font.render(f'Longitude: {lon}', True, (0, 0, 0))
        kalman_lat_text = font.render(f'Filtered Lat: {kalman_lat}', True, (0, 0, 0))
        kalman_lon_text = font.render(f'Filtered Lon: {kalman_lonvrrru}', True, (0, 0, 0))
        
        # Display the text on the screen
        screen.blit(lat_text, (10, 10))  # Display latitude text
        screen.blit(lon_text, (10, 50))  # Display longitude text
        screen.blit(kalman_lat_text, (10, 90))  # Display filtered latitude text
        screen.blit(kalman_lon_text, (10, 130))  # Display filtered longitude text
    else:
        print("Skipping drawing due to out-of-bounds coordinates.")

    pygame.display.flip()

pygame.quit()
