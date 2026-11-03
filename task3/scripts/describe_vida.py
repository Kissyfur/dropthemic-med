"""Description of the VIDA plankton groups (metabarcoding, 2021-2023).

    python task3/scripts/describe_vida.py

Reads task3/VIDA_PST.xlsx: one row per sample, with the relative abundance (%) of each plankton
group among the eukaryotes and among the prokaryotes. Prints the sampling dates and the mean, maximum
and month of maximum of each group, and writes two figures to task3/report/:
- vida_composition.png: the groups of each sample over time;
- vida_seasons.png: the seasonal cycle of the main photosynthetic groups.
Diatoms are the sum of Mediophyceae, Bacillariophyceae and Coscinodiscophyceae, and radiolarians
that of Acantharea and Polycystinea.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DATA = Path("task3/VIDA_PST.xlsx")
REPORT = Path("task3/report")
PROKARYOTES = ["Non.Photosynthetic.Prokaryotes", "Other.Cyanobacteria", "Synechococcus", "Prochlorococcus",
               "Cyanobium"]
GROUPS = {"Diatoms": ["Mediophyceae", "Bacillariophyceae", "Coscinodiscophyceae"],
          "Radiolarians": ["Acantharea", "Polycystinea"],
          "Other cyanobacteria": ["Other.Cyanobacteria", "Prochlorococcus"]}
# Stacked in this order, with the categorical palette in its fixed order; grey is the rest
EUKARYOTE_STACK = ["Diatoms", "Radiolarians", "MOCH", "Dinophyceae", "Haptophyta", "Ciliates"]
PROKARYOTE_STACK = ["Synechococcus", "Cyanobium"]
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER, INK, GRID = "#c3c2b7", "#52514e", "#e5e5e2"
SEASONS = {"Synechococcus": "% of prokaryotes", "Diatoms": "% of eukaryotes", "Dinophyceae": "% of eukaryotes",
           "Haptophyta": "% of eukaryotes"}


def read() -> pd.DataFrame:
    data = pd.read_excel(DATA).sort_values("Date").set_index("Date")
    for name, members in GROUPS.items():
        data[name] = data[members].sum(axis=1)
    return data


def eukaryote_groups(data: pd.DataFrame) -> list[str]:
    first = data.columns.get_loc("Non.Photosynthetic.Eukaryotes")
    return [c for c in data.columns[first:] if c not in PROKARYOTES and c not in GROUPS]


def describe(data: pd.DataFrame) -> None:
    first = data.iloc[0]
    print(f"{len(data)} samples, {data.index.min():%Y-%m-%d} to {data.index.max():%Y-%m-%d}, at "
          f"{first['Lat']} N, {first['Long']} E, {first['Depth']} m, fraction {first['SF']}")
    print(data.index.to_series().groupby(data.index.year).apply(lambda d: ", ".join(d.dt.strftime("%b"))).to_string())
    for domain, columns in [("eukaryotes", eukaryote_groups(data) + ["Diatoms", "Radiolarians"]),
                            ("prokaryotes", PROKARYOTES + ["Other cyanobacteria"])]:
        table = pd.DataFrame({"mean": data[columns].mean(), "max": data[columns].max(),
                              "month of max": data[columns].idxmax().dt.strftime("%Y-%m")})
        print(f"\n% of {domain}:")
        print(table.sort_values("mean", ascending=False).round(2).to_string())


def stack(ax, data: pd.DataFrame, names: list[str], colors: list[str], rest: pd.Series, rest_label: str,
          ylabel: str) -> None:
    bottom = pd.Series(0.0, index=data.index)
    for name, color in zip(names, colors):
        ax.bar(data.index, data[name], bottom=bottom, width=10, color=color, edgecolor="white", linewidth=0.6,
               label=name)
        bottom += data[name]
    ax.bar(data.index, rest, bottom=bottom, width=10, color=OTHER, edgecolor="white", linewidth=0.6,
           label=rest_label)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    handles, labels = ax.get_legend_handles_labels()
    # Listed as stacked, top first
    ax.legend(handles[::-1], labels[::-1], loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, fontsize=8)


def plot_composition(data: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.6), sharex=True, layout="constrained")
    euk = eukaryote_groups(data)
    named = set(EUKARYOTE_STACK) | {m for g in EUKARYOTE_STACK for m in GROUPS.get(g, [])}
    rest = data[[c for c in euk if c not in named and c != "Non.Photosynthetic.Eukaryotes"]].sum(axis=1)
    stack(axes[0], data, EUKARYOTE_STACK, PALETTE[:len(EUKARYOTE_STACK)], rest, "other groups",
          "% of eukaryotes")
    axes[0].set_title("Eukaryotes, without the non-photosynthetic ones (the rest up to 100%)", fontsize=9,
                      loc="left")
    stack(axes[1], data, PROKARYOTE_STACK, PALETTE[6:8], data["Other cyanobacteria"],
          "other cyanobacteria", "% of prokaryotes")
    axes[1].set_title("Prokaryotes: cyanobacteria (non-photosynthetic prokaryotes are the rest up to 100%)",
                      fontsize=9, loc="left")
    fig.suptitle("Plankton groups at VIDA, metabarcoding of each sample")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_seasons(data: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10, 6), sharex=True, layout="constrained")
    month = data.index.month
    for ax, (name, unit) in zip(axes.flat, SEASONS.items()):
        # Months without samples (August, September) break the line
        mean = data[name].groupby(month).mean().reindex(range(1, 13))
        ax.plot(mean.index, mean, color=INK, lw=1.4, label="mean of the samples of the month")
        for color, (year, values) in zip(PALETTE, data[name].groupby(data.index.year)):
            ax.plot(values.index.month, values, "o", ms=6, color=color, mec="white", mew=1, label=str(year))
        ax.set_title(f"{name} ({unit})", fontsize=9, loc="left")
        ax.set_xticks(range(1, 13), ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="outside lower center", ncol=4, frameon=False,
               fontsize=8)
    fig.suptitle("Seasonal cycle at VIDA, 2021-2023")
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> int:
    data = read()
    describe(data)
    plot_composition(data, REPORT / "vida_composition.png")
    plot_seasons(data, REPORT / "vida_seasons.png")
    print(f"\n{REPORT / 'vida_composition.png'}, {REPORT / 'vida_seasons.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
