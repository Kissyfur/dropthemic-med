"""Satellite pigments of the Task 1 CNNs against the HPLC pigments of the Task 2 samples.

    python task1/scripts/hplc_check.py

The Task 2 samples with HPLC pigments (PETRIMED: SOLA, BBMO and MOLA; one per station and date) are
matched with their station cube of station_matchups.py: the 5 x 5 pixels around the station, from
7 days before to 7 days after the sampling day. Each convolutional Task 1 model of the 5
multi-sensor bands predicts the pigments of every pixel and day with a satellite retrieval, and
their median is compared with the HPLC pigments, for the 10 pigments of the proposal: R^2 and
Pearson r of ln(pigment), and MAPE and MPE (bias) of the concentrations, as in the Task 1 paper.
Writes task1/data/hplc_check.csv and, for the model of the record, task1/figures/hplc_check.png
(each pigment, all samples) and task1/figures/hplc_series_<station>.png (each pigment over time).

Values below the detection limit of the satellite pigments, HPLC and satellite alike, are set to it
before scoring: the limit of each pigment is the 5% quantile of the satellite pigments of the whole
station record (stations_daily.nc of predict_pigments.py), the lowest values the satellite gives
(task1/data/detection_limits.csv). It is far above the detection limit of HPLC.

The bias of the model depends on the station, so the model of the record is also calibrated per
station: each pigment times the median HPLC/satellite ratio of all the samples of the station
(task1/data/station_factors.csv). The calibrated pigments are scored (on the samples the factors
come from, so optimistically) and drawn in the series. The calibration is not applied to the
satellite record.
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
STATION_PIGMENTS = Path("task1/data/pigments/stations_daily.nc")
LIMITS = Path("task1/data/detection_limits.csv")
OUTPUT = Path("task1/data/hplc_check.csv")
FACTORS = Path("task1/data/station_factors.csv")
FIGURES = Path("task1/figures")
RECORD_MODEL = "multi_sat_ft/concatenatedCNN"   # the model of the satellite record
SERIES = ["BBMO", "SOLA"]                       # stations with a time series of samples
BANDS = {"RRS412": "412", "RRS443": "442", "RRS490": "490", "RRS555": "560", "RRS670": "673"}
# Task 1 pigment: its name in the HPLC tables
PAIRS = {"chl_a": "Chl_a", "chl_b": "Chl_b", "fucox": "Fucoxanthin", "hxfcx": "19HF", "btfcx": "19BF",
         "diadi": "Diadinoxanthin", "allox": "Alloxanthin", "zeaxa": "Zeaxanthin", "betac": "bb_Carotene",
         "perid": "Peridinine"}
NAMES = {"chl_a": "Chlorophyll a", "chl_b": "Chlorophyll b", "fucox": "Fucoxanthin",
         "hxfcx": "19'-hexanoyloxyfucoxanthin", "btfcx": "19'-butanoyloxyfucoxanthin", "diadi": "Diadinoxanthin",
         "allox": "Alloxanthin", "zeaxa": "Zeaxanthin", "betac": "β-carotene", "perid": "Peridinin"}
INK, SATELLITE, CALIBRATED = "#52514e", "#eb6834", "#2a78d6"
STATION_COLORS = {"BBMO": "#2a78d6", "SOLA": "#eb6834", "MOLA": "#1baf7a"}


def read_samples() -> pd.DataFrame:
    """One row per station and date, with the Id of its station cube: the pigments are the same in
    every PETRIMED table and fraction."""
    tables = [pd.read_csv(p, parse_dates=["Date"])[["ST", "Date", *PAIRS.values()]]
              for p in sorted(DATA_DIR.glob("*pigments*.csv"))]
    samples = pd.concat(tables).drop_duplicates(["ST", "Date"])
    return samples.set_axis([f"{st}_{date:%Y%m%d}" for st, date in zip(samples["ST"], samples["Date"])])


def satellite_inputs(ids: pd.Index) -> xr.Dataset:
    """ln(Rrs) of the station cubes of the samples; pixels and days without a retrieval are empty."""
    # Through dask, each compressed chunk of the file (thousands of cubes) is read once
    with xr.open_dataarray(STATION_CUBES, chunks={}) as cubes:
        cube = cubes.sel(Id=ids.intersection(cubes["Id"].values), variable=list(BANDS)).reset_coords(drop=True)
        return cube.load().to_dataset("variable").rename(BANDS)


def detection_limits() -> pd.Series:
    """Per pigment, the 5% quantile of the satellite pigments of the whole station record: the
    lowest values the satellite gives, as the floor Task 1 applies to its Rrs and training pigments."""
    with xr.open_dataset(STATION_PIGMENTS) as pigments:
        return pd.Series({p: float(pigments[p].quantile(0.05)) for p in PAIRS}, name="limit")


def scores(hplc: pd.DataFrame, predicted: pd.DataFrame) -> pd.DataFrame:
    """Per pigment: R^2 (coefficient of determination) and Pearson r of ln(pigment), MAPE and MPE
    (bias) of the concentrations in %, and the number of samples."""
    from pigment_retrieval.metrics.metrics import Metrics
    log_hplc = np.log(hplc.where(hplc > 0))
    log_pred = np.log(predicted.where(predicted > 0))
    table = Metrics(["R2", "MAPE", "MPE"]).compute_metrics_df(log_hplc, log_pred).T
    table["r"] = [log_hplc[p].corr(log_pred[p]) for p in table.index]
    table["n"] = [int((log_hplc[p].notnull() & log_pred[p].notnull()).sum()) for p in table.index]
    table[["MAPE", "MPE"]] *= 100
    return table[["n", "R2", "r", "MAPE", "MPE"]]


def plot_scatter(hplc: pd.DataFrame, predicted: pd.DataFrame, stations: pd.Series, limits: pd.Series, title: str,
                 path: Path) -> None:
    """Predicted against HPLC pigments, one panel per pigment, coloured by station, with the detection
    limit (dotted)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 4, figsize=(11, 8.6), layout="constrained")
    for ax, pigment in zip(axes.flat, PAIRS):
        x, y = hplc[pigment].where(hplc[pigment] > 0), predicted[pigment]
        for station, color in STATION_COLORS.items():
            at = stations == station
            ax.plot(x[at], y[at], "o", ms=4, color=color, alpha=0.8, mec="white", mew=0.4, label=station)
        both = pd.concat([x, y]).dropna()
        extent = [both.min() / 1.5, both.max() * 1.5]
        ax.plot(extent, extent, color="#8a8a86", lw=0.8)
        ax.axvline(limits[pigment], color="#8a8a86", lw=0.8, ls=":")
        ax.axhline(limits[pigment], color="#8a8a86", lw=0.8, ls=":")
        ax.set(xscale="log", yscale="log", xlim=extent, ylim=extent)
        ax.set_title(NAMES[pigment], fontsize=9)
        ax.tick_params(labelsize=7)
        ax.spines[["top", "right"]].set_visible(False)
    for ax in axes.flat[len(PAIRS):]:
        ax.axis("off")
    axes.flat[-1].legend(*axes.flat[0].get_legend_handles_labels(), loc="center", frameon=False)
    fig.supxlabel("HPLC (mg m$^{-3}$)")
    fig.supylabel("Satellite (mg m$^{-3}$)")
    fig.suptitle(title)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def calibrate(hplc: pd.DataFrame, predicted: pd.DataFrame, stations: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-station factors, the median HPLC/satellite ratio of each pigment over all the samples of
    the station, and the pigments calibrated with the factors of their station."""
    factors = np.exp((np.log(hplc.where(hplc > 0)) - np.log(predicted)).groupby(stations).median())
    return factors.rename_axis("station"), predicted * factors.loc[stations].set_axis(predicted.index)


def label_log_axis(ax) -> None:
    """Plain labels at 1, 2 and 5 of each decade on a narrow log y axis, at each decade on a wide one."""
    from matplotlib.ticker import FuncFormatter, LogLocator, NullLocator
    low, high = ax.get_ylim()
    ax.yaxis.set_major_locator(LogLocator(subs=(1.0,) if high / low > 100 else (1.0, 2.0, 5.0)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
    ax.yaxis.set_minor_locator(NullLocator())


def plot_series(hplc: pd.DataFrame, predicted: pd.DataFrame, calibrated: pd.DataFrame, dates: pd.Series,
                limits: pd.Series, title: str, path: Path) -> None:
    """HPLC, satellite and calibrated satellite pigments of one station over time, one panel per pigment,
    with the detection limit (dotted)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    order = dates.sort_values().index
    table = scores(hplc.loc[order], predicted.loc[order])
    table_calibrated = scores(hplc.loc[order], calibrated.loc[order])
    fig, axes = plt.subplots(5, 2, figsize=(10, 9.5), sharex=True, layout="constrained")
    for ax, pigment in zip(axes.T.flat, PAIRS):
        observed = hplc.loc[order, pigment]
        ax.plot(dates[order], observed.where(observed > 0), color=INK, lw=1.4, marker="o", ms=3, label="HPLC")
        ax.plot(dates[order], predicted.loc[order, pigment], color=SATELLITE, lw=1.2,
                label="satellite, station cube of the sampling day ±7 days")
        ax.plot(dates[order], calibrated.loc[order, pigment], color=CALIBRATED, lw=1.2,
                label="satellite calibrated for the station")
        ax.axhline(limits[pigment], color="#8a8a86", lw=0.8, ls=":")
        ax.set_yscale("log")
        label_log_axis(ax)
        ax.set_title(f"{NAMES[pigment]}: R² = {table.loc[pigment, 'R2']:.2f}, calibrated "
                     f"{table_calibrated.loc[pigment, 'R2']:.2f}; r = {table.loc[pigment, 'r']:.2f}",
                     fontsize=9, loc="left")
        ax.tick_params(labelsize=7)
        ax.grid(axis="y", color="#e5e5e2", lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.supylabel("mg m$^{-3}$")
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="outside lower center", ncol=3, frameon=False,
               fontsize=8)
    fig.suptitle(title)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> int:
    samples = read_samples()
    limits = detection_limits()
    # HPLC zeros are below detection too: set to the limit, as the values below it
    hplc = samples[list(PAIRS.values())].set_axis(list(PAIRS), axis=1).clip(lower=limits, axis=1)
    x = satellite_inputs(samples.index)
    models = [name for name, (exp, _) in available_models().items()
              if exp["INP_VARS"] == list(BANDS.values()) and "cnn" in name.lower()]
    rows = []
    for name in models:
        predicted = (Predictor(name).predict(x, logged=True)[list(PAIRS)].median(["lat", "lon", "time"])
                     .to_dataframe()[list(PAIRS)].dropna().clip(lower=limits, axis=1))
        rows.append(scores(hplc.loc[predicted.index], predicted).assign(model=name))
        if name == RECORD_MODEL:
            at = predicted.index
            plot_scatter(hplc.loc[at], predicted, samples.loc[at, "ST"], limits,
                         f"{RECORD_MODEL} against HPLC, station cubes of the sampling day ±7 days",
                         FIGURES / "hplc_check.png")
            factors, calibrated = calibrate(hplc.loc[at], predicted, samples.loc[at, "ST"])
            calibrated = calibrated.clip(lower=limits, axis=1)
            factors.to_csv(FACTORS, float_format="%.3f")
            rows.append(scores(hplc.loc[at], calibrated).assign(model=f"{name}, calibrated per station"))
            for station in SERIES:
                ids = at[samples.loc[at, "ST"] == station]
                plot_series(hplc.loc[ids], predicted.loc[ids], calibrated.loc[ids], samples.loc[ids, "Date"], limits,
                            f"{station}: HPLC and satellite pigments ({RECORD_MODEL})",
                            FIGURES / f"hplc_series_{station}.png")
    table = pd.concat(rows).rename_axis("pigment").reset_index()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT, index=False, float_format="%.3f")
    limits.rename_axis("pigment").to_csv(LIMITS, float_format="%.4f")
    print(table.query("model == @RECORD_MODEL").drop(columns="model").round(2).to_string(index=False))
    print(table.groupby("model")[["n", "R2", "r", "MAPE"]].median().sort_values("R2").round(2).to_string())
    print(factors.round(2).to_string())
    print(limits.round(4).to_string())
    print(f"{OUTPUT}, {FACTORS}, {LIMITS}, {FIGURES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
