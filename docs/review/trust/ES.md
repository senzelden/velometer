# Trust review: ES

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

<!-- trust:begin -->
## Diagnostics ES (generated)

Classifier v4, config 22238ca57b73. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.10%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| madrid | 1114 | 7758.0 | 0.00% | 17.6% | 22.6% | 0.1% | none |
| barcelona | 1115 | 3687.2 | 0.00% | 26.2% | 5.0% | 2.3% | none |

### madrid: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- none

### barcelona: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- `bicycle=yes;cycleway=pictogram;highway=living_street`: 0.07 km

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
