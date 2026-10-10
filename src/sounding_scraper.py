# https://weather.uwyo.edu/wsgi/sounding?datetime=2026-10-09%2012:00:00&id=10113&src=FM35&type=TEXT:LIST

import pickle
import re
import time
import warnings
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from src.sounding_store import (
    MS_TO_KNOTS,
    PICKLE_PATH,
    PROFILE_VALUE_COLUMNS,
    append_sounding,
    frames_from_legacy,
    latest_time,
    load_profiles,
    load_station,
    save_frames,
)

STATION_NUMBER = "10113"
BASE_URL = "https://weather.uwyo.edu/wsgi/sounding"
USER_AGENT = "noctilucent"
COLUMN_WIDTH = 7
SAVE_EVERY = 20

# KINX matches the historical K index. The other new indices keep their own names.
INDEX_FIELDS = {
    "SLAT": "Station latitude",
    "SLON": "Station longitude",
    "SELV": "Station elevation",
    "SHOW": "Showalter Index",
    "LFVT": "Virtual Lifted Index",
    "SWET": "SWEAT",
    "KINX": "K index",
    "CTOT": "Cross Totals",
    "VTOT": "Vertical Totals",
    "TOTL": "Total Totals",
    "DCAPE": "Downward CAPE",
    "MUCAPE": "Most Unstable CAPE",
    "MUCIN": "Most Unstable CIN",
    "LCLP": "Lifted Condensation Level",
    "LCLT": "Temperature of the Lifted Condensation Level",
    "LCLZ": "Height of the Lifted Condensation Level",
    "CCLP": "Convective Condensation Level",
    "CCLT": "Temperature of the Convective Condensation Level",
    "CCLC": "Convective Temperature",
    "PWAT": "Precipitable Water",
}

INDEX_ROW = re.compile(
    r"<TR>\s*<TD>\s*([A-Z0-9]+)\s*</TD>\s*<TD>([^<]*)</TD>\s*<TD[^>]*>\s*([^<]*)</TD>",
    re.IGNORECASE,
)
INVENTORY_HREF = re.compile(r'href="([^"]+)"', re.IGNORECASE)
INVENTORY_TIME = re.compile(r"datetime=(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def sounding_url(when, station_number, product):
    stamp = when.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"{BASE_URL}?datetime={requests.utils.quote(stamp)}"
        f"&id={station_number}&src=FM35&type={product}"
    )


class FetchError(RuntimeError):
    """The sounding server failed after retries. The slot should be tried again later."""


def http_get(url, timeout=45, attempts=4):
    """GET text. A missing sounding (HTTP 400 or 404) returns None."""
    last_error = None
    for attempt in range(attempts):
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT},
            )
            if response.status_code in (400, 404):
                return None
            if response.status_code >= 500:
                raise requests.HTTPError(f"HTTP {response.status_code}")
            response.raise_for_status()
            return response.text
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as error:
            last_error = error
            time.sleep(2 ** attempt)
    raise FetchError(f"Opvragen mislukt na {attempts} pogingen: {last_error}")


def parse_profile(html):
    """Parse the fixed-width PRE block. Wind is stored as SKNT in knots."""
    match = re.search(r"<PRE>(.*?)</PRE>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    lines = match.group(1).splitlines()
    header_index = None
    for index, line in enumerate(lines):
        if "PRES" in line and "HGHT" in line and "TEMP" in line:
            header_index = index
            break
    if header_index is None:
        return None

    header_line = lines[header_index]
    column_count = max(1, len(header_line) // COLUMN_WIDTH)
    header = [
        header_line[i * COLUMN_WIDTH:(i + 1) * COLUMN_WIDTH].strip()
        for i in range(column_count)
    ]
    while header and not header[-1]:
        header.pop()
    if not header:
        return None

    rows = []
    for line in lines[header_index + 3:]:
        if not line.strip() or set(line.strip()) <= {"-"}:
            continue
        values = []
        for index in range(len(header)):
            chunk = line[index * COLUMN_WIDTH:(index + 1) * COLUMN_WIDTH].strip()
            values.append(chunk or None)
        rows.append(values)
    if not rows:
        return None

    frame = pd.DataFrame(rows, columns=header)
    if "SPED" in frame.columns:
        frame["SKNT"] = pd.to_numeric(frame["SPED"], errors="coerce") * MS_TO_KNOTS
        frame = frame.drop(columns=["SPED"])
    for column in PROFILE_VALUE_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            frame[column] = pd.NA
    return frame[PROFILE_VALUE_COLUMNS]


def parse_indices(html):
    fields = {}
    for code, _description, raw_value in INDEX_ROW.findall(html):
        name = INDEX_FIELDS.get(code.strip().upper())
        if name is None:
            continue
        value = raw_value.strip()
        if not value:
            continue
        try:
            fields[name] = float(value)
        except ValueError:
            fields[name] = value
    return fields


def fetch_sounding(when, station_number=STATION_NUMBER):
    """Download one FM35 sounding. `when` is the inventory time, not the launch clock."""
    html = http_get(sounding_url(when, station_number, "TEXT:LIST"))
    if not html:
        return None
    profile = parse_profile(html)
    if profile is None or profile.empty:
        return None
    timestamp = pd.Timestamp(when)
    profile = profile.copy()
    profile.insert(0, "time", timestamp)
    station_row = {
        "time": timestamp,
        "Station number": str(station_number),
        "Observation time": timestamp.strftime("%y%m%d/%H%M"),
    }
    station_row.update(parse_indices(html))
    return profile, station_row


def inventory_times(year, station_number=STATION_NUMBER):
    """Nominal FM35 times for one year. Year-menu links use type=INVENTORY and are skipped."""
    probe = datetime(year, 1, 1, 0, 0)
    html = http_get(sounding_url(probe, station_number, "INVENTORY"))
    if not html:
        return []
    html = html.replace("&amp;", "&")
    found = []
    for href in INVENTORY_HREF.findall(html):
        if "type=TEXT:LIST" not in href:
            continue
        match = INVENTORY_TIME.search(href)
        if not match:
            continue
        when = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        if when.year == year:
            found.append(when)
    return sorted(set(found))


def _stored_times(station):
    if station.empty or "time" not in station.columns:
        return set()
    stamps = pd.to_datetime(station["time"]).dt.floor("s")
    return set(stamps.dt.to_pydatetime())


def ensure_archive():
    """Load the Parquet archive, converting the legacy pickle once if needed."""
    profiles = load_profiles()
    station = load_station()
    if not station.empty:
        return profiles, station
    if not PICKLE_PATH.exists():
        return profiles, station
    print(f"Parquet ontbreekt, zet {PICKLE_PATH} om.")
    with open(PICKLE_PATH, "rb") as handle:
        legacy = pickle.load(handle)
    profiles, station = frames_from_legacy(legacy)
    save_frames(profiles, station)
    print(f"Omgezet: {station['time'].nunique()} oplatingen, {len(profiles)} niveaus.")
    return load_profiles(), load_station()


def scrape_sounding(station_number=STATION_NUMBER):
    """Fetch FM35 soundings newer than the latest stored observation."""
    warnings.filterwarnings("ignore", category=FutureWarning)
    profiles, station = ensure_archive()
    last = latest_time(station)
    existing = _stored_times(station)
    if last is None:
        start = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(days=33)
        print("Geen bestaand archief, inventaris van de laatste 33 dagen.")
    else:
        start = last
        print(f"Laatste meting: {last.strftime('%Y-%m-%d %H:%M')}")

    end = datetime.now(timezone.utc).replace(tzinfo=None)
    floor = start if last is None else last
    wanted = []
    for year in range(floor.year, end.year + 1):
        for when in inventory_times(year, station_number):
            if when in existing or when > end or when <= floor:
                continue
            wanted.append(when)
    wanted = sorted(set(wanted))

    print("=" * 80)
    print("OPHALEN NIEUWE DATA")
    print("=" * 80)
    print(f"{len(wanted)} ontbrekende FM35-oplatingen tot {end.strftime('%Y-%m-%d %H:%M')}\n")

    added = 0
    failed = 0
    try:
        for when in wanted:
            observation = fetch_sounding(when, station_number)
            if observation is None:
                failed += 1
                print(f"Geen data voor {when.strftime('%Y-%m-%d %H:%M')}")
            else:
                profile_rows, station_row = observation
                profiles, station = append_sounding(profiles, station, profile_rows, station_row)
                added += 1
                k_index = station_row.get("K index")
                print(
                    f"Opgehaald {station_row['Observation time']}"
                    f" ({len(profile_rows)} niveaus, K index {k_index})"
                )
                if added % SAVE_EVERY == 0:
                    save_frames(profiles, station)
                    print(f"  → tussentijds opgeslagen ({station['time'].nunique()} oplatingen)")
            time.sleep(0.35)
    except FetchError as error:
        if added:
            save_frames(profiles, station)
        print(error)
        raise

    if added:
        save_frames(profiles, station)
    print(f"\n{added} nieuwe metingen toegevoegd, {failed} mislukt.")
    if not station.empty:
        print(f"Laatste meting: {latest_time(station).strftime('%Y-%m-%d %H:%M')}")
    print(f"Totaal {0 if station.empty else station['time'].nunique()} oplatingen.")


def fetch_single_observation(target_date, station_number=STATION_NUMBER):
    """Backward-compatible helper. Returns None when the inventory slot is empty."""
    observation = fetch_sounding(target_date, station_number)
    if observation is None:
        return None
    profile_rows, station_row = observation
    info = {key: value for key, value in station_row.items() if key != "time"}
    return {
        "key": target_date.strftime("%Y-%m-%d %H:%M"),
        "table": profile_rows.drop(columns=["time"]),
        "station_info": info,
    }


def scrape_historical_data(start_date=None, end_date=None, station_number=STATION_NUMBER, save_interval=SAVE_EVERY):
    """Fill inventory slots in a date range that are not already stored."""
    profiles, station = ensure_archive()
    existing = set(pd.to_datetime(station["time"]).dt.to_pydatetime()) if not station.empty else set()
    if start_date is None:
        start_date = datetime(2015, 1, 1, 0, 0)
    if end_date is None:
        end_date = datetime.now(timezone.utc).replace(tzinfo=None)

    wanted = []
    for year in range(start_date.year, end_date.year + 1):
        for when in inventory_times(year, station_number):
            if start_date <= when < end_date and when not in existing:
                wanted.append(when)

    print(f"Historisch ontbrekend: {len(wanted)} oplatingen")
    added = 0
    failed = 0
    for when in wanted:
        observation = fetch_sounding(when, station_number)
        if observation is None:
            failed += 1
        else:
            profile_rows, station_row = observation
            profiles, station = append_sounding(profiles, station, profile_rows, station_row)
            added += 1
            if added % save_interval == 0:
                save_frames(profiles, station)
                print(f"  → opgeslagen na {added} nieuwe oplatingen")
        time.sleep(0.35)
    if added:
        save_frames(profiles, station)
    print(f"Nieuw: {added}, mislukt: {failed}, totaal: {0 if station.empty else station['time'].nunique()}")


if __name__ == "__main__":
    import sys

    if "--historical" in sys.argv:
        scrape_historical_data()
    else:
        scrape_sounding()
