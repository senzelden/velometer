# M3 execution rulings

Decisions made while building M3, each with why and what it costs if wrong. The M3 spec and the ADRs win where they differ.

- **R1** The `fetch_history` `cookie_loader` is `(force: bool = False) -> Cookie`. The default binds `load_or_login(data_dir, client=…)`. Why: the plan's signatures disagreed. Cost: none.
- **R2** Test helpers may be adapted to real APIs, but stated assertions may not be weakened (as M2 R1).
- **R3** The current point's activity is stored as `ActivityYear.year = last + 1` and labelled "current". Cost: a confusing year value in raw rows.
- **R4** The commit trailer carries the implementing agent's own model id.
- **R5** `regions_for`:
  - uses no buffer;
  - tolerates a gap of max(0.1% of area, 1 km²) in EPSG:3035;
  - prefers the smallest single covering leaf, otherwise drops greedily, largest first;
  - records `uncovered_km2`.

  Cost if wrong: a sliver of at most 1 km² is missed, and it is recorded.
- **R6** Aggregate leaves (e.g. `dach`) are chosen only as the smallest single cover. None was chosen for the pilot cities.
- **R7** Superseded by R11.
- **R8** Spec §2.6 provenance lives in a new additive v5 table `history_sets`:
  - regions with md5, md5 source and fetch date;
  - index path and sha256;
  - `uncovered_km2`, which is also a per-run diagnostic.

  Why: `diagnostics` is float-only and `data/` is not durable.
- **R9** The current-point activity window is the standard window for year last + 1. It ends where the history file ends.
- **R10** The slow history test caches downloads in the repo `data/`, so the ~411 MB Berlin file is fetched once.
- **R11** `unrecognised_cycling_km` follows spec §14 literally. It counts only road sides that have no tier or an unknown cycleway value and that carry cycling tags. Why: the plan generalised it to all sides, and on Berlin 2018 that counted 5,305 km, mostly plain footways and paths. Under the spec rule it is 7.8 km. Cost: unmatched standalone ways are not surfaced here.
- **R12** Superseded by R19 (activity is always recomputed over the full range).
- **R13** The series uses, per city and kind, the most recently recorded history set that has done runs under the current classifier, parameters and config sha.
- **R14** The current point:
  - It is the latest done current run with identical classifier, parameters and config sha. If there is none, there is no current point.
  - `current_fraction` is the elapsed share of its year.
  - Only `min_km` and the spike threshold scale with it.
- **R15** Required boundary kinds per city are data in `config/history.yaml`: LAU for every city, plus FUA for Berlin and Paris. `--check` enforces them.
- **R16** No `activity_spike` is flagged when the 2018–2026 median of edits is 0.
- **R17** Superseded by R18.
- **R18** M3 has no FUA current point. The current-run path reads only the city's own extract, so it would store a city-only "FUA".
  - `run_city` now refuses any boundary that its region does not cover.
  - Current runs built from regions selected and merged with `regions_for` are deferred to M4.

  Cost: the FUA series end at 2026-01-01.
- **R19** Final-review fixes:
  - Activity always covers the `history.yaml` years plus last + 1.
  - `--check` requires every year, and change rules never span a gap.
  - A cached history file is reused when its md5 matches the published one.
  - `config/activity.yaml` enters run identity only through the report marker (`activity=<sha12>`), and `--check` fails when it changes. Full run-key identity is deferred to M4, because it would invalidate all 68 runs.
  - Accepted, not fixed: history runs record a `-dirty` commit, because docs and scripts were uncommitted while they ran.
- **DB housekeeping:** the real DB was migrated v4 → v5 by Task 9. The v4 copy is kept at `data/velometer-pre-v5.sqlite`.

## Decided after M3 (user, 2026-10-02)
- `tag_drift` gains a km floor, `tag_drift_min_km: 5` in `config/activity.yaml`, scaled like
  `km_jump_min_km` for the current point. It removed 18 flags, all moves of under 5 km; 16
  flagged city-years remain, each explained.
- Classifier v2 (`config/classifier/v2.yaml`) recognises the M3 gaps without counting them:
  `use_sidepath`, `shoulder`, `crossing`, untyped `yes` (all excluded under their own subtype),
  and splits values on `,` as well as `;`. v1 is unchanged; published M3 numbers stay on v1.

## Parked
- The Geofabrik cookie jar also matches subdomains.
- Every current run needs the public Geofabrik index (cached daily).
- A `--years` range outside `history.yaml` gets no activity.
