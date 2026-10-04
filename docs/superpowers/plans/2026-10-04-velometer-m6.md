# velometer M6: classifier v4 and the Berlin deep-dive — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put classifier v4 (unified facility rule, MTB exclusion) under all 420 report runs, and add a per-Bezirk view of Berlin, a change map and the HANDOVER §11 facts, on a hardened base.

**Architecture:**
- **Part 1 (Tasks 1–12, offline, TDD)** prepares the code:
  - the M5 follow-ups;
  - a key-prefix matcher and `v4.yaml`, with a golden-diff tool;
  - schema v8 with subarea tables;
  - subarea config and boundary assembly;
  - per-subarea attribution inside `measure`/`run`;
  - CLI read surfaces and `report change`;
  - the app's Bezirk section;
  - a `source_url`-enforcing figures loader;
  - the methodology entries.
- **Part 2 (Tasks 13–18)** is execution on real data in the spec's §7 order: onboard Bezirke → v4 impact and **your review** → switch → full run → explanations → report.

**Tech Stack:** Python 3.13, uv, typer, Pydantic v2, SQLite, osmium-tool, pyosmium, shapely, FastAPI, Jinja2, altair + vl-convert-python, matplotlib, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-04-velometer-m6-design.md`. Also read:
- ADRs 0002, 0004, 0005, 0006 and 0007;
- `docs/superpowers/rulings-m5.md`, especially "Known follow-ups" and "Classifier design points";
- the M5 plan `docs/superpowers/plans/2026-10-03-velometer-m5.md`, for the conventions its tasks used.

## Global Constraints

- **Gate:** `uv run ruff format --check . && uv run ruff check . && uv run pytest`. Network tests
  are `@pytest.mark.slow` and deselected by default.
- **Tests stay offline.** They never touch the network, the real `velometer.sqlite` or `data/`.
  They build fixture DBs in `tmp_path` with the M3 fakes (`tests/test_run_history.py`) and
  `tests/report_fixture.py`.
- **Units and labels.**
  - Lengths are computed only in the city's projected EPSG.
  - OSM km are "mapped km" (ADR 0006), and the change map's words are "mapped gained / lost /
    retiered / redrawn"; never "built" or "removed".
  - Every chart, CSV and page footer carries `Map data © OpenStreetMap contributors, ODbL 1.0`.
- **Classifier rules are data.** Never edit `config/classifier/v1.yaml`, `v2.yaml` or `v3.yaml`.
  v4 is `config/classifier/v4.yaml` (ADR 0005). `report_classifier` changes only in Task 15.
- **Never type OSM ids from memory.** Query them, and record the query and its date in the file's
  header comment. This applies to the Bezirk relation ids.
- **`config/trust.yaml` and `config/reconcile.yaml` stay out of `config_sha256`** (classifier,
  presets and activity only).
- **The app** binds only to loopback. Scripts come only from `/static/`, and the only external
  host is the OSM tile server.
- **Mapper data is aggregate only:** no uid or username in any table, CSV, page or doc.
- **OSM credentials** come only from `pass` or the stored Geofabrik cookie. Never print, log or
  write them.
- **Commits:**
  - stage explicit paths;
  - end with one trailer, `Assisted-by: Claude:<model-id>`, carrying the implementer's own model
    id;
  - never commit `data/` or `velometer.sqlite`;
  - never push.
- **Red-proof every new test.** It must fail without its change; break the rule under test, and
  say how in the task report.
- **Bash runs unsandboxed** in this repo (`dangerouslyDisableSandbox: true`). The sandbox cannot
  start on this machine.
- **Runs need a clean tree** (no `-dirty`). Never edit tracked files while a run batch is going
  (M5 R13/R19).

## Review Focus

1. **A Berlin v4 LAU run without subarea rows.** For example, a run made before
   `boundaries fetch --subareas`, or with one Bezirk file missing. The run must fail (a missing
   file raises) or `timeseries --check` must fail. Never a silent hole in the Bezirk series.
   Pinned in Tasks 7 and 8.
2. **A change map whose two runs differ in classifier, boundary sha or kind**, or whose snapshot
   file is gone from `data/snapshots`. `report change` refuses with the reason, and never compares
   across classifiers. Pinned in Task 9.
3. **A way split into two ids between snapshots,** same tier and same place. It is `redrawn`,
   not one `lost` plus two `gained`. Pinned in Task 9.
4. **Tag values with `;` or `,` parts on the facility rule** (`foot=yes;designated`,
   `segregated=yes;no`), and `mtb=no`. The same part semantics as v2/v3 apply: any part counts,
   and `mtb=no` never excludes. Pinned in Task 2.
5. **An untrusted city with `subareas` configured.** No Bezirk section, no subarea CSV, 404 on its
   subarea routes, as for the other report surfaces. Pinned in Task 10.

---

## Part 1 — Build (offline)

### Task 1a: Follow-ups, code and test hygiene (T1–T11, T13b, T16)

**Files:**
- Modify (as each item needs):
  - `src/velometer/db.py`, `memory.py`, `cli.py`, `boundaries.py`, `charts.py`;
  - `src/velometer/app/main.py`, `src/velometer/report/data.py`, `src/velometer/trust.py`,
    `config.py`, `sources/download.py`, `timeseries.py`.
- Test: the tests each item names.

**Interfaces:**
- Consumes: nothing new.
- Produces: no new public names. `PageCache.get` stays as is; `ReportData._city_fields` becomes
  the public `ReportData.city_fields()` (T9).

The items are listed in `docs/superpowers/rulings-m5.md` "Known follow-ups". Work through them in
this order. For each one, either fix it with a test that fails without the fix, or close it with a
one-line ruling in `docs/superpowers/rulings-m6.md` (create the file, headed `# M6 rulings`, with
a `## Task 1a` section).

- [ ] **Step 1: T1.** `create_schema` inside a caller's transaction. Test: open a connection, run
  `BEGIN`, then call `create_schema`. Expect a clear `SchemaError("create_schema must not run
  inside an open transaction")` instead of `sqlite3.OperationalError`. Implement this as a check
  of `conn.in_transaction` before `BEGIN`.
- [ ] **Step 2: T2.**
  - In `tests/test_memory.py` (or wherever `PeakRss` is tested), allocate a 200 MB bytearray
    inside `PeakRss()` and assert `peak.peak_mb >= 150`.
  - Copy the three R3 caveats (lower bound under a long GIL hold, process-wide baseline, the
    cross-check) into the `PeakRss` docstring.
- [ ] **Step 3: T3.**
  - Add a CLI test for the `needs_region` branch (a `lau` + `osm_relation` city goes through
    `boundaries fetch`, with the fakes).
  - Add a `write_boundary` test for ±1 zone adjacency with `epsg_exception`.
  - Add `tests/test_epsg_stored.py`. It iterates over `data/boundaries/*_lau.geojson` when the
    directory exists, and skips with the reason "no data/boundaries in this checkout" otherwise.
    For each file it asserts `check_epsg` passes. This brings back the spec §5.3 stored-boundary
    test.
- [ ] **Step 4: T4.**
  - Replace `test_pilot_cities_carry_their_external_source_ids` with a test of the rule: every
    configured city has a non-empty `bikenetkit_id` and `nuts3_code`.
  - Compare golden float fields with `pytest.approx(rel=1e-9)`.
- [ ] **Step 5: T5, T6 (`tests/test_report_data.py`).**
  - Remove the no-op `rankings[1:]` and the `object.__setattr__` mutation; build a second config
    instead.
  - Compute city ids once per `ranking_rows` call.
  - Derive the fixture NUTS3 codes from the fixture cities.
  - Drop the redundant assertion.
  - Make the reconcile `--check` assertion check the exit code and the named missing key.
- [ ] **Step 6: T7.** Pin the cycling-tags filter in `diagnose_city`. Table-driven test: a way
  with only `bicycle=yes` (not cycling-tagged per `config/activity.yaml`), one with
  `cycleway:right=lane`, and one with `bicycle_road=yes`. Assert which ones enter the denominator.
- [ ] **Step 7: T8 (`trust.py`, `cli.py`).**
  - Test the multi-city `osmium.merge` path of `trust sample` with a fake `osmium`.
  - Unit-test the skip reason of `check_country_golden`.
  - Extract the classify→observed loop that appears three times into
    `velometer.trust.observed_tiers(ways, cfg) -> dict[int, set[tuple[str, str, str]]]` (side, tier,
    rule of every tiered way-side). Use it in `trust.py`, `tests/test_golden.py` and
    `tests/test_golden_countries.py`.
  - Move the per-city loading of `trust sample` from `cli.py` into
    `velometer.trust.load_sample_inputs`.
  - Hoist the mid-file imports in `tests/test_trust.py`.
- [ ] **Step 8: T9.**
  - Rename `ReportData._city_fields` to `city_fields`.
  - `ReportConfig` rejects duplicate ids within `highlight` or `comparison_set` with a
    `ConfigError` naming the id. Test it.
  - Assert the rings-layer filter by parsing the spec's layer `transform`, not by substring.
- [ ] **Step 9: T10.**
  - The cached CSV keeps its body cached, but `git_commit()` and the "generated" line are
    computed per request and prepended. Test: two requests with a monkeypatched `git_commit`
    returning different values give different first lines.
  - Add a threaded test for `PageCache.get`: 8 threads, one build call.
  - `LazyData` forwards only the `ReportData` public attributes (`__getattr__` checks
    `name in ReportData.__dict__` and that the name has no leading underscore); test that an
    unknown attribute raises `AttributeError`.
  - Compute the fingerprint once per request (store it on `request.state`).
- [ ] **Step 10: T11.**
  - `_boundary_source` reads `Boundary.kind` and `source_version` instead of the "OSM relation"
    prefix.
  - Build the golden path in one helper, `velometer.trust.golden_paths(cc, config_dir)`.
  - With a scratch `--config-dir`, show "golden: not found at <path>" instead of "none".
  - The English Status column shows the country's `status` from `trust.yaml`.
- [ ] **Step 11: T13b.**
  - Red-proof the missing-code error test and record how in the report.
  - Add a `lau_codes` + `admin_boundary: osm_relation` config test; this combination is rejected
    with a `ConfigError`, since the union and a relation are two admin layers.
  - Remove the `# type: ignore` on `_positive` by typing it `object -> bool` with an explicit
    `isinstance` check.
  - Split the bundled `lau_codes` config test into one test per assertion.
- [ ] **Step 12: T16.**
  - Make the timeseries shipped-config test assert the rule (every trusted city appears in
    `required`), not the default.
  - Parse `history.yaml` with `yaml.safe_load` instead of the 2-space regex.
  - The no-sidecar computed-md5 path logs `md5_source: computed (no published md5)` at WARNING.
    Test it with `caplog`.
- [ ] **Step 13: Run the gate.**

Run: `uv run ruff format --check . && uv run ruff check . && uv run pytest`
Expected: all pass.

- [ ] **Step 14: Commit in item-sized commits.** Use `git add <paths>` with explicit paths, then
  `git commit -m "fix(m6): T<n> …"`, ending each message with the trailer.

### Task 1b: Follow-ups that touch published output (T15, T13c, residuals)

**Files:**
- Modify: `src/velometer/report/maps.py`, `config/cities.yaml` (Madrid, Barcelona
  `population_override.source_url`), `docs/review/m3_timeseries.md`
- Modify: the construction-label test in `tests/test_timeseries.py`
- Test: `tests/test_maps.py`, `tests/test_config.py`, `tests/test_timeseries.py`

**Interfaces:**
- Produces: `velometer.report.maps.clip_feature(geom_4326, boundary_4326) -> BaseGeometry | None`.

- [ ] **Step 1: Write the failing map test.**

```python
def test_a_way_crossing_the_boundary_is_drawn_only_inside(tmp_path):
    # boundary: unit square around (13.40..13.41, 52.52..52.53); way runs from inside to outside
    boundary = box(13.40, 52.52, 13.41, 52.53)
    line = LineString([(13.405, 52.525), (13.42, 52.525)])
    clipped = clip_feature(line, boundary)
    assert clipped is not None
    assert clipped.bounds[2] <= 13.41 + 1e-9
    assert clip_feature(LineString([(13.5, 52.6), (13.6, 52.6)]), boundary) is None
```

- [ ] **Step 2: Run it and confirm it fails** with `ImportError: clip_feature`.
- [ ] **Step 3: Implement `clip_feature`** (return `None` for an empty intersection, otherwise the
  intersection). In the GeoJSON writer and the PNG renderer of `maps.py`, replace each way's
  geometry with `clip_feature(geom, boundary)` and drop `None`.
- [ ] **Step 4: Add a test that drawn and counted km agree** on the measure fixture. Sum the
  lengths of the drawn tier-A features in the city EPSG and compare with the tier-A per_side km
  from `measure` (`pytest.approx(rel=1e-6)`).
- [ ] **Step 5: T13c.** Set Madrid's and Barcelona's `population_override.source_url` to the INE
  API URL already recorded in the `cities.yaml` header. Remove the JS page URL from the
  `source_url` and keep it in the header comment as the human-readable page. Test: every
  `population_override.source_url` of a configured city is `https://` and does not end in `.htm`
  or `.html`. This guards against the JS page coming back.
- [ ] **Step 6: Residuals.**
  - Re-wrap the paris/lau/2021 and ljubljana/fua/2025 explanation lines to 100 columns.
  - Change the construction-label test to check every explanation whose `Cause:` line contains
    `**construction**` anywhere, not only those that start with it.
- [ ] **Step 7: Gate and commit.** Run `uv run velometer timeseries --check` too; it must still
  exit 0.

### Task 2: Key-prefix match and classifier v4

**Files:**
- Modify: `src/velometer/pipeline/match.py`
- Create: `config/classifier/v4.yaml`
- Create: `tests/test_classifier_v4.py`
- Modify: `tests/test_match.py` (or the file that tests `matches`)

**Interfaces:**
- Produces:
  - **Matcher grammar:** a tag key ending in `*` matches the `;`/`,` parts of every tag whose key
    starts with the prefix before the `*`. `{"mtb:scale*": {"absent": false}}` therefore means "any
    `mtb:scale` or `mtb:scale:…` key is present".
  - **v4 rule ids:** `X_mtb_trail` (excluded, subtype `mtb`), `B_crossing`, `A_segregated`,
    `B_shared`, `A_cycle_only`. `A_cycleway`, `B_cycleway_foot`, `A_path_cycle_only`,
    `B_path_segregated` and `B_path` do not exist in v4.

- [ ] **Step 1: Write the failing matcher tests.**

```python
def test_prefix_key_collects_every_matching_key():
    tags = {"mtb:scale:imba": "2"}
    assert matches({"mtb:scale*": {"absent": False}}, tags, {})
    assert matches({"mtb:scale*": {"absent": False}}, {"mtb:scale": "0"}, {})
    assert not matches({"mtb:scale*": {"absent": False}}, {"mtb": "yes"}, {})
    assert matches({"mtb:scale*": ["2"]}, {"mtb:scale": "1", "mtb:scale:imba": "2"}, {})
```

- [ ] **Step 2: Run it and confirm it fails.**
- [ ] **Step 3: Implement the prefix key** in `matches`:

```python
        else:
            if key.endswith("*"):
                prefix = key[:-1]
                values = set()
                for k, v in tags.items():
                    if k.startswith(prefix):
                        values |= set(parts(v, separators))
            else:
                values = set(parts(tags.get(key), separators))
            ok = _check(values, cond, lists)
```

`validate_expr` accepts such keys unchanged; they are plain tag keys to it.

- [ ] **Step 4: Write `config/classifier/v4.yaml`.**
  - Copy v3, set `version: v4`, and add a header paragraph naming the user decisions of
    2026-10-04 (spec §2, decisions 3, 4 and 9).
  - Insert `X_mtb_trail` directly after `X_bicycle_no`.
  - Replace the block from `A_cycleway` through `B_path` with the rules below, keeping
    `B_track_shared` and `A_track_side` where they are (between them, as in v3).

```yaml
  - id: X_mtb_trail
    applies_to: standalone
    tier: excluded
    subtype: mtb
    # explicit MTB tagging only; surface and route=mtb membership are not used (M6 spec §3.3)
    match:
      highway: [path, cycleway, footway]
      any:
        - {"mtb:scale*": {absent: false}}
        - {mtb: ["yes", designated, permissive]}
        - {"mtb:type": {absent: false}}
        - {cycling: mtb}
  # --- tier A/B on standalone ways: the unified facility rule (M6 spec §3.2) ---
  - id: B_crossing
    applies_to: standalone
    tier: B
    # designated crossings stay B, as v1-v3 counted them through B_path (ADR 0002)
    match: {highway: footway, footway: crossing, bicycle: designated}
  - id: A_segregated
    applies_to: standalone
    tier: A
    match:
      segregated: "yes"
      any:
        - {highway: cycleway}
        - {highway: [path, footway, pedestrian], bicycle: designated}
  - id: B_shared
    applies_to: standalone
    tier: B
    match:
      any:
        - {highway: cycleway, foot: [designated, "yes", permissive]}
        # a missing foot tag on path/footway/pedestrian means pedestrians may use it (decision 9)
        - {highway: [path, footway, pedestrian], bicycle: designated, foot: {not_in: ["no"]}}
  - id: A_cycle_only
    applies_to: standalone
    tier: A
    match:
      any:
        - {highway: cycleway}
        - {highway: [path, footway, pedestrian], bicycle: designated, foot: ["no"]}
```

- [ ] **Step 5: Write `tests/test_classifier_v4.py`.** Table-driven over standalone ways
  (`WayRecord(1, tags, LINE)`), asserting `(tier, rule_id)` on v4 and the v3 tier on v3, so every
  case is red-proofed against v3:

```python
CASES = [
    # tags, v4 (tier, rule), v3 tier
    ({"highway": "cycleway"}, ("A", "A_cycle_only"), "A"),
    ({"highway": "cycleway", "foot": "no"}, ("A", "A_cycle_only"), "A"),
    ({"highway": "cycleway", "foot": "yes"}, ("B", "B_shared"), "A"),
    ({"highway": "cycleway", "foot": "permissive"}, ("B", "B_shared"), "A"),
    ({"highway": "cycleway", "foot": "designated"}, ("B", "B_shared"), "B"),
    ({"highway": "cycleway", "foot": "designated", "segregated": "yes"}, ("A", "A_segregated"), "A"),
    ({"highway": "cycleway", "foot": "yes", "segregated": "yes"}, ("A", "A_segregated"), "A"),
    ({"highway": "path", "bicycle": "designated"}, ("B", "B_shared"), "B"),
    ({"highway": "path", "bicycle": "designated", "segregated": "yes"}, ("A", "A_segregated"), "B"),
    ({"highway": "footway", "bicycle": "designated", "segregated": "yes"}, ("A", "A_segregated"), "B"),
    ({"highway": "path", "bicycle": "designated", "foot": "no"}, ("A", "A_cycle_only"), "A"),
    ({"highway": "path", "bicycle": "designated", "foot": "designated"}, ("B", "B_shared"), "B"),
    ({"highway": "pedestrian", "bicycle": "designated"}, ("B", "B_shared"), "B"),
    ({"highway": "footway", "footway": "crossing", "bicycle": "designated", "segregated": "yes"},
     ("B", "B_crossing"), "B"),
    ({"highway": "path", "bicycle": "designated", "foot": "no", "mtb:scale": "1"},
     ("excluded", "X_mtb_trail"), "A"),
    ({"highway": "path", "bicycle": "designated", "foot": "no", "mtb:scale:imba": "2"},
     ("excluded", "X_mtb_trail"), "A"),
    ({"highway": "path", "bicycle": "designated", "foot": "no", "mtb": "designated"},
     ("excluded", "X_mtb_trail"), "A"),
    ({"highway": "path", "bicycle": "designated", "foot": "no", "mtb:type": "downhill"},
     ("excluded", "X_mtb_trail"), "A"),
    ({"highway": "path", "bicycle": "designated", "foot": "no", "cycling": "mtb"},
     ("excluded", "X_mtb_trail"), "A"),
    ({"highway": "path", "bicycle": "designated", "foot": "no", "mtb": "no"},
     ("A", "A_cycle_only"), "A"),
    ({"highway": "path", "bicycle": "designated", "foot": "no", "surface": "dirt"},
     ("A", "A_cycle_only"), "A"),
    # `;` parts (Review Focus 4)
    ({"highway": "cycleway", "foot": "yes;designated"}, ("B", "B_shared"), "B"),
    ({"highway": "path", "bicycle": "designated", "segregated": "yes;no"}, ("A", "A_segregated"), "B"),
]
```

  Also add:
  - `test_retagging_cycleway_to_path_keeps_the_tier`: for every access combination
    (foot ∈ {absent, no, yes, designated} × segregated ∈ {absent, yes, no}), with
    `bicycle=designated` on the path, the v4 tier for `highway=cycleway` equals the tier for
    `highway=path`. The one stated exception is a missing `foot` tag (decision 9: cycleway gives
    A, path gives B), and the test asserts that pair explicitly.
  - `test_every_v3_road_side_rule_classifies_the_same`: the v3 road-side fixtures
    (`tests/fixtures/cases/`) give identical `(side, tier, subtype)` on v3 and v4.
  - `test_v1_to_v3_unchanged`: the v1/v2/v3 YAML files hash to the values recorded in
    `tests/test_classifier_v3.py` (or add the hashes now if none are recorded).

- [ ] **Step 6: Run the tests.** Run `uv run pytest tests/test_classifier_v4.py tests/test_match.py -v`.
  Expected: pass. Red-proof by deleting `X_mtb_trail` from a scratch copy, then by moving
  `B_shared` above `A_segregated`.
- [ ] **Step 7: Gate and commit** with the message `feat(m6): classifier v4 — unified facility rule and MTB exclusion`.

### Task 3: Golden diff tool (`velometer trust golden-diff`)

**Files:**
- Modify: `src/velometer/trust.py`, `src/velometer/cli.py`
- Test: `tests/test_trust.py`

**Interfaces:**
- Consumes: `observed_tiers` (Task 1a), the golden YAML format (`way_id`, `proposed[side, tier,
  rule, subtype, bidirectional]`, `confirmed`, `note`, optional `min_classifier`).
- Produces:
  - `velometer.trust.golden_diff(yml: Path, osm: Path, cfg: ClassifierConfig) ->
    GoldenDiff(cc: str, renamed: list[int], retiered: list[RetierRow], unchanged: list[int])`,
    where `RetierRow(way_id, name, side, old_tier, old_rule, new_tier, new_rule, tags)`.
  - `write_v4_proposal(yml, diff, cfg, out_dir) -> Path`. It writes the golden YAML with
    `proposed` set from `cfg` and `classifier_version: <cfg.version>`.
    - Ways in `renamed` stay `confirmed: true` (tier unchanged, rule id renamed).
    - Ways in `retiered` get `confirmed: false`, with `note: "v3: <tier> <rule>; awaiting
      re-sign"`.
  - CLI: `velometer trust golden-diff --classifier v4 [--out docs/review/trust]` writes
    `<out>/v4-changes.md` and `<out>/v4-golden/<cc>.yaml` for each country file, plus
    `berlin.yaml` from `tests/fixtures/berlin_golden.{yaml,osm}`.

- [ ] **Step 1: Write a failing test** with a two-way fixture: one `highway=cycleway` +
  `foot=yes` way (A → B, retiered) and one `highway=cycleway` way with no foot (A_cycleway →
  A_cycle_only, renamed). Assert the `GoldenDiff` lists, and that the proposal YAML has `confirmed`
  true for the renamed way and false for the retiered one.
- [ ] **Step 2: Run it and confirm it fails.**
- [ ] **Step 3: Implement it** with `observed_tiers` on both configs. A way is `retiered` when its
  set of `(side, tier)` differs between the YAML's `proposed` and v4, and `renamed` when only the
  rule ids differ.
- [ ] **Step 4: Render `v4-changes.md`.**
  - A table per country: way id linked to `https://www.openstreetmap.org/way/<id>`, name, tags
    (sorted `k=v`), the v3 tier and rule, the v4 tier and rule, and an empty `verdict` column.
  - Above the tables, a one-line count: renamed / retiered / unchanged per country.
  - Generated between `<!-- golden-diff:start -->` and `<!-- golden-diff:end -->` markers, as
    `trust diagnose` does.
- [ ] **Step 5: Gate and commit.**

### Task 4: Schema v8 (subareas)

**Files:**
- Modify: `src/velometer/db.py` (`SCHEMA_VERSION`, `_SCHEMA`, `_migrate_7_to_8`,
  `_MIGRATIONS`), `src/velometer/models.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces:
  - **Tables:**

```sql
CREATE TABLE IF NOT EXISTS subareas (
  city_id TEXT NOT NULL, subarea_id TEXT NOT NULL, name TEXT NOT NULL,
  source TEXT NOT NULL, relation_id INTEGER, area_km2 REAL NOT NULL,
  path TEXT NOT NULL, sha256 TEXT NOT NULL,
  PRIMARY KEY (city_id, subarea_id));
CREATE TABLE IF NOT EXISTS subarea_tier_lengths (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL, subarea_id TEXT NOT NULL,
  tier TEXT NOT NULL, subtype TEXT NOT NULL, length_basis TEXT NOT NULL,
  length_km REAL NOT NULL, n_ways INTEGER NOT NULL,
  PRIMARY KEY (run_id, subarea_id, tier, subtype, length_basis));
CREATE TABLE IF NOT EXISTS subarea_road_lengths (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL, subarea_id TEXT NOT NULL,
  road_class TEXT NOT NULL, length_km REAL NOT NULL,
  PRIMARY KEY (run_id, subarea_id, road_class));
```

  - `runs.subarea_sha TEXT` (nullable).
  - `models.Subarea(city_id, subarea_id, name, source, relation_id: int | None, area_km2, path,
    sha256)`.
  - `db.upsert_subareas(conn, rows: list[Subarea])` and
    `db.subarea_rows(conn, run_id) -> dict[str, tuple[list[TierLength], list[RoadLength]]]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_v7_db_migrates_to_v8_keeping_every_row`: copy a v7 fixture DB built with the v7 schema
    script, migrate, assert row counts equal, `subarea_sha` NULL on old runs, `user_version` 8.
  - `test_interrupted_v7_to_v8_leaves_v7`: monkeypatch `_migrate_7_to_8` to run its DDL and then
    raise; assert `user_version` 7 and no `subareas` table.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement it.** `_migrate_7_to_8` adds `subarea_sha` when the `runs` table exists
  and lacks it, the M5 R14 pattern. The three tables go into `_SCHEMA`, so the schema script
  creates them.
- [ ] **Step 4: Gate and commit.**

### Task 5: Subarea config and boundaries

**Files:**
- Modify: `src/velometer/config.py` (`SubareaRelation`, `SubareasConfig`, `CityConfig.subareas`)
- Create: `src/velometer/subareas.py`
- Modify: `src/velometer/cli.py` (`boundaries fetch --subareas`)
- Test: `tests/test_subareas.py`, `tests/test_config.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `osmium.relation_polygon`, `sources.boundaries.load_boundary_polygon`,
  `_valid_polygonal`, `_to`, `db.upsert_subareas`.
- Produces:

```python
class SubareaRelation(_Strict):
    id: int
    name: str
    slug: str  # [a-z0-9_]+, unique within the city

class SubareasConfig(_Strict):
    source: Literal["osm_admin"]
    admin_level: int
    relations: list[SubareaRelation]  # non-empty, unique ids and slugs

# velometer/subareas.py
@dataclass(frozen=True)
class SubareaPolygon:
    subarea_id: str          # the slug
    name: str
    relation_id: int
    polygon: BaseGeometry    # in the city EPSG
    sha256: str              # of the written GeoJSON file

class SubareaCheckError(ValueError): ...

def fetch_subareas(city: CityConfig, region_path: Path, data_dir: Path) -> list[Subarea]
def check_subareas(lau_polygon: BaseGeometry, polys: list[SubareaPolygon],
                   union_tol: float = 0.01, overlap_tol: float = 0.001) -> dict[str, float]
def load_subareas(city: CityConfig, data_dir: Path) -> list[SubareaPolygon]
def subarea_set_sha(polys: list[SubareaPolygon]) -> str  # sha256 over sorted "slug:sha256" lines
```

  Files are written to `data/boundaries/<city>_sub_<slug>.geojson`. `load_subareas` raises
  `FileNotFoundError` naming the missing slug if any configured file is absent (Review Focus 1).

- [ ] **Step 1: Write the failing config tests.** Duplicate slug → `ConfigError`. Empty
  `relations` → `ConfigError`. A city without `subareas` loads as `None`.
- [ ] **Step 2: Write the failing subarea tests** with synthetic polygons in EPSG 25833 near
  Berlin:
  - two halves of a square LAU: `check_subareas` returns
    `{"union_diff_pct": 0.0, "overlap_pct": 0.0}`;
  - halves leaving a 2 % gap → `SubareaCheckError` whose message carries the measured `2.0`;
  - halves overlapping by 0.5 % → `SubareaCheckError`;
  - `load_subareas` with one file deleted → `FileNotFoundError` naming its slug;
  - `subarea_set_sha` is order-independent and changes when one file changes.
- [ ] **Step 3: Run them and confirm they fail.**
- [ ] **Step 4: Implement it.**
  - `fetch_subareas` calls `relation_polygon(region_path, r.id, raw)` per relation.
  - It writes the GeoJSON in the same feature shape as `write_boundary`, with properties
    `{city_id, kind: "subarea", subarea_id, name}`.
  - It projects to the city EPSG for `area_km2`, and returns `Subarea` rows.
  - It does not call `check_epsg`; that is a city-level rule.
- [ ] **Step 5: Implement `boundaries fetch --city X --subareas`.**
  - It needs the city's region file (as for `osm_admin`).
  - It loads the city's LAU polygon from `data/boundaries/<city>_lau.geojson`, then runs
    `check_subareas` and `upsert_subareas`.
  - It prints one line per subarea (slug, name, relation id, km²) and the two check values.
  - A city without `subareas` exits 1 with "no subareas configured for <city>".
  - Test it with the fakes.
- [ ] **Step 6: Gate and commit.**

### Task 6: Per-subarea attribution in `measure`

**Files:**
- Modify: `src/velometer/pipeline/measure.py`
- Test: `tests/test_measure.py`

**Interfaces:**
- Consumes: `SubareaPolygon` (Task 5).
- Produces:

```python
@dataclass(frozen=True)
class SubareaMeasure:
    tier_lengths: list[TierLength]
    road_lengths: list[RoadLength]

class SubareaSumError(ValueError): ...

# MeasureResult gains: road_factors: dict[int, float] = field(default_factory=dict)

def attribute_subareas(
    ways: list[WayRecord], result: MeasureResult, cfg: ClassifierConfig, epsg: int,
    city_boundary: BaseGeometry, subareas: list[SubareaPolygon],
) -> dict[str, SubareaMeasure]

def check_subarea_sums(result: MeasureResult, parts: dict[str, SubareaMeasure],
                       tol: float = 0.005) -> None
```

  `compute_metrics(result, presets)` works on a `SubareaMeasure` unchanged: it reads only
  `tier_lengths` and `road_lengths`.

- [ ] **Step 1: Refactor without behaviour change.** Extract from `measure`:

```python
def _tier_lengths(classified, lengths, clipped: bool) -> list[TierLength]:
    ...  # the existing km / way_ids loop and sort, verbatim

def _road_lengths(public, factors, lengths, rc) -> list[RoadLength]:
    ...  # the existing four RoadLength rows, verbatim
```

`measure` calls them and stores `road_factors=factors`. Run `uv run pytest tests/test_measure.py`:
everything still passes.

- [ ] **Step 2: Write the failing attribution tests.**
  - `test_subareas_sum_to_the_city`: a fixture with ways on both sides of a north/south split,
    one way crossing it. The sum over two subareas equals the city per tier, basis and road class,
    to 1e-9.
  - `test_dual_carriageway_halving_carries_into_subareas`: a paired dual carriageway inside
    subarea `n`. Its `main_excl_motorway` km equals the city's for that pair, both halved.
  - `test_uncovered_sliver_beyond_tolerance_fails`: subareas cover 98 % of the boundary, with a
    tier-A way in the gap. `check_subarea_sums` raises `SubareaSumError` naming the tier and both
    values.
  - `test_a_way_wholly_outside_every_subarea_counts_no_n_ways`.
- [ ] **Step 3: Run them and confirm they fail.**
- [ ] **Step 4: Implement `attribute_subareas`.** For each subarea, `area = subarea.polygon ∩
  city_boundary` and `prepared = prep(area)`. Compute
  `lengths_s = {w.id: clipped_length_km(proj.line(w.coords), prepared, area) for w in relevant}`.
  `relevant` is the ways that carry a tiered way-side in `result.classified`, or are public roads
  (`_public_roads(ways, cfg)`); other ways get 0. Then:
  `SubareaMeasure(_tier_lengths(result.classified, lengths_s, True),
  _road_lengths(public, result.road_factors, lengths_s, cfg.road_classes))`.
- [ ] **Step 5: Implement `check_subarea_sums`.** For each (tier, subtype, basis) and road class
  with a city value above 0.01 km, `abs(sum_parts - city) / city <= tol`. Otherwise raise
  `SubareaSumError(f"{key}: subareas {s:.3f} km vs city {c:.3f} km ({pct:.2f} %)")`.
- [ ] **Step 6: Gate and commit.**

### Task 7: Subareas in the run (current and history)

**Files:**
- Modify: `src/velometer/run.py` (`run_city`, `run_history`), `src/velometer/db.py`
  (`complete_run`)
- Test: `tests/test_run.py`, `tests/test_run_history.py`

**Interfaces:**
- Consumes: `load_subareas`, `subarea_set_sha`, `attribute_subareas`, `check_subarea_sums`.
- Produces:
  - `complete_run(..., subareas: dict[str, SubareaMeasure] | None = None,
    subarea_sha: str | None = None)` writes `subarea_tier_lengths` and `subarea_road_lengths`, and
    `runs.subarea_sha`, in the same transaction.
  - `RunDeps.load_subareas` and `HistoryDeps.load_subareas` (default
    `velometer.subareas.load_subareas`), so tests inject fakes.

- [ ] **Step 1: Write the failing tests** with the M3 fakes:
  - A city with `subareas` on `lau` gets subarea rows and a non-null `subarea_sha`, current and
    history.
  - The same city on `fua` gets none.
  - A city without `subareas` gets none.
  - A missing subarea file makes the run `failed`, with the `FileNotFoundError` text in
    `runs.error`.
  - A `SubareaSumError` makes the run `failed`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement it.** Inside the `PeakRss` block, after `measure`:

```python
            parts, sub_sha = None, None
            if boundary_kind == "lau" and city.subareas is not None:
                polys = deps.load_subareas(city, data_dir)
                parts = attribute_subareas(ways, result, cfg, city.epsg, rec.polygon, polys)
                check_subarea_sums(result, parts)
                sub_sha = subarea_set_sha(polys)
```

  Pass `subareas=parts` and `subarea_sha=sub_sha` to `complete_run`. Mirror this in
  `run_history`. The run key is unchanged (spec §4.2).
- [ ] **Step 4: Gate and commit.**

### Task 8: Subarea read surfaces in the CLI and the timeseries check

**Files:**
- Modify: `src/velometer/cli.py` (`results --subareas`, `timeseries --subareas`),
  `src/velometer/timeseries.py`
- Test: `tests/test_cli.py`, `tests/test_timeseries.py`

**Interfaces:**
- Consumes: `db.subarea_rows`, `compute_metrics`.
- Produces:
  - `timeseries.subarea_series(conn, city_id, selector, history_set_md5) ->
    dict[str, list[SubareaPoint]]`, where `SubareaPoint(label, run_id, osm_timestamp,
    headline: float | None, tier_km: dict[str, float])`;
  - `timeseries.missing_subarea_runs(conn, cities, selector) -> list[str]` (`"<city>/<run_id>"`).

- [ ] **Step 1: Write the failing tests:**
  - `results --city berlin --subareas` prints one row per subarea with the three presets, tier
    km A–E and A/B split, and the line "per 100k: not available per subarea (no subarea
    population)".
  - The same command for a city without subareas exits 1.
  - `timeseries --check` exits 1 naming `berlin/<id>` when a report-classifier LAU run of a
    subarea city has no subarea rows, and exits 0 once the rows exist.
  - `timeseries --city berlin --subareas` prints the yearly series per subarea.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement it.**
  - Per-subarea presets come from `compute_metrics(SubareaMeasure(...), presets)`, on each
    preset's selected basis.
  - `missing_subarea_runs` joins the report runs (`selector`) of cities with `subareas` and
    `boundary_kind='lau'` against `subarea_tier_lengths`.
  - `timeseries --check` calls it and fails with the list.
- [ ] **Step 4: Gate and commit.**

### Task 9: `velometer report change`

**Files:**
- Create: `src/velometer/report/change.py`
- Modify: `src/velometer/run.py` (add `snapshot_path_for_run`), `src/velometer/cli.py`
  (`report change`), `config/report.yaml` (`change_window`), `src/velometer/config.py`
  (`ReportConfig.change_window`)
- Test: `tests/test_change.py`, `tests/test_cli.py`, `tests/test_config.py`
- Create: `tests/fixtures/change/` (two `.osm` files)

**Interfaces:**
- Consumes: `read_ways`, `classify_ways`, `Projector`, `clipped_length_km`,
  `velometer.pipeline.dedupe._share_within` (rename it to `share_within` and keep the old name as
  an alias for the dedupe module), `load_subareas`, `db.run_results`.
- Produces:

```python
Category = Literal["gained", "lost", "retiered", "redrawn", "geometry"]

@dataclass(frozen=True)
class ChangeRow:
    category: Category
    way_id_from: int | None
    way_id_to: int | None
    side: str
    tier_from: str | None   # None/"excluded" on the from side of a gain
    tier_to: str | None
    km: float               # per_side, clipped to the boundary; for redrawn: the to-side km
    km_by_subarea: dict[str, float]
    tags_changed: dict[str, tuple[str | None, str | None]]  # retiered only

@dataclass(frozen=True)
class ChangeResult:
    rows: list[ChangeRow]
    totals_from: dict[str, float]  # tier -> per_side km, recomputed
    totals_to: dict[str, float]

class ChangeRefused(ValueError): ...

def snapshot_path_for_run(conn, run_id: int, data_dir: Path) -> Path
def compute_change(ways_from, ways_to, cfg, epsg, boundary, subareas,
                   redraw_dist_m: float = 15.0, redraw_share: float = 0.8) -> ChangeResult
def check_runs(conn, run_from: int, run_to: int) -> None      # raises ChangeRefused
def check_totals(result: ChangeResult, stored_from, stored_to, tol_km: float = 0.01) -> None
def render_markdown(result, city, run_from, run_to, names: dict[str, str]) -> str
def write_geojson(result, ways_from, ways_to, path: Path) -> Path
def render_png(result, ways_from, ways_to, boundary, path: Path) -> Path
```

- [ ] **Step 1: Write the fixtures.** In `tests/fixtures/change/from.osm` and `to.osm`, use
  synthetic ids ≥ 9,000,000,000 (not real OSM) inside a 1 km box near Berlin:
  - way 9000000001, a cycleway, identical in both → no row;
  - 9000000002, a cycleway in `from` only → `lost`;
  - 9000000003, a cycleway in `to` only, far from everything → `gained`;
  - 9000000004, `highway=cycleway` in `from`, the same geometry with `foot=yes` in `to` →
    `retiered` A → B, with `tags_changed == {"foot": (None, "yes")}`;
  - 9000000005, a 400 m cycleway in `from`, replaced in `to` by 9000000006 + 9000000007 covering
    it → `redrawn` (Review Focus 3);
  - 9000000008, the same id and tier, extended by 50 m → `geometry`.
- [ ] **Step 2: Write the failing tests:**
  - one test per category on the fixtures (above);
  - `test_totals_mismatch_refuses`: `check_totals` with stored totals 1 km off raises
    `ChangeRefused` naming the tier and both values;
  - `test_runs_with_different_classifier_or_boundary_are_refused` (Review Focus 2), with a
    fixture DB of two runs differing in `classifier_version`, then in `boundary_sha256`, then in
    `boundary_kind`;
  - `test_non_done_run_is_refused`;
  - `test_missing_snapshot_is_refused_with_path`: `snapshot_path_for_run` raises
    `FileNotFoundError` naming the expected path;
  - `test_markdown_never_says_built`: the rendered markdown contains no `built` and no
    `removed`, and contains "mapped km".
- [ ] **Step 3: Run them and confirm they fail.**
- [ ] **Step 4: Implement `compute_change`.**
  1. Classify both way lists with `cfg`.
  2. Keep sides with tier A–E. Key them by `(way_id, side)`.
  3. Keys in both with the same tier: `geometry` when the clipped km differ by more than
     0.001 km, otherwise no row. Keys in both with a different tier: `retiered`, with
     `tags_changed` over the union of keys whose values differ.
  4. Keys only in `from` are lost candidates; keys only in `to` are gained candidates. For each
     gained candidate, find lost candidates of the same tier where
     `share_within(gained_geom, lost_geom, 15) >= 0.8` (STRtree on lost geometries). If any match,
     emit one `redrawn` row and mark the matched lost ones consumed.
  5. Remaining candidates are `gained` or `lost`.
  6. `km_by_subarea` clips each geometry to `subarea ∩ boundary`.
  7. `totals_from` and `totals_to` are the per_side sums over all kept sides.
- [ ] **Step 5: Implement `snapshot_path_for_run`.** Read the run row (`source`, `osm_timestamp`,
  `boundary_kind`, `boundary_sha256`, `region_md5`, history set md5), then build the path with the
  same naming functions `pipeline/extract.snapshot` and the history `snapshot_at` use. Factor
  those names out into `velometer.pipeline.extract.snapshot_name(...)` if they are inline.
- [ ] **Step 6: Implement the CLI.**
  - **Invocation:** `velometer report change --city berlin [--from 2023-01-01] [--to current]
    [--out docs/review]`.
  - **Defaults** come from `report.yaml`: `change_window: {from: "2023-01-01", to: current}`.
  - **Run selection:** both dates resolve to done report-classifier `lau` runs via the selector.
    `current` is the latest current run; a date is the history run at that 1 January.
  - **Order:** `check_runs`, then `compute_change`, then `check_totals` against
    `db.run_results(...).tier_lengths` per_side. Then:
    - print `run <from> -> run <to>: totals agree (A..E)`;
    - write `docs/review/berlin_change_<from>_<to>.md` (render_markdown);
    - write `data/maps/berlin_change_<from>_<to>.geojson`;
    - write `docs/review/berlin_change_<from>_<to>.png`.
  - **The markdown:**
    - per-Bezirk km per category;
    - the top 20 rows per category by km, way ids linked to openstreetmap.org;
    - for `retiered`, the changed tags;
    - a header with both run ids, OSM timestamps, classifier and boundary sha;
    - the line "All figures are mapped km (ADR 0006): a gain is a way newly mapped as cycling
      infrastructure, not a construction."
  - **The PNG** uses the `maps.py` palette with four colours (gained, lost, retiered, redrawn),
    light-grey Bezirk outlines and the ODbL footer.
- [ ] **Step 7: Gate and commit.**

### Task 10: The app's Bezirk section and subarea CSV

**Files:**
- Modify: `src/velometer/report/data.py`, `src/velometer/report/charts.py`,
  `src/velometer/app/main.py`, `src/velometer/app/templates/city.html`
- Test: `tests/test_app.py`, `tests/test_report_data.py`, `tests/test_charts.py`,
  `tests/report_fixture.py`

**Interfaces:**
- Consumes: `timeseries.subarea_series`, `db.subarea_rows`, the change GeoJSON path from Task 9.
- Produces:
  - `ReportData.subareas(city_id) -> list[SubareaRow] | None`, where `SubareaRow(subarea_id,
    name, headline, tier_km: dict[str, float], a_share_of_ab: float | None)`; `None` for a city
    without subareas or an untrusted city;
  - `ReportData.subarea_series(city_id) -> dict[str, list[SubareaPoint]]`;
  - `ReportData.subarea_csv_rows(city_id) -> list[dict[str, str]]`, with columns `city_id,
    subarea_id, name, run_id, osm_timestamp, classifier_version, git_commit, config_sha256,
    boundary_sha256, subarea_sha, tier, length_basis, length_km`;
  - `charts.headline_subareas(data, city_id) -> alt.Chart`: small multiples, one per subarea,
    shared y-axis, at most four year labels (as R32);
  - routes: `/data/{city_id}_subareas.csv`, and `/maps/{city_id}_change_{from}_{to}.geojson`
    (served only if the file exists and the city is trusted).

- [ ] **Step 1: Extend `tests/report_fixture.py`.** Berlin gets two subareas with
  `subarea_tier_lengths` and `subarea_road_lengths` rows on its LAU runs.
- [ ] **Step 2: Write the failing tests:**
  - the Berlin page has a "Bezirke" heading, a table with both subareas and the small-multiples
    chart spec;
  - a city without subareas has no "Bezirke" heading;
  - `/data/berlin_subareas.csv` has the provenance columns and the ODbL line;
  - with DE set `pending` in a scratch config, the Berlin page, its CSV and its change GeoJSON
    all return 404 (Review Focus 5);
  - the chart spec has one facet per subarea and a shared y scale.
- [ ] **Step 3: Run them and confirm they fail.**
- [ ] **Step 4: Implement it.** Section order on the city page:
  - the current table;
  - the small multiples;
  - the change map (Leaflet over the existing tile setup, loading the GeoJSON), with its
    per-Bezirk table read from the change markdown's generated block. If no change file exists,
    the text "No change map generated yet" is shown.
- [ ] **Step 5: Gate and commit.**

### Task 11: External figures must carry a source URL; the Berlin "Official and reported figures"

**Files:**
- Modify: `src/velometer/sources/external.py` (`load_figures_csv`), `src/velometer/app/templates/city.html`,
  `src/velometer/report/data.py`
- Test: `tests/test_external.py`, `tests/test_app.py`

**Interfaces:**
- Produces: `load_figures_csv` raises `ConfigError("row <n>: source_url is required")` for a blank
  `source_url`; `ReportData.reported_figures(city_id) -> list[ExternalFigure]` (every source except the three
  comparison layers `clean_cities_2025`, `qecio_v2_10`, `bikenetkit_v1`; sorted by
  `reference_date`). No new source ids are invented: §11 rows use `official` or a source id the
  user approves in Task 14.

- [ ] **Step 1: Write the failing tests:**
  - a CSV row without `source_url` raises with its row number;
  - a row with `network_scope=vorrangnetz` and `length_basis=unknown` round-trips;
  - the Berlin page lists the reported figures with value, unit, scope, basis, date and a source
    link.
- [ ] **Step 2: Run them, implement, and run them again.** First check that `config/external/figures.csv` and every CSV under `tests/fixtures/external/` still
  loads; the existing rows all
  have URLs, and if one does not, stop and report it instead of inventing a URL.
- [ ] **Step 3: Gate and commit.**

### Task 12: Methodology for v4 and subareas

**Files:**
- Modify: `config/limitations.yaml`, `src/velometer/report/methodology.py`
- Test: `tests/test_methodology.py`

**Interfaces:**
- Produces: limitation ids `subareas_osm`, `change_map_mapped`, `mtb_excluded` (EN and DE); the
  rules table shows a `changed from <previous version>` note for every rule id not present in the
  previous classifier version, and lists rule ids removed since it.

- [ ] **Step 1: Write the failing tests.**
  - The three ids exist with non-blank EN and DE text.
  - With a fixture where the report classifier is v4, the rules table shows `A_segregated`,
    `B_shared`, `A_cycle_only`, `B_crossing` and `X_mtb_trail` as new since v3, and lists
    `A_cycleway`, `B_cycleway_foot`, `A_path_cycle_only`, `B_path_segregated` and `B_path` as
    removed.
  - With v3 as report classifier, the output is unchanged from today (`report methodology
    --check` on the shipped config still exits 0).
- [ ] **Step 2: Implement it.** Wording:
  - **`subareas_osm`:** "Bezirk boundaries are the 12 OSM administrative relations
    (admin_level 9), queried from the Berlin extract; slivers against the LAU boundary are under
    0.5 % of every tier and road class."
  - **`change_map_mapped`:** "The change map compares two snapshots on the same classifier. A gain
    is a way newly mapped as cycling infrastructure, and a loss is one no longer mapped. Redrawn
    and retagged ways are shown separately. None of it is evidence of construction (ADR 0006)."
  - **`mtb_excluded`:** "Paths with explicit mountain-bike tagging (mtb:scale, mtb, mtb:type,
    cycling=mtb) are excluded. Trails without such tags remain counted."
  - Write the DE text to match, in the style of the existing entries.
  - Update `classifier_gaps_excluded` to name the MTB exclusion.
- [ ] **Step 3: Gate and commit.**

---

## Part 2 — Execution on real data

Each task here is run by the controller, or by an implementer with the controller watching. Each
ends with a report: commands, run ids, timings and numbers. Back up the DB where a step says so.

### Task 13: Onboard the Berlin Bezirke; migrate to v8

- [ ] **Step 1: Back up the DB:** `cp velometer.sqlite data/velometer-pre-v8.sqlite`. Then run
  `uv run velometer migrate`; expected: `schema v8`.
- [ ] **Step 2: Query the relations** from the Berlin extract (the path comes from
  `velometer osm fetch --city berlin`, which prints it):

```bash
osmium tags-filter -o $TMPDIR/b9.osm.pbf <berlin.osm.pbf> r/boundary=administrative
osmium export -f geojsonseq $TMPDIR/b9.osm.pbf | python -c '…print id, name, admin_level…'
```

  Keep the relations with `admin_level=9` whose polygon lies within the Berlin LAU. Expect 12.
  Write them to `cities.yaml` `berlin.subareas.relations` with `{id, name, slug}`. The slugs are
  ASCII lowercase with `_`, e.g. `charlottenburg_wilmersdorf`. Add the query, the extract's OSM
  timestamp and today's date to the file header. If the count is not 12, stop and report.
- [ ] **Step 3: Fetch the boundaries.** Run `uv run velometer boundaries fetch --city berlin
  --subareas`. Record the union difference and the overlap in ADR 0004 under a new "M6 notes
  (2026-10-04)" section, with the 12 areas.
- [ ] **Step 4: Gate, then commit** `config/cities.yaml` and `docs/adr/0004-two-boundary-layers.md`.

### Task 14: v4 impact, golden diff, §11 research — **stop for review**

- [ ] **Step 1: Run the current LAU runs on v4, clean tree:** `uv run velometer run --cities all
  --classifier v4`. Expect 21 done runs, Berlin with subarea rows. Record the run ids and wall
  clock.
- [ ] **Step 2: Build the delta table.** Write
  `docs/review/trust/v4-impact.md` between generated markers (produced by a scratch script that
  reads the DB; the script is not committed). Per city, from the v3 runs 270–290 and the new v4
  runs:
  - A, B, A+B km per_side, and the deltas;
  - the headline before and after;
  - X_mtb_trail km by highway value;
  - the rank change in `ours_headline`.

  Add one paragraph naming the largest movers.
- [ ] **Step 3: Run the golden diff:** `uv run velometer trust golden-diff --classifier v4`. This
  writes `docs/review/trust/v4-changes.md` and the `v4-golden/` proposals.
- [ ] **Step 4: Research the §11 facts.** For each bullet of HANDOVER §11 (and the four Berlin
  2025 versions of §10.5 that are not yet rows), find the primary source with WebSearch/WebFetch.
  Write `docs/review/berlin_facts.md` with one row per candidate:
  - value, unit and reference date;
  - `network_scope` and `length_basis`;
  - the source URL and retrieval date;
  - primary or secondary;
  - the verbatim sentence;
  - a proposed `source` id;
  - a proposed verdict column, left empty.

  Facts without a reachable source are listed under "Not found" with what was searched. Never
  fill a URL from memory.
- [ ] **Step 5: Commit the three review files**, then **stop and ask the user** in one message to:
  1. accept the v4 impact;
  2. re-sign every retiered golden sample (`v4-changes.md`);
  3. give a verdict on each §11 row.

  Do not continue until they answer.

### Task 15: Switch to v4

- [ ] **Step 1: Copy the golden files.** Copy each re-signed `docs/review/trust/v4-golden/<cc>.yaml`
  over `tests/fixtures/golden/<cc>.yaml`. Set `confirmed: true` with the user's verdicts; a sample
  the user corrected gets their tier and a note. Copy `berlin.yaml` to
  `tests/fixtures/berlin_golden_v4.yaml`. Add
  `test_berlin_golden_on_report_classifier` in `tests/test_golden.py`: it checks
  `berlin_golden_v4.yaml` against the report classifier, and skips with a reason if the file's
  `classifier_version` differs. The v1 Berlin test stays as is.
- [ ] **Step 2: Update the config.**
  - `config/report.yaml` gets `report_classifier: v4`.
  - `config/trust.yaml` gets `classifier_reviewed: v4` for all 14 countries, with today's date in
    a comment.
  - In `config/reconcile.yaml`, `qecio_tracks_km` becomes `{tiers: [A], basis: qecio_weighted}`
    and `qecio_shared_km` becomes `{tiers: [B], basis: qecio_weighted}`, with a comment citing
    spec decision 11.
- [ ] **Step 3: Amend ADR 0002.** Add a "M6 amendment (2026-10-04)" section with:
  - the facility rule table (spec §3.2);
  - decision 9;
  - the MTB exclusion;
  - the divergences it drops (segregated paths in B; `foot!=designated` as the A test);
  - what is kept (`qecio_weighted`, road-side tracks);
  - the measured impact headline numbers from `v4-impact.md`.
- [ ] **Step 4: Load the §11 rows.** Append the signed-off rows to `config/external/figures.csv` (tracked), then run
  `uv run velometer external load config/external/figures.csv`. List the rows not loaded in
  `docs/review/berlin_facts.md` with their reason.
- [ ] **Step 5: Gate, then `trust check`.** `uv run velometer trust check` must exit 0. Then
  commit, with the config, the ADR and the golden files in separate commits.

### Task 16: Full run on v4

- [ ] **Step 1: Back up the DB:** `cp velometer.sqlite data/velometer-pre-m6-run.sqlite`.
- [ ] **Step 2: Run on a clean tree, sequentially, unattended:**

```bash
uv run velometer run --cities all --boundary fua
uv run velometer run --cities all --years 2018-2026
uv run velometer run --cities all --years 2018-2026 --boundary fua
```

  Expect 21 + 189 + 189 done runs. Berlin's 9 LAU history runs carry subarea rows. Record the
  run-id ranges, the wall clock per invocation and the max `peak_rss_kb` per city and kind.
- [ ] **Step 3: Rerun failures.** A failed run is rerun with `--force` only after its cause is
  understood and recorded in `rulings-m6.md`, as R23 did in M5.
- [ ] **Step 4: Record the run set** in ADR 0005 "M6 notes" (the M5 table format) and the peaks
  in ADR 0007 "M6 notes". Commit.

### Task 17: Explanations

- [ ] **Step 1: Regenerate:** `uv run velometer timeseries --write` and `uv run velometer
  reconcile --write`. Commit only the generated blocks.
- [ ] **Step 2: Remove stale explanations.** `timeseries --check` and `reconcile --check` list
  stale explanations (flags or gaps that no longer fire) and missing ones. Remove every stale
  explanation in one commit that lists them in its message.
- [ ] **Step 3: Write the missing and changed explanations,** full prose to the M5 standard
  (M5 decision 2, R24–R26 vocabulary), against run rows and way-level evidence.
  - Name every A/B move v4 causes.
  - Re-check every existing explanation that cites an A/B split or the rules `A_cycleway`,
    `B_cycleway_foot`, `A_path_cycle_only`, `B_path_segregated` or `B_path`, and update the
    numbers and rule names.
  - Use one drafting agent per country group writing to workspace files, and one integrator
    editing the two docs (M5 R24).
- [ ] **Step 4: Run the gates.** `timeseries --check`, `reconcile --check` and `trust check` exit
  0. Commit.

### Task 18: Report, change map, docs and verification

- [ ] **Step 1: Regenerate the report:** `uv run velometer report charts`, `report maps`,
  `report methodology` (EN and DE), `report change --city berlin`. Commit only the generated
  output. `report methodology --check` must exit 0.
- [ ] **Step 2: Render and screenshot.** `uv run velometer serve`, then screenshot every page at
  1280 and 390 px (the headless Chrome script of M5 R31), with a live network log.
  - Check the Berlin Bezirk section, the change map and the reported figures.
  - Spot-check the Berlin, Ljubljana, Stockholm and Vienna pages and three Bezirk rows against
    `velometer results [--subareas]`.
  - Look at every regenerated chart PNG.
- [ ] **Step 3: Update the docs.**
  - Add an M6 entry to HANDOVER §9.
  - Update the `CLAUDE.md` "Latest delivered" line to M6, with its spec and rulings paths.
  - Complete `docs/superpowers/rulings-m6.md` with the rulings by task and the known follow-ups.
  - Commit.
- [ ] **Step 4: Run the final gate:** `uv run ruff format --check . && uv run ruff check . &&
  uv run pytest`, then all four `--check`s. Then do the final whole-branch review
  (superpowers:subagent-driven-development).
