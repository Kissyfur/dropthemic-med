"""Satellite pigments of the Task 1 CNNs against the HPLC pigments of the Task 2 samples.

    python task1/scripts/hplc_check.py

The Task 2 samples with HPLC pigments (PETRIMED: SOLA, BBMO and MOLA; one per station and date) are
matched with their station cube of station_matchups.py: the 11 x 9 pixels around the station, from
7 days before to 7 days after the sampling day. Each convolutional Task 1 model of the 5
multi-sensor bands predicts the pigments of every pixel and day with a satellite retrieval, and
their median is compared with the HPLC pigments with the metrics of Task 1 on ln(pigment) and the
Pearson r. Writes task1/data/hplc_check.csv and task1/figures/hplc_check.png (each pigment, for the
model of the record).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
from pigment_retrieval.predict.predict import Predictor, available_models  # noqa: E402

DATA_DIR = Path("task2/PETRIMED/DATA")
STATION_CUBES = Path("task1/data/station_matchups/datasets/optics.nc")
OUTPUT = Path("task1/data/hplc_check.csv")
FIGURE = Path("task1/figures/hplc_check.png")
RECORD_MODEL = "multi_sat_ft/concatenatedCNN"   # the model of the satellite record
BANDS = {"RRS412": "412", "RRS443": "442", "RRS490": "490", "RRS555": "560", "RRS670": "673"}
# Task 1 pigment: the same pigment in the HPLC tables (Chl_C2 is c2 only, Task 1 gives c1 + c2)
PAIRS = {"chl_a": "Chl_a", "chl_b": "Chl_b", "chc12": "Chl_C2", "fucox": "Fucoxanthin", "hxfcx": "19HF",
         "btfcx": "19BF", "diadi": "Diadinoxanthin", "allox": "Alloxanthin", "zeaxa": "Zeaxanthin",
         "betac": "bb_Carotene", "perid": "Peridinine"}


def read_samples() -> pd.DataFrame:
    """One row per station and date, with the Id of its station cube: the pigments are the same in
    every PETRIMED table and fraction."""
    tables = [pd.read_csv(p, parse_dates=["Date"])[["ST", "Date", *PAIRS.values()]]
              for p in sorted(DATA_DIR.glob("*pigments*.csv"))]
    samples = pd.concat(tables).drop_duplicates(["ST", "Date"])
    return samples.set_axis([f"{st}_{date:%Y%m%d}" for st, date in zip(samples["ST"], samples["Date"])])


def satellite_inputs(ids: pd.Index) -> xr.Dataset:
    """ln(Rrs) of the pixels and days with a satellite retrieval in the station cubes of the samples."""
    # Through dask, each compressed chunk of the file (thousands of cubes) is read once
    with xr.open_dataarray(STATION_CUBES, chunks={}) as cubes:
        cube = cubes.sel(Id=ids.intersection(cubes["Id"].values)).reset_coords(drop=True).load()
    cube = cube.where(cube.sel(variable="cloud_mask", drop=True) == 0).sel(variable=list(BANDS))
    x = cube.to_dataset("variable").rename(BANDS)
    # ln(Rrs) is negative: a 0 is a gap filled by the cubes
    return x.where(x < 0)


def scores(hplc: pd.DataFrame, predicted: pd.DataFrame) -> pd.DataFrame:
    """Task 1 metrics on ln(pigment), Pearson r and number of samples, per pigment."""
    from pigment_retrieval.metrics.metrics import Metrics
    log_hplc = np.log(hplc.where(hplc > 0))
    log_pred = np.log(predicted.where(predicted > 0))
    table = Metrics(["R2", "MAPE", "MPE"]).compute_metrics_df(log_hplc, log_pred).T
    table["r"] = [log_hplc[p].corr(log_pred[p]) for p in table.index]
    table["n"] = [int((log_hplc[p].notnull() & log_pred[p].notnull()).sum()) for p in table.index]
    table[["MAPE", "MPE"]] *= 100
    return table[["n", "r", "R2", "MAPE", "MPE"]]


def plot_scatter(hplc: pd.DataFrame, predicted: pd.DataFrame, stations: pd.Series, title: str, path: Path) -> None:
    """Predicted against HPLC pigments, one panel per pigment, coloured by station."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"BBMO": "#2a78d6", "SOLA": "#eb6834", "MOLA": "#1baf7a"}
    fig, axes = plt.subplots(3, 4, figsize=(11, 8.6), layout="constrained")
    for ax, pigment in zip(axes.flat, PAIRS):
        x, y = hplc[pigment].where(hplc[pigment] > 0), predicted[pigment]
        for station, color in colors.items():
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
    fig.supylabel("Satellite (mg m$^{-3}$)")
    fig.suptitle(title)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> int:
    samples = read_samples()
    hplc = samples[list(PAIRS.values())].set_axis(list(PAIRS), axis=1)
    x = satellite_inputs(samples.index)
    models = [name for name, (exp, _) in available_models().items()
              if exp["INP_VARS"] == list(BANDS.values()) and "cnn" in name.lower()]
    rows = []
    for name in models:
        predicted = (Predictor(name).predict(x, logged=True)[list(PAIRS)].median(["lat", "lon", "time"])
                     .to_dataframe()[list(PAIRS)].dropna())
        rows.append(scores(hplc.loc[predicted.index], predicted).assign(model=name))
        if name == RECORD_MODEL:
            plot_scatter(hplc.loc[predicted.index], predicted, samples.loc[predicted.index, "ST"],
                         f"{RECORD_MODEL} against HPLC, station cubes of the sampling day ±7 days", FIGURE)
    table = pd.concat(rows).rename_axis("pigment").reset_index()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT, index=False, float_format="%.3f")
    print(table.query("model == @RECORD_MODEL").drop(columns="model").round(2).to_string(index=False))
    print(table.groupby("model")[["n", "r", "MAPE"]].median().sort_values("r").round(2).to_string())
    print(f"{OUTPUT}, {FIGURE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
