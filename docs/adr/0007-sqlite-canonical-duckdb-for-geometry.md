# 0007 — SQLite is canonical state; DuckDB (+spatial) for heavy geometry

- Status: accepted
- Date: 2026-10-01

## Decision

- **SQLite (`velometer.sqlite`) is the canonical store.** It holds cities, boundary metadata, runs, results, external and official figures, duplicates and provenance, as a plain-SQL schema mirroring the Pydantic models. No ORM.
- **DuckDB with the `spatial` extension over Parquet** handles heavy geometry work at city and history scale. Results are written back to SQLite.

## Notes (2026-10-01)

For M1, fixture-scale geometry (duplicate and dual-carriageway detection) uses shapely behind pure functions. DuckDB is added in M2, when city-scale data first needs it. Its interface stays the same: way-sides in, flagged pairs out.
