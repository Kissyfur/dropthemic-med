"""Plankton groups (PSTs) from pigments with the PETRIMED models, and how well they transfer.

    python task2/scripts/psts.py

PETRIMED (task2/PETRIMED) trained XGBoost models at SOLA, in 2015-2016, that predict the abundance
of plankton sequence types (PSTs) in the pico (0.2-3 um) and nano (3-20 um) fractions from the
relative composition of 12 HPLC pigments. There is one set of models for each way of measuring
the PSTs: psbO gene (psbo), metagenome-assembled genomes (mags) and metabarcoding (metab).
export_models.R exports the models with a validation correlation of at least 0.6, which PETRIMED
averages, to task2/data/models.

The satellite pigments of Task 1 have a composition outside the one the models learned (e.g. a
zeaxanthin share around 0.10, against about 0.01 at SOLA), so harmonize() first maps each pigment
share, by quantiles, from its distribution in the satellite record at the NW Mediterranean
stations to its distribution in the HPLC samples of SOLA and MOLA. The quantiles are saved in
task2/data/pigment_quantiles.csv.

The pico models of psbo and mags are then tested at BBMO (100 samples, 2004-2014), where they were
not trained and which the harmonization does not use, with the Pearson correlation between
predicted and observed abundance, from
- the HPLC pigments (hplc), also at SOLA (mostly training samples) and MOLA (7 samples);
- the HPLC pigments with prasinoxanthin, which Task 1 does not estimate, replaced by
  PRASINO_PER_CHLB x chlorophyll b (no_prasino);
- the satellite pigments around BBMO, median of the month of each sample, as they are (satellite)
  and harmonized (harmonized), also for the mean seasonal cycle (harmonized_seasonal).
The results go to task2/data/transferability.csv, and task2/figures/bbmo_check.png shows the
observed and predicted abundance at BBMO of the PSTs in CHECK.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
import xgboost as xgb

MODELS_DIR = Path("task2/data/models")
DATA_DIR = Path("task2/PETRIMED/DATA")
SATELLITE = Path("task4/data/pigments/stations_daily.nc")
QUANTILES = Path("task2/data/pigment_quantiles.csv")
OUTPUT = Path("task2/data/transferability.csv")
FIGURE = Path("task2/figures/bbmo_check.png")
CHECK = [("psbo", "Synechococcus"), ("psbo", "Bathycoccus")]
MIN_DAYS = 3

# The pigments of the models, in their order, with the name of the same pigment in Task 1
PIGMENTS = {"Chl_C2": "chc12", "Peridinine": "perid", "X19BF": "btfcx", "Fucoxanthin": "fucox",
            "Prasinoxanthin": None, "X19HF": "hxfcx", "Diadinoxanthin": "diadi", "Alloxanthin": "allox",
            "Zeaxanthin": "zeaxa", "Chl_b": "chl_b", "Chl_a": "chl_a", "bb_Carotene": "betac"}
# Median prasinoxanthin / chlorophyll b at SOLA, where the models were trained
PRASINO_PER_CHLB = 0.30


def read_insitu(method: str) -> pd.DataFrame:
    """PETRIMED's table of HPLC pigments and observed PSTs at SOLA, BBMO and MOLA."""
    data = pd.read_csv(DATA_DIR / f"mola_bbmo_sola_pigments_{method}_pst_rpkm.csv", parse_dates=["Date"])
    data = data.rename(columns={"19BF": "X19BF", "19HF": "X19HF"})
    return data.replace({"SF": {"0.2-3 um": "PICO", "3-20 um": "NANO"}})


def from_task1(pigments: pd.DataFrame) -> pd.DataFrame:
    """The pigments of the models from those of Task 1, with prasinoxanthin from chlorophyll b."""
    x = pd.DataFrame({name: pigments[task1] for name, task1 in PIGMENTS.items() if task1})
    return estimate_prasinoxanthin(x)


def estimate_prasinoxanthin(pigments: pd.DataFrame) -> pd.DataFrame:
    return pigments.assign(Prasinoxanthin=PRASINO_PER_CHLB * pigments["Chl_b"])[list(PIGMENTS)]


def relative(pigments: pd.DataFrame) -> pd.DataFrame:
    """As PETRIMED: zeros set to half the smallest positive value of their pigment, then each sample
    divided by its total."""
    x = pigments[list(PIGMENTS)].apply(lambda col: col.mask(col == 0, col[col > 0].min() / 2))
    return x.div(x.sum(axis=1), axis=0)


def harmonize(shares: pd.DataFrame) -> pd.DataFrame:
    """Satellite pigment shares mapped by quantiles onto the HPLC ones, then made relative again."""
    q = pd.read_csv(QUANTILES)
    mapped = pd.DataFrame({p: np.interp(shares[p], q[f"{p}_satellite"], q[f"{p}_hplc"]) for p in PIGMENTS},
                          index=shares.index)
    return mapped.div(mapped.sum(axis=1), axis=0)


def load_models(method: str, fraction: str, pst: str) -> list[xgb.Booster]:
    models = []
    for line in (MODELS_DIR / f"{method}_{fraction}" / f"{pst}.jsonl").read_text().splitlines():
        # xgboost 3 writes base_score as a list, which xgboost 2.1 does not read
        line = re.sub(r'"base_score":"\[([^\]]+)\]"', r'"base_score":"\1"', line)
        model = xgb.Booster()
        model.load_model(bytearray(line, "utf-8"))
        models.append(model)
    return models


def predict(models: list[xgb.Booster], relative_pigments: pd.DataFrame) -> np.ndarray:
    """As PETRIMED: the mean of the models' predictions, with negative ones set to 0."""
    x = xgb.DMatrix(relative_pigments[list(PIGMENTS)].to_numpy(np.float32), feature_names=list(PIGMENTS))
    total = np.zeros(x.num_row())
    for model in models:
        total += np.maximum(model.predict(x), 0)
    return total / len(models)


def satellite_monthly() -> pd.DataFrame:
    """Task 4 satellite pigments around each station: median of each month, indexed by (station, time)."""
    with xr.open_dataset(SATELLITE) as satellite:
        satellite = satellite.load()
    days = satellite["chl_a"].notnull().any(["lat_pixel", "lon_pixel"]).resample(time="MS").sum()
    monthly = satellite.resample(time="MS").median(dim=["time", "lat_pixel", "lon_pixel"]).where(days >= MIN_DAYS)
    return monthly.reset_coords(drop=True).to_dataframe().reset_index().set_index(["station", "time"])


def save_quantiles(satellite: pd.DataFrame, insitu: pd.DataFrame) -> None:
    """Quantiles of the satellite shares at the NW Mediterranean stations and of the HPLC shares at
    SOLA and MOLA (not BBMO, kept for the test)."""
    sat = relative(from_task1(satellite.loc[["BBMO", "SOLA", "MOLA"]]).dropna())
    hplc = relative(estimate_prasinoxanthin(insitu.loc[insitu["ST"] != "BBMO", list(PIGMENTS)]))
    levels = np.linspace(0, 1, 101)
    table = {"quantile": levels}
    for p in PIGMENTS:
        table[f"{p}_satellite"], table[f"{p}_hplc"] = np.quantile(sat[p], levels), np.quantile(hplc[p], levels)
    QUANTILES.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(table).to_csv(QUANTILES, index=False)


def pearson(observed, predicted) -> tuple[float, int]:
    observed, predicted = np.asarray(observed, float), np.asarray(predicted, float)
    ok = np.isfinite(observed) & np.isfinite(predicted)
    if ok.sum() < 3 or np.std(predicted[ok]) == 0 or np.std(observed[ok]) == 0:
        return np.nan, int(ok.sum())
    return float(np.corrcoef(observed[ok], predicted[ok])[0, 1]), int(ok.sum())


def plot_check(dates: pd.Series, series: dict) -> None:
    """Observed abundance at BBMO, and predicted from HPLC and from harmonized satellite pigments."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    styles = {"observed": ("#52514e", "observed (psbO)"), "hplc": ("#2a78d6", "predicted from HPLC pigments"),
              "harmonized": ("#eb6834", "predicted from harmonized satellite pigments")}
    fig, axes = plt.subplots(len(series), 1, figsize=(10, 2.6 * len(series)), sharex=True, layout="constrained")
    for ax, ((method, pst), values) in zip(np.atleast_1d(axes), series.items()):
        for name, (color, label) in styles.items():
            ax.plot(dates[values[name].index], values[name], color=color, lw=1.6 if name == "observed" else 1.2,
                    marker="o" if name == "observed" else None, ms=3, label=label)
        r_hplc, _ = pearson(values["observed"], values["hplc"])
        r_sat, _ = pearson(values["observed"][values["harmonized"].index], values["harmonized"])
        ax.set_title(f"{pst} (pico, {method}): r = {r_hplc:.2f} from HPLC, {r_sat:.2f} from satellite pigments",
                     fontsize=9, loc="left")
        ax.set_ylabel("RPKM")
        ax.grid(axis="y", color="#e5e5e2", lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.legend(*np.atleast_1d(axes)[0].get_legend_handles_labels(), loc="outside lower center", ncol=3,
               frameon=False, fontsize=8)
    fig.suptitle("PETRIMED models at BBMO, where they were not trained")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE, dpi=150)
    plt.close(fig)


def main() -> int:
    summary = pd.read_csv(MODELS_DIR / "summary.csv")
    check = {}
    satellite = satellite_monthly()
    save_quantiles(satellite, read_insitu("psbo").query("SF == 'PICO'"))
    rows = []
    for method in ["psbo", "mags"]:
        pico = read_insitu(method).query("SF == 'PICO'")
        bbmo = pico[pico["ST"] == "BBMO"]
        months = bbmo["Date"].dt.to_period("M").dt.to_timestamp()
        at_bbmo = from_task1(satellite.reindex(pd.MultiIndex.from_arrays([bbmo["ST"], months]))
                             .set_axis(bbmo.index)).dropna()
        # Pigments made relative within each station, as PETRIMED
        inputs = {
            "hplc": pico.groupby("ST", group_keys=False)[list(PIGMENTS)].apply(relative),
            "no_prasino": pico.groupby("ST", group_keys=False)[list(PIGMENTS)]
                              .apply(lambda g: relative(estimate_prasinoxanthin(g))),
            "satellite": relative(at_bbmo),
            "harmonized": harmonize(relative(at_bbmo)),
        }
        for row in summary.query("method == @method and fraction == 'pico'").itertuples():
            models = load_models(method, "pico", row.pst)
            result = {"method": method, "fraction": "pico", "pst": row.pst, "models": row.models,
                      "cor_valid": row.cor_valid}
            for name, x in inputs.items():
                predicted = pd.Series(predict(models, x), index=x.index)
                for station in ["SOLA", "BBMO", "MOLA"]:
                    at = pico.index[pico["ST"] == station].intersection(x.index)
                    if len(at):
                        result[f"r_{station}_{name}"], result[f"n_{station}_{name}"] = pearson(
                            pico.loc[at, row.pst], predicted[at])
                if name == "harmonized":
                    month = bbmo["Date"].dt.month
                    result["r_BBMO_harmonized_seasonal"], _ = pearson(
                        bbmo[row.pst].groupby(month).mean(), predicted.groupby(month[x.index]).mean())
                if (method, row.pst) in CHECK and name in ("hplc", "harmonized"):
                    check.setdefault((method, row.pst), {"observed": bbmo[row.pst]})[name] = \
                        predicted[predicted.index.intersection(bbmo.index)]
            rows.append(result)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT, index=False, float_format="%.3f")
    plot_check(read_insitu("psbo")["Date"], check)
    print(table[["method", "pst", "models", "r_BBMO_hplc", "r_BBMO_no_prasino", "r_BBMO_satellite",
                 "r_BBMO_harmonized", "r_BBMO_harmonized_seasonal"]].round(2).to_string(index=False))
    print(f"{OUTPUT}, {QUANTILES}, {FIGURE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
