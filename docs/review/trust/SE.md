# Trust review: SE

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

<!-- trust:begin -->
## Diagnostics SE (generated)

Classifier v4, config 22238ca57b73. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.10%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| stockholm | 701 | 3658.1 | 0.08% | 16.5% | 58.2% | 2.1% | none |

### stockholm: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- `cycleway=path;highway=tertiary`: 2.13 km
- `cycleway:left=exclusive;cycleway:left:oneway=-1;highway=residential;oneway:bicycle=no`: 0.40 km
- `cycleway=segregated;highway=unclassified`: 0.32 km
- `bicycle:lanes=no|designated|no;cycleway=no|lane|no;highway=tertiary`: 0.03 km

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
