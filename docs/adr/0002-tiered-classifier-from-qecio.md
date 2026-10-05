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

## M6 amendment (2026-10-04)

Classifier v4 (`config/classifier/v4.yaml`) changes the standalone-way rules and adds an MTB
exclusion (M6 spec §3, `docs/superpowers/specs/2026-10-04-velometer-m6-design.md`). The user
decided it on 2026-10-04, accepted its measured impact on 2026-10-05, and it became the report
classifier then. The text above stays as the record of v1–v3.

### Unified facility rule (spec §3.2)

The v3 rules `A_cycleway`, `B_cycleway_foot`, `A_path_cycle_only`, `B_path_segregated` and
`B_path` are replaced. The new rules apply to standalone ways with `highway=cycleway`, or
`highway=path|footway|pedestrian` + `bicycle=designated`, that survive the exclusions. They are
evaluated in this order, and any `;`/`,`-separated part of a value counts:

| rule | condition | tier |
|---|---|---|
| `A_segregated` | `segregated=yes` | A |
| `B_shared` | pedestrians permitted: `foot` ∈ {designated, yes, permissive}, or no `foot` tag on path/footway/pedestrian (decision 9) | B |
| `A_cycle_only` | otherwise (cycleway with no `foot` tag or `foot=no`; path with `foot=no`) | A |

Designated crossings (`highway=footway` + `footway=crossing` + `bicycle=designated`) stay B through
a new `B_crossing` rule ahead of these, as v1–v3 counted them through `B_path`.

**Decision 9: implicit pedestrian access follows the highway value.** On
`highway=path|footway|pedestrian` a missing `foot` tag means pedestrians are permitted (the OSM
default). On `highway=cycleway` it means they are not. So "otherwise → A" applies to cycleways
with no `foot` tag or `foot=no`, and to paths with `foot=no`. Untagged cycleways stay A.

### MTB exclusion (spec §3.3)

`X_mtb_trail` (tier `excluded`, subtype `mtb`) applies to standalone `highway=path|cycleway|footway`
ways with explicit MTB tagging: `mtb:scale` or any `mtb:scale:*` key; `mtb` ∈ {yes, designated,
permissive}; an `mtb:type` key; or `cycling=mtb`. It sits with the other exclusions, before the
tier rules. Surface and `route=mtb` membership are not used.

### Divergences dropped

- **Segregated shared paths in B.** `highway=path|footway|pedestrian` + `bicycle=designated` +
  `segregated=yes` is now tier A (`A_segregated`), as QECIO counts it as a cycle track. The
  `segregated` subtype of B disappears with `B_path_segregated`, so QECIO's "tracks" comparison is
  A alone (`config/reconcile.yaml`, spec decision 11).
- **`foot!=designated` as the A test on cycleways.** A cycleway with `foot=yes` or
  `foot=permissive` is now B (`B_shared`), like `foot=designated`; only cycleways without
  pedestrian access, or segregated ones, are A.

### Kept

- `qecio_weighted`: QECIO's halving of unidirectional infrastructure still lives in this length
  basis, not in the tiers.
- Road-side tracks are unchanged (decision 10): `cycleway:<side>=track` stays A, and
  `B_track_shared` (`cycleway:<side>:segregated=no`) stays B. Road-side rules are identical to v3.
- C/D (buffered vs painted lanes) and the remaining divergences above.

### Measured impact (`docs/review/trust/v4-impact.md`)

v3 against v4 on the same OSM extract (2026-10-03T20:20:50Z), LAU boundary, 21 cities, mapped km
per side (ADR 0006):

- The headline (`ours_headline`) moves by at most 2.7 points per city (Stockholm 263.7 → 261.0,
  Bratislava 61.2 → 58.7, Vienna 91.0 → 89.1). The only rank change is the top pair: Helsinki
  (262.3) now leads Stockholm (261.0).
- A and B swap km in both directions. Cycleways with explicit foot access move A → B (Stockholm
  A −354 / B +344 km, Helsinki −259 / +255, Amsterdam −191 / +191, Vienna −161 / +147). Segregated
  sidepaths move B → A (Ljubljana A +162 / B −166 km, Kraków +127 / −132, Berlin +124 / −131,
  Wrocław +110 / −110, Warsaw +89 / −90).
- The MTB exclusion removes many km but few were counted: X_mtb_trail is 880 km in Oslo, 548 in
  Helsinki, 169 in Prague, 125 in Berlin, 109 in Madrid, yet A+B falls by at most 14.2 km
  (Vienna).
- Six golden samples change tier (`docs/review/trust/v4-changes.md`). The user re-signed all six
  as v4 classifies them (2026-10-05); they carry `min_classifier: v4`. Berlin's set for v4 is
  `tests/fixtures/berlin_golden_v4.yaml`. The v1 set stays as the M1 record.
