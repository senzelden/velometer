# M8 organisation research log (Task 3)

Retrieved 2026-10-07. Profiles: `content/organisations/*.yaml` (9). Mapping:
`config/organisations.yaml`. New sources: `content/sources/orgs.yaml` (28 sources, every one
reached; all their excerpts found on the live page by `velometer content --check --online`).
Sources already in the registry (`central.yaml`, `cross.yaml`, `north.yaml`, accessed
2026-10-06 in M7) are cited as they stand; the online check cannot read PDF text, so each cited PDF
was downloaded again on 2026-10-07 and its excerpts checked by script against `pdftotext` output
(result in the last column). Downloads are kept outside the repository and never committed. No
archive snapshot was requested.

Facts and quotes about a body come only from these external sources; our own documents are never
quoted. Where a profile says what we think, the sentence says "in our reading".

The first research pass ended in a crash before its log was written. Its sources are all in the
registry and were re-reached for this log; its list of searches that found nothing was lost. No
source was unreachable on 2026-10-07. The "Not found" lines below are the absences the profiles
state; they come from the first pass and were not searched again.

## 1. Coverage

| Pair or publisher | Organisation |
| --- | --- |
| figures.csv `*`/`clean_cities_2025` (17 cities), reconcile `cc_*` | `clean_cities` |
| reconcile `qecio_*` (`qecio_v2_10`) | `ecf` |
| reconcile `bnk_network_km` (`bikenetkit_v1`) | `bikenetkit` |
| figures.csv `berlin/official`, reconcile `official_new_km`; plan `berlin_rvp_2021` publisher; report rows publisher `senmvku` | `senmvku` |
| figures.csv `berlin/changing_cities`, reconcile `official_new_km` | `changing_cities` |
| figures.csv `copenhagen/official` | `copenhagen_kommune` |
| figures.csv `vienna/mobilitaetsagentur_wien` | `mobilitaetsagentur_wien` |
| report rows publisher `abgeordnetenhaus` (Drucksachen) | `abgeordnetenhaus` |
| Berlin plan publisher named in spec §3.2 (no row yet in `config/plans/`) | `infravelo` |

`velometer content --check` checks this coverage mechanically and passes.

## 2. Sources per organisation

Status: **reached** = fetched on 2026-10-07 and the excerpts / the claim found in the text.

### Clean Cities Campaign (`clean_cities`)

| Source id | URL | Status | Supports |
| --- | --- | --- | --- |
| cc-what-we-do | https://cleancitiescampaign.org/what-we-do/ | reached | network of organisations; hosted by T&E; "shape city, national and European policy" |
| cc-ranking-2025-page | https://cleancitiescampaign.org/city-ranking-2025/ | reached | 36 cities; three indicators named in the legend (school streets, safe speeds, protected cycling infrastructure) |
| te-funders | https://www.transportenvironment.org/about-us/funders | reached | T&E funding mix, 49 member organisations |
| paris-fr-cc-ranking-2025 | https://www.paris.fr/pages/paris-ville-europeenne-la-plus-adaptee-a-la-mobilite-des-enfants-31537 | reached | Paris cites its first place (quote) |
| cities-today-cc-ranking-2025 | https://cities-today.com/paris-tops-ranking-for-child-friendly-urban-travel/ | reached | the report's calls on governments and the Commission |
| cc2025-cycling-table (cross.yaml) | https://cleancitiescampaign.org/city-ranking-2025-cycling-infrastructure/ | reached | Vienna update 384.1 → 625.1 km; "UPDATE (JULY 2025)" checked on the page |
| cc2025-report (cross.yaml) | https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf | reached, 8/8 excerpts in pdftotext | metric, city data 34/36, area, collection dates |
| cc2025-annexes (cross.yaml) | https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf | reached, 8/8 | definition, ECF OSM fallback, ratio not share |

Not found: a funding statement for the campaign itself (only T&E's); any source showing the ranking
changed a city's plan. The profile says both.

### European Cyclists' Federation (`ecf`)

| Source id | URL | Status | Supports |
| --- | --- | --- | --- |
| ecf-about | https://www.ecf.com/en/about-us/about-ecf/ | reached | founded 1983, Brussels, non-profit; 70+ members in 40+ countries; footer: LIFE Programme and European Cycling Industries support |
| ecf-2024-breakthroughs | https://www.ecf.com/en/news/-2024-a-year-of-breakthroughs-for-cycling/ | reached | advocacy for the Declaration (quote); EGUM co-chaired by ECF |
| ec-declaration-cycling | https://transport.ec.europa.eu/transport-themes/urban-transport/european-declaration-cycling_en | reached | Declaration signed 2024 by Parliament, Council, Commission |
| qecio-site | https://european-cyclists-federation.github.io/ | reached | purpose: no official European source |
| qecio-methodology (cross.yaml) | https://european-cyclists-federation.github.io/Documents/Methodology.pdf | reached, 10/10 | NUTS 3, clipping, half-length rule, disclaimer |
| qecio-metadata (cross.yaml) | https://european-cyclists-federation.github.io/Documents/Metadata.pdf | reached, 2/2 | extracts of 10–11 January 2024 |

Not found: a city or government adopting QECIO figures as its own (stated as such).

### BikeNetKit (`bikenetkit`)

| Source id | URL | Status | Supports |
| --- | --- | --- | --- |
| bikenetkit-github-org | https://github.com/BikeNetKit | reached | toolkit, NERDS since 2019, started 2026, audience, funders, stance |
| bikenetkit-gisruk-2026 | https://zenodo.org/records/19390654 | reached | NERDS / ITU affiliation; "ad hoc" planning (quote); aimed at planners |
| bikenetkit-zenodo (cross.yaml) | https://zenodo.org/records/22271229 | reached | 403 cities, simplified networks, summer 2026 |
| bikenetkit-export-notebook (cross.yaml) | https://github.com/BikeNetKit/dataexport/blob/e2a5bcff53a941bac757abc01a27d1ea54650fdd/scripts/create_city_networks_from_pbf.ipynb | reached | city boundaries, cities above 100k |
| bikenetkit-pbi-filter (cross.yaml) | https://github.com/BikeNetKit/growbikenet/blob/8820875fcb1f363a743f2ce512e231a06a2337d9/growbikenet/constants.py | reached; `filter-head` fails the online check only because GitHub's HTML escapes the quotes, 2/2 in the raw file | the protected-infrastructure filter |

Not found: any city or parliament citing BikeNetKit figures (stated as such).

### Changing Cities (`changing_cities`)

| Source id | URL | Status | Supports |
| --- | --- | --- | --- |
| changing-cities-verein | https://changing-cities.org/verein/ | reached | origin in Netzwerk Lebenswerte Stadt / Volksentscheid; 1,480 supporting members; own claim on the Mobilitätsgesetz |
| changing-cities-transparenz | https://changing-cities.org/transparenz/ | reached | founded 2016; European Climate Foundation grant > 10 % of the 2025 budget |
| changing-cities-volksentscheid | https://changing-cities.org/kampagnen/volksentscheid-fahrrad/ | reached | 105,425 signatures on 14 June 2016; law negotiated, passed 28 June 2018 |
| klimareporter-radgesetz-2018 | https://klimareporter.de/verkehr/berlin-bekommt-radgesetz | reached | independent press: activists co-drafted the law (quote) |
| berlin-mobg-page | https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrspolitik/mobilitaetsgesetz/ | reached | Senate: citizens' impulses fed into the act |
| berlin-changing-cities-monitor (central.yaml) | https://changing-cities.org/kampagnen/verkehrswende-monitor/ | reached | own measurement, 31.12.2025, target network 2,699.8 km |
| berlin-fortschrittsbericht-2025 (central.yaml) | https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.E-v.pdf | reached; text layer incomplete (pdftotext yields 19 kB), excerpts not machine-checkable: they were transcribed from page images in M7 (`docs/review/m7-sources-central.md`) | Senate RVN 2,398.3 km |

Not found: a published description of how the Verkehrswende-Monitor measures (stated as such). The
association's seat is not in the page text (behind a link), so the profile says "registered
association (e.V.)" without a city.

### SenMVKU (`senmvku`)

| Source id | URL | Status | Supports |
| --- | --- | --- | --- |
| berlin-mobg-page | as above | reached | promulgated 5 July 2018 |
| berlin-radfortschrittsbericht-page | https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrsplanung/radverkehr/radprojekte/radfortschrittsbericht/ | reached | annual report covers Senate, infraVelo, districts; route length since 2022, not comparable |
| berlin-dpa-fortschrittsbericht-hauptausschuss | https://www.nordkurier.de/regional/brandenburg/bericht-senat-liess-viele-mittel-fuer-radverkehr-liegen-4840670 | reached | report for the Hauptausschuss; 27 of 82.4 million euros |
| berlin-tagesspiegel-radwegestopp-2023 | https://www.tagesspiegel.de/berlin/sobald-auch-nur-ein-parkplatz-wegfallt-berliner-senatsverwaltung-stoppt-vorerst-radwegprojekte-9992884.html | reached (lead paragraph; rest paywalled) | June 2023 stop request (quote) |
| infravelo-ueber-uns, infravelo-organisation, infravelo-faq | see infraVelo | reached | name since May 2023; responsibility with SenMVKU and districts; funder |
| berlin-fortschrittsbericht-2025 (central.yaml) | as above | see above | scope, data basis, reference date, revisions |
| berlin-drs-19-25987 (central.yaml) | https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-25987.pdf | reached, 6/6 in pdftotext | written-question answer as a source of `official` rows |
| berlin-tagesspiegel-dpa-2025-12 (central.yaml) | https://www.tagesspiegel.de/berlin/senat-hangt-eigenem-ziel-hinterher-205-kilometer-neue-radwege-in-berlin-gebaut-15065944.html | reached | 20.5 km in Dec 2025, below its target |

### infraVelo (`infravelo`)

| Source id | URL | Status | Supports |
| --- | --- | --- | --- |
| infravelo-ueber-uns | https://www.infravelo.de/ueber-uns/ | reached | founded mid-2017 on behalf of the Senate; subsidiary of Grün Berlin |
| infravelo-organisation | https://www.infravelo.de/ueber-uns/organisation/ | reached | priorities lie with SenMVKU |
| infravelo-faq | https://www.infravelo.de/ueber-uns/fragen-und-antworten/ | reached | public-budget funding; no own projects (quote); central database since 2020, quarterly district updates; cloud database developed by infraVelo; project map; 3–4 steering rounds per year and district with SenMVKU (all checked in the page text) |
| berlin-fortschrittsbericht-2025, berlin-dpa-fortschrittsbericht-hauptausschuss | as above | see above | the report rests mainly on the database |

### Abgeordnetenhaus (`abgeordnetenhaus`)

| Source id | URL | Status | Supports |
| --- | --- | --- | --- |
| agh-arbeitsweise | https://www.parlament-berlin.de/das-parlament/arbeitsweise | reached | three tasks: legislation, election of the governing mayor, scrutiny "durch Fragen und die Anforderungen von Berichten"; budget act |
| agh-parlamentarische-anfragen | https://www.parlament-berlin.de/dokumente/parlamentarische-anfragen | reached | any member may ask in writing; answer within three weeks; PARDOK (quote) |
| berlin-drs-19-25987 (central.yaml) | as above | reached | title "Acht Jahre Mobilitätsgesetz – Zwischen Anspruch und Wirklichkeit im Radverkehr", answer of 20 May 2026 (checked on PDF p. 1) |
| berlin-mobg-amendment-2026 (central.yaml) | https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/gvbl/g26250713.pdf | reached, 2/2 in pdftotext | 2030 / 2035 deadlines; main-road exception |
| changing-cities-volksentscheid, berlin-mobg-page | as above | reached | act passed 28 June 2018 |

### Mobilitätsagentur Wien (`mobilitaetsagentur_wien`)

| Source id | URL | Status | Supports |
| --- | --- | --- | --- |
| mobilitaetsagentur-ueber-uns | https://mobilitaetsagentur.at/ueber-uns | reached | subsidiary of the City of Vienna; bound by its objectives |
| drahtesel-mobilitaetsagentur-2016 | https://www.drahtesel.or.at/fuenf-jahre-mit-blum/ | reached | created by the red-green government soon after it took office; Blum in post since autumn 2011 and head of the agency ("leitet Blum die Mobilitätsagentur"); about two million budget; "communications department" |
| vienna-radwegeausbau-bilanz-2025 (central.yaml) | https://www.fahrradwien.at/wp-content/uploads/sites/2/2026/01/Radwegoffensive_2025_Bilanz.pdf | reached, 5/5 in pdftotext | 53 projects started; measurement; exclusions (quote) |
| vienna-radverkehrsnetz-fakten (central.yaml) | https://www.wien.gv.at/verkehr/radverkehrsnetz-radwege-statistiken | reached | both sides counted since 2018 |
| vienna-mobilitaetsagentur-2026 (central.yaml) | https://mobilitaetsagentur.at/radfahren/radverkehrsplanung | reached | Radweg-Offensive (name checked on the page); 2026: 33 projects, 12.5 km |
| vienna-orf-radwegenetz-2025 (central.yaml) | https://wien.orf.at/stories/3296850/ | reached | 2025 programme around 24 km |

Not found: a current budget figure for the agency; the profile gives the 2016 Drahtesel figure as
dated.

### City of Copenhagen (`copenhagen_kommune`)

| Source id | URL | Status | Supports |
| --- | --- | --- | --- |
| kk-klima-miljoe-teknikforvaltningen | https://www.kk.dk/om-kommunen/forvaltninger/teknik-og-miljoeforvaltningen | reached | administration responsible for running and developing the city; cycling effort |
| kk-br-cykelstrategi-2024 | https://www.kk.dk/dagsordener-og-referater/Borgerrepr%C3%A6sentationen/m%C3%B8de-02052024/referat/punkt-15 | reached | May 2024 vote for a new cycling strategy, 45 to 9 (quote) |
| copenhagen-mobilitetsredegorelse-2026 (north.yaml) | https://byudvikling.kk.dk/sites/default/files/2026-07/Mobilitetsredeg%C3%B8relse%202026_opt-a.pdf | reached, 4/4 in pdftotext | 401 km in 2025; strategy documents 2011–2025 |
| copenhagen-verdens-bedste-cykelby (north.yaml) | https://byudvikling.kk.dk/mobilitet/verdens-bedste-cykelby | reached | bicycle account replaced by the mobility report from 2021 |
| copenhagen-cykelfokus-2024 (north.yaml) | https://www.kk.dk/sites/default/files/agenda/03e7571c-7870-4344-95bf-6d33c5779242/81e1e2f8-dd62-415e-be0c-ea31526f3f0b-bilag-2.pdf | reached, 3/3 in pdftotext | cykelsti / cykelbane definitions |

## 3. Claims changed in this pass

Removed or reworded because the source did not say it:

- Mobilitätsagentur: "created it in 2011, with the city's cycling commissioner at its head".
  Drahtesel dates Blum's start to autumn 2011 and says the agency was created "soon after" the
  red-green government took office, not in which year. Now: created soon after the government
  took office; led by the commissioner, in post since autumn 2011.
- SenMVKU: "Mobilitätsgesetz, in force since July 2018". The source gives the promulgation date
  only. Now: "promulgated on 5 July 2018".
- Abgeordnetenhaus: "Questions are its main tool of scrutiny". The source calls written questions
  "ein wichtiges Mittel" and names questions and requested reports as its means of scrutiny. Now
  cited to `agh-arbeitsweise` with both.
- Copenhagen: "now named" (a renaming we inferred from the URL slug) and "Strategy is decided by
  the City Council" (a general rule cited to a single vote). Now: the council instructs its
  committees on strategy by vote, citing that vote.
- ECF: "co-chairs" (present tense, from a 2024 article). Now "co-chaired by ECF ... in 2024".
- infraVelo: "has no political mandate of its own" was stated as fact; it is our reading and now
  says so.
- BikeNetKit: "research the group has run since 2019" became "a research community that NERDS
  kick-started in 2019", as the README says.
- Changing Cities: "in Berlin" dropped from the legal form (seat not in the page text).

Trimmed for length only (no change of substance): Clean Cities (319 → 300 words, profile prose
plus dimension values, citations excluded) and Changing Cities (303 → 299).

No claim was left unverified. Every cited sentence was checked against its source's excerpts
(verbatim on the live page, or in the re-downloaded PDF's text) and, where it says more than an
excerpt, against the fetched page text; for the scanned Fortschrittsbericht 2025, against the M7
hand transcription.
