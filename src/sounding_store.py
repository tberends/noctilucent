"""Read and write the sounding archive as two Parquet tables."""

from pathlib import Path

import pandas as pd

DATA_DIR = Path("data")
PROFILES_PATH = DATA_DIR / "profiles.parquet"
STATION_PATH = DATA_DIR / "station.parquet"
PICKLE_PATH = DATA_DIR / "sounding.pkl"

PROFILE_COLUMNS = [
    "time",
    "PRES",
    "HGHT",
    "TEMP",
    "DWPT",
    "RELH",
    "MIXR",
    "DRCT",
    "SKNT",
    "THTA",
    "THTE",
    "THTV",
]
PROFILE_VALUE_COLUMNS = PROFILE_COLUMNS[1:]

# 1 m/s = 1.943844 kt (international nautical mile)
MS_TO_KNOTS = 1.943844

STRING_STATION_COLUMNS = {"Observation time", "Station number"}


def load_profiles():
    if not PROFILES_PATH.exists():
        return pd.DataFrame(columns=PROFILE_COLUMNS)
    frame = pd.read_parquet(PROFILES_PATH)
    frame["time"] = pd.to_datetime(frame["time"])
    return frame


def load_station():
    if not STATION_PATH.exists():
        return pd.DataFrame(columns=["time"])
    frame = pd.read_parquet(STATION_PATH)
    frame["time"] = pd.to_datetime(frame["time"])
    return frame


def latest_time(station=None):
    if station is None:
        station = load_station()
    if station.empty or "time" not in station.columns:
        return None
    return pd.Timestamp(station["time"].max()).to_pydatetime()


def save_frames(profiles, station):
    """Write both tables, replacing the previous files only after a successful write."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    profiles = _prepare_profiles(profiles)
    station = _prepare_station(station)
    _write_atomic(profiles, PROFILES_PATH)
    _write_atomic(station, STATION_PATH)


def append_sounding(profiles, station, profile_rows, station_row):
    """Return new frames with one sounding added. Does not write to disk."""
    extra_profile = pd.DataFrame(profile_rows)
    extra_station = pd.DataFrame([station_row])
    if profiles.empty:
        profiles = extra_profile
    else:
        profiles = pd.concat([profiles, extra_profile], ignore_index=True)
    if station.empty:
        station = extra_station
    else:
        station = pd.concat([station, extra_station], ignore_index=True)
    return profiles, station


def frames_from_legacy(data):
    """Convert the historical dict-of-frames pickle into the two tables."""
    profile_frames = []
    station_rows = []
    for item in data.values():
        info = item["station_info"]
        timestamp = pd.to_datetime(info["Observation time"], format="%y%m%d/%H%M")
        table = item["table"].reindex(columns=PROFILE_VALUE_COLUMNS)
        numeric = table.apply(pd.to_numeric, errors="coerce")
        numeric.insert(0, "time", timestamp)
        profile_frames.append(numeric)

        row = {"time": timestamp, "Observation time": info["Observation time"]}
        for key, value in info.items():
            if key == "Observation time":
                continue
            row[key] = value
        station_rows.append(row)

    profiles = pd.concat(profile_frames, ignore_index=True) if profile_frames else pd.DataFrame(columns=PROFILE_COLUMNS)
    station = pd.DataFrame(station_rows) if station_rows else pd.DataFrame(columns=["time"])
    return profiles, station


def _prepare_profiles(profiles):
    frame = profiles.copy()
    frame["time"] = pd.to_datetime(frame["time"])
    for column in PROFILE_VALUE_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[PROFILE_COLUMNS]
    frame = frame.dropna(subset=["HGHT", "TEMP"], how="any")
    frame = frame.drop_duplicates(subset=["time", "PRES", "HGHT"], keep="last")
    return frame.sort_values(["time", "HGHT"], kind="mergesort").reset_index(drop=True)


def _prepare_station(station):
    frame = station.copy()
    frame["time"] = pd.to_datetime(frame["time"])
    frame = frame.drop_duplicates(subset=["time"], keep="last")
    for column in frame.columns:
        if column == "time" or column in STRING_STATION_COLUMNS:
            if column in STRING_STATION_COLUMNS:
                frame[column] = frame[column].apply(_as_text)
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce")
        original_present = frame[column].notna()
        if original_present.sum() == 0 or numeric.notna().sum() == original_present.sum():
            frame[column] = numeric
        else:
            frame[column] = frame[column].apply(_as_text)
    ordered = ["time"] + sorted(column for column in frame.columns if column != "time")
    return frame[ordered].sort_values("time", kind="mergesort").reset_index(drop=True)


def _as_text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return str(value)


def _write_atomic(frame, path):
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False, compression="zstd")
    temporary.replace(path)
