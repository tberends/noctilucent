import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.sounding_store import load_profiles, load_station

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

def _interp_profile(heights, values, unique_heights):
    """Interpolate one sounding. Heights are sorted so a folded profile still plots."""
    order = np.argsort(heights, kind="mergesort")
    xp = heights[order]
    fp = values[order]
    unique_xp, unique_index = np.unique(xp, return_index=True)
    if len(unique_xp) < 2:
        return np.full(len(unique_heights), np.nan)
    return np.interp(unique_heights, unique_xp, fp[unique_index])


def create_wind_grid(time_arr, height_arr, wind_dir, wind_speed):
    """Creëer grids voor windrichting en windsnelheid"""
    unique_times = np.unique(time_arr)
    unique_heights = np.linspace(min(height_arr), max(height_arr), 100)
    
    wind_dir_grid = np.zeros((len(unique_heights), len(unique_times)))
    wind_speed_grid = np.zeros((len(unique_heights), len(unique_times)))
    
    for i, t in enumerate(unique_times):
        mask = time_arr == t
        if np.any(mask):
            wind_dir_grid[:, i] = _interp_profile(height_arr[mask], wind_dir[mask], unique_heights)
            wind_speed_grid[:, i] = _interp_profile(height_arr[mask], wind_speed[mask], unique_heights)
    
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
            rel_hum_grid[:, i] = _interp_profile(height_arr[mask], rel_humidity[mask], unique_heights)
            mix_ratio_grid[:, i] = _interp_profile(height_arr[mask], mix_ratio[mask], unique_heights)
    
    return unique_times, unique_heights, rel_hum_grid, mix_ratio_grid

def _index_series(station, column):
    """Times and values for one index. Missing values stay out of the series."""
    if column not in station.columns:
        return np.array([], dtype="datetime64[ns]"), np.array([], dtype=float)
    values = pd.to_numeric(station[column], errors="coerce")
    mask = values.notna().to_numpy()
    times = station.loc[mask, "time"].to_numpy(dtype="datetime64[ns]")
    return times, values.to_numpy(dtype=float)[mask]


def plot_sounding():
    profiles = load_profiles()
    station = load_station()
    if profiles.empty:
        raise FileNotFoundError("Geen profieldata in data/profiles.parquet")

    valid = profiles["HGHT"].notna() & profiles["TEMP"].notna()
    frame = profiles.loc[valid]
    time_arr = frame["time"].to_numpy(dtype="datetime64[ns]")
    height_arr = frame["HGHT"].to_numpy(dtype=float)
    temp_arr = frame["TEMP"].to_numpy(dtype=float)
    wind_dir_arr = frame["DRCT"].fillna(0).to_numpy(dtype=float)
    wind_speed_arr = frame["SKNT"].fillna(0).to_numpy(dtype=float)
    rel_hum_arr = frame["RELH"].fillna(0).to_numpy(dtype=float)
    mix_ratio_arr = frame["MIXR"].fillna(0).to_numpy(dtype=float)
    pot_temp_arr = frame["THTA"].fillna(frame["TEMP"]).to_numpy(dtype=float)

    k_times, k_index_values = _index_series(station, "K index")
    cape_times, cape_values = _index_series(station, "Convective Available Potential Energy")
    mucape_times, mucape_values = _index_series(station, "Most Unstable CAPE")
    lifted_times, lifted_index_values = _index_series(station, "Lifted index")
    virtual_times, virtual_lifted_values = _index_series(station, "Virtual Lifted Index")

    # Create regular grid voor temperatuur
    unique_times = np.unique(time_arr)
    unique_heights = np.linspace(min(height_arr), max(height_arr), 100)
    temp_grid = np.zeros((len(unique_heights), len(unique_times)))

    # Interpolate temperature data onto regular grid
    for i, t in enumerate(unique_times):
        mask = time_arr == t
        if np.any(mask):
            temp_grid[:, i] = _interp_profile(height_arr[mask], temp_arr[mask], unique_heights)

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
            pot_temp_grid[:, i] = _interp_profile(height_arr[mask], pot_temp_arr[mask], unique_heights)

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

    # 7. K-Index. Historical and new FM35 values share this definition.
    if len(k_times):
        fig.add_trace(
            go.Scatter(
                x=k_times,
                y=k_index_values,
                mode='lines',
                line=dict(color='orange', width=1.5),
                name='K-Index',
                showlegend=True
            ),
            row=7, col=1
        )

    # 8. Classic CAPE and lifted index stop where the new server stops publishing them.
    # MUCAPE and the virtual lifted index continue as their own series.
    if len(cape_times):
        fig.add_trace(
            go.Scatter(
                x=cape_times,
                y=cape_values,
                mode='lines',
                line=dict(color='red', width=1.5),
                name='CAPE',
                showlegend=True
            ),
            row=8, col=1
        )

    if len(mucape_times):
        fig.add_trace(
            go.Scatter(
                x=mucape_times,
                y=mucape_values,
                mode='lines',
                line=dict(color='darkred', width=1.5, dash='dot'),
                name='MUCAPE',
                showlegend=True
            ),
            row=8, col=1
        )

    if len(lifted_times):
        fig.add_trace(
            go.Scatter(
                x=lifted_times,
                y=lifted_index_values,
                mode='lines',
                line=dict(color='blue', width=1.5),
                name='Lifted Index',
                showlegend=True
            ),
            row=8, col=1, secondary_y=True
        )

    if len(virtual_times):
        fig.add_trace(
            go.Scatter(
                x=virtual_times,
                y=virtual_lifted_values,
                mode='lines',
                line=dict(color='royalblue', width=1.5, dash='dot'),
                name='Virtual Lifted Index',
                showlegend=True
            ),
            row=8, col=1, secondary_y=True
        )

    if "Station number" in station.columns and station["Station number"].notna().any():
        station_number = str(station["Station number"].dropna().iloc[0])
    else:
        station_number = "10113"
    
    # Bepaal de laatste werkelijke datum en vandaag
    today = np.datetime64(datetime.now().replace(microsecond=0))
    last_measurement = unique_times.max() if len(unique_times) else today
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