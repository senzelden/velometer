# Trust review: PL

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

## Notes

### krakow/b_share_of_ab

Kraków's B share of A+B is 0.7843 (run 237), against a limit of 0.784 (Wrocław 0.6270 x 1.25),
so it is over by 0.0003. The cause is a mapping convention, not missing tags: Kraków maps most of
its physically separated paths as `highway=path|footway` + `bicycle=designated` +
`segregated=yes` (rule `B_path_segregated`, 154.8 km per side) or unsegregated
(`B_path`, 81.1 km), and few as `highway=cycleway` (`A_cycleway`, 63.7 km). Wrocław shows the
same pattern at a lower level (B_path 136.9 km, B_path_segregated 111.4 km vs A_cycleway
146.6 km). The Polish pilot's shared-path caveat (HANDOVER §10.1) applies: the headline counts
A+B, so this changes the A/B split, not the headline. Report the split for Kraków. No rule
change proposed: these ways are shared or side-by-side foot/cycle paths, which is what tier B means.

<!-- trust:begin -->
## Diagnostics PL (generated)

Classifier v2, config 7416d3c8c103. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.1%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| wroclaw | 151 | 4015.8 | 0.0% | 8.8% | 62.7% | 0.4% | none |
| warsaw | 236 | 10895.9 | 0.0% | 23.1% | 33.4% | 0.0% | none |
| krakow | 237 | 5238.9 | 0.0% | 33.1% | 78.4% | 0.0% | b_share_of_ab |

### Pilot comparison

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| wroclaw | 151 | 4015.8 | 0.0% | 8.8% | 62.7% | 0.4% | none |

### wroclaw: top unmatched tag signatures (OSM 2026-09-30T20:22:42Z)

- none

### warsaw: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- `cycleway:right=sidepath;highway=tertiary`: 0.99 km
- `cycleway=highway;highway=secondary`: 0.12 km

### krakow: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- none

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
