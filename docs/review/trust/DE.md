# Trust review: DE

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

<!-- trust:begin -->
## Diagnostics DE (generated)

Classifier v3, config 0237b5b5c432. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.10%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| berlin | 270 | 28970.0 | 0.00% | 48.6% | 26.1% | 0.2% | none |

### berlin: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- `cycleway:both=lanes;cycleway:both:lane=advisory;highway=secondary`: 0.07 km
- `cycleway=link;highway=service`: 0.02 km

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
