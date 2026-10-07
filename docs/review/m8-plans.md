# M8 plan research log (Task 4)

Retrieved 2026-10-07. Every Berlin value in `config/plans/reports.csv` was checked against the
`pdftotext -layout` output of its PDF page (script check: value present on the stated page and on
the stated table row), or, for scanned pages, read from the page image rendered at 150 dpi. Downloads
are in `data/plans/docs/` (git-ignored, never committed). Figures are stored as printed (German
decimal comma becomes a dot); documents that disagree are separate rows; nothing is corrected.

Totals: 21 plans in `config/plans/plans.yaml`; 129 report rows (118 Berlin, 11 other cities), 28 of
them `implemented_cumulative`, each with `cumulative_from` (the document's own counting start).

## 1. Berlin: plan

| Document | URL | Page | Check |
| --- | --- | --- | --- |
| Vorlage zur Kenntnisnahme vo19-013 (Radverkehrsplan, Verordnung of 16 Nov 2021) | https://www.parlament-berlin.de/ados/19/IIIPlen/vorgang/verordnungen/vo19-013.pdf | PDF p. 42 (plan p. 21), Tabelle 7; PDF p. 35, Tabelle 3 | Text layer. Yearly targets for Vorrangnetz, Ergänzungsnetz and Radverkehrsnetz copied cell by cell into `plans.yaml`; empty cells (Ergänzungsnetz 2022–2024, Vorrangnetz 2028–2030) are absent, not zero. Printed sums 850 / 1.500 / 2.350 km are rounded to 25 km (footnote 12); not stored as targets. |

## 2. Berlin: reports (all plan `berlin_rvp_2021`)

Script results: `verify.py` found 111 of 111 text-layer values on their stated page (0 missing);
the 3 values of 1392 I are image reads. `verify2.py` flagged 10 row-label mismatches, all on
Hauptverkehrsstraßen rows whose label wraps over two lines or repeats in a second table on the same
page; each was confirmed on the page image.

| doc_id | Type, date | URL | Page, table | Values (km) | Check |
| --- | --- | --- | --- | --- | --- |
| 1392 I | rote_nummer, 2021-07-06 | https://www.parlament-berlin.de/adosservice/18/Haupt/vorgang/h18-1392.I-v.pdf | PDF p. 18 | anlagen 2020: 53.5 completed, 30.6 under construction, 120.2 in planning | Scanned, no text layer; read from the page image. |
| Fortschrittsbericht 2020 (Senate website) | report, 2021-07-01 | https://www.berlin.de/sen/uvk/_assets/verkehr/verkehrsplanung/radverkehr/radprojekte/radfortschrittsbericht/fortschrittsbericht-fahrrad-2020.pdf | table of facilities 2020 | anlagen 2020: 53.3 | Text layer. The column cells sum to 53.5 (noted). doc_date from the imprint "Berlin, Juli 2021" (PDF p. 2); day not printed, first of the month used. |
| 0389 A | rote_nummer, 2022-07-05 | https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-0389.A-v.pdf | PDF p. 15, Tabelle 2; PDF p. 17, Tabelle 4 | anlagen 2021: 39.1 / 58.0 / 221.8. Tabelle 4 (bezirkliches Radverkehrsprogramm only), 2021 and 2017–2021: V 7.4 / 27.4, E 7.4 / 29.3, HVS 3.1 / 9.6, sonstige 0.5 / 3.1, total 18.4 / 69.4 | Text layer; scope noted on each row. |
| 1064 | rote_nummer, 2023-06-27 | https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1064-v.pdf | PDF p. 17, Tabelle 3 | 2022 completed / under construction / in planning: V 15.0 / 7.9 / 50.6; E 8.7 / 9.8 / 48.5; HVS 1.7 / 1.7 / 26.8; sonstige 1.1 / 2.3 / 6.4; total 26.5 / 21.7 / 132.3 | Text layer. |
| 1733 B-1 | rote_nummer, 2025-01-28 | https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.B-1-v.pdf | PDF p. 10, Tabelle 2 | 2023: V 13.6 / 14.7 / 32.3; E 4.9 / 16.1 / 21.5; HVS 3.3 / 2.3 / 22.3; sonstige 4.2 / 1.5 / 9.8; total 26.0 / 34.7 / 85.8 | Scanned; read from the image and cross-checked against the text layer of the berlin.de edition (fb-2023). 1733 B (the first version) has blank table headers; B-1 replaces it with the same values. |
| 1733 C | rote_nummer, 2025-06-24 | https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.C-v.pdf | PDF p. 9, Tabelle 1; p. 10, Tabelle 2; p. 11, Abbildung 2 | 2024 and 2022–2024: V 10.8 / 39.4, E 9.6 / 23.2, Radverkehrsnetz 20.4 / 62.6, HVS 2.3 / 7.3, sonstige 0.9 / 6.2, total 23.6 / 76.1; total 24.3 under construction, 84.9 in planning. Abbildung 2 labels: 2022 V 15.0, E 8.7, HVS 1.7, sonstige 1.1; 2023 V 13.6, E 4.9, HVS 3.3, sonstige 4.2 | Text layer; chart labels confirmed on the image. |
| 1733 E | rote_nummer, 2026-08-12 | https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.E-v.pdf | PDF p. 10, Tabelle 1; p. 11, Tabelle 2 | 2025 and 2017–2025: V 8.6 / 78.2, E 7.5 / 61.9, RVN 16.1 / 140.1, HVS 4.0 / 16.8, sonstige 1.1 / 17.0, total 21.2 / 173.9; 17.1 under construction, 67.2 in planning | Text layer. |
| 19/25987 | drucksache, 2026-05-20 | https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-25987.pdf | PDF p. 10 | V 2022–2025: 14.3, 13.6, 10.9, 9.8; E 2022–2025: 10.1, 5.1, 9.6, 7.5; V cumulative 78.2 ("insgesamt" at the time of the answer, stored under 2026 with a note) | Text layer. |
| 19/27049 | drucksache, 2026-09-14 | https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-27049.pdf | PDF p. 6 (printed p. 5) | 2022–2026 (2026 to 1 Sept): V 14.4, 13.6, 10.8, 8.6, 2.3; E 10.0, 55.1, 9.6, 7.5, 3.77; Sonstiges Netz 3.1, 7.2, 3.2, 5.1, 0.15; total 27.5, 25.9, 23.6, 21.2, 6.22; 2026: 7.7 under construction, 92.7 in planning | Text layer. **Ergänzungsnetz 2023 = 55.1 stored as printed**, with a note: the row total 36.24 minus the other cells (30.87) leaves 5.37; the column total 25.9 implies 5.1; Drs 19/25987 prints 5.1. Ergänzungsnetz 2023 is marked `suspect`, so the current value falls back to 5.1 (19/25987). Summe column stored as cumulative 2022 to 1 Sept 2026 (`cumulative_from` 2022): V 49.46, E 36.24, Sonstiges Netz 18.83, total 104.53; cells as printed sum to 49.7, 85.97 (with 55.1), 18.75 and 104.42 (noted). |

## 3. Berlin: findings

- **Parliament and website editions differ.** rote Nummer 1392 I prints 53.5 km for 2020; the
  berlin.de edition prints 53.3 although its own cells sum to 53.5. Both rows stored. The web
  edition is dated July 2021 by its imprint (2021-07-01), so 1392 I (2021-07-06) is current.
- **Revisions across documents.** Vorrangnetz 2025: 8.6 (1733 E, 19/27049) vs 9.8 (19/25987).
  Vorrangnetz 2022: 15.0 (1064, 1733 C) vs 14.3 (19/25987) vs 14.4 (19/27049). Total 2022: 26.5
  (1064) vs 27.5 (19/27049). Ergänzungsnetz 2023: 4.9 (1733 B-1, C) vs 5.1 (19/25987) vs 55.1
  (19/27049).
- **19/27049 "Sonstiges Netz"** equals HVS + sonstige of the reports for 2024 (3.2) and 2025 (5.1),
  but not for 2022 (2.8 vs 3.1) or 2023 (7.5 vs 7.2). Kept as its own item `sonstiges_netz`.
- **Cumulative baselines differ**: 2017–2021 (0389 A), 2022–2024 (1733 C), 2017–2025 (1733 E),
  2022 to Sept 2026 (19/27049 Summe), stored in `cumulative_from`. Drs 19/25987's "insgesamt" 78.2
  states no start; it gets 2017 because 1733 E prints the same 78.2 for 2017–2025.
  `current_and_revisions` keys on `cumulative_from`, so the two Vorrangnetz 2026 cumulative figures,
  49.46 (from 2022, 19/27049) and 78.2 (from 2017, 19/25987), are separate series, each current in
  its own, not revisions of one another.
- **Counting basis changed.** Reports up to 2020 count facility length per side (item `anlagen`);
  from the 2021 report on, network items count route length once per street section (0389 A halves
  main-road facilities: "18,7 geteilt durch 2").
- **Scope.** The 2021 per-network figures cover only the bezirkliches Radverkehrsprogramm.
- **Not stored (logged only):**
  - district-programme subset tables in the web editions of FB 2022 and FB 2024 (e.g. 13.2 / 40.3;
    7.4 / 67.5);
  - facility-type tables (Radfahrstreifen, geschützte Radfahrstreifen etc.);
  - the printed "Radverkehrsnetz + Hauptverkehrsstraßen" rows: 1733 C (PDF p. 10, Tabelle 2) 22.7
    km in 2024 / 69.9 km 2022–2024, and 1733 E (PDF p. 11, Tabelle 2) 20.1 km in 2025 / 156.9 km
    2017–2025. The plan has no item for this combination; each row is the sum of two stored items
    of the same table (Radverkehrsnetz + Hauptverkehrsstraßen außerhalb Radverkehrsnetz:
    20.4 + 2.3, 62.6 + 7.3, 16.1 + 4.0, 140.1 + 16.8), so storing it would add no figure.
- **Disconfirming:** Drs 19/10136 names only the years of the Ausbaupfade, not km; the feasibility
  log's claim that it quotes the table does not hold. Drs 19/25700, 19/26599, 19/26333 and 19/14625
  contain no city-wide km; no rows.
- The progress report on 2025 is not on berlin.de (HTTP 404 at the expected path); 1733 E is used.

## 4. Other 20 cities

`cumulative_from`: Copenhagen 2017 (plan period 2017–2025), Oslo 2015 ("since 2015"), Strasbourg
2021 (plan launch), Bordeaux 107 km 2021 (adoption), Wrocław 2022 (plan presented), Warsaw 2013
(programme prepared). Removed after the `cumulative_from` ruling, because the document states a
network level with no counting start: Helsinki 44.7 and 16.9 km (2022, HEL 2022-010017), Lyon
1165 and 1208 km (2022, 2023, Métropole network length), Bordeaux ReVE 36 km in service (CRC report
p. 47). Their sources stay listed below.

Official documents only; unknowns are marked in each plan's `note`. Reports rows only where an
official document prints a figure tied to the plan.

| City | Plan | Confirmed at source | Unconfirmed | Rows |
| --- | --- | --- | --- | --- |
| Paris | paris_plan_velo_2021 | 180 km target (press kit p. 15) https://cdn.paris.fr/paris/2025/04/23/plan-velo_dossier-de-presse_fr-2024-web-W8kI.pdf | deliberation date; no official km progress | 0 |
| Vienna | vienna_radwegoffensive | 2026 programme 12.5 km (Mobilitätsagentur); Bilanz 2025 20.4 km started | no single adopted plan | 1 (under_construction; doc_date from PDF metadata) |
| Copenhagen | copenhagen_cykelstrategi_2011 | both plans ended 2025 (Mobilitetsredegørelse 2026 pp. 4, 29); 37 initiatives | successor date | 1 (unit initiatives; doc_date from PDF metadata, printed "Juni 2026"; `suspect`: counts funded and under-construction initiatives as implemented) |
| Amsterdam | amsterdam_meerjarenplan_fiets_2017 | expired per Uitvoeringsplan 2024 p. 3; width share target p. 13 | adoption date | 0 |
| Utrecht | utrecht_mobiliteitsplan_2040 | raadsvoorstel | adoption 15 July 2021 (secondary only) | 0 |
| Madrid | madrid_pdmc_2008 | plan pages on madrid.es | status; 2016 revision PDF refused scripted access (HTTP 403) | 0 |
| Barcelona | barcelona_pmu_2024 | final approval 23 Dec 2022, +40 % network (press release) | successor | 0 |
| Stockholm | stockholm_cykelplan_2022 | plan attachment to KF agenda 30 May 2022; share 2040 | decision protocol not opened | 0 |
| Oslo | oslo_sykkelveinettet_2018 | first phase ~100 km to 2025 (plan PDF p. 7); 155 km (press release 11 Nov 2024) | adoption day; successor | 1 |
| Helsinki | helsinki_pyoraliikenne_2020 | 44.7 / 16.9 km (HEL 2022-010017), not stored | approval date | 0 |
| Lyon | lyon_plan_velo_2024 | 355 km by 2030 (p. 9); network 1165 / 1208 km (p. 10), not stored | 250 km by 2026 (press, NGO only); lyon.fr returned 403 | 0 |
| Strasbourg | strasbourg_plan_velo_2021 | ~100 operations / ~100 km by 2026; 52 operations (strasbourg.eu 30 Oct 2024) | launch day | 1 (`suspect`: a forecast at publication) |
| Bordeaux | bordeaux_plan_velo_2021 | approved 25 Nov 2021, 107 km, ReVE 36 km (CRC report pp. 35, 46–47; ReVE not stored) | | 1 |
| Wrocław | wroclaw_plan_rowerowy_2030 | 100 km by 2030; 40 km (wroclaw.pl 5 Sept 2025) | adoption resolution | 1 |
| Warsaw | warsaw_program_tras_2020 | ~200 km (ZDM 4 Feb 2020) | programme km target; successor | 1 |
| Kraków | krakow_polityka_transportowa_2016 | adopted 8 June 2016 (BIP); 3.7 / 5.7 / 0.85 km (krakow.pl 31 May 2022) | no cycling km target | 3 |
| Budapest | budapest_kfht | 10 % share 2030; resolution 1539/2021 | adoption date; 292 / 504 km (press only) | 0 |
| Prague | prague_koncepce_2010 | 300–400 km extension goal cited by IPR 2021 | extension to 2030 | 0 |
| Bratislava | bratislava_zasady_2014 | resolution 1743/2014; 14.2 km in 2025 (bratislava.sk) | 180 km by 2030 (SITA only) | 1 |
| Ljubljana | ljubljana_cps_2025 | adopted 20 Oct 2025 | no cycling km target in the strategy | 0 |

## 5. Downloads (`data/plans/docs/`, retrieved 2026-10-07 10:16–10:34 UTC)

Licence per document, from a search of each document's extracted text (the `.txt` beside each
PDF) for licence, Lizenz, copyright, ©, Urheber and their Danish, Norwegian, French, Polish,
Slovak and Slovene equivalents, checked 2026-10-07. "Not stated" means the document carries no
licence statement; photo and base-map credits (©) cover those images only. All documents are cited
as data, not reproduced.

| File | Source | Licence |
| --- | --- | --- |
| vo19-013.pdf | Radverkehrsplan Verordnung (URL in §1) | not stated (base maps credited "© OpenStreetMap") |
| h18-1392.I-v.pdf | parlament-berlin.de, rote Nummer | not stated |
| h19-0389-v.pdf, h19-0389.A-v.pdf | parlament-berlin.de, rote Nummer | not stated |
| h19-1064-v.pdf | parlament-berlin.de, rote Nummer | not stated |
| h19-1733.B-v.pdf, h19-1733.B-1-v.pdf | parlament-berlin.de, rote Nummer | not stated |
| h19-1733.C-v.pdf, h19-1733.E-v.pdf | parlament-berlin.de, rote Nummer | not stated |
| S19-27049, S19-25987, S19-25700, S19-26599, S19-26333, S19-14625, S19-10136 (.pdf) | pardok.parlament-berlin.de, Schriftliche Anfragen | not stated |
| fb-2020.pdf … fb-2024.pdf | berlin.de, progress reports | not stated |
| oslo-plan-sykkelveinettet.pdf, oslo-sykkelstrategi.pdf, oslo-ey-2024.pdf | oslo.kommune.no | not stated |
| paris-plan-velo-dp.pdf | cdn.paris.fr | not stated (photo credits only) |
| lyon-plan-velo-2024.pdf | avelo.grandlyon.com | not stated (photo credits only) |
| cph-mobilitetsredegorelse-2026.pdf | byudvikling.kk.dk | not stated |
| bdx-crc-plan-velo.pdf | merignac.com (CRC report) | not stated |
| ljubljana-cps.pdf | ljubljana.si | not stated |
| bratislava-41761.pdf | zastupitelstvo.bratislava.sk | text: CC0 ("Licencia: CC0 (len textová časť)"); figures and the route map from Plán Bratislava: CC BY-SA 4.0 |
| bratislava-37247.pdf | zastupitelstvo.bratislava.sk | not stated |
| vienna-bilanz-2025.pdf | fahrradwien.at | not stated |

URL patterns: rote Nummern
`https://www.parlament-berlin.de/adosservice/{18,19}/Haupt/vorgang/<file>`; Schriftliche Anfragen
`https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/<file>`; progress reports
`https://www.berlin.de/sen/uvk/_assets/verkehr/verkehrsplanung/radverkehr/radprojekte/radfortschrittsbericht/`.
Exact URLs of the other documents are in the `url` column of `reports.csv` or `plans.yaml`.
