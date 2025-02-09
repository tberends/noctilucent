
#%%
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
import numpy as np
import pickle

def plot_sounding():
    # Load the data from pickle file in the data folder
    with open('data/sounding.pkl', 'rb') as f:
        data = pickle.load(f)

    # Create lists to store the data
    time_list = []
    height_list = []
    temperature_list = []

    # Loop over each key in the data dictionary
    for key in data.keys():
        # Extract time from station information
        timestamp = data[key]['station_info']['Observation time']
        timestamp = datetime.strptime(timestamp, '%y%m%d/%H%M')

        # Extract the table data for the key
        df_table = data[key]['table']
        
        # Convert HGHT and TEMP to numeric, dropping any non-numeric values
        heights = pd.to_numeric(df_table['HGHT'], errors='coerce')
        temps = pd.to_numeric(df_table['TEMP'], errors='coerce')
        
        # Only append valid data points
        valid_mask = ~(heights.isna() | temps.isna())
        time_list.extend([timestamp] * sum(valid_mask))
        height_list.extend(heights[valid_mask])
        temperature_list.extend(temps[valid_mask])

    # Convert data to numpy arrays for gridding
    time_arr = np.array(time_list)
    height_arr = np.array(height_list)
    temp_arr = np.array(temperature_list)

    # Create regular grid
    unique_times = np.unique(time_arr)
    unique_heights = np.linspace(min(height_arr), max(height_arr), 100)
    temp_grid = np.zeros((len(unique_heights), len(unique_times)))

    # Interpolate data onto regular grid
    for i, t in enumerate(unique_times):
        mask = time_arr == t
        if np.any(mask):
            temp_grid[:, i] = np.interp(unique_heights, height_arr[mask], temp_arr[mask])

    # Plot using pcolormesh
    plt.figure(figsize=(20, 10))
    plt.pcolormesh(unique_times, unique_heights, temp_grid, cmap='coolwarm', shading='auto')
    plt.colorbar(label='Temperature (°C)')
    plt.xlabel('Time')
    plt.ylabel('Height (m)')
    plt.title('Temperature Profile')
    plt.grid(True)

    # Add contour lines
    contour = plt.contour(unique_times, unique_heights, temp_grid, colors='black', linewidths=0.5)
    plt.clabel(contour, inline=True, fontsize=8, fmt='%1.0f')

    # Save the plot to a file in folder visualizations
    plt.savefig('app/visualizations/sounding_plot.png')

if __name__ == '__main__':
    plot_sounding()
