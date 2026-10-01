# 0003 — Headline metric: tier A+B km per 100 km of main roads (excl. motorways)

- Status: accepted
- Date: 2026-10-01

## Context

Protection matters most where traffic is fast and heavy. That is ECF's Sustainable Safety argument, and Buczyński & Chavez-Pacheco's needs model is built on it. Other denominators distort the picture:

- **Clean Cities' total-network denominator** penalises cities with many calm residential streets.
- **Per-area denominators** are dominated by forest and water in Berlin, Oslo and Helsinki.

## Decision

- **Headline:** tier A+B `per_side` km per 100 km of **main roads excluding motorways**.
- **Secondary:** absolute km, and km per 100k residents.
- **Also computed but not headlined:** per-area ratios and total-road-network ratios.

### Road classes (`RoadLength.class`)
| Class | Highways | Dual carriageways |
|---|---|---|
| `main_excl_motorway` | trunk, primary, secondary, tertiary, and their `_link` | deduped |
| `main_incl_motorway` | the above plus motorway and motorway_link | deduped |
| `main_incl_motorway_raw` | same as `main_incl_motorway` | **not** deduped (QECIO-faithful) |
| `all_public` | main incl. motorway, plus unclassified, residential, living_street, pedestrian | deduped |

All classes leave out `access=private`, `access=no` (unless `bicycle=yes|designated|permissive`, mirroring the classifier's exclusion; Ruling R22) and `area=yes`, each tested on any `;`-separated part. `service` is excluded from `all_public` because driveways and parking aisles would swamp it. The lists live in YAML.

**Motorways** are excluded from the headline because cyclists can't use them. Including them penalises cities with urban motorways. The variants that include them are still computed, and the `ecf_qecio` preset uses them.

### Dual carriageways
Our research found that QECIO v2.10 uses `dual_carriageway=yes` only for its contraflow indicator. Its main-road denominator sums every way, so divided roads count twice. We count a divided road once, by giving each carriageway half its length when either:

1. it is tagged `dual_carriageway=yes`, or
2. it pairs geometrically: a `oneway=yes` main-road way with the same `name` or `ref` as another oneway main-road way, opposite bearing, ≤ 50 m apart and ≥ 70 % overlap.

Detected pairs are logged as diagnostics for review. The `ecf_qecio` preset uses `main_incl_motorway_raw` so that it reproduces QECIO.

### Presets
- `ours_headline`: A+B (per_side) / `main_excl_motorway`
- `ecf_qecio`: A+B+C+D (qecio_weighted) / `main_incl_motorway_raw`
- `clean_cities_2025`: A+B (per_side) / `all_public`. This reproduces Clean Cities' *OSM fallback method*, not their published numbers, which were mostly city-submitted.
