"""Figures of the Task 4 pigments, for a first look before the diversity analysis.

    python task4/scripts/pigment_figures.py

Writes to task4/figures:
- <region>/<pigment>_years.png, from task4/data/pigments/<region>_monthly.nc: the mean of each
  complete year, one map per year;
- <region>/periods.png: every pigment (rows) averaged over PERIODS equal periods of years (columns);
- stations/<station>.png, from task4/data/pigments/stations_daily.nc: one panel per pigment, with
  the median of each month over the pixels around the station and its 12-month running mean.
Months with fewer than MIN_DAYS days of data are left out. A year's mean is over its months with
data, so cloudy winters weigh less. All the maps of a pigment share one log colour scale; grey is
land or no data, and circles are the stations.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import xarray as xr
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm  # noqa: E402

PIGMENT_DIR = Path("task4/data/pigments")
STATIONS_CONFIG = Path("task4/configs/station_matchups.yaml")
OUTPUT_DIR = Path("task4/figures")
MIN_DAYS = 3
PERIODS = 4

# One hue, from light (low) to dark (high)
BLUES = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
CMAP = LinearSegmentedColormap.from_list("blues", BLUES)
CMAP.set_bad("#c8c8c4")


def log_ticks(vmin: float, vmax: float) -> list[float]:
    """Round values for a log axis: 1, 2 and 5 of each decade, or finer steps if fewer than 3 fit."""
    decades = 10.0 ** np.arange(np.floor(np.log10(vmin)), np.ceil(np.log10(vmax)) + 1)
    for steps in ([1, 2, 5], [1, 1.5, 2, 3, 5, 7], [1, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 9]):
        ticks = [tick for tick in np.outer(decades, steps).ravel() if vmin <= tick <= vmax]
        if len(ticks) >= 3:
            break
    return ticks


# Maps

def annual_means(pigment: xr.DataArray) -> xr.DataArray:
    """Mean of each calendar year that the record covers entirely."""
    months = pigment["time"].dt.year.to_series().value_counts()
    return pigment.groupby("time.year").mean().sel(year=sorted(months.index[months == 12]))


def period_means(annual: xr.DataArray) -> xr.DataArray:
    """Mean of the annual means over PERIODS consecutive periods of (nearly) equal length."""
    blocks = np.array_split(annual["year"].values, PERIODS)
    labels = [f"{block[0]}-{block[-1]}" for block in blocks for _ in block]
    return annual.assign_coords(period=("year", labels)).groupby("period").mean()


def height_ratio(data: xr.DataArray) -> float:
    """Height / width of a map of the data."""
    lat, lon = data["latitude"].values, data["longitude"].values
    return float(np.ptp(lat) / (np.ptp(lon) * np.cos(np.deg2rad(lat.mean()))))


def draw(ax, field: xr.DataArray, norm: LogNorm, stations: dict, title: str):
    mesh = ax.pcolormesh(field["longitude"], field["latitude"], field, cmap=CMAP, norm=norm, shading="nearest")
    ax.set_aspect(1 / np.cos(np.deg2rad(float(field["latitude"].mean()))))
    for lat, lon in stations.values():
        ax.plot(lon, lat, "o", ms=4, mfc="none", mec="#1a1a19", mew=0.8)
    ax.set_title(title, fontsize=8)
    ax.set_xticks([])
    ax.set_yticks([])
    return mesh


def colorbar(fig, mesh, axes, label: str) -> None:
    bar = fig.colorbar(mesh, ax=axes, extend="both", shrink=0.8, label=label)
    ticks = log_ticks(mesh.norm.vmin, mesh.norm.vmax)
    bar.minorticks_off()
    bar.set_ticks(ticks, labels=[f"{tick:g}" for tick in ticks])


def plot_years(annual: xr.DataArray, norm: LogNorm, stations: dict, title: str, path: Path) -> None:
    ncols = 7
    nrows = -(-annual.sizes["year"] // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 1.9 + 1, nrows * 1.9 * height_ratio(annual) + 0.6),
                             squeeze=False, layout="constrained")
    for ax, year in zip(axes.flat, annual["year"].values):
        mesh = draw(ax, annual.sel(year=year), norm, stations, str(year))
    for ax in axes.flat[annual.sizes["year"]:]:
        ax.axis("off")
    colorbar(fig, mesh, axes, "mg m$^{-3}$")
    fig.suptitle(title)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_periods(periods: dict, norms: dict, stations: dict, title: str, path: Path) -> None:
    first = next(iter(periods.values()))
    labels = first["period"].values
    fig, axes = plt.subplots(len(periods), len(labels),
                             figsize=(len(labels) * 2.2 + 1.4, len(periods) * 2.2 * height_ratio(first) + 0.6),
                             squeeze=False, layout="constrained")
    for i, (name, means) in enumerate(periods.items()):
        for ax, label in zip(axes[i], labels):
            mesh = draw(ax, means.sel(period=label), norms[name], stations, label if i == 0 else "")
        colorbar(fig, mesh, axes[i], f"{name} (mg m$^{{-3}}$)")
    fig.suptitle(title)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def region_maps(path: Path, stations: dict) -> None:
    region = path.name.removesuffix("_monthly.nc")
    output_dir = OUTPUT_DIR / region
    output_dir.mkdir(parents=True, exist_ok=True)
    periods, norms = {}, {}
    with xr.open_dataset(path) as data:
        lats, lons = data["latitude"].values, data["longitude"].values
        inside = {name: (lat, lon) for name, (lat, lon) in stations.items()
                  if lats.min() <= lat <= lats.max() and lons.min() <= lon <= lons.max()}
        well_sampled = data["valid_days"] >= MIN_DAYS
        for name in data.drop_vars("valid_days").data_vars:
            annual = annual_means(data[name].where(well_sampled).load())
            norms[name] = LogNorm(*np.nanpercentile(annual, [2, 98]))
            long_name = data[name].attrs.get("long_name", name)
            plot_years(annual, norms[name], inside, f"{long_name.capitalize()} ({name}), annual mean, {region}",
                       output_dir / f"{name}_years.png")
            periods[name] = period_means(annual)
    plot_periods(periods, norms, inside, f"Pigments, mean of each period, {region}", output_dir / "periods.png")
    print(f"{output_dir}: {len(periods)} pigments, {annual.sizes['year']} years")


# Station series

def monthly_medians(pigments: xr.Dataset) -> xr.Dataset:
    """Median of each month over the pixels and days with data around each station."""
    days = pigments["chl_a"].notnull().any(["lat_pixel", "lon_pixel"]).resample(time="MS").sum()
    medians = pigments.resample(time="MS").median(dim=["time", "lat_pixel", "lon_pixel"])
    return medians.where(days >= MIN_DAYS)


def plot_station(monthly: xr.Dataset, station: str, path: Path) -> None:
    fig, axes = plt.subplots(len(monthly.data_vars), 1, figsize=(10, 1.1 * len(monthly.data_vars) + 0.8),
                             sharex=True, layout="constrained")
    for ax, name in zip(axes, monthly.data_vars):
        series = monthly[name].sel(station=station)
        ax.plot(series["time"], series, color=BLUES[1], lw=0.8, label="monthly median")
        running = series.rolling(time=12, center=True, min_periods=6).mean()
        ax.plot(running["time"], running, color=BLUES[3], lw=1.8, label="12-month running mean")
        ax.set_yscale("log")
        ticks = log_ticks(*ax.get_ylim())
        ax.minorticks_off()
        ax.set_yticks(ticks, labels=[f"{tick:g}" for tick in ticks])
        ax.set_ylabel(name)
        ax.grid(axis="y", color="#e5e5e2", lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside upper right", ncol=2, frameon=False, fontsize=8)
    fig.suptitle(f"Pigments around {station}, mg m$^{{-3}}$")
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> int:
    stations = yaml.safe_load(STATIONS_CONFIG.read_text(encoding="utf-8"))["stations"]
    for path in sorted(PIGMENT_DIR.glob("*_monthly.nc")):
        region_maps(path, stations)

    with xr.open_dataset(PIGMENT_DIR / "stations_daily.nc") as pigments:
        monthly = monthly_medians(pigments.load())
    output_dir = OUTPUT_DIR / "stations"
    output_dir.mkdir(parents=True, exist_ok=True)
    for station in monthly["station"].values:
        plot_station(monthly, station, output_dir / f"{station}.png")
    print(f"{output_dir}: {', '.join(monthly['station'].values)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
