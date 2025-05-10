import pandas as pd
import numpy as np
import pickle
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def find_tropopause(heights, temps):
    """
    Bepaalt de hoogte van de tropopauze volgens WMO-definitie:
    - Het laagste niveau waar de temperatuurgradiënt kleiner wordt dan -2°C/km
    - De gemiddelde gradiënt tussen dit niveau en alle hogere niveaus binnen 2 km
      is niet kleiner dan -2°C/km
    """
    if len(heights) < 2 or len(temps) < 2:
        return None
    
    # Sorteer de data op hoogte (voor het geval dat)
    sort_idx = np.argsort(heights)
    heights = heights[sort_idx]
    temps = temps[sort_idx]
    
    # Bereken temperatuurgradiënt in °C/km
    gradients = np.zeros(len(heights)-1)
    for i in range(len(heights)-1):
        height_diff = (heights[i+1] - heights[i]) / 1000.0  # conversie naar km
        if height_diff > 0:  # voorkom delen door nul
            gradients[i] = (temps[i+1] - temps[i]) / height_diff
    
    # Zoek het laagste niveau waar de gradiënt boven -2°C/km komt
    for i in range(len(gradients)):
        if heights[i] > 5000 and gradients[i] > -2.0:  # Begin zoeken boven 5 km
            # Controleer of de gemiddelde gradiënt in de volgende 2 km ook boven -2°C/km blijft
            next_levels = [j for j in range(i+1, len(heights)) if heights[j] < heights[i] + 2000]
            
            if len(next_levels) > 0:
                mean_gradient = np.mean([gradients[j] for j in range(i, min(i+len(next_levels), len(gradients)))])
                if mean_gradient > -2.0:
                    return heights[i]
    
    return None

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

    # Bereken tropopauze hoogte voor elke tijdstap
    tropopause_heights = []
    tropopause_times = []
    
    for i, t in enumerate(unique_times):
        mask = time_arr == t
        if np.sum(mask) > 10:  # Zorg ervoor dat er voldoende datapunten zijn
            heights_at_t = height_arr[mask]
            temps_at_t = temp_arr[mask]
            tropopause = find_tropopause(heights_at_t, temps_at_t)
            if tropopause is not None:
                tropopause_heights.append(tropopause)
                tropopause_times.append(t)

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

    # Voeg tropopauze toe als rode gestippelde lijn
    if tropopause_heights and tropopause_times:
        tropopause_line = go.Scatter(
            x=tropopause_times,
            y=tropopause_heights,
            mode='lines',
            line=dict(color='#FF0000', width=2, dash='dash'),
            name='Tropopauze (grens tussen troposfeer en stratosfeer)'
        )
        fig.add_trace(tropopause_line)

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
        yaxis=dict(tickfont=dict(size=14)),
        legend=dict(font=dict(size=14))
    )

    # Save the plot to a file in folder visualizations
    fig.write_html('app/visualizations/sounding_plot.html')

if __name__ == '__main__':
    plot_sounding()