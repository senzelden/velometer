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
`overlay_v2` and a design decision for the controller.

## Sanity map

[Vorrangnetz and Ergänzungsnetz, matched vs unmatched, run 743 (2026-01-01)](../../data/maps/berlin_overlay_v1_2026-01-01.png)
(`data/` is git-ignored; rendered by an uncommitted review script reusing `plans.overlay._kept_pieces`). A network stretch is drawn as
matched when a kept A/B way-side piece lies within 12 m of it: Vorrangnetz 225 of 873 km,
Ergänzungsnetz 332 of 1,507 km. Matches follow the main radial and ring roads and look linear,
not scattered; long unmatched stretches are mainly streets whose cycle tracks are mapped as
separate ways beyond the buffer, and network edges with no A/B infrastructure in OSM.

Network data: Senatsverwaltung Berlin, Radverkehrsnetz (dl-de-zero-2.0). Way-sides:
© OpenStreetMap contributors, ODbL 1.0.
