# Trust review: NO

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

## Notes

### oslo/b_share_of_ab

Oslo's B share of A+B is 0.821 (run 241; 0.822 in run 222 on the OSM relation), against a limit
of 0.784. The cause is the Norwegian standard facility, not tagging: the gang- og sykkelvei
(combined foot and cycle path, segregated=no) is mapped as `highway=cycleway` + `foot=designated`
(rule `B_cycleway_foot`, 263.3 km per side), and sidewalks with `bicycle=designated` add `B_path`
(20.0 km). Separate cycle-only paths (`A_cycleway` 53.7 km, `A_track_side` 8.2 km) are rare. The
golden sample confirms the tagging (ways 119146754, 136540510). The headline counts A+B, so this
is the A/B split, not the headline; report the split for Oslo (HANDOVER §10.1). No rule change
proposed.

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

<!-- trust:begin -->
## Diagnostics NO (generated)

Classifier v2, config 7416d3c8c103. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.1%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| oslo | 241 | 4911.6 | 0.0% | 9.3% | 82.1% | 5.3% | b_share_of_ab, boundary_diff_pct |

### oslo: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- `bicycle:lanes:backward=yes;bicycle:lanes:forward=yes|designated;cycleway:lanes:forward=no|lane;cycleway:left=no;cycleway:right=advisory;cycleway:right:marking=dashed_line;cycleway:surface=asphalt;cycleway:surface:colour=red;highway=tertiary`: 0.44 km

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
