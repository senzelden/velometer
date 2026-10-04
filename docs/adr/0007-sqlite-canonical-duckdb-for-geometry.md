# 0007 — SQLite is canonical state; DuckDB (+spatial) for heavy geometry

- Status: accepted
- Date: 2026-10-01

## Decision

- **SQLite (`velometer.sqlite`) is the canonical store.** It holds cities, boundary metadata, runs, results, external and official figures, duplicates and provenance, as a plain-SQL schema mirroring the Pydantic models. No ORM.
- **DuckDB with the `spatial` extension over Parquet** handles heavy geometry work at city and history scale. Results are written back to SQLite.

## Notes (2026-10-01)

For M1, fixture-scale geometry (duplicate and dual-carriageway detection) uses shapely behind pure functions. DuckDB is added in M2, when city-scale data first needs it. Its interface stays the same: way-sides in, flagged pairs out.

## Notes (M2 measurement)

Measured on 2026-10-01 with `/usr/bin/time -v uv run velometer classify --city berlin` (run 1:
GISCO LAU 2024 boundary, Geofabrik `berlin-260930.osm.pbf`, OSM timestamp 2026-09-30T20:22:42Z,
classifier v1, commit 2e90435):

- Wall time: **4:54** (294 s). User CPU 176.9 s; CPU share 60%. The run row itself spans
  168 s (`started_at` 16:25:12 to `finished_at` 16:28:00 UTC); the rest is resolving the
  Geofabrik file and its md5 over a flaky mirror (and, for part of the time, other regions
  downloading in parallel), not geometry work.
- Max RSS: **4,079,832 kB (3.9 GiB)**.
- Ways: 1,282,391 ways in the clipped LAU snapshot, of which 458,256 are `highway=*` ways read
  and classified.

Both are under the thresholds (10 min, 8 GB): **DuckDB not needed at city scale.** Shapely
behind pure functions stays the geometry engine for city runs; revisit for FUA or history runs.

## M5 notes (2026-10-03)

M5 ran all 21 cities (current LAU and FUA runs, and the 2018–2026 history on both boundaries)
under a memory gate: a run with `peak_rss_kb` above 8 GB (8 × 2²⁰ kB) would have made streaming
classification (plan Task 12) due. **The gate was not tripped, so streaming was not built.**
Shapely behind pure functions stays the geometry engine; DuckDB is still not needed.

How peaks are measured: `runs.peak_rss_kb` (schema v7) comes from `PeakRss`, which samples the
process RSS every 0.2 s inside the run block, with samples on entry and exit. Two caveats:

- It is a **lower bound** when one C call holds the GIL for a long time, because the sampler
  thread cannot run then. Python loops yield every 5 ms, so this only matters inside a single
  long C call.
- It is **process-wide**: in a multi-city invocation a later run's peak includes memory still
  held from earlier runs in the same process.

Cross-check: `/usr/bin/time -v` on a lone Paris FUA current run (run 312) gave a maximum RSS of
3,384,384 kB against `peak_rss_kb` 3,387,384 kB, within 0.1 %.

Peak per city, in GB (kB / 2²⁰), over the done classifier-v3 runs (current runs 270–312,
history runs 314–691), sorted by the current FUA peak:

| city | LAU current | FUA current | LAU history (max of 9) | FUA history (max of 9) |
|---|---:|---:|---:|---:|
| paris | 0.77 | 3.23 | 0.97 | **4.86** |
| berlin | 1.68 | 2.55 | 2.43 | 3.69 |
| warsaw | 1.14 | 1.93 | 1.45 | 2.63 |
| helsinki | 0.83 | 1.80 | 0.97 | 2.41 |
| vienna | 0.81 | 1.78 | 0.98 | 2.46 |
| barcelona | 0.76 | 1.72 | 0.64 | 2.17 |
| madrid | 0.81 | 1.72 | 0.92 | 2.24 |
| krakow | 0.99 | 1.60 | 0.80 | 1.43 |
| lyon | 0.76 | 1.60 | 0.50 | 1.61 |
| copenhagen | 0.69 | 1.59 | 0.41 | 1.55 |
| oslo | 0.71 | 1.57 | 0.74 | 2.07 |
| amsterdam | 0.71 | 1.54 | 0.68 | 1.99 |
| ljubljana | 0.84 | 1.45 | 0.52 | 1.57 |
| prague | 0.91 | 1.45 | 1.03 | 1.62 |
| strasbourg | 0.69 | 1.44 | 0.38 | 0.83 |
| wroclaw | 0.72 | 1.42 | 0.75 | 1.09 |
| stockholm | 0.68 | 1.38 | 0.56 | 1.69 |
| budapest | 0.92 | 1.36 | 0.78 | 1.51 |
| bordeaux | 0.64 | 1.28 | 0.32 | 1.05 |
| bratislava | 0.81 | 1.23 | 0.61 | 0.94 |
| utrecht | 0.68 | 0.99 | 0.45 | 0.91 |

- **Largest current run:** Paris FUA, 3.26 GB in run 292 (superseded by run 312, 3.23 GB), about
  40 % of the gate. Paris FUA is also the largest FUA by area (18,159 km²).
- **Largest run of all:** Paris FUA history 2026-01-01 (run 511), 5,092,652 kB (4.86 GB), about
  61 % of the gate.
- **Largest LAU run:** Berlin, 1.68 GB current and 2.43 GB in history.
- **`report maps`:** all 42 maps (21 LAU, 21 FUA) in one process peaked at 3,078,604 kB (2.94 GB,
  `/usr/bin/time`), against M4's 2.3 GB for Berlin FUA alone. The M4 carry-over ("streaming
  classification for `report maps`") is therefore not due either.

Per-city wall clocks of the history runs are in ADR 0005's M5 notes and in
`docs/superpowers/rulings-m5.md`.
