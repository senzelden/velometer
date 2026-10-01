# 0002 — Tiered classifier derived from ECF QECIO tag logic

- Status: accepted
- Date: 2026-10-01

## Context

"Protected" means different things in different sources:

- **ECF QECIO's** "segregated" counts painted lanes.
- **Clean Cities** counts shared foot/cycle paths but not painted lanes, cycle streets or bus lanes.

QECIO's tag logic is published (Methodology v2.10, Annex II, Table 2), which makes it a citable prior method.

## Decision

### Tiers
Classification happens at the **way-side** level. Road ways are split into left and right sides from `cycleway`, `cycleway:both`, `cycleway:left`, `cycleway:right`, and the legacy `cycleway=opposite_*` and `sidewalk:*:bicycle` keys. Separately mapped ways are classified as themselves (side `self`). Every way-side gets one tier:

| Tier | Meaning | Core tags |
|---|---|---|
| A | separated cycle track | `highway=cycleway` with `foot!=designated` or `segregated=yes`; `cycleway:*=track\|opposite_track` |
| B | shared foot/cycle path | `highway=path\|footway\|pedestrian` + `bicycle=designated`; `highway=cycleway` + `foot=designated` + `segregated!=yes`; `cycleway:*=track` + `cycleway:*:segregated=no` (`B_track_shared`) |
| C | physically buffered lane | `cycleway:*=lane` with a physical separation value on the traffic side of the lane (undirected `separation`, or `separation:left` for a right-side lane / `separation:right` for a left-side lane); `buffer` (a width) is not considered |
| D | painted lane | `cycleway:*=lane` otherwise; advisory lanes become sub-attribute `advisory` |
| E | cycle street / shared | `bicycle_road=yes`, `cyclestreet=yes`; `share_busway` becomes sub-attribute `bus` |

**Excluded** (counted under `excluded` for diagnostics, never in a preset):
- `cycleway=no|none|separate|shared_lane|shared`. `shared_lane` is kept as an attribute only.
- `sidewalk:<side|both>:bicycle=yes|permissive` (cycling merely permitted on the footway).
- `access=private|no` unless `bicycle=yes|designated|permissive`; on a road side this tests the road's `access`/`bicycle`.
- `bicycle=no|dismount`.
- `area=yes` (also the road's own `area=yes` for a road side).
- Construction and proposed ways: `highway=construction|proposed`, `construction=yes` on a standalone way; on a road side, the road's `construction=yes` and a side value `cycleway:<side>=construction|proposed`. A `proposed=*` tag on a built way marks a planned change and does not exclude it.

The rules are data (`config/classifier/v1.yaml`), not code. Every classification records the `rule_id` that produced it.

"Protected" is reported as **configurable sums of tiers** (presets, `config/presets.yaml`), so the Clean Cities and ECF definitions can be reproduced as different sums of the same classes.

### Length basis (two lengths are stored for every way-side)
- **`per_side`** (headline): each road side counts its geometry length once. A separately mapped way counts its geometry length once, whether one-way or two-way. This measures **facility length per side of the road**, not route length and not lane length. A main road with cycle tracks on both sides contributes twice its length, so coverage ratios can exceed 100. The two tagging styles (side tags vs separately mapped sidewalk tracks) produce the same numbers.
- **`qecio_weighted`**: QECIO's rule. Unidirectional infrastructure counts half.
  - A way-side from a side tag is bidirectional only if `cycleway:<side>:oneway=no`.
  - A standalone way is bidirectional unless any `;`-separated part of `oneway` or of `oneway:bicycle` is `yes`, `1`, `true` or `-1`.
  - The `ecf_qecio` preset uses this basis.

### Deliberate divergences from QECIO
- `highway=footway|path|pedestrian` + `bicycle=designated` + `segregated=yes` is a QECIO *cycle track*. We put it in **tier B** and keep `segregated=yes` as an attribute. The shared-path inflation in German, Polish and Finnish data then stays visible, and QECIO's "tracks only" figure is still available as A + B[segregated=yes].
- QECIO doesn't separate buffered from painted lanes (its lanes = our C + D).
- `highway=path` + `bicycle=designated` + `foot=no` is tier A (cycle-only path); `access=no` and `construction=yes` are excluded.
- Limited-access roads (QECIO's "extended" indicator) have no tier in v1.

### Notes on side assignment and edge cases
- **Plain `cycleway=<value>` on a oneway road is a tunable parameter** (`parameters.plain_cycleway_on_oneway` in the classifier YAML; decided 2026-10-01). `traffic_side` (default, common OSM reading): on `oneway=yes|1|true` it applies to the right side only, on `oneway=-1` to the left side only, and `junction=roundabout` without an `oneway` tag counts as `oneway=yes`. `both_sides`: the literal reading, both sides. Two-way roads (no oneway, or `oneway=no`) always get both sides; side-specific `cycleway:left|right|both` tags are never affected. `velometer classify --plain-cycleway-on-oneway` overrides it per run. Every run prints the mode it used, how many ways and road km it affects, and, per non-excluded tier, the per_side km that switching modes would add or remove, so the effect on any figure is visible. Persisted runs (M2) must store the effective parameters with the classifier version. Legacy `cycleway=opposite_*` always applies to the left side with `contraflow`.
- **`highway=footway` + `footway=crossing` + `bicycle=designated`** is counted as tier B (`B_path`), as QECIO does.

## Consequences

- Changing a rule means a new classifier version (`v2.yaml`). Versions are frozen per run (ADR 0005).
- Fixture tests pin every rule (`tests/fixtures/`).
