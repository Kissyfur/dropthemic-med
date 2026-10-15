# Task 1 — From radiometry to pigments

A convolutional neural network estimates 13 phytoplankton pigments from remote sensing reflectance
(Rrs), at the 11 OLCI bands or at the 5 bands of the multi-sensor record.

- Code and trained models: [pigment-retrieval-from-olci](https://github.com/Kissyfur/pigment-retrieval-from-olci),
  installed with the environment (`requirements.txt`).
- Paper: Sánchez-López, B., Talone, M., Cerquides, J., Di Cicco, A., Martínez-Fornos, G. and Slavinec, P.
  (2026). Simultaneous retrieval of 13 phytoplankton pigments from Sentinel-3 OLCI using convolutional
  neural networks and transfer learning. *Frontiers in Remote Sensing*, 7.
  https://doi.org/10.3389/frsen.2026.1880618

This folder applies the model to the satellite record of the two study regions, and checks it
against the HPLC pigments of the Task 2 samples. Run everything from the repository root. The data
go to `task1/data/` and the figures to `task1/figures/`, neither kept in git.

| Region | Box | Stations |
|---|---|---|
| `north_adriatic` | 44.50–45.85 N, 12.20–14.50 E | VIDA (Vida buoy, Piran) |
| `nw_mediterranean` | 40.50–43.50 N, 1.50–5.50 E | BBMO (Blanes), SOLA and MOLA (Banyuls-sur-Mer) |

## 1. Monthly radiometry

Each month's mean of the daily 1 km multi-sensor Rrs of Copernicus Marine, from September 1997 to
today, floored at its 5% quantile and log-transformed:

```bash
python task1/scripts/download_monthly_means.py task1/configs/med_radiometry_monthly.yaml
```

This writes `task1/data/radiometry_monthly/<region>_monthly.nc`. The first run downloads about
33 GB. It resumes if interrupted, and later runs only fetch the newest months.

## 2. Daily station cubes

A cube around each station for every day of the record (11 × 9 pixels of about 1 km, ±7 days),
built with [copernicus-matchup](https://github.com/Kissyfur/copernicus-matchup):

```bash
python task1/scripts/station_matchups.py task1/configs/station_matchups.yaml
```

This writes `task1/data/station_matchups/datasets/`. VIDA is at the Vida buoy (45.5488 N, 13.5505
E); the table of the Task 2 samples (ps_mtag.csv) rounds it to 45.5 N, 13.6 E, which is on land.

## 3. Pigments

The model for the 5 multi-sensor bands fine-tuned with satellite matchups
(`multi_sat_ft/concatenatedCNN`), on the monthly maps and on the station cubes:

```bash
python task1/scripts/predict_pigments.py
```

This writes the 13 pigments, in mg m⁻³, to `task1/data/pigments/`:
- `<region>_monthly.nc`, on the (time, latitude, longitude) grid of the monthly radiometry, with
  its `valid_days`. Means of one or two days can be unrealistic: filter on `valid_days`.
- `stations_daily.nc`, as (station, time, lat_pixel, lon_pixel): the pixels around each station,
  every day from 30 September 1997 to two weeks before the end of the record. Only the pixels with
  a satellite retrieval that day are predicted, not the gaps that the cubes fill by interpolation.

`--only monthly` or `--only stations` predicts one of the two. For other files, the environment
also has the `predict-pigments` command of Task 1.

## 4. Check against HPLC

The Task 2 samples (PETRIMED: SOLA, BBMO and MOLA, 196 in 2004–2021) have HPLC pigments. Each is
matched with its station cube of step 2: the 11 × 9 pixels around the station, from 7 days before
to 7 days after the sampling day. The convolutional Task 1 models of the multi-sensor bands predict
the pigments of every pixel and day with a satellite retrieval, and their median is compared with
the HPLC pigments with the metrics of Task 1 on ln(pigment):

```bash
python task1/scripts/hplc_check.py
```

It writes `task1/data/hplc_check.csv` and the figure below. For the model of the record
(`multi_sat_ft/concatenatedCNN`), on all 196 samples:

| Pigment | r (ln) | MAPE | Bias (MPE) |
|---|---|---|---|
| Chlorophyll a | 0.78 | 37% | −25% |
| Fucoxanthin | 0.76 | 75% | −51% |
| Chlorophyll c (HPLC: c2 only) | 0.74 | 61% | −19% |
| Alloxanthin | 0.71 | 75% | −29% |
| Diadinoxanthin | 0.67 | 56% | −23% |
| Chlorophyll b | 0.63 | 72% | +3% |
| β-carotene | 0.52 | 46% | +5% |
| Peridinin | 0.46 | 122% | +50% |
| 19'-hexanoyloxyfucoxanthin | 0.45 | 66% | −60% |
| 19'-butanoyloxyfucoxanthin | 0.38 | 66% | −59% |
| Zeaxanthin | −0.05 | 401% | +389% |

- The satellite pigments follow the HPLC ones for chlorophylls a and c, fucoxanthin, alloxanthin and
  diadinoxanthin, but miss the highest values (the SOLA samples of 2015–2016). The haptophyte and
  pelagophyte pigments barely vary, and zeaxanthin not at all: it stays near 0.04 mg m⁻³, several
  times the HPLC values.
- The two CNNs trained with satellite matchups do best: median r over the 11 pigments 0.63 for the
  fine-tuned one of the record and 0.64 for `multi_sat_preft/cnn`, against 0.53–0.55 for those
  trained only with in situ data. The record's is better for chlorophylls a, b and c, fucoxanthin
  and alloxanthin; `multi_sat_preft/cnn` for 19'-hexanoyloxyfucoxanthin (r = 0.64 against 0.45)
  and peridinin.
- This window was the best of those tried (the tests are not kept). The window matters more in
  time than in space: the sampling day alone matches only 92 samples, and on the samples that all
  the windows share it agrees less with HPLC (median r 0.64 against 0.69), as daily retrievals are
  noisy. Larger areas, up to about 30 km, do not do better: they add offshore water, with less
  chlorophyll than the stations. Nor do the 3 × 3 pixels and ±1 day of the global 4 km product
  with which the model was fine-tuned (median r 0.40 against 0.63 on 149 shared samples): next to
  the coast its pixels overestimate chlorophyll a by about 60%.

<p align="center">
  <img src="report/hplc_check.png" width="80%" alt="Satellite against HPLC pigments at SOLA, BBMO and MOLA">
</p>

*`multi_sat_ft/concatenatedCNN` on the station cubes (sampling day ±7 days) against HPLC.*
