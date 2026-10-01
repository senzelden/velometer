# 0005 — Annual 1 January snapshots, frozen versioned classifier

- Status: accepted
- Date: 2026-10-01

## Decision

- Snapshots are taken at **1 January 00:00 UTC for each year from 2018 to 2026**, from OSM full history, plus one "current" snapshot.
- The full-history source is Geofabrik internal extracts, filtered with `osmium time-filter`. The legacy ohsome API is decommissioned at the end of November 2026, so we don't build on it.
- The classifier is versioned (`config/classifier/vN.yaml`). A run freezes one version.
- Every output row carries `classifier_version` and `osm_timestamp`.
- Runs are idempotent. A (city, date, boundary_kind, classifier_version) tuple that already has a completed `Run` is skipped.

## Consequences

- A rule change never silently rewrites history. It is a new version, and its runs sit next to the old ones.
- The classifier has to handle legacy tagging (`cycleway=opposite_*`, `sidewalk:*:bicycle`), because the 2018 data predates `cycleway:both` and `*:separation`.

## Notes (M3 as run)

Run on 2026-10-01 (local evening, UTC+2), classifier `v1`, config `68162f5aebe8`, one machine,
Geofabrik internal-server history files dated 2026-10-01. 68 history runs (7 city/boundary
series × 9 years, 2018–2026), all `done`, none failed or retried.

Region sets per boundary (`regions_for`, ruling R5) and `uncovered_km2` per history set:

| city/boundary | regions | history set | uncovered km² |
|---|---|---|---:|
| berlin/lau | berlin | `c3335f42` | 0.0 |
| berlin/fua | brandenburg (its extract covers Berlin too: uncovered 0) | `1308e2c9` | 0.0 |
| paris/lau | ile-de-france | `7db1f306` | 0.0 |
| paris/fua | bourgogne, centre, champagne-ardenne, haute-normandie, ile-de-france, picardie | `df7be7ff` | 0.0 |
| vienna/lau | austria | `1254c077` | 0.0 |
| copenhagen/lau | denmark | `be41de5b` | 0.0 |
| wroclaw/lau | dolnoslaskie | `fda036ca` | 0.0 |

Full-history downloads (`.osh.pbf`, md5 published by Geofabrik for every file): berlin 412 MB,
brandenburg 871 MB, ile-de-france 763 MB, bourgogne 391 MB, centre 452 MB, champagne-ardenne
217 MB, haute-normandie 224 MB, picardie 273 MB, austria 1,925 MB, denmark 1,083 MB,
dolnoslaskie 621 MB; 7.2 GB in total. On disk afterwards: `data/history` 9.0 GB (downloads plus
the per-city clipped histories, 45 MB Copenhagen to 852 MB Paris FUA) and `data/snapshots` 6.0 GB
(one clipped `.osm.pbf` per city, boundary and year).

Wall-clock timings:

| step | wall clock | per year (mean, min–max) |
|---|---:|---|
| `run --years 2018-2026`, berlin lau (history already cached) | 311 s | 30 s (15–53) |
| same, copenhagen lau (incl. denmark download) | 159 s | 4 s (2–5) |
| same, wroclaw lau (incl. dolnoslaskie download) | 159 s | 9 s (7–11) |
| same, paris lau (incl. ile-de-france download) | 160 s | 8 s (5–12) |
| same, vienna lau (incl. austria download, alongside the FUA downloads) | 490 s | 12 s (9–15) |
| `osm fetch-history --city berlin --boundary fua` (brandenburg) | 157 s | |
| `osm fetch-history --city paris --boundary fua` (5 new regions) | 220 s | |
| `run --years 2018-2026 --boundary fua`, berlin | 592 s | 56 s (35–88) |
| same, paris (6-region history) | 1,040 s | 98 s (71–130) |

The whole M3 execution (downloads and runs) took about 55 minutes of wall clock. Per-year time
grows with the size of the clipped area: Copenhagen 4 s, Paris FUA 98 s.

FUA series have no current point: `velometer run --boundary fua` (the current-run path) reads
the city's single `geofabrik_region` extract, which covers neither the Berlin nor the Paris FUA,
so it was not run (see the M3 Task 9 report for the open decision).
