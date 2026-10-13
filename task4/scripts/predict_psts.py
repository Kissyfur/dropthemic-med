"""Plankton groups (PSTs) from the Task 4 pigments, with the PETRIMED models of Task 2.

    python task4/scripts/predict_psts.py

Only the PSTs that keep some skill from satellite pigments at BBMO (task2/data/transferability.csv,
made by task2/scripts/psts.py): Synechococcus, and Bathycoccus for its seasonal cycle. The pigments
are made relative and harmonized to the HPLC pigments the models learned from, as in Task 2.
Writes to task4/data/psts:
- <region>_monthly.nc, from task4/data/pigments/<region>_monthly.nc: the abundance of each PST on
  the same grid, plus `valid_days`;
- stations_monthly.nc: each PST around each station, from the median of the month of each pigment
  over the pixels around the station (task4/data/pigments/stations_daily.nc), as validated at BBMO.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import xarray as xr

sys.path.insert(0, "task2/scripts")
import psts  # noqa: E402

PIGMENT_DIR = Path("task4/data/pigments")
OUTPUT_DIR = Path("task4/data/psts")
# PST: (method, fraction, r at BBMO from satellite pigments, monthly and of the seasonal cycle)
PSTS = {"Synechococcus": ("psbo", "pico", 0.61, 0.88), "Bathycoccus": ("psbo", "pico", 0.22, 0.54)}
TASK1_PIGMENTS = [name for name in psts.PIGMENTS.values() if name]


def predict(pigments: pd.DataFrame, models: dict) -> pd.DataFrame:
    """Abundance of each PST for each row of Task 1 pigments, NaN where a pigment is missing."""
    ok = pigments.notnull().all(axis=1)
    x = psts.harmonize(psts.relative(psts.from_task1(pigments[ok])))
    out = pd.DataFrame(index=pigments.index, columns=list(models), dtype="float32")
    for pst, pst_models in models.items():
        out.loc[ok, pst] = psts.predict(pst_models, x)
    return out


def describe(data: xr.Dataset) -> xr.Dataset:
    for pst, (method, fraction, r_month, r_season) in PSTS.items():
        data[pst].attrs = {"long_name": f"{pst} ({fraction}, {method})", "units": "RPKM",
                           "comment": f"r at BBMO from satellite pigments: {r_month} monthly, {r_season} "
                                      f"seasonal cycle"}
    data.attrs["model"] = "PETRIMED XGBoost models, harmonized satellite pigments (task2/scripts/psts.py)"
    return data


def write(data: xr.Dataset, path: Path) -> None:
    encoding = {name: {"zlib": True, "complevel": 4} for name in data.data_vars}
    data.to_netcdf(path, format="NETCDF4", encoding=encoding)
    print(f"{path}: {dict(data.sizes)}")


def main() -> int:
    models = {pst: psts.load_models(method, fraction, pst) for pst, (method, fraction, *_) in PSTS.items()}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for path in sorted(PIGMENT_DIR.glob("*_monthly.nc")):
        with xr.open_dataset(path) as monthly:
            # One year at a time keeps the memory low
            years = [predict(block[TASK1_PIGMENTS].to_dataframe(), models).to_xarray()
                     for _, block in monthly.groupby("time.year")]
            out = xr.concat(years, "time").transpose("time", "latitude", "longitude")
            out["valid_days"] = monthly["valid_days"]
            out.attrs = {"title": f"Plankton groups from {path.name}", "region": monthly.attrs.get("region", "")}
        write(describe(out), OUTPUT_DIR / path.name)

    pigments = psts.satellite_monthly()[TASK1_PIGMENTS]
    out = predict(pigments, models).to_xarray().transpose("station", "time")
    out.attrs = {"title": "Plankton groups around the stations, from the monthly median of their pigments"}
    write(describe(out), OUTPUT_DIR / "stations_monthly.nc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
