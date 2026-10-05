# Trust review: SI

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

## Notes

### ljubljana/b_share_of_ab

Ljubljana's B share of A+B is 0.813 (run 240), against a limit of 0.784. Most of its cycle
paths are mapped as `highway=path` + `bicycle=designated` + `foot=designated` + `segregated=yes`
(rule `B_path_segregated`, 170.2 km per side; v3 rule names and km here and below, superseded by
v4, see ADR 0002 M6 amendment): a cycle path beside the footway on one surface,
separated from it by paint or kerb, as on golden way 1513714682. Unsegregated shared paths add
`B_path` (29.0 km); `A_cycleway` is 37.6 km. This is a mapping convention for side-by-side
foot/cycle paths, which tier B covers; the headline counts A+B, so only the split moves. Report
the split for Ljubljana. No rule change proposed.

Re-checked on classifier v3 (Task 14, run 289, 2026-10-03): 0.813, unchanged; v3 moves no km in Ljubljana.

No longer fires under classifier v4 (run 1126, 2026-10-03): B is 0.148 of A+B (36.3 of 245.0 km per
side), because v4 rates segregated `highway=path` + `bicycle=designated` sidepaths `A_segregated`
(Ljubljana A +162.3 / B −165.9 km against v3 on the same extract, docs/review/trust/v4-impact.md).

<!-- trust:begin -->
## Diagnostics SI (generated)

Classifier v4, config 22238ca57b73. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.10%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| ljubljana | 1126 | 1715.0 | 0.00% | 13.6% | 14.8% | 0.1% | none |

### ljubljana: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- none

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
