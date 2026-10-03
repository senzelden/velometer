# Trust review: SK

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

<!-- trust:begin -->
## Diagnostics SK (generated)

Classifier v3, config 0237b5b5c432. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.1%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| bratislava | 290 | 3036.8 | 0.0% | 10.7% | 34.2% | 0.1% | none |

### bratislava: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- `bicycle:lanes:forward=yes|designated;cycleway:right=shared_busway;highway=tertiary`: 0.16 km
- `cycleway=asl;highway=secondary`: 0.00 km

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
