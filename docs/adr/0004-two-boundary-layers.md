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

## M5 notes (2026-10-03)

The decision stands: GISCO LAU 2024 is the admin layer for all 21 cities, and FUA (URAU 2024) the
robustness layer. Every city now has a stored LAU, FUA and `osm_admin` boundary. The boundary
check compares the LAU area with the OSM admin relation's area, both measured in the city's EPSG
(trust threshold `boundary_diff_pct_max` 5.0 %). The three cities this ADR asked us to check came
out as follows.

- **Ljubljana:** clean. LAU `SI_061` differs from OSM relation 1675898 by 0.10 %.
- **Oslo:** stays on GISCO LAU (`NO_0301`), by user decision of 2026-10-03.
  - LAU 454.98 km², OSM relation 2775550 480.48 km² (EPSG 25832): 5.31 %, over the 5 % limit.
  - The relation adds 28.02 km² and lacks 2.52 km². Of the added area, 26.43 km² is one part,
    Oslofjord water with its islets; the other 76 parts are each under 0.15 km².
- **Helsinki** (not named here originally, but the same case): stays on GISCO LAU (`FI_091`).
  - LAU 221.69 km², OSM relation 34914 717.28 km² (EPSG 25835): 69.09 %.
  - The relation adds 496.68 km², of which 495.9 km² is one sea part, and lacks 1.09 km².
- **Oslo and Helsinki, mechanism.** During onboarding the 5 % rule briefly switched both to
  `admin_boundary: osm_relation`; the user reverted that because the difference is water. The
  check stays an area comparison (there is no offline land/water layer to compute a land-only
  area), and the breach is explained by a reviewed `### <city>/boundary_diff_pct` note in
  `docs/review/trust/NO.md` and `FI.md`, not by an automatic switch.
- **Oslo and Helsinki, land lost.** The difference is not only water. Clipping the relation
  snapshot to the LAU (classifier v2) loses km on islands and shoreline that the 1:1M LAU leaves
  out: Helsinki tiers A–E 1343.0 → 1319.9 km (−23.1 km, −1.7 %), Oslo 509.3 → 505.8 km (−3.5 km,
  −0.7 %). The notes say so.
- **Bratislava:** GISCO LAU 2024 has no Bratislava municipality, only its 17 borough LAUs
  ("Bratislava - mestská časť …", `SK_528595` … `SK_529494`, queried and listed in
  `config/cities.yaml`). The admin layer is **the union of the 17 LAU polygons** (new
  `CityConfig.lau_codes`; user decision 2026-10-03).
  - Area: GISCO AREA_KM2 sums to 367.61 km², equal to Urban Audit SK001C. The union measures
    367.88 km² in EPSG 25833 against OSM relation 1702499's 367.53 km²: 0.09 %.
  - Boundary `source_version`: "LAU 2024 (1:1M), union of 17 LAU". `cities.lau_code` in the DB
    stays NULL for this city.
  - Population is the sum of the 17 `POP_2024` values: 478,040.
- **Prague**, also a suspected case, is clean (0.13 %).

**Population.** The order is now LAU `POP_2024` (summed for a `lau_codes` city), then a cited
`population_override` in `cities.yaml`, then NUTS3, then Urban Audit. The override exists because
French LAUs carry no population and Spain's POP_2024 is 0. The Urban Audit "city" codes for these
cities are greater cities, not the commune (FR002C Lyon 297.3 km² against LAU 48.0 km²), so spec
decision 9 (`urb_cpop1`) did not hold. Cited national figures (user decision 2026-10-03):

| city | population | year | source |
|---|---:|---|---|
| Lyon | 519,127 | 2023 | INSEE populations de référence 2023, population municipale |
| Strasbourg | 293,771 | 2023 | INSEE populations de référence 2023, population municipale |
| Bordeaux | 267,991 | 2023 | INSEE populations de référence 2023, population municipale |
| Madrid | 3,506,730 | 2025 | INE Revisión del Padrón Municipal 2025 (1 Jan 2025) |
| Barcelona | 1,731,649 | 2025 | INE Revisión del Padrón Municipal 2025 (1 Jan 2025) |

The source URLs are in `cities.yaml` (`population_override.source_url`) and the methodology names
these cities under the `population_national_statistics` limitation. Paris keeps NUTS3 FR101.

**EPSG.** Each city's EPSG is its LAU centroid's UTM zone, checked on write (`check_epsg`).
Copenhagen keeps EPSG 25832 through an explicit `epsg_exception` (Danish national standard; the
centroid is 0.57° into zone 33, a scale error of about 0.06 %).
