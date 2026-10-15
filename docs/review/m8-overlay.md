# M8 overlay log: Berlin plan network vs mapped A/B way-sides

Run 2026-10-07, overlay `overlay_v1` (`config/plans/overlay_v1.yaml`: buffer 12 m, max angle 30°,
min part 20 m), report classifier v4, Berlin LAU boundary. All figures are mapped km (ADR 0006),
per_side, in EPSG:25833. They are not km completed to the Mobilitätsgesetz standard.

## Fetch

`uv run velometer plans fetch berlin` (1.4 s wall), retrieved 2026-10-07T10:40:42Z, licence
dl-de-zero-2.0, WFS 2.0.0 GetFeature, GeoJSON in EPSG:25833 as served:

| layer | URL | features |
|---|---|---:|
| radverkehrsnetz:radverkehrsnetz | https://gdi.berlin.de/services/wfs/radverkehrsnetz | 14,882 |
| radverkehrsmassnahmen:radverkehrsmassnahmen | https://gdi.berlin.de/services/wfs/radverkehrsmassnahmen | 332 |

All 14,882 `gisid` values are distinct (paging returned no repeated page). Network length by
`ist_radvorrangnetz`: Radvorrangnetz 5,333 lines, **873.1 km**; Ergänzungsnetz 9,549 lines,
**1,507.8 km** (feasibility log: about 873 / 1,508; official 871 / 1,505).

## Overlay

`uv run velometer plans overlay berlin`: 166 s wall (2:47 incl. start-up), peak RSS 2.3 GB.
Every run's recomputed A–E totals agreed with its stored totals (0.01 km); 40 rows written to
`plan_overlay` (10 runs x 2 classes x tiers A, B).

| run | OSM snapshot | Vorrangnetz A | B | **A+B** | Ergänzungsnetz A | B | **A+B** |
|---:|---|---:|---:|---:|---:|---:|---:|
| 735 | 2018-01-01 | 428.7 | 44.5 | **473.2** | 557.1 | 57.1 | **614.2** |
| 736 | 2019-01-01 | 425.1 | 35.7 | **460.8** | 556.2 | 53.8 | **610.0** |
| 737 | 2020-01-01 | 424.0 | 33.8 | **457.8** | 564.6 | 55.7 | **620.3** |
| 738 | 2021-01-01 | 390.3 | 47.4 | **437.7** | 543.6 | 70.9 | **614.5** |
| 739 | 2022-01-01 | 323.4 | 39.5 | **362.9** | 473.4 | 71.4 | **544.8** |
| 740 | 2023-01-01 | 307.0 | 51.2 | **358.2** | 459.6 | 77.5 | **537.1** |
| 741 | 2024-01-01 | 285.9 | 43.8 | **329.7** | 433.0 | 69.2 | **502.2** |
| 742 | 2025-01-01 | 278.5 | 41.9 | **320.4** | 424.9 | 64.4 | **489.3** |
| 743 | 2026-01-01 | 250.3 | 52.8 | **303.1** | 397.4 | 71.4 | **468.8** |
| 713 | 2026-10-03 (current) | 259.2 | 56.2 | **315.4** | 394.6 | 75.0 | **469.6** |

Change since 2022-01-01 to the current run: Vorrangnetz A+B −47.5 km, Ergänzungsnetz A+B
−75.2 km.

## Concern: the series falls, and the fall is a mapping-practice effect

On-network A+B falls every year from 2020, while Berlin's stored A+B totals stay about level
(per_side A+B: 2018 1,639.8 km, 2022 1,494.3 km, 2026-01-01 1,532.0 km). The on-network share
of A+B falls from 29 % (Vorrangnetz, 2018) to 20 % (2026).

Diagnosis (runs 735 and 743, review script, not stored): in 2018 Berlin's A+B km are mostly
road-side tags on the road centreline (1,287 km road sides, 353 km separate ways); by 2026 they
are mostly separately mapped ways (446 km road sides, 1,086 km separate ways). The network
geometry is the Detailnetz centreline, and separate ways on wide Berlin streets often lie more
than 12 m from it:

| Vorrangnetz on-network km (road sides / separate ways) | buffer 12 m | 20 m | 30 m |
|---|---:|---:|---:|
| 2018-01-01 | 413 / 60 | 436 / 74 | 444 / 79 |
| 2026-01-01 | 115 / 188 | 117 / 317 | 119 / 339 |

A wider buffer recovers part of it (2026 Vorrangnetz A+B at 20 m: 434 km against 510 km in
2018), but the series still falls, as the stored A totals themselves fell 2020–2022
(1,368.8 → 1,223.0 km). So with `overlay_v1` the "mapped on the network" series mostly tracks
the redrawing of road-side tags as separate ways, not change on the street. No parameter was
tuned: a different buffer (or matching separate ways to the centreline by offset) would be
`overlay_v2` and a design decision for the controller. Controller ruling: add `overlay_v2`, keep
v1 (next section).

## overlay_v2: a wider buffer for separately mapped ways

`config/plans/overlay_v2.yaml`: way-sides from tags on a road centreline (left/right road sides;
cycle streets, which are tier E anyway) keep `buffer_m` 12; separately mapped ways (side `self`
of a highway outside the carriageway classes: cycleway, footway, path, …) get
`buffer_separate_m` 25; `max_angle_deg` 30 and `min_part_m` 20 unchanged. v1 stays in the DB
and on disk; content facts read the latest version (`overlay_v2`).

`uv run velometer plans overlay berlin --version overlay_v2`: 164 s wall, peak RSS 2.3 GB, every
run's totals agreed, 40 rows. (v1 was re-run with the split output: same values as above.)

A+B mapped km on the network, per_side, with the split (centreline / separate):

| run | snapshot | Vorrang v1 | Vorrang v2 | Ergänzung v1 | Ergänzung v2 |
|---:|---|---:|---:|---:|---:|
| 735 | 2018-01-01 | 473.2 (413.1 / 60.1) | 490.1 (413.1 / 77.0) | 614.2 (540.4 / 73.8) | 635.4 (540.4 / 95.1) |
| 736 | 2019-01-01 | 460.8 (406.5 / 54.2) | 476.0 (406.5 / 69.5) | 610.0 (539.8 / 70.2) | 630.5 (539.8 / 90.7) |
| 737 | 2020-01-01 | 457.8 (404.0 / 53.8) | 476.8 (404.0 / 72.8) | 620.3 (547.4 / 72.9) | 643.3 (547.4 / 95.9) |
| 738 | 2021-01-01 | 437.7 (349.1 / 88.5) | 489.0 (349.1 / 139.8) | 614.5 (510.8 / 103.7) | 656.9 (510.8 / 146.0) |
| 739 | 2022-01-01 | 362.9 (286.9 / 76.0) | 436.9 (286.9 / 150.0) | 544.8 (420.2 / 124.6) | 607.7 (420.2 / 187.5) |
| 740 | 2023-01-01 | 358.2 (267.0 / 91.2) | 450.4 (267.0 / 183.4) | 537.1 (397.6 / 139.4) | 611.7 (397.6 / 214.1) |
| 741 | 2024-01-01 | 329.7 (207.9 / 121.9) | 441.7 (207.9 / 233.9) | 502.2 (311.7 / 190.5) | 595.5 (311.7 / 283.7) |
| 742 | 2025-01-01 | 320.4 (169.3 / 151.0) | 452.4 (169.3 / 283.1) | 489.3 (276.7 / 212.6) | 590.4 (276.7 / 313.8) |
| 743 | 2026-01-01 | 303.1 (115.5 / 187.6) | 450.3 (115.5 / 334.9) | 468.8 (205.7 / 263.1) | 604.3 (205.7 / 398.6) |
| 713 | 2026-10-03 | 315.4 (112.4 / 202.9) | 465.2 (112.4 / 352.8) | 469.6 (203.1 / 266.6) | 605.7 (203.1 / 402.6) |

Change of A+B on the network:

| | Vorrang v1 | Vorrang v2 | Ergänzung v1 | Ergänzung v2 |
|---|---:|---:|---:|---:|
| 2022-01-01 → current (2026-10-03) | −47.5 | **+28.3** | −75.2 | **−2.0** |
| 2022-01-01 → 2026-01-01 | −59.8 | +13.4 | −76.0 | −3.4 |
| 2018-01-01 → current | −157.8 | −24.9 | −144.6 | −29.7 |

**Does v2 still fall?** Since 2022, no: Vorrangnetz rises slightly (+28.3 km) and Ergänzungsnetz
is flat (−2.0 km). Against 2018, yes, by 25–30 km, and the whole drop sits in 2021 → 2022
(Vorrang 489.0 → 436.9, Ergänzung 656.9 → 607.7). That year the stored city-wide A total also
fell by 125.4 km (per_side A: 2021 1,348.4 → 2022 1,223.0 km), and the centreline part on
the network fell by 62 (Vorrang) and 91 km (Ergänzung) while the separate part rose only 10 and
42 km. So the 2021–2022 redraw of road-side tags lost km in OSM as a whole (fewer or shorter
A-tier sides after the redraw, or redrawn ways classified below B), not only on the network; v2
cannot recover km that are no longer A/B in the snapshot. From 2022 on, the centreline part keeps
falling (286.9 → 112.4 Vorrang) and the separate part rises by more (150.0 → 352.8), so v2's
series is dominated by the hand-over between the two and its small net change should be read as
"about level", not as growth.

### False positives of the 25 m buffer

Run 743, v2-only matched side pieces (matched at 25 m but not at 12 m): 282.5 km over both
classes. For each, the nearest OSM carriageway (excluding `service`) was found, and the distance
from that road to the network line measured: 63.5 km (22 %) lie next to a carriageway more than
10 m from the network line, 17.3 km (6 %) more than 15 m, 3.8 km more than 20 m. Most of the
10–15 m band is dual carriageways and Nebenfahrbahnen of the network road itself (each
direction mapped as its own way off the Detailnetz centreline), which are true matches; the
>15 m part (about 17 km, 6 %) is the realistic false-positive ceiling: sidepaths of parallel
side streets or of crossing streets near junctions. Zoomed crops of four areas
([crops](../../data/maps/berlin_overlay_v2_crops.png)) show the v2-only pieces running along the
network roads' own sidepaths on both sides; the only visibly doubtful pieces are short stubs at
junctions (sidepaths of the crossing street within 25 m and 30° of a network edge); no
parallel side street was picked up in the crops.

## overlay_v3: `min_part_m` on touching way-sides of one tier

**Why.** The Task 5 review measured that v1/v2 apply `min_part_m` (20 m) to each way-side's own
kept parts, so a way split into OSM ways shorter than 20 m counts 0 km even when it lies wholly
on the network and its neighbours are kept. A+B sides under 20 m that would match without the
filter: Vorrangnetz 4.0 km (2018, run 735) → 24.3 km (current, run 713), Ergänzungsnetz 5.5 →
30.4 km, a drift of the same size as v2's 2022 → current change (+28.3 / −2.0). Controller
ruling: overlay_v3.

`config/plans/overlay_v3.yaml`: v2's buffers (12 m centreline tags / 25 m separate ways), angle
(30°) and `min_part_m` (20) unchanged, plus `merge_scope: tier` (v1/v2: `side`, the default, so
their rows and behaviour are unchanged). Kept parts of one tier that touch across way-sides
(within 1 mm, i.e. shared OSM nodes) form a group per network class; the group passes when one
of its parts is at least 20 m or the length of the union of its parts (its extent) is. The two
road sides of one short way share their extent, so they do not add up to a part; a kept part
still counts its own per_side km (both road sides of a passing group count). Tiers do not merge
with each other, and a chain that changes network class does not merge across the classes (each
class is a separate overlay).

`uv run velometer plans overlay berlin --version overlay_v3`: 2:42 wall (161 s in the command),
peak RSS 2.35 GB, every run's A–E totals agreed, 40 rows written. v1 and v2 rows stay in
`plan_overlay` (120 rows). `velometer plans overlay` without `--version` now runs the
highest-numbered `overlay_vN.yaml` (v3).

A+B mapped km on the network, per_side:

| run | snapshot | Vorrang v2 | Vorrang v3 (A / B) | v3 − v2 | Ergänzung v2 | Ergänzung v3 (A / B) | v3 − v2 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 735 | 2018-01-01 | 490.1 | 497.5 (446.8 / 50.7) | +7.4 | 635.4 | 645.4 (578.1 / 67.3) | +10.0 |
| 736 | 2019-01-01 | 476.0 | 483.8 (442.0 / 41.7) | +7.8 | 630.5 | 640.9 (576.0 / 64.9) | +10.4 |
| 737 | 2020-01-01 | 476.8 | 485.0 (442.9 / 42.1) | +8.2 | 643.2 | 654.0 (586.6 / 67.4) | +10.8 |
| 738 | 2021-01-01 | 489.0 | 497.7 (440.2 / 57.4) | +8.7 | 656.9 | 668.1 (582.7 / 85.4) | +11.3 |
| 739 | 2022-01-01 | 436.9 | 446.3 (399.2 / 47.0) | +9.4 | 607.7 | 619.8 (531.9 / 87.9) | +12.1 |
| 740 | 2023-01-01 | 450.4 | 463.0 (404.2 / 58.8) | +12.6 | 611.7 | 625.7 (532.1 / 93.5) | +14.0 |
| 741 | 2024-01-01 | 441.8 | 460.0 (406.9 / 53.2) | +18.3 | 595.5 | 617.2 (532.2 / 85.0) | +21.7 |
| 742 | 2025-01-01 | 452.5 | 473.0 (422.3 / 50.7) | +20.6 | 590.5 | 615.6 (536.3 / 79.3) | +25.1 |
| 743 | 2026-01-01 | 450.3 | 476.2 (413.6 / 62.6) | +25.8 | 604.3 | 636.9 (550.5 / 86.4) | +32.7 |
| 713 | 2026-10-03 | 465.3 | 492.2 (424.5 / 67.7) | +27.0 | 605.7 | 639.5 (549.5 / 90.0) | +33.7 |

(v2 values from the DB; the v2 table above rounds the same rows at most 0.1 km differently.)
Centreline / separate split of v3 (command output), Vorrangnetz: 2018 419.7 / 77.8, 2022
292.5 / 153.8, current 119.0 / 373.2; Ergänzungsnetz: 2018 549.5 / 95.9, 2022 428.4 / 191.4,
current 215.2 / 424.2.

**What v3 recovers, and does the drift disappear?** The km v3 adds over v2 grow from 7.4 (2018)
to 27.0 km (current) on the Vorrangnetz and from 10.0 to 33.7 km on the Ergänzungsnetz: v3
recovers the drift, it does not remove a growing loss by chance. It recovers more than the
review's estimate (4.0 → 24.3) because that estimate counted only whole sides under 20 m, while
v3 also recovers short kept runs at the ends of longer sides that continue on a neighbouring
way. What v3 still drops, measured against the same overlay with the `min_part_m` filter
disabled (read-only scratchpad script, runs 735 / 739 / 713, step unchanged):

| network | 2018 | 2022 | current | drift 2018 → current |
|---|---:|---:|---:|---:|
| Vorrangnetz: dropped by v2 | 8.8 | 11.4 | 29.1 | +20.3 |
| Vorrangnetz: dropped by v3 | 1.4 | 2.0 | 2.2 | +0.8 |
| Ergänzungsnetz: dropped by v2 | 12.7 | 15.4 | 38.0 | +25.3 |
| Ergänzungsnetz: dropped by v3 | 2.6 | 3.3 | 4.3 | +1.7 |

So the drift is gone: what v3 still drops (isolated pieces under 20 m that touch no other kept
part of their tier) moves by under 2 km between 2018 and now.

**Does the 2022 → current change move?** Yes, and by a lot relative to its size:

| change of A+B on the network | Vorrang v2 | Vorrang v3 | Ergänzung v2 | Ergänzung v3 |
|---|---:|---:|---:|---:|
| 2022-01-01 → current (2026-10-03) | +28.4 | **+45.9** | −2.0 | **+19.7** |
| 2022-01-01 → 2026-01-01 | +13.4 | +29.9 | −3.4 | +17.1 |
| 2018-01-01 → current | −24.8 | −5.3 | −29.7 | −5.9 |

Under v3 both classes rise since 2022 (+45.9 / +19.7 km), where v2 showed a small rise and a
flat line. Against 2018 the v3 series is about level (−5.3 / −5.9 km); the 2021 → 2022 drop
(Vorrang 497.7 → 446.3, Ergänzung 668.1 → 619.8) is still there, for the reason given under v2.
The size of the move (17.5 km on the Vorrangnetz, 21.7 km on the Ergänzungsnetz, out of a 4.75-year
change) shows how much of the headline depends on how short OSM ways are treated; v3 removes
that dependence (what it still drops is under 5 km and level), but the change remains a mix of
redrawing and new mapping, so it should still be worded as mapped km on the network, not as
progress on the street.

### Check of the v3-only pieces (Task 8 review stop)

The user's ruling ships v3 after a zoomed check of the pieces v3 keeps and v2 drops, for
crossing-street false positives. Read-only classifier `scripts/overlay_false_positives.py`
(`uv run python scripts/overlay_false_positives.py --run 743 --version overlay_v3 --base
overlay_v2`; it reuses `plans.overlay._kept_pieces` for both versions), run 743 (OSM
2026-01-01); no overlay parameter changed. v3-only pieces: **58.5 km** (Vorrangnetz 25.8,
Ergänzungsnetz 32.7). The pieces are the overlay's own: each A/B way-side clipped to the LAU
boundary and cut into equal pieces of at most `min_part_m / 2` = 10 m; lengths in EPSG:25833.
A *matching* line is a network line of the piece's class within the piece's buffer (12 m for
road-side tags, 25 m for separately mapped ways) whose direction over ±1 m around its point
nearest the piece's midpoint is within 30° of the piece (the overlay's match test). A matching
line runs *alongside* the piece when the midpoint projects onto it more than 0.5 m from either
end, or lies at most 1 m past the end it projects onto, measured along the line's outward
direction over its last 1 m; every line end counts, so a piece across a joint is alongside the
next edge. Each piece was put in the first class that applies:

1. *Past the network line's end*: no matching line runs alongside it (the midpoint lies more than
   1 m past every matching line's end), and no line of the other class runs alongside either
   (within the same buffer and 30°, projecting more than 0.5 m inside it).
2. *Class boundary*: as 1, but a line of the other class runs alongside: the piece is on the
   network, counted in the class whose line ends there.
3. *Crosses a network line, along another*: the nearest line of its class (any distance) is more
   than 30° from the piece (directions over ±5 m), while a matching line runs alongside.
4. *Beside another road*: of the OSM carriageways (the report classifier's
   `road_classes.carriageway`: motorway to living_street, road and busway, with their links,
   without `service`) within 30 m of the midpoint and within 30° of the piece, the nearest is more
   than 30° from the matched line (the nearest matching line), or its point nearest the midpoint
   lies more than 15 m from that line.
5. *Along*: the rest, including pieces beside no carriageway (for example where the network
   itself runs off-road).

| class of the v3-only piece | km | share | Vorrang | Ergänzung |
|---|---:|---:|---:|---:|
| along the network line | 40.5 | 69.3 % | 18.6 | 22.0 |
| crosses a network line, along another | 5.1 | 8.8 % | 2.4 | 2.7 |
| beside another parallel or crossing road | 1.1 | 1.9 % | 0.7 | 0.4 |
| past its class's line end, on the other class | 5.3 | 9.0 % | 2.5 | 2.8 |
| **past the network line's end** | **6.5** | **11.0 %** | 1.6 | 4.8 |

Random samples of 16 pieces per class (120 m windows, numpy `default_rng(1)`, `--detail CLASS`) confirm the first class: almost all are
sidepaths or crossings of the street that continues where the network line ends or turns at a
junction, i.e. sidepaths of crossing streets; a few are crossings inside the junction itself
([sample](../../data/maps/berlin_overlay_v3_vs_overlay_v2_detail_beyond_network_end.png)). In the "crosses a
network line, along another" class most pieces are crossings inside a junction on the route of
the crossing network street; about 3 of 16 are junction pieces whose assignment is doubtful
([sample](../../data/maps/berlin_overlay_v3_vs_overlay_v2_detail_junction_crossing.png)). In the "beside another
road" class about half the sample are the network road's own sidepaths on wide or dual
carriageways (the far carriageway lies more than 15 m from the network line), the rest sidepaths
of a parallel road or junction pieces
([sample](../../data/maps/berlin_overlay_v3_vs_overlay_v2_detail_parallel_or_crossing_street.png)).
[Crops of the six densest 800 m cells, 1.2 km windows, v3-only
pieces coloured by class](../../data/maps/berlin_overlay_v3_vs_overlay_v2_crops.png).

**False-positive share: 11.0 % (6.5 km)** counting only pieces past the network line's end; about
14 % with the doubtful parts of classes 3 and 4 added (3/16 of 5.1 km, half of 1.1 km); 21.7 %
if every piece that crosses a network line at a steep angle counts (classes 1, 3 and 4), and
30.7 % if the class-boundary pieces count too. This exceeds the ~10 % stop threshold the
controller set for this check, so the finding goes to the controller; the method is unchanged.

Over time (same script, runs 739 and 713): v3-only km grow from 21.5 (2022-01-01) to 60.7
(current, 2026-10-03); the "past the network line's end" part from 3.8 to 6.5 km (Vorrangnetz
0.96 → 1.65, Ergänzungsnetz 2.86 → 4.80), class boundaries from 3.7 to 5.5 km, pieces crossing a
network line from 2.0 to 5.3 km, and the "along" part from 11.7 to 42.4 km. So of v3's addition to
the 2022 → current change (+17.5 km Vorrangnetz, +21.7 km Ergänzungsnetz over v2), about 0.7 and
1.9 km are pieces past the network line's end, and the bulk (+14.1 and +16.5 km) are pieces
along the network line.

## overlay_v4: matches stop at a free end of a network line

**Why.** The check above found 6.5 km (11.0 %) of the v3-only pieces past the network line's end:
the overlay's distance test is "any point of the piece within the buffer", so a match runs past
the free end of a network line into the crossing or continuing street by up to buffer + step
(Task 5 review, Minor 2). User ruling: overlay_v4 = v3 plus one rule against this.

`config/plans/overlay_v4.yaml`: v3's parameters (buffers 12 / 25 m, 30°, `min_part_m` 20,
`merge_scope: tier`) plus `clip_free_ends: true` (v1-v3: false, the default, so their rows and
behaviour are unchanged; their 120 rows stay in `plan_overlay`). The rule: a piece does not match
a network line whose *free* end its midpoint lies past (nearest the line at that end, and beyond
it along the line's outward direction over its last 1 m; no tolerance). The network is split
into edges at every junction, so an end is free unless another line of the same class has an end
within 1 m of it that leaves the joint within 30° (`max_angle_deg`) of the line's own direction.
A straight or slightly bent joint (and a gap under 1 m) is therefore not a free end and keeps
every piece across it; where the network turns by more than 30° at a junction, the end is free
and the piece on the street that continues straight on stops matching. Of the network's line
ends, 2,192 of 10,666 (Vorrangnetz) and 4,462 of 19,098 (Ergänzungsnetz) are free by this rule;
by end-point contact alone only 33 and 1,106 would be, which would not have removed the
false positives. `min_part_m` is then tested on the clipped runs.

`uv run velometer plans overlay berlin --version overlay_v4`: 6:05 wall (363 s in the command,
under machine load; v3 took 2:42), peak RSS 2.35 GB, every run's A–E totals agreed, 40 rows
written (160 rows over v1–v4). The default version is now v4, and the content facts read it.

A+B mapped km on the network, per_side (DB values):

| run | snapshot | Vorrang v3 | Vorrang v4 (A / B) | v4 − v3 | Ergänzung v3 | Ergänzung v4 (A / B) | v4 − v3 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 735 | 2018-01-01 | 497.5 | 490.4 (440.6 / 49.8) | −7.1 | 645.4 | 633.4 (567.7 / 65.7) | −12.0 |
| 736 | 2019-01-01 | 483.8 | 476.7 (435.9 / 40.8) | −7.1 | 640.9 | 629.1 (565.8 / 63.3) | −11.8 |
| 737 | 2020-01-01 | 485.0 | 477.8 (436.8 / 41.0) | −7.2 | 654.0 | 642.1 (576.3 / 65.9) | −11.9 |
| 738 | 2021-01-01 | 497.7 | 489.7 (433.4 / 56.3) | −8.0 | 668.1 | 655.6 (571.9 / 83.7) | −12.5 |
| 739 | 2022-01-01 | 446.3 | 438.3 (392.2 / 46.1) | −8.0 | 619.8 | 606.4 (520.1 / 86.3) | −13.4 |
| 740 | 2023-01-01 | 463.0 | 454.3 (396.4 / 57.9) | −8.7 | 625.7 | 611.8 (520.0 / 91.8) | −13.9 |
| 741 | 2024-01-01 | 460.0 | 450.2 (397.9 / 52.3) | −9.9 | 617.2 | 601.3 (518.0 / 83.3) | −15.9 |
| 742 | 2025-01-01 | 473.0 | 462.0 (412.1 / 49.9) | −11.1 | 615.6 | 598.4 (520.7 / 77.7) | −17.2 |
| 743 | 2026-01-01 | 476.2 | 464.4 (402.8 / 61.7) | −11.7 | 636.9 | 617.7 (533.0 / 84.7) | −19.2 |
| 713 | 2026-10-03 | 492.2 | 480.4 (413.6 / 66.7) | −11.9 | 639.5 | 620.2 (531.9 / 88.3) | −19.3 |

Change of A+B on the network, from the unrounded DB values (the v3 table above computed it from
rounded endpoints, hence 45.9 / 19.7 / −5.3 / −5.9 there):

| change of A+B on the network | Vorrang v3 | Vorrang v4 | Ergänzung v3 | Ergänzung v4 |
|---|---:|---:|---:|---:|
| 2022-01-01 → current (2026-10-03) | +46.0 | **+42.1** | +19.6 | **+13.7** |
| 2022-01-01 → 2026-01-01 | +29.9 | +26.2 | +17.1 | +11.3 |
| 2018-01-01 → current | −5.2 | −10.1 | −6.0 | −13.2 |

**How much of the 6.5 km does v4 remove?** Same classifier, run 743, pieces v4 keeps and v2
drops (`--version overlay_v4 --base overlay_v2`): 46.2 km (Vorrangnetz 21.5, Ergänzungsnetz 24.6),
against v3's 58.5 km:

| class | v3-only (km) | v4-only (km) | v4 share |
|---|---:|---:|---:|
| along the network line | 40.5 | 39.9 | 86.4 % |
| crosses a network line, along another | 5.1 | 4.7 | 10.3 % |
| beside another parallel or crossing road | 1.1 | 1.0 | 2.2 % |
| past its class's line end, on the other class | 5.3 | 0.1 | 0.1 % |
| **past the network line's end** | **6.5** | **0.45** | **1.0 %** |

v4 removes 6.0 of the 6.5 km (93 %); what remains (0.45 km) lies past ends the rule does not
treat as free: joints with a continuation within 30° that the piece does not match (the
classifier counts every end, v4 only free ones). The midpoint test also lets a kept run overrun a
free end by up to half a piece (5 m), which the classifier counts as alongside. The strict false-positive share
of the version's additions over v2 falls from 11.0 % to 1.0 %; with the doubtful parts of classes
3 and 4 added at the v3 samples' fractions (3/16 and half), about 4 %
([crops](../../data/maps/berlin_overlay_v4_vs_overlay_v2_crops.png)).

**What else v4 removes, and what real km it loses.** v4 does not only act on the v3-only pieces:
the same overrun was in v1/v2's matches. All pieces v3 keeps and v4 drops (`--version overlay_v3
--base overlay_v4`), classed the same way:

| class of the v3-kept, v4-dropped piece | run 739 (2022-01-01) | run 743 (2026-01-01) | run 713 (current) |
|---|---:|---:|---:|
| past the network line's end | 10.4 | 14.8 | 14.9 |
| past its class's line end, on the other class | 8.6 | 12.8 | 13.0 |
| crosses a network line, along another | 0.9 | 1.3 | 1.3 |
| beside another parallel or crossing road | 0.1 | 0.2 | 0.2 |
| along the network line | 1.4 | 1.9 | 1.9 |
| **total** (Vorrangnetz / Ergänzungsnetz) | 21.4 (8.0 / 13.4) | 31.0 (11.7 / 19.2) | 31.2 (11.9 / 19.3) |

- Past the network line's end, 14.8 km on run 743: mostly the false positives the rule exists
  for, including those v1/v2 already had ([crops](../../data/maps/berlin_overlay_v3_vs_overlay_v4_crops.png),
  [sample](../../data/maps/berlin_overlay_v3_vs_overlay_v4_detail_beyond_network_end.png)), but
  not all: the classifier's "past the end" test uses the same geometry as v4, so a way-side that
  follows the network round a curve split into edges at a bend over 30°, or through a junction
  where the network's edges jog, is classed here too (Task 8b review: cases at EPSG:25833
  383321, 5818298 and 390604, 5810575). The classifier cannot tell those followers from
  sidepaths of the continuing street.
- Class boundaries, 12.8 km: pieces past their class's line end where a line of the other class
  continues. 12.1 km of them are kept by v4 in the other class (`--checks`), so v3 counted them
  in both classes and v4 counts them once; 0.7 km (Vorrangnetz 0.43, Ergänzungsnetz 0.26) are
  counted in neither class by v4, mostly crossings inside junctions and pieces on the street
  continuing past both lines' ends (review render), with an occasional corner piece of a
  cycleway passing from one class's line to the other's. v4 does not end double counting: on
  run 743 it still counts 3.54 km of pieces in both classes (v3: 16.97 km).
- Along the network line, 1.9 km: 1.5 km still match under v4 but their clipped run (or
  touching group) falls below `min_part_m` (20 m): short stubs that reached 20 m only with
  their overrun; 0.4 km lie 0–1 m past a free end, which the classifier's 1 m tolerance calls
  alongside and v4 (no tolerance) does not. In a sample of 16 (seed 1,
  [sample](../../data/maps/berlin_overlay_v3_vs_overlay_v4_detail_along.png)) most are short
  pieces inside or at the edge of a junction; about a quarter are the last metres of a sidepath
  along a network edge.

**Real along-the-network km lost: about 0.5 to 3 km on run 743 (v4 counts 1,082 km on the two
networks, printed by `--checks`), a range, not a bound.** Measured with `--version overlay_v3 --base
overlay_v4 --checks`: a dropped piece lies in a *hole* of a chain v4 keeps when, within 3
consecutive pieces chained end to start (one way-side part, or ways touching in input order), v4
keeps a piece both before and after it; such a piece is almost certainly on the network's route.
Holes: 0.46 km (Vorrangnetz 0.21, Ergänzungsnetz 0.25), of which 0.37 km lie past a *turn end* (a
free end with another line's end within 1 m, where the network turns by more than 30° rather than
stops) and 0.27 km are classed past the network line's end. That is the low end. The high end adds
every dropped piece the classes leave open: the along class (1.9 km) and the class-boundary pieces
counted in neither class (0.7 km), about 3.0 km together with the holes. It is not a strict upper
bound: of the 21.4 km dropped past turn ends (Vorrangnetz 10.9, Ergänzungsnetz 10.6), some
outer-corner pieces of ways following a turning network that do not sit in a hole are classed past
the end, and their share is not measured. The review's renders show the turn ends over 60° to be
mostly sidepaths of the continuing street. Getting the followers back would be a rule change (for
example a wider joint angle for joints of exactly two edges), i.e. a v5 question for the user.

**Does the 2022 → current change move?** Yes, down: Vorrangnetz +46.0 → **+42.1** km,
Ergänzungsnetz +19.6 → **+13.7** km. The pieces v4 drops grow from 21.4 km (2022) to 31.2 km
(current), and they move from road-side tags to separately mapped ways (25 m buffer) as those
take over (v3 − v4, centreline / separate: Vorrangnetz 2018 5.4 / 1.7 km, current 1.1 / 10.7 km;
Ergänzungsnetz 8.8 / 3.2 and 2.8 / 16.4 km, from the commands' split output); of the 3.9 / 5.9 km by which the change falls, past-end pieces are 1.4 /
3.1 km, class-boundary double counts 2.1 / 2.3 km, and along pieces 0.2 / 0.3 km. Against 2018 the
v4 series is lower (−10.1 / −13.2 km). Disconfirming against the expectation that v4 would trim
about 6.5 km from the latest year: it trims 11.7 / 19.2 km on run 743 and 7.1 / 12.0 km already in
2018, because v1–v3 all carried the overrun and the class-boundary double count. The rule was not
tuned (no tolerance, the existing 30° as the joint angle, the 1 m joint distance chosen before the
run; free-end counts above are with these values).

## M13: v4's real loss measured

The M8 estimate above (about 0.5 to 3 km on run 743) left out the outer-corner pieces. M13 measures
the real loss and applies the user's rule ("measure first"): v5 is needed if, on any measured run,
v4 loses more than 2.0 km of real along-network km, or more than 1 % of that run's v4 overlay km.

**Measure.** `uv run python scripts/overlay_false_positives.py --run <id> --version overlay_v3
--base overlay_v4 --real-loss` (with `--checks`; 11–31 s per run). The candidates for real loss
are the pieces v3 keeps and v4 drops that may lie along the network across a turn, in four
disjoint parts:

1. holes: pieces in a hole of a chain v4 keeps (as `--checks`, any class);
2. outside holes, the `along` class;
3. outside holes, the `class_boundary` pieces v4 keeps in neither class;
4. outside holes, the `beyond_network_end` pieces at an **outer corner** (`outer_corner`): the
   midpoint lies within the piece's buffer of a line of its class, past one of its ends and at
   most `END_TOL_M` + the buffer from it. The piece runs within 30° of the line there. At that
   end exactly one other line of the class has an end within 1 m and leaves it turning by more
   than 30°. The midpoint lies on the outer side of that turn.

Runs: the Berlin LAU runs of the current classifier (v4) with `plan_overlay` rows, queried
2026-10-15. All ten have overlay_v4 rows: 713 (current, OSM 2026-10-03) and 735–743 (1 January
2018–2026, commit ae704fa). Measured: 735 (2018), 739 (2022), 743 (2026) and 713, the current
snapshot that the M8 tables use. The v4 overlay km are the `plan_overlay` sums over both classes
and tiers. They equal the "kept by overlay_v4" line of `--checks`.

| run | v4 overlay km | 1 % | holes past a turn end | outer-corner candidates | holes elsewhere | along | class boundary, neither class | all parts, sum (Vorrangnetz / Ergänzungsnetz) | turn-recoverable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 735 (2018-01-01) | 1,123.81 | 11.24 | 0.23 | 2.05 | 0.08 | 0.97 | 0.16 | 3.49 (1.28 / 2.21) | 0.36 |
| 739 (2022-01-01) | 1,044.68 | 10.45 | 0.22 | 2.40 | 0.08 | 1.45 | 0.41 | 4.55 (1.64 / 2.92) | 0.37 |
| 743 (2026-01-01) | 1,082.08 | 10.82 | 0.37 | 3.47 | 0.09 | 1.90 | 0.63 | 6.46 (2.32 / 4.13) | 0.59 |
| 713 (current) | 1,100.51 | 11.01 | 0.37 | 3.49 | 0.09 | 1.89 | 0.66 | 6.50 (2.37 / 4.13) | 0.59 |

All values are km (mapped km, EPSG:25833), as printed by `--real-loss` (both-classes line; the
per-class sums are its per-class lines). The script prints the parts as turn-recoverable (holes
past a turn end, plus outer corners only where a visual check confirms them), outer-corner
candidates (mostly false positives) and the non-turn residual (holes elsewhere, along, class
boundary in neither class). The holes on run 743 match the M8 figure (0.46 km, 0.37 past a turn
end). The class-boundary pieces in neither class are 0.63 km outside holes (M8: 0.7 km including
holes).

**The outer-corner candidates are mostly not real loss.** Two samples of 16 outer-corner pieces on
run 743 ([seed 1](../../data/maps/berlin_overlay_v3_vs_overlay_v4_detail_outer_corner_seed1.png),
[seed 2](../../data/maps/berlin_overlay_v3_vs_overlay_v4_detail_outer_corner_seed2.png);
`--detail outer_corner --seed N`) show mostly pieces on the street that continues straight past
the network's turn. They lie on its far side, within the buffer of the turning edge's end: the
sidepaths of the continuing street that v4 exists to drop. On a visual reading, at most 2 of the
32 pieces follow the network round the corner. That is expected: a way-side that follows the turn
usually shows up as a hole, because v4 keeps it before and after the corner. A piece alone cannot
tell the follower's corner from the continuing street's far side.

**Decision.** The literal sum of the four parts crosses the 2 km threshold on every measured run
(3.49 to 6.50 km); the 1 % threshold (10.45 to 11.24 km) is crossed on none. The threshold is
meant for real turns clipped, pieces dropped while a matching network line runs along them
(spec §4.3), and the sum overstates those:

- Outer-corner candidates: the visual check of 32 sampled pieces found at most 2 following the
  network.
- Turn-recoverable km per run: the holes past a turn end, plus 2/32 of the outer-corner candidates
  as verified corners. The 2/32 rate comes from the check on run 743 and is extrapolated to the
  other runs. This gives 0.36 (735), 0.37 (739), 0.59 (743) and 0.59 (713) km.
- On run 743, the `along` pieces 0–1 m past a free end (0.4 km, M8 figure above, free ends of any
  kind) are the most a turn rule could add. Even with them, run 743 stays near 1.0 km, below 2 km.
- The rest is not a turn question. Most `along` km (1.5 km on run 743) are stubs whose clipped run
  falls below `min_part_m` (20 m) and short pieces inside junctions. The class-boundary pieces in
  neither class are crossings inside junctions and the street continuing past both classes' line
  ends. A rule that keeps pieces across turns does not recover either.

Ruling (controller, 2026-10-15): **v5 not built.** The planned rule (no clipping where the nearest
line of the class continues past the turn) would mainly restore the outer-corner candidates, i.e.
v4's intended removals. Its acceptance test counts those as real, so it would pass by
construction. overlay_v4 stays the published version. No stored value changed: `velometer.sqlite`
was only read.

## Sanity maps

[Vorrangnetz and Ergänzungsnetz, matched vs unmatched, run 743 (2026-01-01)](../../data/maps/berlin_overlay_v1_2026-01-01.png)
(`data/` is git-ignored; rendered by an uncommitted review script reusing
`plans.overlay._kept_pieces`). A network stretch is drawn as matched when a kept A/B way-side piece lies within 12 m of it: Vorrangnetz 225 of 873 km,
Ergänzungsnetz 332 of 1,507 km. Matches follow the main radial and ring roads and look linear,
not scattered; long unmatched stretches are mainly streets whose cycle tracks are mapped as
separate ways beyond the buffer, and network edges with no A/B infrastructure in OSM.

[overlay_v2, run 743 (2026-01-01)](../../data/maps/berlin_overlay_v2_2026-01-01.png):
Vorrangnetz 312 of 873 km matched, Ergänzungsnetz 418 of 1,507 km; v2-only side pieces in
orange (282 km). They follow the main radial and ring roads (wide streets with separately
mapped cycle tracks) and form continuous runs, not scattered fragments.

Network data: Senatsverwaltung Berlin, Radverkehrsnetz (dl-de-zero-2.0). Way-sides:
© OpenStreetMap contributors, ODbL 1.0.
