# Trust review: NL

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

<!-- trust:begin -->
## Diagnostics NL (generated)

Classifier v4, config 22238ca57b73. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.10%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| amsterdam | 697 | 3131.2 | 0.00% | 18.7% | 24.5% | 0.1% | none |
| utrecht | 698 | 1704.3 | 0.00% | 25.3% | 12.1% | 0.5% | none |

### amsterdam: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- `cycleway=use;highway=residential`: 0.13 km
- `cycleway:left=right;highway=residential`: 0.01 km

### utrecht: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- none

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
