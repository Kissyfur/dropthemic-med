# Task 1 — From radiometry to pigments

A convolutional neural network estimates 13 phytoplankton pigments from remote sensing reflectance
(Rrs), at the 11 OLCI bands or at the 5 bands of the multi-sensor record.

- Code and trained models: [pigment-retrieval-from-olci](https://github.com/Kissyfur/pigment-retrieval-from-olci),
  installed with the environment (`requirements.txt`).
- Paper: Sánchez-López, B., Talone, M., Cerquides, J., Di Cicco, A., Martínez-Fornos, G. and Slavinec, P.
  (2026). Simultaneous retrieval of 13 phytoplankton pigments from Sentinel-3 OLCI using convolutional
  neural networks and transfer learning. *Frontiers in Remote Sensing*, 7.
  https://doi.org/10.3389/frsen.2026.1880618

This folder applies the model to the satellite record of two regions and four stations, and checks
it against the HPLC pigments of the Task 2 samples. Run everything from the repository root. The
data go to `task1/data/` and the figures to `task1/figures/`, neither kept in git.

| Area | Where | Satellite data |
|---|---|---|
| `nw_mediterranean` | 40.50–43.50 N, 1.50–5.50 E | monthly maps (step 1) |
| `balearic_islands` | 38.55–40.20 N, 1.10–4.50 E | monthly maps (step 1) |
| BBMO, SOLA, MOLA, VIDA | 5 × 5 pixels around each station | daily cubes (step 2) |

BBMO is the Blanes Bay Microbial Observatory, SOLA and MOLA the coastal and offshore stations of
Banyuls-sur-Mer, and VIDA the Vida buoy off Piran, in the Gulf of Trieste.

## 1. Monthly radiometry

Each month's mean of the daily 1 km multi-sensor Rrs of Copernicus Marine, from September 1997 to
today, floored at its 5% quantile and log-transformed:

```bash
python task1/scripts/download_monthly_means.py task1/configs/med_radiometry_monthly.yaml
```

This writes `task1/data/radiometry_monthly/<region>_monthly.nc`. The first run downloads about
39 GB (26 GB for the NW Mediterranean, 13 GB for the Balearic Islands). It resumes if interrupted,
and later runs only fetch the newest months.

## 2. Daily station cubes

A cube around each station for every day of the record (5 × 5 pixels of about 1 km, ±7 days),
built with [copernicus-matchup](https://github.com/Kissyfur/copernicus-matchup). Pixels without a
satellite retrieval stay empty; each band is floored at the 5% quantile of its positive values in
the cube, then log-transformed:

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
  every day from 23 September 1997 to a week before the end of the record. Pixels without a
  satellite retrieval that day stay empty.

`--only monthly` or `--only stations` predicts one of the two. For other files, the environment
also has the `predict-pigments` command of Task 1.

## 4. Check against HPLC

The Task 2 samples (PETRIMED: SOLA, BBMO and MOLA, 196 in 2004–2021) have HPLC pigments. Each is
matched with its station cube of step 2: the 5 × 5 pixels around the station, from 7 days before
to 7 days after the sampling day. The convolutional Task 1 models of the multi-sensor bands predict
the pigments of every pixel and day with a satellite retrieval, and their median is compared with
the HPLC pigments, for the 10 pigments of the proposal:

```bash
python task1/scripts/hplc_check.py
```

The metrics are those of the Task 1 paper: the coefficient of determination R² of ln(pigment), and
the mean absolute percentage error (MAPE) and the bias (mean percentage error, MPE) of the
concentrations. The Pearson correlation r of ln(pigment) is added: unlike R², it ignores the bias,
so it shows whether the satellite pigments rise and fall with the HPLC ones. The script writes
`task1/data/hplc_check.csv` and the figures below. For the model of the record
(`multi_sat_ft/concatenatedCNN`), on all 196 samples:

| Pigment | R² | r | MAPE | Bias (MPE) |
|---|---|---|---|---|
| Chlorophyll a | 0.39 | 0.77 | 35% | −19% |
| Chlorophyll b | 0.26 | 0.60 | 75% | +11% |
| Diadinoxanthin | 0.24 | 0.68 | 55% | −18% |
| β-carotene | 0.20 | 0.55 | 48% | +10% |
| Peridinin | 0.19 | 0.50 | 122% | +52% |
| Alloxanthin | 0.05 | 0.72 | 73% | −27% |
| Fucoxanthin | 0.00 | 0.77 | 78% | −41% |
| Zeaxanthin | −0.69 | −0.06 | 394% | +379% |
| 19'-butanoyloxyfucoxanthin | −1.63 | 0.36 | 66% | −58% |
| 19'-hexanoyloxyfucoxanthin | −1.73 | 0.43 | 66% | −60% |

- R² is at most 0.39, against 0.70–0.93 in situ and about 0.2 less on satellite data in the paper,
  mostly because of biases: the satellite pigments rise and fall with the HPLC ones (r = 0.60–0.77
  for chlorophylls a and b, fucoxanthin, alloxanthin and diadinoxanthin), but fucoxanthin and the
  haptophyte and pelagophyte pigments come out at half the HPLC values or less, and zeaxanthin
  about five times higher. Zeaxanthin barely varies: it stays near 0.04 mg m⁻³.
- The underestimation is a coastal one and grows with concentration, as the satellite pigments vary
  less than the HPLC ones. Over time they follow the timing of the BBMO samples and the seasonal
  cycle of the weekly SOLA samples of 2015–2016, but not the size of their peaks. Fucoxanthin and
  the haptophyte and pelagophyte pigments come out at 13–21% of the HPLC values at SOLA, where the
  2015–2016 blooms give the highest values, and at 40–51% at BBMO. Offshore at MOLA (7 samples)
  most pigments are within about a third of HPLC.
- A bias by the same factor at all times would not change trends in % per decade or seasonal
  timing, the measures of Task 4. But the satellite pigments also vary less than the HPLC ones, so
  trends and seasonal amplitudes are damped, though their sign and timing hold, and the composition
  is distorted, which Task 2 corrects before using the pigments. A calibration
  against HPLC would correct chlorophylls a and b at other stations (a factor fitted at BBMO raises
  the R² of chlorophyll a at SOLA from 0.47 to 0.60), but not the other pigments, whose bias
  depends on the site; it is not applied, as the project applies the published models as they are.
- Of the five CNNs, the one of the record, fine-tuned with satellite matchups, has the best median
  R² (0.12, against −0.22 to −0.06) and is the best for chlorophylls a and b and fucoxanthin. The
  others do better for 19'-hexanoyloxyfucoxanthin (r = 0.58–0.60 for three of them, against 0.43)
  and peridinin, and none for zeaxanthin.
- The window, 5 × 5 pixels (about 5 km) and the sampling day ±7 days, was the best of those tried
  (the tests are not kept). With 11 × 9 pixels the median R² is 0.05 and the bias −24%, against
  0.12 and −18%: the larger area adds offshore water, with less pigment than the coastal stations.
  3 × 3 pixels reduce the bias a little more but lose 14 samples. The sampling day alone matches
  only 65 samples and agrees less with HPLC, as daily retrievals are noisy, and the global 4 km
  product with which the model was fine-tuned overestimates chlorophyll a by about 60% next to the
  coast.

<p align="center">
  <img src="report/hplc_check.png" width="80%" alt="Satellite against HPLC pigments at SOLA, BBMO and MOLA">
</p>

*`multi_sat_ft/concatenatedCNN` on the station cubes (sampling day ±7 days) against HPLC, all samples.*

<p align="center">
  <img src="report/hplc_series_BBMO.png" width="80%" alt="HPLC and satellite pigments at BBMO, 2004-2014">
</p>

*HPLC and satellite pigments at BBMO, 2004–2014; R² and r of this station.*

<p align="center">
  <img src="report/hplc_series_SOLA.png" width="80%" alt="HPLC and satellite pigments at SOLA, 2015-2016">
</p>

*HPLC and satellite pigments at SOLA, 2015–2016; R² and r of this station.*
