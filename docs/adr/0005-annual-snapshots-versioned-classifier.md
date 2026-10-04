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
Geofabrik internal-server history files dated 2026-10-01. 63 history runs (7 city/boundary
series × 9 years, 2018–2026) plus the 5 M2 current runs (LAU only) make the 68 runs of the
chart; all `done`, none failed or retried.

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

## M5 notes (2026-10-03)

The decision stands. M5 added classifier **v3** (`config/classifier/v3.yaml`): v2 plus two
road-side rules that read `cycleway[:side]=soft_lane` and `cycleway[:side]=advisory` as tier D,
advisory (user decision 2026-10-03). As this ADR requires, it is a new version: v1 and v2 are
unchanged, the v2 runs stay in the DB, and v3 became the report classifier
(`config/report.yaml`). On the current snapshot v3 moves Prague +58.8 km into D, Bratislava
+0.56 km and Oslo +0.44 km; every other city, the five pilots included, changes by 0.0 km.

All runs are on schema v7, at OSM 2026-10-02T20:21:34Z (current) or 1 January 00:00 UTC
2018–2026 (history). The run set behind the report (classifier v3, all `done`, none `-dirty`):

| run set | runs | count | commit | note |
|---|---|---:|---|---|
| current LAU, 21 cities | 270–290 | 21 | fe3bfdc | wall 10:04, batch max RSS 1.80 GB |
| current FUA, 21 cities | 291–311, with Paris 312 | 21 | 15e0a06 | wall 20:17; 8 FUAs merge several Geofabrik regions, all `uncovered_km2` 0.0 |
| history LAU, 21 × 2018–2026 | 314–493, Vienna 683–691 | 189 | 9a545a2 (Berlin, Paris), 0b4e0f2 | |
| history FUA, 21 × 2018–2026 | 494–682 | 189 | 0b4e0f2 | |
| **total** | | **420** | | |

- **History:** 2 h 36 min of wall clock on 2026-10-03 (16:57–19:33 UTC), downloads included;
  16 GB of new Geofabrik full-history files. The per-city wall-clock table, history sets and
  region sets are in `docs/superpowers/rulings-m5.md` ("History run wall clock").
- **Commits:** 0b4e0f2 changes only how a broken published md5 is handled (rulings-m5 R1), not
  what a run measures; every v3 run has the same `config_sha256`.
- **Not in the report:** the v2 runs 217–248 (onboarding, superseded by v3) and 37 `failed` rows.
  Of these, 36 were superseded by a `--force` rerun and carry "superseded by run N": 219–235
  (dirty or pre-population runs), 249–269 (a dirty v3 pass) and 292 (Paris FUA, rerun as 312
  under `/usr/bin/time`). The other is run 313, a Berlin LAU 2018 row killed when its launcher
  was relaunched; Berlin LAU 2018 is run 314. No city-year lacks a done run.
- `velometer timeseries --check` and `reconcile --check` pass: every flagged year and every gap
  over 20 % has a written explanation against these runs.

The rulings behind these runs are in `docs/superpowers/rulings-m5.md`.
