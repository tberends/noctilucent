"""Export the sounding archive as compact files for the static site."""

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.sounding_store import load_profiles, load_station

WEB_DIR = Path("app/data")
HEIGHT_COUNT = 80
RECENT_DAYS = 60
ARCHIVE_COLUMNS = 1200
FIELDS = ["TEMP", "SKNT", "DRCT", "RELH", "MIXR", "THTA"]


def find_tropopause(heights, temps):
    """Lowest WMO tropopause: lapse rate above -2 C/km, and the same over the next 2 km."""
    if len(heights) < 2 or len(temps) < 2:
        return None

    sort_idx = np.argsort(heights)
    heights = heights[sort_idx]
    temps = temps[sort_idx]

    gradients = np.zeros(len(heights) - 1)
    for i in range(len(heights) - 1):
        height_diff = (heights[i + 1] - heights[i]) / 1000.0
        if height_diff > 0:
            gradients[i] = (temps[i + 1] - temps[i]) / height_diff

    for i in range(len(gradients)):
        if heights[i] > 5000 and gradients[i] > -2.0:
            next_levels = [j for j in range(i + 1, len(heights)) if heights[j] < heights[i] + 2000]
            if len(next_levels) > 0:
                mean_gradient = np.mean(
                    [gradients[j] for j in range(i, min(i + len(next_levels), len(gradients)))]
                )
                if mean_gradient > -2.0:
                    return float(heights[i])
    return None


def _interp_profile(heights, values, unique_heights):
    """Interpolate one sounding onto the height grid. Folded profiles are sorted first."""
    mask = np.isfinite(heights) & np.isfinite(values)
    if mask.sum() < 2:
        return np.full(len(unique_heights), np.nan)
    order = np.argsort(heights[mask], kind="mergesort")
    xp = heights[mask][order]
    fp = values[mask][order]
    unique_xp, unique_index = np.unique(xp, return_index=True)
    if len(unique_xp) < 2:
        return np.full(len(unique_heights), np.nan)
    return np.interp(unique_heights, unique_xp, fp[unique_index])


def _interp_direction(heights, directions, unique_heights):
    """Interpolate wind direction through sine and cosine so 359 and 1 stay neighbours."""
    mask = np.isfinite(heights) & np.isfinite(directions)
    if mask.sum() < 2:
        return np.full(len(unique_heights), np.nan)
    radians = np.deg2rad(directions[mask])
    sine = _interp_profile(heights[mask], np.sin(radians), unique_heights)
    cosine = _interp_profile(heights[mask], np.cos(radians), unique_heights)
    angle = np.rad2deg(np.arctan2(sine, cosine)) % 360
    angle[~np.isfinite(sine) | ~np.isfinite(cosine)] = np.nan
    return angle


def _dewpoint_c(temp_c, relative_humidity):
    """Magnus dewpoint. Returns None when humidity is missing or not positive."""
    if not np.isfinite(temp_c) or not np.isfinite(relative_humidity) or relative_humidity <= 0:
        return None
    humidity = min(float(relative_humidity), 100.0)
    a, b = 17.625, 243.04
    gamma = np.log(humidity / 100.0) + (a * temp_c) / (b + temp_c)
    return float((b * gamma) / (a - gamma))


def _epoch_ms(stamp):
    return int(np.datetime64(stamp, "ms").astype(np.int64))


def _iso_z(stamp):
    return pd.Timestamp(stamp).strftime("%Y-%m-%dT%H:%M:%SZ")


def _finite_or_none(value, digits):
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), digits)


def _series_list(values, digits):
    return [_finite_or_none(value, digits) for value in values]


def _build_grids(frame, times, heights):
    n_h = len(heights)
    n_t = len(times)
    grids = {name: np.full((n_h, n_t), np.nan, dtype=np.float32) for name in FIELDS}
    tropopause = np.full(n_t, np.nan, dtype=np.float64)
    index = {np.datetime64(stamp, "ns"): i for i, stamp in enumerate(times)}

    for stamp, group in frame.groupby("time", sort=False):
        column = index.get(np.datetime64(stamp, "ns"))
        if column is None:
            continue
        level_heights = group["HGHT"].to_numpy(dtype=float)
        temperature = group["TEMP"].to_numpy(dtype=float)
        grids["TEMP"][:, column] = _interp_profile(level_heights, temperature, heights)
        grids["SKNT"][:, column] = _interp_profile(
            level_heights, group["SKNT"].to_numpy(dtype=float), heights
        )
        grids["DRCT"][:, column] = _interp_direction(
            level_heights, group["DRCT"].to_numpy(dtype=float), heights
        )
        grids["RELH"][:, column] = _interp_profile(
            level_heights, group["RELH"].to_numpy(dtype=float), heights
        )
        grids["MIXR"][:, column] = _interp_profile(
            level_heights, group["MIXR"].to_numpy(dtype=float), heights
        )
        grids["THTA"][:, column] = _interp_profile(
            level_heights, group["THTA"].to_numpy(dtype=float), heights
        )
        finite = np.isfinite(level_heights) & np.isfinite(temperature)
        found = find_tropopause(level_heights[finite], temperature[finite])
        if found is not None:
            tropopause[column] = found
    return grids, tropopause


def _bin_edges(count, bins):
    edges = np.linspace(0, count, bins + 1).astype(int)
    pairs = []
    for start, end in zip(edges[:-1], edges[1:]):
        if end > start:
            pairs.append((int(start), int(end)))
    return pairs


def _nanmean_bins(values, edges):
    columns = []
    for start, end in edges:
        with np.errstate(invalid="ignore", divide="ignore"):
            block = values[:, start:end]
            if not np.isfinite(block).any():
                columns.append(np.full(values.shape[0], np.nan))
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    columns.append(np.nanmean(block, axis=1))
    return np.stack(columns, axis=1).astype(np.float32)


def _circular_mean_bins(degrees, edges):
    columns = []
    for start, end in edges:
        block = degrees[:, start:end]
        if not np.isfinite(block).any():
            columns.append(np.full(degrees.shape[0], np.nan))
            continue
        radians = np.deg2rad(block)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            sine = np.nanmean(np.sin(radians), axis=1)
            cosine = np.nanmean(np.cos(radians), axis=1)
        angle = np.rad2deg(np.arctan2(sine, cosine)) % 360
        angle[~np.isfinite(sine) | ~np.isfinite(cosine)] = np.nan
        columns.append(angle)
    return np.stack(columns, axis=1).astype(np.float32)


def _median_bins(values, edges):
    columns = []
    for start, end in edges:
        block = values[start:end]
        if not np.isfinite(block).any():
            columns.append(np.nan)
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                columns.append(np.nanmedian(block))
    return np.asarray(columns, dtype=np.float64)


def _downsample(times, grids, tropopause, limit):
    count = len(times)
    if count <= limit:
        return times, grids, tropopause
    edges = _bin_edges(count, limit)
    reduced = {}
    for name, values in grids.items():
        if name == "DRCT":
            reduced[name] = _circular_mean_bins(values, edges)
        else:
            reduced[name] = _nanmean_bins(values, edges)
    ends = [times[end - 1] for start, end in edges]
    return np.asarray(ends, dtype="datetime64[ns]"), reduced, _median_bins(tropopause, edges)


def _write_grid(path, grids):
    parts = [np.ascontiguousarray(grids[name], dtype="<f4").ravel(order="C") for name in FIELDS]
    blob = np.concatenate(parts)
    path.write_bytes(blob.tobytes())
    return blob.nbytes


def _index_payload(station):
    ordered = station.sort_values("time")
    times = ordered["time"].to_numpy(dtype="datetime64[ns]")

    def column(name, digits):
        if name not in ordered.columns:
            return [None] * len(ordered)
        values = pd.to_numeric(ordered[name], errors="coerce").to_numpy(dtype=float)
        return _series_list(values, digits)

    return {
        "times": [_epoch_ms(stamp) for stamp in times],
        "k": column("K index", 1),
        "cape": column("Convective Available Potential Energy", 0),
        "mucape": column("Most Unstable CAPE", 0),
        "lifted": column("Lifted index", 1),
        "virtualLifted": column("Virtual Lifted Index", 1),
    }


def _latest_summary(times, grids, tropopause, station):
    stamp = times[-1]
    temp = float(grids["TEMP"][0, -1])
    humidity = float(grids["RELH"][0, -1])
    row = station.loc[station["time"] == pd.Timestamp(stamp)]
    k_index = None
    mucape = None
    if not row.empty:
        if "K index" in row.columns:
            k_index = _finite_or_none(pd.to_numeric(row["K index"], errors="coerce").iloc[-1], 1)
        if "Most Unstable CAPE" in row.columns:
            mucape = _finite_or_none(
                pd.to_numeric(row["Most Unstable CAPE"], errors="coerce").iloc[-1], 0
            )
    return {
        "time": _iso_z(stamp),
        "temp": _finite_or_none(temp, 1),
        "dewpoint": _finite_or_none(_dewpoint_c(temp, humidity), 1),
        "windSpeed": _finite_or_none(grids["SKNT"][0, -1], 0),
        "windDir": _finite_or_none(grids["DRCT"][0, -1], 0),
        "tropopause": _finite_or_none(tropopause[-1], 0),
        "kIndex": k_index,
        "mucape": mucape,
    }


def _pack_view(times, grids, tropopause):
    return {
        "times": [_iso_z(stamp) for stamp in times],
        "tropopause": _series_list(tropopause, 0),
    }


def export_site():
    """Write app/data/meta.json, recent.bin and archive.bin from the Parquet archive."""
    profiles = load_profiles()
    station = load_station()
    if profiles.empty:
        raise FileNotFoundError("Geen profieldata in data/profiles.parquet")

    valid = profiles["HGHT"].notna() & profiles["TEMP"].notna()
    frame = profiles.loc[valid].sort_values(["time", "HGHT"])
    times = np.sort(frame["time"].unique().astype("datetime64[ns]"))
    observed = frame.loc[frame["HGHT"] >= 0, "HGHT"].to_numpy(dtype=float)
    low = float(np.nanmin(observed))
    high = float(np.nanmax(observed))
    heights = np.linspace(low, high, HEIGHT_COUNT)

    grids, tropopause = _build_grids(frame, times, heights)
    cutoff = times[-1] - np.timedelta64(RECENT_DAYS, "D")
    recent_index = np.flatnonzero(times >= cutoff)
    if len(recent_index) == 0:
        recent_index = np.arange(len(times))
    recent_slice = slice(int(recent_index[0]), int(recent_index[-1]) + 1)
    recent_times = times[recent_slice]
    recent_grids = {name: values[:, recent_slice] for name, values in grids.items()}
    recent_tropopause = tropopause[recent_slice]

    archive_times, archive_grids, archive_tropopause = _downsample(
        times, grids, tropopause, ARCHIVE_COLUMNS
    )

    WEB_DIR.mkdir(parents=True, exist_ok=True)
    recent_bytes = _write_grid(WEB_DIR / "recent.bin", recent_grids)
    archive_bytes = _write_grid(WEB_DIR / "archive.bin", archive_grids)

    station_number = "10113"
    if "Station number" in station.columns and station["Station number"].notna().any():
        station_number = str(station["Station number"].dropna().iloc[0])

    meta = {
        "station": station_number,
        "place": "Norderney",
        "heights": [round(float(height), 1) for height in heights],
        "fields": FIELDS,
        "latest": _latest_summary(recent_times, recent_grids, recent_tropopause, station),
        "recent": {
            "file": "app/data/recent.bin",
            **_pack_view(recent_times, recent_grids, recent_tropopause),
        },
        "archive": {
            "file": "app/data/archive.bin",
            **_pack_view(archive_times, archive_grids, archive_tropopause),
        },
        "indices": _index_payload(station),
    }
    (WEB_DIR / "meta.json").write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
    print(
        f"Export: recent {len(recent_times)} oplatingen ({recent_bytes} bytes), "
        f"archief {len(archive_times)} kolommen ({archive_bytes} bytes)."
    )


def plot_sounding():
    """Backward-compatible name used by main.py."""
    export_site()


if __name__ == "__main__":
    export_site()
