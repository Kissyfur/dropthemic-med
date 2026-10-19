"""Plankton groups (PSTs) from pigments with the PETRIMED models, and how well they transfer.

    python task2/scripts/psts.py

PETRIMED (task2/PETRIMED) trained XGBoost models at SOLA, in 2015-2016, that predict the abundance
of plankton sequence types (PSTs) from the relative composition of 12 HPLC pigments. Here the pico
(0.2-3 um) psbO models are used, those with a validation correlation of at least 0.6, which
PETRIMED averages, exported by export_models.R to task2/data/models.

They are tested on the HPLC pigments of BBMO (100 samples, 2004-2014) and MOLA (7, 2020-2021),
where they were not trained, with the Pearson correlation between predicted and observed
abundance, from
- the HPLC pigments (hplc), also at SOLA (mostly training samples);
- the HPLC pigments with prasinoxanthin, which Task 1 does not estimate, replaced by
  PRASINO_PER_CHLB x chlorophyll b (no_prasino).
The results go to task2/data/transferability.csv, and task2/figures/insitu_check.png shows the
observed and predicted abundance at BBMO of the PSTs in CHECK.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

MODELS_DIR = Path("task2/data/models")
DATA_DIR = Path("task2/PETRIMED/DATA")
OUTPUT = Path("task2/data/transferability.csv")
FIGURE = Path("task2/figures/insitu_check.png")
CHECK = ["Micromonas", "Synechococcus", "Pelagophyceae", "Bathycoccus"]

# The pigments of the models, in their order
PIGMENTS = ["Chl_C2", "Peridinine", "X19BF", "Fucoxanthin", "Prasinoxanthin", "X19HF", "Diadinoxanthin",
            "Alloxanthin", "Zeaxanthin", "Chl_b", "Chl_a", "bb_Carotene"]
# Median prasinoxanthin / chlorophyll b at SOLA, where the models were trained
PRASINO_PER_CHLB = 0.30


def read_insitu() -> pd.DataFrame:
    """PETRIMED's table of HPLC pigments and observed pico psbO PSTs at SOLA, BBMO and MOLA."""
    data = pd.read_csv(DATA_DIR / "mola_bbmo_sola_pigments_psbo_pst_rpkm.csv", parse_dates=["Date"])
    return data[data["SF"] == "PICO"].rename(columns={"19BF": "X19BF", "19HF": "X19HF"})


def estimate_prasinoxanthin(pigments: pd.DataFrame) -> pd.DataFrame:
    return pigments.assign(Prasinoxanthin=PRASINO_PER_CHLB * pigments["Chl_b"])[PIGMENTS]


def relative(pigments: pd.DataFrame) -> pd.DataFrame:
    """As PETRIMED: zeros set to half the smallest positive value of their pigment, then each sample
    divided by its total."""
    x = pigments[PIGMENTS].apply(lambda col: col.mask(col == 0, col[col > 0].min() / 2))
    return x.div(x.sum(axis=1), axis=0)


def load_models(pst: str) -> list[xgb.Booster]:
    models = []
    for line in (MODELS_DIR / f"{pst}.jsonl").read_text().splitlines():
        # xgboost 3 writes base_score as a list, which xgboost 2.1 does not read
        line = re.sub(r'"base_score":"\[([^\]]+)\]"', r'"base_score":"\1"', line)
        model = xgb.Booster()
        model.load_model(bytearray(line, "utf-8"))
        models.append(model)
    return models


def predict(models: list[xgb.Booster], relative_pigments: pd.DataFrame) -> np.ndarray:
    """As PETRIMED: the mean of the models' predictions, with negative ones set to 0."""
    x = xgb.DMatrix(relative_pigments[PIGMENTS].to_numpy(np.float32), feature_names=PIGMENTS)
    total = np.zeros(x.num_row())
    for model in models:
        total += np.maximum(model.predict(x), 0)
    return total / len(models)


def pearson(observed, predicted) -> tuple[float, int]:
    observed, predicted = np.asarray(observed, float), np.asarray(predicted, float)
    ok = np.isfinite(observed) & np.isfinite(predicted)
    if ok.sum() < 3 or np.std(predicted[ok]) == 0 or np.std(observed[ok]) == 0:
        return np.nan, int(ok.sum())
    return float(np.corrcoef(observed[ok], predicted[ok])[0, 1]), int(ok.sum())


def plot_check(dates: pd.Series, series: dict, title: str, path: Path) -> None:
    """One panel per PST: observed abundance and predictions. `series[pst]` is a dict
    {"observed": Series, "<source of the pigments>": predicted Series, ...} indexed like `dates`."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = ["#52514e", "#2a78d6", "#eb6834"]
    fig, axes = plt.subplots(len(series), 1, figsize=(10, 2.3 * len(series) + 0.6), sharex=True, squeeze=False,
                             layout="constrained")
    for ax, (pst, values) in zip(axes[:, 0], series.items()):
        observed = values["observed"]
        for color, (source, values_) in zip(colors, values.items()):
            first = source == "observed"
            ax.plot(dates[values_.index], values_, color=color, lw=1.6 if first else 1.2,
                    marker="o" if first else None, ms=3, label=source if first else f"predicted from {source}")
        r = ", ".join(f"{pearson(observed[v.index], v)[0]:.2f} from {source}"
                      for source, v in values.items() if source != "observed")
        ax.set_title(f"{pst}: r = {r}", fontsize=9, loc="left")
        ax.set_ylabel("RPKM")
        ax.grid(axis="y", color="#e5e5e2", lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="outside lower center", ncol=3, frameon=False,
               fontsize=8)
    fig.suptitle(title)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> int:
    summary = pd.read_csv(MODELS_DIR / "summary.csv")
    pico = read_insitu()
    # Pigments made relative within each station, as PETRIMED
    inputs = {
        "hplc": pico.groupby("ST", group_keys=False)[PIGMENTS].apply(relative),
        "no_prasino": pico.groupby("ST", group_keys=False)[PIGMENTS]
                          .apply(lambda g: relative(estimate_prasinoxanthin(g))),
    }
    rows, check = [], {}
    for row in summary.itertuples():
        models = load_models(row.pst)
        result = {"pst": row.pst, "models": row.models, "cor_valid": row.cor_valid}
        for name, x in inputs.items():
            predicted = pd.Series(predict(models, x), index=x.index)
            for station in ["SOLA", "BBMO", "MOLA"]:
                at = pico.index[pico["ST"] == station]
                result[f"r_{station}_{name}"], result[f"n_{station}_{name}"] = pearson(
                    pico.loc[at, row.pst], predicted[at])
            if row.pst in CHECK and name == "hplc":
                at = pico.index[pico["ST"] == "BBMO"]
                check[row.pst] = {"observed": pico.loc[at, row.pst], "HPLC pigments": predicted[at]}
        rows.append(result)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT, index=False, float_format="%.3f")
    plot_check(pico["Date"], {pst: check[pst] for pst in CHECK},
               "PETRIMED models (pico, psbO) at BBMO, where they were not trained", FIGURE)
    print(table[["pst", "models", "cor_valid", "r_BBMO_hplc", "r_BBMO_no_prasino", "r_MOLA_hplc"]]
          .round(2).to_string(index=False))
    print(f"{OUTPUT}, {FIGURE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
