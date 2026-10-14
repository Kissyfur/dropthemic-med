"""Task 1 satellite pigments against the HPLC pigments of the Task 2 samples (SOLA, BBMO, MOLA).

    python task4/scripts/check_pigments.py

For each station and date with HPLC pigments in PETRIMED (task2/PETRIMED/DATA: 196 samples,
2004-2021), takes the median of that day's satellite pigments over the pixels around the station
(task4/data/pigments/stations_daily.nc) and compares the 11 pigments that both have, with the
metrics of Task 1 on ln(pigment) (pigment_retrieval.metrics) and the Pearson r. The HPLC Chl_C2 is
chlorophyll c2, while Task 1 estimates c1 + c2. Writes task4/data/pigments/hplc_check.csv and
task4/figures/pigments/hplc_check.png.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import xarray as xr

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from pigment_retrieval.metrics.metrics import Metrics  # noqa: E402

DATA_DIR = Path("task2/PETRIMED/DATA")
SATELLITE = Path("task4/data/pigments/stations_daily.nc")
OUTPUT = Path("task4/data/pigments/hplc_check.csv")
FIGURE = Path("task4/figures/pigments/hplc_check.png")
# Task 1 pigment: the same pigment in the HPLC tables
PAIRS = {"chl_a": "Chl_a", "chl_b": "Chl_b", "chc12": "Chl_C2", "fucox": "Fucoxanthin", "hxfcx": "19HF",
         "btfcx": "19BF", "diadi": "Diadinoxanthin", "allox": "Alloxanthin", "zeaxa": "Zeaxanthin",
         "betac": "bb_Carotene", "perid": "Peridinine"}
COLORS = {"BBMO": "#2a78d6", "SOLA": "#eb6834", "MOLA": "#1baf7a"}


def hplc_samples() -> pd.DataFrame:
    """One row per station and date: the pigments are the same in every table and size fraction."""
    tables = [pd.read_csv(path, parse_dates=["Date"])[["ST", "Date", *PAIRS.values()]]
              for path in sorted(DATA_DIR.glob("*pigments*.csv"))]
    return pd.concat(tables).drop_duplicates(["ST", "Date"]).reset_index(drop=True)


def satellite_days(samples: pd.DataFrame) -> pd.DataFrame:
    """Median of the satellite pigments of each sample's day over the pixels around its station."""
    with xr.open_dataset(SATELLITE) as satellite:
        days = satellite[list(PAIRS)].load().median(["lat_pixel", "lon_pixel"])
    table = days.reset_coords(drop=True).to_dataframe().reset_index().set_index(["station", "time"])
    keys = pd.MultiIndex.from_arrays([samples["ST"], samples["Date"].dt.normalize()])
    return table.reindex(keys).set_axis(samples.index)


def scores(hplc: pd.DataFrame, satellite: pd.DataFrame) -> pd.DataFrame:
    """Task 1 metrics on ln(pigment), plus Pearson r and the number of matchups, per pigment."""
    log_hplc = np.log(hplc.where(hplc > 0))
    log_sat = np.log(satellite)
    table = Metrics(["R2", "MAPE", "MPE"]).compute_metrics_df(log_hplc, log_sat).T
    table["r"] = [log_hplc[p].corr(log_sat[p]) for p in table.index]
    table["n"] = [int((log_hplc[p].notnull() & log_sat[p].notnull()).sum()) for p in table.index]
    table[["MAPE", "MPE"]] *= 100
    return table[["n", "r", "R2", "MAPE", "MPE"]]


def plot(hplc: pd.DataFrame, satellite: pd.DataFrame, stations: pd.Series) -> None:
    fig, axes = plt.subplots(3, 4, figsize=(11, 8.6), layout="constrained")
    for ax, pigment in zip(axes.flat, PAIRS):
        x, y = hplc[pigment].where(hplc[pigment] > 0), satellite[pigment]
        for station, color in COLORS.items():
            at = stations == station
            ax.plot(x[at], y[at], "o", ms=4, color=color, alpha=0.8, mec="white", mew=0.4, label=station)
        both = pd.concat([x, y]).dropna()
        limits = [both.min() / 1.5, both.max() * 1.5]
        ax.plot(limits, limits, color="#8a8a86", lw=0.8)
        ax.set(xscale="log", yscale="log", xlim=limits, ylim=limits)
        ax.set_title(f"{pigment} ({PAIRS[pigment]})", fontsize=9)
        ax.tick_params(labelsize=7)
        ax.spines[["top", "right"]].set_visible(False)
    axes.flat[-1].axis("off")
    axes.flat[-1].legend(*axes.flat[0].get_legend_handles_labels(), loc="center", frameon=False)
    fig.supxlabel("HPLC (mg m$^{-3}$)")
    fig.supylabel("Satellite, Task 1 (mg m$^{-3}$)")
    fig.suptitle("Satellite against HPLC pigments at the Task 2 stations, same day")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE, dpi=150)
    plt.close(fig)


def main() -> int:
    samples = hplc_samples()
    satellite = satellite_days(samples)
    hplc = samples[list(PAIRS.values())].set_axis(list(PAIRS), axis=1)
    matched = satellite.notnull().all(axis=1)
    print("samples with satellite data that day:",
          samples[matched].groupby("ST").size().to_dict(), "of", samples.groupby("ST").size().to_dict())
    tables = [scores(hplc[matched], satellite[matched]).assign(station="all")]
    tables += [scores(hplc[matched & (samples["ST"] == st)], satellite[matched & (samples["ST"] == st)])
               .assign(station=st) for st in COLORS]
    table = pd.concat(tables).rename_axis("pigment").reset_index()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT, index=False, float_format="%.3f")
    plot(hplc[matched], satellite[matched], samples.loc[matched, "ST"])
    print(table.round(2).to_string(index=False))
    print(f"{OUTPUT}, {FIGURE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
