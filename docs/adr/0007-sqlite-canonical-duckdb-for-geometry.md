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
