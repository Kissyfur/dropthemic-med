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
git clone https://github.com/Kissyfur/dropthemic-med.git
cd dropthemic-med
py -3.9 -m venv .venv               # Linux / macOS: python3.9 -m venv .venv
.venv\Scripts\activate              # Linux / macOS: source .venv/bin/activate
pip install -r requirements.txt
copernicusmarine login              # once, for the Copernicus Marine downloads
```

Python 3.9 and TensorFlow 2.10 are the versions of the Task 1 models; TensorFlow 2.10 is also the
last version with GPU support on Windows. The environment installs from GitHub:
- [pigment-retrieval-from-olci](https://github.com/Kissyfur/pigment-retrieval-from-olci) (Task 1),
  with its trained models;
- [copernicus-matchup](https://github.com/Kissyfur/copernicus-matchup), which downloads Copernicus
  Marine data and builds matchups.

Run the commands below from the repository root.

## Task 1 — From radiometry to pigments

A convolutional neural network estimates 13 phytoplankton pigments from Rrs, either at the 11 OLCI
bands or at the 5 bands of the multi-sensor record.

- Code and trained models: [pigment-retrieval-from-olci](https://github.com/Kissyfur/pigment-retrieval-from-olci),
  installed with the environment.
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

The data go to `task4/data/` and the figures to `task4/figures/`, neither kept in git.

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

**3. Pigments.** The Task 1 model for the 5 multi-sensor bands (`multi_sat_ft/concatenatedCNN`),
on the monthly maps and on the station cubes:

```bash
python task4/scripts/predict_pigments.py
```

This writes the 13 pigments, in mg m⁻³, to `task4/data/pigments/`:
- `<region>_monthly.nc`, on the (time, latitude, longitude) grid of the monthly radiometry, with
  its `valid_days`. Means of one or two days can be unrealistic: filter on `valid_days`.
- `stations_daily.nc`, as (station, time, lat_pixel, lon_pixel): the 11 × 9 pixels of about 1 km
  around each station, every day from 30 September 1997 to two weeks before the end of the record.
  Only the pixels with a satellite retrieval that day are predicted, not the gaps that the cubes
  fill by interpolation.

`--only monthly` or `--only stations` predicts one of the two. For other files, the environment
also has the `predict-pigments` command of Task 1 (see its README).

**4. Figures.** Maps and station series of the pigments, for a first look before the diversity
analysis:

```bash
python task4/scripts/pigment_figures.py
```

This writes to `task4/figures/`:
- `<region>/<pigment>_years.png`: the mean of each complete year (1998–2025), one map per year;
- `<region>/periods.png`: every pigment (rows) averaged over four periods of about seven years
  (columns);
- `stations/<station>.png`: one panel per pigment, with the median of each month over the pixels
  around the station and its 12-month running mean.

Months with fewer than 3 days of data are left out. All the maps of a pigment share one log colour
scale. The record joins several sensors (SeaWiFS, MODIS, VIIRS, OLCI), so a change between years
can come from a change of sensor rather than of the plankton.

### Analysis

A first look at the pigments, before computing diversity indicators from them. The figures are
copies of those of step 4, kept in `task4/report/`.

- **Where.** In both regions every pigment is highest in the river plumes and along the coast (the
  Po in the western north Adriatic, the Rhône in the Gulf of Lion) and lowest offshore. The
  regional median of the annual mean chlorophyll a is 0.40–0.93 mg m⁻³ in the north Adriatic and
  0.22–0.34 mg m⁻³ in the NW Mediterranean.
- **When.** At BBMO, SOLA and MOLA most pigments peak between January and March (the late-winter
  bloom) and are lowest in July–August; zeaxanthin peaks in May and changes little over the year.
  At VIDA, chlorophyll a and fucoxanthin peak in November.
- **Year to year.** The north Adriatic varies strongly, with all pigments together: highest in
  1998, 2001, 2010–2011 and 2024, lowest in 2022–2023. This probably follows the Po discharge
  (2022 was a year of severe drought in the Po basin), to be checked with river data.
- **Long term.** In the NW Mediterranean most pigments decrease. From 2005–2011 to 2019–2025 the
  regional chlorophyll a falls 13% and fucoxanthin 26%, while zeaxanthin rises 8%; at BBMO,
  chlorophyll a falls 25% and fucoxanthin 43%. Less diatom pigment and relatively more zeaxanthin
  (picocyanobacteria) is the kind of community change the diversity indicators should measure.
- **Sensor change.** At the four stations chlorophyll a is 22–38% lower in 2005–2025 than in
  1998–2002, mostly through a step around 2003, and offshore zeaxanthin steps up at the same time
  in both regions. The step coincides with MODIS-Aqua joining the record in mid-2002, so it is
  more likely instrumental than ecological: trends should start in 2003, or be checked sensor by
  sensor.
- **Limits.** The model's chlorophyll a does not go below about 0.1 mg m⁻³, so the clearest summer
  waters are probably overestimated. The coastal stations have few clear pixels around them: 13%
  of the pixel-days at SOLA and 17% at BBMO, against 27% at VIDA and 50% at MOLA. VIDA is at the
  Vida buoy (45.5488 N, 13.5505 E); ps_mtag.csv rounds it to 45.5 N, 13.6 E, which is on land.

<p>
  <img src="task4/report/nw_mediterranean_periods.png" width="49%"
       alt="The 13 pigments in the NW Mediterranean, mean of 1998-2004, 2005-2011, 2012-2018 and 2019-2025">
  <img src="task4/report/north_adriatic_periods.png" width="49%"
       alt="The 13 pigments in the north Adriatic, mean of 1998-2004, 2005-2011, 2012-2018 and 2019-2025">
</p>

*The 13 pigments over four periods: NW Mediterranean (left) and north Adriatic (right). Circles
are the stations.*

<p>
  <img src="task4/report/BBMO_monthly.png" width="49%" alt="Monthly pigments around BBMO, 1997-2026">
  <img src="task4/report/VIDA_monthly.png" width="49%" alt="Monthly pigments around VIDA, 1997-2026">
</p>

*Monthly pigments around BBMO (left) and VIDA (right), with their 12-month running mean.*
