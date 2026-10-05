# Trust review: NO

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

## Notes

### oslo/b_share_of_ab

Oslo's B share of A+B is 0.821 (run 241; 0.822 in run 222 on the OSM relation), against a limit
of 0.784. The cause is the Norwegian standard facility, not tagging: the gang- og sykkelvei
(combined foot and cycle path, segregated=no) is mapped as `highway=cycleway` + `foot=designated`
(rule `B_cycleway_foot`, 263.3 km per side; v3 rule names and km in this paragraph, superseded by
v4, see ADR 0002 M6 amendment), and sidewalks with `bicycle=designated` add `B_path`
(20.0 km). Separate cycle-only paths (`A_cycleway` 53.7 km, `A_track_side` 8.2 km) are rare. The
golden sample confirms the tagging (ways 119146754, 136540510). The headline counts A+B, so this
is the A/B split, not the headline; report the split for Oslo (HANDOVER §10.1). No rule change
proposed.

Re-checked on classifier v3 (Task 14, run 280, 2026-10-03): 0.821, unchanged. v3 adds 0.44 km of
D advisory in Oslo (`cycleway:right=advisory`, rule `D_advisory`), outside A+B.

Re-checked on classifier v4 (run 1117, 2026-10-03): 0.825, still over the limit. The gang- og
sykkelvei (`highway=cycleway` + `foot=designated`) and the sidewalks with `bicycle=designated` are
now both `B_shared`, and separate cycle-only paths `A_cycle_only`. v4 moves little in Oslo: A
61.9 → 59.8 km and B 284.1 → 281.6 km per side against v3 on the same extract; the 4.7 km fall of
A+B is the MTB exclusion (`X_mtb_trail`; docs/review/trust/v4-impact.md). The note's conclusion
stands.

### oslo/boundary_diff_pct

The GISCO LAU polygon is 454.98 km², the OSM relation 2775550 480.48 km² (EPSG 25832, measured
2026-10-03): a difference of 5.31 %, against a limit of 5 %. The relation adds 28.02 km² and lacks
2.52 km². Of the added area, one part of 26.43 km² is Oslofjord water with its islets; the other 76
parts are under 0.15 km² each (coastline generalisation). The difference is water, so the admin
boundary stays GISCO LAU, the ADR 0004 default (user decision 2026-10-03; Oslo used the relation
from Task 13 until Task 13c). Effect, measured on the relation snapshot with v2: tiers A–E fall
from 509.3 to 505.8 km (−3.5 km, −0.7 %), cycling km from 4945.8 (run 222) to 4911.6 (run 241);
the lost km lie in the added area: fjord islands and shoreline outside the generalised
LAU polygon.

Re-checked on classifier v3 (Task 14, run 280, 2026-10-03): 5.31 %, unchanged (same boundary).

<!-- trust:begin -->
## Diagnostics NO (generated)

Classifier v4, config 22238ca57b73. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.10%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| oslo | 1117 | 4914.4 | 0.00% | 27.2% | 82.5% | 5.3% | b_share_of_ab, boundary_diff_pct |

### oslo: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- none

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
