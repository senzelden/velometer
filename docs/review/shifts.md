# Unflagged shifts (M7)

Shifts in the v4 run set that no flag rule fires on, investigated for the narratives. Km are
mapped km per side (ADR 0006). Not read by `timeseries --check`.

Causes: tag drift (retagging that moves km between tiers or out of them), mapping activity (new,
redrawn or newly tagged ways), denominator (the main-road km changed, not the cycling km). Runs
are the v4 report set (classifier v4, current config); each shift was rebuilt way by way from the
runs' cached snapshots and reproduces the stored tier and road km. "Same id" compares a way with
itself across the two snapshots; "new" and "deleted" are way ids present on one side only. The
current extracts carry no changeset or mapper metadata, so edits after the last 1 January
snapshot cannot be attributed.

### bratislava/lau/2020

Cause: **tag drift** (clean-up retagging, one mapper dominant). A+B fell 132.2 -> 112.9 km
(−19.3; A 63.0 -> 49.8, B 69.3 -> 63.1) between the 2019 and 2020 snapshots (runs 916, 917).
Ways that kept their id but lost their tier account for −17.0 km net (80 ways), deleted ways for
−5.1 km, shortened ways for −3.7 km, and new ways add +6.5 km. The largest single item is way
5027830, a 7.3 km asphalt embankment path: on 7 December 2019 it went from `highway=cycleway` to
`highway=footway` + `man_made=dyke` + `motor_vehicle=private`, with no `bicycle` tag, which no
rule tiers. It gained `bicycle=yes` in August 2023 and was back to `highway=cycleway` +
`bicycle=designated` in September 2024 (by then split, 3.67 km under this id), within the A step
63.4 -> 78.6 km of bratislava 2025. Further retags: 4 ways `highway=cycleway` -> `path` without a
bicycle tag (2.57 km, e.g. way 374860730), 17 ways that lost `bicycle=designated` +
`foot=designated` (4.01 km, e.g. way 140391539) and 14 short ways `cycleway` -> `footway`
(0.58 km). The deleted way 445623343 (4.71 km, `highway=cycleway`, `surface=ground`) carried a
`FIXME` doubting that it existed as a path at all. The 63 ways retagged out of A/B (−19.5 km
gross) were last edited in 27 changesets by 9 mappers across 2019; one mapper accounts for 0.73
of their km, including the dyke way.

### stockholm/lau/2018-current

Cause: **tag drift** (gradual, community-wide `segregated` and `foot` tagging), alongside new
ways. From 1 January 2018 to 3 October 2026 (runs 816, 1116) A rose 315.0 -> 414.7 km and B fell
629.1 -> 576.6 (A+B 944.1 -> 991.3). By rule, `A_segregated` rose 18.0 -> 194.6 km while
`A_cycle_only` fell 255.6 -> 195.5 and `B_shared` 629.1 -> 576.3. Same-id flows over the period:
100.9 km of `B_shared` became `A_segregated` (491 ways that gained `segregated=yes`, often with
`cycleway:surface` / `footway:surface`, e.g. way 24404271, way 170157519) and 17.7 km moved
`A_cycle_only` -> `A_segregated`. The other way, 62.8 km of `A_cycle_only` became `B_shared`
(457 ways that gained `foot=yes` or `bicycle` + `foot=designated`, e.g. way 120088083). B also
lost 50.2 km to no tier (298 ways, mostly `highway=cycleway` -> `footway`, e.g. way 50127745) and
45.6 km of deleted ways, and gained 77.8 km of new ways. New ways added 59.3 km to
`A_segregated`, 45.8 km to `A_cycle_only` and 7.6 km to `A_track_side`; deleted ways took 26.1 km
of `A_cycle_only`, and 28.1 km of `A_track_side` left the tiers where roads dropped
`cycleway=track` (81 ways, e.g. way 43379465 Sörgårdsvägen). The change is spread over the years:
A fell and B rose until 2020 (`A_cycle_only` 255.6 -> 207.0, B 629.1 -> 656.5), then the two
largest steps were 2020 -> 2021 (A +45.7, B −39.2; 29.8 km `B_shared` -> `A_segregated` in 190
ways, 86 changesets, 19 mappers, top-mapper share 0.31 by ways, mostly September to December
2020) and 2022 -> 2023 (B −30.7; 23.6 km of B left the tiers in 143 ways, 16.7 km of it
`highway=cycleway` -> `footway`, in 58 changesets by 25 mappers; 15.9 km `B_shared` ->
`A_segregated` in 109 ways, 71 changesets, 38 mappers). No single sweep.

### budapest/lau/2024

Cause: **mapping activity** (painted lanes tagged on existing roads). D rose 118.1 -> 152.7 km
(+34.6) between the 2023 and 2024 snapshots (runs 893, 894) while A+B moved normally (212.6 ->
215.4). Same-id ways add +29.6 km net (286 ways). By rule, 26.7 km went from no tier to `D_lane`
(204 ways gaining `cycleway=lane`, `cycleway:right=lane` or `cycleway:both=lane`, e.g. way
127060029 Hunyadi utca, way 47679839 Harmat utca), 2.4 km to `D_lane_advisory` (2 ways with
`cycleway:lane=advisory`, e.g. way 152908559 Kossuth Lajos utca), and 4.2 km from `E_bus` to
`D_lane` (56 ways, `cycleway:share_busway` -> `lane`, e.g. way 262231251). New ways add 9.4 km of
`D_lane` (122 ways, e.g. way 1133257418); deleted ways take 1.5 km, shortened ways 4.2 km. Of the
40.7 km gained (399 ways), 32.9 km were last edited in September to December 2023 (12.5 km in
December), in 124 changesets by 28 mappers (top mapper 0.35 of the km, top changeset 7%).
Whether these are new markings or existing ones mapped late cannot be told from the data.

### ljubljana/lau/current

Cause: **mapping activity** (side paths drawn as separate ways). A+B rose 228.1 -> 245.0 km
(+16.9; A 193.7 -> 208.7, B 34.3 -> 36.3) between 1 January and 3 October 2026 (runs 914, 1126).
New ways add 21.2 km (227 ways); deleted ways take 2.2 km, shortened ways 1.5 km, retags 0.6 km.
18.2 km of the new km are `A_segregated` (`highway=path` + `bicycle=designated` +
`foot=designated` + `segregated=yes`, partly `path=sidewalk`), and 13.5 km of the new ways were
last edited in May 2026. By street name: Črna vas 7.4 km (e.g. way 1513714682, 2.8 km; way
1513714685, 2.6 km), Ižanska cesta 4.0 km, Litijska cesta 1.2 km. Along Črna vas the 3.7 km
tertiary road went from `bicycle=designated` to `bicycle=use_sidepath`, so the paths add km.
Along Ižanska cesta the road went from `cycleway=track` to `cycleway=separate` (and `tertiary` ->
`secondary`), so 4.0 km of `A_track_side` became excluded (11 ways, e.g. way 13027280) and the new
path ways there roughly replace road-side km. The edits cannot be attributed (current extract,
no metadata), and whether the Črna vas paths are new on the ground is not determinable from the
data.

### amsterdam/lau/2025

Cause: **tag drift** (one mapper's `segregated=yes` sweep). Between the 2024 and 2025 snapshots
(runs 786, 787) A fell 704.3 -> 660.3 km and B rose 160.2 -> 207.0 while A+B stayed flat (864.5
-> 867.4). 44.5 km of `A_segregated` became `B_shared` (490 ways). These are `highway=cycleway`
ways with `foot=yes` and `sidewalk=right` or `left` (a cycle path with its footway on the same
way) that lost `segregated=yes` and otherwise kept their tags, so v4 reads them as shared with
pedestrians: e.g. way 533017636 and way 267973415 (Bert Haanstrakade), way 256591399 (Ma
Braunpad). In all, 561 ways (54.4 km) lost `segregated=yes`; where `foot` tags went too they
stayed in A (9.5 km `A_segregated` -> `A_cycle_only`, e.g. way 122239973 Haarlemmerweg). 529 of
the 561 were last edited in September 2024, in 197 changesets by 19 mappers, and one mapper
accounts for 0.87 of their km. Elsewhere 100 ways (11.5 km) gained `segregated=yes`. The rest is
redrawing: new cycleways add 12.9 km of `A_cycle_only`, deleted ones take 11.1 km.

### copenhagen/lau/2025

Cause: **tag drift** (designation dropped and restored). B went 88.8 -> 74.0 -> 86.5 km on the
2024, 2025 and 2026 snapshots (runs 768, 769, 770) while A rose steadily (480.2 -> 482.2 ->
485.5). During 2024, 20.4 km of `B_shared` left the tiers (89 ways), mostly gravel `highway=path`
ways that lost `bicycle=designated` + `foot=designated` (42 ways, 10.5 km, e.g. way 27220164, way
25172042, way 88324561). The 89 ways were last edited in 30 changesets by 8 mappers (top mapper
0.69 of the km), 13.6 km of it in November and December 2024 and 6.1 km in August. During 2025, 59
ways (13.6 km) were retagged `highway=cycleway` + `bicycle=designated` + `foot=designated` +
`segregated=no`, which puts them back in `B_shared`. 55 of the 89 (14.4 km) are in B again on
1 January 2026, 8.7 km of that from January 2025 edits, in 10 changesets by 6 mappers, with a
different top mapper than in 2024.

### warsaw/lau/2025

Cause: **denominator** (expressways retagged as motorways). The main-road km
(`main_excl_motorway`) fell 1,039.4 -> 945.6 (−93.8) between the 2024 and 2025 snapshots (runs
876, 877), while `main_incl_motorway` barely moved (1,039.4 -> 1,045.5); the 2024 snapshot has no
motorway-class way in the city. 778 ways that were main roads in 2024 (98.9 km after
dual-carriageway halving) carry `highway=motorway` or `motorway_link` in 2025: mostly `trunk` ->
`motorway` (343 ways, 50.0 km; refs S2, S8, S7;S8, S79, e.g. way 496667835 on S2 Południowa
Obwodnica Warszawy) and `trunk_link` -> `motorway_link` (339 ways, 42.1 km), plus 35
`primary_link` ways (4.1 km). 704 of the 778 were last edited in November 2024, in 11 changesets
by 6 mappers; the largest changeset holds 406 of them. Other class changes (e.g. 69 ways
`residential` -> `tertiary`, +6.5 km), new ways (+25.5 km), deleted ways (−10.0 km) and length
changes (−14.6 km) offset a little. A+B rose normally (705.4 -> 735.3, +4.2%), but the headline
went 67.9 -> 77.8%; on the 2024 main-road km it would be 70.7%.

### helsinki/lau/2025

Cause: **denominator** (street reclassification). The main-road km (`main_excl_motorway`) rose
467.4 -> 484.1 (+16.8) between the 2024 and 2025 snapshots (runs 840, 841) while A+B stayed flat
(1,282.3 -> 1,281.7), so the headline fell 274.4 -> 264.7%; on the 2024 main-road km it would be
274.2%. Class changes add +17.4 km net: 248 ways `residential` -> `tertiary` (+16.6 km, spread
over many streets, the largest Lehtisaarentie 1.0 km and Sienitie 1.0 km, e.g. way 329182565)
and 77 ways `unclassified` -> `tertiary` (+3.6 km, e.g. way 652865992), against 87 ways
`tertiary` -> `residential` (−3.5 km, Hämeentie the largest at 1.1 km, e.g. way 116644651). The
248 upgrades were last edited in 42 changesets by 14 mappers (top-mapper share 0.79 by ways), 118
of them in June 2024 and 96 in September. New ways (+5.7 km), deleted ways (−2.6 km) and length
changes (−3.6 km) make up the rest.
