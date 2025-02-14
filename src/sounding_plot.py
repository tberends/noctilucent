import pandas as pd
import numpy as np
import pickle
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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

    # Create the interactive plot
    fig = make_subplots(rows=1, cols=1)

    # Add heatmap
    heatmap = go.Heatmap(
        x=unique_times,
        y=unique_heights,
        z=temp_grid,
        colorscale='thermal',
        colorbar=dict(title='Temperatuur (°C)')
    )
    fig.add_trace(heatmap)

    # # Add contour lines
    # contour = go.Contour(
    #     x=unique_times,
    #     y=unique_heights,
    #     z=temp_grid,
    #     line_width=1.5,
    #     showscale=False,
    #     contours=dict(
    #         coloring='lines'
    #     ),
    #     colorscale='gray',
    #     opacity=0.5
    # )
    # fig.add_trace(contour)

    # Update layout
    # Get station number from the first entry in data
    first_key = list(data.keys())[0]
    station_number = data[first_key]['station_info']['Station number']
    
    fig.update_layout(
        title=dict(
            text=f'Temparatuurprofiel - Station {station_number}',
            font=dict(size=24, weight='bold')
        ),
        xaxis_title=dict(text='Datum', font=dict(size=18, weight='bold')),
        yaxis_title=dict(text='Hoogte (m)', font=dict(size=18, weight='bold')),
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=7, label="Afgelopen week", step="day", stepmode="backward"),
                    dict(count=1, label="Afgelopen maand", step="month", stepmode="backward"),
                    dict(count=3, label="Afgelopen 3 maand", step="month", stepmode="backward"),
                    dict(count=1, label="Huidige jaar", step="year", stepmode="todate"),
                    dict(count=1, label="Afgelopen jaar", step="year", stepmode="backward"),
                    dict(label="Alle data", step="all")
                ])
            ),
            rangeslider=dict(visible=True),
            type="date",
            tickfont=dict(size=14)
        ),
        yaxis=dict(tickfont=dict(size=14))
    )

    # Save the plot to a file in folder visualizations
    fig.write_html('app/visualizations/sounding_plot.html')

if __name__ == '__main__':
    plot_sounding()