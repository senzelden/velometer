# HANDOVER — European Cycling Infrastructure Comparator ("velometer")

Handover for Claude Code. Drop this file into the repo root (or rename to `CLAUDE.md` / copy the relevant parts there). Status of research: 1 October 2026. Owner: Dennis.

---

## 1. What we are building and why

A reproducible pipeline and small read-only app that measures **protected cycling infrastructure** in ~21 European cities from OpenStreetMap, as a **time series 2018–2026**, and sets it against official city figures and published rankings. It is the data backbone for a comparative journalism series with Berlin as the centrepiece (CDU–SPD Senate 2023–2026, documented rollbacks, budget underspend; Die Linke won the 20 September 2026 election, coalition talks ongoing).

The journalistic premise that drives every design decision: **existing rankings are not reproducible.** Clean Cities 2025 mixes city-submitted data with OSM and publishes no code; Copenhagenize is expert scoring; ECF/QECIO publishes tag logic but only per NUTS3 region and frozen in Jan 2024. Our asset is a pipeline anyone can re-run that produces per-city numbers with explicit definitions, and that shows *why* rankings disagree (definitions, denominators, boundaries) rather than hiding it.

Non-goals for v1: no counter/usage modelling, no modal-share harmonisation, no LTS/network-connectivity analysis, no interactive map editor, no scraping of vendor APIs.

---

## 2. Locked decisions (write these up as ADRs first)

Create `docs/adr/` and write these before code. They are decided; the ADRs record rationale.

| ADR | Decision |
|---|---|
| 0001 | Self-built OSM pipeline is the primary source. Published rankings and official figures are comparison layers, never blended into our numbers. |
| 0002 | Classifier is derived from ECF QECIO tag logic (cite it), extended into **tiers A–E** (see §5). "Protected" is reported as configurable sums of tiers, so Clean Cities' and ECF's definitions are reproducible as presets. |
| 0003 | Headline metric: **tier A+B protected km per 100 km of main-road network**. Secondary: absolute km, km per 100k residents. Per-area and total-road-network ratios are computed but not headlined. |
| 0004 | Two boundary layers per city: administrative (LAU 2024) and Functional Urban Area (FUA). Admin is default; FUA is a robustness check. |
| 0005 | Snapshots on 1 January 00:00 UTC each year 2018–2026, from OSM full history, plus one "current" snapshot. The classifier is versioned and frozen per run; every output row carries `classifier_version` and `osm_timestamp`. |
| 0006 | OSM km are labelled "mapped km", never "built km". Mapping-effort artefacts are diagnosed (changeset activity, tag completeness), not corrected away. |
| 0007 | State: **SQLite is canonical** (cities, boundaries metadata, runs, results, official figures, provenance). DuckDB (+spatial) over Parquet for heavy geometry work; results are written back to SQLite. |
| 0008 | Licences: code MIT, derived data ODbL with OSM attribution. External comparison numbers stored with source URL and retrieval date; not redistributed beyond what citation allows. |

---

## 3. Stack and conventions

Ubuntu 26.04, Python 3.12+, **uv** for env/deps, **typer** CLI, **Pydantic v2** at every I/O boundary, **ruff** format+check, **pytest**. Existing user-level Claude Code hooks already run ruff on edit and pytest on stop — keep tests fast (golden fixtures, no network in unit tests; mark network/integration tests `@pytest.mark.slow`).

Core libraries: `osmium` CLI (osmium-tool) and `pyosmium`, `duckdb` with `spatial` extension, `geopandas`/`shapely` only where DuckDB is awkward, `pyproj`, `httpx`, `fastapi` + `jinja2` for the read-only app, `matplotlib` or `vega-lite` (via `altair`) for static charts. Avoid OSMnx for bulk extraction (Overpass-bound, no history).

Projection: compute lengths in a local equal-distance/UTM CRS per city (store EPSG in city config), never in EPSG:4326 degrees.

---

## 4. Repo layout

```
velometer/
  pyproject.toml
  HANDOVER.md
  docs/adr/0001-…md
  docs/methodology.md          # public-facing, generated sections from config
  config/
    cities.yaml                # id, name, country, lau_code, fua_code, osm_relation_id, epsg, geofabrik_region
    classifier/v1.yaml         # tier rules (data, not code)
    presets.yaml               # clean_cities_2025, ecf_qecio, ours_headline
  data/                        # gitignored
    raw/ history/ snapshots/ parquet/ external/
  velometer.sqlite             # gitignored
  src/velometer/
    cli.py                     # typer app
    models.py                  # Pydantic models (§7)
    db.py                      # SQLite schema + repository functions
    sources/ geofabrik.py history.py boundaries.py bikenetkit.py qecio.py
    pipeline/ snapshot.py extract.py explode.py classify.py dedupe.py measure.py
    diagnostics/ completeness.py activity.py reconcile.py
    report/ tables.py charts.py
    app/ main.py templates/
  tests/
    fixtures/                  # tiny .osm XML files per tagging case
    test_classify.py test_explode.py test_dedupe.py test_measure.py
```

---

## 5. Classifier spec (the heart of the project)

Classification happens at the **way-side** level, not the way level. Step one explodes every road way into left and right sides using `cycleway`, `cycleway:both`, `cycleway:left`, `cycleway:right` (and legacy `cycleway=opposite*`). Separately mapped ways (`highway=cycleway`, paths with `bicycle=designated`) are classified as themselves.

Tiers (rules live in `config/classifier/v1.yaml`, not hard-coded):

- **A — separated cycle track.** `highway=cycleway` with `foot` not `designated` or with `segregated=yes`; side tags `cycleway:*=track` / `opposite_track`.
- **B — shared foot/cycle path.** `highway=path|footway|pedestrian` with `bicycle=designated`; `highway=cycleway` with `foot=designated` and `segregated!=yes`. Keep `segregated=yes/no` as an attribute.
- **C — physically buffered lane.** `cycleway:*=lane` where `cycleway:*:separation*` or `cycleway:*:buffer*` indicates kerb, bollard, flex post, planter, parking (any non-paint separation).
- **D — painted lane.** `cycleway:*=lane` without physical separation; includes advisory lanes (`cycleway:*:lane=advisory`) as a sub-attribute.
- **E — cycle street / shared low-traffic.** `bicycle_road=yes`, `cyclestreet=yes`; also bus lanes open to bikes (`cycleway:*=share_busway`) as sub-attribute `E_bus`.
- Excluded: `cycleway=no|separate|shared_lane` (shared_lane recorded as attribute only), `access=private`, `bicycle=no`, ways with `area=yes`, construction/proposed.

Length rules: a separately mapped one-way cycleway counts its geometry length once; a two-way one counts once (we measure route length, not lane length) — record `oneway` as attribute so a lane-length view can be computed later. Side tags on a road count once per side. Divergence from QECIO (which halves unidirectional infrastructure) must be documented in ADR 0002 and handled as a preset option.

**Double-mapping dedupe.** If a road carries `cycleway:*=separate` and a parallel `highway=cycleway` exists, count only the separate way. Implement as: drop `separate` sides entirely (they carry no length), then flag parallel-duplicate candidates where a tier-A/B way lies within 15 m and ≥80% overlap of a road side also classified A–D; log them to `diagnostics.duplicates` for manual review rather than auto-deleting.

**Main-road denominator.** `highway in (motorway, trunk, primary, secondary, tertiary)` plus `_link`, minus `access=private`, minus `area=yes`. Dual carriageways (`dual_carriageway=yes` or paired oneways) count once — follow QECIO v2.10 handling. Motorways are reported both included and excluded; headline uses **excluded** (cyclists can't use them; including them penalises cities with urban motorways). Document in ADR 0003.

Presets in `config/presets.yaml`:
- `ours_headline`: (A+B) / main roads excl. motorway.
- `ecf_qecio`: (A+B+C+D) / main roads incl. motorway, QECIO halving rule.
- `clean_cities_2025`: (A+B, excluding C/D/E) / all public roads (any `highway` road class, excl. private/footways). Note: Clean Cities used city-submitted numbers for 34/36 cities, so this preset reproduces their *OSM fallback method*, not their published numbers.

---

## 6. Data sources

| Source | Use | Access | Notes |
|---|---|---|---|
| Geofabrik full-history extracts (`osm-internal.download.geofabrik.de`) | Historical snapshots | Free, requires OSM account login (OAuth) | Per country `.osh.pbf`. Preferred over the full planet history file (very large). |
| Geofabrik public extracts | Current snapshot | Free | |
| `osmium time-filter` / `osmium extract` | Snapshot at timestamp, clip to boundary | CLI | `osmium time-filter X.osh.pbf 2020-01-01T00:00:00Z -o snap.osm.pbf` then `osmium extract -p boundary.geojson`. |
| ohsome API 2.0 (HeiGIT) | Optional cross-check only | Account/token required | Legacy ohsome API decommissioned end of Nov 2026 — do not build on it. ohsome-planet (OSM history → GeoParquet) is an alternative path if osmium proves slow. |
| Eurostat GISCO LAU 2024 + FUA (Urban Audit) | Boundaries | Free | Fallback: OSM admin relation (store relation id) for any city without a clean LAU polygon. Check Oslo, Ljubljana, Bratislava carefully. |
| Eurostat population (LAU / FUA) | per-100k metric | Free | Store year with the value. |
| BikeNetKit export, Zenodo record 22271229 (Szell & Pessoa, 3 Sep 2026, ODbL) | Validation layer | Free, 5.7 GB | 403 European cities; bike + street networks. Compare our tier totals vs their bike network; record their OSM snapshot date. |
| ECF QECIO v2.10 downloads (`european-cyclists-federation.github.io/download.html`) | Validation at NUTS3 | Free, no licence stated (OSM-derived) | Summary CSV + per-NUTS3 GeoPackages. Berlin = one NUTS3 region; others need careful matching. |
| Clean Cities 2025 report + annexes | Comparison numbers | PDF | Enter manually into `external_figures` (city, km, network km, ratio, note; Vienna corrected value 625.1 km / 22.0%). |
| Official city figures | Comparison | Manual | Stored with `network_scope` and `length_basis` (see §7). |

Do **not** use the Eco-Counter/Eco-Visio API (paid, v1→v2 key change). Counter data, if added later, comes only from open portals (daten.berlin.de, opendata.paris.fr).

---

## 7. Data model (Pydantic + SQLite)

Pydantic models in `models.py`, mirrored as SQLite tables in `db.py` (plain SQL, no ORM required). Key models:

- `City`: id (slug), name, country_iso2, lau_code, fua_code, osm_relation_id, epsg, geofabrik_region, population (value, year, source).
- `Boundary`: city_id, kind (`lau`|`fua`|`osm_admin`), source, source_version, area_km2, path to GeoJSON, sha256.
- `Run`: id, started_at, classifier_version, git_commit, osm_timestamp, boundary_kind, status.
- `TierLength`: run_id, city_id, tier (A–E + sub-attributes), length_km, n_ways.
- `RoadLength`: run_id, city_id, class (`main_excl_motorway`, `main_incl_motorway`, `all_public`), length_km.
- `Metric`: run_id, city_id, preset, value, numerator_km, denominator_km.
- `Completeness`: run_id, city_id, tier, share_with_width, share_with_surface, share_with_segregated.
- `ExternalFigure`: city_id, source (`clean_cities_2025`, `copenhagenize_2025`, `qecio_v2_10`, `bikenetkit_v1`, `official`), metric_name, value, unit, reference_date, **network_scope** (e.g. `whole_network`, `vorrangnetz`, `new_in_year`), **length_basis** (`streckenlaenge`|`reallaenge`|`unknown`), source_url, retrieved_at, note.
- `Duplicate`: run_id, way_id_separate, way_id_road, side, overlap_share, distance_m, resolved (bool).

Every result row is traceable to a `Run`, which is traceable to a git commit, classifier version, OSM timestamp and boundary sha256.

---

## 8. CLI

```
velometer init                              # create sqlite, load config/cities.yaml
velometer boundaries fetch [--city X]       # GISCO LAU/FUA (+ OSM fallback), write GeoJSON + Boundary rows
velometer osm fetch-history --country DE    # download Geofabrik .osh.pbf (needs auth)
velometer osm snapshot --city X --date 2020-01-01
velometer classify --city X --date ... [--boundary lau]
velometer run --cities all --years 2018-2026 [--boundary lau|fua]   # orchestrates the above, resumable
velometer diagnose completeness|activity|duplicates --city X
velometer external load path/to/figures.csv
velometer reconcile --city X                # ours vs QECIO / BikeNetKit / Clean Cities / official; writes gap table
velometer report tables|charts
velometer serve                             # FastAPI read-only app
```

Runs must be resumable and idempotent: skip a (city, date, boundary, classifier_version) tuple that already has a completed `Run`.

---

## 9. Milestones and acceptance criteria

Build for **5 pilot cities first: Berlin, Paris, Vienna, Copenhagen, Wrocław** (covers German shared-path tagging, French dense core, Austrian cycle-street dispute, Danish reference, Polish outlier). Scale to all 21 only after M3 passes.

**M0 — Skeleton (day 1–2).** ADRs 0001–0008 written. uv project, typer CLI stub, SQLite schema, `cities.yaml` with the 5 pilot cities, CI-ready pytest + ruff. *Accept:* `velometer init` creates the DB; tests run green.

**M1 — Classifier with golden tests (week 1).** Implement explode → classify → dedupe → measure on tiny hand-written `.osm` fixtures covering every rule in §5 (≥25 cases: each tier, each exclusion, both/left/right sides, separate, dual carriageway, oneway cycleway, segregated yes/no, advisory lane, bus lane, private access). Then a Berlin real-data fixture: fetch current OSM for ~50 hand-picked ways via Overpass *once*, save as fixture, and have Dennis confirm the expected tier for each (include Kantstraße, Ollenhauerstraße, Unter den Eichen, Karl-Marx-Allee, a Fahrradstraße, a Hochbord shared path). Do not invent way IDs — query them. *Accept:* all fixture tests pass; Dennis signs off the Berlin golden table.

**M2 — Current snapshot for 5 cities (week 2).** Boundaries, current Geofabrik extract, full run, metrics for all three presets, completeness diagnostics. *Accept:* results table per city; `reconcile` output comparing against Clean Cities 2025, QECIO v2.10 (Berlin NUTS3 at minimum) and BikeNetKit; **every gap >20% has a written explanation** in `docs/reconciliation.md`.

**M3 — History 2018–2026 (week 3).** Full-history extracts, yearly 1 January snapshots, runs for all years, activity diagnostics (changesets touching cycling tags per year). *Accept:* time-series table; flagged years where mapping activity spikes coincide with km jumps; FUA robustness run for Berlin and Paris.

**M4 — Report and app (week 4).** Static charts (headline metric over time; tier composition per city; preset comparison showing how rankings flip), generated `docs/methodology.md`, FastAPI read-only app with city pages and a downloadable CSV. *Accept:* `velometer serve` renders all pilot cities; methodology doc lists classifier version, OSM timestamps, presets, known limitations.

**M5 — Scale to 21 cities.** Paris, Copenhagen, Vienna, Amsterdam, Utrecht, Madrid, Barcelona, Stockholm, Oslo, Helsinki, Lyon, Strasbourg, Bordeaux, Wrocław, Warsaw, Kraków, Budapest, Prague, Bratislava, Ljubljana, plus Berlin. Per-country tag-completeness check before trusting any new city.

**M6 — Classifier v4 and the Berlin deep-dive** (added after M5; spec `docs/superpowers/specs/2026-10-04-velometer-m6-design.md`, rulings `docs/superpowers/rulings-m6.md`). Classifier v4 draws the A/B line by whether pedestrians share the surface, not by the `highway` value, and excludes explicit MTB trails (ADR 0002 M6 amendment). Berlin is read per Bezirk (12 OSM admin_level 9 relations plus an explicit LAU-edge remainder row), with a mapped-km change map for a chosen window. HANDOVER §11 length figures sit in the DB as cited rows. *Accept:* v4 is the report classifier with 420 done runs (current and 2018–2026, LAU and FUA, none `-dirty`); Bezirk rows plus remainder sum to the city within 0.01 km; every flag and gap is explained on the v4 run set; delivered 2026-10-05.

**M7 — Reader app and narratives** (added after M6; spec `docs/superpowers/specs/2026-10-06-velometer-m7-design.md`, rulings `docs/superpowers/rulings-m7.md`). The app becomes a reader: hybrid navigation, a tab page per city (including a Figures tab that sets our numbers beside every reported figure), a compare page with four views (lines, small multiples, rank, table) whose state lives in the URL, a step-driven stories page, and a `/differences` explainer. Narratives exist for all 21 cities plus a combined story; they quote external sources only, from a registry of 106 sources and 266 excerpts in `content/sources/*.yaml`, and project documents are cited as data, never quoted. `velometer content --check` validates every narrative against the DB (declared numbers, no construction verbs for OSM figures, excerpt length and attribution, all 21 cities present). Charts are an own SVG module with `node:test` tests; Vega is removed, the CSP is strict, and the only external host a page loads from is `tile.openstreetmap.org`. The Berlin Vorrangnetz figure in `config/external/figures.csv` is corrected from 7.5 to 9.8 km (7.5 was the Ergänzungsnetz sum row). No new runs; for that correction the curated external sources were reloaded into the DB (backed up first) and `reconcile --write` rewrote the one reconciliation row (7.5 -> 9.8 km); no run row changed. *Accept:* gate green including the node tests; `timeseries`, `reconcile`, `trust`, `report methodology` and `content` checks exit 0; user review of sources, shifts, narratives and explainer approved 2026-10-06 (rulings-m7 Task 8); delivered 2026-10-06.

**M8 — Organisations, plans and counters** (added after M7; spec `docs/superpowers/specs/2026-10-07-velometer-m8-design.md`, rulings `docs/superpowers/rulings-m8.md`). `/organisations` profiles the 9 bodies behind our comparison figures and Berlin's plan (who they are, how they measure, their political role), with claims and quotes from the source registry only. `/plans` gives one row per city's cycling plan (21 plans, 129 reported figures stored as printed in `config/plans/reports.csv`, revisions and suspect figures kept and flagged); `/plans/berlin` sets, per plan item, the yearly target against every document's reported figure (118 Berlin rows), the infraVelo completed projects and our mapped A+B km on the planned network, drawn as the change since 1 January 2022. That overlay (`velometer plans overlay berlin`) re-reads the cached Berlin LAU snapshots and matches A/B way-sides to the Senate's network by buffer and angle; its parameters are versioned data and the page shows `overlay_v4` (v1 to v3 superseded, history in `docs/review/m8-overlay.md`). Counters: open counter data for Berlin, Paris, Vienna, Helsinki, Madrid, Oslo and Barcelona (`velometer counters fetch/load`), indexed per spec §2.13 (base 2019, Madrid 2020; Barcelona as average daily intensity); a Counts tab beside the A+B mapped-km index, a counter-index metric in Compare, and a "no open counter data found" note with the portals checked for the other 14 cities. Counts are context, never an outcome; `content --check` rejects causal wording between counts and km. **DB writes:** no new OSM runs and no change to existing tables. Schema v8 → v9 added `plan_overlay` and `counter_sites`, `counter_daily`, `counter_monthly`, `counter_index`, and M8 wrote only into those tables (160 overlay rows, four versions; 682 counter sites, 90 index years), after the one-time backup `data/velometer-pre-m8.sqlite` (v8; the 15 pre-existing tables have the same row counts in both files). *Accept:* gate green including the node tests; `timeseries`, `reconcile`, `trust`, `report methodology`, `content` and `counters` checks exit 0; user review of profiles, plans, overlay and counters 2026-10-07 (rulings-m8 Task 8), overlay_v4 by user decision; render check of every new route at 1280 and 390 px; delivered 2026-10-08.

---

## 10. Known pitfalls (put these in tests or diagnostics, not just in prose)

1. **Shared paths inflate German, Polish, Finnish figures.** Always report A and B separately; headline A+B but show the split.
2. **OSM mapping effort ≠ construction.** A km jump may be a mapping campaign or import. Diagnose with changeset activity; never write "Berlin built X km" from OSM deltas.
3. **Boundaries.** Berlin is a city-state of 891 km²; Paris intra-muros is ~105 km²; Lyon commune vs Métropole changes everything. Admin and FUA both computed.
4. **Berlin official series has a methodology break** (Reallänge until 2022, Streckenlänge from 2023). Never splice; store `length_basis`.
5. **Berlin 2025 figure exists in four versions:** 21.2 km (Senate Fortschrittsbericht via dpa, Sep 2026 — use this, basis unknown), 20.5 km (Senate preliminary, Dec 2025), 17.3 km (infraVelo, Vorrang+Ergänzungsnetz only), 25.2 km (Changing Cities monitor). Load all four as separate `ExternalFigure` rows.
6. **Clean Cities Vienna correction:** 14% → 22.0% after city resubmitted, adding restricted-access streets. Store both values.
7. **Tag schema drift over time.** `cycleway:both` and `*:separation` became common only in recent years; 2018 data uses older patterns. Classifier must handle legacy tags (`cycleway=opposite_track`, `cycleway=opposite_lane`, `sidewalk:*:bicycle=yes`) — test against an old snapshot.
8. **Geometry lengths in metres in a projected CRS.** Unit test that a known 1 km segment measures 1.000 ± 0.005 km.
9. **Network-dependent tests must not run in the default pytest pass** (the Stop hook runs pytest).

---

## 11. Reference facts for the narrative layer (status 27 Sep 2026)

Not inputs to the pipeline; load relevant ones as `ExternalFigure` rows with confidence notes. Re-verify before publication.

- Berlin Vorrangnetz: 78.2 km of ~870 km implemented (Senate answer, Drs. 19/25987) — primary source.
- Berlin 2025 money: ~€27M spent of €82.4M available across all budget lines (Fortschrittsbericht via dpa).
- Berlin network 2017–2025: ~140 km of 2,400 km (~5.8%) completed (Senate report as reported).
- Berlin Mobilitätsgesetz amendment July 2026: Vorrangnetz target 2030 kept, rest moved to 2035 (secondary).
- Kantstraße: rollback to shared bus/bike lane (~€2.4M) before Verwaltungsgericht on DUH urgent application; Senate postponed works to 7 Oct 2026; no ruling yet.
- Titel 72016: €6.5M (2025) → €0.5M/yr from 2026 per ADFC; conflicting €4.75M figure for 2025 — unresolved.
- Clean Cities 2025 (protected share of road network): Paris 48%, Helsinki 48%, Copenhagen 43%, Amsterdam 34%, Wrocław 20%, Barcelona 19%, Berlin 17% (925 km), Oslo 17%, Warsaw 15%, Lyon 14%, Vienna 22.0% (corrected), Madrid 8%, Prague 6%, Budapest 4%.
- Copenhagen: no Cykelregnskab since the switch to annual Mobilitetsredegørelse; 2026 edition reports cycling trip share 28% (−1 pp) and cycle km −6%.
- Vienna Radwegoffensive 2025 Bilanz: 20,447 m of projects.
- EU Urban Mobility Indicators (C(2026) 4676, 9 Jul 2026): cycling only as trip mode share, first data end-2027 — no infrastructure indicator.

---

## 12. Open questions for Dennis (ask, don't guess)

1. Repo name and whether it lives in the personal web monorepo or standalone.
2. Confirm the Berlin golden-way expected tiers (M1).
3. Headline excludes motorways from the denominator — confirm.
4. Publish the app publicly from M4, or keep private until the first article?
5. Geofabrik internal access: Dennis needs to provide OSM OAuth credentials via the existing secrets setup; Claude Code must not hard-code or log them.

---

## 13. First session for Claude Code

1. Read this file fully. 2. Create the ADRs from §2. 3. Scaffold §4 with uv. 4. Write `config/classifier/v1.yaml` and the fixture tests from §9/M1 **before** implementing classification. 5. Implement until fixtures pass. 6. Stop and ask Dennis for the Berlin golden-way review.
