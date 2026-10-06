# M7 content review

Review stop (spec §2.15). Everything below is rendered from `content/`: the 21 city narratives, the combined story, the differences explainer, and the external sources they quote. Quotes come only from external sources (`content/sources/*.yaml`); internal material is cited as *[internal: …]*. All numbers are checked against the database by `velometer content --check` (exit 0).

## Judgement calls

Decisions taken while preparing this content that you may want to overturn:

**Sources**
1. **Berlin Vorrangnetz 2025 corrected from 7.5 to 9.8 km** (`config/external/figures.csv`,
   commit 67ed739). The earlier extraction took the sum row of the following Ergänzungsnetz table
   in Drucksache 19/25987; checked against the PDF text. The reconciliation report changed by that
   one row.
2. **Berlin Fortschrittsbericht 2025** was reached (attached to Hauptausschuss report 1733 E). The
   PDF is a scan, so its excerpts were transcribed by hand from the page images; they are the only
   excerpts not checked by script.
3. **Oslo: the EY evaluation is tagged `official`** because the city commissioned it; the title names
   the consultant.
4. **Two excerpts were reassembled from PDF layout** (Paris press kit p. 8, Lyon Plan vélo p. 10);
   the reading order was verified and the locators say so.
5. **Secondary or mirrored sources, each labelled in its title:** Madrid's 1,167 km (a press report;
   madrid.es blocked fetching), the Stockholm Cykelplan (a copy on insynsverige.se), the Bordeaux
   audit-chamber report (republished by Mérignac). Utrecht's only split (2012) comes from a
   historical society, tagged `ngo`.
6. **The Portal Samorządowy article is registered three times** (Wrocław, Warsaw, Kraków), with the
   same URL and city-specific excerpts.

**Narratives**

7. **Official totals that are not in the database appear only inside quotes**, never as bare numbers
   in the prose (the checker requires every number to be a declared fact). Examples: Vienna 1,811 km,
   Oslo 290 km, Berlin's 8.6 km.
8. **The headline is worded "mapped A+B km per 100 km of main roads" everywhere**, not as a
   percentage (Helsinki is 264.7).
9. **Changes with no investigation on record are called unexplained**, not guessed at. Examples:
   Copenhagen FUA 2019→2020, Utrecht A→B, Strasbourg 2021, Vienna FUA tier A→B.
10. **Paris:** the city's own km series is an OSM extract, so the narrative says it cannot confirm or
    refute our km.
11. **Claims dropped from the spike drafts as unsupported:** the +16% total rise, "10 of 17 within 20%
    of Clean Cities", "nine within 3% of QECIO", Lyon "rising every year", Madrid "moved the least",
    and Bordeaux "new mayor".
12. **A content review led to wording fixes** (85b1d7c). It removed phrases that read as building
    ("the city added", "new paths"), an unsupported Prague cause and a false "Berlin is the only city
    below 2018" (Helsinki is too). It also clarified that Clean Cities gives no rule for how cycling km
    are measured.

**Explainer**

13. **One section per dimension** (what is counted, kind of km, length, date, area, who measured), each
    with a worked example. Warsaw's main-road drop illustrates the date dimension. Vienna's July 2025
    Clean Cities update (384 → 625.1 km after traffic-calmed roads were counted) illustrates scope.

## Shift findings

Full analysis: `docs/review/shifts.md`. One line per shift:

- **bratislava/lau/2020** Cause: **tag drift** (clean-up retagging, one mapper dominant). A+B fell 132.2 -> 112.9 km
- **stockholm/lau/2018-current** Cause: **tag drift** (gradual, community-wide `segregated` and `foot` tagging), alongside new
- **budapest/lau/2024** Cause: **mapping activity** (painted lanes tagged on existing roads). D rose 118.1 -> 152.7 km
- **ljubljana/lau/current** Cause: **mapping activity** (side paths drawn as separate ways). A+B rose 228.1 -> 245.0 km
- **amsterdam/lau/2025** Cause: **tag drift** (one mapper's `segregated=yes` sweep). Between the 2024 and 2025 snapshots
- **copenhagen/lau/2025** Cause: **tag drift** (designation dropped and restored). B went 88.8 -> 74.0 -> 86.5 km on the
- **warsaw/lau/2025** Cause: **denominator** (expressways retagged as motorways). The main-road km
- **helsinki/lau/2025** Cause: **denominator** (street reclassification). The main-road km (`main_excl_motorway`) rose

## Sources not reached

### central (`docs/review/m7-sources-central.md`)

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

Not reached or not used: the Fortschrittsbericht 2025 is not on the berlin.de report page (the page
lists 2020 to 2024 only). It is reachable only via the parliament PDF, which has no Wayback snapshot.
There is no Wayback snapshot for Drucksache 19/25987, the 2024 report PDF or the GVBl. PDF. The
consolidated MobG text on gesetze.berlin.de was not used, because the portal is JS-only; the
amendment act was quoted instead.

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

Not reached: the council PDF zastupitelstvo.bratislava.sk/data/att/37247.pdf (Akčný plán) was not
fetched, because the press coverage quotes its target.

Not reached: bkk.hu downloads (for example the SUMP monitoring report /downloads/32854/) redirect
to the home page for non-browser clients. hvg.hu (11 Aug 2026) returned HTTP 403. The 244 km
(2025) figure seen in a search snippet was therefore not quoted. There is no Wayback snapshot for the
KFHT PDF.

Not reached: um.warszawa.pl (the city cycling summary) returned an empty HTTP 202 (bot challenge).
There is no Wayback snapshot for the ZDM 2025 summary.

Not reached: the TransInfo article on Kraków 2025 (9 Jan 2026) contains the 2.5 km / 4.8 km figures
only in content that is not in the static HTML, so it was not quoted.

### cross (`docs/review/m7-sources-cross.md`)

- **Found:** `qecio-methodology` (10 excerpts) and `qecio-metadata` (2), both on ECF's own tracker site, `european-cyclists-federation.github.io` (author contacts are @ecf.com addresses; the ecf.com QECIO page links to this site). The downloaded Methodology.pdf has the same SHA-256 as the repo copy `docs/research/ecf-qecio-2.1-methodology.pdf` (11f69d40…).
- **Not reached:** `https://ecf.com/quantifying-europe-cycling-infrastructure-using-openstreetmap-qecio-2` returned a Cloudflare 403 page to curl and an empty page to WebFetch. No Wayback snapshot exists for Methodology.pdf; one exists for Metadata.pdf (2023-12-12, which predates v2.10).
- **What counts:** Table 2 (p.15) defines cycle tracks (physically separated), cycle lanes (paint only) and cycle and pedestrian tracks (signed shared). The "segregated" ratio adds painted cycle lanes to tracks and shared paths (p.5), so ECF's "segregated" is **not** Clean Cities' "protected".
- **How length is measured:** side-tagged ways become two features, and one-way infrastructure is counted at half length (p.5). A ratio of 100 means "bidirectional" infrastructure on all main roads.
- **Area:** NUTS 3 regions, with highways clipped to NUTS-3 boundaries (pp.2, 4).
- **Date:** PBF files downloaded 10–11 January 2024 from Geofabrik (Metadata p.1). There has been no release since.
- **Kind of km:** mapped km only. The Disclaimer (p.8) says the data "only represents OSM contributions".

- **Found:** the Zenodo record (`bikenetkit-zenodo`, 3 excerpts; published 2026-09-03; Szell, Pessoa), read via WebFetch as described above. The Zenodo description sends readers to GitHub "for details", so the method was taken from the code at pinned commits: `bikenetkit-export-notebook` (dataexport e2a5bcf: country PBFs, cropped to city boundaries of cities above 100k population) and `bikenetkit-pbi-filter` (growbikenet 8820875: `PBI_CUSTOM_FILTER`, "protected bicycle infrastructure").
- **What counts:** the bike network filter includes `highway=living_street` and footway/path/pedestrian ways with `bicycle=yes|permissive|designated`. That is broader than the Clean Cities "protected" definition and includes living streets, which Clean Cities excludes.
- **How length is measured:** the notebook builds the graph with `force_bidirectional=True` and simplifies it. No km basis is stated in prose. **No quotable definition of length**.
- **Date:** only "over the summer of 2026". The PBF snapshot date is not stated.
- **Not reached:** zenodo.org gave HTTP 403 to curl (rate limit). No Wayback snapshot exists for the record or the GitHub files.

- **Found:** the act PDF (`eu-c2026-4676-act`, 2 excerpts), the Annex PDF (`eu-c2026-4676-annex`, 2) and the DG MOVE news item (`eu-umi-news`, 1; Wayback snapshot recorded). No Wayback snapshot exists for the two PDFs.
- **Cycling:** the only indicator that mentions cycling is SU.1, trips per day by mode, collected by survey, mobile phone data, model or big data (Annex p.2). **There is no cycling-infrastructure-length indicator.** First data is due 31 December 2027 (Article 5(1)), and SU.1 may be reported every fifth year (Article 5(3), not excerpted).
- **Area:** each urban node is a set of LAUs (Article 6(1), pp.5–6).

### north (`docs/review/m7-sources-north.md`)

Not reached:
- The Bicycle Account 2022 at `kk.sites.itera.dk/apps/kk_pub2/pdf/2420_d4db2492337f.pdf`. The
  server returned an SQL error page. The same document was reached at
  urbandevelopmentcph.kk.dk instead.
- English *Mobility Report 2026* (`byudvikling.kk.dk/.../Mobility%20Report%202026.pdf`). It
  was fetched and matches the Danish text ("In 2025, there were 401 km of cycle paths"). It
  was not added, to avoid a duplicate. Note that it translates *cykelsti* as "cycle paths".
- No snapshot exists for the Bicycle Account 2022 URL.

Not reached / not used:
- Aftenposten and Nettavisen articles (paywall or not fetched).
- The *Plan for sykkelveinettet* PDF itself, as it was not needed.

Gaps:
- No 2024–2026 official monitoring report was reached. The Yle figures are the latest and come
  from the press.
- The paatokset.hel.fi case page has no Wayback snapshot.

Not reached:
- **Utrecht open data, Indicatoren Fiets** (`open.utrecht.nl/dataset/indicatoren-fiets-mobiliteit/...`)
  returned a 404.
- data.utrecht.nl was not tried after the 404.
- Staat van Utrecht (provincial) has only total road km (gemeente Utrecht 1,185 km of road,
  2024) and no cycle path km, so it was not used.
- The Mobiliteitsplan 2040 itself was found only as a third-party copy (bollunetten.nl) and
  was not used.

### west (`docs/review/m7-sources-west.md`)

Not reached or not used:
- `https://www.bordeaux.fr/velo-et-marche-des-modes-de-deplacement-doux-dans-une-ville-apaisee`: HTTP 403.
- The CRC report as hosted by ccomptes.fr was not found. `ccomptes.fr/…/NAR2025-062.pdf` is a different report, so the copy republished by the Ville de Mérignac is quoted instead, and the title says so.
- Rue89 Bordeaux on the CRC report: reached, but no quotable figures in the accessible text.

Not reached or not used:
- madrid.es returns HTTP 403 (Akamai) to plain GETs. Affected: the Plan Director 2008 revision PDF (`…/PDMC2008_Revision_y_actualizacion_1.pdf`), the plan's landing page, and the 2007 news item on the 274 km network. The official press release behind the 1,167 km figure was not found, so a secondary source is quoted and the title says so.
- madridpress.com: HTTP 403.
- madridactual.es: reached, but it covers the regional (Comunidad de Madrid) network, not the city.

Not reached:
- `https://ce.atm.cat/ca/web/observatori/w/quilometres-xarxa-ciclable-ciutat-barcelona` (ATM mobility observatory, km by type): TLS certificate verification failed, and the page was not fetched without verification. Not quoted.
- barcelona.cat/mobilitat news (11 Feb 2025): reached. It repeats the 268 km, so the Servei de Premsa release is used instead.

## Registry: 106 sources, 266 excerpts

## Combined story

### 21 cities on one map: a stable top, faster climbers below

*Across the 21 cities, mapped A+B rose from 8,942 km in January 2018 to 10,400 km in October 2026. The top of the table held its places; several cities that started low gained fastest.*

#### One yardstick for 21 cities (step: all)

Every figure here is mapped km in OpenStreetMap, measured the same way in each city proper (LAU) every January from 2018 and in October 2026 [internal: velometer run set, LAU series of all 21 cities (classifier v4, mapped km)]. Tiers A (separated tracks) and B (shared foot and cycle paths) make up the headline, mapped A+B km per 100 km of main roads, counted per road side. A rise on the map can be new infrastructure, catch-up mapping or the same paths retagged, and the map alone rarely tells which.

#### The leaders (step: leaders)

Helsinki (262.3), Stockholm (261.0) and Copenhagen (237.9) lead, followed by Amsterdam (203.0) and Utrecht (193.6) [internal: velometer run set, LAU series of all 21 cities (classifier v4, mapped km)]. Each of them maps more km of A+B than of main roads. The top seven, down to Strasbourg and Berlin, hold the same ranks as in 2018. Helsinki leads on shared paths: 943 of its 1,279 mapped A+B km are tier B, a kind of path Clean Cities also counts as protected. Its headline fell, from 276.2 to 262.3, while its mapped A+B barely moved; the cause is in the main roads it divides by.

> “Shared foot and bike paths, while not ideal, still offer protection from motorised traffic, helping certain cities perform relatively well. These types of infrastructure are common in countries like Germany, Poland and Finland.”
>
> — Clean Cities Campaign [1]

#### At the other end (step: tail)

Budapest (22.3) and Prague (29.6) trail, behind Bordeaux (40.3) and Madrid (42.5) [internal: velometer run set, LAU series of all 21 cities (classifier v4, mapped km)]. A low value can mean little infrastructure, little mapping, or infrastructure in tiers the headline leaves out: Prague's painted lanes rose from 56 to 190 km and Budapest's from 72 to 161 km, all in tier D. The middle of the table moved more: Wrocław passed Vienna for eighth, Kraków rose from 14th to 12th, Paris from 16th to 14th and Lyon from 19th to 17th, while Oslo slipped from 11th to 13th and Madrid from 15th to 18th.

> “The data featured in this dashboard only represents OSM contributions. The lower numbers may therefore reflect missing OSM data rather than the actual absence of cycling infrastructure in each area.”
>
> — European Cyclists' Federation (ECF) [2]

#### Indexed, who grew fastest on the map (step: growth)

Indexed to its own 2018 value, Ljubljana's mapped A+B reaches 192, Kraków's 184, Lyon's 175 and Paris's 171 [internal: velometer run set, LAU series of all 21 cities (classifier v4, mapped km)]. In km, Warsaw's mapped A+B rose most, by 235 km (from 528 to 763), ahead of Paris (+148), Wrocław (+137), Kraków (+135) and Ljubljana (+117). The densely mapped northern and Dutch cities barely moved: Helsinki stands at 100, Amsterdam 101, Stockholm 105 and Utrecht 106. Two cities map less A+B now than in 2018: Helsinki only just, 1,279 km against 1,283 km, and Berlin clearly, at 95, from one re-mapping step, not a trend.

#### Not every jump is new infrastructure (step: jumps)

Seven city years carry a km-jump flag, and in most of them the step is a change in how existing paths were mapped. Berlin's 2022 drop, from 1,677 to 1,494 km, is mappers redrawing road-side tracks as separate ways and retagging shared paths as footways [internal: velometer time-series explanation, berlin/lau/2022]. Ljubljana's 2021 step, 138 to 194 km, was a campaign that drew sidepaths as separate ways [internal: velometer time-series explanation, ljubljana/lau/2021]. Most of Oslo's 2021 step, 264 to 298 km, is footways retagged as combined foot and cycle paths [internal: velometer time-series explanation, oslo/lau/2021], and most of the 31 km of mapped A+B Prague gained in 2020 is park and riverside footways retagged as cycleways [internal: velometer time-series explanation, prague/lau/2020]. About half of Kraków's 2024 step of 33 km is retagging [internal: velometer time-series explanation, krakow/lau/2024]. Paris is different: its rise from 224 to 306 km between 2019 and 2021 coincides with the Plan Vélo and the 2020 coronapistes, but no official build figure is cited, so these remain mapped km only [internal: velometer time-series explanation, paris/lau/2020] [internal: velometer time-series explanation, paris/lau/2021].

Some jumps sit in the yardstick and carry no flag. In Warsaw the mapped main roads fell from 1,039 to 946 km between the 2024 and 2025 points, when expressways were retagged as motorways, which the headline does not count; the headline rose from 67.9 to 77.8 while A+B rose 4% [internal: velometer shift investigation, warsaw/lau/2025]. In Helsinki residential streets reclassified as tertiary roads lifted the main roads from 467 to 484 km, and the headline fell from 274.4 to 264.7 with A+B flat [internal: velometer shift investigation, helsinki/lau/2025]. Both describe the road map, not cycling infrastructure.

#### Inside one city, Berlin's 12 Bezirke (step: bezirke)

Berlin maps the most A+B of any city, 1,551 km, at a headline of 109.1, seventh [internal: velometer run set, LAU series of all 21 cities (classifier v4, mapped km)]. Inside the city the spread is wide: Neukölln maps 164.3 and Pankow 62.8 [internal: velometer Bezirk series (12 Bezirke, classifier v4)]. Mitte (75.2 to 90.7) and Tempelhof-Schöneberg (123.9 to 138.3) gained most since 2018, while Spandau fell from 149.3 to 109.8, most of it in 2022. The Senate's figures answer another question: its 21.2 km for 2025 are km of route that projects completed or improved [3]. We count all mapped infrastructure per road side: from 2023 to October 2026 the map gained 442 km of newly mapped way-sides, redrew 656 km, and A+B rose 35.6 km net [internal: velometer mapped change, Berlin, 2023-01-01 to current].

> “In 2025 wurden insgesamt 21,2 Kilometer Strecke neu gebaut oder verbessert. Zum Jahresende 2025 befanden sich weitere 17,1 Kilometer in Bau/Bauvorbereitung sowie 67,2 Kilometer in Planung.”
>
> *(In 2025 a total of 21.2 km of route were newly built or improved. At the end of 2025 a further 17.1 km were under construction or in preparation for construction and 67.2 km were being planned.)*
>
> — Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU) [3]

#### Against published figures (figures)

Published figures differ from ours along six dimensions, set out on the differences page. Scope: Clean Cities 2025, which covers 17 cities here, counts protected infrastructure only [4], and its Vienna figure rose from 384 to 625.1 km in July 2025, once roads with restricted motor access in traffic-calmed areas were counted [5]. Length: Clean Cities defines the road network it divides by, each road once whatever its lanes or directions, and gives no rule for how cycling km are measured. Berlin's 925 km sits by our centreline basis, 913.5 km, not our 1,550.7 km per side [internal: velometer reconciliation, berlin/cc_km]; Ljubljana's 251 km sits by our per-side 245 km [internal: velometer reconciliation, ljubljana/cc_ratio].

> “This includes cycle tracks but also shared foot and bike paths, pedestrian streets or greenways. It doesn't include cycle lanes that are painted on the road, nor cycle streets, nor living streets or shared spaces, nor shared bus lanes.”
>
> — Clean Cities Campaign [4]

> “The number of lanes or directions on a road does not affect the road network length, .i.e. a road with 3 lanes counts for the same as a single-lane road, a two-way street the same as a one-way street.”
>
> — Clean Cities Campaign [4]

Date: their data date from early 2025, ours from October 2026. Area: QECIO reports NUTS3 regions from data of January 2024 [6]. Where the region is the city the main roads agree closely: 2,153 against 2,150 km for Berlin [internal: velometer reconciliation, berlin (qecio_main_km row)]; elsewhere it covers a county, as Stockholm's 4,946 km of main roads against our 667 km show [internal: velometer reconciliation, stockholm/qecio_main_km]. Method: Clean Cities took most figures from the cities themselves [1], and its 822 km for Paris exceeds everything we map there across all tiers [internal: velometer reconciliation, paris/cc_km].

> “Each city administration was invited to provide local data and offer feedback on any missing or incomplete information. 34 out of the 36 cities provided data for this ranking. For the two cities which did not provide data and for any incomplete data, public data sources were used instead.”
>
> — Clean Cities Campaign [1]

**Sources**

1. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)
2. European Cyclists' Federation (ECF): [Quantifying Europe's Cycling Infrastructure using OSM (QECIO 2.1): Our Methodology (v2.10)](https://european-cyclists-federation.github.io/Documents/Methodology.pdf), 2024-01-11 (index, en)
3. Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU): [Fahrrad Berlin – Fortschrittsbericht 2025 (Anlage 1 to Hauptausschuss report rote Nr. 1733 E of 12 August 2026; scanned PDF, excerpts transcribed from the page images)](https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.E-v.pdf), 2026-08-12 (official, de)
4. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025, Annexes (methodology)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf) (ngo, en)
5. Clean Cities Campaign: [City Ranking 2025: Protected cycling infrastructure table](https://cleancitiescampaign.org/city-ranking-2025-cycling-infrastructure/), 2025-05-14 (ngo, en)
6. European Cyclists' Federation (ECF): [Quantifying Europe's Cycling Infrastructure using OSM (QECIO 2.1): Metadata](https://european-cyclists-federation.github.io/Documents/Metadata.pdf), 2024-01-11 (index, en)

## Why figures differ (explainer)

### Why the figures differ

A published figure and ours can both be correct and still be far apart, because they measure different things. Each comparison on a city's Figures tab is read along six dimensions: what is counted, what kind of km, how length is measured, when, where, and who measured. This page takes them once, each with an example from the 21 cities and, where the source states one, the source's own definition.

Our side is always the same: mapped km in OpenStreetMap, classified into tiers A to E, per road side, in the city proper (LAU), at a snapshot date. A rise on the map can be new infrastructure, catch-up mapping or retagging, so a match with a published figure does not prove either right, and a gap does not prove either wrong.

#### What is counted (dimension: scope)

Every figure counts a chosen set of facilities. Our headline, mapped A+B km per 100 km of main roads, takes tiers A and B, separated tracks and shared foot and cycle paths; painted lanes (D) and cycle streets and bus lanes (E) are measured but left out of it. Clean Cities 2025 counts protected infrastructure, quoted below: shared paths and pedestrian streets in, painted lanes and cycle streets out [1]. QECIO keeps cycle tracks, cycle lanes and shared paths as separate classes, each with its own definition [2].

> “This includes cycle tracks but also shared foot and bike paths, pedestrian streets or greenways. It doesn't include cycle lanes that are painted on the road, nor cycle streets, nor living streets or shared spaces, nor shared bus lanes.”
>
> — Clean Cities Campaign [1]

Copenhagen shows how far scope alone goes. The city counts 401 km of cykelsti for 2025, kerbed tracks, with painted lanes in a separate row [3]; our A+B of 582 km also holds shared paths. Scope can change after publication, too: in July 2025 Clean Cities raised Vienna from 384 to 625.1 km once traffic-calmed roads with restricted motor access were counted [4]. Against that wider scope our A+B is +6.5% from theirs [internal: velometer reconciliation, vienna/cc_km].

> “Explanation: A more detailed breakdown of traffic-calmed areas revealed roads with restricted motor vehicle access that are part of the cycling network. These have now been included.”
>
> — Clean Cities Campaign [4]

A ratio has a second scope: the road network it divides by. Our headline divides by main roads. Clean Cities divides by the entire public road network [1], and for that comparison we divide by all public roads as well; even then the networks differ, 2,700 km in theirs against 2,041 km in ours for Amsterdam [internal: velometer reconciliation, amsterdam/cc_network_km].

#### What kind of km (dimension: kind)

Our km are mapped km: what is in OpenStreetMap at the snapshot date, whenever mappers recorded it. Official series often count another kind of km. Berlin's Senate reports 21.2 km of route that projects completed or improved in 2025, from a project database at year end [5]. Its priority network is a planned network of about 870 km, of which 78.2 km had been implemented by May 2026 [6]. Vienna's 20.4 km for 2025 counts projects started that year, not finished ones, quoted below [7].

> “Die Bilanz zum Radwegeausbau 2025 enthält 53 Radinfrastrukturprojekte im Hauptradverkehrsnetz, mit deren Realisierung im Jahr 2025 begonnen wurde. Es handelt sich um 20,4 Kilometer, die im Jahr 2025 gestartet wurden.”
>
> *(The 2025 cycle path tally contains 53 cycling infrastructure projects in the main cycle network whose realisation began in 2025. They amount to 20.4 km started in 2025.)*
>
> — Mobilitätsagentur Wien GmbH (fahrradwien.at) [7]

Mapped change is a different quantity again. From 2023 to October 2026 Berlin's map gained 442 km of newly mapped way-sides and redrew 656 km, while A+B rose 35.6 km net [internal: velometer mapped change, Berlin, 2023-01-01 to current]. Completed km, started km, planned km and mapped km answer different questions; none of them confirms or refutes another.

#### How length is measured (dimension: length)

We count each side of a road: a street with a one-way track on both sides contributes twice its length. Clean Cities counts each road once in the road network it divides by, however many lanes or directions it has, quoted below [1], but gives no rule for its cycling km. QECIO counts one-way infrastructure at half length [2]. Vienna's own network total counts facilities on both sides of a street, as we do [8]. On two-sided streets the centreline roughly halves our km.

> “The number of lanes or directions on a road does not affect the road network length, .i.e. a road with 3 lanes counts for the same as a single-lane road, a two-way street the same as a one-way street.”
>
> — Clean Cities Campaign [1]

> “In some cases, we translated a single highway feature into two cycling infrastructure features (for example when cycleway:both is used or cycleway:left and cycleway:right on the same highway). For the length calculations, we divided the length of the unidirectional cycling infrastructure by two.”
>
> — European Cyclists' Federation (ECF) [2]

Clean Cities' figures use both bases: Berlin's 925 km sits by our centreline 913.5 km, not our 1,550.7 km per side [internal: velometer reconciliation, berlin/cc_km], and Ljubljana's 251 km by our per-side 245 km [internal: velometer reconciliation, ljubljana/cc_ratio]. In Oslo, where QECIO's region is the city, its total of 413 km of cycle infrastructure matches our 414 km counted on its half-length rule [internal: velometer reconciliation, oslo (qecio_total_km row)]. Many official figures state no basis at all; the Figures tab then says "basis not stated by the source".

#### When (dimension: date)

Our side is the OpenStreetMap snapshot of October 2026, with yearly points from January 2018. Clean Cities collected its data from December 2024 to February 2025 and took updates until April 2025, quoted below [9]; QECIO rests on data downloaded in January 2024 [10]. Where the map moved fast, a year or more between the two dates matters: Warsaw's mapped A+B went from 735 km in January 2025 to 763 km now.

> “Data collection took place from December 2024 to February 7, 2025, using the most up-to-date information”
>
> — Clean Cities Campaign [9]

> “PBF files downloaded 10-11 January 2024 from Geofabrik.”
>
> — European Cyclists' Federation (ECF) [10]

Our own yearly points move for reasons other than cycling, too. Warsaw's mapped main roads fell from 1,039 to 946 km between the 2024 and 2025 points, when expressways were retagged as motorways [internal: velometer shift investigation, warsaw/lau/2025], so which of our dates a ratio is set against changes it. And a mapping date is not a completion date: a path drawn in 2026 may have existed for years, and a retag dates the edit, not the path.

#### Where (dimension: area)

We measure the city proper (LAU) and, where it tells a different story, the functional urban area. Clean Cities refers to the municipality [9]. QECIO reports by NUTS3 region and clips each way at the region's boundary, quoted below [2]. BikeNetKit cuts with a city boundary file whose source it does not state [11].

> “The analysis was performed at NUTS-3 level, clipping the highway per NUTS-3 administrative boundary.”
>
> — European Cyclists' Federation (ECF) [2]

Where the NUTS3 region is the city, the main roads agree closely: 2,153 km in ours against 2,150 km in theirs for Berlin [internal: velometer reconciliation, berlin (qecio_main_km row)], and −0.6% for Warsaw [internal: velometer reconciliation, warsaw (qecio_main_km row)]. Where the region is larger, QECIO's km describe another place: Stockholms län has 4,946 km of main roads against our 667 km for the city [internal: velometer reconciliation, stockholm/qecio_main_km].

#### Who measured (dimension: method)

Our km come from OpenStreetMap through the velometer classifier. Clean Cities asked the city administrations for data and used public sources, OpenStreetMap among them, where none came, quoted below [9]; for a single city it does not say which applied [1]. QECIO and BikeNetKit read OpenStreetMap with their own rules [2] [12].

> “Each city administration was invited to provide local data and offer feedback on any missing or incomplete information. 34 out of the 36 cities provided data for this ranking. For the two cities which did not provide data and for any incomplete data, public data sources were used instead.”
>
> — Clean Cities Campaign [9]

A figure derived from OpenStreetMap cannot confirm ours. Paris's official cycle-route series is an extract of OpenStreetMap, quoted below [13], the map we read, so a match would only show the same source twice. Strasbourg's open data are drawn on the city's own road centreline network [14], a measure independent of ours. Clean Cities' 822 km for Paris exceeds everything we map there across all tiers and cannot be reproduced from OpenStreetMap [internal: velometer reconciliation, paris/cc_km].

> “Ces données sont une extraction de la base de OSM © Les Contributeurs d’OpenStreetMap”
>
> *(These data are an extract of the OSM database © OpenStreetMap contributors.)*
>
> — Ville de Paris, Paris Data [13]

**Sources**

1. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025, Annexes (methodology)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf) (ngo, en)
2. European Cyclists' Federation (ECF): [Quantifying Europe's Cycling Infrastructure using OSM (QECIO 2.1): Our Methodology (v2.10)](https://european-cyclists-federation.github.io/Documents/Methodology.pdf), 2024-01-11 (index, en)
3. Københavns Kommune, Teknik- og Miljøforvaltningen: [Mobilitetsredegørelse 2026](https://byudvikling.kk.dk/sites/default/files/2026-07/Mobilitetsredeg%C3%B8relse%202026_opt-a.pdf) (official, da)
4. Clean Cities Campaign: [City Ranking 2025: Protected cycling infrastructure table](https://cleancitiescampaign.org/city-ranking-2025-cycling-infrastructure/), 2025-05-14 (ngo, en)
5. Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU): [Fahrrad Berlin – Fortschrittsbericht 2025 (Anlage 1 to Hauptausschuss report rote Nr. 1733 E of 12 August 2026; scanned PDF, excerpts transcribed from the page images)](https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.E-v.pdf), 2026-08-12 (official, de)
6. Abgeordnetenhaus Berlin (answer of the Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt): [Schriftliche Anfrage 19/25987: Acht Jahre Mobilitätsgesetz – Zwischen Anspruch und Wirklichkeit im Radverkehr (answer of 20 May 2026)](https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-25987.pdf), 2026-05-20 (parliament, de)
7. Mobilitätsagentur Wien GmbH (fahrradwien.at): [Bilanz Radwegeausbau 2025 (Radwegoffensive 2025)](https://www.fahrradwien.at/wp-content/uploads/sites/2/2026/01/Radwegoffensive_2025_Bilanz.pdf) (official, de)
8. Stadt Wien – Verkehrsorganisation und technische Verkehrsangelegenheiten: [Zahlen und Fakten zum Wiener Radverkehrsnetz](https://www.wien.gv.at/verkehr/radverkehrsnetz-radwege-statistiken), 2026-01-21 (official, de)
9. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)
10. European Cyclists' Federation (ECF): [Quantifying Europe's Cycling Infrastructure using OSM (QECIO 2.1): Metadata](https://european-cyclists-federation.github.io/Documents/Metadata.pdf), 2024-01-11 (index, en)
11. BikeNetKit (GitHub, IT University of Copenhagen): [BikeNetKit dataexport: create_city_networks_from_pbf.ipynb (commit e2a5bcf)](https://github.com/BikeNetKit/dataexport/blob/e2a5bcff53a941bac757abc01a27d1ea54650fdd/scripts/create_city_networks_from_pbf.ipynb) (index, en)
12. Zenodo (M. Szell, M. Pessoa; IT University of Copenhagen): [Bicycle networks, street networks, and POIs for 403 European cities for BikeNetKit](https://zenodo.org/records/22271229), 2026-09-03 (index, en)
13. Ville de Paris, Paris Data: [Linéaire cyclable (en km), dataset description](https://opendata.paris.fr/explore/dataset/lineaire-cyclable-km/information/) (official, fr)
14. Ville et Eurométropole de Strasbourg, data.strasbourg.eu: [Aménagements cyclables au format BNAC, dataset description](https://data.strasbourg.eu/explore/dataset/amg_cycl_bnac/information/) (official, fr)

## City narratives

### Amsterdam: a full map that barely moves

*The headline went from 205.6 in 2018 to 203.0 in October 2026; the one visible shift, from tracks to shared paths in 2025, was a retag.*

#### From 2018 to now

Amsterdam's map is dense and changes little. In the city proper (LAU) the headline (mapped A+B km per 100 km of main roads) was 205.6 in 2018 and 203.0 in October 2026, and mapped A+B stayed between 852 and 867 km throughout [internal: velometer time series, amsterdam LAU and FUA (mapped km)].

What moved is the split inside it. Between the 2024 and 2025 points separated tracks (tier A) fell from 704 to 660 km and shared paths (tier B) rose from 160 to 207 km, with A+B flat. That is tag drift: in September 2024 hundreds of cycle paths that carry their footway on the same line lost `segregated=yes`, mostly in one contributor's edits, so the classifier now reads them as shared with pedestrians [internal: velometer shift investigation, amsterdam/lau/2025]. Retagging is not a change on the street. Painted lanes (tier D, 76 → 90 km) and cycle streets (tier E, 0.2 → 9.0 km) grew slowly.

The functional urban area (FUA) rose slowly, 134.1 → 138.6. Its one flagged year, 2022, was contraflow retagging that touched painted lanes only [internal: velometer time-series explanation, amsterdam/fua/2022].

#### Why the figures differ (figures)

Clean Cities counts 919 km of protected infrastructure [1]; our A+B is 862 km per side (−6%). We found no published city total, but the city's own definition of a fietspad, quoted below, matches that scope [2]. The gap is in the road network: Clean Cities divides by 2,700 km, we by 2,041 km (−24%), so its ratio is 34% against our 42.2% [internal: velometer reconciliation, amsterdam/cc_ratio and amsterdam/cc_network_km]. Which roads its network includes, and whether the city or OpenStreetMap supplied the data, is not stated. Their data date from early 2025, ours from October 2026. QECIO reports Groot-Amsterdam, a region larger than the city [internal: velometer reconciliation, amsterdam/qecio_main_km].

> “Verplichte fietspaden, onverplichte fietspaden en fiets/bromfietspaden zijn fysiek gescheiden van de rijbaan, dus (fysiek) niet toegankelijk voor auto’s.”
>
> *(Mandatory cycle paths, non-mandatory cycle paths and cycle/moped paths are physically separated from the carriageway, so (physically) not accessible to cars.)*
>
> — Gemeente Amsterdam, Ingenieursbureau (Maps Amsterdam) [2]

> “For this indicator, the entire public road network within the city area has been considered.”
>
> — Clean Cities Campaign [3]

**Sources**

1. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)
2. Gemeente Amsterdam, Ingenieursbureau (Maps Amsterdam): [Plusnet en Hoofdnet Fiets](https://maps.amsterdam.nl/fietsnetten/) (official, nl)
3. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025, Annexes (methodology)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf) (ngo, en)

### Barcelona: almost all tracks, growth until 2024

*Mapped A+B rose from 161 to 244 km between 2018 and October 2026, and the headline from 34.6 to 55.1 mapped A+B km per 100 km of main roads.*

#### Since 2018

Barcelona's map is nearly all one tier: separated tracks (tier A) hold 231 of the 244 mapped A+B km, and painted lanes barely appear, because the city's cycle infrastructure is mapped as cycleways [internal: velometer reconciliation explanation, barcelona/qecio_lanes_km]. A+B rose every year from 2018 to 2024, from 161 to 239 km, and has been nearly flat since. The headline (mapped A+B km per 100 km of main roads) went from 34.6 to 55.1.

The 2021 and 2022 points are flagged for a footway campaign led by one mapper, mostly in December 2020 and early 2021. Footways carry no tier. The cycling gain of 2021, 24.8 km, came separately, from cycleway mapping, for example on Carrer d'Aragó [internal: velometer time-series explanation, barcelona/lau/2021]. Part of that year's movement is existing cycleways gaining segregation tags, which moves them within tier A.

In the wider urban area (FUA) the 2021 step of 176 km is catch-up mapping, spread over 83 municipalities, about half of it drawn by one mapper [internal: velometer time-series explanation, barcelona/fua/2021]. That it was catch-up rather than new paths is inferred from that spread, not checked on the ground.

#### Why the figures differ (figures)

The Ajuntament's bike-lane network [1] and Clean Cities' 264 km of protected infrastructure both sit close to our A+B; ours is −7.7% from Clean Cities'. Neither says whether a two-sided street counts once or twice, and Clean Cities' data were collected by early 2025 [2]. A wider count of cycle routes, reported in the press, adds traffic-calmed streets with low speed limits [3], a category our tiers leave out. BikeNetKit counts more (−43.1%) because it includes living streets [internal: velometer reconciliation explanation, barcelona/bnk_network_km], and QECIO reports the whole province [internal: velometer reconciliation explanation, barcelona/qecio_main_km].

> “Aquestes actuacions se sumaran als 15,4 km de nous carrils bici ja construïts durant aquest mandat i als 5,24 km millorats, en el marc de l’estratègia de millora de la connectivitat i de la infraestructura. Actualment, la xarxa de carrils bici de Barcelona és de 268 km.”
>
> *(These works will add to the 15.4 km of new bike lanes already built this term and the 5.24 km improved, under the strategy to improve connectivity and infrastructure. Barcelona's bike lane network is currently 268 km.)*
>
> — Ajuntament de Barcelona, Servei de Premsa [1]

> “D'aquesta manera, sumant tots els recorreguts, carrers i carrils bici aptes per desplaçar-se en bicicleta, Barcelona ja té prop de 1.150 quilòmetres d'itineraris ciclistes a disposició dels ciutadans.”
>
> *(Thus, adding up all routes, streets and bike lanes suitable for cycling, Barcelona already has nearly 1,150 kilometres of cycle routes available to residents.)*
>
> — Ara [3]

> “Ratio of protected (i.e. physically separated through a barrier, height difference or distance from motorised traffic) cycling infrastructure total vs road network (in km)”
>
> — Clean Cities Campaign [2]

**Sources**

1. Ajuntament de Barcelona, Servei de Premsa: [Barcelona intervé en més de 42 km de carrils bici per incrementar la connectivitat entre els barris i millorar la infraestructura ciclista](https://ajuntament.barcelona.cat/premsa/2025/02/11/barcelona-interve-en-mes-de-42-km-de-carrils-bici-per-incrementar-la-connectivitat-entre-els-barris-i-millorar-la-infraestructura-ciclista/), 2025-02-11 (official, ca)
2. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)
3. Ara: [Barcelona ampliarà en 32 quilòmetres la xarxa de carrils bici](https://www.ara.cat/societat/ajuntament-barcelona-bici-bicing_1_4141511.html), 2021-10-09 (press, ca)

### Berlin: one re-mapping campaign, then a slow climb

*Mapped A+B km per 100 km of main roads went from 113.7 in 2018 to 109.1 in October 2026: one step down in a 2022 re-mapping campaign, a slow climb since.*

#### Since 2018

Berlin's headline, mapped A+B km per 100 km of main roads, was 113.7 in 2018 and 109.1 in October 2026; mapped A+B went from 1,640 to 1,551 km [internal: velometer time series, berlin/lau (classifier v4)]. The fall is one step, not a trend. The headline peaked at 117.0 in 2021 and stood at 104.3 in January 2022, after mappers redrew road-side tracks as separate ways and retagged many shared paths as footways where cycling is only allowed. That was a mapping campaign, not lost infrastructure [internal: velometer time-series explanation, berlin/lau/2022]. Since then the headline has risen in every year but 2024.

Outside A+B the map gained too. Painted lanes (tier D) went from 403 to 461 km, cycle streets and bus lanes (E) from 53 to 117 km, and lanes mapped with a physical buffer (C), absent in 2018, now come to 29 km [internal: velometer time series, berlin/lau (classifier v4)]. The functional urban area fell with the same campaign, which reached into Brandenburg, from 71.5 in 2021 to 64.7 in 2022, and is at 64.5 now [internal: velometer time series, berlin/fua (classifier v4)] [internal: velometer time-series explanation, berlin/fua/2022].

#### The 12 Bezirke

The 12 Bezirke diverge [internal: velometer Bezirk series (12 Bezirke, classifier v4)]. Neukölln maps densest (164.3), Pankow thinnest (62.8). Since 2018 Mitte (75.2 to 90.7) and Tempelhof-Schöneberg (123.9 to 138.3) gained most; Spandau fell most (149.3 to 109.8), the largest part of it in 2022.

#### Why the Senate's figures differ (figures)

The Senate's figures answer a different question [1]. Its 21.2 km for 2025 are km of route that projects completed or improved, taken from a project database at year end. The 20.5 km was a preliminary figure the administration called possibly incomplete [2]; the 9.8 km covers the Vorrangnetz alone [3], for which the progress report itself gives a smaller figure.

> “In 2025 wurden insgesamt 21,2 Kilometer Strecke neu gebaut oder verbessert. Zum Jahresende 2025 befanden sich weitere 17,1 Kilometer in Bau/Bauvorbereitung sowie 67,2 Kilometer in Planung.”
>
> *(In 2025 a total of 21.2 km of route were newly built or improved. At the end of 2025 a further 17.1 km were under construction or in preparation for construction and 67.2 km were being planned.)*
>
> — Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU) [1]

> “Die in diesem Bericht für das Jahr 2025 dargestellten Analysen zum Ausbau des Radnetzes Berlin basieren überwiegend auf einer verwaltungsübergreifenden, von der GB infraVelo GmbH (infraVelo) betriebenen Projekt-Datenbank „Radverkehr“. Alle Tabellen und Grafiken beziehen sich auf den Stichtag 31.12.2025.”
>
> *(The analyses of the expansion of Berlin's cycle network presented in this report for 2025 are based mainly on a cross-administration project database 'Radverkehr' operated by GB infraVelo GmbH. All tables and charts refer to the reference date 31 Dec 2025.)*
>
> — Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU) [1]

We count all mapped infrastructure per road side, whenever mappers record it. From 2023 to October 2026, 442 km of way-sides were newly mapped and 656 km redrawn, and A+B rose by 35.6 km net [internal: velometer mapped change, Berlin, 2023-01-01 to current]. The report's Vorrangnetz inventory used OpenStreetMap too, but only within that network. Neither set confirms or refutes the other.

> “Diese Bestandserhebung der Radinfrastruktur im Vorrangnetz wurde auf Grundlage von Open Street Maps-Daten durchgeführt und lag der Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU) zum Jahreswechsel 2025/2026 vor.”
>
> *(This inventory survey of the cycling infrastructure in the priority network was carried out on the basis of OpenStreetMap data and was available to the Senate Department (SenMVKU) at the turn of 2025/2026.)*
>
> — Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU) [1]

**Sources**

1. Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU): [Fahrrad Berlin – Fortschrittsbericht 2025 (Anlage 1 to Hauptausschuss report rote Nr. 1733 E of 12 August 2026; scanned PDF, excerpts transcribed from the page images)](https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.E-v.pdf), 2026-08-12 (official, de)
2. Der Tagesspiegel (dpa): [Senat verfehlt eigenes Ziel: In diesem Jahr wurden nur 20,5 Kilometer neue Radwege in Berlin gebaut (dpa; Senate figure given on request, before year end)](https://www.tagesspiegel.de/berlin/senat-hangt-eigenem-ziel-hinterher-205-kilometer-neue-radwege-in-berlin-gebaut-15065944.html), 2025-12-19 (press, de)
3. Abgeordnetenhaus Berlin (answer of the Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt): [Schriftliche Anfrage 19/25987: Acht Jahre Mobilitätsgesetz – Zwischen Anspruch und Wirklichkeit im Radverkehr (answer of 20 May 2026)](https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-25987.pdf), 2026-05-20 (parliament, de)

### Bordeaux: a painted-lane city, slow on separated paths

*Mapped A+B rose from 53 to 65 km between 2018 and October 2026, and the headline from 31.8 to 40.3 mapped A+B km per 100 km of main roads.*

#### Since 2018

Within the commune, Bordeaux has the smallest change of the French cities here. Mapped A+B moved between 51 and 57 km from 2018 to 2024 and only then rose, to 65 km now; the headline (mapped A+B km per 100 km of main roads) went from 31.8 to 40.3. Painted lanes (tier D) dominate the map and stayed roughly level, between 99 and 107 km. The tier that grew is E, bus lanes and cycle streets, from 21 to 49 mapped km. The 2021 dip in tier B, from 17 to 10 km, was not flagged and has no recorded explanation.

The wider urban area (FUA) tells a busier story: A+B rose from 850 to 1,278 km. Its 2019 step was led by one mapper drawing cycleways beside roads that were already on the map. In the same year a long cycle path, the Piste Roger Lapébie, dropped out of every tier through a retag and was back a year later [internal: velometer time-series explanation, bordeaux/fua/2019]. That is a change in the map, not on the ground. Since 2019 the FUA has grown every year, mostly in shared paths (tier B, from 218 to 515 km).

#### Why the figures differ (figures)

The Ville de Bordeaux's own figure includes bus lanes [1] and does not say how length is measured or whether a two-sided street counts twice. The Métropole's figures cover all its communes and include traffic-calmed and pedestrian streets [2], which none of our tiers counts; the regional audit chamber describes the same series as all types combined [3]. Bordeaux is not in the Clean Cities ranking. QECIO reports the Gironde département, hence its −97.6% gap on main roads; on that area the main roads agree, and the commune has more painted lanes and fewer separate tracks than the rest of Gironde [internal: velometer reconciliation explanation, bordeaux/qecio_main_km].

> “378 km d'aménagements cyclables (dont couloirs bus), soit + 36 km depuis 2020”
>
> *(378 km of cycle facilities (including bus lanes), i.e. +36 km since 2020.)*
>
> — Ville de Bordeaux [1]

> “En juin 2021, la Métropole était dotée de 1 506 km d’aménagements cyclables pour 1 022 km en 2015, soit une augmentation de 47% (+100% en 10 ans) : 348 km de pistes cyclables et voies vertes 367 km de bandes cyclables et couloirs bus 624 km de voies de circulation apaisée 167 km de voies piétonnes”
>
> *(In June 2021 the Métropole had 1,506 km of cycle facilities against 1,022 km in 2015, a 47% increase (+100% in 10 years): 348 km of cycle tracks and greenways, 367 km of cycle lanes and bus lanes, 624 km of traffic-calmed streets, 167 km of pedestrian streets.)*
>
> — Bordeaux Métropole [2]

> “évolution du linéaire des voies cyclables tous types confondus (bandes, pistes, zones apaisées, couloirs « bus&vélo ») sur le territoire de Bordeaux Métropole”
>
> *(change in the length of cycle ways of all types combined (lanes, tracks, traffic-calmed zones, bus-and-bike lanes) in Bordeaux Métropole.)*
>
> — Chambre régionale des comptes Nouvelle-Aquitaine [3]

**Sources**

1. Ville de Bordeaux: [Bordeaux à vélo](https://www.bordeaux.fr/p57231/circuler-a-velo) (official, fr)
2. Bordeaux Métropole: [3ème Plan vélo métropolitain 2021-2026](https://www.bordeaux-metropole.fr/sites/MET-BXMETRO-DRUPAL/files/2023-08/Plan_velo2021.pdf) (official, fr)
3. Chambre régionale des comptes Nouvelle-Aquitaine: [Bordeaux Métropole – Plan vélo, rapport d’observations définitives, exercices 2019 et suivants, deliberated 5 August 2025 (copy published by the Ville de Mérignac)](https://www.merignac.com/sites/default/files/2026-04/crc-bordeaux-metropole-plan-velo.pdf) (official, fr)

### Bratislava: a dip, then a steady climb

*The headline rose from 43.5 in 2018 to 58.7 in October 2026, after a fall in 2020 that was a retagging clean-up, not lost paths.*

#### Since 2018

Bratislava's mapped A+B went from 124 km in 2018 to 172 km in October 2026, and its headline, mapped A+B km per 100 km of main roads, from 43.5 to 58.7 [internal: velometer time series, bratislava/lau (classifier v4)]. The path was not smooth. A+B fell from 132 km in 2019 to 113 km in 2020 and passed its 2019 level again only in 2024. That fall was retagging during 2019: ways left the cycling tiers, the largest a long embankment path retagged as a footway, which was a cycleway again by late 2024 [internal: velometer shift investigation, bratislava/lau/2020]. From 2024 tier A rose fastest, from 63 to 90 km.

Painted lanes (D) more than tripled on the map, from 17 to 55 km per side. Since 2024 part of that is retagging of shared lanes into proper lanes, alongside lanes on roads that had no cycleway tag [internal: velometer reconciliation, bratislava/qecio_lanes_km]. The activity flag on the current point is a pedestrian mapping campaign of sidewalks and crossings; A+B moved normally [internal: velometer time-series explanation, bratislava/lau/current].

The functional urban area grew faster than the city, A+B from 284 to 443 km. Its 2022 jump is mostly newly mapped cycleways; the city's share of it was 15.5 km [internal: velometer time series, bratislava/fua (classifier v4)] [internal: velometer time-series explanation, bratislava/fua/2022].

#### Why the figures differ (figures)

Clean Cities 2025 and our figures roughly agree: it reports 186 km of protected infrastructure and 12% of the road network [1], against our 172 km and 13.2% [internal: velometer reconciliation, bratislava (cc_ratio, cc_km)]. QECIO measured the whole Bratislava region, more than five times the city's area, so its km are not the city's [internal: velometer reconciliation, bratislava/qecio_main_km]. The city reports km added by type, advisory lanes among them, and a total of its own without a stated length basis [2]; the local cycling NGO counted a new path on both sides of the road, as we do [3].

> “Z vyše štrnástich kilometrov, o ktoré sa sieť rozšírila, je 6,9 kilometra samostatných cyklistických komunikácií, 2,2 kilometra ochranných pruhov, 3,6 kilometra spoločného chodníka pre chodcov a cyklistov a 1,5 kilometra bicyklovej cesty. Cyklistická infraštruktúra v meste celkovo meria viac než 205 kilometrov.”
>
> *(Of the more than fourteen kilometres by which the network grew, 6.9 km are separate cycle tracks, 2.2 km advisory lanes, 3.6 km shared footpaths for pedestrians and cyclists and 1.5 km bicycle road. Cycling infrastructure in the city measures more than 205 km in total.)*
>
> — Hlavné mesto Slovenskej republiky Bratislava [2]

> “V katastri Vrakune pribudla nová zmiešaná cestička pre chodcov a cyklistov. Pred jej výstavbou tu chýbali dokonca aj chodníky. Spolu má dĺžku necelý kilometer (na jednej aj druhej strane).”
>
> *(In the Vrakuňa district a new shared path for pedestrians and cyclists was added. Before it was built there were not even footways here. In total it is just under a kilometre long (on one side and the other).)*
>
> — Cyklokoalícia [3]

**Sources**

1. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)
2. Hlavné mesto Slovenskej republiky Bratislava: [Cyklistická infraštruktúra v Bratislave sa rozširuje](https://bratislava.sk/spravy/cyklisticka-infrastruktura-v-bratislave-sa-rozsiruje), 2025-12-03 (official, sk)
3. Cyklokoalícia: [Bratislava: Čo pribudlo v roku 2025](https://cyklokoalicia.sk/2026/04/bratislava-co-pribudlo-v-roku-2025/), 2026-04-10 (ngo, sk)

### Budapest: slow A+B, painted lanes doubled

*The headline rose from 19.4 in 2018 to 22.3 in October 2026, the lowest of the 21 cities, while mapped painted lanes more than doubled.*

#### Since 2018

Budapest's map grew slowly and without flags. Mapped A+B in the city went from 196 km in 2018 to 231 km in October 2026, and the headline, mapped A+B km per 100 km of main roads, from 19.4 to 22.3, the lowest of the 21 cities [internal: velometer time series, budapest/lau (classifier v4)]. Tier A carried the gain, from 126 to 162 km; tier B stayed between 66 and 76 km.

The larger change is outside A+B. Painted lanes (D) rose from 72 to 161 km, with the biggest step between the 2023 and 2024 points, from 118 to 153 km. That step is lane tags added to existing roads, most of them last edited in late 2023; whether the markings were new or existing ones mapped late cannot be told from the data [internal: velometer shift investigation, budapest/lau/2024]. Bus lanes open to cycles (E) rose from 20 to 29 km. The headline counts neither tier.

The functional urban area grew faster than the city: A+B rose from 408 to 550 km, +35% against the city's +18% [internal: velometer time series, budapest/fua (classifier v4)].

#### Why the figures differ (figures)

External figures agree closely where they measure the same thing. QECIO's region is the city itself, and our main roads, tracks, lanes and shared paths are each within 6% of its numbers [internal: velometer reconciliation, budapest (QECIO rows)]. Clean Cities' 212 km sits near our 231 km; its 4% is rounded to a whole percent from its own km [internal: velometer reconciliation, budapest/cc_ratio]. BikeNetKit counts 588 km, more than twice our 260 km of tiers A, B and E, because it includes living streets, which no tier here counts [internal: velometer reconciliation, budapest/bnk_network_km]. City figures count other things, such as a city-managed inventory or a planned main network [1]. A 2024 press analysis called km a poor indicator and set an OpenStreetMap-based count against the statistics office's figure [2].

> “A hálózat kilométerben kifejezett hossza pedig valójában nem túl jó mutató, mert például a fővárosban sok helyen egyszerűen a járdára húztak egy-egy sárga vonalat, és ebből lett a kerékpárút, de ez nem nagyon tekinthető minőségi, modern megoldásnak.”
>
> *(The length of the network in kilometres is actually not a very good indicator, because in many places in the capital a yellow line was simply painted on the footway and that became the cycle path, which can hardly be considered a quality, modern solution.)*
>
> — Telex (G7) [2]

> “E szerint Budapesten 307 km kerékpárút volt 2024 januárjában, minden formát beleértve. Ez az adat harmadával magasabb, mint a KSH által 2022-ben nyilvántartott 210 km, az eltérés oka abban lehet, hogy az eltérő típusú infrastruktúrákat melyik forrás számolja kerékpárútnak és melyik nem.”
>
> *(According to this, Budapest had 307 km of cycle paths in January 2024, all forms included. That figure is a third higher than the 210 km recorded by the statistics office KSH for 2022; the difference may lie in which source counts which types of infrastructure as cycle paths.)*
>
> — Telex (G7) [2]

**Sources**

1. BKK Budapesti Közlekedési Központ Zrt.: [Kerékpárforgalmi Főhálózati Terv, 2. melléklet – Helyzetértékelés (7 October 2022; document of the Fővárosi Közgyűlés)](https://einfoszab.budapest.hu/File/DownloadDvD/118717?filename=f02_KFHT_helyzetert.pdf&prevcont=Session&prevaction=DvdItem&path=Tev%C3%A9kenys%C3%A9gre,+m%C5%B1k%C3%B6d%C3%A9sre+vonatkoz%C3%B3+adatok+/+D%C3%B6nt%C3%A9shozatal,+%C3%BCl%C3%A9sek+/+A+F%C5%91v%C3%A1rosi+K%C3%B6zgy%C5%B1l%C3%A9s+%C3%BCl%C3%A9sei&type=5&key=fovarosi-kozgyules-nyilvanos-ulesei&fileId=191823&sessionType=1&organizationtype=2&parentId=16335&parenttype=2), 2022-10-07 (official, hu)
2. Telex (G7): [Nem látszik, hogy ellenzéki vezetés alatt dübörögne a budapesti kerékpáros fejlesztés](https://telex.hu/g7/adat/2024/04/12/nem-latszik-hogy-ellenzeki-vezetes-alatt-duborogne-a-budapesti-kerekparos-fejlesztes), 2024-04-12 (press, hu)

### Copenhagen: kerbed tracks carry the gain

*Mapped A+B rose from 530 to 582 km between 2018 and October 2026, almost all of it in separated tracks; the 2025 dip in shared paths was retagging.*

#### From 2018 to now

In Copenhagen's city proper (LAU) the headline (mapped A+B km per 100 km of main roads) went from 213.9 in 2018 to 237.9 in October 2026, third of the 21 cities. Mapped A+B rose from 530 to 582 km (+10%), and separated tracks (tier A) carry almost all of the gain, 447 → 493 km [internal: velometer time series, copenhagen LAU and FUA (mapped km)]. Painted lanes (tier D) slipped from 40.2 to 36.5 km.

The one irregular year is 2025. Shared paths (tier B) dipped from 88.8 to 74.0 km and were back at 86.5 km on the 2026 snapshot, and the headline dipped with them (234.5 → 227.9). That is tag drift: during 2024 gravel paths lost their foot-and-cycle designation and left the tiers, and during 2025 most of them were retagged as shared cycleways and returned to B [internal: velometer shift investigation, copenhagen/lau/2025]. Retagging is not new or lost infrastructure.

The functional urban area (FUA) grew a little faster, A+B 4,632 → 5,234 km (+13%), but there the split moved the other way: tier A fell from 2,903 to 2,689 km while tier B rose from 1,729 to 2,545 km, most of it between 2019 and 2020 [internal: velometer time series, copenhagen LAU and FUA (mapped km)]. No investigation covers that step yet.

#### Why the figures differ (figures)

The city counts 401 km of cykelsti for 2025 [1] and Clean Cities 397 km of protected infrastructure [2]; our A+B is 582 km. Scope: a cykelsti is a kerbed track, painted lanes are a separate row, and our A+B also holds shared paths. The city's design guidance advises against painted lanes in new schemes [3]. Length: Copenhagen's tracks are mostly one-way pairs, one per road side; on the centreline ours is 359 km (−9% against Clean Cities) [internal: velometer reconciliation, copenhagen/cc_km]. Kind and date: theirs are existing km counted for 2025, ours mapped km in October 2026. Area: both are the municipality. Method: the city's own count against OpenStreetMap; whether Clean Cities used the city's figure is not stated.

> “I 2025 var der 401 km cykelsti i København. Heraf er der 66 km Grønne Ruter og 64 km supercykelsti.”
>
> *(In 2025 there were 401 km of cycle track (cykelsti) in Copenhagen. Of these, 66 km are Green Routes and 64 km are cycle superhighway.)*
>
> — Københavns Kommune, Teknik- og Miljøforvaltningen [1]

> “Cykelstier er udformet med kantsten mod kørebane og fortov som fysisk adskillelse mod fodgængere og bilister.”
>
> *(Cycle tracks (cykelstier) are built with kerbs towards the carriageway and the pavement as physical separation from pedestrians and motorists.)*
>
> — Københavns Kommune [3]

> “Der findes cykelbaner i dag i København, men cykelbaner frarådes ved nyanlæg.”
>
> *(Cycle lanes exist in Copenhagen today, but cycle lanes are advised against in new construction.)*
>
> — Københavns Kommune [3]

**Sources**

1. Københavns Kommune, Teknik- og Miljøforvaltningen: [Mobilitetsredegørelse 2026](https://byudvikling.kk.dk/sites/default/files/2026-07/Mobilitetsredeg%C3%B8relse%202026_opt-a.pdf) (official, da)
2. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)
3. Københavns Kommune: [Cykelfokus 2024: Københavns Kommunes retningslinjer for cykel- og vejprojekter (council agenda annex)](https://www.kk.dk/sites/default/files/agenda/03e7571c-7870-4344-95bf-6d33c5779242/81e1e2f8-dd62-415e-be0c-ea31526f3f0b-bilag-2.pdf) (official, da)

### Helsinki: a flat map at the top

*Mapped A+B stayed between 1,279 and 1,292 km from 2018 to October 2026; the headline fell from 276.2 to 262.3 because more streets were tagged as main roads, not because cycle paths went missing.*

#### From 2018 to now

Helsinki has the highest headline of the 21 cities, and its city map barely moved. Mapped A+B in the city proper (LAU) was 1,283 km in 2018 and 1,279 km in October 2026 [internal: velometer time series, helsinki LAU and FUA (mapped km)]. The headline still fell, from 276.2 to 262.3 mapped A+B km per 100 km of main roads, most of it between the 2024 and 2025 points (274.4 → 264.7).

That fall is a denominator change, not a loss of cycle paths. A+B stayed at 1,282 km across both points, while mapped main roads rose from 467 to 484 km, because during 2024 hundreds of residential streets were reclassified as tertiary roads [internal: velometer shift investigation, helsinki/lau/2025]. On the 2024 main-road km the 2025 headline would have stayed level.

Most of the city's network is shared foot and cycle paths: 943 of the 1,279 km are tier B, against 336 km of separated tracks (tier A). Painted lanes (tier D) are small but growing, 14 → 38 km.

The functional urban area (FUA) tells a different story. A+B rose from 5,018 to 5,742 km, while tier A fell from 909 to 589 km. Part of that fall is retagging: since 2024 cycleways outside the city gained foot tags and moved from A to B [internal: velometer reconciliation, helsinki/qecio_tracks_km].

#### Why the figures differ (figures)

Clean Cities counts 783 km of protected infrastructure for Helsinki [1]; our A+B is 1,279 km per side (+63%). Length is not the cause: most of the city's paths are two-way [2], so the centreline barely changes ours. Scope is: their figure lies between our tier A and A+B, so it counts fewer shared paths, though which ones is not stated [internal: velometer reconciliation, helsinki/cc_km]. The city's own figure for separate cycleways, quoted below, is close to our A+B; its date and method are not stated. QECIO reports the Helsinki-Uusimaa region, not the city. Baana figures count completed high-quality routes, a kind of km we do not measure.

> “Helsingissä on yli 1200 kilometriä erillisiä pyöräväyliä. Tämän lisäksi pyörällä ajetaan ajoradoilla siellä, missä erillisiä pyöräteitä ei ole.”
>
> *(Helsinki has more than 1,200 km of separate cycleways. In addition, people cycle on the carriageway where there are no separate cycle paths.)*
>
> — Helsingin kaupunki, kaupunkiympäristön toimiala [2]

> “Tällä hetkellä baanaa on valmistunut noin 33 kilometriä ja kantakaupungin tavoiteverkosta valmiina on noin 71 kilometriä.”
>
> *(At present about 33 km of baana has been completed, and about 71 km of the inner-city target network is complete.)*
>
> — Yle [3]

**Sources**

1. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)
2. Helsingin kaupunki, kaupunkiympäristön toimiala: [Pyöräväylien priorisointi- ja toteuttamisohjelma (Kaupunkiympäristön julkaisuja 2021:21)](https://www.hel.fi/static/liitteet/kaupunkiymparisto/julkaisut/julkaisut/julkaisu-21-21.pdf) (official, fi)
3. Yle: [Helsinki satsasi satoja miljoonia, ja se kannatti: pyöräilijät hehkuttavat baanoja, vaikka kaikki ei ole edes valmista](https://yle.fi/a/74-20240701), 2026-08-25 (press, fi)

### Kraków: mapped km nearly doubled, and half of one jump is retagging

*The headline rose from 40.2 to 72.6 mapped A+B km per 100 km of main roads between 2018 and October 2026, the steepest relative climb of the three Polish cities.*

#### From 2018 to now

Kraków's mapped A+B km in the city proper rose from 161 in 2018 to 296 in October 2026, up 84%, and the headline from 40.2 to 72.6. Tier A went from 112 to 192 km and tier B from 49 to 105 km; painted lanes stayed small, at 22 km now.

The largest step is the 2024 point, +33 km of A+B. About half of it is new ways and half is existing footways and paths retagged as designated cycle paths [internal: velometer time-series explanation, krakow/lau/2024], so part of that jump is a change of tags, not new infrastructure. The earlier flag, on 2022, is a tag change on contraflow lanes that leaves A+B on its normal course [internal: velometer time-series explanation, krakow/lau/2022].

The functional urban area grew from 202 to 541 mapped km. Its early jumps came largely from mappers adding long regional routes east of the city, the Wiślana Trasa Rowerowa in 2019 and Velo Raba in 2020 [internal: velometer time-series explanation, krakow/fua/2019].

#### Why the figures differ (figures)

The city's own totals use a broad definition that also counts footways where cycling is allowed and contraflow cycling in calmed streets, both outside our A+B [1], and they give neither a length basis nor a counting method. Clean Cities 2025 counts protected infrastructure [2]: its 229 km is below every OSM count near its date, and our per-side A+B is 29.3% above it. As for Warsaw, the reason may be that shared foot and cycle paths are left out, but that is an inference [internal: velometer reconciliation, krakow/cc_km]. Its road network of 2,128 km is wider than our 1,718 km, so its ratio is 11% against our 17.2%.

> “Na szeroko rozumianą infrastrukturę rowerową składają się: drogi dla rowerów, ciągi pieszo-rowerowe, chodniki z dopuszczonym ruchem rowerowym, pasy rowerowe, kontrapasy oraz tzw. kontraruch rowerowy, gdzie dopuszczona jest jazda rowerem „pod prąd” na ulicach jednokierunkowych w strefie uspokojonego ruchu drogowego, czyli z ograniczeniem prędkości do 30 km/h.”
>
> *(Cycling infrastructure in the broad sense comprises: cycle tracks, shared footpath/cycle paths, footways where cycling is permitted, cycle lanes, contraflow lanes and so-called contraflow cycling, where riding 'against the flow' is allowed on one-way streets in traffic-calmed zones, i.e. with a 30 km/h limit.)*
>
> — Urząd Miasta Krakowa (krakow.pl) [1]

> “Nieco mniej - blisko 410 km - ma Poznań. Kraków i Gdańsk to odpowiednio ok. 316 i 311 km tras rowerowych, a Łódź 260 km.”
>
> *(Somewhat less, close to 410 km, has Poznań. Kraków and Gdańsk have about 316 and 311 km of cycle routes respectively, and Łódź 260 km.)*
>
> — Portal Samorządowy [3]

> “This includes cycle tracks but also shared foot and bike paths, pedestrian streets or greenways. It doesn't include cycle lanes that are painted on the road, nor cycle streets, nor living streets or shared spaces, nor shared bus lanes.”
>
> — Clean Cities Campaign [2]

**Sources**

1. Urząd Miasta Krakowa (krakow.pl): [250 kilometrów infrastruktury rowerowej miasta](https://krakow.pl/aktualnosci/260628,1912,komunikat,250_kilometrow_infrastruktury_rowerowej_miasta.html), 2022-05-31 (official, pl)
2. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025, Annexes (methodology)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf) (ngo, en)
3. Portal Samorządowy: [Sieci tras rowerowych w miastach liczą już po kilkaset kilometrów. Znamy plany na 2026 rok (figures supplied by city halls)](https://www.portalsamorzadowy.pl/inwestycje/sieci-tras-rowerowych-w-miastach-licza-juz-po-kilkaset-kilometrow-znamy-plany-na-2026-rok,641875.html), 2026-01-04 (press, pl)

### Ljubljana: sidepaths redrawn, then a steady climb

*The headline rose from 46.5 to 73.5 mapped A+B km per 100 km of main roads between 2018 and October 2026; its largest step is mostly the same paths mapped a new way.*

#### From 2018 to now

Mapped A+B km in Ljubljana's city proper rose from 128 in 2018 to 245 in October 2026, and the headline from 46.5 to 73.5. The largest step sits at the 2021 point, 138 → 194 km. Our explanation finds a mapping campaign in late 2020: road sides lost their cycle-track tags and the sidepaths beside them were drawn as separate ways [internal: velometer time-series explanation, ljubljana/lau/2021]. Much of that step is existing paths mapped in a new way, not new infrastructure.

In 2022 and 2023 the same sidepaths were retagged from cycleway to path, which under classifier v4 moves almost nothing between tiers [internal: velometer time-series explanation, ljubljana/lau/2022]. Mapped painted lanes (tier D) went from 37 to 102 km. Since the January 2026 snapshot A+B rose again, from 228 to 245 km, as side paths were drawn as separate ways along a few roads at the city edge [internal: velometer shift investigation, ljubljana/lau/current]. Whether those paths are new on the ground cannot be told from the data.

The functional urban area nearly tripled, from 211 to 617 mapped km. After 2021 its flagged jumps come mostly from mapping outside the city; for 2025 the explanation infers from the tags of two ways that some of the new km is probably new infrastructure [internal: velometer time-series explanation, ljubljana/fua/2025].

#### Why the figures differ (figures)

Ljubljana's own figure states no length basis or counting date: the city's web page counts lanes on footways and carriageways together with separated tracks and shared paths [1], while our headline leaves lanes out. Clean Cities 2025 counts protected infrastructure only [2]. Its 251 km is close to our per-side A+B of 245 km (−2.4%), though the report does not say whether the city submitted it. Its road network of 1,649 km is wider than our 1,172 km, so its ratio is 15% against our 20.9% [internal: velometer reconciliation, ljubljana/cc_ratio]. QECIO counts the whole NUTS3 region around the city, not the municipality [internal: velometer reconciliation, ljubljana/qecio_main_km].

> “V Ljubljani je več kot 350 km urejenih kolesarskih površin v obliki kolesarskih pasov na pločniku ali vozišču, ločenih kolesarskih stez ter skupnih poti za pešce in kolesarje.”
>
> *(Ljubljana has more than 350 km of designated cycling surfaces in the form of cycle lanes on the footway or carriageway, separated cycle tracks and shared paths for pedestrians and cyclists.)*
>
> — Mestna občina Ljubljana [1]

> “This includes cycle tracks but also shared foot and bike paths, pedestrian streets or greenways. It doesn't include cycle lanes that are painted on the road, nor cycle streets, nor living streets or shared spaces, nor shared bus lanes.”
>
> — Clean Cities Campaign [2]

**Sources**

1. Mestna občina Ljubljana: [Hoja in kolesarjenje (ljubljana.si web page)](https://www.ljubljana.si/sl/ljubljana/mobilna/hoja-in-kolesarjenje) (official, sl)
2. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025, Annexes (methodology)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf) (ngo, en)

### Lyon: flat until 2020, then a rise that sped up

*Mapped A+B rose from 64 to 113 km between 2018 and October 2026, and the headline from 31.0 to 52.3 mapped A+B km per 100 km of main roads.*

#### Since 2018

Lyon's map barely moved at first: A+B stayed between 61 and 64 km from 2018 to 2020, and the headline (mapped A+B km per 100 km of main roads) slipped from 31.0 to 28.4. It then rose, slowly until 2023 and faster since: from 74 km in 2023 to 113 km now, with the headline from 33.9 to 52.3. Separated tracks (tier A) more than doubled, from 40 to 93 km. Painted lanes (tier D) are still the largest tier, up from 110 to 173 km.

The 2025 point is flagged for activity, but the spike was a July 2024 sidewalk and crossing campaign. Footways carry no tier, and that year's cycling gain came mostly from cycleways drawn beside roads [internal: velometer time-series explanation, lyon/lau/2025]. How much of the rise is new on the ground the map cannot say; the local cycling association's review of the Voies Lyonnaises programme gives its own count [1].

> “Sur les 250 km promis pour 2026, seuls 170 km (dont 60 km préexistants) seront livrés en 2026 : le réseau comporte encore de nombreuses discontinuités, qui constituent autant de points noirs soulevés par les cyclistes lors de l’enquête du Baromètre Vélo 2025.”
>
> *(Of the 250 km promised for 2026, only 170 km (including 60 km that already existed) will be delivered in 2026: the network still has many gaps, each a black spot raised by cyclists in the 2025 Baromètre Vélo survey.)*
>
> — La Ville à Vélo [1]

In the wider urban area (FUA) A+B rose from 543 to 894 km. Its 2026 step is ordinary mapping by many mappers, but part of it is retagging: mapped footways and tracks that became designated paths [internal: velometer time-series explanation, lyon/fua/2026]. That is a change in the map, not new infrastructure.

#### Why the figures differ (figures)

Clean Cities gives Lyon 14% protected, a ratio of protected km to the whole road network [2]. Our 17.7% counts each side of a road. On the centreline basis the gap shrinks to +7.6%, and against Clean Cities' own road network it matches their figure [internal: velometer reconciliation explanation, lyon/cc_ratio]. Both refer to the commune; their data were collected by early 2025, ours come from the October 2026 map. The Métropole's own total covers the whole Métropole and adds contraflow streets, greenways and paved shoulders [3], so it differs in area and scope. QECIO reports the Rhône département; measured on that area, the main roads agree [internal: velometer reconciliation explanation, lyon/qecio_main_km].

> “Ratio of protected (i.e. physically separated through a barrier, height difference or distance from motorised traffic) cycling infrastructure total vs road network (in km)”
>
> — Clean Cities Campaign [2]

> “Répartition des 1 208 kilomètres d’aménagements cyclables 57 km en accotement revêtu 367 km en bande cyclable 234 km en piste cyclable 92 km en couloir bus/vélo 229 km en double sens cyclable 228 km en voie verte”
>
> *(Breakdown of the 1,208 kilometres of cycle facilities: 57 km paved shoulder, 367 km cycle lane, 234 km cycle track, 92 km bus/bike lane, 229 km contraflow cycling, 228 km greenway.)*
>
> — Métropole de Lyon [3]

**Sources**

1. La Ville à Vélo: [Bilan du premier mandat des Voies Lyonnaises : un effort inédit pour la sécurisation des cyclistes, un réseau discontinu à poursuivre](https://lavilleavelo.org/2025/12/17/bilan-du-premier-mandat-des-voies-lyonnaises-un-effort-inedit-pour-la-securisation-des-cyclistes-un-reseau-discontinu-a-poursuivre/), 2025-12-17 (ngo, fr)
2. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)
3. Métropole de Lyon: [Plan vélo de la Métropole de Lyon (août 2024)](https://avelo.grandlyon.com/fileadmin/user_upload/pdf/GL_PlanVelo_FR_aout2024_BAT03.pdf) (official, fr)

### Madrid: slow growth under three years of footway mapping

*Mapped A+B rose from 282 to 353 km between 2018 and October 2026, while the headline moved only from 38.1 to 42.5 mapped A+B km per 100 km of main roads.*

#### Since 2018

Madrid's mapped A+B was flat from 2018 to 2020, at 282 and then 278 km, and has risen a little every year since, to 353 km now. The headline (mapped A+B km per 100 km of main roads) went from 38.1 to 42.5. Inside the total the map shifted between tiers: in 2021 tier A rose from 186 to 225 km while tier B fell from 93 to 63 km. That year was not flagged and has no recorded explanation.

From 2024 on, Madrid's activity flags are a pedestrian campaign. Mappers added tens of thousands of sidewalks and crossings, and the crossings split existing cycleways into pieces, so the number of tiered ways nearly doubled while A+B grew by only 8.5 km [internal: velometer time-series explanation, madrid/lau/2025]. Some cycleways also gained foot-access tags and moved from tier A to B. The current point is the same mapping continuing, not a new event [internal: velometer time-series explanation, madrid/lau/current]. The headline slipped from 43.1 to 42.5 during 2026 even as A+B rose, because more main-road km were mapped.

The wider urban area (FUA) rose from 973 to 1,196 km of A+B by 2026 and has slipped to 1,182 km since; that last change was not flagged and has no recorded explanation.

#### Why the figures differ (figures)

The city's network figure, as the press reported it from the city's mobility department [1], is more than three times our A+B. The official release behind it was not found, so the figure is secondary. It includes ciclocarriles, lanes shared with motor traffic [2]; our tiers leave such shared lanes out. Clean Cities' 8% protected sits close to our 7.7%, both against the whole road network of the municipio; their data were collected by early 2025 [3]. BikeNetKit's network is longer than ours (−26.3%) because it includes living streets [internal: velometer reconciliation explanation, madrid/bnk_network_km]. QECIO reports the whole Comunidad de Madrid [internal: velometer reconciliation explanation, madrid/qecio_main_km].

> “La red ciclista de la capital llega a los 1.167 kilómetros sumando un 11,4% más desde que José Luis Martínez-Almeida llegó a la Alcaldía en 2019, han informado desde el área de Urbanismo, Medio Ambiente y Movilidad, con Borja Carabante al frente.”
>
> *(The capital's cycle network reaches 1,167 kilometres, 11.4% more than when José Luis Martínez-Almeida became mayor in 2019, the Urban Planning, Environment and Mobility department headed by Borja Carabante reported.)*
>
> — Ultima Hora [1]

> “Ciclocarril: Carril especialmente acondicionado para el uso de la bicicleta en donde la circulación es compartida con el resto de vehículos, el ciclista no disfruta de un uso exclusivo o preferente.”
>
> *(Ciclocarril: a lane specially adapted for cycling where traffic is shared with other vehicles; the cyclist has no exclusive or preferential use.)*
>
> — Ayuntamiento de Madrid, Portal de datos abiertos [2]

> “Ratio of protected (i.e. physically separated through a barrier, height difference or distance from motorised traffic) cycling infrastructure total vs road network (in km)”
>
> — Clean Cities Campaign [3]

**Sources**

1. Ultima Hora: [La red ciclista de la capital llega a los 1.167 kilómetros y da un estirón de un 11,4% más desde que Almeida es alcalde (figures as reported from the city's Área de Urbanismo, Medio Ambiente y Movilidad)](https://www.ultimahora.es/noticias/comunidades/2026/03/31/2600335/red-ciclista-capital-llega-1167-kilometros-estiron-mas-desde-almeida-alcalde.html), 2026-03-31 (press, es)
2. Ayuntamiento de Madrid, Portal de datos abiertos: [Bici. Infraestructura ciclista, dataset description](https://datos.madrid.es/dataset/205107-0-vias-ciclistas) (official, es)
3. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)

### Oslo: a retag in 2020, then steady mapping

*The headline rose from 53.1 to 70.8 between 2018 and October 2026; its one large step came from footways retagged as combined foot and cycle paths.*

#### From 2018 to now

In Oslo kommune (LAU) mapped A+B rose from 261 km in 2018 to 341 km in October 2026, and the headline (mapped A+B km per 100 km of main roads) from 53.1 to 70.8 [internal: velometer time series, oslo LAU and FUA (mapped km)]. The one flagged step is the 2021 point, when A+B went from 264 to 298 km. Most of it is tag drift: during 2020 existing footways were retagged as combined foot and cycle paths, the way Norway's standard gang- og sykkelvei is mapped, and newly drawn ways added the rest [internal: velometer time-series explanation, oslo/lau/2021]. Retagging is not new infrastructure.

Shared paths (tier B) dominate throughout, 222 → 282 km, against 38 → 60 km of separated tracks (tier A). Painted lanes (tier D) rose from 111 to 161 km, most of it at the 2023 point (128 → 160 km). An evaluation commissioned by the city describes the network as mainly marked lanes [1]; in the mapped data shared paths are the largest group.

> “I Oslo består sykkelveinettet hovedsakelig av markerte sykkelfelt, og ikke sykkelinfrastruktur fysisk separert fra biltrafikken”
>
> *(In Oslo the cycle network consists mainly of marked cycle lanes, not cycling infrastructure physically separated from motor traffic)*
>
> — EY (Ernst & Young), commissioned by Oslo kommune [1]

The functional urban area (FUA) grew more, A+B 1,546 → 2,071 km, with its own flagged step in 2021: combined foot and cycle paths newly drawn in the surrounding municipalities, plus retagging [internal: velometer time-series explanation, oslo/fua/2021]. Tier A there fell from 268 to 161 km, in part because cycleways gained foot tags and moved to B.

#### Why the figures differ (figures)

Clean Cities counts 307 km of protected infrastructure for Oslo [2]; our A+B is 341 km per side, 11% above [internal: velometer reconciliation, oslo/cc_ratio]. Its data date from early 2025, ours from October 2026, and whether the city or OpenStreetMap supplied it is not stated. The city's own network figure, quoted below, includes shared paths, painted lanes and cycle tracks [3], so its scope is our tiers A, B and D; its length basis and method are not stated by the source. QECIO's region here is the city itself, and its total of 413 km of cycle infrastructure matches our 414 km counted on its half-length rule [internal: velometer reconciliation, oslo/qecio_tracks_km].

> “Oslo har per i dag et sykkelveinett på mer enn 290 km”
>
> *(Oslo today has a cycle network of more than 290 km)*
>
> — Oslo kommune, Bymiljøetaten [3]

> “Sykkeltilrettelegging i dag (gang- og sykkelveier, sykkelfelt og sykkelveier)”
>
> *(Cycling provision today (shared walking and cycling paths, painted cycle lanes and cycle tracks))*
>
> — Oslo kommune, Bymiljøetaten [3]

**Sources**

1. EY (Ernst & Young), commissioned by Oslo kommune: [Evaluering av Oslo kommunes sykkelstrategi 2015-2025, sluttrapport](https://www.ey.com/content/dam/ey-unified-site/ey-com/no-no/insights/government-public-sector/documents/ey-evaluering-av-oslo-kommunes-sykkelstrategi-2015-2025-sluttrapport.pdf) (official, nb)
2. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)
3. Oslo kommune, Bymiljøetaten: [Sykkelkart](https://www.oslo.kommune.no/gate-transport-og-parkering/sykkel/sykkelkart/) (official, nb)

### Paris: two fast years, then a steady climb

*Mapped A+B rose from 209 to 357 km between 2018 and October 2026, and the headline from 34.8 to 63.1 mapped A+B km per 100 km of main roads.*

#### Since 2018

Most of Paris's rise falls in two years. Between 2019 and 2021 mapped A+B went from 224 to 306 km, and the headline (mapped A+B km per 100 km of main roads) from 37.5 to 51.9. The 2020 step is cycleways that mappers drew during 2019, while the city's 2015–2020 Plan Vélo ran; no official figure for what was finished that year is cited [internal: velometer time-series explanation, paris/lau/2020]. In the same years contraflow lanes were retagged, which moved a diagnostic count, not the tiers. The 2021 step is the temporary coronapistes of 2020 as mappers recorded them [internal: velometer time-series explanation, paris/lau/2021]; the city's 2021–2026 plan set out to make them permanent.

> “Doté d’un budget de 250 millions d’euros, son objectif est de faire de Paris une ville 100 % cyclable en déployant un total de 180 km d’aménagements cyclables d’ici la fin de la mandature : 130 km de nouvelles pistes cyclables et la pérennisation d’ici 2024 des 52 km de coronapistes.”
>
> *(With a budget of 250 million euros, its aim is to make Paris 100% cyclable by deploying 180 km of cycle facilities by the end of the term: 130 km of new cycle tracks and making the 52 km of coronapistes permanent by 2024.)*
>
> — Paris en Selle [1]

After a flat 2022 and 2023, the 2024 and 2025 points are flagged for activity, which was mostly footway mapping, tens of thousands of new footways in 2023 alone; footways carry no tier [internal: velometer time-series explanation, paris/lau/2024]. Cycling A+B kept its usual pace, to 346 km in 2025 and 357 km now. Separated tracks (tier A, 181 to 332 km) carry almost all of the gain; painted lanes (tier D) went from 127 to 147 km.

The wider urban area (FUA) grew more evenly, from 2,326 to 3,726 mapped km of A+B. Its one flagged year, 2019, was ordinary catch-up mapping by many hands, not a campaign or an import [internal: velometer time-series explanation, paris/fua/2019].

#### Why the figures differ (figures)

The city's yearly cycle-route length counts much more than our A+B: lanes, bus lanes open to bikes, pedestrian streets and contraflow cycling as well as tracks [2]. It is dated to the start of each year; we read the October 2026 map. It is also not independent of ours: the city extracts it from OSM, the map we read, so it cannot confirm or refute our km. Clean Cities' 822 km of protected infrastructure (48% of the road network) exceeds everything we map in Paris across all tiers [internal: velometer reconciliation explanation, paris/cc_km]; Clean Cities took most cities' figures from the cities themselves [3]. QECIO, also measuring OSM, lands within +9.3% of our tracks.

> “Le linéaire pour une année donnée correspond au cumul au 1er janvier des itinéraires cyclables sous forme de piste, voie verte, bande, couloir bus ouverts aux vélos, voies et chemins fermés à la circulation générale, voies piétonnes ouvertes aux vélos et doubles sens cyclable simples sur le territoire de la ville de Paris.”
>
> *(The length for a given year is the total at 1 January of cycle routes in the form of tracks, greenways, lanes, bus lanes open to bicycles, roads and paths closed to general traffic, pedestrian streets open to bicycles and simple contraflow cycling on the territory of the City of Paris.)*
>
> — Ville de Paris, Paris Data [2]

> “Ces données sont une extraction de la base de OSM © Les Contributeurs d’OpenStreetMap”
>
> *(These data are an extract of the OSM database © OpenStreetMap contributors.)*
>
> — Ville de Paris, Paris Data [2]

**Sources**

1. Paris en Selle: [Engagements du Plan vélo – Observatoire du Plan Vélo de Paris](https://observatoire.parisenselle.fr/engagements/) (ngo, fr)
2. Ville de Paris, Paris Data: [Linéaire cyclable (en km), dataset description](https://opendata.paris.fr/explore/dataset/lineaire-cyclable-km/information/) (official, fr)
3. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)

### Prague: shared paths and painted lanes

*The headline rose from 18.7 in 2018 to 29.6 in October 2026, while mapped painted-lane km more than tripled.*

#### Since 2018

Prague's mapped A+B rose from 182 km in 2018 to 289 km in October 2026, and its headline, mapped A+B km per 100 km of main roads, from 18.7 to 29.6, 20th of the 21 cities [internal: velometer time series, prague/lau (classifier v4)]. Most of the map's change is on the road: painted lanes (D) went from 56 to 190 km per side, cycle streets and bus lanes (E) from 20 to 42 km.

The one flagged jump, in 2020, is mostly retagging. In early 2019 mappers turned park and riverside footways where cycling was allowed into cycleways that pedestrians may still use, and added some new cycleways [internal: velometer time-series explanation, prague/lau/2020]. Pedestrians are permitted on those ways, so the classifier rates them tier B, as it does most of Prague's mapped cycleways: tier B (245 km) is more than five times tier A (45 km), and was already over four times A in 2018 [internal: velometer time series, prague/lau (classifier v4)].

The functional urban area follows the same pattern: A+B rose from 325 to 540 km, most of it in tier B, and its 2020 step is the same retagging plus new suburban cycleways [internal: velometer time series, prague/fua (classifier v4)] [internal: velometer time-series explanation, prague/fua/2020].

#### Why the figures differ (figures)

Clean Cities 2025 puts Prague at 248 km of protected infrastructure and 6% of the road network [1]. On its method we get 8.5%: our A+B is 17% higher and our road network is 3,423 km against its 4,093 km, and the two gaps compound [internal: velometer reconciliation, prague/cc_ratio]. The length basis is not the cause, and the date gap does not explain the km: we already had more at the start of 2025. We found no published city total for cycling facilities; the city's route system counts routes, which need not be signed or carry any facility [2].

> “This includes cycle tracks but also shared foot and bike paths, pedestrian streets or greenways. It doesn't include cycle lanes that are painted on the road, nor cycle streets, nor living streets or shared spaces, nor shared bus lanes.”
>
> — Clean Cities Campaign [3]

> “Trasy mohou a nemusí být opatřeny orientačním značením v terénu, trasa může být realizována také za pomoci vhodných cykloopatření.”
>
> *(Routes may or may not carry wayfinding signs on the ground; a route can also be realised by means of suitable cycling measures.)*
>
> — Institut plánování a rozvoje hl. m. Prahy (IPR Praha) [2]

**Sources**

1. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)
2. Institut plánování a rozvoje hl. m. Prahy (IPR Praha): [Systém celoměstských cyklotras hlavního města Prahy, Aktualizace 10/2021, průvodní zpráva (Příloha č. 1 k usnesení Rady HMP č. 418 ze dne 7. 3. 2022)](https://iprpraha.cz/assets/files/files/506ba6ec042dbcfbd30a0ebf0f4dbf87.pdf), 2022-03-07 (official, cs)
3. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025, Annexes (methodology)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf) (ngo, en)

### Stockholm: a steady total, with tracks overtaking shared paths

*The headline moved only from 257.9 to 261.0 between 2018 and October 2026, while years of small retags moved km from shared paths to separated tracks.*

#### From 2018 to now

Stockholm stays near the top of the 21 cities throughout. In the city proper (LAU) mapped A+B went from 944 km in 2018 to 991 km in October 2026 (+5%), and the headline from 257.9 to 261.0 mapped A+B km per 100 km of main roads, never below 249.7 or above 262.5 [internal: velometer time series, stockholm LAU and FUA (mapped km)]. No year is flagged.

Inside that steady total the split moved. Separated tracks (tier A) rose from 315 to 415 km, while shared foot and cycle paths (tier B) fell from 629 to 577 km. This is gradual tag drift alongside newly drawn ways, not one sweep [internal: velometer shift investigation, stockholm/lau/2018-current]: shared paths gained `segregated=yes` and moved to A, other cycleways gained foot tags and moved to B, and some cycleways became footways and left the tiers. The largest steps fell between 2020 and 2021 and between 2022 and 2023, each spread over many contributors. Retagging is not new infrastructure. Painted lanes (tier D) stay small, 38 → 48 km.

The functional urban area (FUA) tells a growth story the city does not: A+B rose from 3,272 to 3,906 km (+19%), most of it in tier B (2,022 → 2,635 km), so most of the newly mapped km lie outside the city [internal: velometer time series, stockholm LAU and FUA (mapped km)].

#### Why the figures differ (figures)

The city's own network figure, quoted below, counts separate cycle tracks, shared walking and cycling paths and painted lanes together [1]. Scope: that is our tiers A, B and D, 991 km of A+B plus 48 km of lanes. Its length basis, date and method are not stated by the source; ours are per road side, October 2026 and OpenStreetMap. Area: QECIO reports Stockholms län, a county far larger than the city, with 4,946 km of main roads against our 667 km [internal: velometer reconciliation, stockholm/qecio_main_km], so its figures are no check on the city. BikeNetKit, also based on OpenStreetMap, counts 1,102 km against our 995 km of tiers A, B and E (−10%) [2].

> “Stockholm har ungefär 117 mil cykelvägar, både egna cykelbanor, kombinerade gång- och cykelbanor och cykelfält.”
>
> *(Stockholm has about 117 Swedish miles (about 1,170 km) of cycleways, comprising separate cycle tracks, combined walking and cycling paths, and painted cycle lanes.)*
>
> — Stockholms stad, trafikkontoret [1]

**Sources**

1. Stockholms stad, trafikkontoret: [Cykelvägar](https://cykla.stockholm/cykelvagar/) (official, sv)
2. Zenodo (M. Szell, M. Pessoa; IT University of Copenhagen): [Bicycle networks, street networks, and POIs for 403 European cities for BikeNetKit](https://zenodo.org/records/22271229), 2026-09-03 (index, en)

### Strasbourg: high from the start, reshuffled between A and B

*Mapped A+B rose from 184 to 241 km between 2018 and October 2026; already in 2018 the headline was 123.2 mapped A+B km per 100 km of main roads.*

#### Since 2018

Strasbourg starts far ahead of the other French cities: in 2018 the map already held more A+B km than main-road km. A+B grew slowly and steadily, from 184 to 241 km, and the headline (mapped A+B km per 100 km of main roads) from 123.2 to 136.1. The headline dipped from 132.6 to 116.9 in 2021 although A+B rose, because the main-road length it divides by went from 150 to 176 mapped km that year. The year was not flagged, so no cause is recorded.

The larger change is inside A+B. Tier B, shared foot and cycle paths, rose from 28 to 69 km while tier A stayed between 156 and 172 km. Part of that is tagging, not new paths: in spring 2024 mappers swept the city's cycle paths, adding segregation and designation tags and turning some cycleways into shared paths [internal: velometer time-series explanation, strasbourg/lau/2025]. Tier A fell and tier B rose that year while their sum moved normally. A 2022 footway campaign shows in the activity flags but not in the tiers [internal: velometer time-series explanation, strasbourg/lau/2023]. Mapped painted lanes fell from 58 to 45 km.

The wider urban area (FUA) shows the same shift: tier B grew from 201 to 426 km and now nearly equals tier A at 428 km.

#### Why the figures differ (figures)

The official network figure [1] is more than twice our A+B. The page does not say whether it covers the commune or the whole Eurométropole, which facilities it counts, how length is measured or at what date. The city's open data are drawn on its own road centreline network in the national BNAC schema [2], not taken from OSM, so they are a measure independent of ours. Strasbourg is not in the Clean Cities ranking. QECIO reports the Bas-Rhin département, which is why its main-road km sit −95.3% away from ours; measured on that area, the main roads agree [internal: velometer reconciliation explanation, strasbourg/qecio_main_km].

> “Avec plus de 600 km d’itinéraires cyclables, Strasbourg propose le 1er réseau vélo de France.”
>
> *(With more than 600 km of cycle routes, Strasbourg offers France's leading cycle network.)*
>
> — Ville et Eurométropole de Strasbourg [1]

> “Données issues du filaire de voie de l'Eurométropole de Strasbourg structurées dans un schéma permettant de modéliser et définir les aménagements cyclables sur le territoire national : la Base Nationale des Aménagements Cyclables (BNAC).”
>
> *(Data derived from the Eurométropole de Strasbourg road centreline network, structured in a schema for modelling and defining cycle facilities nationally: the national cycle facility database (BNAC).)*
>
> — Ville et Eurométropole de Strasbourg, data.strasbourg.eu [2]

> “We researched 37 European countries, including all 27 EU member states, and the information was gathered at NUTS 3 level (Nomenclature of territorial units for statistics).”
>
> — European Cyclists' Federation (ECF) [3]

**Sources**

1. Ville et Eurométropole de Strasbourg: [Strasbourg à vélo](https://www.strasbourg.eu/a-velo) (official, fr)
2. Ville et Eurométropole de Strasbourg, data.strasbourg.eu: [Aménagements cyclables au format BNAC, dataset description](https://data.strasbourg.eu/explore/dataset/amg_cycl_bnac/information/) (official, fr)
3. European Cyclists' Federation (ECF): [Quantifying Europe's Cycling Infrastructure using OSM (QECIO 2.1): Our Methodology (v2.10)](https://european-cyclists-federation.github.io/Documents/Methodology.pdf), 2024-01-11 (index, en)

### Utrecht: small gains on a dense map

*The headline rose from 179.7 in 2018 to 193.6 in October 2026, partly because fewer main-road km were mapped; inside A+B, km drifted from tracks to shared paths.*

#### From 2018 to now

Utrecht's headline (mapped A+B km per 100 km of main roads) rose from 179.7 in 2018 to 193.6 in October 2026; mapped A+B rose more modestly, from 341 to 360 km [internal: velometer time series, utrecht LAU and FUA (mapped km)]. The rest is the denominator: mapped main roads in the city fell slightly, from 190 to 186 km.

Inside A+B the split shifted. Separated tracks (tier A) went from 336 to 317 km, shared paths (tier B) from 5.0 to 43.6 km. Cycle streets (tier E) rose from 10 to 27 km and painted lanes (tier D) moved from 51 to 48 km [internal: velometer time series, utrecht LAU and FUA (mapped km)].

No year in the city series is flagged, and the city's own move from A to B has not been traced way by way. The functional urban area (FUA), where A+B rose from 1,216 to 1,269 km, shows how such shifts arise: during 2019 mappers moved cycle streets from a non-standard tag to `cyclestreet=yes`, which shifted km into tier E, outside the headline, and cycleways that gained `foot=yes` moved from A to B [internal: velometer time-series explanation, utrecht/fua/2020]. Retagging of this kind is not new infrastructure.

#### Why the figures differ (figures)

No current official total was found for the city. A historical-society article gives older figures that keep cycle paths apart from painted lanes, quoted below [1]; that is roughly our tiers A and B against tier D, but the date is 2012 and the source is secondary. The city grits a main cycle path network [2], a maintenance scope, not a total. Area: QECIO reports the whole province, with 2,324 km of main roads against our 423 km for the city [internal: velometer reconciliation, utrecht/qecio_main_km], so it is no benchmark. BikeNetKit, also from OpenStreetMap, counts 420 km against our 387 km of tiers A, B and E (−8%) [3]; which boundary it uses is not stated by the source.

> “In 2012 telde Utrecht hierdoor 245 kilometer fietspad en 90 kilometer fietsstrook.”
>
> *(As a result, in 2012 Utrecht had 245 km of cycle path and 90 km of cycle lane.)*
>
> — Historische Vereniging Oud-Utrecht [1]

> “De gemeente is verantwoordelijk voor de gladheidbestrijding en strooit bij verwachte gladheid dag en nacht op ongeveer 400 km hoofdfietspaden en belangrijke bruggen.”
>
> *(The city is responsible for winter maintenance and, when ice is expected, grits about 400 km of main cycle paths and important bridges day and night.)*
>
> — Gemeente Utrecht [2]

**Sources**

1. Historische Vereniging Oud-Utrecht: [Hoe Utrecht fietsstad werd (reprint of a 2015 Tijdschrift Oud-Utrecht article)](https://oud-utrecht.nl/nieuws/1049-hoe-utrecht-fietsstad-werd), 2022-04-18 (ngo, nl)
2. Gemeente Utrecht: [Actieplan Utrecht fietst! 2015-2020: Samen op weg naar wereldfietsstad](https://api1.ibabs.eu/publicdownload.aspx?site=utrecht&id=19971) (official, nl)
3. Zenodo (M. Szell, M. Pessoa; IT University of Copenhagen): [Bicycle networks, street networks, and POIs for 403 European cities for BikeNetKit](https://zenodo.org/records/22271229), 2026-09-03 (index, en)

### Vienna: a late, steady rise

*Mapped A+B km per 100 km of main roads rose from 74.6 in 2018 to 89.1 in October 2026, most of it since 2024.*

#### Since 2018

Vienna's headline, mapped A+B km per 100 km of main roads, went from 74.6 in 2018 to 89.1 in October 2026, and mapped A+B from 558 to 666 km [internal: velometer time series, vienna/lau (classifier v4)]. Until 2024 it stayed between 73.8 and 79.7; since then it has risen every year, to 83.0 in 2025 and 87.3 in 2026. Mapped separated tracks (tier A) carry most of the gain, from 239 to 314 km. Shared foot and cycle paths (B) rose from 320 to 352 km, cycle streets and bus lanes (E) from 18 to 41 km.

The one flagged year, 2025, is tag drift, not new infrastructure: mappers replaced the old contraflow tag `cycleway=opposite_lane` on one-way streets [internal: velometer time-series explanation, vienna/lau/2025]. That touched painted lanes (D) only, which have stayed between 252 and 285 km since 2018 [internal: velometer time series, vienna/lau (classifier v4)].

The functional urban area rose more evenly, from 18.1 to 22.8, with a different mix: there tier A shrank from 603 to 512 km while tier B grew from 683 to 1,105 km [internal: velometer time series, vienna/fua (classifier v4)].

#### Why the city's figures differ (figures)

Vienna's own network total counts every facility type on both sides of a street, including contraflow streets, traffic-calmed areas and signed routes [1], so it covers far more than A+B. The 2025 tally of 20.4 km counts projects in the main network that started that year, not finished ones [2]. Clean Cities first printed 14%; in July 2025 it raised Vienna to 22.0% after roads with restricted motor access in traffic-calmed areas were included in the count [3]. On Clean Cities' method our ratio is 22.7%, +3% against the corrected figure, and the road networks agree [internal: velometer reconciliation, vienna (cc_ratio, cc_network_km)].

> “Das Radverkehrsnetz umfasst sämtliche Radverkehrsanlagen in Wien. Seit dem Jahr 2018 werden die tatsächlichen Längen der verschiedenen Anlagearten gezählt, womit auch (unterschiedliche) Anlagen auf beiden Seiten einer Straße erfasst werden. Derzeit beträgt die Länge des Radverkehrsnetzes in Wien circa 1.811 Kilometer.”
>
> *(The cycle network comprises all cycling facilities in Vienna. Since 2018 the actual lengths of the different facility types have been counted, so that (different) facilities on both sides of a street are also recorded. The cycle network in Vienna is currently about 1,811 km long.)*
>
> — Stadt Wien – Verkehrsorganisation und technische Verkehrsangelegenheiten [1]

> “Die Bilanz zum Radwegeausbau 2025 enthält 53 Radinfrastrukturprojekte im Hauptradverkehrsnetz, mit deren Realisierung im Jahr 2025 begonnen wurde. Es handelt sich um 20,4 Kilometer, die im Jahr 2025 gestartet wurden.”
>
> *(The 2025 cycle path tally contains 53 cycling infrastructure projects in the main cycle network whose realisation began in 2025. They amount to 20.4 km started in 2025.)*
>
> — Mobilitätsagentur Wien GmbH (fahrradwien.at) [2]

> “Explanation: A more detailed breakdown of traffic-calmed areas revealed roads with restricted motor vehicle access that are part of the cycling network. These have now been included.”
>
> — Clean Cities Campaign [3]

**Sources**

1. Stadt Wien – Verkehrsorganisation und technische Verkehrsangelegenheiten: [Zahlen und Fakten zum Wiener Radverkehrsnetz](https://www.wien.gv.at/verkehr/radverkehrsnetz-radwege-statistiken), 2026-01-21 (official, de)
2. Mobilitätsagentur Wien GmbH (fahrradwien.at): [Bilanz Radwegeausbau 2025 (Radwegoffensive 2025)](https://www.fahrradwien.at/wp-content/uploads/sites/2/2026/01/Radwegoffensive_2025_Bilanz.pdf) (official, de)
3. Clean Cities Campaign: [City Ranking 2025: Protected cycling infrastructure table](https://cleancitiescampaign.org/city-ranking-2025-cycling-infrastructure/), 2025-05-14 (ngo, en)

### Warsaw: steady tracks, and a shorter yardstick in 2025

*The headline rose from 53.4 to 82.3 mapped A+B km per 100 km of main roads between 2018 and October 2026; its biggest step came from retagged expressways, not from cycle paths.*

#### From 2018 to now

Inside the city, Warsaw's mapped A+B km rose from 528 in 2018 to 763 in October 2026, and the headline from 53.4 to 82.3. Almost all of it is separated track: tier A went from 395 to 598 km, while shared paths (tier B) moved from 134 to 165 km. Painted lanes grew from 46 to 65 km. No year in the city series is flagged.

The largest headline step, 67.9 to 77.8 in 2025, is not a cycling change. A+B rose by a normal 4% that year, but the main roads the headline divides by fell from 1,039 to 946 km: expressways that had been mapped as trunk roads were retagged as motorways in late 2024, and motorways are not in the denominator [internal: velometer shift investigation, warsaw/lau/2025]. Most of that step is a shorter yardstick, not more mapped cycle km.

The functional urban area grew much faster, from 833 to 2,033 mapped km. Its flagged jumps of 2019 to 2021 were ordinary mapping activity spread over the suburban gminas, with no campaign or import, partly ways retagged from construction to cycleway, which dates the mapping rather than the path [internal: velometer time-series explanation, warsaw/fua/2019].

#### Why the figures differ (figures)

The road authority ZDM counts a network that includes cycle lanes and contraflow lanes, which we keep in tier D outside the headline [1], and its yearly summaries report km added in the year, a different kind of km from ours. Clean Cities 2025 counts protected infrastructure [2]; our per-side A+B is 20.9% above its 631 km. Every OSM count near its date is higher, which suggests it leaves out shared foot and cycle paths, though that is an inference [internal: velometer reconciliation, warsaw/cc_km]. Its road network of 4,300 km is wider than our 3,386 km, so its ratio is 15% against our 22.5%.

> “Obecnie sieć rowerowa w stolicy liczy już 544 km (w tym 406 km dróg dla rowerów, 70 km ciągów pieszo-rowerowych oraz 68 km pasów i kontrapasów). 2/3 z nich ma nawierzchnię asfaltową.”
>
> *(The cycle network in the capital now totals 544 km (including 406 km of cycle tracks, 70 km of shared footpath/cycle paths and 68 km of cycle lanes and contraflow lanes). Two thirds of it has an asphalt surface.)*
>
> — Zarząd Dróg Miejskich w Warszawie (ZDM) [1]

> “Ogółem w 2025 roku sieć rowerowa w stolicy wydłużyła się o aż 55 km. W międzyczasie rozpoczęliśmy też budowę kolejnych tras, m.in. w al. „Solidarności” czy al. Jana Pawła II. Rekordowa jest też długość wyremontowanych tras – aż 20 km.”
>
> *(Overall, in 2025 the cycle network in the capital grew by as much as 55 km. Meanwhile we also started building further routes, including on al. Solidarności and al. Jana Pawła II. The length of renovated routes is also a record, as much as 20 km.)*
>
> — Zarząd Dróg Miejskich w Warszawie (ZDM) [3]

> “This includes cycle tracks but also shared foot and bike paths, pedestrian streets or greenways. It doesn't include cycle lanes that are painted on the road, nor cycle streets, nor living streets or shared spaces, nor shared bus lanes.”
>
> — Clean Cities Campaign [2]

**Sources**

1. Zarząd Dróg Miejskich w Warszawie (ZDM): [Rekordowy sezon inwestycji rowerowych](https://zdm.waw.pl/aktualnosci/rekordowy-sezon-inwestycji-rowerowych/), 2018-07-05 (official, pl)
2. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025, Annexes (methodology)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf) (ngo, en)
3. Zarząd Dróg Miejskich w Warszawie (ZDM): [Podsumowujemy 2025 rok na stołecznych ulicach](https://zdm.waw.pl/aktualnosci/podsumowujemy-2025-rok-na-stolecznych-ulicach/), 2026-01-05 (official, pl)

### Wrocław: mapped km up at every point

*The headline rose from 62.0 to 95.3 mapped A+B km per 100 km of main roads between 2018 and October 2026, with no unexplained jump on the way.*

#### From 2018 to now

Wrocław's map shows an even climb. Mapped A+B km in the city proper rose from 261 in 2018 to 399 in October 2026, higher at every yearly point, and the headline went from 62.0 to 95.3. Separated tracks (tier A) grew from 178 to 258 km and shared foot and cycle paths (tier B) from 83 to 141 km. Painted lanes stay minor, 22 to 32 km.

The only flag on the city series sits on the 2018 starting point: in 2017 a single mapper drew much of the pedestrian network, footways rather than cycleways [internal: velometer time-series explanation, wroclaw/lau/2018]. Because 2018 is the first point, no change in km is attributed to it.

The functional urban area grew faster, from 332 to 701 mapped km. Its flagged steps of 2020, 2022 and 2023 were mapping activity in the suburban gminas, partly ways retagged from construction to cycleway. Such a retag dates the mapping, not the path on the ground [internal: velometer time-series explanation, wroclaw/fua/2023].

#### Why the figures differ (figures)

The city hall's figures count wider networks than ours: its "cyclist-friendly routes" include contraflow lanes and traffic-calmed zones, which our headline does not count [1], and its other totals give no definition or length basis. Clean Cities 2025 counts protected infrastructure, shared foot and cycle paths included [2]. Our per-side A+B of 399 km is 12.3% above its 355 km, and 6.8% above on the centreline basis, with a year and a half between the two dates [internal: velometer reconciliation, wroclaw/cc_ratio]. The ratio differs more: its road network of 1,769 km is wider than our 1,340 km [internal: velometer reconciliation, wroclaw/cc_network_km], so its 20% stands against our 29.8%.

> “Urząd miejski w swoim oświadczeniu zaznacza, że poza ujętymi w raporcie drogami rowerowymi, ciągami pieszo-rowerowymi i rowerowymi pasami ruchu, w mieście istnieją też inne trasy „przyjazne rowerzystom”. Urzędnicy szacują ich długość na 1,4 tys. km. Chodzi tu m.in. o kontrapasy i strefy uspokojonego ruchu.”
>
> *(In its statement the city hall stresses that besides the cycle tracks, shared footpath/cycle paths and cycle lanes covered by the report, there are other 'cyclist-friendly' routes in the city. Officials estimate their length at 1,400 km. These include contraflow lanes and traffic-calmed zones.)*
>
> — wroclife.pl [1]

> “We Wrocławiu - jak podaje magistrat - taka infrastruktura liczy 428 km.”
>
> *(In Wrocław, according to the city hall, such infrastructure totals 428 km.)*
>
> — Portal Samorządowy [3]

> “This includes cycle tracks but also shared foot and bike paths, pedestrian streets or greenways. It doesn't include cycle lanes that are painted on the road, nor cycle streets, nor living streets or shared spaces, nor shared bus lanes.”
>
> — Clean Cities Campaign [2]

**Sources**

1. wroclife.pl: [Raport NIK ws. ścieżek rowerowych we Wrocławiu. Miasto dumne, aktywiści mają inne wnioski](https://wroclife.pl/artykul/2953/raport-nik-ws-sciezek-rowerowych-we-wroclawiu-miasto-dumne-aktywisci-maja-inne-wnioski), 2023-04-28 (press, pl)
2. Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025, Annexes (methodology)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf) (ngo, en)
3. Portal Samorządowy: [Sieci tras rowerowych w miastach liczą już po kilkaset kilometrów. Znamy plany na 2026 rok (figures supplied by city halls)](https://www.portalsamorzadowy.pl/inwestycje/sieci-tras-rowerowych-w-miastach-licza-juz-po-kilkaset-kilometrow-znamy-plany-na-2026-rok,641875.html), 2026-01-04 (press, pl)
