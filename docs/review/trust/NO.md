# Trust review: NO

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

## Notes

### oslo/b_share_of_ab

Oslo's B share of A+B is 0.822 (run 222), against a limit of 0.784. The cause is the Norwegian
standard facility, not tagging: the gang- og sykkelvei (combined foot and cycle path, segregated=no)
is mapped as `highway=cycleway` + `foot=designated` (rule `B_cycleway_foot`, 265.6 km per side),
and sidewalks with `bicycle=designated` add `B_path` (20.0 km). Separate cycle-only paths
(`A_cycleway` 53.9 km, `A_track_side` 8.2 km) are rare. The golden sample confirms the tagging
(ways 119146754, 136540510). The headline counts A+B, so this is the A/B split, not the headline;
report the split for Oslo (HANDOVER §10.1). No rule change proposed.

<!-- trust:begin -->
## Diagnostics NO (generated)

Classifier v2, config 7416d3c8c103. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.1%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| oslo | 222 | 4945.8 | 0.0% | 9.4% | 82.2% | 0.0% | b_share_of_ab |

### oslo: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- `bicycle:lanes:backward=yes;bicycle:lanes:forward=yes|designated;cycleway:lanes:forward=no|lane;cycleway:left=no;cycleway:right=advisory;cycleway:right:marking=dashed_line;cycleway:surface=asphalt;cycleway:surface:colour=red;highway=tertiary`: 0.44 km

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
