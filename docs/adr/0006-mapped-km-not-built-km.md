# 0006 — "Mapped km", never "built km"

- Status: accepted
- Date: 2026-10-01

## Context

A rise in OSM km can come from construction, but it can equally come from a mapping campaign, an import, or a tagging switch such as adopting `cycleway:both` or separating sidewalk cycleways.

## Decision

- All OSM-derived lengths are labelled **mapped km**.
- Mapping-effort artefacts are **diagnosed, not corrected**:
  - changeset activity touching cycling tags, per year;
  - tag completeness (share with `width`, `surface`, `segregated`) per tier;
  - duplicate candidates (`Duplicate` rows).
- No output ever states "city X built Y km" from OSM deltas.

## Consequences

The M3 acceptance check flags years where activity spikes coincide with km jumps. The narrative layer uses official figures (with `length_basis` and `network_scope`) for construction claims.
