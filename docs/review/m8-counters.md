# M8 counters: portal research and real load (Task 6: Berlin, Paris, Vienna; Task 7: Helsinki, Madrid, Oslo, Barcelona)

Retrieved 2026-10-07 by `velometer counters fetch` (URLs in `config/counters.yaml`; raw files in
`data/counters/<city>/`, git-ignored, with URL, licence and retrieval time per file in
`retrieved.json`). Counts are what was recorded at counter sites; they are context for the
mapped km, not a measure of all cycling in a city (spec §2.12).

## Berlin

- **Files:** `gesamtdatei-stundenwerte.xlsx`, linked from the Senate page
  <https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrsplanung/radverkehr/weitere-radinfrastruktur/zaehlstellen-und-fahrradbarometer/>
  (17,842,671 bytes, `last-modified` 2026-06-25; retrieved 2026-10-07T13:12:12Z).
- **Licence:** dl-de-zero-2.0, confirmed in the file itself (sheet `Hinweise`, "Nutzungsbedingungen":
  "Datenlizenz Deutschland – Zero – Version 2.0 (dl-de-zero-2.0)").
- **Format:** sheets `Hinweise`, `Legende`, `Standortdaten` (35 directions: id, description,
  latitude, longitude, installation date) and `Jahresdatei 2012` … `Jahresdatei 2025`: column A
  the local wall-clock hour, one column per direction headed `<id> <installation date>`.
- **History:** 2012-03-01 (Schwedter Steg) to 2025-12-31. The `2012` sheet holds 2012 and 2013;
  the `2013` sheet is read after it and wins on 2013.
- **Quirks found:**
  - Data quality is coded as cell fill (sheet `Legende`): orange `FFFFC000` = "no or implausible
    data" (2019 alone: 18,858 flagged zeros and 7,485 flagged non-zero values); yellow `FFFFEB9C`
    = "keine Zähldaten an den Zählstellen vorhanden" (no count data; 16,856 cells, all empty or
    `''` except seven 0s in 2022, none positive); a theme fill marks reconstructed values. Cells
    with either flag fill are missing hours (fix round 1 added the yellow one); reconstructed
    values are counts. The adapter takes the flag colours from the `Legende` rows whose text says
    `keine`.
  - Every day has 24 rows. On spring-forward days the non-existent 02:00 row is empty or 0 (2019
    has 23 rows that day); on fall-back days 02:00 appears once. So spring-forward days are
    complete (the placeholder is ignored) and fall-back days have 24 of 25 hours: incomplete, one
    day a year per site.
  - Six header ids differ from `Standortdaten`: `02-MI-AL-W`, `02-PA-SE-N`, `03-SP-NO-O/W` were
    renumbered (to `01-MI-AL-W`, `11-PA-SE-N`, `16-SP-NO-O/W`; same installation dates in the
    headers), and `Standortdaten` spells `17-SK-BRE-O/W` where every year sheet has
    `17-SZ-BRE-O/W`. Mapped by `site_aliases` in the config; an unmapped header is a
    `CounterFormatError`.
- **Fixture** (`tests/fixtures/counters/berlin/gesamtdatei-stundenwerte.xlsx`, 9.5 KB): `Legende`,
  three `Standortdaten` rows and the hourly rows of 2018-12-31, 2019-01-01, 2019-03-31 and
  2019-10-27 for `02-MI-JAN-N`, `05-FK-OBB-O`, `12-PA-SCH`, values and fills copied from the real
  file. Hand totals: `02-MI-JAN-N` 887 (2018-12-31), 458 (2019-01-01), 1,924 (2019-03-31, 23
  hours), 1,643 (2019-10-27, 24 hours: incomplete); every `05-FK-OBB-O` cell of 2019-10-27 is
  flagged.

## Paris

- **Files:** the ten yearly archives of
  <https://opendata.paris.fr/explore/dataset/comptage-velo-historique-donnees-compteurs/>
  (attachments `2016_…` to `2025_…`, each a zip holding one CSV; 1.1–47.9 MB zipped, up to 1.9 GB
  unzipped) and the rolling 13 months of `comptage-velo-donnees-compteurs` as a CSV export with
  labels as headers and UTC times (142.5 MB; 1,040,237 rows, 2025-09-05T23:00Z to
  2026-10-06T21:00Z). Retrieved 2026-10-07T13:12:13Z to 13:15:01Z.
- **Licence:** ODbL (`license` in the Explore API v2.1 metadata of both datasets, publisher
  "Direction de la Voirie et des Déplacements - Ville de Paris").
- **Columns used:** `Identifiant du compteur`, `Identifiant du site de comptage`, `Nom du site de
  comptage`, `Comptage horaire`, `Date et heure de comptage`, `Coordonnées géographiques`.
- **History:** 2016-01-01 to 2026-10-06.
- **Quirks found:**
  - Each file has its own dialect: UTF-8 (2023 with BOM) or cp1252 (2025), `;` or `,` (2025),
    counts as `12`, `12.0` or `1 007` with a non-breaking space (2025), times naive (2016, 2017,
    2021, 2022), with an offset (`2019-01-01T07:00:00+01:00`) or as `2024-01-02 19:00:00.000
    +0100` (2024, 2025). Naive times are local wall clock: their hourly profile matches the
    offset files in January and July (peak at 08:00–09:00 local), and spring-forward days carry a
    02:00 row.
  - Counter ids are renumbered between files (`100003096-SC` → `100003096-353242251` →
    `101003096-100003096` → `100003096-101003096`), and the 2021–2022 files list extra counters
    per direction. The site id is stable (59/60, 69/69, 75/75, 68/72, 88/92 sites kept year to
    year), so the site is the unit: each hour is the sum of the site's counters in that file.
    Within one file a counter repeating an hour (the spring-forward placeholder written as a second
    `03:00+02:00`) keeps the larger count.
  - Rule (fix round 1): a site-hour is present only when every counter of the site in service
    that day reports it; a counter is in service from its first to its last reported day in that
    file. Found in the real files: in sites with two or more counters, no counter starts or
    stops reporting inside a file while a sibling reports (renumbering happens between files),
    and the counter-days missing inside a counter's span are outages: 26 (2023), 39 (2024), 30
    (2025), none in 2016–2022 (the UTC rolling export was not split this way). Counter-days
    with fewer than 23 rows: 32, 64, 14 (2018–2020) and 105, 204, 102 (2023–2025). A day where
    one counter of a site lacks hours is therefore incomplete; its stored total covers only the
    hours every in-service counter reported.
  - The 2016 and 2017 archives list counters installed later with 0 for every hour (37 of 48
    sites in 2017); such days are outages (rule below), so 2016–2018 index links rest on 6–8
    sites.
  - The 2024 and 2025 archives contain an unlabelled row per hour (no counter, site or name; the
    2024 rows sum to 23.1 million): an all-counters total. Skipped.
  - The archives of 2018 and 2019 end at 12-31 00:00, and every source (archive and rolling
    export) has 24 of the 25 hours of a fall-back day, so those days are incomplete.
  - The rolling export overlaps the 2025 archive (2025-09-06 to 2025-12-31); it is read last and
    wins on shared hours. On the fixture day 2025-10-25 both give 989 for site 100003096.
- **Fixtures** (`tests/fixtures/counters/paris/`, 1.0–10.9 KB each): header plus the rows of sites
  100003096 and 100036718 for 2019-03-31 and 2019-12-31 (`2019.zip`), 2020-01-01 (`2020.zip`),
  2022-03-27 (`2022.zip`, naive times), 2025-10-25 (`2025.zip`, cp1252 and commas) and UTC
  2025-10-24T22:00 to 2025-10-25T23:00 (`rolling.csv`), cut byte for byte from the real files.
  Hand totals: 604 and 1,088 (2019-03-31), 3 (2019-12-31, one hour), 234 and 655 (2020-01-01),
  953 and 0 (2022-03-27), 989 and 2,082 (2025-10-25).

## Vienna

- **File:** `radverkehrszaehlungen.csv`, <https://www.wien.gv.at/gogv/l9ogdradverkehrszaehlungen>
  (redirects to `https://www.wien.gv.at/data/ogd/ma46/radverkehrszaehlungen.csv`; 402,526 bytes,
  `last-modified` 2026-09-04; retrieved 2026-10-07T13:15:01Z). A separate 2011–2012 file
  (`l9ogdbikeroutes`) is not loaded: the index starts long after.
- **Licence:** CC BY 4.0, from the data.gv.at hub API record of dataset
  `2e9f926c-f688-4889-856d-5e6935440c28` (both distributions:
  `https://creativecommons.org/licenses/by/4.0/deed.de`; publisher Stadt Wien).
- **Format:** UTF-8 with BOM, CRLF, `;`; `Datum` (YYYYMMDD) and one column per counter, daily,
  4,748 days (2013-01-01 to 2025-12-31), 20 counter columns.
- **Quirks found:**
  - Thousands are sometimes grouped with a dot (`1.121`; 1,723 cells), sometimes not.
  - `Opernring` equals `Opernring Innen` + `Opernring Außen` on all 4,748 rows: excluded
    (`exclude_columns`), else Opernring would count twice.
  - Whole years of 0 where a counter was not counting: Argentinierstraße 2024 (366 days),
    Margaritensteg 2025 (365) and 2013 (212), Operngasse 2013 (212), Pfeilgasse 2017 (304).
  - No coordinates in the file or its metadata; sites carry none (ruling below).
- **Fixture** (`tests/fixtures/counters/vienna/radverkehrszaehlungen.csv`, 0.9 KB): the header and
  the rows of 2024-01-01, 2024-01-02, 2023-12-30, 2023-12-31, 2013-01-09, 2013-01-10, byte for
  byte. Hand values: Donaukanal 395 (2023-12-31), Opernring Innen 1,121 (2013-01-09, written
  `1.121`), Argentinierstraße 1,028 (2013-01-10) and 0 (2024-01-01).

## Helsinki

- **Files:** `Helsingin_pyorailijamaarat.xlsx` (12,103,856 bytes, `last-modified` 2026-08-24) and
  `pyoralaskentapisteiden_sijainnit.csv` (926 bytes, `last-modified` 2025-07-04), both under
  `https://www.hel.fi/static/avoindata/kymp/`, the resources of HRI dataset
  <https://hri.fi/data/en_GB/dataset/helsingin-pyorailijamaarat>; retrieved 2026-10-07T14:21:26Z.
- **Licence:** CC BY 4.0 (`license_id` `CC-BY-4.0` in the HRI CKAN API record; publisher
  Helsingin kaupunkiympäristön toimiala).
- **Format:** one sheet; `Päivämäärä_aika` (local wall-clock hour, a datetime), `Päivämäärä` and
  `Aika` (the same, as values or text), then 21 point columns (an unnamed 25th column is empty).
  109,534 rows, 2014-01-01 00:00 to 2026-06-30 23:00. The CSV: `piste;x;y`, ISO-8859-1, decimal
  commas, ETRS-GK25 (EPSG:3879; the publisher calls the coordinates indicative), 21 points.
- **Quirks found:**
  - Local wall clock: the 2019 hourly profile peaks at 08:00 and 16:00 in both January and July.
    Every day has 24 rows up to 2024; the spring-forward day carries a 03:00 row (zeros, and 3
    at Baana on 2019-03-31; ignored). From 2025 that day has 23 rows. Fall-back days have 24
    rows (the repeated hour once): incomplete, one day a year per site.
  - Empty cells and 28,147 `''` strings are missing hours. 33 cells hold fractional values
    (Baana 2021, Lauttasaari 2022: `41.447…`, `33.5`), not whole counts (the file does not say
    why); they are rounded to the nearest integer per hour.
  - The file moves counts between the two side columns of a bridge. The publisher notes that in
    2016 both sides of the Kulosaari bridge are in one column; in the file `Kulosaaren silta et.`
    totals 295, 83 and 597 bicycles in 2015–2017 while `po.` holds 609 k–505 k, and
    `Lauttasaaren silta pohjoispuoli` is 0 in 2019 while `eteläpuoli` holds 991 k (pair total
    1,142 k in 2018, 1,105 k in 2020). Yearly totals in thousands:

    | Column | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 |
    |---|---|---|---|---|---|---|
    | Kulosaaren silta et. | 0 | 0 | 0 | 106 | 146 | 209 |
    | Kulosaaren silta po. | 609 | 602 | 505 | 499 | 489 | 705 |
    | Lauttasaaren silta eteläpuoli | 684 | 745 | 843 | 853 | 991 | 426 |
    | Lauttasaaren silta pohjoispuoli | 357 | 335 | 286 | 289 | 0 | 679 |
    | Munkkiniemen silta eteläpuoli | 215 | 424 | 306 | 487 | 453 | 546 |
    | Munkkiniemi silta pohjoispuoli | 385 | 230 | 309 | 222 | 228 | 272 |

    Ruling: the two sides of each of these three bridges are one site (`site_aliases`, summed by
    `days.sum_counters`: an hour counts only when every side in service that day reports it).
    18 sites. Without the merge the index differs by at most 3.0 points (2021: 88.6 against
    85.6); the merge is kept because a link must not count one bridge side twice and the other
    not at all. Pitkäsilta's sides are not merged: no swap is visible (`itäpuoli` ends in 2023).
  - Publisher-listed outages (Kaisaniemi 2021-12-19 to 2022-06-30 and others) appear as empty
    cells. Some site-years hold near-zero totals (Viikintie 2019: 17 k; Baana 2023: 75 k against
    873 k in 2022). They are mostly missing days, not zero days, and none of them reaches 90 %
    complete days, so none feeds a link: Baana 2023 has 92 complete days (2024: 14), Viikintie
    2019 has 50 (2024: 88), and Pitkäsilta itäpuoli 2024 has 0 (141 zero days). Leaving them
    out moves the 2025 index by 0.0 (Task 7 review).
- **Open question for the user (step-down sites, spec §2.13).** The 2024 and 2025 links rest on
  8–9 sites, and two of them step down while still counting (no zeros), which looks like works
  or diversions; the data cannot tell. Kaivokatu: May–August means about 3,200 in 2023, 1,900 in
  2024 and 1,200 in 2025, from April 2024 (per-site ratios 0.59 for 2023→24 and 0.73 for
  2024→25). Pitkäsilta länsipuoli: about halved from May 2025 (0.58), while `itäpuoli` has
  written only zeros since mid-2024. These two account for about 15 points: the 2025 index is
  84.2 (9 sites) as built and 99.9 (7 sites) without Kaivokatu 2024–25 and Pitkäsilta länsipuoli
  2025 (2024: 85.9 and 93.9). The build keeps them, as the recorded §2.13 rule says; dropping
  them, or a generic structural-break rule, would change that decision and is the user's call.
- **Fixture** (`tests/fixtures/counters/helsinki/`): `Helsingin_pyorailijamaarat.xlsx` (18.0 KB,
  header and the rows of 2016-06-01, 2019-03-31, 2019-10-27, 2021-03-10, 2022-03-15, 2025-03-30,
  values copied from the real file) and the coordinate CSV byte for byte. Hand totals: Baana 671
  (2019-03-31, without the 03:00 placeholder 3), 548 (2019-10-27, incomplete), 553 (2021-03-10,
  rounded estimates); Viikin Baana 504 (2025-03-30, 23 rows); Kulosaaren silta 5,852
  (2016-06-01, all in `po.`), incomplete on 2022-03-15 (`po.` 19 of 24 hours).

## Madrid

- **Files:** the six "Aforos bicicletas. <year>" CSVs of
  <https://datos.madrid.es/dataset/300321-0-aforos-peatones-bicicletas> (CKAN API
  `package_show`; resources `300321-25` 2019, `-12` 2020, `-13` 2021, `-24` 2022, `-11` 2023,
  `-10` 2024; 12.7–57.3 MB, 179.5 MB in all), retrieved 2026-10-07T14:21:27Z to 14:21:35Z. The
  XLSX twins hold the same rows (checked for 2021 and 2024).
- **Licence:** CC BY 4.0 (`license_id` `cc-by`, `https://creativecommons.org/licenses/by/4.0/legalcode.es`;
  publisher Ayuntamiento de Madrid).
- **History:** 2019-09-01 to 2021-06-30 and 2022-09-01 to 2024-06-30. The dataset page reports a
  data interruption from August 2021 to September 2022 while detectors were changed and
  adjusted, and advises against comparing data across it; the 2021 file ends in June and the
  2024 file in June (nothing later published on 2026-10-07).
- **Format and quirks:**
  - Two header schemas: 2019–2021 `FECHA;HORA;IDENTIFICADOR;BICICLETAS;NÚMERO_DISTRITO;DISTRITO;
    NOMBRE_VIAL;NÚMERO;CÓDIGO_POSTAL;OBSERVACIONES_DIRECCION;LATITUD;LONGITUD` with decimal
    commas; 2022–2024 `fecha;hora;identificador;bicicletas;device_id;Número_distrito;distrito;
    direccion;observaciones_direccion;latitude;longitude` with dot-grouped coordinates
    (`40.405.472`, `-3.711.961`: the first dot is the decimal point).
  - The 2022 and 2023 files are UTF-8 encoded twice (`NÃºmero`, `PirÃ¡mides`); repaired.
  - `fecha` is `dd/mm/yyyy H:MM` or (72,864 rows of 2019) the date alone; the hour is read from
    `hora`. Local wall clock.
  - 2019–2021: every counter-day has 24 rows; the spring-forward day writes a `2:00` placeholder
    (ignored) and the fall-back day the repeated hour once (incomplete). 2022–2024: 23 and 25
    rows, the repeated `2:00` written twice (28 counters in 2022, 15 in 2023) and read as fold 0
    and fold 1.
  - 2020, October to December: PERM_BICI16_PM01 and PM02 are listed twice per hour under two
    street numbers (Paseo de los Pontones 43 and 24) with identical counts (4,416 hours listed twice, none
    differing): counted once. A duplicate listing with differing counts raises.
  - 41 empty counts (2023: 37, 2024: 4): missing hours.
  - One counter per direction (`PM01`, `PM02`, up to `PM06` at BICI29); 55 counters in all.
- **Index:** base 2020 (spec §2.13). No year links to it: 2019 has four months, 2021 six, 2022
  four, 2024 six; and 2023 cannot link to 2020 because a link joins neighbouring years. Madrid's
  index is 2020 = 100 (33 sites) and nothing else; `counters --check` passes on it (a base year
  carried by at least 3 sites). The portal's own warning against comparing across the detector
  change says the same.
- **Fixture** (`tests/fixtures/counters/madrid/2019.csv`, `2020.csv`, `2022.csv`, `2024.csv`,
  7.7–21.3 KB): header and the rows of chosen counters and days, byte for byte. Hand totals:
  PERM_BICI01_PM01 260 (2019-09-01), 290 (2019-10-27, incomplete), 29 (2020-03-29, 23 hours),
  253 (2022-10-30, 25 hours), 285 (2024-03-31); PERM_BICI16_PM01 78 (2020-10-01, 48 rows),
  151 (2020-10-25, incomplete); PERM_BICI22_PM01 86 (2024-03-12, 9 of 13 rows with a count).

## Oslo

- **API:** <https://trafikkdata-api.atlas.vegvesen.no/> (GraphQL). Public, no key: confirmed,
  every query of this task was answered without credentials (HTTP 200). Retrieved
  2026-10-07T15:00:30Z to 15:03:34Z (18 files, 40.9 MB; refetched in Task 7 fix round 1):
  `00_points.json` (every BICYCLE point of county 3) and one file per kept point with its
  `byDay` nodes, 100 days per page, cursor-paged, from the point's `firstData` to 2026-10-08,
  and the `byHour` nodes of each day with a volume and coverage below 100 % or none (6,317
  days, 20 days per request as GraphQL aliases); the queries and variables of each file are in
  `retrieved.json`. Page sizes above 100 fail with a `DataFetchingException`.
- **Licence:** NLOD (`license_id` `NLOD`, <https://data.norge.no/nlod/no>, on the dataut.vegvesen.no
  record <https://dataut.vegvesen.no/dataset/trafikkdata>; publisher Statens vegvesen). The record
  describes the data as measurements on the state and county road network and some municipal
  roads: these are **state counters**, not Oslo kommune's own (`source` says so).
- **Points:** 17 BICYCLE points in county 3, all `CONTINUOUS`, all in municipality 301, all
  inside the stored Oslo LAU boundary (`data/boundaries/oslo_lau.geojson`; nearest to its edge:
  Frognerstranda about 40 m, Lysaker about 50 m). Bryn has been `OUT_OF_SERVICE` since 2026-03-04.
- **Quirks found:**
  - `byDay` is the sum of `byHour`: Frognerstranda 2019-10-27 has 25 hourly nodes summing to 732,
    the day's `byDay` volume. So the adapter reads days. `coverage.percentage` is the share of
    the day's time reported, not of its hours. Of 50,134 days with a volume, 43,817 have
    coverage 100, 2,303 have 99–100 %, 682 less, and 3,332 (2003–2015, before quality metrics)
    have a volume and no coverage. 397 days have no volume (coverage 0): not stored.
  - **Spot check of `byHour` (Task 7 fix round 1), 51 days sampled at random (seed 7) from the
    real files:**

    | Day coverage | Days | Hours with a volume | Partly covered hours |
    |---|---|---|---|
    | 99–100 % | 25 | 24 of 24 on every day | 1–3 per day (77.8–99.4 %) |
    | 95–99 % | 10 | 24 of 24 on every day | 1–9 per day (50–99.2 %) |
    | below 95 % | 6 | 10–19 (whole hours missing or at coverage 0) | |
    | none (2005–2014) | 6 | 24 of 24 on every day | no coverage figure per hour |
    | 100 % | 4 | 24 of 24 | 0 |

    So coverage below 100 % means minutes missing inside present hours down to about 95 %, and
    whole hours missing below it; the days without a coverage figure have every hour. No
    coverage threshold says "all hours present" exactly, so the adapter derives it from `byHour`
    (spec §5.2, as for the other cities): a day at coverage 100 is complete; any other day is
    complete when `byHour` gives every local hour of it (23, 24 or 25) a volume, however much
    of the hour is covered. In 2015 the API lists each old-system hour twice, once with a volume
    and no coverage, once at coverage 0 without a volume: the hour counts as present.
  - Result over the 50,134 stored days: the rule marks 49,778 complete (43,817 at coverage 100;
    all 2,303 at 99–100 %; 315 of 350 at 95–99 %; 10 of 81 at 90–95 %; 3,326 of the 3,332
    without coverage; 7 of 251 below 90 %, in 2015–16, with every hour partly covered), and the
    zero-day rule then takes out 129 zero-total days: 49,649 complete.
  - `firstData` reaches back to 2003 (Frognerstranda) and 2009 (Aker sykehus), but no link
    before 2016→2017 has 3 qualifying sites; the index starts in 2017.
- **Fixture** (`tests/fixtures/counters/oslo/`): `points.json` (Frognerstranda, Dr. Eufemias gt.
  Vestgående and, from a county-32 query, Snarøyveien in Bærum: outside Oslo), their day nodes for
  a few days cut from the real files (Snarøyveien from a 2019-10-26..28 query), and a copy of the
  stored Oslo LAU boundary (5.9 KB). Hand values: Frognerstranda 732 (2019-10-27, complete), 1,306
  (2015-10-26, coverage 45.83 %, 11 of 24 hours: incomplete), 2,894 (2010-05-06, no coverage, 24
  hours: complete), no day 2017-05-20 (coverage 0); Dr. Eufemias 483 (2019-10-28, coverage
  99.69 %, 24 hours with a volume: complete). The `byHour` nodes of those three days are cut
  from the real API answer (2026-10-07).

## Barcelona

- **Files:** the yearly CSVs of Open Data BCN datasets
  <https://opendata-ajuntament.barcelona.cat/data/en/dataset/aforaments-descriptiu> (gauges,
  2017–2025, 65–117 KB) and
  <https://opendata-ajuntament.barcelona.cat/data/en/dataset/aforaments-detall> (values,
  2017–2025, 1.0–1.9 MB), retrieved 2026-10-07T14:23:53Z to 14:24:11Z. The portal answers
  httpx's default User-Agent with 502; downloads now send `velometer/<version>` (no contact).
- **Licence:** CC BY 4.0 (`license_id` `CC-BY-4.0` on both CKAN records; organisation Transport,
  Ajuntament de Barcelona).
- **Format:** detail rows `Any,Id_aforament,Mes,Codi_tipus_dia,Desc_tipus_dia,Valor_IMD`: the
  monthly average daily intensity per gauge and day type (1 Monday, 2 working days, 3 Friday,
  4 Saturday, 5 Sunday; labels vary in case and number by year). Descriptor rows give the gauge
  type (`Codi_tipus_aforament` 2 = `Bicis`), description, WGS84 and ETRS89 coordinates. Not
  counts: a separate series, `avg_daily_intensity` (spec §2.14).
- **Quirks found:**
  - `Mesura no disponible` marks a missing month (152 to 797 working-day bike values a year); a
    value of 0 (2021) is also read as missing. Values carry a leading space (` 9365`).
  - The 2017 descriptor has a broken row (a stray quote merges gauges 20093 and 20094, with
    Valencia's coordinates, -0.39, 39.47); rows of another width are skipped and both gauges are
    described in later years.
  - The 2022–2024 descriptors type the three Glòries tunnel gauges 30001, 30002, 30005 `Bicis`
    (values up to 41,496 a day); the 2025 descriptor types them traffic. Ruling: a gauge's type,
    name and coordinates are those of the latest descriptor listing it; the tunnel gauges drop out.
  - Gauge ids are stable across years; a few descriptions and positions move by up to 264 m
    between 2017 and 2018 (20093: 1.8 km, 2018 to 2019), kept as the same gauge.
- **Index:** the yearly mean of a site's twelve working-day months; a site is valid in a year
  only with all twelve; links and chaining as for counts (`chain_index_monthly`). 429 bike gauges
  with values; 127 valid in 2019.
- **Fixture** (`tests/fixtures/counters/barcelona/`, 0.3–8.6 KB): the 2019, 2024 and 2025
  descriptor rows and the 2019, 2020 and 2024 detail rows of gauges 20012, 20013, 20015, 20037
  and 30001, byte for byte. Hand values: working-day means 2019 / 2020: 20012 2,037.4 / 1,802.7,
  20013 1,996.6 / 1,608.4, 20015 786.75 / 734.25; 20037 lacks April 2020; link 2019→2020 =
  49,744 / 57,849 = 0.8599 on three sites.

## Rules applied in the load

- Hourly to daily (`counters/days.py`): a day is complete when it holds every local hour that
  exists that date (23, 24 or 25); records for a non-existent hour are ignored; repeated hours
  from overlapping files count once, the later file winning.
- A site-day with a total of 0 is an outage, not a valid day (kept with count 0, `complete` 0),
  for every city: Paris writes 0 for counters not yet installed, Vienna for counters not
  counting, and Berlin's legend codes 0 as "no or implausible data".
- Vienna sites have no coordinates (`lat`/`lon` NULL, allowed by the schema); the Counts tab
  shows them as a list. No coordinates were derived from the names.
- `counters load` replaces a city's daily rows (one transaction), sites and index from its files.

## Real load (2026-10-07)

`velometer counters load berlin paris vienna`: 144 s, 1.9 GB peak RSS (Paris: 10.2 million rows
read). `velometer counters --check`: exit 0, "counters ok: 3 cities". Figures after fix round 1
(Berlin yellow fill as missing, Paris in-service counter rule); the values before it are given
where they changed.

| City | Sites | Days stored (complete) | First day | Last day |
|---|---|---|---|---|
| Berlin | 35 | 101,963 (101,375); before: 101,970 | 2012-03-01 | 2025-12-31 |
| Paris | 109 | 242,703 (202,263); before: 242,753 (202,312) | 2016-01-01 | 2026-10-06 |
| Vienna | 19 | 67,933 (66,473) | 2013-01-01 | 2025-12-31 |

Index of counts recorded at counter sites, 2019 = 100 (qualifying sites in brackets; "none" =
fewer than 3 sites with 90 % complete days in both years of the link, or a broken chain):

| Year | Berlin | Paris | Vienna |
|---|---|---|---|
| 2012 | none (0) | | |
| 2013 | none (1) | | 71.7 (10) |
| 2014 | none (1) | | 88.1 (12) |
| 2015 | none (1) | | 87.5 (12) |
| 2016 | 93.8 (14) | 75.9 (7) | 93.9 (12) |
| 2017 | 89.6 (23) | 76.9 (6) | 93.0 (12) |
| 2018 | 101.3 (20) | 66.9 (8) | 99.2 (13) |
| 2019 | 100.0 (21) | 100.0 (31) | 100.0 (13) |
| 2020 (COVID year) | 114.6 (21) | 130.2 (26) | 112.0 (13) |
| 2021 | 102.2 (22) | 141.3 (49) | 113.3 (13) |
| 2022 | 102.0 (23) | 165.2 (49) | 113.8 (13) |
| 2023 | 98.5 (23) | 186.5 (48); before 185.2 (49) | 116.9 (18) |
| 2024 | 101.6 (29) | 191.5 (60); before 186.5 (62) | 122.5 (17) |
| 2025 | 100.3 (29) | 205.2 (74); before 199.9 (75) | 121.6 (16) |
| 2026 | | none (0; Jan–Oct only) | |

The base-year count is the number of sites with 90 % complete days in 2019; every other year's
count is the sites of its link with the neighbouring year towards 2019.

Fix round 1 changed no Berlin or Vienna index value (Berlin lost seven days, the 2022 yellow-filled
0s, none of them complete); in Paris the in-service rule leaves 49 fewer complete site-days (and
50 site-days with no hour reported by every counter drop out) and moves 2023–2025.

## Rules added in Task 7

- Sites mapped to one id by `site_aliases` are summed hour by hour with the in-service rule of
  Paris (`days.sum_counters`, moved there from the Paris adapter).
- An entry's `boundary: lau` drops sites outside `data/boundaries/<city>_lau.geojson` (and their
  rows) at fetch and at load; a missing boundary file is a `CounterFormatError`.
- A monthly portal (`grain: monthly`) loads into `counter_monthly`; its index series is
  `avg_daily_intensity`; `counters --check` also flags negative monthly values.

## Real load, all seven cities (2026-10-07, Task 7)

`velometer counters load helsinki madrid oslo barcelona`: 33 s, 0.75 GB peak RSS. `velometer
counters --check`: exit 0, "counters ok: 7 cities".

| City | Sites | Stored (complete) | First day | Last day |
|---|---|---|---|---|
| Helsinki | 18 | 65,413 days (64,562) | 2014-01-01 | 2026-06-30 |
| Madrid | 55 | 51,485 days (47,949) | 2019-09-01 | 2024-06-30 |
| Oslo | 17 | 50,134 days (49,649) | 2003-08-01 | 2026-10-07 |
| Barcelona | 429 | 130,485 monthly values (26,110 working-day) | 2017-01-01 | 2025-12-31 |

Index of counts recorded at counter sites (Barcelona: of average daily intensity), base 2019 =
100 (Madrid 2020 = 100); qualifying sites in brackets. Oslo has `none (0)` rows for 2003–2015
and `none (2)` for 2016, Berlin and Paris as in the Task 6 table.

| Year | Berlin | Paris | Vienna | Helsinki | Madrid | Oslo | Barcelona |
|---|---|---|---|---|---|---|---|
| 2013 | none (1) | | 71.7 (10) | | | none (0) | |
| 2014 | none (1) | | 88.1 (12) | 87.6 (5) | | none (0) | |
| 2015 | none (1) | | 87.5 (12) | 91.1 (8) | | none (0) | |
| 2016 | 93.8 (14) | 75.9 (7) | 93.9 (12) | 92.2 (13) | | none (2) | |
| 2017 | 89.6 (23) | 76.9 (6) | 93.0 (12) | 90.8 (12) | | 92.4 (5) | 89.2 (19) |
| 2018 | 101.3 (20) | 66.9 (8) | 99.2 (13) | 104.4 (13) | | 108.7 (7) | 95.8 (31) |
| 2019 | 100.0 (21) | 100.0 (31) | 100.0 (13) | 100.0 (13) | none (0) | 100.0 (11) | 100.0 (127) |
| 2020 (COVID year) | 114.6 (21) | 130.2 (26) | 112.0 (13) | 106.2 (13) | 100.0 (33) | 128.3 (9) | 91.8 (114) |
| 2021 | 102.2 (22) | 141.3 (49) | 113.3 (13) | 85.6 (13) | none (0) | 103.5 (8) | 119.3 (164) |
| 2022 | 102.0 (23) | 165.2 (49) | 113.8 (13) | 79.0 (9) | none (0) | 113.6 (10) | 132.9 (165) |
| 2023 | 98.5 (23) | 186.5 (48) | 116.9 (18) | 85.6 (10) | none (0) | 117.2 (13) | 135.8 (174) |
| 2024 | 101.6 (29) | 191.5 (60) | 122.5 (17) | 85.9 (8) | none (0) | 124.7 (14) | 135.3 (191) |
| 2025 | 100.3 (29) | 205.2 (74) | 121.6 (16) | 84.2 (9) | | 140.6 (15) | 140.3 (207) |
| 2026 | | none (0) | | none (0) | | none (0) | |

Oslo before and after the complete-day fix (Task 7 fix round 1; `coverage == 100` against all
local hours present from `byHour`), reloaded with `velometer counters load oslo`, `counters
--check` exit 0:

| Oslo | 2017 | 2019 (base sites) | 2020 | 2021 | 2025 |
|---|---|---|---|---|---|
| coverage == 100 (before) | 91.5 (4) | 100.0 (8) | 124.0 (7) | 99.4 (6) | 133.6 (13) |
| all hours present (after) | 92.4 (5) | 100.0 (11) | 128.3 (9) | 103.5 (8) | 140.6 (15) |

`velometer content --check`: ok (the counter explainer `content/counters.yaml`, sources in
`content/sources/counters.yaml`, every excerpt found on its page with `check_online`).
