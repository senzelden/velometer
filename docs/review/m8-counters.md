# M8 counters: portal research and real load (Task 6: Berlin, Paris, Vienna)

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
