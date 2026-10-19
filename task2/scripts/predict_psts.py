"""Plankton groups (PSTs) from the satellite pigments of Task 1, with the PETRIMED models.

    python task2/scripts/predict_psts.py [--check-only]

1. Harmonization. The composition of the satellite pigments of Task 1 is outside the one the models
   learned (e.g. a zeaxanthin share around 0.10, against about 0.01 at SOLA). Each pigment share is
   mapped by quantiles from its distribution in the satellite record at the NW Mediterranean
   stations (median of each month around each station) onto its distribution in the HPLC samples
   of SOLA and MOLA. The quantiles go to task2/data/psts/pigment_quantiles.csv.
2. Check at BBMO, which the harmonization does not use: Pearson correlation between the abundance
   observed in each BBMO sample (2004-2014) and the one predicted from the satellite pigments of
   its month, as they are and harmonized, also for the mean seasonal cycle, for the pico psbo PSTs.
   Writes task2/data/psts/satellite_check.csv and task2/figures/satellite_check.png.
3. Prediction, from the harmonized pigments, of the PSTs in PSTS, those with some skill in the check:
   - <region>_monthly.nc, from task1/data/pigments/<region>_monthly.nc, plus its `valid_days`;
   - stations_monthly.nc, from the monthly median of the pigments around each station.
--check-only stops after step 2.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import psts
import xarray as xr

PIGMENT_DIR = Path("task1/data/pigments")
OUTPUT_DIR = Path("task2/data/psts")
QUANTILES = OUTPUT_DIR / "pigment_quantiles.csv"
CHECK = OUTPUT_DIR / "satellite_check.csv"
FIGURE = Path("task2/figures/satellite_check.png")
MIN_DAYS = 3
# Predicted PSTs (pico, psbo)
PSTS = ["Synechococcus", "Bathycoccus"]
# The pigments of the models with their name in Task 1, which has no prasinoxanthin
TASK1 = {"Chl_C2": "chc12", "Peridinine": "perid", "X19BF": "btfcx", "Fucoxanthin": "fucox", "X19HF": "hxfcx",
         "Diadinoxanthin": "diadi", "Alloxanthin": "allox", "Zeaxanthin": "zeaxa", "Chl_b": "chl_b",
         "Chl_a": "chl_a", "bb_Carotene": "betac"}


def from_task1(pigments: pd.DataFrame) -> pd.DataFrame:
    """The pigments of the models from those of Task 1, with prasinoxanthin from chlorophyll b."""
    x = pd.DataFrame({name: pigments[task1] for name, task1 in TASK1.items()})
    return psts.estimate_prasinoxanthin(x)


def satellite_monthly() -> pd.DataFrame:
    """Task 1 pigments around each station: median of each month, indexed by (station, time)."""
    with xr.open_dataset(PIGMENT_DIR / "stations_daily.nc") as daily:
        daily = daily.load()
    days = daily["chl_a"].notnull().any(["lat_pixel", "lon_pixel"]).resample(time="MS").sum()
    monthly = daily.resample(time="MS").median(dim=["time", "lat_pixel", "lon_pixel"]).where(days >= MIN_DAYS)
    return monthly.reset_coords(drop=True).to_dataframe().reset_index().set_index(["station", "time"])


def save_quantiles(satellite: pd.DataFrame) -> None:
    """Quantiles of the satellite shares at the NW Mediterranean stations and of the HPLC shares at
    SOLA and MOLA (not BBMO, kept for the check)."""
    sat = psts.relative(from_task1(satellite.loc[["BBMO", "SOLA", "MOLA"]]).dropna())
    insitu = psts.read_insitu().query("ST != 'BBMO'")
    hplc = psts.relative(psts.estimate_prasinoxanthin(insitu[psts.PIGMENTS]))
    levels = np.linspace(0, 1, 101)
    table = {"quantile": levels}
    for p in psts.PIGMENTS:
        table[f"{p}_satellite"], table[f"{p}_hplc"] = np.quantile(sat[p], levels), np.quantile(hplc[p], levels)
    pd.DataFrame(table).to_csv(QUANTILES, index=False)


def harmonize(shares: pd.DataFrame) -> pd.DataFrame:
    """Satellite pigment shares mapped by quantiles onto the HPLC ones, then made relative again."""
    q = pd.read_csv(QUANTILES)
    mapped = pd.DataFrame({p: np.interp(shares[p], q[f"{p}_satellite"], q[f"{p}_hplc"]) for p in psts.PIGMENTS},
                          index=shares.index)
    return mapped.div(mapped.sum(axis=1), axis=0)


def check(satellite: pd.DataFrame) -> pd.DataFrame:
    summary = pd.read_csv(psts.MODELS_DIR / "summary.csv")
    bbmo = psts.read_insitu().query("ST == 'BBMO'")
    months = bbmo["Date"].dt.to_period("M").dt.to_timestamp()
    pigments = from_task1(satellite.reindex(pd.MultiIndex.from_arrays([bbmo["ST"], months]))
                          .set_axis(bbmo.index)).dropna()
    inputs = {"satellite": psts.relative(pigments), "harmonized": harmonize(psts.relative(pigments))}
    month = bbmo["Date"].dt.month
    rows, series = [], {}
    for pst in summary["pst"]:
        models = psts.load_models(pst)
        observed = bbmo[pst]
        result = {"pst": pst}
        predicted = {}
        for name, x in inputs.items():
            predicted[name] = pd.Series(psts.predict(models, x), index=x.index)
            result[f"r_{name}"], result["n"] = psts.pearson(observed[x.index], predicted[name])
            result[f"r_{name}_seasonal"], _ = psts.pearson(observed.groupby(month).mean(),
                                                           predicted[name].groupby(month[x.index]).mean())
        rows.append(result)
        if pst in PSTS:
            hplc = psts.relative(bbmo[psts.PIGMENTS])
            series[pst] = {"observed": observed,
                           "HPLC pigments": pd.Series(psts.predict(models, hplc), index=hplc.index),
                           "harmonized satellite pigments": predicted["harmonized"]}
    table = pd.DataFrame(rows)
    table.to_csv(CHECK, index=False, float_format="%.3f")
    psts.plot_check(bbmo["Date"], series,
                    "PETRIMED models (pico, psbO) at BBMO from the satellite pigments of each month", FIGURE)
    print(table.round(2).to_string(index=False))
    print(f"{CHECK}, {FIGURE}")
    return table


def predict(pigments: pd.DataFrame, models: dict) -> pd.DataFrame:
    """Abundance of each PST for each row of Task 1 pigments, NaN where a pigment is missing."""
    ok = pigments[list(TASK1.values())].notnull().all(axis=1)
    x = harmonize(psts.relative(from_task1(pigments[ok])))
    out = pd.DataFrame(index=pigments.index, columns=list(models), dtype="float32")
    for pst, pst_models in models.items():
        out.loc[ok, pst] = psts.predict(pst_models, x).astype("float32")
    return out


def describe(data: xr.Dataset, table: pd.DataFrame) -> xr.Dataset:
    for pst in PSTS:
        r = table.set_index("pst").loc[pst]
        data[pst].attrs = {"long_name": f"{pst} (pico, psbO)", "units": "RPKM",
                           "comment": f"r at BBMO from harmonized satellite pigments: {r.r_harmonized:.2f} "
                                      f"monthly, {r.r_harmonized_seasonal:.2f} seasonal cycle"}
    data.attrs["model"] = "PETRIMED XGBoost models (Task 2) on harmonized satellite pigments"
    return data


def write(data: xr.Dataset, path: Path) -> None:
    encoding = {name: {"zlib": True, "complevel": 4} for name in data.data_vars}
    data.to_netcdf(path, format="NETCDF4", encoding=encoding)
    print(f"{path}: {dict(data.sizes)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check-only", action="store_true", help="Stop after the check at BBMO.")
    args = parser.parse_args(argv)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    satellite = satellite_monthly()
    save_quantiles(satellite)
    table = check(satellite)
    if args.check_only:
        return 0

    models = {pst: psts.load_models(pst) for pst in PSTS}
    for path in sorted(PIGMENT_DIR.glob("*_monthly.nc")):
        with xr.open_dataset(path) as monthly:
            # One year at a time keeps the memory low
            years = [predict(block.drop_vars("valid_days").to_dataframe(), models).to_xarray()
                     for _, block in monthly.groupby("time.year")]
            out = xr.concat(years, "time").transpose("time", "latitude", "longitude")
            out["valid_days"] = monthly["valid_days"]
            out.attrs = {"title": f"Plankton groups from {path.name}", "region": monthly.attrs.get("region", "")}
        write(describe(out, table), OUTPUT_DIR / path.name)

    out = predict(satellite, models).to_xarray().transpose("station", "time")
    out.attrs = {"title": "Plankton groups around the stations, from the monthly median of their pigments"}
    write(describe(out, table), OUTPUT_DIR / "stations_monthly.nc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
