"""Pigment concentrations from the Task 4 radiometry, with the Task 1 model.

    python task1/scripts/predict_pigments.py [--only monthly|stations]

Uses multi_sat_ft/concatenatedCNN of pigment-retrieval-from-olci, the CNN for the 5 multi-sensor
bands fine-tuned with satellite matchups. Both inputs already hold ln(Rrs), floored at their 5%
quantile, so no transform is applied here. Writes to task1/data/pigments:
- <region>_monthly.nc for each task1/data/radiometry_monthly/<region>_monthly.nc: the 13
  pigments on the same (time, latitude, longitude) grid, plus its `valid_days`. Means of one or
  two days can be unrealistic: filter on `valid_days`.
- stations_daily.nc from the station cubes, task1/data/station_matchups/datasets/optics.nc: the
  pigments of the 11 x 9 pixels around each station on each day, as (station, time, lat_pixel,
  lon_pixel). Only the cube's centre day is used, and only its pixels with a retrieval
  (cloud_mask 0): the gaps that the cubes fill by interpolation stay empty.
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import pandas as pd
import xarray as xr
import yaml

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
from pigment_retrieval.predict.cli import PRODUCT_BANDS  # noqa: E402
from pigment_retrieval.predict.predict import Predictor  # noqa: E402

logger = logging.getLogger("predict_pigments")

MODEL = "multi_sat_ft/concatenatedCNN"
MONTHLY_DIR = Path("task1/data/radiometry_monthly")
STATION_CUBES = Path("task1/data/station_matchups/datasets/optics.nc")
STATIONS_CONFIG = Path("task1/configs/station_matchups.yaml")
OUTPUT_DIR = Path("task1/data/pigments")

PIGMENT_NAMES = {
    "chlid": "chlorophyllide a", "chl_a": "chlorophyll a", "chl_b": "chlorophyll b",
    "chc12": "chlorophyll c1+c2", "fucox": "fucoxanthin", "hxfcx": "19'-hexanoyloxyfucoxanthin",
    "btfcx": "19'-butanoyloxyfucoxanthin", "diadi": "diadinoxanthin", "allox": "alloxanthin",
    "diato": "diatoxanthin", "zeaxa": "zeaxanthin", "betac": "beta-carotene", "perid": "peridinin",
}


def predict(predictor: Predictor, log_rrs: xr.Dataset) -> xr.Dataset:
    """Pigments [mg m-3] of a Dataset with one ln(Rrs) variable per Copernicus band."""
    bands = log_rrs.rename({name: band for name, band in PRODUCT_BANDS.items() if name in log_rrs})
    bands = bands[predictor.bands]
    # ln(Rrs) is negative: a 0 is a gap filled by the cubes, not a measurement
    pigments = predictor.predict(bands.where(bands < 0), logged=True)
    for name in pigments.data_vars:
        pigments[name] = pigments[name].astype("float32")
        pigments[name].attrs = {"long_name": PIGMENT_NAMES.get(name, name), "units": "mg m-3"}
    pigments.attrs["model"] = f"pigment-retrieval-from-olci {MODEL}"
    return pigments


def write(data: xr.Dataset, path: Path) -> None:
    encoding = {name: {"zlib": True, "complevel": 4} for name in data.data_vars}
    tmp = path.with_suffix(".tmp.nc")
    data.to_netcdf(tmp, format="NETCDF4", encoding=encoding)
    tmp.replace(path)
    predicted = int(data["chl_a"].notnull().sum())
    logger.info("%s: %d pixels predicted, %s", path, predicted, dict(data.sizes))


def predict_monthly(predictor: Predictor, path: Path, output: Path) -> None:
    with xr.open_dataset(path) as monthly:
        pigments = predict(predictor, monthly)
        pigments["valid_days"] = monthly["valid_days"]
        pigments.attrs.update(
            title=f"Phytoplankton pigments from the monthly mean Rrs of {monthly.attrs['source_dataset']}",
            input_file=path.name,
            **{key: monthly.attrs[key] for key in ("region", "period") if key in monthly.attrs},
        )
        write(pigments, output)


def predict_stations(predictor: Predictor, cubes_path: Path, stations: dict, output: Path) -> None:
    with xr.open_dataarray(cubes_path) as cubes:
        # The cube's 15 days are centred on the day of its Id, <station>_<yyyymmdd>
        day = cubes.isel(time=cubes.sizes["time"] // 2, drop=True).reset_coords(drop=True).load()
    observed = day.sel(variable="cloud_mask", drop=True) == 0
    pigments = predict(predictor, day.where(observed).to_dataset("variable"))

    ids = pd.Series(pigments["Id"].values).str.split("_", expand=True)
    pigments = (
        pigments.assign_coords(
            station=("Id", ids[0].values), time=("Id", pd.to_datetime(ids[1], format="%Y%m%d").values)
        )
        .set_index(Id=["station", "time"])
        .unstack("Id")
    )
    days = pd.date_range(pigments["time"].values.min(), pigments["time"].values.max(), freq="D")
    pigments = pigments.reindex(time=days).transpose("station", "time", "lat", "lon")

    # The cube's centre pixel is the grid point nearest to the station
    pigments = pigments.rename(lat="lat_pixel", lon="lon_pixel").assign_coords(
        lat_pixel=pigments["lat"].values - pigments.sizes["lat"] // 2,
        lon_pixel=pigments["lon"].values - pigments.sizes["lon"] // 2,
        station_lat=("station", [float(stations[s][0]) for s in pigments["station"].values]),
        station_lon=("station", [float(stations[s][1]) for s in pigments["station"].values]),
    )
    pigments["lat_pixel"].attrs = {"long_name": "1 km pixels north of the station pixel"}
    pigments["lon_pixel"].attrs = {"long_name": "1 km pixels east of the station pixel"}
    pigments.attrs.update(
        title="Phytoplankton pigments around the stations, from the daily multi-sensor Rrs",
        input_file=cubes_path.as_posix(),
    )
    write(pigments, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", choices=["monthly", "stations"], help="Predict only these inputs.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

    predictor = Predictor(MODEL)
    # Loading the model disables all logging up to WARNING (pigment_retrieval keras_models)
    logging.disable(logging.NOTSET)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.only != "stations":
        for path in sorted(MONTHLY_DIR.glob("*_monthly.nc")):
            predict_monthly(predictor, path, OUTPUT_DIR / path.name)
    if args.only != "monthly":
        stations = yaml.safe_load(STATIONS_CONFIG.read_text(encoding="utf-8"))["stations"]
        predict_stations(predictor, STATION_CUBES, stations, OUTPUT_DIR / "stations_daily.nc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
