import pandas as pd

# Load your CSV file
df = pd.read_csv('device_info.csv')

# Define the bounds
x_min, x_max = 0, 1.5
y_min, y_max = 0, 0.75

# Filter out rows where x or y is out of bounds
df_filtered = df[(df['X'] > x_min) & (df['X'] < x_max) & 
                 (df['Y'] > y_min) & (df['Y'] < y_max)]

# Calculate moving average with a window of 10
window_size = 10
moving_averages = []

for i in range(len(df_filtered) - window_size + 1):
    window = df_filtered.iloc[i:i + window_size]
    valid_count = len(window)
    
    # Calculate the average for x and y only with valid values
    avg_x = window['X'].sum() / valid_count
    avg_y = window['Y'].sum() / valid_count
    
    moving_averages.append((avg_x, avg_y))

# Convert to DataFrame for further use or save to CSV
df_moving_avg = pd.DataFrame(moving_averages, columns=['avg_x', 'avg_y'])

df_moving_avg['X'] = df_filtered['X'].iloc[window_size - 1:].values
df_moving_avg['Y'] = df_filtered['Y'].iloc[window_size - 1:].values

# Save to CSV if needed
df_moving_avg.to_csv('filtered_moving_average.csv', index=False)
