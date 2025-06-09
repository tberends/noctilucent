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

def create_wind_grid(time_arr, height_arr, wind_dir, wind_speed):
    """Creëer grids voor windrichting en windsnelheid"""
    unique_times = np.unique(time_arr)
    unique_heights = np.linspace(min(height_arr), max(height_arr), 100)
    
    wind_dir_grid = np.zeros((len(unique_heights), len(unique_times)))
    wind_speed_grid = np.zeros((len(unique_heights), len(unique_times)))
    
    for i, t in enumerate(unique_times):
        mask = time_arr == t
        if np.any(mask):
            wind_dir_grid[:, i] = np.interp(unique_heights, height_arr[mask], wind_dir[mask])
            wind_speed_grid[:, i] = np.interp(unique_heights, height_arr[mask], wind_speed[mask])
    
    return unique_times, unique_heights, wind_dir_grid, wind_speed_grid

def create_humidity_grid(time_arr, height_arr, rel_humidity, mix_ratio):
    """Creëer grids voor vochtigheidsparameters"""
    unique_times = np.unique(time_arr)
    unique_heights = np.linspace(min(height_arr), max(height_arr), 100)
    
    rel_hum_grid = np.zeros((len(unique_heights), len(unique_times)))
    mix_ratio_grid = np.zeros((len(unique_heights), len(unique_times)))
    
    for i, t in enumerate(unique_times):
        mask = time_arr == t
        if np.any(mask):
            rel_hum_grid[:, i] = np.interp(unique_heights, height_arr[mask], rel_humidity[mask])
            mix_ratio_grid[:, i] = np.interp(unique_heights, height_arr[mask], mix_ratio[mask])
    
    return unique_times, unique_heights, rel_hum_grid, mix_ratio_grid

def plot_sounding():
    # Load the data from pickle file in the data folder
    with open('data/sounding.pkl', 'rb') as f:
        data = pickle.load(f)

    # Create lists to store all data
    time_list = []
    height_list = []
    temperature_list = []
    wind_dir_list = []
    wind_speed_list = []
    rel_humidity_list = []
    mix_ratio_list = []
    pot_temp_list = []
    
    # Lists for stability indices (één waarde per tijdstap)
    stability_times = []
    cape_values = []
    lifted_index_values = []
    k_index_values = []

    # Loop over each key in the data dictionary
    for key in data.keys():
        # Extract time from station information
        timestamp = data[key]['station_info']['Observation time']
        timestamp = datetime.strptime(timestamp, '%y%m%d/%H%M')

        # Extract the table data for the key
        df_table = data[key]['table']
        
        # Convert all relevant columns to numeric
        heights = pd.to_numeric(df_table['HGHT'], errors='coerce')
        temps = pd.to_numeric(df_table['TEMP'], errors='coerce')
        wind_dir = pd.to_numeric(df_table['DRCT'], errors='coerce')
        wind_speed = pd.to_numeric(df_table['SKNT'], errors='coerce')
        rel_humidity = pd.to_numeric(df_table['RELH'], errors='coerce')
        mix_ratio = pd.to_numeric(df_table['MIXR'], errors='coerce')
        pot_temp = pd.to_numeric(df_table['THTA'], errors='coerce')
        
        # Only append valid data points
        valid_mask = ~(heights.isna() | temps.isna())
        valid_count = sum(valid_mask)
        
        if valid_count > 0:
            time_list.extend([timestamp] * valid_count)
            height_list.extend(heights[valid_mask])
            temperature_list.extend(temps[valid_mask])
            
            # Voeg winddata toe (met fallback voor missende waarden)
            wind_dir_valid = wind_dir[valid_mask].fillna(0)
            wind_speed_valid = wind_speed[valid_mask].fillna(0)
            wind_dir_list.extend(wind_dir_valid)
            wind_speed_list.extend(wind_speed_valid)
            
            # Voeg vochtigheidsdata toe
            rel_hum_valid = rel_humidity[valid_mask].fillna(0)
            mix_ratio_valid = mix_ratio[valid_mask].fillna(0)
            rel_humidity_list.extend(rel_hum_valid)
            mix_ratio_list.extend(mix_ratio_valid)
            
            # Voeg potentiële temperatuur toe
            pot_temp_valid = pot_temp[valid_mask].fillna(temps[valid_mask])
            pot_temp_list.extend(pot_temp_valid)
        
        # Extract stability indices (één per tijdstap)
        try:
            cape = float(data[key]['station_info'].get('Convective Available Potential Energy', 0))
            lifted_idx = float(data[key]['station_info'].get('Lifted index', 0))
            k_idx = float(data[key]['station_info'].get('K index', 0))
            
            stability_times.append(timestamp)
            cape_values.append(cape)
            lifted_index_values.append(lifted_idx)
            k_index_values.append(k_idx)
        except (ValueError, TypeError):
            pass

    # Convert data to numpy arrays
    time_arr = np.array(time_list)
    height_arr = np.array(height_list)
    temp_arr = np.array(temperature_list)
    wind_dir_arr = np.array(wind_dir_list)
    wind_speed_arr = np.array(wind_speed_list)
    rel_hum_arr = np.array(rel_humidity_list)
    mix_ratio_arr = np.array(mix_ratio_list)
    pot_temp_arr = np.array(pot_temp_list)

    # Create regular grid voor temperatuur
    unique_times = np.unique(time_arr)
    unique_heights = np.linspace(min(height_arr), max(height_arr), 100)
    temp_grid = np.zeros((len(unique_heights), len(unique_times)))

    # Interpolate temperature data onto regular grid
    for i, t in enumerate(unique_times):
        mask = time_arr == t
        if np.any(mask):
            temp_grid[:, i] = np.interp(unique_heights, height_arr[mask], temp_arr[mask])

    # Bereken tropopauze hoogte voor elke tijdstap
    tropopause_heights = []
    tropopause_times = []
    
    for i, t in enumerate(unique_times):
        mask = time_arr == t
        if np.sum(mask) > 10:
            heights_at_t = height_arr[mask]
            temps_at_t = temp_arr[mask]
            tropopause = find_tropopause(heights_at_t, temps_at_t)
            if tropopause is not None:
                tropopause_heights.append(tropopause)
                tropopause_times.append(t)

    # Create wind grids
    _, _, wind_dir_grid, wind_speed_grid = create_wind_grid(time_arr, height_arr, wind_dir_arr, wind_speed_arr)
    
    # Create humidity grids
    _, _, rel_hum_grid, mix_ratio_grid = create_humidity_grid(time_arr, height_arr, rel_hum_arr, mix_ratio_arr)
    
    # Create potential temperature grid
    pot_temp_grid = np.zeros((len(unique_heights), len(unique_times)))
    for i, t in enumerate(unique_times):
        mask = time_arr == t
        if np.any(mask):
            pot_temp_grid[:, i] = np.interp(unique_heights, height_arr[mask], pot_temp_arr[mask])

    # Create subplots with multiple rows
    fig = make_subplots(
        rows=8, cols=1,
        subplot_titles=['Temperatuurprofiel met Tropopauze', 'Windsnelheid',
                       'Windrichting', 'Relatieve Vochtigheid (%)',
                       'Mengverhouding (g/kg)', 'Potentiële Temperatuur (K)',
                       'K-Index (Stabiliteitsindex)', 'CAPE en Lifted Index'],
        specs=[[{"secondary_y": False}],
               [{"secondary_y": False}],
               [{"secondary_y": False}],
               [{"secondary_y": False}],
               [{"secondary_y": False}],
               [{"secondary_y": False}],
               [{"secondary_y": False}],
               [{"secondary_y": True}]],
        vertical_spacing=0.04,
        shared_xaxes=True,
        row_heights=[0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.08, 0.08]  # Laatste twee plots kleiner
    )

    # 1. Temperatuurprofiel met tropopauze (originele plot)
    fig.add_trace(
        go.Heatmap(
            x=unique_times,
            y=unique_heights,
            z=temp_grid,
            colorscale='thermal',
            colorbar=dict(title='°C', x=1.01, len=0.14, y=0.93),
            showscale=True
        ),
        row=1, col=1
    )

    if tropopause_heights and tropopause_times:
        fig.add_trace(
            go.Scatter(
                x=tropopause_times,
                y=tropopause_heights,
                mode='lines',
                line=dict(color='#FF0000', width=2, dash='dash'),
                name='Tropopauze',
                showlegend=True
            ),
            row=1, col=1
        )

    # 2. Windsnelheid
    fig.add_trace(
        go.Heatmap(
            x=unique_times,
            y=unique_heights,
            z=wind_speed_grid,
            colorscale='Viridis',
            colorbar=dict(title='knots', x=1.01, len=0.14, y=0.79),
            showscale=True
        ),
        row=2, col=1
    )

    # 3. Windrichting
    fig.add_trace(
        go.Heatmap(
            x=unique_times,
            y=unique_heights,
            z=wind_dir_grid,
            colorscale='HSV',
            colorbar=dict(title='graden', x=1.01, len=0.14, y=0.65),
            showscale=True
        ),
        row=3, col=1
    )

    # 4. Relatieve vochtigheid
    fig.add_trace(
        go.Heatmap(
            x=unique_times,
            y=unique_heights,
            z=rel_hum_grid,
            colorscale='Blues',
            colorbar=dict(title='%', x=1.01, len=0.14, y=0.51),
            showscale=True
        ),
        row=4, col=1
    )

    # 5. Mengverhouding
    fig.add_trace(
        go.Heatmap(
            x=unique_times,
            y=unique_heights,
            z=mix_ratio_grid,
            colorscale='YlGnBu',
            colorbar=dict(title='g/kg', x=1.01, len=0.14, y=0.37),
            showscale=True
        ),
        row=5, col=1
    )

    # 6. Potentiële temperatuur
    fig.add_trace(
        go.Heatmap(
            x=unique_times,
            y=unique_heights,
            z=pot_temp_grid,
            colorscale='plasma',
            colorbar=dict(title='K', x=1.01, len=0.14, y=0.23),
            showscale=True
        ),
        row=6, col=1
    )

    # 7. K-Index tijdserie (stabiliteitsindex)
    if stability_times and k_index_values:
        fig.add_trace(
            go.Scatter(
                x=stability_times,
                y=k_index_values,
                mode='lines+markers',
                line=dict(color='orange', width=2),
                marker=dict(size=4),
                name='K-Index',
                showlegend=True
            ),
            row=7, col=1
        )

    # 8. CAPE en Lifted Index
    if stability_times and cape_values:
        fig.add_trace(
            go.Scatter(
                x=stability_times,
                y=cape_values,
                mode='lines+markers',
                line=dict(color='red', width=2),
                marker=dict(size=4),
                name='CAPE',
                showlegend=True
            ),
            row=8, col=1
        )

    if stability_times and lifted_index_values:
        fig.add_trace(
            go.Scatter(
                x=stability_times,
                y=lifted_index_values,
                mode='lines+markers',
                line=dict(color='blue', width=2),
                marker=dict(size=4),
                name='Lifted Index',
                yaxis='y2',
                showlegend=True
            ),
            row=8, col=1, secondary_y=True
        )

    # Update layout voor alle subplots
    first_key = list(data.keys())[0]
    station_number = data[first_key]['station_info']['Station number']
    
    # Bepaal de laatste werkelijke datum en vandaag
    today = datetime.now()
    last_measurement = max(unique_times) if len(unique_times) > 0 else today
    
    # Gebruik de vroegste van vandaag of laatste meting als eindpunt
    end_date = min(today, last_measurement)
    
    fig.update_layout(
        title=dict(
            text=f'Uitgebreide Atmosferische Analyse - Station {station_number}',
            font=dict(size=20, weight='bold'),
            x=0.5
        ),
        height=2200,  # Aangepaste hoogte
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.8)"
        ),
        margin=dict(r=120),  # Extra ruimte voor colorbars
        xaxis=dict(range=[min(unique_times), end_date])  # Beperk x-as tot vandaag
    )

    # Update x-axes - voeg range selector toe aan de bovenste plot
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=7, label="7d", step="day", stepmode="backward"),
                dict(count=1, label="1m", step="month", stepmode="backward"),
                dict(count=3, label="3m", step="month", stepmode="backward"),
                dict(label="Alles", step="all")
            ]),
            yanchor="top",
            y=1.02,
            xanchor="left",
            x=0.01
        ),
        type="date",
        range=[min(unique_times), end_date],  # Beperk ook hier de range
        row=1, col=1
    )

    # Voeg alleen datum label toe aan onderste plot
    fig.update_xaxes(title_text='Datum', row=8, col=1)

    # Update y-axes labels voor hoogte plots (eerste 6 rijen)
    for row in range(1, 7):
        fig.update_yaxes(title_text='Hoogte (m)', row=row, col=1)

    # Y-axis labels voor stabiliteitsindices
    fig.update_yaxes(title_text='K-Index', row=7, col=1)
    fig.update_yaxes(title_text='CAPE (J/kg)', row=8, col=1)
    fig.update_yaxes(title_text='Lifted Index', row=8, col=1, secondary_y=True)

    # Save the plot to a file in folder visualizations
    fig.write_html('app/visualizations/sounding_plot.html')

if __name__ == '__main__':
    plot_sounding()