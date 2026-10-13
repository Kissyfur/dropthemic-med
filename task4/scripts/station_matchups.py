"""Matchup cubes for fixed stations on every day of a period, for prediction rather than training.

    python task4/scripts/station_matchups.py task4/configs/station_matchups.yaml [--station NAME ...]

The config is a copernicus-matchup data config plus four keys read here: `stations`
(name: [lat, lon]), `period` (start, end), `box_margin` (degrees) and `output_root`. For each
station, under <output_root>/<station>, the script
1. writes a table with one row per day and an empty target column,
2. downloads each product once over a box around the station, for the whole period,
3. runs the download, matchup and preprocess stages on that box as a local product,
then concatenates the stations' cubes into <output_root>/datasets.

Stations run one at a time to keep memory bounded. With per-cube quantile floors
(`positive_quantile_dims: [time, lat, lon]`) that gives the same cubes as one joint run. A
station whose matchups exist is not matched again; delete its directory after changing the
period, the stations or the matchup window. Transform settings only need a rerun.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import logging
from pathlib import Path

import copernicusmarine as cm
import pandas as pd
import xarray as xr
import yaml

from copernicus_matchup import DataConfig, RunLayout, build_dataset

logger = logging.getLogger("station_matchups")
DATA_SECTIONS = ("target", "products", "matchup", "preprocess", "regrid")


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _as_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


def write_station_table(path: Path, station: str, lat: float, lon: float, start, end, target: str) -> int:
    """One row per day, Id `<station>_<yyyymmdd>`, and an empty target column."""
    days = pd.date_range(start, end, freq="D")
    table = pd.DataFrame(
        {
            "Id": [f"{station}_{day:%Y%m%d}" for day in days],
            "station": station,
            "lat": lat,
            "lon": lon,
            "time": days,
            target: float("nan"),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False)
    return len(table)


def download_box(product: dict, lat: float, lon: float, margin: float, start, end, path: Path) -> None:
    """The product over the station +/- `margin` degrees, for the whole period, saved at `path`."""
    if path.exists():
        logger.info("%s: box already downloaded", path)
        return
    dataset_ids = _as_list(product.get("dataset_ids", product.get("dataset_id")))
    if len(dataset_ids) > 1:
        logger.warning("%s: only the first dataset id, %s, is downloaded", product["name"], dataset_ids[0])
    logger.info("%s: downloading %s around %.3f, %.3f", path, dataset_ids[0], lat, lon)
    cm.subset(
        dataset_id=dataset_ids[0],
        variables=product.get("variables") or None,
        minimum_latitude=lat - margin,
        maximum_latitude=lat + margin,
        minimum_longitude=lon - margin,
        maximum_longitude=lon + margin,
        start_datetime=f"{start}T00:00:00",
        end_datetime=f"{end}T00:00:00",
        output_directory=path.parent,
        output_filename=path.name,
        netcdf_compression_level=1,
        overwrite=True,
        disable_progress_bar=True,
    )


def run_station(config: dict, station: str, lat: float, lon: float, root: Path) -> Path:
    start, end = _as_date(config["period"]["start"]), _as_date(config["period"]["end"])
    margin = float(config.get("box_margin", 0.15))
    data = copy.deepcopy({key: config[key] for key in DATA_SECTIONS if key in config})
    layout = RunLayout(root / station)

    table = layout.root / "stations.csv"
    rows = write_station_table(table, station, lat, lon, start, end, str(data["target"]["target_column"]))
    logger.info("%s: %d days, %s to %s", station, rows, start, end)
    data["target"]["path"] = str(table)
    data["target"]["keep_missing_targets"] = True

    matchup = data.get("matchup", {})
    for product in data["products"]:
        window = {**matchup, **product.get("matchup", {})}
        largest = max(float(window.get("lat_window", 0.06)), float(window.get("lon_window", 0.06)))
        if margin <= largest:
            raise ValueError(f"box_margin {margin} must exceed the matchup window {largest}.")
        # The time window reaches this far beyond the first and last day.
        pad = dt.timedelta(days=int(window.get("time_window_days", 1)) + 1)
        # Saved where the download stage looks for a local product, so it is not copied again.
        box = layout.raw_product(product["name"])
        download_box(product, lat, lon, margin, start - pad, end + pad, box)
        product["source"], product["source_path"] = "local", str(box)

    build_dataset(DataConfig.from_dict(data), layout.root)
    return layout.datasets


def combine(dataset_dirs: list[Path], output_dir: Path) -> None:
    """Concatenate the stations' cubes along Id, one file per artifact."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(path.stem for path in dataset_dirs[0].glob("*.nc")):
        parts = [xr.load_dataarray(d / f"{name}.nc") for d in dataset_dirs if (d / f"{name}.nc").exists()]
        # exact: every station must share the cube shape and channels, never be padded to fit
        combined = xr.concat(parts, dim="Id", join="exact").rename(name)
        encoding = {name: {"zlib": True, "complevel": 1}} if combined.size else {}
        tmp = output_dir / f"{name}.tmp.nc"
        combined.to_netcdf(tmp, format="NETCDF4", encoding=encoding)
        tmp.replace(output_dir / f"{name}.nc")
        logger.info("%s: %s", output_dir / f"{name}.nc", dict(combined.sizes))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("config", help="Data config with stations, period, box_margin and output_root.")
    parser.add_argument("--station", action="append", help="Only this station; repeatable.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    logging.getLogger("copernicusmarine").setLevel(logging.WARNING)

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    stations = config["stations"]
    unknown = sorted(set(args.station or []) - set(stations))
    if unknown:
        parser.error(f"unknown station(s): {unknown}; the config has {sorted(stations)}")
    root = Path(config.get("output_root", "task4/data/station_matchups"))

    for station in args.station or stations:
        lat, lon = stations[station]
        run_station(config, station, float(lat), float(lon), root)

    done = [root / s / "datasets" for s in stations if (root / s / "datasets").exists()]
    missing = sorted(set(stations) - {d.parent.name for d in done})
    if missing:
        logger.warning("not combined, no cubes yet: %s", missing)
    combine(done, root / "datasets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
