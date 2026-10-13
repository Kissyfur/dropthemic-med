# DROPTHEMIC-MED

**Diversity and Responses Of Plankton: Tracking MIcrobial Community structure in the MEDiterranean
Sea — from Satellite to DNA.** An OYSTER (EuroMarine) Marine ECR Cooperation Project between the
Institut de Ciències del Mar (ICM-CSIC, Barcelona) and the Marine Biology Station Piran (NIB,
Slovenia).

The project links satellite ocean colour to plankton diversity in two steps, each learnt from
existing data:
1. remote sensing reflectance (Rrs) → photosynthetic pigments;
2. pigments → plankton groups from metabarcoding.

New DNA and pigment data from the Gulf of Trieste test the second step. Both models are then
applied to more than 25 years of satellite records of the Mediterranean.

| Task | Content | Status |
|---|---|---|
| [1](#task-1--from-radiometry-to-pigments) | Pigment concentrations from radiometry | Done: model and paper |
| [2](#task-2--from-pigments-to-plankton-diversity) | Plankton groups from pigments | To come |
| [3](#task-3--plankton-diversity-in-the-gulf-of-trieste) | New metabarcoding and pigment time series at VIDA | To come |
| [4](#task-4--25-years-of-satellite-records) | Satellite radiometry → pigments → diversity, 1997 to today | In progress |

## Installation

```bash
git clone --recurse-submodules https://github.com/Kissyfur/dropthemic-med.git
cd dropthemic-med
py -3.9 -m venv .venv               # Linux / macOS: python3.9 -m venv .venv
.venv\Scripts\activate              # Linux / macOS: source .venv/bin/activate
pip install -r requirements.txt
copernicusmarine login              # once, for the Copernicus Marine downloads
```

Python 3.9 is required because the Task 1 models need TensorFlow 2.10. The environment installs:
- [pigment-retrieval-from-olci](https://github.com/Kissyfur/pigment-retrieval-from-olci) (Task 1),
  a git submodule in `external/` that includes its trained models;
- [copernicus-matchup](https://github.com/Kissyfur/copernicus-matchup), which downloads Copernicus
  Marine data and builds matchups.

Run the commands below from the repository root.

## Task 1 — From radiometry to pigments

A convolutional neural network estimates 13 phytoplankton pigments from Rrs, either at the 11 OLCI
bands or at the 5 bands of the multi-sensor record.

- Code and trained models: [pigment-retrieval-from-olci](https://github.com/Kissyfur/pigment-retrieval-from-olci),
  included in `external/pigment-retrieval-from-olci`.
- Paper: Sánchez-López, B., Talone, M., Cerquides, J., Di Cicco, A., Martínez-Fornos, G. and Slavinec, P.
  (2026). Simultaneous retrieval of 13 phytoplankton pigments from Sentinel-3 OLCI using convolutional
  neural networks and transfer learning. *Frontiers in Remote Sensing*, 7.
  https://doi.org/10.3389/frsen.2026.1880618

## Task 2 — From pigments to plankton diversity

To come.

## Task 3 — Plankton diversity in the Gulf of Trieste

To come.

## Task 4 — 25 years of satellite records

For now this covers two areas around the sampling stations, not the whole Mediterranean:

| Region | Box | Stations |
|---|---|---|
| `north_adriatic` | 44.50–45.85 N, 12.20–14.50 E | VIDA (Piran) |
| `nw_mediterranean` | 40.50–43.50 N, 1.50–5.50 E | BBMO (Blanes), SOLA and MOLA (Banyuls-sur-Mer) |

The data go to `task4/data/`, which is not kept in git.

**1. Monthly radiometry.** Each month's mean of the daily 1 km multi-sensor Rrs, from September
1997 to today, floored at its 5% quantile and log-transformed:

```bash
python task4/scripts/download_monthly_means.py task4/configs/med_radiometry_monthly.yaml
```

This writes `task4/data/radiometry_monthly/<region>_monthly.nc`. The first run downloads about
33 GB. It resumes if interrupted, and later runs only fetch the newest months.

**2. Daily station cubes.** A cube around each station for every day of the record, built with
copernicus-matchup like the training matchups:

```bash
python task4/scripts/station_matchups.py task4/configs/station_matchups.yaml
```

This writes `task4/data/station_matchups/datasets/`.

**3. Pigments.** The Task 1 model for the 5 multi-sensor bands, run from its own folder on a
monthly file. `--logged` is needed because the file already holds ln(Rrs):

```bash
cd external/pigment-retrieval-from-olci
python bin/predict.py --data ../../task4/data/radiometry_monthly/north_adriatic_monthly.nc --logged --output_dir ../../task4/data/pigments
cd ../..
```

This writes `task4/data/pigments/north_adriatic_monthly_multi_sat_ft_concatenatedCNN.nc`: the 13
pigments in mg m⁻³ on the same (time, latitude, longitude) grid.

The analysis is still to come.
