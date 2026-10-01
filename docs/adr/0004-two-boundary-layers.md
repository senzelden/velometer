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

## Notes (2026-10-01, M2)

- The LAU source is `LAU_RG_01M_2024_3035.gpkg`, keyed by `GISCO_ID`.
- The FUA source is URAU 2024, keyed by the `…F` codes (field `URAU_CODE`). `DE001L1` is the retired scheme.
- Population is LAU `POP_2024`. When it is 0 or missing (all French LAUs), it comes from Eurostat `demo_r_pjangrp3` for the NUTS3 unit identical to the commune (Paris = FR101).
- Berlin's LAU figure (census-based) differs from NUTS3 (register): about 3.3%.
- The OSM admin fallback is assembled offline from the region extract with `osmium getid -r` + `export`.
- Boundary polygons are repaired with `shapely.make_valid` (polygonal parts only) on write and on load.
