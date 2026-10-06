# M7 external sources: central region (research log)

Registry file: `content/sources/central.yaml`. Accessed 2026-10-06 throughout. Every excerpt was
copied from the fetched page or PDF (text extracted locally with `pdftotext` or an HTML-to-text
pass) and checked against that text by script. The one exception is the scanned Berlin
Fortschrittsbericht 2025: its pages contain no text layer, so those excerpts were transcribed by
hand from rendered images of the pages, and the title says so. Archive links come only from the
Wayback "available" API, and no snapshots were requested. Full page texts are not committed.

## Berlin (10 sources, 37 excerpts)

Searched: the Senate's Radfortschrittsbericht page and PDFs; Hauptausschuss reports 1733 C/D/E;
pardok (Drucksache 19/25987, GVBl. 2026 no. 25); the Radverkehrsplan page and PDF; the Radverkehrsnetz
page; dpa coverage (Nordkurier, Tagesspiegel); the Changing Cities Verkehrswende-Monitor.

Found:
- **Fortschrittsbericht 2025 primary reached** (it was "not reached" in `figures.csv`). It is
  attached to Hauptausschuss report 1733 E of 12 Aug 2026 (`h19-1733.E-v.pdf`, scanned). It
  confirms 21.2 km "neu gebaut oder verbessert" in 2025, and Table 2 gives an
  RVN total of 2,398.3 km, 140.1 km (5.84%) completed 2017 to 2025, and a Vorrangnetz of 870.5 km.
  The counting basis is the infraVelo project database, reference date 31.12.2025, covering all
  measures whoever builds or funds them, with retroactive corrections possible. New finding: in
  2025 the Senate carried out a Vorrangnetz inventory survey "auf Grundlage von Open Street
  Maps-Daten".
- Fortschrittsbericht 2024 (berlin.de PDF): 23.6 km in 2024, Vorrangnetz 872 km, Ergänzungsnetz
  1,507 km, reference date 31.12.2024; quality standards met on 8.4 of 10.8 km of Vorrangnetz.
- Drucksache 19/25987 re-fetched. The quotes for 870 km, ca. 350 km on main roads / >500 km
  minor network, and 78.2 km are confirmed verbatim.
- Radverkehrsplan 2021: Table 3 gives 865 + 1,506 = 2,371 km. A further 553 km of main roads
  outside the RVN and about 388 km of long-distance routes are excluded. Plan deadline 2030.
- Third amendment of the Mobilitätsgesetz (GVBl. 22 Jul 2026): the Vorrangnetz deadline stays at
  2030, the Nebennetz deadline becomes 2035, and § 43(1) now allows main roads without a cycling
  facility. The berlin.de Radverkehrsnetz page still says "bis 2030" for the whole network.
- dpa (Nordkurier, 8 Sep 2026) re-fetched. The `figures.csv` quote ("Von den 2.400 Kilometern
  …") is confirmed verbatim.
- Tagesspiegel/dpa (19 Dec 2025) re-fetched: 20.5 km is confirmed, with the Senate's caveat that the
  tally may be incomplete.
- Changing Cities monitor re-fetched: 25.2 km in 2025 (its own measurement, as of 31.12.2025),
  183.6 km since 2018, and a target network of 2,699.8 km.

Discrepancies worth knowing (all in quotable sources):
- **The `figures.csv` row `berlin,official,new_cycle_infra_km,7.5,…,vorrangnetz` is wrong.** In
  Drucksache 19/25987 (PDF p. 10), 10.1 / 5.1 / 9.6 / 7.5 is the **Ergänzungsnetz** sum row. The
  **Vorrangnetz** sum row is 14.3 / 13.6 / 10.9 / 9.8.
- For 2025 the Vorrangnetz has 9.8 km in Drucksache 19/25987 but 8.6 km in Fortschrittsbericht 2025,
  Table 2. For 2024 it has 10.9 km in Drucksache 19/25987 but 10.8 km in Fortschrittsbericht 2024.
- The 2022 total is 32.4 km in the dpa text on the 2025 report but "rund 26,5 Kilometer" in the
  Tagesspiegel/dpa piece of Dec 2025.
- Vorrangnetz size: 865 km (Radverkehrsplan 2021), 872 km (Fortschrittsbericht 2024), 870.5 km
  (Fortschrittsbericht 2025), ca. 870 km (Drucksache 19/25987). RVN total: 2,371 km (plan), "2.400"
  (dpa), 2,398.3 km (Fortschrittsbericht 2025), 2,699.8 km (Changing Cities).

Not reached or not used: the Fortschrittsbericht 2025 is not on the berlin.de report page (the page
lists 2020 to 2024 only). It is reachable only via the parliament PDF, which has no Wayback snapshot.
There is no Wayback snapshot for Drucksache 19/25987, the 2024 report PDF or the GVBl. PDF. The
consolidated MobG text on gesetze.berlin.de was not used, because the portal is JS-only; the
amendment act was quoted instead.

## Vienna (4 sources, 12 excerpts)

Searched: wien.gv.at Radverkehrsnetz facts page; Mobilitätsagentur / fahrradwien.at Radwegoffensive
pages and Bilanz PDF; presse.wien.gv.at; ORF Wien.

Found:
- **Official definition:** Since 2018, the actual lengths of each facility type have been counted,
  including facilities on both sides of a street. The network is about 1,811 km (page last updated
  21 Jan 2026). The 14 facility types sum to 1,810.9 km and include 365.8 km of contraflow, 411.3 km
  of traffic-calmed areas and 259.7 km of "Radroute".
- Bilanz Radwegeausbau 2025 re-fetched. The `figures.csv` reading is confirmed: 53 projects and
  20,447 m in the main cycle network, counting projects **started** in 2025 (not completed). Each
  facility is measured from start to end point in the city's digital map, a junction counts as 1 m,
  and resurfacing is excluded. The publisher is confirmed from the site imprint as Mobilitätsagentur
  Wien GmbH. fahrradwien.at now redirects to mobilitaetsagentur.at. The agency's city ownership was
  not checked on wien.gv.at.
- ORF Wien (13 Mar 2025): about 24 km planned for 2025, and about 100 km "auf den Weg gebracht" in
  the legislative period. Mobilitätsagentur page: more than 100 km in the main network in recent
  years, and 33 projects totalling about 12.5 km in 2026.

Not reached: the presse.wien.gv.at release of 25 Feb 2026 on the 2026 programme timed out twice.
The Clean Cities rows for Vienna in `figures.csv` belong to the cross-region file and are not
duplicated here.

## Prague (4 sources, 11 excerpts)

Searched: TSK (web, Ročenka dopravy 2024), IPR Praha (Systém celoměstských cyklotras), Městem na
kole, praha.eu.

Found:
- TSK web page: 549 km of "značených cyklotras" (signed routes), 74 km of reserved lanes and 40 km of
  bus/taxi lanes. These are signed routes, not facilities.
- Ročenka 2024, p. 28: 549 km of signed routes, of which 256 km are protected or recommended; 63 km of
  contraflow; reserved / advisory lanes 74.2 / 80.1 km. New in 2024: 0 / 6.6 km of lanes and 16.4 km
  of contraflow. The three basic-data excerpts join a table label with its value cell (the locator
  says so), and the alignment was checked in the `pdftotext -layout` output.
- IPR 2021 update (Council resolution 418/2022): routes "mohou a nemusí být opatřeny orientačním
  značením", meaning a route may be implemented by any cycling measure.
- Městem na kole (26 Jan 2026): slow 2025 (lanes 1.1 km reserved + 6.5 km advisory). The figures come
  from the magazine's own monitoring.

Not found: a city-published total for cycling *facilities* (as opposed to signed routes).

## Bratislava (3 sources, 8 excerpts)

Found: City of Bratislava news of 3 Dec 2025: 14.2 km built in 2025, with a breakdown by type;
total "viac než 205 kilometrov"; a connected network of at least 90 km. SITA (2 Apr 2025):
about 50 km since 2019, and a Bratislava 2030 target of 180 km of main city routes. Cyklokoalícia
(10 Apr 2026): 2025 additions came "v stovkách metrov"; the Vrakuňa path is "necelý kilometer (na
jednej aj druhej strane)", which shows both-sides counting.

Not reached: the council PDF zastupitelstvo.bratislava.sk/data/att/37247.pdf (Akčný plán) was not
fetched, because the press coverage quotes its target.

## Budapest (2 sources, 6 excerpts)

Found: BKK, Kerékpárforgalmi Főhálózati Terv, annex 2 Helyzetértékelés (7 Oct 2022, via the
Fővárosi Közgyűlés document portal). It sets a main network of about 800 km within a base network of
about 5,500 km, and city-managed tracks and lanes total 235 km. Telex/G7 (12 Apr 2024) gives four
points. First, km is "nem túl jó mutató". Second, under the plan, acceptable-standard paths rise from
139 km (2022) to 292 km (2027) and 504 km (2030). Third, ECF's OpenStreetMap-based figure of 307 km
(Jan 2024) compares with 210 km from KSH (2022). Fourth, BKK's reply says 52 km of main network were
built in 2020–2024.

Not reached: bkk.hu downloads (for example the SUMP monitoring report /downloads/32854/) redirect
to the home page for non-browser clients. hvg.hu (11 Aug 2026) returned HTTP 403. The 244 km
(2025) figure seen in a search snippet was therefore not quoted. There is no Wayback snapshot for the
KFHT PDF.

## Ljubljana (3 sources, 4 excerpts)

Found three city-family figures that disagree: "več kot 350 km" (ljubljana.si), "okoli 400 km
kolesarskih poti različnih tipov" (draft CPS 2025–2032, Oct 2025, PDF p. 33) and "okoli 230
kilometrov" (Turizem Ljubljana). The CPS also cites a 4.2% cycling share from Oct 2024 counts on
main roads.

Not used: the 2010 CIVITAS cycling strategy (lkm.kolesarji.org), which is out of period, and the LKM
regional-links article (no figures). There is no official definition of how the 350 km is counted.

## Wrocław (4 sources, 9 excerpts)

Found: wroclaw.pl (5 Sep 2025): 1,450 km of "tras przyjaznych rowerzystom", and nearly 40 km built
since the 2030 plan. Portal Samorządowy (4 Jan 2026): the city hall gives 428 km, and 25 km in 2024.
NIK audit (27 Apr 2023): Wrocław added the most of ten audited cities (more than 45.5 km, 2019 to
Q1 2022); its cycle tracks grew from 84.20 to 110.63 km; city strategies have targets that cannot be
measured. wroclife (28 Apr 2023): the city's 1.4 thousand km includes contraflow lanes and calmed
zones.

## Warsaw (5 sources, 7 excerpts)

Found: ZDM figures differ by date and statement. In 2018 the network was 544 km (406 km tracks +
70 km shared paths + 68 km lanes and contraflow lanes). In Mar 2025 it was 814 km. The year-end
summary says "+55 km" in 2025. In early Dec 2025 ZDM gave 36.9 km built in 2025 and an estimated
860 km at year end (via Portal Samorządowy). TransInfo reports "ponad 873 km" at the end of 2025
and 20.7 km renovated.

Not reached: um.warszawa.pl (the city cycling summary) returned an empty HTTP 202 (bot challenge).
There is no Wayback snapshot for the ZDM 2025 summary.

## Kraków (3 sources, 7 excerpts)

Found: krakow.pl (31 May 2022): 142.5 km of separated infrastructure (2014) rose to about 250 km.
The page defines "szeroko rozumiana infrastruktura rowerowa" to include footways where cycling is
allowed and contraflow cycling in 30 zones, and gives 3.7 / 5.7 / 0.85 km for 2019–2021. ZTP
(3 Sep 2026), 2026–2030 recommendations: do not measure by km alone, and spend 0.6% of the budget.
Portal Samorządowy (Jan 2026): about 316 km, and 9.1 km planned for 2026.

Not reached: the TransInfo article on Kraków 2025 (9 Jan 2026) contains the 2.5 km / 4.8 km figures
only in content that is not in the static HTML, so it was not quoted.

## Notes for the controller

- The Portal Samorządowy article serves three cities, so it is registered three times
  (`wroclaw-`, `warsaw-` and `krakow-portal-samorzadowy-2026`) with the same URL and city-specific
  excerpts.
- Every city has at least one excerpt that states a definition or basis. Where no definition exists,
  the figures given are labelled as reported.
