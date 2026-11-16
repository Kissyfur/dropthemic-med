# Task 3 — Plankton groups at VIDA

A metabarcoding time series of the plankton at the Vida buoy, off Piran in the Gulf of Trieste
(45.549 N, 13.551 E), from January 2021 to December 2023. The sequences are summarized into the
plankton groups (plankton sequence types, PSTs) of PETRIMED ([Task 2](../task2/README.md)), so that
the groups predicted from satellite data can be compared with those observed in the Gulf of
Trieste.

## 1. The data

`task3/VIDA_PST.xlsx`: one sheet, one row per sample, 23 samples.

| Column | Content |
|---|---|
| `ID_Prokaryota`, `ID_Eukaryota` | Codes of the sample in the prokaryote and eukaryote sequencing |
| `Date` | Sampling day |
| `Depth`, `Lat`, `Long`, `ST` | 1 m, 45.54875 N, 13.5507 E, VIDA |
| `SF` | Size fraction: > 0.8 µm |
| 21 eukaryote groups, `Non.Photosynthetic.Eukaryotes` to `Eustigmatophyceae` | Relative abundance, % of the eukaryotes (100% per sample) |
| 5 prokaryote groups, `Non.Photosynthetic.Prokaryotes` to `Cyanobium` | Relative abundance, % of the prokaryotes (100% per sample) |

Samples were taken about once a month, never in August or September:

| Year | Months sampled |
|---|---|
| 2021 | January to July, October, December (twice) |
| 2022 | January to May, October, December |
| 2023 | March, May, July, October, November, December |

- The groups are those of PETRIMED's metabarcoding table at SOLA, with some differences. VIDA has
  no Bathycoccus, Micromonas or Chlorodendrales, and its other green algae (`Other.Chlorophyta`)
  are zero in every sample. It adds radiolarians (`Acantharea`, `Polycystinea`), `Chlorarachnida`,
  `Pinguiophyceae`, `Eustigmatophyceae` (always zero), `Cyanobium` and an `Unknown` group.
- The size fraction is > 0.8 µm, against the pico (0.2–3 µm) and nano (3–20 µm) fractions at SOLA:
  a difference foreseen in the proposal (Risk 2).
- The sample of 3 March 2023 has the eukaryote code `Feb23.0`; the analysis uses `Date`.

## 2. Description

```bash
python task3/scripts/describe_vida.py
```

It prints the sampling dates and the mean and maximum of each group, and draws the two figures
below into `task3/report/`. Diatoms are the sum of `Mediophyceae`, `Bacillariophyceae` and
`Coscinodiscophyceae`, and radiolarians that of `Acantharea` and `Polycystinea`.

| Group | Mean | Range | Maximum |
|---|---|---|---|
| *% of the eukaryotes* | | | |
| Non-photosynthetic eukaryotes | 88% | 77–99% | May 2021 |
| Diatoms (mostly Mediophyceae) | 5.0% | 0.3–13.9% | December 2023 |
| Radiolarians | 2.4% | 0.2–8.1% | March 2022 |
| MOCH (marine ochrophytes) | 1.5% | 0–10.8% | January 2021 |
| Dinophyceae | 0.7% | 0–4.8% | July 2021 |
| Haptophyta | 0.6% | 0–6.9% | January 2022 |
| Ciliates | 0.6% | 0–4.4% | October 2021 |
| *% of the prokaryotes* | | | |
| Non-photosynthetic prokaryotes | 83% | 47–98.5% | December 2022 |
| Synechococcus | 15.4% | 1.1–49.9% | July 2023 |
| Cyanobium | 1.1% | 0–7.9% | November 2023 |

The other groups are below 0.4% on average, and Prochlorococcus below 0.1%.

- **Synechococcus** is lowest in December (1–4% of the prokaryotes every year) and highest in
  July (25% in 2021, 50% in 2023) and October–November (8–33%), with high values in March too
  (21–25%). Cyanobium is above 1% only from July to November.
- **Diatoms** are the main photosynthetic eukaryotes, without a regular season: above 9% of the
  eukaryotes in January 2021 and 2022, February and June 2021, October 2022, and May and December
  2023, and below 4% in every March and April.
- Other groups have single peaks: MOCH in winter (January 2021, December 2021), haptophytes in
  January 2022, dinoflagellates in July 2021 and Dictyochophyceae in May 2023 (5.1%).

<p align="center">
  <img src="report/vida_composition.png" width="80%" alt="Plankton groups of each sample at VIDA, 2021-2023">
</p>

*The groups of each sample: eukaryotes without the non-photosynthetic ones (top) and cyanobacteria
(bottom); the rest up to 100% is non-photosynthetic.*

<p align="center">
  <img src="report/vida_seasons.png" width="80%" alt="Seasonal cycle of Synechococcus, diatoms, dinoflagellates and haptophytes at VIDA">
</p>

*Seasonal cycle of Synechococcus, diatoms, dinoflagellates and haptophytes: each sample, coloured by
year, and the mean of each month.*

## 3. Validation of the chain of Tasks 1 and 2

```bash
python task3/scripts/validate_chain.py
```

It needs the outputs of Tasks 1 and 2. For each VIDA sample, the satellite pigments of Task 1
around VIDA in its month are corrected as in [Task 2](../task2/README.md) and go to the PETRIMED
metabarcoding models, whose units are those of the VIDA data (% of the eukaryotes or of the
prokaryotes), so that predictions and observations can be compared directly. The models exist for
the pico (0.2–3 µm) and nano (3–20 µm) fractions, both different from the > 0.8 µm of VIDA, so both
are compared. All 23 samples have satellite pigments in their month; with 23 samples, a correlation
is significant (p < 0.05) above 0.41.

| Group | Observed (mean) | r, pico models | r, nano models | Predicted (mean, pico / nano) |
|---|---|---|---|---|
| Non-photosynthetic eukaryotes | 88% | 0.41 | 0.33 | 54% / 64% |
| Non-photosynthetic prokaryotes | 83% | −0.11 | 0.30 | 97% / 92% |
| Synechococcus | 15% | −0.17 | 0.48 | 7% / 8% |
| Mediophyceae | 4.5% | 0.36 | 0.13 | 11% / 10% |
| MOCH | 1.5% | 0.76 | 0.56 | 0.4% / 1.4% |
| Dinophyceae | 0.7% | −0.05 | −0.23 | 5% / 18% |
| Haptophyta | 0.6% | 0.24 | −0.09 | 1.3% / 0.7% |
| Pelagophyceae | 0.3% | 0.44 | 0.48 | 1.8% / 0.4% |

The other groups with models, all at 0.6% of their domain or less, are not followed either
(|r| ≤ 0.39); green algae, absent at VIDA, cannot be compared.

- The chain does not hold at VIDA for most groups. Only MOCH (r = 0.76 and 0.56) and the minor
  Pelagophyceae (0.44 and 0.48) follow the observations with both kinds of models, MOCH mostly
  through its two winter peaks, which the models predict much smaller. Synechococcus reaches 0.48
  with the nano models but −0.17 with the pico ones. With 34 comparisons, one or two values above
  0.41 are expected by chance.
- The levels are off too: dinoflagellates are predicted 8 to 27 times too high, Synechococcus at
  about half its share, and the photosynthetic eukaryotes too high as a whole (36–46% of the
  eukaryotes, against 12%).
- Without the correction of Task 2 the results are similar or worse (MOCH 0.70 and 0.22,
  Synechococcus −0.27 and 0.46).
- No detection limit is applied, as for the plankton groups of Task 2: the VIDA shares are given to
  0.01%, and setting the observed and predicted values below 0.01% to it changes r by less than
  0.01.
- The data cannot tell whether the error comes from the pigments of Task 1 or from the models of
  Task 2, but the result agrees with the low transferability of the models between ecosystems found
  by Ramond et al. (2026), and with the proposal's choice (Risk 3) to analyse the plankton groups in
  the NW Mediterranean.

<p align="center">
  <img src="report/vida_chain.png" width="80%" alt="Observed and predicted Synechococcus, MOCH, Mediophyceae and Dinophyceae at VIDA">
</p>

*Synechococcus, MOCH, Mediophyceae and Dinophyceae at VIDA: observed, and predicted from the
corrected satellite pigments of each month by the pico and nano metabarcoding models of PETRIMED.*
