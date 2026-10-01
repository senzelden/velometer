# velometer M3 design: history 2018–2026, activity diagnostics, FUA robustness

- Date: 2026-10-01
- Scope: handover milestone M3. M4 (report/app) and M5 (scale to 21 cities) get their own specs.
- Inputs:
  - `HANDOVER.md` §5, §10 (pitfalls 2 and 7), §13 M3;
  - ADRs 0001–0008, especially ADR 0005;
  - the M2 spec and `docs/superpowers/rulings-m2.md`;
  - the Geofabrik `index-v1.json` (retrieved 2026-10-01), whose `urls.history` lists an internal `.osh.pbf` for every region we need.

## 1. Intent

**Outcome:** a yearly time series of every M2 metric for the 5 pilot cities, one point per 1 January 00:00 UTC from 2018 to 2026, plus the M2 "current" point. Each city-year carries mapping-activity diagnostics, so that a jump in km can be read as a mapping campaign or as construction.

**Acceptance (HANDOVER §13 M3):**
- A time-series table for the 5 cities on LAU.
- Flagged years where a mapping-activity spike coincides with a km jump. Every flagged year has a written explanation, enforced by `timeseries --check`.
- FUA robustness runs for Berlin and Paris, covering every year.

**Success:**
- `velometer run --cities all --years 2018-2026` reproduces the table from the downloaded history files. The run is resumable and skips completed runs.
- Every number traces to its run row (the M2 provenance rules).
- No OSM credential is written to any file, and no mapper identity is stored.

## 2. Decisions

### Taken with the user on 2026-10-01

1. **FUA runs** for Berlin and Paris cover **every year** 2018–2026 plus current. Their regions are found automatically (§2.6).
2. **Population** for past years is **held at the 2024 value**, the same population row as M2. Every output that shows per-100k says "population 2024 held constant".
3. **Mapper data is kept as aggregates only:**
   - edit counts, distinct changesets and distinct mappers per city and year;
   - the share of edits made by the single most active mapper.
   
   OSM user ids and names are used in memory only and never written to the DB, files or logs.
4. **Credentials:**
   - The OSM account is stored in `pass` as `velometer/osm-username` (display name) and `velometer/osm-password`.
   - It is wired via direnv `use_pass` to `VELOMETER_OSM_USER` and `VELOMETER_OSM_PASSWORD`.
   - No settings file holds them.
5. **This design** was approved in chat on 2026-10-01.

### Technical

6. **Region selection.**
   - `regions_for(polygon)` intersects the boundary with the Geofabrik `index-v1.json` region geometries.
   - It picks the smallest set of leaf regions whose union covers the polygon, after a 1 km buffer.
   - An index snapshot is stored dated in `data/external/geofabrik/index-v1-YYYYMMDD.json`, and its sha256 is recorded in provenance.
   - LAU runs need one region each (berlin, ile-de-france, austria, denmark, dolnoslaskie).
   - Berlin's FUA (DE001F, 9,274 km²) needs berlin plus brandenburg.
   - Paris's FUA (FR001F, 18,172 km²) needs ile-de-france plus the neighbouring regions the intersection finds.
   - A test pins the rule (the chosen set covers the polygon and no chosen region is redundant), not today's set.
7. **Pipeline order: clip once, filter per date.**
   1. Each region history is fetched (§3).
   2. If more than one region is needed, `osmium merge` (history-aware) produces a merged file.
   3. `osmium extract --with-history -s complete_ways` with the boundary polygon produces one **city history** file per (city, boundary kind, history-set checksum). It keeps every version of anything that was ever inside the boundary.
   4. `osmium time-filter <city history> <date>` produces each snapshot.
   5. The M2 pipeline runs on the snapshot (read, classify, dedupe, measure, clipped to the same polygon).
8. **Dates and the current point.**
   - The dates are `YYYY-01-01T00:00:00Z` for YYYY from 2018 to 2026 (ADR 0005).
   - "Current" stays the M2 public-extract run.
   - A history run stores `osm_timestamp = <date>`.
   - The time series uses the latest current run, labelled with its own timestamp.
9. **Boundaries.** The GISCO 2024 LAU and FUA polygons are used for every year. None of the five municipalities changed boundaries between 2018 and 2026; if that turns out wrong, it is a documented limitation.
10. **Classifier.** `v1` is frozen for every year, with default parameters plus the presets' `clean_cities_basis` (ADR 0005, M2 R15). No rule changes in M3.
11. **Run key.**
    - The existing key fields are reused.
    - `osm_timestamp` is the snapshot date.
    - `region_md5` is the **history-set checksum**: the md5 of the sorted `region:md5` lines of the history files used.
    - A run also records `source = 'history' | 'current'`. This is schema v5, an additive column that defaults to `'current'` for existing rows.
    - Runs with different sources never share a key.
12. **Activity definition.** Computed from the city history file.
    - Cycling-relevant keys are listed in `config/activity.yaml`. The default list covers:
      - `highway` when its value is `cycleway|path|footway|pedestrian|living_street`;
      - `cycleway*`, `bicycle*`, `segregated`, `sidewalk:*:bicycle`, `bicycle_road`, `cyclestreet`, `oneway:bicycle`, `cycleway:*:separation*`, `cycleway:*:lane`.
    - A **cycling edit** in year Y is a way version with its timestamp in Y whose cycling-relevant tags differ from the previous version. This covers a new way with such tags, and a deletion of a way that had them.
    - Per (city, boundary kind, year) we store:
      - `n_edits`, `n_changesets` and `n_mappers`;
      - `top_mapper_share` (the largest single-uid share of `n_edits`);
      - `n_ways_created_cycling` and `n_ways_deleted_cycling`.
    - Edits are attributed to the year whose 1 January snapshot **follows** them. Year Y's activity is everything in [Y-1-01-01, Y-01-01), which explains the change from snapshot Y-1 to snapshot Y. For 2018 the window is 2017.
13. **Flag rules** (`config/activity.yaml`, thresholds are data):
    - `km_jump`: the headline numerator (A+B per_side km) changes by ≥ max(10%, 25 km) between consecutive snapshots.
    - `activity_spike`: `n_edits` ≥ 2× the city's median `n_edits` over 2018–2026.
    - `campaign_suspected` = `km_jump` and `activity_spike`.
    - `single_mapper` = `km_jump` and `top_mapper_share` ≥ 0.5.
    - `tag_drift`: legacy-only km (sides classified through legacy rules: `cycleway=opposite_*`, `sidewalk:*:bicycle`) or unrecognised cycling-tag km change by ≥ 50% year on year.
    - Any flag makes the city-year **flagged**. A flagged year needs an explanation.
    - 2018 is the first point, so it has no `km_jump` and cannot be flagged by the km rules; only `tag_drift` (against nothing) is skipped too.
    - The current point is compared with the 2026-01-01 snapshot. Its activity window is [2026-01-01, current `osm_timestamp`). Its thresholds are scaled by the window's share of a year.
14. **Tag-drift diagnostic.** `measure` already records `rule_id` per side. M3 adds two per-run aggregates:
    - `legacy_km`: the sum of sides whose rule is in a configured legacy-rule list;
    - `unrecognised_cycling_km`: road sides with a cycling-relevant key whose classification is `excluded/unknown`, or untiered.
    
    They are stored in a `diagnostics` table (run_id, key, value), which is generic so later diagnostics need no schema change.
15. **Performance.** Berlin's current run takes 168 s. Nine history runs per city at a similar cost is fine; DuckDB is still not needed (ADR 0007). Runs are sequential.

## 3. Units and interfaces

### `sources/geofabrik_auth.py` (new)

- `login(user, password, *, client) -> Cookie`:
  - It implements Geofabrik's documented OAuth cookie flow with httpx: get the authorisation URL from `…/get_cookie`, log in on openstreetmap.org, authorise, and receive the `gf_download_oauth` cookie. It is our own implementation, not a vendored copy.
  - Credentials come only from arguments, which the CLI reads from the environment.
  - On failure it raises `AuthError`, and the message never contains the password.
- `cookie_path(data_dir)` is `data/auth/geofabrik_cookie.json`, mode 0600, holding only the cookie and its expiry.
- `load_or_login(...)` reuses a cookie that hasn't expired and logs in again otherwise.
- Logging never prints the cookie value or the password.

### `sources/geofabrik.py` (extend)

- `HistoryFile(region, path, md5, fetched_at)`.
- `fetch_history(region, data_dir, *, cookie, client) -> HistoryFile`:
  - The URL comes from the stored index (`urls.history`).
  - It uses the published `.md5` if the server has one; Task 1 verifies this. If there is none, it computes the md5 after download and records "md5 computed locally".
  - The local name is `data/history/<region>_<YYYYMMDD>_<md5[:8]>.osh.pbf`.
- `regions_for(polygon_wgs84, index) -> list[str]` (§2.6).

### `osmium.py` (extend)

- `merge_history(srcs, dst)`.
- `extract_history(src, polygon, dst)`, with `--with-history -s complete_ways`.
- `time_filter(src, ts, dst)`.
- Each writes through a `.part` file plus an atomic replace, like `extract`.

### `pipeline/history.py` (new)

- `city_history(city, kind, history_files, boundary, data_dir) -> Path`. It caches by (city, kind, history-set checksum, boundary sha).
- `snapshot_at(city_history, date, data_dir) -> Path`. It caches by (city_history, date).

### `pipeline/activity.py` (new)

- `activity(city_history, years, cfg) -> list[ActivityYear]`.
  - It uses a pyosmium handler over way versions in id/version order (the history files are sorted) and compares cycling-relevant tags with the previous version.
  - uids are kept in memory only.
- `flags(series, cfg) -> list[Flag]`. It works on run results plus activity and is a pure function.

### `db.py` (schema v5)

- `runs.source`: an additive column, default `'current'`.
- `activity(city_id, boundary_kind, year, history_set_md5, n_edits, n_changesets, n_mappers, top_mapper_share, n_ways_created_cycling, n_ways_deleted_cycling)`, with PK (city_id, boundary_kind, year, history_set_md5).
- `diagnostics(run_id, key, value)`, with PK (run_id, key).
- Selection: a `timeseries_runs(conn, city, kind, config_sha, years)` helper returns one done run per year. History runs are selected by `osm_timestamp` date, and the current run is the latest `source='current'` run.

### `run.py` (extend)

- `run_city_year(conn, city, date, *, boundary_kind, ...)` follows the same pattern as `run_city`: `RunDeps` injection, `fail_run`, atomic `complete_run`, and per-year skip.
- `run_history(conn, city, years, ...)`:
  - it fetches region histories once;
  - builds the city history once;
  - then loops over the years;
  - computes activity once per city and kind, and writes it atomically.

### `timeseries.py` (new)

- `series(conn, city, kind) -> list[YearPoint]` (one per year plus current).
- `render_block(...)` writes the generated table between markers in `docs/review/m3_timeseries.md`.
- `missing_explanations(...)`: every flagged (city, kind, year) needs a `### <city>/<kind>/<year>` heading under `## Explanations`.
- An `explained-against` marker lists the run ids, as in reconcile (M2 R13).

### CLI

- `velometer auth check`: logs in and reports success or failure only.
- `velometer osm fetch-history --region R | --city C [--boundary lau|fua]`.
- `velometer run --cities ... --years 2018-2026 [--boundary lau|fua]`. Without `--years` it is the M2 current run.
- `velometer timeseries [--city ...] [--boundary lau|fua] [--write] [--check]`.

### Outputs

- `scripts/render_m3_timeseries.py` writes `docs/review/m3_timeseries.png`:
  - (a) the headline over time per city, with flagged years marked;
  - (b) small multiples of A–E per_side km per year for each city;
  - (c) LAU vs FUA headline for Berlin and Paris.

## 4. Testing

- **Offline (default pass):**
  - A tiny hand-written `.osh` history fixture: a few ways with versions in 2017, 2019 and 2021, including a deletion and a way that moves out of the boundary.
  - Tests cover:
    - `time_filter` results per date;
    - `extract_history` keeping the moved-out way;
    - activity counts per year, the year attribution (§2.12) and `top_mapper_share`;
    - the absence of any uid in the DB after a run.
  - Login flow: an httpx MockTransport for the whole OAuth dance, an expired-cookie relogin, and an AuthError whose message has no password.
  - `regions_for` against a synthetic index: it covers the polygon and contains no redundant region.
  - Flag rules, each threshold red-proofed.
  - The `timeseries --check` paths.
  - The schema v4→v5 migration with existing rows.
- **Slow (`@pytest.mark.slow`):**
  - a real `auth check`;
  - `fetch-history --region berlin` plus one 2018 snapshot run for Berlin, asserting rules: status done, osm_timestamp 2018-01-01, headline not None, tier km ≥ 0;
  - **pitfall 7:** the 2018 Berlin snapshot contains legacy-tagged ways, and they classify to a tier, not to unknown.
- **Red-proof** every new rule by breaking it.

## 5. Execution (after the code lands)

1. The user unlocks gpg so `pass` can decrypt. Then `auth check` must pass.
2. Fetch the histories for the 5 LAU regions plus the FUA regions, and record the sizes and times.
3. Run `run --cities all --years 2018-2026`, plus `--boundary fua --cities berlin,paris`.
4. Run `timeseries --write`, render the chart and view it.
5. Write an evidence-based explanation for each flagged year, citing:
   - activity numbers;
   - per-tier deltas;
   - tag-drift numbers;
   - a few example ways where useful.

   Classifier suspicions go into a list for the user. No rule is changed.
6. Run `timeseries --check` and `reconcile --check`; both must exit 0.

## 6. Out of scope

- New classifier versions; legacy-tag rule changes need a v2 and the user's sign-off.
- Yearly population, which is held constant per decision 2.
- Per-mapper attribution (decision 3).
- Official Berlin time-series comparison: methodology break, pitfall 4. That is M4 narrative.
- Scaling past 5 cities (M5).
- Deferred from M2: the atomic v1→v2 migration and an `--offline` mode. Carry them as M3 minors only if they are cheap; otherwise M4.
