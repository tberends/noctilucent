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

def scrape_sounding(station_number=10113):
    """
    Scrapt nieuwe sounding data vanaf de laatste meting.
    
    Args:
        station_number: Station nummer (default 10113)
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

def scrape_historical_data(start_date=None, end_date=None, station_number=10113, save_interval=100):
    """
    Haalt historische data op voor een periode. Haalt alleen ontbrekende tijdstempels op.
    
    Args:
        start_date: Start datum (datetime object). Als None, start vanaf 2017-06-17
        end_date: Eind datum (datetime object). Als None, gebruikt 2024-12-30
        station_number: Station nummer
        save_interval: Sla data op elke N metingen (om data niet te verliezen bij crashes)
    """
    # Laad bestaande data
    try:
        with open('data/sounding.pkl', 'rb') as f:
            data = pickle.load(f)
        print(f"Bestaande data geladen: {len(data)} entries")
    except FileNotFoundError:
        print("Geen bestaande data gevonden, start vanaf scratch.")
        data = {}
    
    # Verzamel alle bestaande tijdstempels voor efficiënte checks
    existing_timestamps = set()
    for key in data.keys():
        try:
            obs_time = data[key]['station_info']['Observation time']
            timestamp = datetime.strptime(obs_time, '%y%m%d/%H%M')
            existing_timestamps.add(timestamp)
        except:
            pass
    
    # Bepaal start en eind datum
    if start_date is None:
        start_date = datetime(2015, 1, 1, 0, 0)
    
    if end_date is None:
        end_date = datetime(2024, 12, 31, 0, 0)
    
    # Zorg dat start_date op 00 of 12 uur is
    if start_date.hour not in [0, 12]:
        start_date = start_date.replace(hour=0, minute=0)
    
    # Zorg dat end_date niet voorbij start_date is
    if end_date <= start_date:
        print(f"Eind datum ({end_date.strftime('%Y-%m-%d')}) is niet na start datum ({start_date.strftime('%Y-%m-%d')}).")
        print("Geen historische data om op te halen.")
        return
    
    print("\n" + "=" * 80)
    print("HISTORISCHE BATCH UPDATE")
    print("=" * 80)
    print(f"Periode: {start_date.strftime('%Y-%m-%d %H:%M')} tot {end_date.strftime('%Y-%m-%d %H:%M')}")
    
    # Bereken totaal aantal te halen metingen
    total_hours = (end_date - start_date).total_seconds() / 3600
    total_measurements = int(total_hours / 12)
    total_days = (end_date - start_date).days
    
    # Bereken hoeveel metingen er daadwerkelijk ontbreken
    missing_count = 0
    current_check = start_date
    while current_check < end_date:
        if current_check not in existing_timestamps:
            missing_count += 1
        current_check += timedelta(hours=12)
    
    print(f"Periode: {total_days} dagen ({total_measurements} metingen)")
    print(f"Ontbrekende metingen: {missing_count} (al aanwezig: {total_measurements - missing_count})")
    print(f"Opslaan elke {save_interval} metingen")
    print(f"Geschatte tijd: ~{(missing_count * 0.3) / 60:.0f} minuten\n")
    
    current_date = start_date
    fetched_count = 0
    skipped_count = 0
    failed_count = 0
    
    print("Start met ophalen historische data...\n")
    start_time = datetime.now()
    
    while current_date < end_date:
        # Skip als we deze meting al hebben
        if current_date in existing_timestamps:
            skipped_count += 1
            if skipped_count % 100 == 0:
                print(f"Skipped {skipped_count} bestaande metingen...")
            current_date += timedelta(hours=12)
            continue
        
        # Haal data op
        observation = fetch_single_observation(current_date, station_number)
        
        if observation:
            try:
                obs_time_str = observation['station_info']['Observation time']
                obs_timestamp = datetime.strptime(obs_time_str, '%y%m%d/%H%M')
                
                # Valideer dat de tijdstempel overeenkomt
                time_diff = abs((obs_timestamp - current_date).total_seconds() / 3600)
                if time_diff <= 12:
                    data[observation['key']] = {
                        'table': observation['table'],
                        'station_info': observation['station_info']
                    }
                    fetched_count += 1
                    
                    # Print progress elke 50 metingen
                    if fetched_count % 50 == 0:
                        progress_pct = (fetched_count / missing_count * 100) if missing_count > 0 else 0
                        elapsed_time = (datetime.now() - start_time).total_seconds() / 60
                        rate = fetched_count / elapsed_time if elapsed_time > 0 else 0
                        remaining = missing_count - fetched_count
                        eta_minutes = remaining / rate if rate > 0 else 0
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {fetched_count}/{missing_count} ({progress_pct:.1f}%) | "
                              f"Datum: {current_date.strftime('%Y-%m-%d %H:%M')} | "
                              f"{rate:.1f}/min | ETA: {eta_minutes:.0f} min")
                    
                    # Periodiek opslaan
                    if fetched_count % save_interval == 0:
                        sorted_keys = sorted(data.keys(), key=lambda k: datetime.strptime(data[k]['station_info']['Observation time'], '%y%m%d/%H%M'))
                        data = {key: data[key] for key in sorted_keys}
                        with open('data/sounding.pkl', 'wb') as f:
                            pickle.dump(data, f)
                        print(f"  → Opgeslagen: {len(data)} entries totaal")
                else:
                    failed_count += 1
            except (KeyError, ValueError) as e:
                failed_count += 1
        else:
            failed_count += 1
        
        # Rate limiting
        time.sleep(0.3)
        
        # Volgende 12-uurs periode
        current_date += timedelta(hours=12)
    
    # Final save
    sorted_keys = sorted(data.keys(), key=lambda k: datetime.strptime(data[k]['station_info']['Observation time'], '%y%m%d/%H%M'))
    data = {key: data[key] for key in sorted_keys}
    
    with open('data/sounding.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    # Bereken totale tijd
    total_time = (datetime.now() - start_time).total_seconds() / 60
    
    print("\n" + "=" * 80)
    print("HISTORISCHE BATCH UPDATE VOLTOOID")
    print("=" * 80)
    print(f"Nieuw opgehaald: {fetched_count} metingen")
    print(f"Overgeslagen (al aanwezig): {skipped_count} metingen")
    print(f"Mislukt: {failed_count} metingen")
    print(f"Totale tijd: {total_time:.1f} minuten")
    print(f"Totaal entries in database: {len(data)}")
    if data:
        sorted_keys = sorted(data.keys(), key=lambda k: datetime.strptime(data[k]['station_info']['Observation time'], '%y%m%d/%H%M'))
        first_key = sorted_keys[0]
        last_key = sorted_keys[-1]
        print(f"Eerste record: {data[first_key]['station_info']['Observation time']}")
        print(f"Laatste record: {data[last_key]['station_info']['Observation time']}")
    print("=" * 80)

if __name__ == '__main__':
    import sys
    
    # Check of historische batch mode wordt gevraagd
    if '--historical' in sys.argv or '-h' in sys.argv:
        scrape_historical_data()
    else:
        scrape_sounding()

# %%
