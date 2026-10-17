"""Shared fixtures for the noctilucent test suite."""

from pathlib import Path

import pandas as pd
import pytest

from src.sounding_store import PROFILE_COLUMNS

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES


@pytest.fixture
def fm35_html(fixtures_dir):
    return (fixtures_dir / "fm35_sounding.html").read_text(encoding="utf-8")


@pytest.fixture
def inventory_html(fixtures_dir):
    return (fixtures_dir / "fm35_inventory.html").read_text(encoding="utf-8")


@pytest.fixture
def archive_paths(tmp_path, monkeypatch):
    """Point sounding_store paths at a temporary data directory."""
    import src.sounding_store as store
    import src.sounding_scraper as scraper
    import src.clean_data as clean
    import src.sounding_plot as plot

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    profiles_path = data_dir / "profiles.parquet"
    station_path = data_dir / "station.parquet"
    pickle_path = data_dir / "sounding.pkl"

    for module in (store, scraper, clean):
        monkeypatch.setattr(module, "DATA_DIR", data_dir, raising=False)
        monkeypatch.setattr(module, "PROFILES_PATH", profiles_path, raising=False)
        monkeypatch.setattr(module, "STATION_PATH", station_path, raising=False)
        monkeypatch.setattr(module, "PICKLE_PATH", pickle_path, raising=False)

    web_dir = tmp_path / "app" / "data"
    monkeypatch.setattr(plot, "WEB_DIR", web_dir)

    return {
        "data_dir": data_dir,
        "profiles": profiles_path,
        "station": station_path,
        "pickle": pickle_path,
        "web_dir": web_dir,
    }


def make_profile_rows(stamp, n_levels=8, base_height=10.0):
    """Synthetic profile levels for one sounding."""
    rows = []
    for i in range(n_levels):
        height = base_height + i * 1000.0
        rows.append(
            {
                "time": stamp,
                "PRES": 1000.0 - i * 80.0,
                "HGHT": height,
                "TEMP": 15.0 - i * 6.5,
                "DWPT": 10.0 - i * 6.0,
                "RELH": max(20.0, 80.0 - i * 5.0),
                "MIXR": max(0.1, 7.0 - i * 0.8),
                "DRCT": (270.0 + i * 10.0) % 360.0,
                "SKNT": 10.0 + i,
                "THTA": 288.0 + i,
                "THTE": 300.0 + i,
                "THTV": 289.0 + i,
            }
        )
    return pd.DataFrame(rows, columns=PROFILE_COLUMNS)


def make_station_row(stamp, **extra):
    row = {
        "time": stamp,
        "Station number": "10113",
        "Observation time": pd.Timestamp(stamp).strftime("%y%m%d/%H%M"),
        "K index": 12.5,
        "Most Unstable CAPE": 40.0,
        "Virtual Lifted Index": 1.2,
        "Convective Available Potential Energy": 10.0,
        "Lifted index": 2.0,
    }
    row.update(extra)
    return row


@pytest.fixture
def sample_sounding():
    stamp = pd.Timestamp("2024-06-15 12:00:00")
    return make_profile_rows(stamp), make_station_row(stamp)
