"""Validation of the chain of Tasks 1 and 2 with the plankton groups observed at VIDA.

    python task3/scripts/validate_chain.py

For each VIDA sample, the satellite pigments of Task 1 around VIDA in its month (median of the month,
as in Task 2) are made relative and corrected as in task2/scripts/predict_psts.py, and go to the
PETRIMED metabarcoding models, whose units are those of the VIDA data: % of the eukaryotes or of the
prokaryotes. Each VIDA group with models is compared with its prediction by the pico (0.2-3 um) and
the nano (3-20 um) models, both different from the > 0.8 um fraction of VIDA, from the corrected
and, for reference, the uncorrected pigments. Needs the outputs of Tasks 1 and 2 (stations_daily.nc,
pigment_factors.csv and the exported models). Prints the comparison and writes
task3/report/vida_chain.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "task2/scripts")
import predict_psts as pp  # noqa: E402
import psts  # noqa: E402

DATA = Path("task3/VIDA_PST.xlsx")
FIGURE = Path("task3/report/vida_chain.png")
FIGURE_GROUPS = ["Synechococcus", "MOCH", "Mediophyceae", "Dinophyceae"]
FRACTIONS = ["pico", "nano"]


def main() -> int:
    vida = pd.read_excel(DATA).sort_values("Date").reset_index(drop=True)
    months = vida["Date"].dt.to_period("M").dt.to_timestamp()
    pigments = pp.from_task1(pp.satellite_monthly().loc["VIDA"].reindex(months).set_axis(vida.index)).dropna()
    shares = psts.relative(pigments)
    inputs = {"corrected": pp.correct(shares), "uncorrected": shares}
    print(f"{len(pigments)} of {len(vida)} VIDA samples have satellite pigments in their month")

    summary = pd.read_csv(psts.MODELS_DIR / "summary.csv")
    with_models = set(summary.query("set == 'metab_pico'")["pst"]) & set(summary.query("set == 'metab_nano'")["pst"])
    rows, series = [], {}
    for group in [c for c in vida.columns if c in with_models]:
        observed = vida.loc[pigments.index, group]
        row = {"group": group, "observed %": observed.mean()}
        predicted = {}
        for fraction in FRACTIONS:
            models = psts.load_models(group, f"metab_{fraction}")
            for name, x in inputs.items():
                values = pd.Series(psts.predict(models, x), index=x.index)
                row[f"r {fraction} {name}"] = psts.pearson(observed, values)[0]
                if name == "corrected":
                    row[f"predicted % {fraction}"] = values.mean()
                    predicted[f"{fraction} models"] = values
        rows.append(row)
        if group in FIGURE_GROUPS:
            series[group] = {"observed": observed, **predicted}
    table = pd.DataFrame(rows).set_index("group").sort_values("observed %", ascending=False)
    pd.set_option("display.width", 200)
    print(table.round(2).to_string())

    psts.plot_check(vida["Date"], {g: series[g] for g in FIGURE_GROUPS},
                    "VIDA: observed and predicted from the corrected satellite pigments of each month", FIGURE,
                    ylabel="% of the domain")
    print(FIGURE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
