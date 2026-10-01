# velometer M0 + M1 design: skeleton and way-side classifier

- Date: 2026-10-01
- Scope: handover milestones M0 (skeleton) and M1 (classifier with golden tests). M2–M5 get their own specs.
- Inputs: `HANDOVER.md`; ADRs 0001–0008 in `docs/adr/`; `docs/research/*`; QECIO methodology (`docs/research/ecf-qecio-2.1-methodology.pdf`).

## 1. Intent

**Outcome:** a test-pinned, data-driven classifier that turns OSM ways into tiered way-side lengths and main-road denominators, plus the project skeleton it lives in.

**Who uses it:**
- Dennis, who signs off on the Berlin golden table.
- Later milestones, which run the classifier on whole cities and history snapshots.

**Done means:**
- Every rule in ADR 0002/0003 is pinned by a fixture test.
- `velometer init` builds the DB.
- The Berlin golden review sheet is ready to sign off.

## 2. Decisions taken in brainstorming (beyond the handover)

1. **Dual carriageways** are deduped by the `dual_carriageway=yes` tag plus geometric pairing. QECIO has no rule to follow here. See ADR 0003.
2. **Two length bases are stored:** `per_side` (headline) and `qecio_weighted`. See ADR 0002.
3. Segregated designated footways and paths stay in **tier B** with an attribute. See ADR 0002.
4. Motorways are excluded from the headline denominator.
5. The repo is standalone in this directory; the package is `velometer`.

## 3. Layout (M0/M1 subset of handover §4)

```
pyproject.toml  CLAUDE.md  HANDOVER.md  LICENSE  .gitignore  .python-version
config/cities.yaml  config/classifier/v1.yaml  config/presets.yaml
docs/adr/  docs/research/  docs/superpowers/
scripts/fetch_berlin_golden.py  scripts/render_golden_review.py
src/velometer/__init__.py cli.py models.py db.py config.py
src/velometer/pipeline/__init__.py read.py explode.py classify.py dedupe.py measure.py
tests/conftest.py tests/fixtures/cases/*.osm tests/fixtures/expected.yaml
tests/fixtures/berlin_golden.osm tests/fixtures/berlin_golden.yaml
tests/test_{config,db,cli,read,explode,classify,dedupe,measure,golden}.py
```

## 4. Units and interfaces

Every pipeline stage is a pure function over plain data. Only `read.py` touches pyosmium, and only `db.py` touches SQLite.

### `config.py`
- Loads and validates the YAML files into Pydantic models:
  - `CityConfig` list;
  - `ClassifierConfig` (version, road classes, separation value lists, ordered rules);
  - `Preset` list.
- An invalid YAML file raises a validation error with the file path.

### `pipeline/read.py`
`read_ways(path) -> list[WayRecord]`
- `WayRecord(id: int, tags: dict[str, str], coords: list[tuple[float, float]])`, with coords as lon/lat.
- Uses pyosmium with node locations, so it works for `.osm` and `.osm.pbf`.
- Ways with fewer than 2 resolvable nodes are skipped and counted, never silently dropped. The function also returns, or logs, a skipped count.

### `pipeline/explode.py`
`explode(way: WayRecord) -> list[WaySide]`

**Output type:** `WaySide(way_id, side: "left"|"right"|"self", kind: "road_side"|"standalone", tags: dict, coords, contraflow: bool)`.

**Standalone ways:** any way whose `highway` is not a carriageway class, i.e. not in the road-class lists, yields exactly one side, `self`.

**Road ways** (`highway` in a road class) yield 0–2 sides:
- **Value precedence:** `cycleway:<side>` > `cycleway:both` > `cycleway`.
- **Sub-keys:** `cycleway:<side>:X` > `cycleway:both:X` > `cycleway:X`. They are resolved into a normalised side tag dict with keys `cycleway`, `cycleway:separation`, `cycleway:buffer`, `cycleway:lane`, `cycleway:oneway`, etc. Side-specific separation keys (`:separation:left`, etc.) are collapsed into the same `separation` key.
- **Plain `cycleway=<value>`** applies to both sides. Exception: `opposite_track|opposite_lane|opposite_share_busway` applies to the **left** side only (contraflow, right-hand traffic), with `contraflow=True` and the value normalised to `track|lane|share_busway`.
- **`cycleway=opposite`** (contraflow with no infrastructure) yields no side.
- **Legacy `sidewalk:<side|both>:bicycle=<v>`** yields a side whose normalised tag is `sidewalk_bicycle=<v>`, when no `cycleway` value exists for that side.
- **Carried attributes:** the road's own `access`, `bicycle`, `area`, `highway`, `oneway`, `construction` and `proposed` are copied into every side's tags under `road:` prefixes, so rules can test them.

### `pipeline/classify.py`
`classify(side: WaySide, cfg: ClassifierConfig) -> Classified`

**Output type:** `Classified(side: WaySide, tier: "A"|"B"|"C"|"D"|"E"|"excluded"|None, rule_id: str|None, attrs: dict[str, str|bool])`.
- `None` means no rule matched. Unmatched cases are not infrastructure, e.g. a plain residential road side without cycleway tags. Callers drop them.

**Rules** are evaluated in YAML order and the first match wins. Exclusion rules come first in the file.

**Rule schema:**
```yaml
- id: A_track_side
  applies_to: road_side          # road_side | standalone
  tier: A
  match: {cycleway: [track]}
  attrs: {}
```

**Match expression grammar:**
- `{all: [...]}`, `{any: [...]}`, `{not: expr}`.
- A mapping of key → condition. Every key must hold. A condition is one of:
  - a scalar (equals);
  - a list (in);
  - `{absent: true}`;
  - `{not_in: [...]}`;
  - `{in_list: <named list>}`, which references a value list in the config (`physical_separation`).
- Keys ending in `*` match any tag key with that prefix, and the condition must hold for at least one such key.

**Attribute extraction (data-driven):**
- `segregated` comes from the `segregated` tag.
- `advisory` = `cycleway:lane=advisory`.
- `bus` = `share_busway`.
- `shared_lane`.
- `oneway` = the bidirectionality per QECIO Table 3, stored as a bool `bidirectional`.

### `pipeline/dedupe.py`

**`flag_parallel_duplicates(classified, crs) -> list[DuplicateFlag]`**
- Pairs a standalone A/B side with a road side classed A–D when the standalone geometry lies within 15 m, buffer-overlaps ≥ 80% of the road-side length, and meets the road side's line.
- Nothing is removed.

**`pair_dual_carriageways(roads, crs) -> dict[way_id, float]`**
- Returns a length factor (0.5 or 1.0) for each main-road way, using the ADR 0003 rule:
  - `dual_carriageway=yes` gives 0.5;
  - otherwise a oneway way with the same `name` or `ref` as another, opposite bearing (angle > 150°), Hausdorff-ish distance ≤ 50 m and ≥ 70% overlap: both ways get 0.5.
- Also returns the detected pairs for diagnostics.

**Implementation:** shapely STRtree in a projected CRS (ADR 0007 note).

### `pipeline/measure.py`
`measure(ways: list[WayRecord], cfg, epsg) -> MeasureResult`

The function orchestrates read → explode → classify → dedupe for one file.

- Lengths are geodesic-free planar lengths in `EPSG:<epsg>` via pyproj `Transformer(always_xy=True)`.

**`MeasureResult`:**
- `tier_lengths: list[TierLength]`. The key is (tier, sub-attribute, basis) and the value is km and `n_ways`.
- `road_lengths: list[RoadLength]`, one per class (ADR 0003).
- `duplicates`.
- `dual_pairs`.
- `classified`, used for review and debugging.

**`qecio_weighted`:** standalone bidirectional → 1.0, otherwise 0.5; road side → 1.0 if `cycleway:oneway=no`, otherwise 0.5.

**Tier lengths** sum every non-excluded tier. Excluded sides are counted under `excluded` (with `rule_id`) for diagnostics.

**`compute_metrics(result, presets) -> list[Metric]`:** numerator = the sum of the preset tiers on the preset basis; denominator = the preset road class; value = 100 × num / den.

### `models.py` and `db.py`
- **Models:** the Pydantic models of handover §7, with the additions from ADR 0002/0003:
  - `TierLength.length_basis`;
  - `Metric.length_basis`;
  - the road classes `main_incl_motorway_raw`;
  - `Duplicate.kind` (`parallel` | `dual_carriageway`).
- **`db.py`:**
  - `connect(path)`;
  - `create_schema(conn)`, an idempotent `CREATE TABLE IF NOT EXISTS`;
  - `upsert_cities(conn, cities)`;
  - generic insert and fetch helpers per model.
- The schema has a `schema_version` pragma (`user_version`).

### `cli.py` (Typer)
- `velometer init [--db PATH]`: creates the schema and upserts `config/cities.yaml`. It is idempotent.
- `velometer classify --file PATH --epsg N [--classifier v1]`: runs `measure` and prints the tier, road and preset tables. It does not write to the DB in M1.

## 5. Config content

**`cities.yaml`:** id, name, country_iso2, epsg, geofabrik_region, osm_relation_id, lau_code (null), fua_code (null), population (null). Five pilot cities:
| City | EPSG |
|---|---|
| Berlin | 25833 |
| Paris | 25831 |
| Vienna | 25833 |
| Copenhagen | 25832 |
| Wrocław | 25833 |

`osm_relation_id` is filled from one Nominatim or Overpass lookup at implementation time, with the query recorded in a comment. Never from memory.

**`classifier/v1.yaml`:**
- `version`;
- `road_classes` (main, motorway, local, `all_public` extras);
- `physical_separation` values (kerb, bollard, flex_post, vertical_panel, planter, parking_lane, fence, guard_rail, jersey_barrier, separation_kerb, grass_verge, tree_row, bump, …);
- `paint_separation` values (solid_line, dashed_line, no);
- ordered `rules`.

**`presets.yaml`:** as listed in ADR 0003.

## 6. Testing

- **Fixtures:** `tests/fixtures/cases/*.osm` are hand-written OSM XML, one case per file. Geometry is synthetic lines near Berlin, with lengths computed in the test from the projected coordinates.
- **`expected.yaml`:** for each case it lists the expected sides (way_id, side, tier, rule_id, key attrs) and, where relevant, `per_side_km`, `qecio_km`, road factors and duplicate flags.
- **At least 25 cases.** The coverage list is in the plan: each tier, each exclusion, side precedence, legacy tags, separation variants, bus lane, cycle streets, oneway/two-way, dual carriageway (tag + pairing), parallel duplicate, motorway handling.
- **Measurement check:** a 1 km synthetic segment measures 1.000 ± 0.005 km.
- **Red-proofing:** `test_classify.py` includes mutation tests. They load v1.yaml, delete or weaken a named rule, and assert that its fixture now classifies differently. This proves every core fixture is sensitive to its rule.
- **Berlin golden set:** `scripts/fetch_berlin_golden.py` queries Overpass once and writes `berlin_golden.osm` (ODbL attribution header) plus `berlin_golden.yaml`. Each entry has way_id, name, proposed tier per side, rule_id and `confirmed: false`. `test_golden.py` asserts that confirmed entries match. Unconfirmed entries are skipped, and the skip count is reported.
- **Review rendering:** `scripts/render_golden_review.py` writes `docs/review/berlin_golden.md` (a table with osm.org links, key tags, proposed tier and rule) and `docs/review/berlin_golden.png` (a matplotlib map coloured by tier).
- **Defaults:**
  - The default pytest run has no network access.
  - The `slow` marker is deselected by default.
  - The ruff format and check gate must be clean.

## 7. Error handling

- Config validation fails loudly, with the file path.
- `read_ways` reports how many ways it skipped.
- An unknown `cycleway` value on a side becomes `tier=None` with `attrs.unknown_value`. Such values are counted in the `classify` output, so tag drift is visible instead of silently disappearing.

## 8. Out of scope

Boundaries, Geofabrik downloads, history snapshots, DuckDB, external figures, reconcile, reports and the app.
