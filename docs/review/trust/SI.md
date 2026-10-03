# Trust review: SI

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

## Notes

### ljubljana/b_share_of_ab

Ljubljana's B share of A+B is 0.813 (run 240), against a limit of 0.784. Most of its cycle
paths are mapped as `highway=path` + `bicycle=designated` + `foot=designated` + `segregated=yes`
(rule `B_path_segregated`, 170.2 km per side): a cycle path beside the footway on one surface,
separated from it by paint or kerb, as on golden way 1513714682. Unsegregated shared paths add
`B_path` (29.0 km); `A_cycleway` is 37.6 km. This is a mapping convention for side-by-side
foot/cycle paths, which tier B covers; the headline counts A+B, so only the split moves. Report
the split for Ljubljana. No rule change proposed.

Re-checked on classifier v3 (Task 14, run 289, 2026-10-03): 0.813, unchanged; v3 moves no km in Ljubljana.

<!-- trust:begin -->
## Diagnostics SI (generated)

Classifier v3, config 0237b5b5c432. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.1%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| ljubljana | 289 | 1715.0 | 0.0% | 12.0% | 81.3% | 0.1% | b_share_of_ab |

### ljubljana: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- none

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
