#https://weather.uwyo.edu/cgi-bin/sounding?region=europe&TYPE=TEXT%3ALIST&YEAR=2025&MONTH=01&FROM=2000&TO=2100&STNM=10113
#https://weather.uwyo.edu/cgi-bin/sounding?region=europe&TYPE=TEXT%3ALIST&YEAR=2005&MONTH=01&FROM=2000&TO=2700&STNM=06260

#%%
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import warnings
import pickle
import time

def fetch_single_observation(target_date, station_number=10113):
    """
    Haalt een enkele observation op voor een specifieke datum/tijd.
    
    Args:
        target_date: datetime object voor de gewenste observation
        station_number: Station nummer (default 10113)
    
    Returns:
        Dictionary met 'table' en 'station_info', of None als data niet beschikbaar is
    """
    base_url = f"https://weather.uwyo.edu/cgi-bin/sounding?region=europe&TYPE=TEXT%3ALIST&YEAR={target_date.year}&MONTH={target_date.strftime('%m')}&FROM={target_date.strftime('%d%H')}&TO={target_date.strftime('%d%H')}&STNM={station_number}"
    
    try:
        warnings.filterwarnings('ignore')
        response = requests.get(base_url, verify=False, timeout=10)
        html_content = response.text
        
        soup = BeautifulSoup(html_content, 'html.parser')
        pre_tags = soup.find_all('pre')
        
        if len(pre_tags) < 2:
            return None
        
        # Extract the table data from the first <pre> section
        table_data = pre_tags[0].text.strip().split('\n')
        
        # Extract the header and data rows
        header = table_data[1].split()
        data_rows = [row for row in table_data[4:] if row.strip()]
        
        # Split each data row after every 7 characters
        data_rows = [[row[i:i+7].strip() or None for i in range(0, len(row), 7)] for row in data_rows]
        
        # Create a DataFrame for the table data
        df_table = pd.DataFrame(data_rows, columns=header)
        
        # Extract the station information from the second <pre> section
        station_info = pre_tags[1].text.strip().split('\n')
        
        # Create a dictionary for the station information
        station_info_dict = {}
        for line in station_info:
            if ':' in line:
                key, value = line.split(':', 1)
                station_info_dict[key.strip()] = value.strip()
        
        # Extract the <h2> tag content
        h2_tag = soup.find('h2').text.strip()
        
        return {
            'key': h2_tag,
            'table': df_table,
            'station_info': station_info_dict
        }
    except Exception as e:
        print(f"Fout bij ophalen data voor {target_date.strftime('%Y-%m-%d %H:%M')}: {str(e)}")
        return None

def detect_missing_timestamps(data):
    """
    Detecteert ontbrekende tijdstempels in de data.
    
    Args:
        data: Dictionary met sounding data
    
    Returns:
        List van datetime objecten voor ontbrekende tijdstempels
    """
    if not data:
        return []
    
    # Verzamel alle tijdstempels en sorteer ze
    timestamps = []
    for key in data.keys():
        try:
            obs_time = data[key]['station_info']['Observation time']
            timestamp = datetime.strptime(obs_time, '%y%m%d/%H%M')
            timestamps.append(timestamp)
        except (KeyError, ValueError):
            continue
    
    if len(timestamps) < 2:
        return []
    
    timestamps.sort()
    
    # Vind gaps (ontbrekende 12-uurs metingen)
    missing_timestamps = []
    for i in range(len(timestamps) - 1):
        current = timestamps[i]
        next_ts = timestamps[i + 1]
        
        # Check of er een gap is van meer dan 12 uur maar minder dan 7 dagen
        # (gaps groter dan 7 dagen zijn waarschijnlijk geen echte gaps maar legitieme missende data)
        time_diff = (next_ts - current).total_seconds() / 3600  # in uren
        
        if 12 < time_diff <= 168:  # Meer dan 12 uur maar minder dan 1 week
            # Genereer alle ontbrekende 12-uurs tijdstempels
            gap_start = current + timedelta(hours=12)
            while gap_start < next_ts:
                missing_timestamps.append(gap_start)
                gap_start += timedelta(hours=12)
    
    return missing_timestamps

def fill_missing_timestamps(data, station_number=10113, max_attempts=3):
    """
    Vult ontbrekende tijdstempels op door data op te halen.
    
    Args:
        data: Dictionary met sounding data
        station_number: Station nummer
        max_attempts: Maximum aantal pogingen per ontbrekende timestamp
    
    Returns:
        Tuple (updated_data, aantal_opgehaald, aantal_mislukt)
    """
    missing = detect_missing_timestamps(data)
    
    if not missing:
        print("Geen ontbrekende tijdstempels gevonden.")
        return data, 0, 0
    
    print(f"\n{len(missing)} ontbrekende tijdstempels gedetecteerd.")
    print("Poging om ontbrekende data op te halen...\n")
    
    fetched_count = 0
    failed_count = 0
    
    for missing_ts in missing:
        print(f"Ophalen data voor {missing_ts.strftime('%Y-%m-%d %H:%M')}...", end=' ')
        
        for attempt in range(max_attempts):
            observation = fetch_single_observation(missing_ts, station_number)
            
            if observation:
                # Controleer of de observation time overeenkomt met wat we verwachten
                try:
                    obs_time_str = observation['station_info']['Observation time']
                    obs_timestamp = datetime.strptime(obs_time_str, '%y%m%d/%H%M')
                    
                    # Accepteer als het binnen 12 uur is van de verwachte tijd
                    time_diff = abs((obs_timestamp - missing_ts).total_seconds() / 3600)
                    if time_diff <= 12:
                        data[observation['key']] = {
                            'table': observation['table'],
                            'station_info': observation['station_info']
                        }
                        fetched_count += 1
                        print(f"✓ Opgehaald")
                        break
                    else:
                        print(f"✗ Tijdstempel mismatch (verschil: {time_diff:.1f} uur)", end=' ')
                except (KeyError, ValueError) as e:
                    print(f"✗ Ongeldige observation time", end=' ')
            else:
                if attempt < max_attempts - 1:
                    print(f"✗ Poging {attempt + 1}/{max_attempts} mislukt, opnieuw proberen...", end=' ')
                else:
                    print(f"✗ Mislukt na {max_attempts} pogingen")
                    failed_count += 1
        
        # Kleine delay om server niet te overbelasten
        time.sleep(0.5)
    
    # Herordenen op chronologische volgorde
    sorted_keys = sorted(data.keys(), key=lambda k: datetime.strptime(data[k]['station_info']['Observation time'], '%y%m%d/%H%M'))
    data = {key: data[key] for key in sorted_keys}
    
    print(f"\nResultaat: {fetched_count} ontbrekende metingen opgehaald, {failed_count} mislukt.")
    
    return data, fetched_count, failed_count

def scrape_sounding(station_number=10113, fill_gaps=True):
    """
    Scrapt sounding data en vult ontbrekende tijdstempels op.
    
    Args:
        station_number: Station nummer (default 10113)
        fill_gaps: Of ontbrekende tijdstempels automatisch moeten worden opgevuld
    """
    # Load the existing data if the file exists
    try:
        with open('data/sounding.pkl', 'rb') as f:
            data = pickle.load(f)
            latest_key = max(data.keys(), key=lambda k: datetime.strptime(data[k]['station_info']['Observation time'], '%y%m%d/%H%M'))
            latest_data = data[latest_key]
            print(f"Latest key: {latest_key}")
            print(f"Station information for the latest key: {latest_data['station_info']['Observation time']}")
    except FileNotFoundError:
        print("No existing data found, starting from scratch.")
        data = {}
    except Exception as e:
        print(f"Fout bij laden van data: {str(e)}")
        data = {}

    # Vul eerst ontbrekende tijdstempels op als gevraagd
    if fill_gaps and data:
        print("\n" + "=" * 80)
        print("CONTROLE OP ONTBREKENDE TIJDSTEMPELS")
        print("=" * 80)
        data, fetched, failed = fill_missing_timestamps(data, station_number)
        if fetched > 0:
            # Sla de bijgewerkte data op
            with open('data/sounding.pkl', 'wb') as f:
                pickle.dump(data, f)
            print(f"Tussentijds opgeslagen: {fetched} nieuwe metingen toegevoegd.\n")

    # Base URL
    base_url = f"https://weather.uwyo.edu/cgi-bin/sounding?region=europe&TYPE=TEXT%3ALIST&YEAR={{year}}&MONTH={{month}}&FROM={{from_time}}&TO={{to_time}}&STNM={station_number}"

    # Start and end dates for scraping
    if data:
        latest_key = max(data.keys(), key=lambda k: datetime.strptime(data[k]['station_info']['Observation time'], '%y%m%d/%H%M'))
        latest_data = data[latest_key]
        start_date = datetime.strptime(latest_data['station_info']['Observation time'], '%y%m%d/%H%M')
    else:
        start_date = datetime.now() - timedelta(days=33)
    
    # Ensure start_date is at 00 or 12 hours
    if start_date.hour not in [0, 12]:
        start_date = start_date.replace(hour=12 if start_date.hour > 12 else 0)
    
    # Begin vanaf de volgende 12-uurs periode
    start_date += timedelta(hours=12)
    end_date = datetime.now()

    # Print the start and end dates in one line
    print("=" * 80)
    print("OPHALEN NIEUWE DATA")
    print("=" * 80)
    print(f"Start date: {start_date.strftime('%Y-%m-%d %H:%M')}, End date: {end_date.strftime('%Y-%m-%d %H:%M')}\n")

    # Loop over each 12-hour interval
    new_data_count = 0
    while start_date < end_date:
        # Extract the year, month and day from the start date
        year = start_date.strftime("%Y")
        month = start_date.strftime("%m")
        from_time = start_date.strftime("%d%H")
        
        # Format the URL with the current FROM and TO times
        url = base_url.format(year=year, month=month, from_time=from_time, to_time=from_time)
        
        # Fetch the HTML content with SSL verification disabled
        warnings.filterwarnings('ignore')
        try:
            response = requests.get(url, verify=False, timeout=10)
            html_content = response.text
        except Exception as e:
            print(f"Fout bij ophalen {start_date.strftime('%Y-%m-%d %H:%M')}: {str(e)}")
            start_date += timedelta(hours=12)
            continue
        
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract the <pre> sections
        pre_tags = soup.find_all('pre')
        
        if len(pre_tags) < 2:
            start_date += timedelta(hours=12)
            continue
        
        # Extract the table data from the first <pre> section
        table_data = pre_tags[0].text.strip().split('\n')
        
        # Extract the header and data rows
        header = table_data[1].split()
        data_rows = [row for row in table_data[4:] if row.strip()]
        
        # Split each data row after every 7 characters
        data_rows = [[row[i:i+7].strip() or None for i in range(0, len(row), 7)] for row in data_rows]
        
        # Create a DataFrame for the table data
        df_table = pd.DataFrame(data_rows, columns=header)
        
        # Extract the station information from the second <pre> section
        station_info = pre_tags[1].text.strip().split('\n')
        
        # Create a dictionary for the station information
        station_info_dict = {}
        for line in station_info:
            if ':' in line:
                key, value = line.split(':', 1)
                station_info_dict[key.strip()] = value.strip()
        
        # Extract the <h2> tag content
        h2_tag = soup.find('h2').text.strip()
        
        # Store the data in the all_data dictionary
        data[h2_tag] = {
            "table": df_table,
            "station_info": station_info_dict
        }
        
        new_data_count += 1
        
        # Move to the next 12-hour interval
        start_date += timedelta(hours=12)
        
        # print station information Observation time
        print(f"Retrieved data for observation time: {station_info_dict['Observation time']}")

    # Order the keys by the observation time
    sorted_keys = sorted(data.keys(), key=lambda k: datetime.strptime(data[k]['station_info']['Observation time'], '%y%m%d/%H%M'))

    # Reorder the data dictionary using the sorted keys
    data = {key: data[key] for key in sorted_keys}

    print(f"\n{new_data_count} nieuwe metingen toegevoegd.")
    if data:
        print(f"Laatste meting: {data[list(data.keys())[-1]]['station_info']['Observation time']}")

    # Save the updated data object back to the file
    with open('data/sounding.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    print(f"Data opgeslagen: totaal {len(data)} entries.")

if __name__ == '__main__':
    scrape_sounding()

# %%
