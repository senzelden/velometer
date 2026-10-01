# 0004 — Two boundary layers: LAU (default) and FUA (robustness)

- Status: accepted
- Date: 2026-10-01

## Context

City units are not comparable:

- Berlin is a city-state of 891 km².
- Paris intra-muros is about 105 km².
- Lyon commune and Métropole give very different pictures.

Any ranking that uses a single boundary layer hides this.

## Decision

Every city is computed on two boundaries:

- **Administrative, Eurostat GISCO LAU 2024 (default).** Where a city has no clean LAU polygon, the fallback is the OSM admin relation, with its relation ID stored. Check Oslo, Ljubljana and Bratislava.
- **Functional Urban Area (Urban Audit FUA).** Used as a robustness check.

Every `Boundary` row stores its source, version, area and file sha256.

## Consequences

- `Run` carries `boundary_kind`. Results are only compared within the same kind.
- The FUA robustness run is part of M3 acceptance for Berlin and Paris.
