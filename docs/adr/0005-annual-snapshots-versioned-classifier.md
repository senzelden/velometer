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
