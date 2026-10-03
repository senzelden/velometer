# Trust review: ES

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

<!-- trust:begin -->
## Diagnostics ES (generated)

Classifier v2, config 7416d3c8c103. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.1%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| madrid | 219 | 7756.6 | 0.0% | 16.2% | 10.9% | 0.1% | none |
| barcelona | 220 | 3687.2 | 0.0% | 25.0% | 4.6% | 2.3% | none |

### madrid: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- none

### barcelona: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- `bicycle=yes;cycleway=pictogram;highway=living_street`: 0.07 km

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
