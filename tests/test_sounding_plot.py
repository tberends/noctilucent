"""Tests for export numerics: tropopause, interpolation, dewpoint, grids."""

import json

import numpy as np
import pandas as pd
import pytest

from src.sounding_plot import (
    ANOMALY_SOURCES,
    ARCHIVE_COLUMNS,
    CORE_FIELDS,
    FIELDS,
    HEIGHT_COUNT,
    _bin_edges,
    _dewpoint_c,
    _downsample,
    _field_anomaly,
    _interp_direction,
    _interp_profile,
    _monthly_climate,
    _write_grid,
    export_site,
    find_tropopause,
)
from src.sounding_store import PROFILE_COLUMNS, append_sounding, save_frames
from tests.conftest import make_profile_rows, make_station_row


def test_find_tropopause_returns_none_for_short_or_shallow_profiles():
    assert find_tropopause(np.array([0.0, 1000.0]), np.array([15.0, 8.0])) is None
    heights = np.linspace(0, 4000, 9)
    temps = 15.0 - 0.0065 * heights
    assert find_tropopause(heights, temps) is None


def test_find_tropopause_wmo_lowest_stable_layer_above_5_km():
    # Troposphere cools at 6.5 C/km, then becomes isothermal from 10 km.
    heights = np.arange(0.0, 14001.0, 500.0)
    temps = np.empty_like(heights)
    for i, height in enumerate(heights):
        if height <= 10000:
            temps[i] = 15.0 - 6.5 * (height / 1000.0)
        else:
            temps[i] = 15.0 - 6.5 * 10.0
    tropopause = find_tropopause(heights, temps)
    assert tropopause == pytest.approx(10000.0)


def test_find_tropopause_skips_thin_inversion_above_5_km():
    # 500 m spacing: short warm spike near 6 km, then cooling to an isothermal layer at 10 km.
    heights = np.arange(0.0, 14001.0, 500.0)
    temps = np.empty_like(heights)
    for i, height in enumerate(heights):
        if height < 6000:
            temps[i] = 15.0 - 6.5 * (height / 1000.0)
        elif height < 6500:
            temps[i] = 15.0 - 6.5 * 6.0 + 3.0
        elif height < 10000:
            temps[i] = (15.0 - 6.5 * 6.0) - 6.5 * ((height - 6000.0) / 1000.0)
        else:
            temps[i] = 15.0 - 6.5 * 10.0
    tropopause = find_tropopause(heights, temps)
    assert tropopause == pytest.approx(10000.0)
    assert tropopause != pytest.approx(6000.0)


def test_interp_profile_handles_unsorted_and_duplicate_heights():
    heights = np.array([2000.0, 0.0, 1000.0, 1000.0])
    values = np.array([5.0, 15.0, 10.0, 11.0])
    grid = np.array([0.0, 1000.0, 2000.0])
    result = _interp_profile(heights, values, grid)
    assert result[0] == pytest.approx(15.0)
    assert result[2] == pytest.approx(5.0)
    assert np.isfinite(result[1])


def test_interp_profile_returns_nan_grid_with_too_few_points():
    result = _interp_profile(np.array([0.0]), np.array([10.0]), np.array([0.0, 1000.0]))
    assert np.isnan(result).all()


def test_interp_direction_crosses_north_without_wrap_artifact():
    heights = np.array([0.0, 1000.0, 2000.0])
    directions = np.array([350.0, 0.0, 10.0])
    grid = np.array([500.0, 1500.0])
    result = _interp_direction(heights, directions, grid)
    assert result[0] == pytest.approx(355.0, abs=1.0)
    assert result[1] == pytest.approx(5.0, abs=1.0)


def test_dewpoint_magnus_formula_and_guards():
    assert _dewpoint_c(20.0, 50.0) == pytest.approx(9.27, abs=0.05)
    assert _dewpoint_c(10.0, 0.0) is None
    assert _dewpoint_c(float("nan"), 50.0) is None
    # Humidity above 100% is capped.
    assert _dewpoint_c(10.0, 150.0) == pytest.approx(_dewpoint_c(10.0, 100.0))


def test_monthly_climate_and_anomaly_shape():
    times = np.array(
        [
            "2024-01-01T00:00",
            "2024-01-01T12:00",
            "2024-02-01T00:00",
            "2024-02-01T12:00",
        ],
        dtype="datetime64[ns]",
    )
    grid = np.array(
        [
            [1.0, 3.0, 10.0, 14.0],
            [2.0, 4.0, 20.0, 24.0],
        ],
        dtype=np.float32,
    )
    climate = _monthly_climate(grid, times)
    assert climate.shape == (12, 2)
    assert climate[0, 0] == pytest.approx(2.0)
    assert climate[1, 1] == pytest.approx(22.0)
    anomaly = _field_anomaly(grid, times, climate)
    assert anomaly[0, 0] == pytest.approx(-1.0)
    assert anomaly[0, 1] == pytest.approx(1.0)


def test_downsample_uses_circular_mean_for_direction():
    times = np.arange("2024-01-01", "2024-01-09", dtype="datetime64[D]").astype(
        "datetime64[ns]"
    )
    grids = {
        "TEMP": np.ones((2, len(times)), dtype=np.float32),
        "DRCT": np.tile(np.array([350.0, 10.0], dtype=np.float32), (2, len(times) // 2)),
    }
    for name in CORE_FIELDS:
        grids.setdefault(name, np.ones((2, len(times)), dtype=np.float32))
    tropopause = np.full(len(times), 10000.0)
    reduced_times, reduced_grids, reduced_trop = _downsample(
        times, grids, tropopause, limit=2
    )
    assert len(reduced_times) == 2
    # Mean of 350 and 10 should stay near north, not near 180.
    direction = float(reduced_grids["DRCT"][0, 0]) % 360.0
    assert min(direction, 360.0 - direction) <= 5.0
    assert np.isfinite(reduced_trop).all()


def test_bin_edges_cover_full_range_without_empty_bins():
    edges = _bin_edges(5, 3)
    assert edges[0][0] == 0
    assert edges[-1][1] == 5
    assert all(end > start for start, end in edges)


def test_write_grid_byte_layout_matches_field_order(tmp_path):
    n_h, n_t = 4, 3
    grids = {name: np.full((n_h, n_t), float(i), dtype=np.float32) for i, name in enumerate(FIELDS)}
    path = tmp_path / "grid.bin"
    nbytes = _write_grid(path, grids)
    assert nbytes == n_h * n_t * len(FIELDS) * 4
    raw = np.frombuffer(path.read_bytes(), dtype="<f4")
    assert raw[: n_h * n_t][0] == pytest.approx(0.0)  # TEMP
    assert raw[n_h * n_t] == pytest.approx(1.0)  # SKNT block start


def test_export_site_writes_meta_and_bins(archive_paths):
    stamps = pd.to_datetime(
        ["2024-05-01 00:00", "2024-05-01 12:00", "2024-06-01 00:00", "2024-06-01 12:00"]
    )
    profiles = pd.DataFrame(columns=PROFILE_COLUMNS)
    station = pd.DataFrame(columns=["time"])
    for stamp in stamps:
        profiles, station = append_sounding(
            profiles,
            station,
            make_profile_rows(stamp, n_levels=12, base_height=10.0),
            make_station_row(stamp),
        )
    # Stretch the top so the height grid has range.
    top = profiles["HGHT"].max()
    profiles.loc[profiles["HGHT"] == top, "HGHT"] = 20000.0
    save_frames(profiles, station)

    export_site()

    meta_path = archive_paths["web_dir"] / "meta.json"
    recent = archive_paths["web_dir"] / "recent.bin"
    archive = archive_paths["web_dir"] / "archive.bin"
    assert meta_path.exists()
    assert recent.exists()
    assert archive.exists()

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["station"] == "10113"
    assert meta["place"] == "Norderney"
    assert meta["fields"] == FIELDS
    assert len(meta["heights"]) == HEIGHT_COUNT
    assert len(meta["tempClimate"]) == 12
    assert len(meta["tempClimate"][0]) == HEIGHT_COUNT
    assert set(meta["latest"]) >= {
        "time",
        "temp",
        "dewpoint",
        "windSpeed",
        "windDir",
        "tropopause",
        "kIndex",
        "mucape",
    }
    assert set(meta["indices"]) == {
        "times",
        "k",
        "cape",
        "mucape",
        "lifted",
        "virtualLifted",
    }
    n_recent = len(meta["recent"]["times"])
    n_archive = len(meta["archive"]["times"])
    assert recent.stat().st_size == HEIGHT_COUNT * n_recent * len(FIELDS) * 4
    assert archive.stat().st_size == HEIGHT_COUNT * n_archive * len(FIELDS) * 4
    assert n_archive <= ARCHIVE_COLUMNS
    assert set(ANOMALY_SOURCES) <= set(FIELDS)


def test_export_site_requires_profiles(archive_paths):
    with pytest.raises(FileNotFoundError):
        export_site()
