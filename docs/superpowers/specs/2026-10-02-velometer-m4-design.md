# velometer M4 design: report and app

- **Date:** 2026-10-02
- **Scope:** handover milestone M4 (report and app), plus four items the user moved into M4. M5 (scale to 21 cities) gets its own spec.
- **Inputs:**
  - `HANDOVER.md` §3, §4, §8, §9 (M4) and §12, question 4;
  - ADRs 0001–0008;
  - the M2 and M3 specs;
  - `docs/superpowers/rulings-m2.md` and `docs/superpowers/rulings-m3.md`.

## 1. Intent

**Outcome:** a private, local, read-only web app and a generated methodology. Together they show the pilot cities' numbers, how they change over time, how published rankings differ from ours, and how every number was made. This is the working surface for the journalism series. It is not yet a publication.

**Acceptance (HANDOVER §9 M4):**
- Static charts:
  - headline metric over time;
  - tier composition per city;
  - a preset comparison showing how rankings flip.
- A generated `docs/methodology.md`.
- A FastAPI read-only app with city pages and a downloadable CSV.
- `velometer serve` renders every pilot city.
- The methodology lists:
  - the classifier version;
  - the OSM timestamps;
  - the presets;
  - the known limitations.

**Success:**
- Every number in the app and in the docs comes from one classifier (the report classifier) and one config identity, and traces to its run row.
- After the M4 rerun, `reconcile --check`, `timeseries --check` and `report methodology --check` all exit 0.
- The app makes no network request: the JS is vendored and there is no tile server.

## 2. Decisions

### Taken with the user (2026-10-02)

1. The app stays **private**. It runs locally only, bound to 127.0.0.1, and has no deployment target in M4.
2. Charts in the app are **interactive Vega-Lite**, built with altair. The Vega JS is vendored in the repo; nothing loads from a CDN.
3. The **rankings-flip chart** compares the five cities' ranks under:
   - our three presets: `ours_headline`, `ecf_qecio` and `clean_cities_2025`;
   - the published Clean Cities 2025 share;
   - the published QECIO v2.10 indicator.
4. Four items join M4:
   - FUA current runs (deferred by M3 R18);
   - reconcile on the report classifier;
   - a tier map per city;
   - `config/activity.yaml` in run identity.
5. The methodology is written in **both English and German**, as `docs/methodology.md` and `docs/methodology.de.md`.

### Taken in design (user approved the design on 2026-10-02)

6. The app is **live FastAPI plus Jinja over the SQLite file, opened read-only** (`mode=ro`), as HANDOVER §3 specifies. It is not a static-site build.
7. The app UI is in English. Only the methodology is bilingual.
8. Docs charts are PNG exports of the same Vega-Lite specs, made with `vl-convert-python`, which needs no Node. The existing M3 matplotlib chart stays as it is.
9. Tier maps are static matplotlib PNGs drawn from the current snapshot. They have no basemap and carry the ODbL attribution. They are generated into `data/maps/` and never committed.
10. `report_classifier` moves from `config/history.yaml` to a new `config/report.yaml`. Every report surface defaults to it: reconcile, timeseries, charts, methodology and the app. Its value stays `v2`.

## 3. Part 1: data (built first; everything shown depends on it)

### 3.1 `activity.yaml` in run identity (schema v6)

- `config_sha256` covers three files, in this order: the classifier YAML, `presets.yaml` and `activity.yaml`. Each is hashed as `name NUL bytes NUL`, as before.
  - Old runs keep their stored sha. The selector no longer matches them, so they stay in the DB as history but are not reported.
- The `activity` table gains `activity_sha256 TEXT NOT NULL`, which joins its primary key.
  - The v5→v6 migration rebuilds the table, giving existing rows the sha of the `activity.yaml` they were computed with. That is the sha recorded in the current M3 report marker.
  - The migration is atomic, in one transaction, and tested on a v5 copy.
- `fetch_activity` and `replace_activity` take `activity_sha256`.
- `timeseries` reads only activity rows whose sha matches the run identity.
- The `activity=` part of the explained-against marker is **removed**. Identity now covers it, so a changed `activity.yaml` simply finds no runs, and `--check` fails with "no history runs".
- Because the run key includes the sha, any edit to `activity.yaml`, even a threshold, means every run is redone and activity is recomputed for the new sha. This is accepted: it is the identity the user asked for.

### 3.2 FUA current runs

- `run_city` with a boundary that the city's own region extract does not cover (the R18 guard condition) proceeds as follows. The R18 guard stays for the case where no covering set exists.
  1. `regions_for(boundary)` against the cached index.
  2. `fetch_region` for each region: these are current public extracts with published md5.
  3. If there is more than one region, `osmium merge` into `data/raw/merged/<city>_<kind>_<set md5[:8]>.osm.pbf`, cached and atomic. The merged file's `osm_timestamp` is the **oldest** of the region timestamps. The run's `region_md5` is the set md5 over the region md5s, as in M3.
  4. The normal snapshot, measure and persist steps follow.
- Expected sets:
  - Berlin FUA: `brandenburg`, a single region whose extract covers Berlin.
  - Paris FUA: the six regions found in M3.
- Provenance: the regions of a current FUA run, with their md5s, the index path and sha256, and `uncovered_km2`, are recorded in `history_sets` under the run's set md5. `source='current'` runs therefore trace to their region files as history runs do.

### 3.3 One report classifier

- `config/report.yaml` holds `report_classifier: v2`. `history.yaml` keeps only `years` and `required_kinds`.
- `reconcile`, `timeseries`, the chart builders, `report methodology` and the app default to it. Each CLI keeps a `--classifier` override.
- `docs/reconciliation.md` is regenerated on v2. Every explanation is re-checked against the new numbers: text that cites v1-only values is corrected, and stale headings are removed. `reconcile --check` exits 0.
- `docs/review/m2_results.md` and its PNG stay as the M2 record on v1. They gain a one-line note that current figures live in the app and the methodology.

### 3.4 Rerun and regenerate

- Runs on the report classifier with the new identity:

  | Runs | Count |
  |---|---|
  | current LAU | 5 |
  | current FUA (Berlin, Paris) | 2 |
  | LAU history 2018–2026 | 45 |
  | FUA history 2018–2026 | 18 |
  | **Total** | **70** |

- Cached history files and snapshots are reused. Only the current FUA region extracts are new downloads.
- Then the following are regenerated, each followed by its check:
  - `timeseries --write`, with explanations re-checked, since the FUA series now have a current point that may flag;
  - `reconcile --write`;
  - the M3 chart;
  - the M4 charts;
  - the methodology.
- The DB is copied to `data/velometer-pre-v6.sqlite` before the migration.

## 4. Part 2: report and app

### 4.1 Module layout

```
src/velometer/report/
  data.py         # read-only queries the app, charts, CSV and methodology share
  charts.py       # altair chart builders -> Vega-Lite dict; PNG export via vl-convert
  csvexport.py    # CSV rows + attribution header
  methodology.py  # render docs/methodology{,.de}.md from templates + facts; check
  maps.py         # matplotlib tier map per city from the current snapshot
  templates/methodology.en.md.j2, methodology.de.md.j2
src/velometer/app/
  main.py         # FastAPI app factory create_app(db_path, config_dir, maps_dir)
  templates/      # base.html, index.html, city.html, methodology.html
  static/         # vendored vega, vega-lite, vega-embed (pinned versions + LICENSE files), app.css
config/report.yaml        # report_classifier, ranking metrics
config/limitations.yaml   # known limitations, each with en and de text
```

`report/data.py` is the only module that queries the DB for presentation. Charts, CSV, methodology and app all consume its Pydantic models. This keeps one definition of "the current point", "the series" and "the headline" (it reuses `timeseries.build_city` and reconcile's `ours_value`).

### 4.2 Charts

There are three builders. Each returns a Vega-Lite v5 dict and is testable as data.

1. `headline_over_time(series)`:
   - one line per city on LAU, with FUA dashed for Berlin and Paris;
   - x is the snapshot year, plus "now";
   - flagged years are ringed;
   - tooltips give the value, A+B km and flags.
2. `tier_composition(series, city)`: stacked per-side km for tiers A–E per year.
3. `rankings_flip(rank_table)`: a slope chart with one column per ranking source and one line per city. Rank 1 is the highest value.
   - The QECIO published indicator is `(cycle_tracks_km + cycle_lanes_km + shared_pedestrians_km) / main_roads_km × 100` from the `qecio_v2_10` external figures (NUTS3).
   - The Clean Cities published indicator is `protected_share_pct`, scope `whole_network`.
   - These definitions are data in `config/report.yaml`. Each column's footnote states its scope, for example "QECIO: NUTS3 region; Vienna and Paris NUTS3 = city; Berlin = DE300".

`velometer report charts` writes `docs/review/m4_headline.png`, `m4_tiers.png` and `m4_rankings.png`, plus their `.vl.json` specs. Every chart carries the ODbL attribution and "OSM mapped km (ADR 0006)".

### 4.3 CSV

- `/data/all.csv` and `/data/{city}.csv` (also `velometer report csv`) have one row per (city, boundary kind, label), where the label is a year or `current`. Columns:
  - `city_id, boundary_kind, label, run_id, osm_timestamp, classifier_version, config_sha256`;
  - `tier_A_km … tier_E_km` (per side), `ab_km`;
  - `ours_headline, ecf_qecio, clean_cities_2025` (values on each preset's reported basis);
  - `population_value, population_year`;
  - `flags`.
- The first two lines are `#`-comments:
  - `# Map data © OpenStreetMap contributors, ODbL 1.0 — OSM mapped km, not built km`;
  - `# velometer <git commit> generated <UTC timestamp>`.
- No mapper data appears in the CSV.

### 4.4 Methodology (EN + DE)

- `velometer report methodology [--check]` renders both files from Jinja templates.
- The prose is hand-written in the templates, once per language.
- The facts are generated:
  - the report classifier version and a rules table (id, tier, applies_to, match summary);
  - the parameters;
  - per city: boundary kinds, OSM timestamps (current and history), the history set and population;
  - the presets, with numerator and denominator;
  - the snapshot dates;
  - the flag rules and thresholds from `activity.yaml`;
  - the known limitations from `config/limitations.yaml`, in the language of the file.
- `--check` re-renders in memory and fails when either file differs from the committed text. It also fails when a limitation lacks `en` or `de` text.
- The initial limitations list:
  - mapped km, not built km;
  - population 2024 held constant;
  - FUA has no per-100k figure;
  - no `width` or `surface` quality;
  - classifier gaps are excluded, not counted;
  - Clean Cities and QECIO scope differences;
  - `-dirty` provenance on M3 runs;
  - the history file date versus the current run date.

### 4.5 Tier maps

- `velometer report maps [--city X]` reads the current run's snapshot (the path is recorded by the run) and classifies it with the report classifier.
- It plots the sides by tier, with the A–E colours from the M3 chart and `excluded` and untiered sides omitted. It draws the boundary outline in the city EPSG.
- Output: `data/maps/<city>_<kind>.png`, rebuilt when the run id changes.
- The PNG carries the ODbL attribution and the run's OSM timestamp.
- It is never committed: it is data-sized and regenerable.

### 4.6 App

- `velometer serve [--host 127.0.0.1] [--port 8000]`:
  - refuses any host other than a loopback address, with exit 2;
  - exits 1 when the DB is missing.
- `create_app(db_path, config_dir, maps_dir)` opens SQLite with `mode=ro` per request.
- Routes:

  | Route | Content |
  |---|---|
  | `GET /` | city table (current headline, A+B km, presets, flags count); `headline_over_time`; `rankings_flip`; links to cities |
  | `GET /city/{id}` | presets and per-100k; `tier_composition`; LAU vs FUA; flagged years with explanation text from `docs/review/m3_timeseries.md`; reconcile rows (ours vs Clean Cities, QECIO, BikeNetKit, official); tier map image; provenance (run ids, OSM timestamp, classifier, config sha[:12], history set) |
  | `GET /methodology` | renders `docs/methodology.md`, with a link to `/methodology/de` |
  | `GET /maps/{city}_{kind}.png` | from `maps_dir`, or 404 |
  | `GET /data/all.csv`, `GET /data/{city}.csv` | the CSV of §4.3 |
  | `GET /static/...` | the vendored JS and CSS |

- An unknown city returns 404. A city with no run for a kind shows "no run" in that section and never returns a 500. A missing map shows "map not generated (`velometer report maps`)".
- Pages carry the ODbL attribution and "mapped km" in the footer.

### 4.7 Dependencies

- Runtime: `fastapi`, `uvicorn`, `jinja2`, `altair`, `vl-convert-python`, `markdown`.
- `matplotlib` moves from dev to runtime, because the maps need it.
- JS: `vega`, `vega-lite` and `vega-embed` minified bundles at pinned versions. Each is committed with its licence (BSD-3) in `app/static/vendor/`.

## 5. Testing

- Everything is offline and fast. Real-data checks happen only in the execution task.
- Schema v6:
  - migrate a v5 copy, check that `activity` rows carry the expected sha and that runs are untouched;
  - run the migration twice to show it is idempotent;
  - an interrupted migration leaves v5.
- Identity:
  - changing `activity.yaml` changes `config_sha256`;
  - a rerun creates new runs, and the old runs are no longer selected.
- FUA current: with fake region fetches, a two-region boundary merges, records the set md5 and its regions in `history_sets`, and finishes as `source='current'`. A boundary with no covering set still hits the R18 guard.
- Report classifier: reconcile, timeseries and app all default to `config/report.yaml`. This is red-proofed by changing the file in a copied config dir.
- Charts:
  - each builder's spec contains the expected data rows and encodings for a hand-built series;
  - the rankings rank is correct, including ties;
  - PNG export produces a non-empty PNG.
- CSV: the header comments and the columns are present; there are no `uid` or `user` columns; values match the DB for a fixture run.
- Methodology:
  - `--check` fails when a generated fact changes or a limitation lacks a language;
  - both files contain the classifier version and every city's OSM timestamp.
- App (TestClient on a fixture DB built with the M3 fakes):
  - every route returns 200;
  - an unknown city returns 404;
  - no-run sections render;
  - `serve` refuses `--host 0.0.0.0`;
  - the HTML references only `/static/` scripts, with no `http(s)://` script sources.
- Maps: on a tiny snapshot fixture, a PNG is written with the expected size, and it is rebuilt only when the run id changes.

## 6. Execution (last task, most capable model)

1. Back up the DB.
2. Migrate to v6.
3. Rerun all 70 runs.
4. Regenerate the M3 report and re-check its explanations.
5. Regenerate the reconcile report and re-check its explanations.
6. Build the charts, maps and methodology, and view every PNG.
7. Start `velometer serve` and open every page in the browser. For each page, check:
   - the numbers against the CLI output;
   - that no external requests are made, using the network log.
8. The three `--check`s (`reconcile`, `timeseries`, `report methodology`) exit 0, and the gate is green.

## 7. Out of scope

- Public hosting, authentication, deployment, a German app UI, basemap tiles, interactive maps, classifier v3, and new cities (M5).
