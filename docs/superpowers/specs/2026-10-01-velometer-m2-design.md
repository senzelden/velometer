# velometer M2 design: current snapshot for 5 pilot cities, persisted runs, reconcile

- Date: 2026-10-01
- Scope: handover milestone M2. M3 (history), M4 (report/app) and M5 (scale) get their own specs.
- Inputs: `HANDOVER.md` §6–§10; ADRs 0001–0008; M0/M1 spec §9 "As built"; `docs/superpowers/rulings-m0-m1.md`; `docs/research/m2-data-sources-2026-10-01.md` (verified URLs and fields, retrieved 2026-10-01).

## 1. Intent

**Outcome:** for Berlin, Paris, Vienna, Copenhagen and Wrocław, a persisted, reproducible current-snapshot run on the LAU boundary. It produces:
- tier lengths;
- road lengths;
- all three presets;
- completeness diagnostics;
- a reconciliation against published figures, in which every gap over 20% has a written explanation.

**Handover acceptance (M2):**
- a results table per city;
- `reconcile` output comparing ours against Clean Cities 2025, QECIO v2.10 (Berlin NUTS3 at minimum) and BikeNetKit;
- every gap >20% explained in `docs/reconciliation.md`.

**Done means:**
- `velometer run --cities all` reproduces the table from a clean `data/` directory (network required).
- `velometer reconcile --check` passes.
- The gate is green.
- Results are rendered as a chart and reviewed.

## 2. Decisions

### Taken with the user on 2026-10-01
1. **osmium-tool** (apt) is used for clipping now (`osmium extract`). M3 reuses it for `time-filter`.
2. **Lengths are clipped exactly at the boundary polygon.** A way crossing the boundary counts only its inside part. This applies to numerators and denominators alike.
3. **BikeNetKit:** only `bike_networks.zip` and `boundaries.zip` (about 163 MB) are downloaded.
4. M2 runs on classifier v1 now. The Berlin golden sign-off happens in parallel, and a rule change becomes v2 plus a rerun.

### Taken from the source research (they correct the handover)
5. **LAU** comes from GISCO `LAU_RG_01M_2024_3035.gpkg`, selected by `GISCO_ID`:
   | City | GISCO_ID |
   |---|---|
   | Berlin | DE_11000000 |
   | Paris | FR_75056 |
   | Vienna | AT_90001 |
   | Copenhagen | DK_101 |
   | Wrocław | PL_1003021056401 |

   `cities.yaml.lau_code` stores the GISCO_ID.
6. **FUA** comes from GISCO URAU 2024 (`URAU_RG_100K_2024_3035_FUA.gpkg`). Codes:
   | City | FUA code |
   |---|---|
   | Berlin | DE001F |
   | Paris | FR001F |
   | Vienna | AT001F |
   | Copenhagen | DK001F |
   | Wrocław | PL004F |

   The handover's `DE001L1` is the retired scheme. FUA polygons are fetched and stored in M2; FUA *runs* are M3 acceptance.
7. **Population (per-100k metric).** LAU `POP_2024` is 0 for all French LAUs. The rule:
   - Use LAU `POP_2024`.
   - If it is 0 or missing, use Eurostat `demo_r_pjangrp3` (total, 2024) for the NUTS3 unit that is identical to the commune. For Paris that is FR101.
   - Store the source and year with the value.
   - Berlin's LAU (3,782,202, census-based) and NUTS3 (3,662,381, register) figures differ. The LAU value is used for every city with a non-zero LAU value, documented in ADR 0004.
8. **Geofabrik:** use the dated extract URLs (`<region>-YYMMDD.osm.pbf`), resolved from `-latest` by redirect, and verify against `.md5`. The run's `osm_timestamp` is read from the PBF header (`osmosis_replication_timestamp`), not from `state.txt`. Vienna is clipped from the Austria extract, because Geofabrik has no Wien sub-region.
9. **QECIO comparability.** QECIO rows are NUTS3 units:
   | City | NUTS3 | Same area as the LAU? |
   |---|---|---|
   | Berlin | DE300 | yes |
   | Paris | FR101 | yes |
   | Vienna | AT130 | yes |
   | Wrocław | PL514 | yes |
   | Copenhagen | DK011 | no: "Byen København" adds Frederiksberg, Dragør and Tårnby |

   The Copenhagen comparison is reported but tagged `boundary_mismatch`. QECIO data is from January 2024, and the reconcile row carries that date.
10. **Clean Cities 2025**, Table 5 of the 2025-05-14 report, stored as external figures:
    | City | Protected km | Network km | Ratio |
    |---|---|---|---|
    | Paris | 822 | 1,700 | 48% |
    | Copenhagen | 397 | 926 | 43% |
    | Wrocław | 355 | 1,769 | 20% |
    | Berlin | 925 | 5,350 | 17% |
    | Vienna | 384 | 2,844 | 14% |

    Vienna also has a July 2025 web correction: 625.1 km of 2,844 km (22.0%), which adds traffic-calmed streets and so is not like-for-like. Its rows carry `reference_date` 2025-07-17 (the page's modified date; the correction's own date is not published). Both rows are stored, with notes. Whether each city's figure is city-submitted or OSM is not stated per city, so the note field says so.
11. **BikeNetKit's "bike network"** includes living streets and cycle streets, so it is wider than "protected". It is compared against our `A+B+E` sum (BikeNetKit has no lanes; research §7, Ruling R10, amended in the final fix dispatch), not the headline. Its boundaries are OSM/Nominatim polygons, which differ from LAU. The snapshot date is "summer 2026" (unverified), and the row carries that note.
12. **Scale engine.** shapely with STRtree stays the engine. DuckDB is introduced only if a full Berlin `classify` takes more than 10 minutes or more than 8 GB RSS on this machine. The measurement is recorded in ADR 0007 either way.

## 3. Units and interfaces

All network access sits in `src/velometer/sources/*`. All subprocess calls to `osmium` sit in `src/velometer/osmium.py`. Pipeline stages stay pure.

### `osmium.py`
Thin wrappers that raise `OsmiumError` with stderr on a non-zero exit:
- `require_osmium() -> str` gives the version. Its error message says `sudo apt install osmium-tool`.
- `extract(src, polygon_geojson, dst, strategy="smart")`.
- `fileinfo_timestamp(path) -> datetime | None` reads the header `osmosis_replication_timestamp`.
- `relation_polygon(src, relation_id, dst_geojson)` uses `getid -r` + `export`, for the OSM admin fallback.

### `sources/download.py`
`fetch(url, dst, md5_url=None) -> Path` handles:
- a streaming download to a `.part` file, then an atomic rename;
- md5 verification;
- skipping if `dst` exists and its md5 matches;
- the User-Agent `velometer/<version>`, with the contact from `VELOMETER_CONTACT` appended only if set.

Retries are bounded (3) with back-off.

### `sources/geofabrik.py`
- `resolve_dated(region) -> (url, md5_url)` follows the `-latest` redirect to the dated file.
- `fetch_region(region, data_dir) -> RegionFile(path, url, md5, osm_timestamp)`.

### `sources/boundaries.py`
- `fetch_gisco(data_dir)` downloads the LAU and FUA gpkg files, once, cached.
- `city_boundary(city, kind, data_dir) -> BoundaryRecord`:
  - selects the polygon by code;
  - reprojects to EPSG:4326 GeoJSON for osmium, and keeps the city-EPSG polygon for measuring;
  - writes `data/boundaries/<city>_<kind>.geojson`;
  - computes `area_km2` in the city EPSG and the file sha256.

  GeoPackages are read with `pyogrio` + `shapely` (a new dependency; pyogrio ships GDAL wheels). No geopandas.
- `osm_admin` fallback: `osmium.relation_polygon` on the city's Geofabrik extract.
- `population(city, lau_row) -> Population`, following §2.7. The Eurostat fallback goes through the Eurostat JSON API, `demo_r_pjangrp3`.

### `pipeline/extract.py`
`snapshot(region_file, boundary, data_dir) -> Path` calls `osmium extract` with the strategy `smart` and writes `data/snapshots/<city>_<kind>_<YYYYMMDD>.osm.pbf`. The output is cached by (region md5, boundary sha256).

### `pipeline/read.py` (change)
- Only ways with a `highway` tag are kept (a Python-side filter, parked from M1).
- `read_ways` stays a pure reader.

### `pipeline/measure.py` (change)
`measure(ways, cfg, epsg, boundary=None)`:
- When `boundary` (a shapely polygon in the city EPSG) is given, each way's length is the length of `line ∩ boundary`. A prepared polygon is used, with a `contains` fast path.
- Dedupe and dual-carriageway pairing still use the full geometry; only lengths are clipped.
- `MeasureResult` gains `completeness: list[Completeness]`. Per tier A–E it holds the length-weighted share of way-sides that carry:
  - width: `cycleway:width` or `width`;
  - surface: `cycleway:surface` or `surface`;
  - segregation (B only): `segregated` or `cycleway:segregated`.

### `db.py` (schema v2)
- **Migration and guard:**
  - `create_schema` refuses with a `SchemaError` when `user_version > SCHEMA_VERSION`.
  - When it is lower, it applies the ordered migrations.
  - v1→v2 recreates the empty result tables. It refuses if any v1 result rows exist, since none were ever written.
- **`runs` gains:**
  - `city_id REFERENCES cities`;
  - `boundary_sha256`;
  - `classifier_parameters` (canonical JSON);
  - `region_md5`;
  - `finished_at`;
  - a `UNIQUE(city_id, osm_timestamp, boundary_kind, boundary_sha256, classifier_version, classifier_parameters)` constraint over status `done`, enforced by the run logic (see below).
- **Result tables:**
  - They get `REFERENCES cities(id)`.
  - Unique keys are added for `tier_lengths(run_id, city_id, tier, subtype, length_basis)` and `duplicates(run_id, kind, way_id_separate, way_id_road, side)`.
  - `metrics` gains `per_100k` (nullable; km of the preset numerator per 100k residents).
- **Repository:**
  - `start_run(...) -> int`, `finish_run(id)`, `fail_run(id, error)`;
  - `find_done_run(key) -> int | None`;
  - `write_result(run_id, city_id, MeasureResult, metrics)`, in one transaction;
  - `upsert_boundary` and `upsert_external_figures`.
- Every connection is used as a context manager.
- **Schema v3 (Ruling R12, final fix dispatch):** an additive migration (`ALTER TABLE ADD COLUMN`) adds `runs.population_value/year/source`, written at run start, and `runs.config_sha256` (sha256 of the classifier YAML bytes followed by `presets.yaml` bytes). `config_sha256` is part of the run key and the done-run unique index; pre-v3 runs keep NULL and are never reused.

### `run.py` (orchestration)
`run_city(city, boundary_kind="lau", classifier="v1", force=False) -> RunOutcome` chains these steps:
1. fetch the region;
2. get the boundary;
3. take the snapshot;
4. `read_ways`;
5. `measure` with the boundary;
6. `compute_metrics`;
7. persist.

A completed run with the same key is skipped unless `force`. A failure marks the run `failed` with its error and continues with the next city.

### `sources/external.py`
- `config/external/figures.csv` is versioned and curated by hand. Its columns are the `ExternalFigure` fields. It holds:
  - Clean Cities 2025 (all five, plus the Vienna corrected row);
  - Berlin's four 2025 figures from handover pitfall 5 (21.2, 20.5, 17.3, 25.2 km), each with `network_scope` and `length_basis` as the handover states;
  - a `note` "per handover research 27 Sep 2026; re-verify before publication" where no primary URL is known.
- `load_qecio(data_dir)` downloads `Summary-all.csv` and emits `qecio_v2_10` rows for each pilot NUTS3: main roads km, tracks, lanes, shared pedestrian, and total cycle infrastructure km.
- `load_bikenetkit(data_dir)` downloads the two zips, md5 per Zenodo. For each pilot city, `bike_networks/<cityid>.gpkg` gives the total network km, measured in the city EPSG. It emits `bikenetkit_v1` rows plus their boundary area (km²) for context.

### `reconcile.py`
`reconcile(city, conn) -> list[Gap]`. Each `Gap` pairs our value from the latest done LAU run with one external figure, through a declared comparison map in `config/reconcile.yaml`:
| Comparison id | External figure | Our value |
|---|---|---|
| `cc_ratio` | Clean Cities ratio | `clean_cities_2025` preset value |
| `cc_km` | Clean Cities km | A+B per_side km |
| `cc_network_km` | Clean Cities network km | `all_public` road km |
| `qecio_main_km` | QECIO main roads km | `main_incl_motorway_raw` |
| `qecio_tracks_km` | QECIO tracks km | A + B[segregated=yes], qecio_weighted |
| `qecio_lanes_km` | QECIO lanes km | C + D, qecio_weighted |
| `qecio_total_km` | QECIO total cycle infrastructure | A+B+C+D, qecio_weighted |
| `bnk_network_km` | BikeNetKit network km | A+B+E, per_side (BikeNetKit has no lanes, R10) |
| `official_*` | Berlin official figures | listed, never flagged: they measure new km per year, not stock |

- `gap_pct = (ours − theirs) / theirs`.
- `flag = |gap_pct| > 0.20` and the comparison is not `informational`.
- Mismatch tags (`boundary_mismatch`, `definition_mismatch`, `date_gap`) come from the map and the data dates.
- `scope_mismatch` is added by the code when an external row's `network_scope` is not like-for-like (e.g. Vienna's `incl_traffic_calmed_restricted_access` web correction); that row keeps its own key `<city>/<id>@<scope>` and is still flagged and explained like any other.

### `docs/reconciliation.md`
- Generated tables sit between `<!-- reconcile:begin -->` / `<!-- reconcile:end -->`.
- Hand-written explanations sit under `### <city>/<comparison id>` headings.
- `velometer reconcile --write` rewrites only the generated block.
- `velometer reconcile --check` exits 1 when a flagged gap has no explanation heading.
- Final fix dispatch (R13, I7): each city's generated block starts with a provenance line (run, OSM timestamp, classifier and parameters, config sha, commit, boundary sha, `retrieved_at` per source). The explanations carry `<!-- explained-against: city=run_id ... -->`, and `--check` also exits 1 when a city's latest run differs from it, or when a comparison marked `required` in `config/reconcile.yaml` (`cc_ratio`, `qecio_main_km`, `bnk_network_km`) has no external row for a city with a run. It warns about headings that match no flagged gap.
- Task 10 (Clean Cities basis): `config/presets.yaml` has a `parameters.clean_cities_basis` (default `per_side`, ADR 0003); a preset with `basis: {parameter: clean_cities_basis}` is computed on both bases (schema v4: `metrics` is keyed by `(run_id, city_id, preset, length_basis)`), `reconcile.yaml`'s `cc_km` uses the same parameter, and `results`, `reconcile` and `classify` take `--clean-cities-basis` for reporting only. Comparisons that depend on it also emit an informational `<city>/<id>~<other basis>` gap, never flagged and never part of `--check`. Reports cover the runs of the config on disk (`config_sha256`).

### CLI additions
```
velometer boundaries fetch [--city X]
velometer osm fetch [--city X]
velometer classify --city X [--boundary lau|fua|osm_admin] [--force]   # persisted
velometer classify --file F --epsg N                                    # M1 mode, unchanged
velometer run --cities all|x,y [--boundary lau] [--force]
velometer external load [--qecio] [--bikenetkit] [--figures PATH]
velometer reconcile [--city X] [--write] [--check]
velometer results [--boundary lau]        # the per-city results table
```

## 4. Testing

- **Unit (default pass, no network, no osmium):**
  - clipped length: a line half inside a polygon gives half its length;
  - completeness shares;
  - schema v1→v2 migration and the guard;
  - run idempotency against a temp DB with a stubbed pipeline;
  - the reconcile gap math and `--check` on a fixture markdown;
  - the figures.csv schema (every row validates; every `source_url` is non-empty or the note says "re-verify");
  - the QECIO and BikeNetKit parsers on tiny fixture files (a CSV with the real header and 2 rows; a 3-feature gpkg written in the test);
  - the population fallback rule;
  - md5 and download resume logic against a local file:// or stub transport.
- **osmium-dependent:** `@pytest.mark.skipif(shutil.which("osmium") is None, reason="osmium-tool not installed")` runs extract and fileinfo on a tiny fixture PBF made with pyosmium in the test. These tests are visible as skips in CI, not silent.
- **Network/integration:** `@pytest.mark.slow`, deselected by default. One end-to-end Berlin run.
- **Guards assert the rule:**
  - the clipped-length test fails if clipping is removed;
  - the `--check` test fails if one explanation heading is deleted;
  - the migration test fails if the guard is removed.

## 5. Execution (after the code lands)

1. `velometer boundaries fetch`, `osm fetch`, `external load --qecio --bikenetkit`, then `run --cities all`. This needs about 2 GB of downloads.
2. Time and record the Berlin run (§2.12).
3. `velometer results` gives the table. Render a chart in `docs/review/m2_results.png` (headline value per city, the tier composition stacked bars, the three presets side by side) and look at it.
4. `reconcile --write`. Investigate each flagged gap with evidence: boundary areas, definitions, data dates, sample ways. Write each explanation. Then `reconcile --check`.

## 6. Out of scope

- History snapshots and changeset activity (M3).
- FUA runs (M3; fetched only).
- The app and generated methodology (M4).
- The 16 further cities (M5).
- Classifier v2: only if the golden review demands it.
