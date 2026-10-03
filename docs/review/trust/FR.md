# Trust review: FR

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

<!-- trust:begin -->
## Diagnostics FR (generated)

Classifier v2, config 7416d3c8c103. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.1%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| paris | 148 | 6981.3 | 0.0% | 41.3% | 6.0% | 0.0% | none |
| lyon | 233 | 2320.3 | 0.0% | 32.9% | 15.2% | 0.1% | none |
| strasbourg | 234 | 1197.7 | 0.0% | 29.9% | 29.3% | 0.1% | none |
| bordeaux | 235 | 890.5 | 0.0% | 37.5% | 18.0% | 1.0% | none |

### Pilot comparison

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| paris | 148 | 6981.3 | 0.0% | 41.3% | 6.0% | 0.0% | none |

### paris: top unmatched tag signatures (OSM 2026-09-30T20:22:42Z)

- `bicycle=yes;cycleway:left=piste_double_sens_cyclable;cycleway:right=no;highway=residential;oneway:bicycle=no`: 0.16 km
- `cycleway:left=opposite:lane;highway=residential`: 0.07 km
- `cycleway:left=no;cycleway:right=ane;cycleway:right:lane=pictogram;highway=primary`: 0.02 km

### lyon: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- `cycleway:left=share_emergencyway;highway=residential;oneway:bicycle=no`: 0.15 km
- `cycleway:right=share_taxiway;highway=residential;oneway:bicycle=no`: 0.09 km
- `cycleway=link;highway=service`: 0.02 km
- `cycleway:both=link;highway=residential;oneway:bicycle=no`: 0.02 km
- `cycleway:left=opposite:lane;highway=residential;oneway:bicycle=no`: 0.01 km

### strasbourg: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- none

### bordeaux: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- `cycleway=left;cycleway:left:oneway=-1;highway=residential;oneway:bicycle=no`: 0.33 km

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
