"""Tests for Parquet archive read/write helpers."""

from datetime import datetime

import pandas as pd
import pytest

from src.sounding_store import (
    PROFILE_COLUMNS,
    append_sounding,
    frames_from_legacy,
    latest_time,
    load_profiles,
    load_station,
    save_frames,
)
from tests.conftest import make_profile_rows, make_station_row


def test_load_empty_archive_returns_typed_frames(archive_paths):
    profiles = load_profiles()
    station = load_station()
    assert list(profiles.columns) == PROFILE_COLUMNS
    assert profiles.empty
    assert list(station.columns) == ["time"]
    assert station.empty
    assert latest_time(station) is None


def test_save_and_load_round_trip(archive_paths, sample_sounding):
    profile_rows, station_row = sample_sounding
    profiles, station = append_sounding(
        pd.DataFrame(columns=PROFILE_COLUMNS),
        pd.DataFrame(columns=["time"]),
        profile_rows,
        station_row,
    )
    save_frames(profiles, station)

    loaded_profiles = load_profiles()
    loaded_station = load_station()
    assert len(loaded_station) == 1
    assert loaded_profiles["time"].nunique() == 1
    assert latest_time(loaded_station) == datetime(2024, 6, 15, 12, 0)
    assert float(loaded_station.iloc[0]["K index"]) == pytest.approx(12.5)


def test_save_frames_is_atomic(archive_paths, sample_sounding):
    profile_rows, station_row = sample_sounding
    profiles, station = append_sounding(
        pd.DataFrame(columns=PROFILE_COLUMNS),
        pd.DataFrame(columns=["time"]),
        profile_rows,
        station_row,
    )
    save_frames(profiles, station)
    assert archive_paths["profiles"].exists()
    assert archive_paths["station"].exists()
    assert not list(archive_paths["data_dir"].glob("*.tmp"))


def test_prepare_drops_incomplete_levels_and_duplicates(archive_paths):
    stamp = pd.Timestamp("2024-01-01 00:00:00")
    rows = make_profile_rows(stamp, n_levels=3)
    rows.loc[1, "TEMP"] = pd.NA
    duplicate = rows.iloc[[0]].copy()
    duplicate["SKNT"] = 99.0
    profiles = pd.concat([rows, duplicate], ignore_index=True)
    station = pd.DataFrame([make_station_row(stamp)])
    save_frames(profiles, station)

    loaded = load_profiles()
    # Row with missing TEMP is gone; duplicate (time, PRES, HGHT) keeps last SKNT.
    assert loaded["TEMP"].notna().all()
    kept = loaded.loc[
        (loaded["PRES"] == rows.iloc[0]["PRES"]) & (loaded["HGHT"] == rows.iloc[0]["HGHT"])
    ]
    assert len(kept) == 1
    assert float(kept.iloc[0]["SKNT"]) == pytest.approx(99.0)


def test_append_sounding_does_not_write_disk(archive_paths, sample_sounding):
    profile_rows, station_row = sample_sounding
    profiles, station = append_sounding(
        pd.DataFrame(columns=PROFILE_COLUMNS),
        pd.DataFrame(columns=["time"]),
        profile_rows,
        station_row,
    )
    assert len(station) == 1
    assert not archive_paths["profiles"].exists()


def test_frames_from_legacy_converts_observation_time():
    stamp = datetime(2024, 6, 15, 12, 0)
    table = make_profile_rows(pd.Timestamp(stamp)).drop(columns=["time"])
    legacy = {
        "2024-06-15 12:00": {
            "table": table,
            "station_info": {
                "Observation time": "240615/1200",
                "Station number": "10113",
                "K index": 8.0,
            },
        }
    }
    profiles, station = frames_from_legacy(legacy)
    assert latest_time(station) == stamp
    assert float(station.iloc[0]["K index"]) == pytest.approx(8.0)
    assert set(PROFILE_COLUMNS).issubset(profiles.columns)


def test_station_deduplicates_on_time(archive_paths):
    stamp = pd.Timestamp("2024-06-15 12:00:00")
    first = make_station_row(stamp, **{"K index": 1.0})
    second = make_station_row(stamp, **{"K index": 2.0})
    profiles = make_profile_rows(stamp)
    station = pd.DataFrame([first, second])
    save_frames(profiles, station)
    loaded = load_station()
    assert len(loaded) == 1
    assert float(loaded.iloc[0]["K index"]) == pytest.approx(2.0)
