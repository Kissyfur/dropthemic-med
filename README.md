# DROPTHEMIC-MED

**Diversity and Responses Of Plankton: Tracking MIcrobial Community structure in the MEDiterranean
Sea — from Satellite to DNA.** An OYSTER (EuroMarine) Marine ECR Cooperation Project between the
Institut de Ciències del Mar (ICM-CSIC, Barcelona) and the Marine Biology Station Piran (NIB,
Slovenia).

The project links satellite ocean colour to plankton diversity in two steps, each learnt from
existing data:
1. remote sensing reflectance (Rrs) → photosynthetic pigments;
2. pigments → plankton groups from meta-omics (metagenomes and metabarcoding).

New DNA and pigment data from the Gulf of Trieste test the second step. Both models are then
applied to more than 25 years of satellite records of the NW Mediterranean, the Balearic Islands and
the Gulf of Trieste. This repository applies the published models as they are, without training
them: those of [pigment-retrieval-from-olci](https://github.com/Kissyfur/pigment-retrieval-from-olci)
(Task 1) and [PETRIMED](https://github.com/pjmramond/PETRIMED) (Task 2).

| Task | Content | Status | Folder |
|---|---|---|---|
| 1 | Pigment concentrations from radiometry | Model and paper; applied to the satellite record and checked against HPLC | [task1](task1/README.md) |
| 2 | Plankton groups from pigments | PETRIMED models, tested away from SOLA and on satellite pigments; the biodiversity indicator is to come | [task2](task2/README.md) |
| 3 | New metabarcoding and pigment time series at VIDA (monthly, 2021–2024) | To come | |
| 4 | Satellite radiometry → pigments → diversity, 1997 to today | Analysis and technical note (draft) | [task4](task4/README.md) |

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

Task 2 also needs R with the xgboost package, once, to export the PETRIMED models.

## Running

From the repository root, in this order. The README of each task describes its steps and outputs;
data and figures are written inside each task folder and are not kept in git.

```bash
# Task 1: satellite radiometry and pigments
python task1/scripts/download_monthly_means.py task1/configs/med_radiometry_monthly.yaml
python task1/scripts/station_matchups.py task1/configs/station_matchups.yaml
python task1/scripts/predict_pigments.py

# Task 2: PETRIMED models, in situ and on the satellite pigments
git clone --depth 1 https://github.com/pjmramond/PETRIMED.git task2/PETRIMED
Rscript task2/scripts/export_models.R
python task2/scripts/psts.py
python task2/scripts/predict_psts.py

# Task 1 check against the HPLC samples of Task 2, and Task 4 figures
python task1/scripts/hplc_check.py
python task4/scripts/figures.py
```

## Main results

**Task 1 — Pigments from radiometry** ([details](task1/README.md))
- The 13 pigments for every month of the 1 km multi-sensor record, 1997–2026, over the NW
  Mediterranean and the Balearic Islands, and for every day around four stations: BBMO, SOLA and
  MOLA on the Catalan and French coast, and VIDA in the Gulf of Trieste.
- Against the 196 HPLC samples of SOLA, BBMO and MOLA (station cubes, sampling day ±7 days), the
  satellite pigments rise and fall with the HPLC ones (r = 0.78 for chlorophyll a and 0.76 for
  fucoxanthin, on ln values) but are biased, so R², the metric of the paper, is at most 0.33:
  fucoxanthin and the haptophyte and pelagophyte pigments come out at half the HPLC values or less,
  and zeaxanthin about five times higher, without following the HPLC one. Bloom peaks are missed.
- The CNN of the record, fine-tuned with satellite matchups, is the best of the Task 1 CNNs at the
  stations. A window of ±7 days around the sample matters more than a larger area, which only adds
  offshore water.

**Task 2 — Plankton groups from pigments** ([details](task2/README.md); provisional)
- The PETRIMED models (Ramond et al., 2026) run in Python with the same results as in R. Trained
  at SOLA, only 4 of the 18 psbO plankton groups keep r ≥ 0.5 at BBMO: Micromonas, Synechococcus,
  Pelagophyceae and Bathycoccus.
- From the satellite pigments none holds until their composition is harmonized with the HPLC one;
  then Synechococcus does (r = 0.62 monthly, 0.89 for the seasonal cycle), mostly as a
  low-chlorophyll signal.
- The biodiversity indicator of PETRIMED is still to come; this task will be rewritten with it.

**Task 4 — 25 years of satellite records** ([technical note](task4/README.md))
- The satellite pigments carry two signals, biomass and one axis of composition (haptophyte and
  pelagophyte pigments against zeaxanthin): indicators built from them will largely re-express
  these two.
- They show the expected patterns: diatom pigments on the coast and haptophyte, pelagophyte and
  cyanobacterial ones offshore, the late-winter bloom of the Catalan coast, a winter maximum two
  months earlier around the Balearic Islands, and the years of VIDA set by the rivers.
- From 2003 to 2025 the NW Mediterranean loses chlorophyll a (−8% per decade) and fucoxanthin
  (−18%) while zeaxanthin rises (+5%), as satellite functional types do (Martínez-Fornos et al.,
  2026). The Balearic Islands change the same way, more weakly (−5%, −12%, +2%), the coastal
  stations BBMO and SOLA most strongly (chlorophyll a −17 to −19%), and VIDA has no trend.
- Around the Balearic Islands the shelf has 20% less chlorophyll a than the deep basin in winter,
  and the same in summer: it lacks part of the winter increase.
- Limits: a step in the record in 2002–2003 (change of sensors), a floor of the model near
  0.1 mg m⁻³ of chlorophyll a that the Balearic summer reaches, and a weak composition signal at
  the coast.
