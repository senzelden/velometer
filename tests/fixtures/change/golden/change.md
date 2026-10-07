# berlin: mapped cycling infrastructure change

From run 11 (OSM 2024-01-01T00:00:00Z) to run 12 (OSM 2026-09-30T20:21:22Z); classifier v4, boundary sha `bbbbbbbbbbbb`.

All figures are mapped km (ADR 0006): a gain is a way newly mapped as cycling infrastructure, not a construction.
Categories: mapped gained / lost / retiered / redrawn, and geometry (the same way-side and tier, its length changed by more than 1 m; km is the signed length change). A redrawn way-side lies within 15 m of replaced way-sides of the same tier for at least 80 % of its length, and the new way-sides together cover 80 % of each one they replace; a way-side split off an existing way-side of the same tier (a new way id along a way-side that got shorter, up to 1.2 times the length it lost) counts as redrawn too. A redrawn row's km is the new way-side's.

## Totals (per_side mapped km, recomputed and checked against both runs)

The net change (to − from) is the change in mapped km per tier. The categories below do not sum to it: a redrawn or retiered row carries only its `to` km, and a split way's persisting piece shows its shortening as a negative geometry row, which its split-off (redrawn) pieces offset.

| tier | from | to | net change (to − from) |
|---|---:|---:|---:|
| A | 1.215 | 1.062 | -0.153 |
| B | 0.000 | 0.204 | +0.204 |
| C | 0.000 | 0.000 | +0.000 |
| D | 0.000 | 0.000 | +0.000 |
| E | 0.000 | 0.000 | +0.000 |
| **A–E** | 1.215 | 1.265 | +0.050 |

## Mapped km per category

| | gained | lost | retiered | redrawn | geometry |
|---|---:|---:|---:|---:|---:|
| Ostend | 0.051 | 0.051 | 0.051 | 0.051 | 0.000 |
| Westend | 0.102 | 0.107 | 0.097 | 0.092 | 0.000 |
| Outside the 2 Bezirke (LAU edge) | 0.051 | 0.046 | 0.056 | 0.258 | 0.050 |
| **berlin** | 0.204 | 0.204 | 0.204 | 0.400 | 0.050 |

## gained: 1 way-side (top 20 by mapped km)

| way (from) | way (to) | side | tier | mapped km |
|---|---|---|---|---:|
| – | [9000000003](https://www.openstreetmap.org/way/9000000003) | self | – → A | 0.204 |

## lost: 1 way-side (top 20 by mapped km)

| way (from) | way (to) | side | tier | mapped km |
|---|---|---|---|---:|
| [9000000002](https://www.openstreetmap.org/way/9000000002) | – | self | A → – | 0.204 |

## retiered: 1 way-side (top 20 by mapped km)

| way (from) | way (to) | side | tier | mapped km | tags changed |
|---|---|---|---|---:|---|
| [9000000004](https://www.openstreetmap.org/way/9000000004) | [9000000004](https://www.openstreetmap.org/way/9000000004) | self | A → B | 0.204 | `foot`: – → yes |

## redrawn: 2 way-sides (top 20 by mapped km)

| way (from) | way (to) | side | tier | mapped km |
|---|---|---|---|---:|
| [9000000005](https://www.openstreetmap.org/way/9000000005) | [9000000006](https://www.openstreetmap.org/way/9000000006) | self | A | 0.204 |
| [9000000005](https://www.openstreetmap.org/way/9000000005) | [9000000007](https://www.openstreetmap.org/way/9000000007) | self | A | 0.197 |

## geometry: 1 way-side (top 20 by mapped km)

| way (from) | way (to) | side | tier | mapped km |
|---|---|---|---|---:|
| [9000000008](https://www.openstreetmap.org/way/9000000008) | [9000000008](https://www.openstreetmap.org/way/9000000008) | self | A | 0.050 |

_Map data © OpenStreetMap contributors, ODbL 1.0_
