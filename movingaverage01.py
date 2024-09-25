import pandas as pd
import numpy as np

# Load your CSV file
df = pd.read_csv('device_info.csv')

# Define the bounds
x_min, x_max = 0, 1.5
y_min, y_max = 0, 0.75

# Filter the data based on the bounds by replacing out-of-bounds values with NaN
df['x_valid'] = np.where((df['X'] > x_min) & (df['X'] < x_max), df['X'], np.nan)
df['y_valid'] = np.where((df['Y'] > y_min) & (df['Y'] < y_max), df['Y'], np.nan)

# Count valid values in the rolling window and calculate the sum
x_count = df['x_valid'].rolling(window=10, min_periods=1).count()
y_count = df['y_valid'].rolling(window=10, min_periods=1).count()

x_sum = df['x_valid'].rolling(window=10, min_periods=1).sum()
y_sum = df['y_valid'].rolling(window=10, min_periods=1).sum()

# Calculate the moving average considering only valid values
df['avg_x'] = x_sum / x_count
df['avg_y'] = y_sum / y_count

# Select only the columns you want to save
df_moving_avg = df[['X', 'Y', 'avg_x', 'avg_y']]

# Save the result to a new CSV file
df_moving_avg.to_csv('filtered_moving_average1.csv', index=False)

print(df_moving_avg)
