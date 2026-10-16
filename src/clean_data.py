import shutil
from datetime import datetime
import pandas as pd
from collections import defaultdict

from src.sounding_store import PROFILES_PATH, STATION_PATH, load_profiles, load_station, save_frames

def analyze_timestamps(data):
    """Find corrupt observation times in the station records."""
    corrupt_entries = []
    valid_entries = []
    timestamp_issues = defaultdict(list)

    print("=" * 80)
    print("ANALYSE VAN TIJDSTEMPELS")
    print("=" * 80)
    print()

    for key in data.keys():
        try:
            station_info = data[key]['station_info']

            if 'Observation time' not in station_info:
                corrupt_entries.append({
                    'key': key,
                    'issue': 'Missing Observation time',
                    'station_info': station_info
                })
                timestamp_issues['Missing Observation time'].append(key)
                continue

            obs_time_str = station_info['Observation time']

            try:
                timestamp = datetime.strptime(obs_time_str, '%y%m%d/%H%M')
                issues = []

                if timestamp.year < 1900 or timestamp.year > 2100:
                    issues.append(f'Ongeldig jaar: {timestamp.year}')

                if timestamp.month < 1 or timestamp.month > 12:
                    issues.append(f'Ongeldige maand: {timestamp.month}')

                if timestamp.day < 1 or timestamp.day > 31:
                    issues.append(f'Ongeldige dag: {timestamp.day}')

                try:
                    datetime(timestamp.year, timestamp.month, timestamp.day, timestamp.hour, timestamp.minute)
                except ValueError as e:
                    issues.append(f'Ongeldige datum combinatie: {str(e)}')

                if timestamp.hour < 0 or timestamp.hour > 23:
                    issues.append(f'Ongeldig uur: {timestamp.hour}')

                if timestamp.minute < 0 or timestamp.minute > 59:
                    issues.append(f'Ongeldige minuut: {timestamp.minute}')

                # FM35 soundings are 00 and 12 UTC, with occasional 06 and 18 UTC slots.
                if timestamp.hour not in [0, 6, 12, 18]:
                    issues.append(f'Ongebruikelijk uur: {timestamp.hour} (verwacht 0, 6, 12 of 18)')

                if issues:
                    corrupt_entries.append({
                        'key': key,
                        'issue': '; '.join(issues),
                        'timestamp': timestamp,
                        'timestamp_str': obs_time_str,
                        'station_info': station_info
                    })
                    for issue in issues:
                        timestamp_issues[issue].append(key)
                else:
                    valid_entries.append({
                        'key': key,
                        'timestamp': timestamp,
                        'timestamp_str': obs_time_str
                    })

            except ValueError as e:
                corrupt_entries.append({
                    'key': key,
                    'issue': f'Kan tijdstempel niet parsen: {str(e)}',
                    'timestamp_str': obs_time_str,
                    'station_info': station_info
                })
                timestamp_issues[f'Parse error: {str(e)}'].append(key)

        except Exception as e:
            corrupt_entries.append({
                'key': key,
                'issue': f'Onverwachte fout: {str(e)}',
                'station_info': data[key].get('station_info', {})
            })
            timestamp_issues[f'Unexpected error: {str(e)}'].append(key)

    return corrupt_entries, valid_entries, timestamp_issues


def check_temporal_consistency(valid_entries):
    """
    Flag jumps larger than one week or more than 12 hours backwards.
    For a large forward jump, mark the older entry; for a backward jump, the newer one.
    """
    if len(valid_entries) < 2:
        return []

    sorted_entries = sorted(valid_entries, key=lambda x: x['timestamp'])

    suspicious_entries = []
    for i in range(1, len(sorted_entries)):
        prev_time = sorted_entries[i-1]['timestamp']
        curr_time = sorted_entries[i]['timestamp']
        time_diff = (curr_time - prev_time).total_seconds() / 3600  # hours

        if time_diff > 168:  # one week
            suspicious_entries.append({
                'key': sorted_entries[i-1]['key'],
                'issue': f'Zeer grote tijdsprong: {time_diff/24:.1f} dagen ({time_diff:.1f} uur) naar volgende meting - oudere entry waarschijnlijk corrupt',
                'timestamp': prev_time,
                'next_timestamp': curr_time
            })

        if time_diff < -12:
            suspicious_entries.append({
                'key': sorted_entries[i]['key'],
                'issue': f'Tijdstempel gaat terug in tijd: {time_diff:.1f} uur verschil - nieuwere entry waarschijnlijk corrupt',
                'timestamp': curr_time,
                'previous_timestamp': prev_time
            })

    return suspicious_entries


def print_report(corrupt_entries, valid_entries, timestamp_issues, suspicious_entries):
    """Print counts and details for corrupt and suspicious entries."""
    print(f"Totaal aantal entries: {len(corrupt_entries) + len(valid_entries)}")
    print(f"Geldige entries: {len(valid_entries)}")
    print(f"Corrupte entries: {len(corrupt_entries)}")
    print(f"Verdachte entries (tijdsconsistency): {len(suspicious_entries)}")
    print()

    if timestamp_issues:
        print("=" * 80)
        print("OVERZICHT VAN PROBLEMEN PER TYPE")
        print("=" * 80)
        for issue_type, keys in timestamp_issues.items():
            print(f"\n{issue_type}: {len(keys)} entries")
            for key in keys[:5]:
                print(f"  - {key}")
            if len(keys) > 5:
                print(f"  ... en {len(keys) - 5} meer")
        print()

    if corrupt_entries:
        print("=" * 80)
        print("DETAILS VAN CORRUPTE ENTRIES")
        print("=" * 80)
        for i, entry in enumerate(corrupt_entries, 1):
            print(f"\n{i}. Key: {entry['key']}")
            print(f"   Probleem: {entry['issue']}")
            if 'timestamp_str' in entry:
                print(f"   Tijdstempel string: {entry['timestamp_str']}")
            if 'timestamp' in entry:
                print(f"   Geparste tijdstempel: {entry['timestamp']}")
            if 'station_info' in entry:
                print(f"   Station info: {entry['station_info']}")
        print()

    if suspicious_entries:
        print("=" * 80)
        print("VERDACHTE ENTRIES (TIJDSORDENING)")
        print("=" * 80)
        for i, entry in enumerate(suspicious_entries, 1):
            print(f"\n{i}. Key: {entry['key']}")
            print(f"   Probleem: {entry['issue']}")
            print(f"   Tijdstempel: {entry['timestamp']}")
            if 'previous_timestamp' in entry:
                print(f"   Vorige tijdstempel: {entry['previous_timestamp']}")
            if 'next_timestamp' in entry:
                print(f"   Volgende tijdstempel: {entry['next_timestamp']}")
        print()


def clean_data(data, corrupt_keys, suspicious_keys=None, dry_run=True):
    """
    Remove corrupt keys from the data dict.

    dry_run=True only prints the keys that would be removed.
    """
    if suspicious_keys is None:
        suspicious_keys = []

    keys_to_remove = set(corrupt_keys + suspicious_keys)

    print("=" * 80)
    if dry_run:
        print("DRY RUN - Geen data wordt daadwerkelijk verwijderd")
    else:
        print("VERWIJDEREN VAN CORRUPTE DATA")
    print("=" * 80)
    print()

    print(f"Entries die verwijderd zouden worden: {len(keys_to_remove)}")
    print()

    for key in sorted(keys_to_remove):
        print(f"  - {key}")

    if not dry_run:
        cleaned_data = {k: v for k, v in data.items() if k not in keys_to_remove}
        print(f"\n{len(keys_to_remove)} entries verwijderd.")
        print(f"Resterende entries: {len(cleaned_data)}")
        return cleaned_data

    return None


def station_as_records(station):
    """Adapt the station table to the dict shape the timestamp checks expect."""
    data = {}
    for _, row in station.iterrows():
        timestamp = pd.Timestamp(row["time"])
        key = timestamp.strftime("%Y-%m-%d %H:%M")
        observation = row["Observation time"] if "Observation time" in row.index else None
        if observation is None or pd.isna(observation):
            observation = timestamp.strftime("%y%m%d/%H%M")
        info = {"Observation time": str(observation)}
        for column, value in row.items():
            if column in ("time", "Observation time") or pd.isna(value):
                continue
            info[column] = value
        data[key] = {"station_info": info}
    return data


def main():
    """
    Analyse and optionally clean the Parquet archive.

    Usage: python src/clean_data.py [--clean] [--backup]
    --clean: remove flagged soundings
    --backup: copy the Parquet files before cleaning
    """
    import sys

    do_clean = "--clean" in sys.argv
    do_backup = "--backup" in sys.argv or do_clean

    print("Laden van data/station.parquet en data/profiles.parquet...")
    try:
        station = load_station()
        profiles = load_profiles()
    except Exception as error:
        print(f"Fout bij het laden van data: {error}")
        return
    if station.empty:
        print("Fout: data/station.parquet is leeg of ontbreekt.")
        return

    data = station_as_records(station)
    print(f"Data geladen: {len(data)} entries gevonden.\n")

    corrupt_entries, valid_entries, timestamp_issues = analyze_timestamps(data)
    suspicious_entries = check_temporal_consistency(valid_entries)
    print_report(corrupt_entries, valid_entries, timestamp_issues, suspicious_entries)

    corrupt_keys = [entry["key"] for entry in corrupt_entries]
    suspicious_keys = [entry["key"] for entry in suspicious_entries]

    if corrupt_keys or suspicious_keys:
        print("=" * 80)
        print("OPSCHONING")
        print("=" * 80)
        print()

        if do_clean:
            if do_backup:
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                profile_backup = PROFILES_PATH.with_name(f"profiles_backup_{stamp}.parquet")
                station_backup = STATION_PATH.with_name(f"station_backup_{stamp}.parquet")
                shutil.copy(PROFILES_PATH, profile_backup)
                shutil.copy(STATION_PATH, station_backup)
                print(f"Backup gemaakt: {profile_backup.name}, {station_backup.name}\n")

            remove = set(corrupt_keys + suspicious_keys)
            keep = ~station["time"].dt.strftime("%Y-%m-%d %H:%M").isin(remove)
            cleaned_station = station.loc[keep].copy()
            cleaned_profiles = profiles.loc[
                profiles["time"].dt.strftime("%Y-%m-%d %H:%M").isin(
                    cleaned_station["time"].dt.strftime("%Y-%m-%d %H:%M")
                )
            ].copy()
            save_frames(cleaned_profiles, cleaned_station)
            print("\nOpgeschoonde data opgeslagen naar de Parquet-bestanden")
            print(f"Origineel had {len(station)} entries, nu {len(cleaned_station)} entries.")
        else:
            print("Dit is een DRY RUN. Geen data wordt verwijderd.")
            print("Voeg --clean toe aan het commando om daadwerkelijk op te schonen.")
            print("Voeg --backup toe om automatisch een backup te maken.\n")
            clean_data(data, corrupt_keys, suspicious_keys, dry_run=True)
    else:
        print("Geen corrupte data gevonden! Data ziet er goed uit.")

if __name__ == '__main__':
    main()

