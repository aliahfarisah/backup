import argparse
import pandas as pd
import numpy as np
import HiwonderSDK.mecanum as mecanum
import HiwonderSDK.Board as Board
import time
import datetime

#######################################################################

def read_csv_and_loop_by_row(file_path):
    # Read the CSV file into a DataFrame
    df = pd.read_csv(file_path)

    #print(df)
    return df

#######################################################################

def calculate_angles(df):
    # Calculate the differences between consecutive points
    df['dX'] = df['x [m]'].diff()
    df['dY'] = df['y [m]'].diff()
    df['dTime'] = df['Time [msec]'].diff() / 1000  # Convert time difference from milliseconds to seconds
   
    # Calculate the angles using atan2 (in radians)
    df['Angle (rad)'] = np.arctan2(df['dY'], df['dX'])
   
    # Convert angles to degrees for easier interpretation (optional)
    df['Angle (deg)'] = np.degrees(df['Angle (rad)'])

    # Calculate the distance between points
    df['Distance (m)'] = np.sqrt(df['dX']**2 + df['dY']**2)
   
    return df

#######################################################################

def execute_movement():
    print(f"Executing movement for Rover {id_rover}")
    # Example usage:
    file_path = 'Drone 2 (1).csv'
    df = read_csv_and_loop_by_row(file_path)

    # Apply the function to calculate angles
    df = calculate_angles(df)
    #print(df)

    chassis = mecanum.MecanumChassis()
    for index, row in df.iterrows():
        #print(f"Index: {index}")
        if index == 0:
            pass
        else:
            chassis.set_velocity(50, row['Angle (deg)'], 0)  # Adjust velocity parameters as needed
            Board.RGB.setPixelColor(0, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
            Board.RGB.setPixelColor(1, Board.PixelColor(int(row['Red']), int(row['Green']), int(row['Blue'])))
            Board.RGB.show()
            time.sleep(0.25)

    # Close RGB show by turning off the LEDs
    Board.RGB.setPixelColor(0, Board.PixelColor(0, 0, 0))  # Set pixel color to black
    Board.RGB.setPixelColor(1, Board.PixelColor(0, 0, 0))  # Set pixel color to black
    Board.RGB.show()

    chassis.set_velocity(0, 0, 0)
   
def should_move_now(t_execute):
    t_current_rover = datetime.datetime.now().time()
    print(f"t_current_rover {id_rover} = {t_current_rover}")
    return t_current_rover >= t_execute
   

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute robot movement based on data from CSV after a delay.")
    parser.add_argument("--id_rover", type=int, help="ID of the Rover for which movement is executed")    
    parser.add_argument("--hour", type=int, help="Delay in seconds before starting the movement.")
    parser.add_argument("--minute", type=int, help="Delay in seconds before starting the movement.")
    parser.add_argument("--second", type=int, help="Delay in seconds before starting the movement.")

    args = parser.parse_args()
   
    id_rover = args.id_rover
    t_execute = datetime.time(args.hour,args.minute,args.second)

    print(f"t_execute rover {id_rover} = {t_execute}")
   
    try:
        while True:
            if should_move_now(t_execute):
                execute_movement()
                break
            else:
                pass
            time.sleep(0.05)
           
    except KeyboardInterrupt:
        print("Keyboard Interrupt")
   
