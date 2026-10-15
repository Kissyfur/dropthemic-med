"""Satellite pigments of the Task 1 models against the HPLC pigments of the Task 2 samples.

    python task1/scripts/hplc_matchups.py task1/configs/hplc_matchups.yaml

The Task 2 samples with HPLC pigments (PETRIMED: SOLA, BBMO, MOLA; one row per station and date,
written to <output_root>/samples.csv) are matched with satellite Rrs in several ways:
- station_cubes: the cubes of station_matchups.py (Mediterranean 1 km product, the sampling day,
  the 11 x 9 pixels around the station with a retrieval); the pigments are predicted per pixel,
  then their median is taken;
- one per product of the config, built with copernicus-matchup as the Task 1 satellite matchups
  (see the config) under <output_root>/<product>, and averaged with the weights of Task 1 (exp of
  minus the Manhattan distance to the centre, over pixels and days, skipping gaps).
Every Task 1 model of the 5 multi-sensor bands predicts the pigments, compared with the HPLC ones
with the metrics of Task 1 on ln(pigment) and the Pearson r: on all the samples of each matchup and
on those shared by the matchups in `compare_on`. Writes <output_root>/scores.csv,
task1/figures/hplc_matchups.png (median r per model and matchup) and
task1/figures/hplc_check.png (each pigment, for the model and matchup of Task 4).
"""
from __future__ import annotations

import argparse
import copy
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import yaml

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
from copernicus_matchup import DataConfig, build_dataset  # noqa: E402
from pigment_retrieval.predict.predict import Predictor, available_models  # noqa: E402

DATA_DIR = Path("task2/PETRIMED/DATA")
STATION_CUBES = Path("task1/data/station_matchups/datasets/optics.nc")
FIGURE = Path("task1/figures/hplc_matchups.png")
SCATTER = Path("task1/figures/hplc_check.png")
TASK4_MODEL = "multi_sat_ft/concatenatedCNN"   # the model and matchup of the Task 4 record
BANDS = {"RRS412": "412", "RRS443": "442", "RRS490": "490", "RRS555": "560", "RRS670": "673"}
# Task 1 pigment: the same pigment in the HPLC tables (Chl_C2 is c2 only, Task 1 gives c1 + c2)
PAIRS = {"chl_a": "Chl_a", "chl_b": "Chl_b", "chc12": "Chl_C2", "fucox": "Fucoxanthin", "hxfcx": "19HF",
         "btfcx": "19BF", "diadi": "Diadinoxanthin", "allox": "Alloxanthin", "zeaxa": "Zeaxanthin",
         "betac": "bb_Carotene", "perid": "Peridinine"}


def write_samples(stations: dict, path: Path) -> pd.DataFrame:
    """One row per station and date: the pigments are the same in every PETRIMED table and fraction."""
    tables = [pd.read_csv(p, parse_dates=["Date"])[["ST", "Date", *PAIRS.values()]]
              for p in sorted(DATA_DIR.glob("*pigments*.csv"))]
    samples = pd.concat(tables).drop_duplicates(["ST", "Date"]).reset_index(drop=True)
    samples.insert(0, "Id", [f"{st}_{date:%Y%m%d}" for st, date in zip(samples["ST"], samples["Date"])])
    samples["lat"] = [float(stations[st][0]) for st in samples["ST"]]
    samples["lon"] = [float(stations[st][1]) for st in samples["ST"]]
    samples = samples.rename(columns={"Date": "time"})
    path.parent.mkdir(parents=True, exist_ok=True)
    samples.to_csv(path, index=False)
    return samples.set_index("Id")


def task1_weights(cube: xr.DataArray) -> xr.DataArray:
    """Task 1's weights: exp(max distance - Manhattan distance to the centre) over lat, lon and time."""
    shape = [cube.sizes[d] for d in ("lat", "lon", "time")]
    distance = sum(np.abs(i - s // 2) for i, s in zip(np.indices(shape), shape))
    return xr.DataArray(np.exp(distance.max() - distance), dims=("lat", "lon", "time"))


def product_inputs(config: dict, root: Path) -> dict[str, pd.DataFrame]:
    """ln(Rrs) per sample for each product, averaged as Task 1, with the bands named as Task 1 expects."""
    inputs = {}
    for product in config["products"]:
        data = copy.deepcopy({key: config[key] for key in ("target", "matchup", "preprocess")})
        data["target"]["path"] = str(root / "samples.csv")
        data["products"] = [{**product, "preprocess": {"mask_kinds": ["cloud_mask"]}}]
        run = root / product["name"]
        build_dataset(DataConfig.from_dict(data), run)
        cube = xr.load_dataarray(run / "datasets" / f"{product['feature_group']}.nc").sel(variable=list(BANDS))
        averaged = cube.weighted(task1_weights(cube)).mean(("lat", "lon", "time"))
        inputs[product["name"]] = averaged.to_pandas().rename(columns=BANDS).dropna()
    return inputs


def station_cube_inputs(samples: pd.DataFrame) -> xr.Dataset:
    """ln(Rrs) of the pixels with a retrieval on the sampling day, in the station cubes of step 2."""
    with xr.open_dataarray(STATION_CUBES) as cubes:
        ids = samples.index.intersection(cubes["Id"].values)
        day = cubes.sel(Id=ids).isel(time=cubes.sizes["time"] // 2, drop=True).reset_coords(drop=True).load()
    day = day.where(day.sel(variable="cloud_mask", drop=True) == 0).sel(variable=list(BANDS))
    x = day.to_dataset("variable").rename(BANDS)
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


def plot(table: pd.DataFrame, path: Path) -> None:
    """Median r over the pigments, per model and matchup, on the shared samples."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    median = table.groupby(["model", "matchup"])["r"].median().unstack("matchup")
    median = median.loc[median.mean(axis=1).sort_values().index]
    colors = ["#2a78d6", "#eb6834", "#1baf7a"]
    fig, ax = plt.subplots(figsize=(7.5, 0.45 * len(median) + 1.3), layout="constrained")
    offsets = np.linspace(-0.2, 0.2, len(median.columns))
    for (matchup, values), color, offset in zip(median.items(), colors, offsets):
        ax.plot(values, np.arange(len(median)) + offset, "o", ms=7, color=color, mec="white", mew=1, label=matchup)
    ax.set_yticks(range(len(median)), median.index, fontsize=8)
    ax.set_xlabel(f"Median r over the 11 pigments, satellite against HPLC (ln), {table['n'].max()} samples")
    ax.grid(axis="x", color="#e5e5e2", lw=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("config", help="Data config with stations_config, output_root and compare_on.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    logging.getLogger("copernicusmarine").setLevel(logging.WARNING)

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    stations = yaml.safe_load(Path(config["stations_config"]).read_text(encoding="utf-8"))["stations"]
    root = Path(config["output_root"])
    samples = write_samples(stations, root / "samples.csv")
    hplc = samples[list(PAIRS.values())].set_axis(list(PAIRS), axis=1)
    inputs = product_inputs(config, root)
    cubes = station_cube_inputs(samples)

    rows = []
    models = [name for name, (exp, _) in available_models().items() if exp["INP_VARS"] == list(BANDS.values())]
    for name in models:
        predictor = Predictor(name)
        # Loading a model disables all logging up to WARNING (pigment_retrieval keras_models)
        logging.disable(logging.NOTSET)
        predicted = {"station_cubes": predictor.predict(cubes, logged=True)[list(PAIRS)]
                     .median(["lat", "lon"]).to_dataframe()[list(PAIRS)].dropna()}
        predicted.update({m: predictor.predict(x, logged=True)[list(PAIRS)] for m, x in inputs.items()})
        if name == TASK4_MODEL:
            at = predicted["station_cubes"].index
            plot_scatter(hplc.loc[at], predicted["station_cubes"], samples.loc[at, "ST"],
                         f"{TASK4_MODEL} on the station cubes against HPLC, same day", SCATTER)
        shared = samples.index
        for matchup in config["compare_on"]:
            shared = shared.intersection(predicted[matchup].index)
        for matchup, values in predicted.items():
            rows.append(scores(hplc.loc[values.index], values).assign(model=name, matchup=matchup, samples="all"))
            if matchup in config["compare_on"]:
                rows.append(scores(hplc.loc[shared], values.loc[shared])
                            .assign(model=name, matchup=matchup, samples="shared"))
        print(f"{name}: {', '.join(f'{m} {len(v)}' for m, v in predicted.items())} samples, {len(shared)} shared")
    table = pd.concat(rows).rename_axis("pigment").reset_index()
    table.to_csv(root / "scores.csv", index=False, float_format="%.3f")
    plot(table.query("samples == 'shared'"), FIGURE)
    summary = table.groupby(["samples", "matchup", "model"])[["n", "r", "MAPE", "MPE"]].median()
    print(summary.round(2).to_string())
    print(f"{root / 'scores.csv'}, {FIGURE}, {SCATTER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
