# 0001 — Self-built OSM pipeline is the primary source

- Status: accepted
- Date: 2026-10-01

## Context

The three published cross-city benchmarks can't be reproduced per city:

- **Clean Cities 2025** (protected-cycling indicator): 34 of 36 cities supplied their own km. OSM was only a fallback. No code is published. Vienna's figure was revised after publication, from 14% to 22.0%.
- **Copenhagenize 2025:** mixes expert scoring with city data. No per-indicator dataset is published.
- **ECF QECIO v2.10:** publishes its tag logic (see `docs/research/ecf-qecio-2.1-methodology.pdf`, Annex II), but results exist only per NUTS3 region and were frozen in January 2024.

The journalistic premise of this project is that rankings disagree because of definitions, denominators and boundaries. We can only show that with numbers that anyone can re-run.

## Decision

Our own pipeline over OpenStreetMap is the primary source for every number we publish. Published rankings, official city figures and other datasets (BikeNetKit, QECIO) are **comparison layers**. They are stored next to our numbers with provenance and never blended into them.

## Consequences

- Every published figure traces back to a `Run`: git commit, classifier version, OSM timestamp, boundary hash.
- Disagreements with external figures are reconciled and explained (M2 `reconcile`), not averaged away.
- We take on the effort of handling tagging differences ourselves (ADR 0002).
