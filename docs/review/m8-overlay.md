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
