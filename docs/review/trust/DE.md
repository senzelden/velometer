# Trust review: DE

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

<!-- trust:begin -->
## Diagnostics DE (generated)

Classifier v4, config 22238ca57b73. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.10%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| berlin | 713 | 28969.9 | 0.00% | 49.0% | 17.8% | 0.2% | none |

### berlin: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- `cycleway:both=lanes;cycleway:both:lane=advisory;highway=secondary`: 0.07 km
- `cycleway=link;highway=service`: 0.02 km

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
