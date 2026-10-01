# M2 source verification (retrieved 2026-10-01)

Legend: VERIFIED = fetched live on 2026-10-01 from the stated URL. UNVERIFIED = could not confirm.

## 1. GISCO LAU 2024
- VERIFIED: https://gisco-services.ec.europa.eu/distribution/v2/lau/datasets.json lists lau-2011..lau-2024; `lau-2024` released 2025-06-30, files patched 2026-02-18 (Norway codes only; release notes).
- VERIFIED: only ONE scale: 01M (1:1 million). No 10M/20M/60M/100K variants. CRS: 3035, 3857, 4326. Formats: geojson, gpkg, shp.zip, pbf, topojson, svg.zip, fgdb, csv.
- URLs (base https://gisco-services.ec.europa.eu/distribution/v2/lau/):
  - gpkg/LAU_RG_01M_2024_3035.gpkg  (78,225,408 B = 75 MiB; too large to download here)
  - geojson/LAU_RG_01M_2024_4326.geojson (149,866,427 B); geojson/LAU_RG_01M_2024_3035.geojson also exists
  - csv/LAU_RG_01M_2024_3035.csv (5.6 MB, attributes only, no geometry; downloaded and inspected)
  - listing: lau-2024-files.json. Last-Modified of files: 2026-02-18.
- VERIFIED fields (csv + geojson properties): GISCO_ID, CNTR_CODE, LAU_NAME, POP_2024, POP_DENS_2024, AREA_KM2, YEAR. There is NO separate LAU_ID field; the id is inside GISCO_ID. 97,987 rows. Geometry is polygons (geojson Polygon type seen).
- GISCO_ID = `<CNTR_CODE>_<national LAU code>`. Verified rows:
  - Berlin: DE_11000000, "Berlin, Stadt", POP 3,782,202, 891.78 km2
  - Paris: FR_75056, "Paris", POP_2024 = 0 (!), 105.30 km2
  - Wien: AT_90001, "Wien", POP 2,005,760, 413.47 km2
  - København: DK_101, "København", POP 659,350, 91.93 km2
  - Wrocław: PL_1003021056401 (16 chars; ALL Polish GISCO_IDs are PL_ + 13 digits, NOT the 7-digit TERYT), "Wrocław", POP 673,743, 292.80 km2. (Note "Kąty Wrocławskie" is a different row; match on exact name or id.)
- WARNING (contradicts the handover's assumption that LAU holds population): POP_2024 is 0 for ALL 34,946 French LAUs (and all ES, many others; 43,859 zeros overall). Paris population must come from elsewhere (item 3).

## 2. Functional Urban Areas / Urban Audit (URAU)
- VERIFIED: https://gisco-services.ec.europa.eu/distribution/v2/urau/datasets.json: urau-2001, 2004, 2014, 2018, 2020, 2021, 2024. Latest = urau-2024 (dated 01/01/2024; release note 2025-12-15 "based on Census, Degree of Urbanisation and Commuting data"; files Last-Modified 2026-02-19).
- Files (base .../distribution/v2/urau/): geojson|gpkg|shp|pbf|topojson|svg, naming URAU_{RG|LB}_{100K}_2024_{3035|3857|4326}[_CITIES|_FUA].ext. RG = polygons only at 100K scale (RG_100K); LB = label points.
  - FUA polygons: gpkg/URAU_RG_100K_2024_3035_FUA.gpkg (20,545,536 B, not downloaded), geojson/URAU_RG_100K_2024_4326_FUA.geojson etc. (3035 geojson 46 MB).
  - City polygons: gpkg/URAU_RG_100K_2024_3035_CITIES.gpkg (6.5 MB; downloaded, inspected).
  - Attribute table: csv/URAU_AT_2024.csv (63 KB, downloaded).
- VERIFIED fields (gpkg table, 739 rows in CITIES; EPSG:3035): URAU_CODE, URAU_CATG (C=city, F=FUA, K=greater city also exists in older), CNTR_CODE, URAU_NAME, CITY_CPTL, FUA_CODE, AREA_SQM (actually km2), NUTS3_2024. No population field.
- CONTRADICTION: the handover's "DE001L1" is the OLD code scheme. In URAU 2024 the FUA code is DE001F (L1 codes belong to the pre-2020 Urban Audit).
- Codes (VERIFIED from URAU_AT_2024.csv):
  - Berlin: city DE001C (891.78 km2, NUTS3 DE300), FUA DE001F (9,273.5 km2)
  - Paris: city FR001C "Paris" (2,021.4 km2, NUTS3 FR101; this is a larger-than-LAU "greater city"-type unit, NOT the 105 km2 commune), FUA FR001F (18,171.9 km2, NUTS3 FR107)
  - Wien: city AT001C "Wien (greater city)" (454.5 km2 vs LAU 413.5), FUA AT001F (10,093.7 km2)
  - København: city DK001C (457.4 km2 vs LAU 91.9, i.e. a greater city, not Københavns Kommune), FUA DK001F (4,208.6 km2)
  - Wrocław: city PL004C (292.80 km2 = LAU), FUA PL004F (3,109.4 km2)
  - Berlin and Wrocław city = LAU geometry; Paris, Wien, København are wider. Use LAU for the city boundary, URAU only for FUA.

## 3. Population
- LAU file: POP_2024 present but 0 for France (Paris unusable) -> see 1.
- VERIFIED (Eurostat API https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_r_pjangrp3?...sex=T&age=TOTAL&unit=NR; dataset updated 2026-08-28), 1 Jan population by NUTS3:
  - Berlin DE300: 2024 = 3,662,381; 2025 = 3,685,265
  - Paris FR101: 2024 = 2,084,894; 2025 = 2,065,560 (NUTS3 FR101 = Paris dept = commune)
  - Wien AT130: 2024 = 2,005,760; 2025 = 2,028,289
  - Hovedstaden-city DK011 (Byen København): 2024 = 822,733; 2025 = 831,423 (NOT the commune; includes Frederiksberg etc. Commune is 659,350 in LAU)
  - Wrocław PL514: 2024 = 670,892; 2025 = 672,400 (LAU POP_2024 673,743)
- urb_cpop1 (indic_ur=DE1001V) is also available (updated 2026-09-28) but patchy: DK001C and AT001C have no values; Berlin DE001C 2024=3,662,381 and 2025=3,685,265; Wrocław PL004C 2024 = 672,882, 2025 none. Not recommended as the source.
- Berlin LAU POP_2024 (3,782,202) differs from Eurostat NUTS3 (3,662,381): different vintages (census-based vs. register). Pick one source and document it.

## 4. Geofabrik extracts (all retrieved 2026-10-01; the "latest" snapshot is 260930)
Note: the mirror from this machine was flaky (intermittent 502s and 301 loops to `...pbf/`); the dated URLs worked reliably. https://download.geofabrik.de/<path>-latest.osm.pbf is the stable name and 307-redirects to the dated file (seen for Berlin and Denmark).
| Region | URL (dated, HEAD verified 200) | Bytes | md5 |
| Berlin | https://download.geofabrik.de/europe/germany/berlin-260930.osm.pbf | 99,581,016 (~95 MiB) | d9f43a4a986c3912f6c750c3d0033218 (berlin-latest.osm.pbf.md5) |
| Ile-de-France | https://download.geofabrik.de/europe/france/ile-de-france-260930.osm.pbf | 338,876,731 (~323 MiB) | cf264dbeefde66348fe15def3860e4c1 |
| Austria | https://download.geofabrik.de/europe/austria-260930.osm.pbf | 811,337,470 (~774 MiB) | 74212346f51f564d78eda757b75e5abb |
| Denmark | https://download.geofabrik.de/europe/denmark-260930.osm.pbf | 495,094,198 (~472 MiB) | ba5b1ed10f6ee92f901d88f51c362d69 |
| Dolnoslaskie | https://download.geofabrik.de/europe/poland/dolnoslaskie-260930.osm.pbf | 181,090,882 (~173 MiB) | 0ab5acc368a11fbe98ddcb23f9c6f0ee |
- Region ids confirmed in https://download.geofabrik.de/index-v1-nogeom.json (berlin->germany, ile-de-france->france, austria->europe, denmark->europe, dolnoslaskie->poland).
- Wien: VERIFIED no Wien sub-region; austria has no children in index-v1-nogeom.json. Use the Austria extract and clip.
- .md5 exists for all five (`<name>-latest.osm.pbf.md5` and `<name>-260930.osm.pbf.md5`).
- state.txt (https://download.geofabrik.de/<path>-updates/state.txt): VERIFIED for Berlin, Austria, Denmark, Dolnoslaskie (timestamp=2026-09-30T20:22:42Z, sequenceNumber 4919/4926/4927/3990 respectively). Ile-de-France: UNVERIFIED (502 on every attempt; the file almost certainly exists). The state.txt "timestamp" is the replication-stream position; the .osm.pbf header (osmosis_replication_timestamp) is the authoritative data time and was NOT inspected (files too large). Daily extract is dated 260930, and Last-Modified of the PBFs is 2026-10-01 01:15-05:16 GMT.
- CAVEAT: state.txt of the -updates directory is the minutely/daily diff state, not necessarily identical to the PBF snapshot timestamp; confirm from the PBF header after download.

## 5. ECF QECIO
- VERIFIED page https://european-cyclists-federation.github.io/download.html: titled "QECIO (2.0) Downloads". Metadata PDF (https://european-cyclists-federation.github.io/Documents/Metadata.pdf) says "QECIO 2.1"; the Methodology PDF changelog says "Version 2.10, 2024/01/11". So v2.10 is verified in the docs; page title is merely stale.
- Data date: PBF files downloaded 10-11 January 2024 from Geofabrik; last code update 11 Jan 2024 (Metadata.pdf). CSV `Date` column = 2024-01-10/11 per row. CSV file last-modified 2024-12-09 (HTTP header), last content commit in repo 2024-01-11.
- Downloadable:
  - Summary CSV: https://european-cyclists-federation.github.io/Download/Summary/Summary-all.csv (992,938 B; 1514 data rows; downloaded).
  - Per-country GeoPackages: NOT zips; the page links to GitHub folders https://github.com/European-Cyclists-Federation/European-Cyclists-Federation.github.io/tree/main/Download/Cyclenetworks/<CC> (CC = AL AT BE BG CH CY CZ DE DK EE EL ES FI FR HR HU IE IS IT LI LT LU LV ME MK MT NL NO PL PT RO RS SE SI SK TR UK). One file per NUTS3: `<NUTS3 name>-cycle_network.gpkg`. Raw base: https://raw.githubusercontent.com/European-Cyclists-Federation/European-Cyclists-Federation.github.io/main/Download/Cyclenetworks/<CC>/<file>
  - City files: DE/Berlin-cycle_network.gpkg (9.3 MB), AT/Wien-cycle_network.gpkg (3.3 MB), FR/Paris-cycle_network.gpkg (2.6 MB), DK/Byen_Kbenhavn-cycle_network.gpkg (2.6 MB), PL/Miasto_Wroclaw-cycle_network.gpkg (3.2 MB).
  - Local road networks: only on request (ECF contact listed on the download page). Docs: Metadata.pdf, Methodology.pdf under /Documents/.
- CSV columns (143): Country, City, NUTS_ID, "Lat, Lon", Area, Date, overview-main-road-network, local_oneway_km, local_twoway_km, local_dualcw_km, local_contra_km, overview-local-road-network, ratio_contraflow, overview-cycle_tracks-km, overview-cycle_lanes-km, overview-shared_pedestrians-km, overview-limited-access-km, overview-total-cycle-infrastructure, overview-busways-km, overview-cycle_streets-km, overview-ext-cycle-infrastructure, ratio-cycle_tracks-main_roads, ratio-cycle_infra-main_roads, sum_total_surface/smoothness/width, percentage_with_*_tag, type-pedestrian-bidirectional, then many surface_type-<type>-<surface>-km columns etc.
- Rows (km): Berlin DE300 (Date 2024-01-10 19:40, Area 892.633): main roads 2149.623; local roads 4028.123; cycle_tracks 679.471; cycle_lanes 244.319; shared_pedestrians 245.083; limited_access 86.536; total cycle infra 1255.41; busways 29.922; cycle_streets 36.179; ext 1321.511; ratio tracks/main 0.316; ratio infra/main 0.584.
  - Wien AT130: Area 413.486; main 1078.174; local 1961.944; tracks 380.49; lanes 141.157; shared_ped 166.115; limited 113.241; total 801.003.
  - Paris FR101: Area 105.235; main 706.687; local 855.284; tracks 202.694; lanes 66.047; shared_ped 24.3; limited 65.74; total 358.781.
  - Byen København DK011 (name "Byen København"; Area 184.997 km2, i.e. NOT Københavns Kommune): main 474.213; local 1007.182; tracks 385.684; lanes 25.192; total 505.258.
  - Miasto Wrocław PL514: Area 292.068; main 582.65; local 844.518; tracks 227.215; lanes 15.622; shared_ped 128.941; limited 13.799; total 385.578.
- Gotcha: NUTS3 units, not municipalities (DK011 = 185 km2 Byen København, vs commune 91.9/103.9).

## 6. Clean Cities 2025 ranking
- Report: "Streets for Kids, Cities for All" (City Ranking 2025: Streets for Kids Edition), published 2025-05-14 (WordPress datePublished; PDF creation date 2025-05-08). 36 cities. Ranking page https://cleancitiescampaign.org/city-ranking-2025/ ; cycling table page https://cleancitiescampaign.org/city-ranking-2025-cycling-infrastructure/ (modified 2025-07-17).
- PDFs (VERIFIED 200):
  - Report (21 pp): https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf  (Table 5 "Results for Indicator 3: Protected cycling infrastructure" is on PDF page 16, printed pages 28-29)
  - Annexes (8 pp): https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf (Annex methodology for indicator 3 on PDF page 4)
  - Data PDF (10 pp, image-only, no text layer; not read): https://cleancitiescampaign.org/wp-content/uploads/2025/05/CCC-city-ranking-2025-data.pdf
  - Executive summary: .../Executive-Summary-Streets-For-Kids-Cities-For-All.pdf
- Table 5 values (report PDF p.16), protected km / road network km / ratio:
  - Paris 822 / 1,700 / 48%  (rank 1)
  - Copenhagen 397 / 926 / 43% (rank 3)
  - Wroclaw 355 / 1,769 / 20% (rank 9)
  - Berlin 925 / 5,350 / 17% (rank 13)
  - Vienna 384 / 2,844 / 14% (rank 19) in the PDF
- Web page (updated July 2025): Vienna 625.1 km (previously 384.1) of 2,844 km = 22.0% (9th, up from 19th), because the City of Vienna supplied a breakdown of traffic-calmed roads with restricted motor access that are part of the cycling network. VERIFIED in the page text.
- Handover claims: Paris 48% CONFIRMED; Copenhagen 43% CONFIRMED; Wrocław 20% CONFIRMED; Berlin 17% (925 km) CONFIRMED; Vienna 22.0% CONFIRMED only as the post-publication web correction (625.1 km). The PDF itself says 14% (384 km). Note 625.1 now includes traffic-calmed roads, so is not a like-for-like "protected" figure.
- Small discrepancy: the web page (summarised through WebFetch, so UNVERIFIED in detail) shows slightly different denominators (Paris ~1,713, Berlin ~5,441, Copenhagen ~923, Wrocław ~1,775) than the PDF (1,700 / 5,350 / 926 / 1,769). Use the PDF figures.
- Definition (Annexes p.3-4): protected = physically segregated: cycle tracks, shared foot/bike paths, pedestrian streets or greenways; excludes painted lanes, cycle streets, living streets, shared bus lanes. Ratio = protected km / road network km (network not just roads with cycle infra).
- Source per city (city-submitted vs OSM): the report states only "In absence of official city data, OSM data compiled by the ECF was used (ECF tracker methodology)". The per-city source is NOT stated in any text I could extract: UNVERIFIED per city (Data PDF is image-only). Vienna: city-submitted for the July correction (verified). Report text says cities provided "at least partial data".

## 7. BikeNetKit Zenodo 22271229
- VERIFIED via https://zenodo.org/api/records/22271229: "Bicycle networks, street networks, and POIs for 403 European cities for BikeNetKit"; DOI 10.5281/zenodo.22271229; published 2026-09-03; authors Michael Szell (ITU Copenhagen), Mariana Pessoa; code repo https://github.com/BikeNetKit/dataexport. Cities "selected, collected, and processed over the summer of 2026". License field is null in the API response: UNVERIFIED.
- Files (https://zenodo.org/api/records/22271229/files/<name>/content):
  - bike_networks.zip 156,872,639 B md5 ffccda3c4fa40953a31d4cb8d88930d5
  - boundaries.zip 5,821,011 B md5 655c204a16f17b644e6a22d40cf1f68a
  - also growable_networks.zip (1.26 GB), street_networks.zip (557 MB), streetbike_networks.zip (3.7 GB, full OSM), schools.zip (22 MB), rail_stations.zip (2 MB)
- bike_networks.zip layout (VERIFIED by reading the zip central directory via HTTP range, no full download): top dir `bike_networks/`, 403 files `bike_networks/<cityid>.gpkg`, plus a .DS_Store. e.g. berlin_de.gpkg, paris_fr.gpkg, vienna_at.gpkg, copenhagen_dk.gpkg, wroclaw_pl.gpkg (all five present).
- boundaries.zip layout (VERIFIED, downloaded and unzipped): `boundaries/<cityid>.geojson`, 403 files (plus __MACOSX junk entries; 810 entries total). cityid = lowercase ascii name without spaces/diacritics + `_` + lowercase ISO-2 country code: berlin_de, paris_fr, vienna_at (English name, NOT wien), copenhagen_dk, wroclaw_pl. GeoJSON CRS84 (RFC7946), FeatureCollection with empty properties. Berlin/Paris/Vienna/Wroclaw: 1 Polygon feature. copenhagen_dk: 2 features (one ~104 km2 polygon and a ~0.1 km2 sliver).
- Computed boundary areas (equirectangular approximation, km2): Berlin 883, Paris 104.6, Vienna 412, Copenhagen 103.9 (+0.1), Wroclaw 290. Consistent with administrative city limits: Paris = commune only (no Bois), Copenhagen = Københavns Kommune (103.9 incl. coastal waters vs LAU land area 91.9).
- Boundary definition (create_boundaries.ipynb in dataexport/scripts): Nominatim geocode (osmnx `geocode_to_gdf`) of `nominatim_query` from cities.csv (Berlin, Paris, Vienna, Wroclaw); if multipolygon take the largest polygon; fill holes. Copenhagen has an empty nominatim_query and was built from Danish polygons (scripts/development/download_danish_polygons.ipynb, not read: exact definition UNVERIFIED). So boundaries = OSM admin boundaries as of ~mid 2026, not GISCO.
- Bike network content (create_city_networks_from_pbf.ipynb): pyrosm cycling network from country Geofabrik PBF cropped to the boundary envelope, filtered with growbikenet.constants.PBI_CUSTOM_FILTER = highway=cycleway|living_street; highway=path|pedestrian|footway with bicycle=designated|yes|permissive and access!=private; cyclestreet=yes; bicycle_road=yes; cycleway=track; cycleway:right/left/both=track|opposite_track. Truncated to boundary polygon (truncate_graph_polygon), simplified (osmnx simplify), isolates removed, converted to undirected MultiGraph, saved with osmnx save_graph_geopackage (gpkg layers: nodes and edges). Dropped edge tags: key, bicycle, busway, cycleway, est_width, foot, int_ref, lit, motor_vehicle, oneway:bicycle, passing_places, sidewalk, smoothness, surface, tracktype, width, timestamp, version, tags, osm_type; osmid/tags/version/changeset/visible dropped from nodes. => No surface/width info; includes cycle streets and living streets, i.e. NOT equivalent to "protected" (ADR 0006/Clean Cities definition). Edges are simplified (merged) segments; lengths must be recomputed in a projected CRS.
- Geopackage internal schema (layer names, columns, CRS) NOT inspected (UNVERIFIED): no range-read of a gpkg was done.
- OSM snapshot date: UNVERIFIED as one date. Zenodo says only "summer 2026". dataexport/cities/meta/versions.csv lists osm_data_date per tool: growbikenet 0.14.4 2026-07-23, fixbikenet 0.8.0 2026-07-23, linkbikenet 0.7.2 2026-07-23, superblockify 1.0.2 2026-09-08, sortbikenet 0.0.0 2026-01-28. The most likely snapshot for bike_networks (growbikenet-era) is 2026-07-23 but this is inferred, not stated for the Zenodo files. Source PBFs = Geofabrik country extracts ("countryname.osm.pbf").
- Note: boundaries.zip/bike_networks.zip use OSM city boundary, cities limited to >100k pop plus capitals; city ids in docs: https://github.com/BikeNetKit/dataexport/blob/main/cities/meta/cities.csv (columns cityid;name_en;country_en;nominatim_query;country_code;population;center_lat;center_lon).
