# Trust review: FI

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

## Notes

### helsinki/boundary_diff_pct

The GISCO LAU polygon is 221.69 km², the OSM relation 34914 717.28 km² (EPSG 25835, measured
2026-10-03): a difference of 69.09 %, against a limit of 5 %. The relation adds 496.68 km² and
lacks 1.09 km². Of the added area, one part of 495.9 km² is the sea area of the municipality with
its islands; the other 63 parts are under 0.15 km² each (coastline generalisation). The LAU is the
land area, so the difference is water, and the admin boundary stays GISCO LAU, the ADR 0004
default (user decision 2026-10-03; Helsinki used the relation from Task 13 until Task 13c).
Effect, measured on the relation snapshot with v2: tiers A–E fall from 1343.0 to 1319.9 km
(−23.1 km, −1.7 %), cycling km from 5404.6 (run 232) to 5224.8 (run 242); the lost km lie in
the added area: islands and shoreline that the generalised (1:1M) LAU polygon leaves out.

Re-checked on classifier v3 (Task 14, run 281, 2026-10-03): 69.09 %, unchanged (same boundary).

<!-- trust:begin -->
## Diagnostics FI (generated)

Classifier v4, config 22238ca57b73. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.10%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| helsinki | 703 | 5226.6 | 0.00% | 36.8% | 73.7% | 69.1% | boundary_diff_pct |

### helsinki: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- none

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
