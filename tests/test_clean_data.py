"""Tests for observation-time checks and archive cleaning helpers."""

from datetime import datetime

import pandas as pd

from src.clean_data import (
    analyze_timestamps,
    check_temporal_consistency,
    clean_data,
    station_as_records,
)
from src.sounding_store import PROFILE_COLUMNS, append_sounding, load_station, save_frames
from tests.conftest import make_profile_rows, make_station_row


def _entry(key, observation_time, **extra):
    info = {"Observation time": observation_time}
    info.update(extra)
    return {key: {"station_info": info}}


def test_analyze_timestamps_accepts_fm35_hours():
    data = {}
    data.update(_entry("2024-06-15 00:00", "240615/0000"))
    data.update(_entry("2024-06-15 12:00", "240615/1200"))
    data.update(_entry("2024-06-15 06:00", "240615/0600"))
    data.update(_entry("2024-06-15 18:00", "240615/1800"))
    corrupt, valid, issues = analyze_timestamps(data)
    assert corrupt == []
    assert len(valid) == 4
    assert issues == {}


def test_analyze_timestamps_flags_unusual_hour_and_bad_parse():
    data = {}
    data.update(_entry("2024-06-15 03:00", "240615/0300"))
    data.update(_entry("2024-06-15 12:00", "not-a-time"))
    data.update(_entry("broken", "240615/1200"))  # key unused; observation drives parse
    # Missing observation time
    data["missing"] = {"station_info": {"Station number": "10113"}}

    corrupt, valid, issues = analyze_timestamps(data)
    assert len(valid) == 1
    assert any("Ongebruikelijk uur" in entry["issue"] for entry in corrupt)
    assert any("Kan tijdstempel niet parsen" in entry["issue"] for entry in corrupt)
    assert any(entry["issue"] == "Missing Observation time" for entry in corrupt)
    assert issues


def test_check_temporal_consistency_flags_jump_larger_than_one_week():
    valid = [
        {"key": "older", "timestamp": datetime(2024, 1, 1, 0, 0)},
        {"key": "gap", "timestamp": datetime(2024, 1, 20, 0, 0)},
    ]
    suspicious = check_temporal_consistency(valid)
    assert len(suspicious) == 1
    assert suspicious[0]["key"] == "older"


def test_check_temporal_consistency_accepts_normal_spacing():
    valid = [
        {"key": "a", "timestamp": datetime(2024, 6, 15, 0, 0)},
        {"key": "b", "timestamp": datetime(2024, 6, 15, 12, 0)},
        {"key": "c", "timestamp": datetime(2024, 6, 16, 0, 0)},
    ]
    assert check_temporal_consistency(valid) == []


def test_clean_data_dry_run_preserves_input():
    data = _entry("2024-06-15 12:00", "240615/1200")
    data.update(_entry("2024-06-15 03:00", "240615/0300"))
    result = clean_data(data, ["2024-06-15 03:00"], dry_run=True)
    assert result is None
    assert "2024-06-15 03:00" in data


def test_clean_data_removes_keys_when_not_dry_run():
    data = _entry("keep", "240615/1200")
    data.update(_entry("drop", "240615/0300"))
    cleaned = clean_data(data, ["drop"], dry_run=False)
    assert set(cleaned) == {"keep"}


def test_station_as_records_and_parquet_clean_round_trip(archive_paths):
    good = pd.Timestamp("2024-06-15 12:00:00")
    bad = pd.Timestamp("2024-06-15 03:00:00")
    profiles = pd.DataFrame(columns=PROFILE_COLUMNS)
    station = pd.DataFrame(columns=["time"])
    for stamp in (good, bad):
        profiles, station = append_sounding(
            profiles,
            station,
            make_profile_rows(stamp),
            make_station_row(stamp),
        )
    save_frames(profiles, station)

    records = station_as_records(load_station())
    assert "2024-06-15 12:00" in records
    assert "2024-06-15 03:00" in records
    corrupt, valid, _issues = analyze_timestamps(records)
    assert any(entry["key"] == "2024-06-15 03:00" for entry in corrupt)
    assert any(entry["key"] == "2024-06-15 12:00" for entry in valid)
