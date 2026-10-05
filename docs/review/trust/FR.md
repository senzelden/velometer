# Trust review: FR

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

<!-- trust:begin -->
## Diagnostics FR (generated)

Classifier v4, config 22238ca57b73. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.10%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| paris | 693 | 6982.3 | 0.00% | 41.3% | 6.8% | 0.0% | none |
| lyon | 1119 | 2321.2 | 0.01% | 33.0% | 17.6% | 0.1% | none |
| strasbourg | 1120 | 1203.6 | 0.00% | 30.3% | 28.7% | 0.1% | none |
| bordeaux | 1121 | 889.6 | 0.04% | 37.4% | 25.5% | 1.0% | none |

### Pilot comparison

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| paris | 693 | 6982.3 | 0.00% | 41.3% | 6.8% | 0.0% | none |

### paris: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- `bicycle=yes;cycleway:left=piste_double_sens_cyclable;cycleway:right=no;highway=residential;oneway:bicycle=no`: 0.16 km
- `cycleway:left=opposite:lane;highway=residential`: 0.07 km
- `cycleway:left=no;cycleway:right=ane;cycleway:right:lane=pictogram;highway=primary`: 0.02 km

### lyon: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- `cycleway:left=share_emergencyway;highway=residential;oneway:bicycle=no`: 0.15 km
- `cycleway:right=share_taxiway;highway=residential;oneway:bicycle=no`: 0.09 km
- `cycleway=link;highway=service`: 0.02 km
- `cycleway:both=link;highway=residential;oneway:bicycle=no`: 0.02 km
- `cycleway:left=opposite:lane;highway=residential;oneway:bicycle=no`: 0.01 km

### strasbourg: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- none

### bordeaux: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- `cycleway=left;cycleway:left:oneway=-1;highway=residential;oneway:bicycle=no`: 0.33 km

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
