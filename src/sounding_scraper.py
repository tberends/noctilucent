#https://weather.uwyo.edu/cgi-bin/sounding?region=europe&TYPE=TEXT%3ALIST&YEAR=2025&MONTH=01&FROM=2000&TO=2100&STNM=10113
#https://weather.uwyo.edu/cgi-bin/sounding?region=europe&TYPE=TEXT%3ALIST&YEAR=2005&MONTH=01&FROM=2000&TO=2700&STNM=06260

#%%
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import warnings
import pickle

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

# Base URL
base_url = "https://weather.uwyo.edu/cgi-bin/sounding?region=europe&TYPE=TEXT%3ALIST&YEAR=2025&MONTH={month}&FROM={from_time}&TO={to_time}&STNM=10113"

# Start and end dates for scraping
start_date = datetime.strptime(latest_data['station_info']['Observation time'], '%y%m%d/%H%M') if 'latest_data' in locals() else datetime.now() - timedelta(days=33)
# Ensure start_date is at 00 or 12 hours
if start_date.hour not in [0, 12]:
    start_date = start_date.replace(hour=12 if start_date.hour > 12 else 0)
end_date = datetime.now()

# Print the start and end dates in one line
print(f"Start date: {start_date.strftime('%Y-%m-%d %H:%M')}, End date: {end_date.strftime('%Y-%m-%d %H:%M')}")

# Loop over each 12-hour interval in January 2025
while start_date < end_date:
    # Extract the month and day from the start date
    month = start_date.strftime("%m")
    from_time = start_date.strftime("%d%H")
    
    # Format the URL with the current FROM and TO times
    url = base_url.format(month=month,from_time=from_time, to_time=from_time)
    
    # Fetch the HTML content with SSL verification disabled
    warnings.filterwarnings('ignore')
    response = requests.get(url, verify=False)
    html_content = response.text
    
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
    
    # Move to the next 12-hour interval
    start_date += timedelta(hours=12)
    
    # print station information Observation time
    print(f"Retrieved data for observation time:\n{station_info_dict['Observation time']}")

# Order the keys by the observation time
sorted_keys = sorted(data.keys(), key=lambda k: datetime.strptime(data[k]['station_info']['Observation time'], '%y%m%d/%H%M'))

# Reorder the data dictionary using the sorted keys
data = {key: data[key] for key in sorted_keys}

# Print the station information for the first key without knowing the key name
print(data[list(data.keys())[-1]]['station_info'])

# Save the updated data object back to the file
with open('data/sounding.pkl', 'wb') as f:
    pickle.dump(data, f)

# %%
