# M8 content review

Review stop (plan Task 8). Four verdicts are needed: **Profiles**, **Plans**, **Overlay** and **Counters**. Everything below is rendered from the files on branch `m8`:

- the nine organisation profiles (`content/organisations/`);
- the plans and progress figures (`config/plans/plans.yaml`, `reports.csv`);
- the Berlin plan page (`content/plans/berlin.yaml`);
- the overlay log (`docs/review/m8-overlay.md`) and the `plan_overlay` rows;
- the counter index (`counter_index` in `velometer.sqlite`) and the counter page (`content/counters.yaml`).

Citations are numbered in first-use order per document, as the app numbers them. Quotes come only from the source registry (`content/sources/*.yaml`). Every fact printed in a text was evaluated again for this document against the database and config, and all of them match. `velometer content --check` is clean at HEAD (controller gate after Task 7).

## Judgement calls

Decisions taken while building M8 that you may want to overturn. The first four need you most.

**Need your verdict**

1. **Helsinki counter index, 2025: 84.2 or about 100?** Two of the nine sites in the 2025 link count much less while still reporting. Kaivokatu drops from April 2024 (May–August means about 3,200 → 1,900 → 1,200) and Pitkäsilta west halves from May 2025. That looks like works or diversions, but the data cannot say. As built, the index is 84.2 (2024: 85.9). Without these two sites it is 99.9 (2024: 93.9). A generic rule would drop a site from a link when its mean per complete day changes by more than ×1.5 or ÷1.5. That rule gives 101.8 (8 sites) and would apply to every city. The build keeps both sites, because spec §2.13 records "same sites, complete days" with no break rule. *If you disagree:* we add the rule (a spec change) and reload all seven cities. Every city's index may then move a little.
2. **The Berlin on-network change since 2022 depends on the method version.** It is +28.4 km on the Vorrangnetz and −2.0 km on the Ergänzungsnetz under `overlay_v2`, against +46.0 and +19.6 under `overlay_v3`. v3 ships because it is the latest version: it stops dropping short OSM ways that lie on the network, a loss that grew over the years. The page names v3 and says the series depends on how OSM draws cycleways (Overlay section). *If you disagree:* the page shows v2, shows both, or drops the "mapped on the network" series entirely. The last option is the one the v1 result raised.
3. **Copenhagen's 37 and Strasbourg's 52 are stored as "implemented".** Copenhagen's "fuldt udmøntet" counts initiatives that are completed, funded *or under construction*. Strasbourg's "auront été réalisées" was a forecast when it was published. Each row's note says so, but `/plans` shows only the quantity (Task 3+4 review, Minor 3). *If you disagree:* mark both rows `suspect`, or add a caveat to the page next to the quantity.
4. **Drs 19/27049 prints 55.1 km of Ergänzungsnetz for 2023. We keep it but mark it suspect.** Its own column total (25.9) and row total (36.24) do not support 55.1, and the earlier answer printed 5.1. So 5.1 (19/25987) is shown as current, and 55.1 appears as a flagged revision. Spec §2.8 says the latest document is current. *If you disagree:* drop the flag, and 55.1 becomes the current Ergänzungsnetz 2023 value.

**Content fixes waiting for a yes/no**

5. **Fault found while rendering this document: the Berlin plan page's quotes sit one paragraph too late.** The `after:` indices in `content/plans/berlin.yaml` were counted with the intro paragraph included, but the renderer counts without it. The app renders it that way too (checked with `render_explainer`). As a result, the 55.1 table row appears under "Completed projects", and the geoportal abstract appears under "Mapped on the network". The fix is to set `after` to 0, 0, 1 and 2. *If no:* the page ships with the quotes misplaced.
6. **Abgeordnetenhaus profile:** "eight years of the Mobilitätsgesetz" is a translated title in quotation marks, so it reads like a quote (Task 3+4 Minor 4). Proposed fix: give the German title. *If no:* it stays as is.
7. **Two Berlin figures with no plan item are not stored and not logged.** These are the printed "Radverkehrsnetz + Hauptverkehrsstraßen" rows: 1733 C 22.7 / 69.9 and 1733 E 20.1 / 156.9 (Minor 6). Proposed fix: list them under "not stored" in `m8-plans.md`. *Alternative:* add a plan item and store them.
8. **Five expired plans name no successor** (Madrid, Barcelona, Oslo, Helsinki, Kraków; Minor 7). The research found none, and Task 9's page will say "no successor found". *If no:* more research before Task 9.
9. **Licence wording for the downloaded plan documents.** The log says "likely § 5 UrhG" for all of them, which does not cover the non-German documents (Minor 2). Proposed fix: record "licence: not stated" for each document. *If no:* the general sentence stays.

**Recorded rulings (already applied)**

10. **Madrid's counter index has a value for 2020 only.** The portal has no data from July 2021 to August 2022 and warns against comparing across its change of detectors. The Madrid page will draw no index line and will say why. *If you disagree:* we index 2023 onwards as a separate series.
11. **Oslo: a complete day means all 24 local hours were reported (read from `byHour`), not the portal's coverage = 100.** A spot check showed that coverage ≥ 95 % meant all 24 hours with some minutes missing. With this rule the 2019 base has 11 sites, not 8, and 2025 is 140.6, not 133.6.
12. **A day whose city-wide total is exactly 0 counts as an outage (an incomplete day) in every city.** A whole counter recording zero bicycles all day is almost always a fault. *If you disagree:* a real zero day would count, and indexes could shift slightly.
13. **Paris: a counter that falls silent inside its own first-to-last span counts as an outage.** As a result the site-day is incomplete. This moved Paris 2023/24/25 from 185.2/186.5/199.9 to 186.5/191.5/205.2.
14. **Berlin counter cells marked "keine Zähldaten" (orange fill) count as missing hours.** Six renumbered Berlin counters and the two sides of Helsinki's bridges are merged through `site_aliases`. Without the Helsinki merge, the index differs by at most 3.0 points.
15. **Which report row is current.** A non-suspect row wins over a suspect one. Then the later `doc_date` wins. On equal dates a Drucksache or rote Nummer beats a report, and a report beats a web page. The web edition of Fortschrittsbericht 2020 is dated by its imprint (July 2021), so 1392 I (6 July 2021, 53.5 km) is current and the web edition's 53.3 is a revision.
16. **Cumulative figures with different start years are separate series, not revisions.** Examples are 49.46 km from 2022 and 78.2 km from 2017. The 78.2 in Drs 19/25987 states no start year. It gets 2017 because 1733 E prints the same 78.2 for 2017–2025. Five network-level figures with no start year were removed rather than given an invented one (Helsinki 44.7 and 16.9 km, and others; see `m8-plans.md` §4).
17. **The overlay's 25 m buffer for separately mapped ways matches some wrong ways.** The realistic ceiling is about 17 km, or 6 % of the pieces that only the wider buffer matches (run 743). These are mostly stubs at junctions; the sanity maps and crops show no parallel side street picked up.
18. **Profiles carry no `sources:` field.** `config/organisations.yaml` is the only place that maps a source to an organisation, so the two cannot drift apart.
19. **The v3 sanity map was drawn by a new read-only script, not the one behind the v1/v2 maps.** That script was lost in the crash. Its A+B totals match the stored v3 rows exactly (476.2 / 636.9 km). Its "matched network km" may be computed slightly differently from v1/v2 (v3: 316 / 423 against v2: 312 / 418).

Also still open, no decision needed: `docs/review/m8-plans.md:51-52` still says `current_and_revisions` ignores `cumulative_from`. It no longer does: the code keys on it, as the Berlin tables below show (Task 3+4 Minor 1).

## Profiles: 9 organisations

Rendered from `content/organisations/*.yaml` the way the app renders them, with `[n]` for a source citation and `[dn]` for a data reference. Each profile has the three sections "Who they are", "How they measure" (its six dimensions as a table) and "Political role". The sources each profile cites follow it. Profiles carry no facts. Sources are mapped to organisations in `config/organisations.yaml`: `clean_cities_2025` → clean_cities, `qecio_v2_10` → ecf, `bikenetkit_v1` → bikenetkit, Berlin `official` → senmvku, Berlin `changing_cities` → changing_cities, Copenhagen `official` → copenhagen_kommune, Vienna `mobilitaetsagentur_wien` → mobilitaetsagentur_wien. The Berlin plan publishers are senmvku, infravelo and abgeordnetenhaus. Research log: `docs/review/m8-organisations.md`.

### Abgeordnetenhaus Berlin (`abgeordnetenhaus`, parliament)

<https://www.parlament-berlin.de/>

#### Who they are

The Abgeordnetenhaus is the parliament of the Land Berlin. It legislates, elects the governing mayor and scrutinises the government, the Senate [1]. Its budget act decides what the Land's money is spent on, for one or two years at a time [1].

#### How they measure

| dimension | their practice |
|---|---|
| scope | whatever a question asks; for the priority network, km implemented per year and district [2] |
| kind | as the Senate answers it [3] |
| length | as the Senate answers it; Drucksache 19/25987 gives route length for the target network only [2] |
| date | the date of the Senate's answer [2] |
| area | Land Berlin |
| method | parliament does not measure; it publishes the Senate's answers and reports [3] |

Parliament publishes Berlin's cycling figures rather than producing them. In a written question (Schriftliche Anfrage) any member can demand information; the Senate answers in writing, normally within three weeks [3], and every answer stays available in the parliamentary documentation system PARDOK [3]. Drucksache 19/25987 of May 2026 is the source of our priority-network rows [2].

The yearly progress report reaches parliament as a report of the Senate transport administration to the Hauptausschuss [4].

#### Political role

The Abgeordnetenhaus passed the Mobilitätsgesetz on 28 June 2018, after the cycling referendum campaign [5] [6]. In July 2026 it amended the act: the priority network keeps its 2030 deadline, the secondary network moves to 2035, and a main road may go without a cycling facility where a qualified alternative on minor streets exists nearby [7].

> “Anfragen des Abgeordnetenhauses an den Senat sind ein wichtiges Mittel zur Ausübung der parlamentarischen Kontrolle (Kontrollrecht).”
>
> *(Questions from the Abgeordnetenhaus to the Senate are an important means of exercising parliamentary control (right of scrutiny).)*
>
> — Abgeordnetenhaus Berlin [3]

It scrutinises the Senate through questions and requests for reports [1]; Drucksache 19/25987, titled "eight years of the Mobilitätsgesetz", asked how much of the priority network exists [2]. In our reading, written questions are where the Senate's figures get tied to a document and a date, which is why we cite them one document at a time.

**Sources**

1. `agh-arbeitsweise`: Abgeordnetenhaus Berlin: [Aufgaben und Arbeitsweise des Parlaments](https://www.parlament-berlin.de/das-parlament/arbeitsweise) (parliament, de)
2. `berlin-drs-19-25987`: Abgeordnetenhaus Berlin (answer of the Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt): [Schriftliche Anfrage 19/25987: Acht Jahre Mobilitätsgesetz – Zwischen Anspruch und Wirklichkeit im Radverkehr (answer of 20 May 2026)](https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-25987.pdf), 2026-05-20 (parliament, de)
3. `agh-parlamentarische-anfragen`: Abgeordnetenhaus Berlin: [Parlamentarische Anfragen](https://www.parlament-berlin.de/dokumente/parlamentarische-anfragen) (parliament, de)
4. `berlin-dpa-fortschrittsbericht-hauptausschuss`: Nordkurier (dpa): [Bericht: Senat ließ viele Mittel für Radverkehr liegen (dpa report on the Senate's Fahrrad-Fortschrittsbericht 2025; same article as berlin-dpa-fortschrittsbericht-2025, other passages)](https://www.nordkurier.de/regional/brandenburg/bericht-senat-liess-viele-mittel-fuer-radverkehr-liegen-4840670), 2026-09-08 (press, de)
5. `changing-cities-volksentscheid`: Changing Cities e.V.: [Volksentscheid Fahrrad](https://changing-cities.org/kampagnen/volksentscheid-fahrrad/) (ngo, de)
6. `berlin-mobg-page`: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt: [Berliner Mobilitätsgesetz (berlin.de web page)](https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrspolitik/mobilitaetsgesetz/) (official, de)
7. `berlin-mobg-amendment-2026`: Land Berlin, Gesetz- und Verordnungsblatt für Berlin: [Drittes Gesetz zur Änderung des Berliner Mobilitätsgesetzes vom 9. Juli 2026 (GVBl. 82. Jg., Nr. 25, 22 July 2026, p. 713)](https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/gvbl/g26250713.pdf), 2026-07-22 (official, de)

### BikeNetKit (IT University of Copenhagen) (`bikenetkit`, research)

<https://bikenetkit.org/>

#### Who they are

BikeNetKit is an open-source Python toolkit for planning bicycle networks, from the Networks, Data and Society group (NERDS) at the IT University of Copenhagen [1] [2]. It packages planning algorithms of a research community that NERDS kick-started in 2019; work on the toolkit itself started in 2026 [2]. Its development is supported by the Innovation Fund Denmark, the EU Horizon project JUST STREETS and the university's Data Science Section [2].

#### How they measure

| dimension | their practice |
|---|---|
| scope | a simplified OpenStreetMap bicycle network selected by the toolkit's filter for protected bicycle infrastructure [3] [4] |
| kind | mapped in OpenStreetMap [3] |
| length | not stated by the source |
| date | data collected and processed over the summer of 2026 [3] |
| area | city boundaries of European cities above 100k population [5] |
| method | OpenStreetMap extracts processed with the project's own scripts [5] |

BikeNetKit's figures are a by-product. The project publishes bicycle networks, street networks and points of interest for 403 European cities so that its tools can run locally [3]. The bicycle networks are simplified and stripped of some tags [3]; which ways belong to them follows the toolkit's filter for protected bicycle infrastructure, which selects cycleways, living streets, and paths and footways open to bicycles [4].

In our reading the filter leaves out painted lanes, so we compare BikeNetKit only with our tiers A, B and E.

#### Political role

BikeNetKit is aimed at urban planners as a decision-support tool, and at citizens who want to make a case for cycling in their city [2]. Its authors say bicycle network planning is largely ad hoc, sometimes outsourced to consultancies with opaque methods [1], and that politicians often fail to plan for cycling at all [2].

> “Contemporary bicycle network planning is largely an ad hoc process based on little empirical evidence, sometimes outsourced to for-profit consultancies working with opaque methods.”
>
> — Zenodo (GISRUK 2026 conference proceeding; IT University of Copenhagen) [1]

We found no source of a city or parliament citing BikeNetKit figures. In our reading its political role so far is the one it states for itself: a research tool meant to reach policy, still under development.

**Sources**

1. `bikenetkit-gisruk-2026`: Zenodo (GISRUK 2026 conference proceeding; IT University of Copenhagen): [BikeNetKit: Developing an open-source bicycle network software suite for urban planners](https://zenodo.org/records/19390654), 2026-04-02 (research, en)
2. `bikenetkit-github-org`: BikeNetKit (GitHub organisation profile): [BikeNetKit organisation README](https://github.com/BikeNetKit) (research, en)
3. `bikenetkit-zenodo`: Zenodo (M. Szell, M. Pessoa; IT University of Copenhagen): [Bicycle networks, street networks, and POIs for 403 European cities for BikeNetKit](https://zenodo.org/records/22271229), 2026-09-03 (index, en)
4. `bikenetkit-pbi-filter`: BikeNetKit (GitHub, IT University of Copenhagen): [GrowBikeNet constants.py: PBI_CUSTOM_FILTER (commit 8820875)](https://github.com/BikeNetKit/growbikenet/blob/8820875fcb1f363a743f2ce512e231a06a2337d9/growbikenet/constants.py) (index, en)
5. `bikenetkit-export-notebook`: BikeNetKit (GitHub, IT University of Copenhagen): [BikeNetKit dataexport: create_city_networks_from_pbf.ipynb (commit e2a5bcf)](https://github.com/BikeNetKit/dataexport/blob/e2a5bcff53a941bac757abc01a27d1ea54650fdd/scripts/create_city_networks_from_pbf.ipynb) (index, en)

### Changing Cities e.V. (`changing_cities`, ngo)

<https://changing-cities.org/>

#### Who they are

Changing Cities is a registered association (e.V.) founded in 2016 [1]. It grew out of the network that organised the Volksentscheid Fahrrad, Berlin's cycling referendum campaign [2]. About 1,480 supporting members form its financial basis [2]; in 2025 one grant, from the European Climate Foundation, made up more than a tenth of its budget [1].

#### How they measure

| dimension | their practice |
|---|---|
| scope | km of Berlin's cycle network newly created in the year, against the monitor's own target network [3] |
| kind | newly created in the year [3] |
| length | not stated by the source |
| date | reference date 31 December 2025 [3] |
| area | Berlin [3] |
| method | the association's own measurement [3] |

Changing Cities runs the Verkehrswende-Monitor, which tracks Berlin's cycle network against the Mobilitätsgesetz [3]. It says it measures the network itself, as of 31 December 2025 [3]. Its target network of 2,699.8 km is longer than the 2,398.3 km in the Senate's progress report [3] [4].

We found no published description of how the monitor measures. In our reading its yearly figure and the Senate's describe different networks and cannot be set against each other one to one.

#### Political role

In 2016 the referendum campaign handed 105,425 signatures to the Abgeordnetenhaus after three and a half weeks of collection, then negotiated a cycling law with the Senate, ADFC, BUND and FUSS e.V. [5]. It was passed on 28 June 2018 as part of the Berlin Mobilitätsgesetz [5]. That the law came from the referendum is not just the association's claim [2]: press coverage on the day of the vote reported that the Senate administration drew up the law together with the referendum's activists, ADFC and BUND [6], and the Senate's page says citizens' impulses fed directly into the act [7].

> “Die Euphorie kommt allerdings nicht von ungefähr, denn die Aktivisten haben selbst an dem Gesetz mitgearbeitet.”
>
> *(The euphoria is no accident, though: the activists themselves worked on the law.)*
>
> — Klimareporter° [6]

In our reading, its monitor and the Senate's progress report are the two yearly scorecards of the Mobilitätsgesetz: one kept by its advocate, one by the administration that must deliver it.

**Sources**

1. `changing-cities-transparenz`: Changing Cities e.V.: [Transparenz (Initiative Transparente Zivilgesellschaft)](https://changing-cities.org/transparenz/) (ngo, de)
2. `changing-cities-verein`: Changing Cities e.V.: [Verein](https://changing-cities.org/verein/) (ngo, de)
3. `berlin-changing-cities-monitor`: Changing Cities e.V.: [Verkehrswende-Monitor (Radnetz monitoring, as of 31 Dec 2025)](https://changing-cities.org/kampagnen/verkehrswende-monitor/) (ngo, de)
4. `berlin-fortschrittsbericht-2025`: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU): [Fahrrad Berlin – Fortschrittsbericht 2025 (Anlage 1 to Hauptausschuss report rote Nr. 1733 E of 12 August 2026; scanned PDF, excerpts transcribed from the page images)](https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.E-v.pdf), 2026-08-12 (official, de)
5. `changing-cities-volksentscheid`: Changing Cities e.V.: [Volksentscheid Fahrrad](https://changing-cities.org/kampagnen/volksentscheid-fahrrad/) (ngo, de)
6. `klimareporter-radgesetz-2018`: Klimareporter°: [Berlin bekommt Radgesetz](https://klimareporter.de/verkehr/berlin-bekommt-radgesetz), 2018-06-28 (press, de)
7. `berlin-mobg-page`: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt: [Berliner Mobilitätsgesetz (berlin.de web page)](https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrspolitik/mobilitaetsgesetz/) (official, de)

### Clean Cities Campaign (`clean_cities`, ngo)

<https://cleancitiescampaign.org/>

#### Who they are

The Clean Cities Campaign calls itself Europe's largest network of organisations campaigning for cities to shift from polluting cars to active, shared and electric mobility [1]. It is hosted by Transport & Environment (T&E), a European clean-transport NGO [1]. We found no separate funding statement for the campaign; T&E says it is funded by foundations, government agencies, multilateral institutions and its 49 members [2].

#### How they measure

| dimension | their practice |
|---|---|
| scope | physically separated cycling infrastructure, shared foot and bike paths included, painted lanes excluded [3] |
| kind | existing infrastructure as reported by the city, else public data [4] |
| length | not stated for cycling infrastructure [3] |
| date | data collected from December 2024 to 7 February 2025, updates accepted until 4 April 2025 [4] |
| area | the municipality of the same name [4] |
| method | city data, else public sources and ECF's OpenStreetMap data [4] [3] |

The 2025 ranking, Streets for Kids, Cities for All, scores 36 European cities on school streets, safe speeds and protected cycling infrastructure [5]. Our figures use the last: protected cycling infrastructure as a ratio to road-network length [4], which the annex calls comparable to, but not equivalent to, a share of the road network [3].

Each city administration was invited to supply data, and 34 of the 36 did; gaps were filled from public sources [4], including OpenStreetMap data compiled by the European Cyclists' Federation [3].

#### Political role

The campaign says its research shapes city, national and European policy [1]; the 2025 report asks national governments and the European Commission for stronger legal frameworks and better data collection [6]. The City of Paris announced its first place on paris.fr [7]. Vienna supplied a finer breakdown of traffic-calmed streets in July 2025, and the campaign raised the city's protected km from 384.1 to 625.1 [8].

> “Paris est la capitale européenne la plus accueillante pour les enfants : c’est le résultat d’une étude menée l’association Clean Cities auprès de 36 villes européennes.”
>
> *(Paris is the most child-friendly European capital: that is the result of a study by the Clean Cities association of 36 European cities.)*
>
> — Ville de Paris [7]

In our reading, cities either cite the ranking or contest it with their own data. We found no source showing that it changed a city's plan.

**Sources**

1. `cc-what-we-do`: Clean Cities Campaign: [What we do](https://cleancitiescampaign.org/what-we-do/) (ngo, en)
2. `te-funders`: Transport & Environment (T&E): [Funders](https://www.transportenvironment.org/about-us/funders) (ngo, en)
3. `cc2025-annexes`: Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025, Annexes (methodology)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf) (ngo, en)
4. `cc2025-report`: Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025 (report)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf) (ngo, en)
5. `cc-ranking-2025-page`: Clean Cities Campaign: [City Ranking 2025: Streets for Kids, Cities for All (overview page)](https://cleancitiescampaign.org/city-ranking-2025/) (ngo, en)
6. `cities-today-cc-ranking-2025`: Cities Today: [Paris tops ranking for child-friendly urban travel](https://cities-today.com/paris-tops-ranking-for-child-friendly-urban-travel/), 2025-05-19 (press, en)
7. `paris-fr-cc-ranking-2025`: Ville de Paris: [Paris, ville européenne la plus adaptée à la mobilité des enfants](https://www.paris.fr/pages/paris-ville-europeenne-la-plus-adaptee-a-la-mobilite-des-enfants-31537) (official, fr)
8. `cc2025-cycling-table`: Clean Cities Campaign: [City Ranking 2025: Protected cycling infrastructure table](https://cleancitiescampaign.org/city-ranking-2025-cycling-infrastructure/), 2025-05-14 (ngo, en)

### Københavns Kommune (City of Copenhagen) (`copenhagen_kommune`, official)

<https://www.kk.dk/>

#### Who they are

Københavns Kommune is the municipality of Copenhagen. Its technical administration, the Klima-, Miljø- og Teknikforvaltningen, is responsible for running and developing the city and says it works to make getting around quick and easy by bicycle, public transport or car [1]. The City Council (Borgerrepræsentationen) instructs its committees on strategy by vote [2].

#### How they measure

| dimension | their practice |
|---|---|
| scope | cycle tracks (cykelstier), separated by kerbs from carriageway and pavement; cycle lanes are reported in a separate row [3] [4] |
| kind | existing cycle track in 2025 [4] |
| length | not stated by the source |
| date | the year 2025 [4] |
| area | the municipality of Copenhagen [4] |
| method | the administration's own inventory [4] |

Our Copenhagen figure, 401 km of cycle track in 2025, comes from the Mobilitetsredegørelse 2026 [4]. The city used to report on cycling every second year in a bicycle account; since 2021 the mobility report has replaced it [5]. In the city's design guidelines a cykelsti has kerbs towards the carriageway and the pavement, while painted cycle lanes are a separate category that new schemes should avoid [3].

#### Political role

Copenhagen's cycling targets came from the Cycling Strategy 2011–2025 and the Cycle Track Priority Plan 2017–2025 [4]; the bicycle account was there to show progress against the strategy's goals [5]. In May 2024 the City Council instructed its technical committee to give the city a new, strong cycling strategy when revising its plans [2].

In our reading, the city both delivers the infrastructure and keeps the score, and its km figures serve its own targets.

> “Det foreslås, at Borgerrepræsentationen pålægger Teknik- og Miljøudvalget, at det i arbejdet med at revidere planer, politikker og strategier indenfor teknik- og miljøområdet, indgår at Københavns Kommune får en ny stærk cykelstrategi”
>
> *(It is proposed that the City Council instructs the Technical and Environmental Committee that, in revising plans, policies and strategies in the technical and environmental field, the City of Copenhagen gets a new, strong cycling strategy)*
>
> — Københavns Kommune, Borgerrepræsentationen [2]

**Sources**

1. `kk-klima-miljoe-teknikforvaltningen`: Københavns Kommune: [Klima-, Miljø- og Teknikforvaltningen](https://www.kk.dk/om-kommunen/forvaltninger/teknik-og-miljoeforvaltningen) (official, da)
2. `kk-br-cykelstrategi-2024`: Københavns Kommune, Borgerrepræsentationen: [Medlemsforslag om cykelstrategi (Borgerrepræsentationen, meeting of 2 May 2024, item 15, minutes)](https://www.kk.dk/dagsordener-og-referater/Borgerrepr%C3%A6sentationen/m%C3%B8de-02052024/referat/punkt-15), 2024-05-02 (official, da)
3. `copenhagen-cykelfokus-2024`: Københavns Kommune: [Cykelfokus 2024: Københavns Kommunes retningslinjer for cykel- og vejprojekter (council agenda annex)](https://www.kk.dk/sites/default/files/agenda/03e7571c-7870-4344-95bf-6d33c5779242/81e1e2f8-dd62-415e-be0c-ea31526f3f0b-bilag-2.pdf) (official, da)
4. `copenhagen-mobilitetsredegorelse-2026`: Københavns Kommune, Teknik- og Miljøforvaltningen: [Mobilitetsredegørelse 2026](https://byudvikling.kk.dk/sites/default/files/2026-07/Mobilitetsredeg%C3%B8relse%202026_opt-a.pdf) (official, da)
5. `copenhagen-verdens-bedste-cykelby`: Københavns Kommune: [Verdens bedste cykelby](https://byudvikling.kk.dk/mobilitet/verdens-bedste-cykelby) (official, da)

### European Cyclists' Federation (ECF) (`ecf`, ngo)

<https://www.ecf.com/>

#### Who they are

The European Cyclists' Federation is a Brussels-based independent non-profit association, founded in 1983 [1]. It calls itself the single European umbrella organisation for cycling, with more than 70 member organisations in over 40 countries [1]. Its website acknowledges financial support from the EU's LIFE Programme and from the European cycling industries [1].

#### How they measure

| dimension | their practice |
|---|---|
| scope | cycle tracks, cycle lanes, and shared cycle and pedestrian tracks, as tagged in OpenStreetMap [2] |
| kind | mapped in OpenStreetMap; low numbers may reflect missing data rather than missing infrastructure [2] |
| length | unidirectional infrastructure at half length [2] |
| date | OpenStreetMap extracts downloaded on 10–11 January 2024 [3] |
| area | NUTS 3 regions, not municipalities [2] |
| method | ECF's own analysis of OpenStreetMap (QECIO) [4] |

QECIO, Quantifying Europe's Cycling Infrastructure using OpenStreetMap, answers a gap that ECF names itself: no official source gives cycling-infrastructure data on a European scale [4]. It clips OpenStreetMap ways to NUTS 3 boundaries and sorts them into tracks, lanes and shared paths [2]. Its disclaimer says the figures show OpenStreetMap contributions only [2].

The Clean Cities Campaign uses ECF's OpenStreetMap data where a city supplies none [5], so ECF's method also stands behind some Clean Cities figures.

#### Political role

ECF works at EU level. With its industry partners it campaigned for a unified European cycling policy [6], and in 2024 the European Parliament, Council and Commission signed the European Declaration on Cycling [7]. The Commission's Expert Group on Urban Mobility, co-chaired by ECF, issued road-safety recommendations for people walking and cycling in 2024 [6].

> “ECF, as the only Europe-wide civil society voice for cycling, together with its industry partners Cycling Industries Europe and Confederation of the European Bicycle Industry (CONEBI) had long advocated for a unified cycling policy at the European level and were at the forefront every step of the way”
>
> — European Cyclists' Federation (ECF) [6]

In our reading, QECIO serves this advocacy: it supplies comparable numbers where governments publish none. We found no source of a city or government adopting QECIO figures as its own.

**Sources**

1. `ecf-about`: European Cyclists' Federation (ECF): [About ECF](https://www.ecf.com/en/about-us/about-ecf/) (ngo, en)
2. `qecio-methodology`: European Cyclists' Federation (ECF): [Quantifying Europe's Cycling Infrastructure using OSM (QECIO 2.1): Our Methodology (v2.10)](https://european-cyclists-federation.github.io/Documents/Methodology.pdf), 2024-01-11 (index, en)
3. `qecio-metadata`: European Cyclists' Federation (ECF): [Quantifying Europe's Cycling Infrastructure using OSM (QECIO 2.1): Metadata](https://european-cyclists-federation.github.io/Documents/Metadata.pdf), 2024-01-11 (index, en)
4. `qecio-site`: European Cyclists' Federation (ECF): [ECF Cycling Infrastructure Tracker: Quantifying Europe’s Cycling Infrastructure using OpenStreetMap (QECIO 2.0)](https://european-cyclists-federation.github.io/) (index, en)
5. `cc2025-annexes`: Clean Cities Campaign: [Streets for Kids, Cities for All: City Ranking 2025, Annexes (methodology)](https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf) (ngo, en)
6. `ecf-2024-breakthroughs`: European Cyclists' Federation (ECF): [2024: A year of breakthroughs for cycling](https://www.ecf.com/en/news/-2024-a-year-of-breakthroughs-for-cycling/), 2024-12-18 (ngo, en)
7. `ec-declaration-cycling`: European Commission, DG Mobility and Transport: [European declaration on cycling](https://transport.ec.europa.eu/transport-themes/urban-transport/european-declaration-cycling_en) (official, en)

### GB infraVelo GmbH (`infravelo`, agency)

<https://www.infravelo.de/>

#### Who they are

GB infraVelo GmbH was founded in mid-2017 on behalf of the Senate transport department [1]. It is a wholly owned subsidiary of the state-owned Grün Berlin GmbH [1] and is funded by allocations from Berlin's public budget [2]. It does not initiate projects: SenMVKU assigns and prioritises them, and infraVelo manages their planning and construction as the client [2]. The districts and SenMVKU also run cycling projects themselves [2].

> “infraVelo initiiert keine Projekte, sondern nimmt Projektsteuerungs-, Projektmanagement-, Baumanagement- und Bauherrenaufgaben wahr, die infraVelo zuvor von der Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU) übertragen wurden.”
>
> *(infraVelo does not initiate projects; it carries out project control, project management, construction management and client tasks previously assigned to it by SenMVKU.)*
>
> — GB infraVelo GmbH [2]

#### How they measure

| dimension | their practice |
|---|---|
| scope | cycling measures of all Berlin districts, recorded as projects [2] |
| kind | projects, monitored above all for scheduling and finances [2] |
| length | not stated by the source |
| date | updated quarterly by the districts [2] |
| area | Land Berlin [2] |
| method | a cloud project database developed by infraVelo and kept up by district project leads [2] |

Since January 2020 infraVelo has kept a central database of all cycling measures in Berlin, which the districts update every quarter [2]. The Senate's progress report draws mainly on this database [3], so the reported km and infraVelo's project list share one source.

In our reading this is a register of projects, not a survey of the street: a measure enters when a district records it, with the length its project gives.

#### Political role

The direction and priorities of infraVelo's projects lie with SenMVKU [4]; in our reading it has no political mandate of its own. It chairs three to four steering rounds a year with each district and SenMVKU [2] and shows the database on a public project map [2].

In our reading, because the report to the Hauptausschuss rests on its database [3] [5], the completeness of infraVelo's data is part of what parliament scrutinises when it reads the Senate's figures.

**Sources**

1. `infravelo-ueber-uns`: GB infraVelo GmbH: [Über uns](https://www.infravelo.de/ueber-uns/) (official, de)
2. `infravelo-faq`: GB infraVelo GmbH: [Fragen und Antworten](https://www.infravelo.de/ueber-uns/fragen-und-antworten/) (official, de)
3. `berlin-fortschrittsbericht-2025`: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU): [Fahrrad Berlin – Fortschrittsbericht 2025 (Anlage 1 to Hauptausschuss report rote Nr. 1733 E of 12 August 2026; scanned PDF, excerpts transcribed from the page images)](https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.E-v.pdf), 2026-08-12 (official, de)
4. `infravelo-organisation`: GB infraVelo GmbH: [Organisation (Unternehmensstruktur und Organe der Gesellschaft)](https://www.infravelo.de/ueber-uns/organisation/) (official, de)
5. `berlin-dpa-fortschrittsbericht-hauptausschuss`: Nordkurier (dpa): [Bericht: Senat ließ viele Mittel für Radverkehr liegen (dpa report on the Senate's Fahrrad-Fortschrittsbericht 2025; same article as berlin-dpa-fortschrittsbericht-2025, other passages)](https://www.nordkurier.de/regional/brandenburg/bericht-senat-liess-viele-mittel-fuer-radverkehr-liegen-4840670), 2026-09-08 (press, de)

### Mobilitätsagentur Wien GmbH (`mobilitaetsagentur_wien`, agency)

<https://mobilitaetsagentur.at/>

#### Who they are

Mobilitätsagentur Wien is a company owned by the City of Vienna that works for better conditions for cycling and walking, and it says it is bound by the city's objectives [1]. The red-green city government created it soon after taking office, and the city's cycling commissioner, in post since autumn 2011, led it [2]. A 2016 portrait in the cycling magazine Drahtesel put its yearly budget at around two million and called it a kind of communications department of the city, unable to push through infrastructure itself [2].

#### How they measure

| dimension | their practice |
|---|---|
| scope | cycling projects of all facility types in the main cycle network whose realisation began in the year [3] |
| kind | projects started, not completed [3] |
| length | measured in the city's digital map from start to end point, each facility separately; a junction project enters as one metre [3] |
| date | the year in which the project started [3] |
| area | City of Vienna, main cycle network [3] |
| method | the agency's own tally of the city's projects [3] |

Our Vienna figure is the agency's Bilanz Radwegeausbau 2025: 53 projects in the main cycle network whose realisation began in 2025 [3]. It is a tally of starts, not of completed or existing km, and renovation of existing paths is left out [3]. The city's network statistics are a separate series, which has recorded facilities on both sides of a street since 2018 [4].

> “Die Bilanz zum Radwegeausbau 2025 enthält 53 Radinfrastrukturprojekte im Hauptradverkehrsnetz, mit deren Realisierung im Jahr 2025 begonnen wurde. Es handelt sich um 20,4 Kilometer, die im Jahr 2025 gestartet wurden.”
>
> *(The 2025 cycle path tally contains 53 cycling infrastructure projects in the main cycle network whose realisation began in 2025. They amount to 20.4 km started in 2025.)*
>
> — Mobilitätsagentur Wien GmbH (fahrradwien.at) [3]

#### Political role

The agency presents the city's yearly cycling programme, the Radweg-Offensive; for 2026 it announced 33 projects and about 12.5 km of new cycle paths [5]. ORF reported the 2025 programme as around 24 km [6].

In our reading, these are the city's own account of its programme, published by a city company rather than an independent body, and they measure intentions and starts more than finished network.

**Sources**

1. `mobilitaetsagentur-ueber-uns`: Mobilitätsagentur Wien GmbH: [Über uns](https://mobilitaetsagentur.at/ueber-uns) (official, de)
2. `drahtesel-mobilitaetsagentur-2016`: Drahtesel (Radlobby Österreich magazine): [Fünf Jahre mit Blum](https://www.drahtesel.or.at/fuenf-jahre-mit-blum/), 2016-12-02 (press, de)
3. `vienna-radwegeausbau-bilanz-2025`: Mobilitätsagentur Wien GmbH (fahrradwien.at): [Bilanz Radwegeausbau 2025 (Radwegoffensive 2025)](https://www.fahrradwien.at/wp-content/uploads/sites/2/2026/01/Radwegoffensive_2025_Bilanz.pdf) (official, de)
4. `vienna-radverkehrsnetz-fakten`: Stadt Wien – Verkehrsorganisation und technische Verkehrsangelegenheiten: [Zahlen und Fakten zum Wiener Radverkehrsnetz](https://www.wien.gv.at/verkehr/radverkehrsnetz-radwege-statistiken), 2026-01-21 (official, de)
5. `vienna-mobilitaetsagentur-2026`: Mobilitätsagentur Wien GmbH: [Radverkehrsplanung (Radwegoffensive page; fahrradwien.at/radwegoffensive-2025/ now redirects here)](https://mobilitaetsagentur.at/radfahren/radverkehrsplanung) (official, de)
6. `vienna-orf-radwegenetz-2025`: ORF Wien (wien.ORF.at): [Radwegenetz soll heuer um 24 Kilometer wachsen](https://wien.orf.at/stories/3296850/), 2025-03-13 (press, de)

### Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU) (`senmvku`, official)

<https://www.berlin.de/sen/uvk/>

#### Who they are

SenMVKU is the department of the Berlin Senate for mobility, transport, climate protection and the environment; it has carried this name since May 2023 [1]. Responsibility for cycling infrastructure in Berlin lies with SenMVKU and with the districts [2]. It administers the Mobilitätsgesetz, promulgated on 5 July 2018 [3], and funds and directs the state cycling company infraVelo [4].

#### How they measure

| dimension | their practice |
|---|---|
| scope | all cycling measures implemented or improved in the year, whoever is responsible for the road or pays [5] |
| kind | measures completed in the year, not network stock [5] |
| length | route length since the 2022 report: a street with facilities on both sides is one length; earlier reports took each direction [6] |
| date | reference date 31 December of the report year [5] |
| area | Land Berlin [5] |
| method | mainly the project database run by infraVelo and updated by the districts [5] [4] |

Our Berlin `official` rows come from SenMVKU: its yearly Fahrrad-Fortschrittsbericht and its answers to written questions in the Abgeordnetenhaus [5] [7]. The report covers the work of the Senate administration, infraVelo and the districts [6]. Its numbers come mainly from the infraVelo project database, refer to 31 December and may be revised in later reports [5].

Since the 2022 report it gives route length instead of length per direction; the department says this makes the figures lower and not directly comparable with earlier years [6].

#### Political role

The progress report goes to the Abgeordnetenhaus's main committee, the Hauptausschuss [8]. For 2025, dpa read from it that just under 27 million euros went into cycling, of about 82.4 million available [8].

In our reading, the same department sets the pace and reports on it. In June 2023 it asked the districts to stop cycle path projects for the time being if they would cost even one car parking space [9]. In December 2025 it gave 20.5 km for the year, below its own target [10].

> “Keine neuen Radwege mehr für Berlin, wenn dafür auch nur ein Pkw-Stellplatz wegfällt: Die Senatsverkehrsverwaltung hat die Bezirke gebeten, Radwegprojekte vorerst zu stoppen.”
>
> *(No more new cycle paths for Berlin if even one car parking space would be lost: the Senate transport administration has asked the districts to stop cycle path projects for the time being.)*
>
> — Der Tagesspiegel [9]

**Sources**

1. `infravelo-ueber-uns`: GB infraVelo GmbH: [Über uns](https://www.infravelo.de/ueber-uns/) (official, de)
2. `infravelo-organisation`: GB infraVelo GmbH: [Organisation (Unternehmensstruktur und Organe der Gesellschaft)](https://www.infravelo.de/ueber-uns/organisation/) (official, de)
3. `berlin-mobg-page`: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt: [Berliner Mobilitätsgesetz (berlin.de web page)](https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrspolitik/mobilitaetsgesetz/) (official, de)
4. `infravelo-faq`: GB infraVelo GmbH: [Fragen und Antworten](https://www.infravelo.de/ueber-uns/fragen-und-antworten/) (official, de)
5. `berlin-fortschrittsbericht-2025`: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU): [Fahrrad Berlin – Fortschrittsbericht 2025 (Anlage 1 to Hauptausschuss report rote Nr. 1733 E of 12 August 2026; scanned PDF, excerpts transcribed from the page images)](https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.E-v.pdf), 2026-08-12 (official, de)
6. `berlin-radfortschrittsbericht-page`: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt: [Radfortschrittsbericht (berlin.de web page)](https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrsplanung/radverkehr/radprojekte/radfortschrittsbericht/) (official, de)
7. `berlin-drs-19-25987`: Abgeordnetenhaus Berlin (answer of the Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt): [Schriftliche Anfrage 19/25987: Acht Jahre Mobilitätsgesetz – Zwischen Anspruch und Wirklichkeit im Radverkehr (answer of 20 May 2026)](https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-25987.pdf), 2026-05-20 (parliament, de)
8. `berlin-dpa-fortschrittsbericht-hauptausschuss`: Nordkurier (dpa): [Bericht: Senat ließ viele Mittel für Radverkehr liegen (dpa report on the Senate's Fahrrad-Fortschrittsbericht 2025; same article as berlin-dpa-fortschrittsbericht-2025, other passages)](https://www.nordkurier.de/regional/brandenburg/bericht-senat-liess-viele-mittel-fuer-radverkehr-liegen-4840670), 2026-09-08 (press, de)
9. `berlin-tagesspiegel-radwegestopp-2023`: Der Tagesspiegel: [Sobald ein Auto-Parkplatz wegfällt: Berliner Senat stoppt vorerst Radwegprojekte](https://www.tagesspiegel.de/berlin/sobald-auch-nur-ein-parkplatz-wegfallt-berliner-senatsverwaltung-stoppt-vorerst-radwegprojekte-9992884.html), 2023-06-15 (press, de)
10. `berlin-tagesspiegel-dpa-2025-12`: Der Tagesspiegel (dpa): [Senat verfehlt eigenes Ziel: In diesem Jahr wurden nur 20,5 Kilometer neue Radwege in Berlin gebaut (dpa; Senate figure given on request, before year end)](https://www.tagesspiegel.de/berlin/senat-hangt-eigenem-ziel-hinterher-205-kilometer-neue-radwege-in-berlin-gebaut-15065944.html), 2025-12-19 (press, de)
## Plans

### 21 plans (`config/plans/plans.yaml`)

The targets are stored as printed. "not confirmed" means the adoption date of a council decision was not found; the plan's note says what was found instead. "none found" means an expired plan with no successor confirmed (judgement call 8).

| city | plan | adopted | status | successor | items: target |
|---|---|---|---|---|---|
| berlin | [Radverkehrsplan des Landes Berlin (Verordnung vom 16. November 2021, Vorlage zur Kenntnisnahme vo19-013)](https://www.parlament-berlin.de/ados/19/IIIPlen/vorgang/verordnungen/vo19-013.pdf) | 2021-11-16 | current | — | Vorrangnetz (ohne Radschnellverbindungen): km_per_year 2022 40, 2023 60, 2024 100, 2025 150, 2026 250, 2027 250; Ergänzungsnetz: km_per_year 2025 50, 2026 100, 2027 100, 2028 350, 2029 450, 2030 450; Radverkehrsnetz (Vorrangnetz + Ergänzungsnetz): km_per_year 2022 40, 2023 60, 2024 100, 2025 200, 2026 350, 2027 350, 2028 350, 2029 450, 2030 450; Hauptverkehrsstraßen außerhalb des Radverkehrsnetzes: no km target; Sonstige Strecke: no km target; Sonstiges Netz (as named in Drs 19/27049; outside Vorrang- and Ergänzungsnetz): no km target; All reported routes (Summe): no km target; Radverkehrsanlagen, facility length with each side counted (reports on 2020 and 2021): no km target |
| paris | [Plan Vélo 2021-2026](https://opendata.paris.fr/explore/dataset/plan-velo-2026/) | not confirmed | current | — | Pistes cyclables sécurisées (new and made permanent): km_total 2026 180 |
| vienna | [Radwegoffensive (yearly construction programme for the Hauptradverkehrsnetz)](https://mobilitaetsagentur.at/radfahren/radverkehrsplanung) | not confirmed | current | — | Hauptradverkehrsnetz, km of new cycle paths in the yearly programme: km_per_year 2026 12.5 |
| copenhagen | [Cykelstrategi 2011–2025 and Cykelstiprioriteringsplan 2017–2025](https://byudvikling.kk.dk/mobilitet/verdens-bedste-cykelby) | not confirmed | expired | Samlet mobilitetsstrategi (decided by the Klima-, Miljø- og Teknikudvalg; political treatment expected early 2027) | Initiatives of the Cykelstiprioriteringsplan 2017–2025: no km target |
| amsterdam | [Meerjarenplan Fiets 2017-2022](https://bikecity.amsterdam.nl/wp-content/uploads/2023/11/Meerjarenplan_Fiets_2017-2022.pdf) | not confirmed | expired | Uitvoeringsplan 2024 Verkeersveiligheid, 30 km/u, voetganger en fiets | Plusnet Fiets routes inside the A10 ring, south of the IJ, at least 2.50 m wide: share 2025 50 |
| utrecht | [Mobiliteitsplan 2040](https://utrecht.bestuurlijkeinformatie.nl/Document/View/1042744c-3d66-4915-846f-a513f41b36f1) | not confirmed | current | — | Fietsnetwerk: no km target |
| madrid | [Plan Director de Movilidad Ciclista (2008)](https://www.madrid.es/portales/munimadrid/es/Inicio/Vivienda-urbanismo-y-obras/Publicaciones/Plan-Director-de-Movilidad-Ciclista-2008-/?vgnextfmt=default&vgnextoid=09bccea83e67a110VgnVCM2000000c205a0aRCRD&vgnextchannel=cf6031d3b28fe410VgnVCM1000000b205a0aRCRD) | not confirmed | expired | none found | Red Básica de Vías Ciclistas: no km target |
| barcelona | [Pla de Mobilitat Urbana 2024](https://ajuntament.barcelona.cat/premsa/2022/12/23/aprovacio-definitiva-del-pla-de-mobilitat-urbana-2024/) | 2022-12-23 | expired | none found | Increase of the bike-lane network over its size at approval: share 2024 40 |
| stockholm | [Cykelstaden – Cykelplan för Stockholms stad](https://meetingspublic.stockholm.se/welcome-sv/namnder-styrelser/kommunfullmaktige/mote-2022-05-30/agenda/bilaga-2-cykelstaden-cykelplan-for-stockholmpdf?downloadMode=open) | 2022-05-30 | current | — | Share of trips by bike: share 2040 25 |
| oslo | [Plan for sykkelveinettet i Oslo](https://www.oslo.kommune.no/slik-bygger-vi-oslo/plan-for-sykkelveinettet/) | not confirmed | expired | none found | New cycle network, first phase to 2025: km_total 2025 100; New and upgraded cycleway since 2015: no km target |
| helsinki | [Pyöräliikenteen kehittämisohjelma 2020–2025](https://www.hel.fi/static/liitteet/kaupunkiymparisto/julkaisut/julkaisut/julkaisu-31-20.pdf) | not confirmed | expired | none found | Inner-city target cycle network (about 140 km): no km target; Baana target network (about 140 km): no km target |
| lyon | [Plan vélo 2024-2030 de la Métropole de Lyon (incl. Voies Lyonnaises)](https://avelo.grandlyon.com/fileadmin/user_upload/pdf/GL_PlanVelo_FR_aout2024_BAT03.pdf) | not confirmed | current | — | Voies Lyonnaises: km_total 2030 355; Linéaire d'aménagements cyclables (whole Métropole network): no km target |
| strasbourg | [Plan vélo de l'Eurométropole 2021-2026](https://www.strasbourg.eu/-/plan-velo-eurometropole-102024) | not confirmed | current | — | Cycle tracks rebuilt or built (about): km_total 2026 100; Operations of the plan (about 100): no km target |
| bordeaux | [3ème Plan vélo métropolitain 2021-2026](https://www.bordeaux-metropole.fr/sites/MET-BXMETRO-DRUPAL/files/2023-08/Plan_velo2021.pdf) | 2021-11-25 | current | — | Cycling modal share: share 2030 18; Réseau Vélo Express (ReVE): no km target; Cycle routes of all types added since adoption: no km target |
| wroclaw | [Wrocławski Plan Działań Rowerowych do 2030 roku](https://www.wroclaw.pl/komunikacja/wroclawski-plan-dzialan-rowerowych-do-2030) | not confirmed | current | — | New cycle routes (about): km_total 2030 100 |
| warsaw | [Program rozwoju tras rowerowych Warszawy do 2020 roku](https://zdm.waw.pl/aktualnosci/jaka-ma-byc-rowerowa-warszawa-2030/) | not confirmed | expired | Program Rozwoju Ruchu Rowerowego na lata 2020–2030 (tendered February 2020; adoption not found) | New cycle routes: no km target |
| krakow | [Polityka transportowa dla miasta Krakowa na lata 2016–2025 (uchwała Nr XLVII/848/16)](https://www.bip.krakow.pl/?sub_dok_id=19585) | 2016-06-08 | expired | none found | Cycling infrastructure (city-wide): no km target |
| budapest | [Kerékpárforgalmi főhálózati terv (KFHT)](https://bkk.hu/rolunk/strategiank/kerekparforgalmi-fohalozati-terv/) | not confirmed | current | — | Cycling share of trips: share 2030 10 |
| prague | [Koncepce rozvoje cyklistické dopravy na území hl. m. Prahy (2010)](https://iprpraha.cz/assets/files/files/506ba6ec042dbcfbd30a0ebf0f4dbf87.pdf) | not confirmed | current | — | Base network of signed cycle routes, extension by 300–400 km: no km target |
| bratislava | [Zásady rozvoja cyklistickej a pešej dopravy (uznesenie č. 1743/2014)](https://zastupitelstvo.bratislava.sk/data/att/37247.pdf) | not confirmed | current | — | New cycling infrastructure, all types: no km target |
| ljubljana | [Celostna prometna strategija Mestne občine Ljubljana 2025–2032](https://www.ljubljana.si/sl/ljubljana/mobilna/celostna-prometna-strategija) | 2025-10-20 | current | — | Cycling infrastructure: no km target |

<details><summary>Plan notes (adoption, status and target reasoning per plan)</summary>

| plan | note |
|---|---|
| `berlin_rvp_2021` | Issued by the Senatsverwaltung für Umwelt, Verkehr und Klimaschutz (predecessor of SenMVKU). Targets from Tabelle 7 'Jahresausbauziele zur Errichtung des Radverkehrsnetzes Berlin' (PDF p. 42, plan p. 21): yearly completion in km, rounded to 5 km; the printed sums 850 km (Vorrangnetz ohne RSV), 1.500 km (Ergänzungsnetz) and 2.350 km are rounded to 25 km (footnote 12). Tabelle 3 (PDF p. 35, plan p. 14) gives the network lengths 865 km (Radvorrangnetz), 1.506 km (Ergänzungsnetz), 2.371 km in total. Progress reports before 2022 count facility length with each side of a street counted (item anlagen); from the 2021 report on, network items count route length once per street section. |
| `paris_plan_velo_2021` | Presented to the Conseil de Paris in October 2021 (open-data dataset description); the adoption date of a deliberation was not confirmed. Target per the Ville de Paris press kit (p. 15): 180 km of protected cycle tracks, 130 km new and 52 km of coronapistes made permanent. No official progress figure in km found. |
| `vienna_radwegoffensive` | No single adopted cycling plan with a km target found; the city announces a programme each year. 2026: 33 projects and around 12.5 km of new cycle paths (Mobilitätsagentur page). The yearly tally counts km of projects started in the year, not completed. |
| `copenhagen_cykelstrategi_2011` | Both plans ran to the end of 2025 (Mobilitetsredegørelse 2026, pp. 4 and 29). The strategy's targets are shares (50 % of trips to work and education by bike), not km; the priority plan lists 151 initiatives. |
| `amsterdam_meerjarenplan_fiets_2017` | The Uitvoeringsplan 2024 (p. 3) names the 2017 cycling plan as expiring. No km target; the plan's network target is a width share on the Plusnet Fiets (p. 13). |
| `utrecht_mobiliteitsplan_2040` | URL is the council proposal (raadsvoorstel). Adoption by the gemeenteraad on 15 July 2021 is reported by APPM; the council decision itself was not opened. The plan sets a cycle network on a map, with no km target. |
| `madrid_pdmc_2008` | Status not confirmed. The 2008 plan (Red Básica de Vías Ciclistas) and its 2016 revision are on madrid.es, but the revision PDF refused scripted access (HTTP 403) and no current city cycling plan with a km target was found; no successor confirmed. |
| `barcelona_pmu_2024` | Final approval by the plenary of the Consell Municipal (press release of 23 December 2022). Bicycle measures: increase the current bike-lane network by 40 %; bicycle and VMP modal share from 2.28 % (2018) to 5 % in 2024. Horizon 2024 has passed; no successor confirmed. |
| `stockholm_cykelplan_2022` | The plan is an attachment to the Kommunfullmäktige agenda of 30 May 2022 (the decision protocol was not opened). It designates about 36 Swedish miles (about 360 km) as the primary network for successive expansion, with no deadline; the target is a share: every fourth trip by bike by 2040 (Kommunstyrelsen statement, 18 May 2022). |
| `oslo_sykkelveinettet_2018` | Adopted by the bystyre in 2018 (city page; day not printed). Implements the Sykkelstrategi for Oslo 2015–2025. First phase to 2025: about 100 km of new cycle network (about 70 km by Oslo kommune, 30 km by Statens vegvesen), giving about 280 km in 2025; full future network about 530 km (plan PDF p. 7). First-phase horizon has passed; no successor plan confirmed. |
| `helsinki_pyoraliikenne_2020` | Proposed by the Urban Environment Committee in 2020; the City Executive Board tabled it on 26 October 2020 and approved it in November 2020 (date not confirmed at source). Target networks of about 140 km (inner city) and about 140 km (baana), with no km deadline; share target 20 % by 2035. Programme period ended 2025; no successor confirmed. |
| `lyon_plan_velo_2024` | Métropole plan (published August 2024), not the city proper. Voies Lyonnaises: objective 355 km in 2030 (p. 9); 2023: 29 km 'en cours de travaux ou livrés' (not stored: mixes started and delivered). Cycle network objective 2 000 km, no year printed (p. 10). The earlier 250 km by 2026 Voies Lyonnaises target is reported only by press and an NGO. |
| `strasbourg_plan_velo_2021` | Launched by the Eurométropole in 2021 (day not printed). About a hundred operations for about a hundred km of cycle tracks rebuilt or built by 2026, Eurométropole-wide. |
| `bordeaux_plan_velo_2021` | Approved 25 November 2021 (Chambre régionale des comptes report, p. 35). Métropole-wide; the target is a share (18 % by 2030). ReVE: 14 routes, 272 km on the Métropole page, 270 km in the CRC report, no deadline printed. |
| `wroclaw_plan_rowerowy_2030` | Presented on 11 May 2022; no adoption resolution found. Targets: about 100 km of new routes, 25 km of modernised routes and 26 km with major transport projects by 2030 (city page). |
| `warsaw_program_tras_2020` | Prepared in 2013 (ZDM, 4 February 2020); its km target was not confirmed at the source. No adopted successor found. |
| `krakow_polityka_transportowa_2016` | General transport policy; no cycling km target found. Period ended 2025. A city cycling team presented recommendations to 2030 in September 2026 (ZTP), not an adopted plan. |
| `budapest_kfht` | Prepared by BKK under Fővárosi Közgyűlés resolution 1539/2021 (X. 27.); its situation assessment is dated 7 October 2022; the adoption date of the plan itself was not confirmed. Main network about 800 km within about 5 500 km of roads; share target 10 % of trips by 2030 (Budapest Mobility Plan). The km goals 292 km by 2027 and 504 km by 2030 are reported only by press (Telex). |
| `prague_koncepce_2010` | URL is IPR Praha's 2021 Systém pražských cyklotras (published 7 March 2022), which cites the Koncepce's goal of extending the base route network by a further 300–400 km; no single km figure or deadline. The extension of the Koncepce to 2030 was not confirmed at source. |
| `bratislava_zasady_2014` | Approved by the city council in September 2014 (resolution 1743/2014; day not printed in the council material of 2018). The target of 180 km of main city cycle routes by 2030 (Bratislava 2030) is reported by SITA quoting the city hall, not confirmed in an official document. |
| `ljubljana_cps_2025` | Adopted by the Mestni svet MOL on 20 October 2025. Main goal about two thirds of trips by walking, cycling and public transport; no cycling km target found in the strategy document. |

</details>

### Berlin: every printed figure, by plan item → year → quantity

118 rows from `config/plans/reports.csv`. Each column is one document. The **bold** value is the current one, chosen by the same `current_and_revisions` that the app uses: a non-suspect row first, then the latest `doc_date`, then Drucksache/rote Nummer over report over web. "cumulative from N" is `cumulative_from`. Cumulative figures from different start years are separate series, not revisions of each other. "target" is the plan's yearly target for that item and year, where one exists. Values are as printed: the 2021 network items count route length once per street section, and `anlagen` (reports on 2020 and 2021) counts facility length with each side counted.

Only one row is suspect: Ergänzungsnetz 2023, 55.1 in 19/27049 (judgement call 4).

Documents (oldest first):

| document | type | dated | URL |
|---|---|---|---|
| FB 2020 web | report | 2021-07-01 | <https://www.berlin.de/sen/uvk/_assets/verkehr/verkehrsplanung/radverkehr/radprojekte/radfortschrittsbericht/fortschrittsbericht-fahrrad-2020.pdf> |
| 1392 I | rote_nummer | 2021-07-06 | <https://www.parlament-berlin.de/adosservice/18/Haupt/vorgang/h18-1392.I-v.pdf> |
| 0389 A | rote_nummer | 2022-07-05 | <https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-0389.A-v.pdf> |
| 1064 | rote_nummer | 2023-06-27 | <https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1064-v.pdf> |
| 1733 B-1 | rote_nummer | 2025-01-28 | <https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.B-1-v.pdf> |
| 1733 C | rote_nummer | 2025-06-24 | <https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.C-v.pdf> |
| 19/25987 | drucksache | 2026-05-20 | <https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-25987.pdf> |
| 1733 E | rote_nummer | 2026-08-12 | <https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.E-v.pdf> |
| 19/27049 | drucksache | 2026-09-14 | <https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-27049.pdf> |

#### `vorrangnetz`: Vorrangnetz (ohne Radschnellverbindungen)

| year | quantity | target | 0389 A | 1064 | 1733 B-1 | 1733 C | 19/25987 | 1733 E | 19/27049 | current | revisions |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 2021 | in year |  | **7.4** |  |  |  |  |  |  | 7.4 (0389 A) | — |
| 2021 | cumulative from 2017 |  | **27.4** |  |  |  |  |  |  | 27.4 (0389 A) | — |
| 2022 | in year | 40 |  | 15 |  | 15 | 14.3 |  | **14.4** | 14.4 (19/27049) | 14.3 (19/25987); 15 (1733 C); 15 (1064) |
| 2022 | under construction |  |  | **7.9** |  |  |  |  |  | 7.9 (1064) | — |
| 2022 | in planning |  |  | **50.6** |  |  |  |  |  | 50.6 (1064) | — |
| 2023 | in year | 60 |  |  | 13.6 | 13.6 | 13.6 |  | **13.6** | 13.6 (19/27049) | 13.6 (19/25987); 13.6 (1733 C); 13.6 (1733 B-1) |
| 2023 | under construction |  |  |  | **14.7** |  |  |  |  | 14.7 (1733 B-1) | — |
| 2023 | in planning |  |  |  | **32.3** |  |  |  |  | 32.3 (1733 B-1) | — |
| 2024 | in year | 100 |  |  |  | 10.8 | 10.9 |  | **10.8** | 10.8 (19/27049) | 10.9 (19/25987); 10.8 (1733 C) |
| 2024 | cumulative from 2022 |  |  |  |  | **39.4** |  |  |  | 39.4 (1733 C) | — |
| 2025 | in year | 150 |  |  |  |  | 9.8 | 8.6 | **8.6** | 8.6 (19/27049) | 8.6 (1733 E); 9.8 (19/25987) |
| 2025 | cumulative from 2017 |  |  |  |  |  |  | **78.2** |  | 78.2 (1733 E) | — |
| 2026 | in year | 250 |  |  |  |  |  |  | **2.3** | 2.3 (19/27049) | — |
| 2026 | cumulative from 2017 |  |  |  |  |  | **78.2** |  |  | 78.2 (19/25987) | — |
| 2026 | cumulative from 2022 |  |  |  |  |  |  |  | **49.46** | 49.46 (19/27049) | — |

#### `ergaenzungsnetz`: Ergänzungsnetz

| year | quantity | target | 0389 A | 1064 | 1733 B-1 | 1733 C | 19/25987 | 1733 E | 19/27049 | current | revisions |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 2021 | in year |  | **7.4** |  |  |  |  |  |  | 7.4 (0389 A) | — |
| 2021 | cumulative from 2017 |  | **29.3** |  |  |  |  |  |  | 29.3 (0389 A) | — |
| 2022 | in year |  |  | 8.7 |  | 8.7 | 10.1 |  | **10** | 10 (19/27049) | 10.1 (19/25987); 8.7 (1733 C); 8.7 (1064) |
| 2022 | under construction |  |  | **9.8** |  |  |  |  |  | 9.8 (1064) | — |
| 2022 | in planning |  |  | **48.5** |  |  |  |  |  | 48.5 (1064) | — |
| 2023 | in year |  |  |  | 4.9 | 4.9 | **5.1** |  | 55.1 (suspect) | 5.1 (19/25987) | 4.9 (1733 C); 4.9 (1733 B-1); 55.1 (19/27049, suspect) |
| 2023 | under construction |  |  |  | **16.1** |  |  |  |  | 16.1 (1733 B-1) | — |
| 2023 | in planning |  |  |  | **21.5** |  |  |  |  | 21.5 (1733 B-1) | — |
| 2024 | in year |  |  |  |  | 9.6 | 9.6 |  | **9.6** | 9.6 (19/27049) | 9.6 (19/25987); 9.6 (1733 C) |
| 2024 | cumulative from 2022 |  |  |  |  | **23.2** |  |  |  | 23.2 (1733 C) | — |
| 2025 | in year | 50 |  |  |  |  | 7.5 | 7.5 | **7.5** | 7.5 (19/27049) | 7.5 (1733 E); 7.5 (19/25987) |
| 2025 | cumulative from 2017 |  |  |  |  |  |  | **61.9** |  | 61.9 (1733 E) | — |
| 2026 | in year | 100 |  |  |  |  |  |  | **3.77** | 3.77 (19/27049) | — |
| 2026 | cumulative from 2022 |  |  |  |  |  |  |  | **36.24** | 36.24 (19/27049) | — |

#### `radverkehrsnetz`: Radverkehrsnetz (Vorrangnetz + Ergänzungsnetz)

| year | quantity | target | 1733 C | 1733 E | current | revisions |
|---|---|---|---:|---:|---|---|
| 2024 | in year | 100 | **20.4** |  | 20.4 (1733 C) | — |
| 2024 | cumulative from 2022 |  | **62.6** |  | 62.6 (1733 C) | — |
| 2025 | in year | 200 |  | **16.1** | 16.1 (1733 E) | — |
| 2025 | cumulative from 2017 |  |  | **140.1** | 140.1 (1733 E) | — |

#### `hauptverkehrsstrassen`: Hauptverkehrsstraßen außerhalb des Radverkehrsnetzes

| year | quantity | target | 0389 A | 1064 | 1733 B-1 | 1733 C | 1733 E | current | revisions |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| 2021 | in year |  | **3.1** |  |  |  |  | 3.1 (0389 A) | — |
| 2021 | cumulative from 2017 |  | **9.6** |  |  |  |  | 9.6 (0389 A) | — |
| 2022 | in year |  |  | 1.7 |  | **1.7** |  | 1.7 (1733 C) | 1.7 (1064) |
| 2022 | under construction |  |  | **1.7** |  |  |  | 1.7 (1064) | — |
| 2022 | in planning |  |  | **26.8** |  |  |  | 26.8 (1064) | — |
| 2023 | in year |  |  |  | 3.3 | **3.3** |  | 3.3 (1733 C) | 3.3 (1733 B-1) |
| 2023 | under construction |  |  |  | **2.3** |  |  | 2.3 (1733 B-1) | — |
| 2023 | in planning |  |  |  | **22.3** |  |  | 22.3 (1733 B-1) | — |
| 2024 | in year |  |  |  |  | **2.3** |  | 2.3 (1733 C) | — |
| 2024 | cumulative from 2022 |  |  |  |  | **7.3** |  | 7.3 (1733 C) | — |
| 2025 | in year |  |  |  |  |  | **4** | 4 (1733 E) | — |
| 2025 | cumulative from 2017 |  |  |  |  |  | **16.8** | 16.8 (1733 E) | — |

#### `sonstige_strecke`: Sonstige Strecke

| year | quantity | target | 0389 A | 1064 | 1733 B-1 | 1733 C | 1733 E | current | revisions |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| 2021 | in year |  | **0.5** |  |  |  |  | 0.5 (0389 A) | — |
| 2021 | cumulative from 2017 |  | **3.1** |  |  |  |  | 3.1 (0389 A) | — |
| 2022 | in year |  |  | 1.1 |  | **1.1** |  | 1.1 (1733 C) | 1.1 (1064) |
| 2022 | under construction |  |  | **2.3** |  |  |  | 2.3 (1064) | — |
| 2022 | in planning |  |  | **6.4** |  |  |  | 6.4 (1064) | — |
| 2023 | in year |  |  |  | 4.2 | **4.2** |  | 4.2 (1733 C) | 4.2 (1733 B-1) |
| 2023 | under construction |  |  |  | **1.5** |  |  | 1.5 (1733 B-1) | — |
| 2023 | in planning |  |  |  | **9.8** |  |  | 9.8 (1733 B-1) | — |
| 2024 | in year |  |  |  |  | **0.9** |  | 0.9 (1733 C) | — |
| 2024 | cumulative from 2022 |  |  |  |  | **6.2** |  | 6.2 (1733 C) | — |
| 2025 | in year |  |  |  |  |  | **1.1** | 1.1 (1733 E) | — |
| 2025 | cumulative from 2017 |  |  |  |  |  | **17** | 17 (1733 E) | — |

#### `sonstiges_netz`: Sonstiges Netz (as named in Drs 19/27049; outside Vorrang- and Ergänzungsnetz)

| year | quantity | target | 19/27049 | current | revisions |
|---|---|---|---:|---|---|
| 2022 | in year |  | **3.1** | 3.1 (19/27049) | — |
| 2023 | in year |  | **7.2** | 7.2 (19/27049) | — |
| 2024 | in year |  | **3.2** | 3.2 (19/27049) | — |
| 2025 | in year |  | **5.1** | 5.1 (19/27049) | — |
| 2026 | in year |  | **0.15** | 0.15 (19/27049) | — |
| 2026 | cumulative from 2022 |  | **18.83** | 18.83 (19/27049) | — |

#### `total`: All reported routes (Summe)

| year | quantity | target | 0389 A | 1064 | 1733 B-1 | 1733 C | 1733 E | 19/27049 | current | revisions |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 2021 | in year |  | **18.4** |  |  |  |  |  | 18.4 (0389 A) | — |
| 2021 | cumulative from 2017 |  | **69.4** |  |  |  |  |  | 69.4 (0389 A) | — |
| 2022 | in year |  |  | 26.5 |  |  |  | **27.5** | 27.5 (19/27049) | 26.5 (1064) |
| 2022 | under construction |  |  | **21.7** |  |  |  |  | 21.7 (1064) | — |
| 2022 | in planning |  |  | **132.3** |  |  |  |  | 132.3 (1064) | — |
| 2023 | in year |  |  |  | 26 |  |  | **25.9** | 25.9 (19/27049) | 26 (1733 B-1) |
| 2023 | under construction |  |  |  | **34.7** |  |  |  | 34.7 (1733 B-1) | — |
| 2023 | in planning |  |  |  | **85.8** |  |  |  | 85.8 (1733 B-1) | — |
| 2024 | in year |  |  |  |  | 23.6 |  | **23.6** | 23.6 (19/27049) | 23.6 (1733 C) |
| 2024 | cumulative from 2022 |  |  |  |  | **76.1** |  |  | 76.1 (1733 C) | — |
| 2024 | under construction |  |  |  |  | **24.3** |  |  | 24.3 (1733 C) | — |
| 2024 | in planning |  |  |  |  | **84.9** |  |  | 84.9 (1733 C) | — |
| 2025 | in year |  |  |  |  |  | 21.2 | **21.2** | 21.2 (19/27049) | 21.2 (1733 E) |
| 2025 | cumulative from 2017 |  |  |  |  |  | **173.9** |  | 173.9 (1733 E) | — |
| 2025 | under construction |  |  |  |  |  | **17.1** |  | 17.1 (1733 E) | — |
| 2025 | in planning |  |  |  |  |  | **67.2** |  | 67.2 (1733 E) | — |
| 2026 | in year |  |  |  |  |  |  | **6.22** | 6.22 (19/27049) | — |
| 2026 | cumulative from 2022 |  |  |  |  |  |  | **104.53** | 104.53 (19/27049) | — |
| 2026 | under construction |  |  |  |  |  |  | **7.7** | 7.7 (19/27049) | — |
| 2026 | in planning |  |  |  |  |  |  | **92.7** | 92.7 (19/27049) | — |

#### `anlagen`: Radverkehrsanlagen, facility length with each side counted (reports on 2020 and 2021)

| year | quantity | target | FB 2020 web | 1392 I | 0389 A | current | revisions |
|---|---|---|---:|---:|---:|---|---|
| 2020 | in year |  | 53.3 | **53.5** |  | 53.5 (1392 I) | 53.3 (FB 2020 web) |
| 2020 | under construction |  |  | **30.6** |  | 30.6 (1392 I) | — |
| 2020 | in planning |  |  | **120.2** |  | 120.2 (1392 I) | — |
| 2021 | in year |  |  |  | **39.1** | 39.1 (0389 A) | — |
| 2021 | under construction |  |  |  | **58** | 58 (0389 A) | — |
| 2021 | in planning |  |  |  | **221.8** | 221.8 (0389 A) | — |

<details><summary>Notes stored on Berlin rows</summary>

| item | year | quantity | value | document | note |
|---|---|---|---:|---|---|
| anlagen | 2020 | in year | 53.5 | 1392 I | facility length, each side counted; includes 25.0 km of pop-up cycle lanes (Straßenverkehrsrechtliche Anordnung) |
| anlagen | 2020 | under construction | 30.6 | 1392 I | facility length, each side counted |
| anlagen | 2020 | in planning | 120.2 | 1392 I | facility length, each side counted |
| anlagen | 2020 | in year | 53.3 | FB 2020 web | Senate website edition of the report in rN 1392 I; doc_date from the imprint 'Berlin, Juli 2021' (PDF p. 2; day not printed, first of the month used); the column's cells (17.7 + 5.4 + 5.4 + 25.0) sum to 53.5, as printed in rN 1392 I |
| anlagen | 2021 | in year | 39.1 | 0389 A | facility length, each side counted |
| anlagen | 2021 | under construction | 58 | 0389 A | facility length, each side counted; printed '58' |
| anlagen | 2021 | in planning | 221.8 | 0389 A | facility length, each side counted |
| vorrangnetz | 2021 | in year | 7.4 | 0389 A | scope: bezirkliches Radverkehrsprogramm only (not all actors); main-road facilities halved to network length (footnote 3) |
| vorrangnetz | 2021 | cumulative from 2017 | 27.4 | 0389 A | cumulative 2017–2021; scope: bezirkliches Radverkehrsprogramm only (not all actors); main-road facilities halved to network length (footnote 3) |
| ergaenzungsnetz | 2021 | in year | 7.4 | 0389 A | scope: bezirkliches Radverkehrsprogramm only (not all actors); main-road facilities halved to network length (footnote 3) |
| ergaenzungsnetz | 2021 | cumulative from 2017 | 29.3 | 0389 A | cumulative 2017–2021; scope: bezirkliches Radverkehrsprogramm only (not all actors); main-road facilities halved to network length (footnote 3) |
| hauptverkehrsstrassen | 2021 | in year | 3.1 | 0389 A | scope: bezirkliches Radverkehrsprogramm only (not all actors); main-road facilities halved to network length (footnote 3) |
| hauptverkehrsstrassen | 2021 | cumulative from 2017 | 9.6 | 0389 A | cumulative 2017–2021; scope: bezirkliches Radverkehrsprogramm only (not all actors); main-road facilities halved to network length (footnote 3) |
| sonstige_strecke | 2021 | in year | 0.5 | 0389 A | scope: bezirkliches Radverkehrsprogramm only (not all actors); main-road facilities halved to network length (footnote 3) |
| sonstige_strecke | 2021 | cumulative from 2017 | 3.1 | 0389 A | cumulative 2017–2021; scope: bezirkliches Radverkehrsprogramm only (not all actors); main-road facilities halved to network length (footnote 3) |
| total | 2021 | in year | 18.4 | 0389 A | scope: bezirkliches Radverkehrsprogramm only (not all actors); main-road facilities halved to network length (footnote 3) |
| total | 2021 | cumulative from 2017 | 69.4 | 0389 A | cumulative 2017–2021; scope: bezirkliches Radverkehrsprogramm only (not all actors); main-road facilities halved to network length (footnote 3) |
| vorrangnetz | 2024 | cumulative from 2022 | 39.4 | 1733 C | cumulative 2022–2024 |
| ergaenzungsnetz | 2024 | cumulative from 2022 | 23.2 | 1733 C | cumulative 2022–2024 |
| radverkehrsnetz | 2024 | cumulative from 2022 | 62.6 | 1733 C | cumulative 2022–2024 |
| hauptverkehrsstrassen | 2024 | cumulative from 2022 | 7.3 | 1733 C | cumulative 2022–2024 |
| sonstige_strecke | 2024 | cumulative from 2022 | 6.2 | 1733 C | cumulative 2022–2024 |
| total | 2024 | cumulative from 2022 | 76.1 | 1733 C | cumulative 2022–2024 |
| vorrangnetz | 2025 | cumulative from 2017 | 78.2 | 1733 E | cumulative 2017–2025 |
| ergaenzungsnetz | 2025 | cumulative from 2017 | 61.9 | 1733 E | cumulative 2017–2025 |
| radverkehrsnetz | 2025 | cumulative from 2017 | 140.1 | 1733 E | cumulative 2017–2025 |
| hauptverkehrsstrassen | 2025 | cumulative from 2017 | 16.8 | 1733 E | cumulative 2017–2025 |
| sonstige_strecke | 2025 | cumulative from 2017 | 17 | 1733 E | cumulative 2017–2025 |
| total | 2025 | cumulative from 2017 | 173.9 | 1733 E | cumulative 2017–2025 |
| vorrangnetz | 2026 | cumulative from 2017 | 78.2 | 19/25987 | printed as implemented 'insgesamt' at the time of the answer (20 May 2026), no start year stated; cumulative_from 2017 because rN 1733 E prints the same 78.2 for 2017–2025 |
| vorrangnetz | 2026 | in year | 2.3 | 19/27049 | 2026 to 1 September 2026 (Stand: 01.09.2026) |
| ergaenzungsnetz | 2023 | in year | 55.1 (suspect) | 19/27049 | stored as printed; the row total printed is 36.24 km, which with the other cells (30.87 km) leaves 5.37 for 2023, the 2023 column total 25.9 implies 5.1 (25.9 − 13.6 − 7.2), and Drs 19/25987 prints 5.1 |
| ergaenzungsnetz | 2026 | in year | 3.77 | 19/27049 | 2026 to 1 September 2026 (Stand: 01.09.2026) |
| sonstiges_netz | 2026 | in year | 0.15 | 19/27049 | 2026 to 1 September 2026 (Stand: 01.09.2026) |
| total | 2026 | in year | 6.22 | 19/27049 | 2026 to 1 September 2026 (Stand: 01.09.2026) |
| total | 2026 | under construction | 7.7 | 19/27049 | 'derzeit' at the time of the answer (14 Sep 2026); printed as km of Radverkehrsanlagen 'im Bau bzw. in Bauvorbereitung' |
| total | 2026 | in planning | 92.7 | 19/27049 | 'derzeit' at the time of the answer (14 Sep 2026) |
| vorrangnetz | 2026 | cumulative from 2022 | 49.46 | 19/27049 | cumulative 2022 to 1 September 2026 (Summe column, counted from 2022, not from 2017); the row cells as printed (14.4 + 13.6 + 10.8 + 8.6 + 2.3) sum to 49.7 |
| ergaenzungsnetz | 2026 | cumulative from 2022 | 36.24 | 19/27049 | cumulative 2022 to 1 September 2026 (Summe column, counted from 2022, not from 2017); the row cells as printed sum to 85.97 because of the 2023 cell 55.1 (suspect); 36.24 is consistent with about 5.37 for 2023 |
| sonstiges_netz | 2026 | cumulative from 2022 | 18.83 | 19/27049 | cumulative 2022 to 1 September 2026 (Summe column, counted from 2022, not from 2017); the row cells as printed (3.1 + 7.2 + 3.2 + 5.1 + 0.15) sum to 18.75 |
| total | 2026 | cumulative from 2022 | 104.53 | 19/27049 | cumulative 2022 to 1 September 2026 (Summe column, counted from 2022, not from 2017); the column totals as printed (27.5 + 25.9 + 23.6 + 21.2 + 6.22) sum to 104.42; the three row sums give 104.53 |

</details>

### Other cities: 11 report rows

Only official figures are stored. Not every row is in km: Copenhagen counts initiatives and Strasbourg counts operations (judgement call 3).

| city | plan item | year | quantity | value | document | dated | note |
|---|---|---|---|---:|---|---|---|
| vienna | hauptradverkehrsnetz | 2025 | under construction | 20.4 | [Bilanz Radwegeausbau 2025](https://www.fahrradwien.at/wp-content/uploads/sites/2/2026/01/Radwegoffensive_2025_Bilanz.pdf) | 2026-01-09 | km of projects in the main cycle network whose realisation began in 2025 (started, not completed); header prints 20.447 m; no date printed; doc_date is the PDF creation date |
| copenhagen | cykelstiprioriteringsplan | 2025 | cumulative from 2017 | 37 | [Mobilitetsredegørelse 2026](https://byudvikling.kk.dk/sites/default/files/2026-07/Mobilitetsredeg%C3%B8relse%202026_opt-a.pdf) | 2026-06-30 | initiatives of the 151 in the Cykelstiprioriteringsplan 2017–2025 fully implemented 2017–2025 (completed, funded or under construction); not km; report dated 'Juni 2026'; doc_date is the PDF modification date |
| oslo | nye_og_oppgraderte | 2024 | cumulative from 2015 | 155 | [pressemelding 11 November 2024](https://aktuelt.oslo.kommune.no/oslos-sykkelsatsing-har-bidratt-til-mer-og-tryggere-sykling) | 2024-11-11 | new and upgraded cycleway since 2015 ('bygget og oppgradert'), as stated with the EY evaluation of the strategy |
| strasbourg | operations | 2024 | cumulative from 2021 | 52 | [Plan vélo Eurométropole 2024-10-30](https://www.strasbourg.eu/-/plan-velo-eurometropole-102024) | 2024-10-30 | operations completed by end of 2024 (printed as 'auront été réalisées', a forecast at publication), 30 of them outside the city of Strasbourg; not km; cumulative_from 2021 is the plan's launch year (the article counts the plan's operations, no start date printed) |
| bordeaux | reseau_cyclable | 2024 | cumulative from 2021 | 107 | [CRC Nouvelle-Aquitaine, Bordeaux Métropole plan vélo](https://www.merignac.com/sites/default/files/2026-04/crc-bordeaux-metropole-plan-velo.pdf) | 2025-08-05 | km of cycle routes of all types added since the plan's adoption, per Bordeaux Métropole's monitoring tables, to end of 2024; whole Métropole; cumulative_from 2021 is the plan's adoption year (25 November 2021) |
| wroclaw | nowe_trasy | 2025 | cumulative from 2022 | 40 | [Urząd Miejski Wrocławia 2025-09-05](https://www.wroclaw.pl/dla-mieszkanca/inwestycje-rowerowe-we-wroclawiu-podsumowanie-plan-2030) | 2025-09-05 | printed 'blisko 40 kilometrów' (nearly 40 km) of routes built since the plan was adopted; cumulative_from 2022 is the year the plan was presented (11 May 2022); no adoption resolution found |
| warsaw | trasy_rowerowe | 2020 | cumulative from 2013 | 200 | [ZDM 2020-02-04](https://zdm.waw.pl/aktualnosci/jaka-ma-byc-rowerowa-warszawa-2030/) | 2020-02-04 | printed 'ok. 200 km nowych tras' (about 200 km of new routes) since the programme was prepared |
| krakow | infrastruktura_rowerowa | 2019 | in year | 3.7 | [Magiczny Kraków 2022-05-31](https://krakow.pl/aktualnosci/260628,1912,komunikat,250_kilometrow_infrastruktury_rowerowej_miasta.html) | 2022-05-31 | printed 'ok. 3,7 km ścieżek'; city-wide paths, not tied to a plan item |
| krakow | infrastruktura_rowerowa | 2020 | in year | 5.7 | [Magiczny Kraków 2022-05-31](https://krakow.pl/aktualnosci/260628,1912,komunikat,250_kilometrow_infrastruktury_rowerowej_miasta.html) | 2022-05-31 | city-wide paths, not tied to a plan item |
| krakow | infrastruktura_rowerowa | 2021 | in year | 0.85 | [Magiczny Kraków 2022-05-31](https://krakow.pl/aktualnosci/260628,1912,komunikat,250_kilometrow_infrastruktury_rowerowej_miasta.html) | 2022-05-31 | city-wide paths, not tied to a plan item |
| bratislava | cyklisticka_infrastruktura | 2025 | in year | 14.2 | [bratislava-sk 2025-12-03](https://bratislava.sk/spravy/cyklisticka-infrastruktura-v-bratislave-sa-rozsiruje) | 2025-12-03 | new cycling infrastructure built by the city in 2025, all types |

## Berlin plan page (`content/plans/berlin.yaml`)

The page as rendered, with its quotes where the app actually puts them. This shows the misplacement in judgement call 5: the 55.1 table row appears under "Completed projects", and the geoportal abstract appears under "Mapped on the network". The Task 9 chart (target steps, documents' markers, completed projects and the mapped series) is not built yet.

*Page title: Reported, completed, mapped*

Berlin's Radverkehrsplan sets a yearly path for its planned cycle network: so many km of the priority network (Vorrangnetz) and of the supplementary network (Ergänzungsnetz) per year up to 2030 [1]. The plan itself expects that path to be adjusted, quoted below. This page sets three series against it. They count different things, and none of them confirms or refutes another.

#### Reported (dimension: reported)

Reported km are the Senate's own. The yearly progress report goes to the main committee as a report (rote Nummer); written questions are answered as Drucksachen. Both draw on a project database run by infraVelo [2] and count route length once per street section, so a street with facilities on both sides counts once. The report on 2021 still halved main-road facilities to reach that basis, quoted below [3].

> “Die Ausbaupfade können beziehungsweise müssen dann entsprechend des aktuellen Umsetzungsstandes angepasst werden.”
>
> *(The expansion paths can, or must, then be adjusted to the current state of implementation.)*
>
> — Abgeordnetenhaus Berlin (Vorlage zur Kenntnisnahme of the Senatsverwaltung für Umwelt, Verkehr und Klimaschutz) [1]

Documents revise one another, and every printed figure is kept. For 2025 the latest answer reports 8.6 km on the priority network, as the 2025 report does, while an answer of May 2026 printed 9.8 km for the same year [4] [5]. For the supplementary network in 2023 the latest answer prints 55.1 km, which neither its own column total nor the earlier answer's 5.1 km supports. It stays as printed, with a note, and is marked suspect, so the earlier figure is shown as current [4].

> “Da an beiden Straßenseiten Radverkehrsanlagen bestehen, entspricht dies einer Länge im Radnetz von 9,4 Kilometern (18,7 geteilt durch 2).”
>
> *(As there are cycling facilities on both sides of the street, this corresponds to a length in the cycle network of 9.4 km (18.7 divided by 2).)*
>
> — Senatsverwaltung für Umwelt, Mobilität, Verbraucher- und Klimaschutz (SenUMVK) [3]

#### Completed projects (dimension: completed)

Completed projects come from the measures dataset on Berlin's geoportal, a view of the planning and implementation of cycling infrastructure that is fed from the same infraVelo database, quoted below [6]. Our count takes the projects marked completed, by the year their works ended. It is a separate series, so it and the reported km need not agree.

> “Ergänzungsnetz 10,0 55,1 9,6 7,5 3,77 36,24”
>
> *(Supplementary network 10.0 55.1 9.6 7.5 3.77 36.24 (km implemented in 2022, 2023, 2024, 2025, 2026 to 1 September, and the row total).)*
>
> — Abgeordnetenhaus Berlin (answer of the Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt) [4]

#### Mapped on the network (dimension: mapped)

The third series is ours: OpenStreetMap way-sides in tiers A and B that run along a segment of the planned network, measured per side in mapped km [d1]. Mapped km are not km completed to the plan's standard. They include tracks that existed long before the plan. The level therefore says little about the plan. The comparable quantity is the change since the start of 2022, the plan's first target year, and even that change is context for the reported figures, not a check on them.

> “Der Datensatz zeigt die Planungen und Umsetzungen baulicher Radverkehrsinfrastruktur. Er ermöglicht es eine Übersicht und Auswertung über den Bestand vorzunehmen. Die Datenerfassung erfolgte kontinuierlich über die Datenbank der GB infraVelo GmbH.”
>
> *(The dataset shows the planning and implementation of structural cycling infrastructure. It allows an overview and evaluation of the stock. Data were captured continuously via the database of GB infraVelo GmbH.)*
>
> — Land Berlin, Geoportal (gdi.berlin.de); data from GB infraVelo GmbH [6]

The series is sensitive to how mappers draw cycleways and to the matching method. Between 2021 and 2022 Berlin's tiers A and B moved from tags on road centrelines to separately drawn ways, and the change moves with the method version; the earlier version `overlay_v2` showed a smaller change than the figures here, which come from `overlay_v3`. On the priority network the overlay finds 446.3 mapped km at the start of 2022 and 492.2 km in the current snapshot (October 2026), a change of 46.0 km. On the supplementary network it finds 619.8 km and 639.5 km, a change of 19.6 km. Changes are computed before rounding, so they can differ in the last digit from the difference of the printed endpoints. These are changes in what is mapped, not km of new infrastructure.

**Facts** (printed in the text; value as evaluated now against the DB and config)

| id | expression | printed | evaluates to | match |
|---|---|---:|---:|---|
| `vrn-2025` | `plan.berlin_rvp_2021.vorrangnetz.2025.implemented_in_year` | 8.6 | 8.6 | yes |
| `vrn-2025-report` | `plan.berlin_rvp_2021.vorrangnetz.2025.implemented_in_year.1733 E` | 8.6 | 8.6 | yes |
| `vrn-2025-may` | `plan.berlin_rvp_2021.vorrangnetz.2025.implemented_in_year.19_25987` | 9.8 | 9.8 | yes |
| `erg-2023` | `plan.berlin_rvp_2021.ergaenzungsnetz.2023.implemented_in_year.19_27049` | 55.1 | 55.1 | yes |
| `erg-2023-may` | `plan.berlin_rvp_2021.ergaenzungsnetz.2023.implemented_in_year.19_25987` | 5.1 | 5.1 | yes |
| `ov-vrn-2022` | `overlay.berlin.vorrangnetz.2022-01-01.ab_km` | 446.3 | 446.252 | yes |
| `ov-vrn-now` | `overlay.berlin.vorrangnetz.2026-10-03.ab_km` | 492.2 | 492.247 | yes |
| `ov-vrn-change` | `overlay_change.berlin.vorrangnetz.2022-01-01.2026-10-03` | 46.0 | 45.995 | yes |
| `ov-erg-2022` | `overlay.berlin.ergaenzungsnetz.2022-01-01.ab_km` | 619.8 | 619.812 | yes |
| `ov-erg-now` | `overlay.berlin.ergaenzungsnetz.2026-10-03.ab_km` | 639.5 | 639.462 | yes |
| `ov-erg-change` | `overlay_change.berlin.ergaenzungsnetz.2022-01-01.2026-10-03` | 19.6 | 19.65 | yes |

**Sources**

1. `berlin-radverkehrsplan-vo19-013`: Abgeordnetenhaus Berlin (Vorlage zur Kenntnisnahme of the Senatsverwaltung für Umwelt, Verkehr und Klimaschutz): [Vorlage zur Kenntnisnahme vo19-013: Verordnung über Radverkehrsplan des Landes Berlin vom 16. November 2021 (with the Radverkehrsplan as Anlage)](https://www.parlament-berlin.de/ados/19/IIIPlen/vorgang/verordnungen/vo19-013.pdf), 2021-11-16 (parliament, de)
2. `berlin-fortschrittsbericht-2025`: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (SenMVKU): [Fahrrad Berlin – Fortschrittsbericht 2025 (Anlage 1 to Hauptausschuss report rote Nr. 1733 E of 12 August 2026; scanned PDF, excerpts transcribed from the page images)](https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-1733.E-v.pdf), 2026-08-12 (official, de)
3. `berlin-fortschrittsbericht-2021`: Senatsverwaltung für Umwelt, Mobilität, Verbraucher- und Klimaschutz (SenUMVK): [Fahrrad Berlin – Fortschrittsbericht 2021 (Hauptausschuss report rote Nr. 0389 A of 5 July 2022)](https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-0389.A-v.pdf), 2022-07-05 (official, de)
4. `berlin-drs-19-27049`: Abgeordnetenhaus Berlin (answer of the Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt): [Schriftliche Anfrage 19/27049: Verkehrspolitische Bilanz des Senats (answer of 14 September 2026)](https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-27049.pdf), 2026-09-14 (parliament, de)
5. `berlin-drs-19-25987`: Abgeordnetenhaus Berlin (answer of the Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt): [Schriftliche Anfrage 19/25987: Acht Jahre Mobilitätsgesetz – Zwischen Anspruch und Wirklichkeit im Radverkehr (answer of 20 May 2026)](https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-25987.pdf), 2026-05-20 (parliament, de)
6. `berlin-gdi-radverkehrsmassnahmen`: Land Berlin, Geoportal (gdi.berlin.de); data from GB infraVelo GmbH: [Radverkehrsmaßnahmen (seit 2021), WFS service metadata record (publication date 2026-09-08)](https://gdi.berlin.de/geonetwork/srv/api/records/9093d642-e2c4-4cb6-9798-4d1e3f12f3bf), 2026-09-08 (official, de)

**Data references**

- d1. velometer ADR 0006, mapped km (`docs/adr/0006-mapped-km-not-built-km.md`, ## Decision)

## Overlay: mapped A+B km on Berlin's plan network

Source: `docs/review/m8-overlay.md` and the `plan_overlay` rows (read-only). The network is the Senate's Radverkehrsnetz WFS, fetched 2026-10-07: Vorrangnetz 873.1 km, Ergänzungsnetz 1,507.8 km. The figures are mapped km per side in tiers A and B, classifier v4 (ADR 0006). They are not km built to the plan's standard.

There are three method versions. All their rows are kept in the database; the app and the facts read the latest (v3).

| version | rule |
|---|---|
| `overlay_v1` | a piece counts within 12 m of the network centreline and at most 30° off its direction; parts under 20 m are dropped per way-side |
| `overlay_v2` | as v1, but separately mapped ways (cycleway, footway, path beside the road) get a 25 m buffer; road-side tags on the centreline keep 12 m |
| `overlay_v3` | v2's buffers, but the 20 m minimum is tested on touching kept parts of one tier merged across OSM ways, not on each way-side |

Why the versions exist: v1 fell every year from 2020 (Vorrangnetz 473 → 315 km). In those years Berlin's cycle tracks were redrawn from centreline tags to separate ways, which often lie more than 12 m from the centreline on wide streets. v2 fixed that. The review then found that v2's per-way-side 20 m minimum dropped short OSM ways that lie wholly on the network, and that loss grew from 4 to 24 km as ways were split more finely over the years. v3 fixes that; what it still drops stays under 5 km and level over time.

**A+B mapped km on the network, per snapshot:**

| snapshot | run | Vorrang v1 | Vorrang v2 | Vorrang v3 | Ergänzung v1 | Ergänzung v2 | Ergänzung v3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2018-01-01 | 735 | 473.2 | 490.1 | 497.5 | 614.2 | 635.4 | 645.4 |
| 2019-01-01 | 736 | 460.7 | 476.0 | 483.8 | 610.0 | 630.5 | 640.9 |
| 2020-01-01 | 737 | 457.8 | 476.8 | 485.0 | 620.3 | 643.2 | 654.0 |
| 2021-01-01 | 738 | 437.6 | 489.0 | 497.7 | 614.6 | 656.9 | 668.1 |
| 2022-01-01 | 739 | 362.9 | 436.9 | 446.3 | 544.8 | 607.7 | 619.8 |
| 2023-01-01 | 740 | 358.2 | 450.4 | 463.0 | 537.1 | 611.7 | 625.7 |
| 2024-01-01 | 741 | 329.8 | 441.8 | 460.0 | 502.2 | 595.5 | 617.2 |
| 2025-01-01 | 742 | 320.4 | 452.5 | 473.0 | 489.3 | 590.5 | 615.6 |
| 2026-01-01 | 743 | 303.1 | 450.3 | 476.2 | 468.8 | 604.3 | 636.9 |
| 2026-10-03 (current) | 713 | 315.4 | 465.3 | 492.2 | 469.6 | 605.7 | 639.5 |
| **change 2022-01-01 → current** | | -47.5 | +28.4 | +46.0 | -75.1 | -2.0 | +19.6 |
| change 2022-01-01 → 2026-01-01 | | -59.8 | +13.5 | +29.9 | -76.0 | -3.4 | +17.1 |
| change 2018-01-01 → current | | -157.8 | -24.8 | -5.2 | -144.6 | -29.7 | -6.0 |

Numbers come from the database and are rounded once. The log rounds some v1/v2 rows 0.1 km differently.

**Reading it:**

- **v1 is not usable.** It measures the mapping style.
- **v2 and v3 agree on the shape:** a drop in 2021→2022, when city-wide stored A fell by 125 km in the redraw, then a rise. They disagree on the size of the change since 2022: Vorrangnetz +28.4 (v2) against +46.0 (v3), Ergänzungsnetz −2.0 against +19.6. The 17–22 km gap is the short-way loss described above, so the difference comes from the method, not from the street.
- **Against 2018, v3 is about level** (−5.2 / −6.0 km).
- **The page prints the v3 values** (446.3 → 492.2, +46.0; 619.8 → 639.5, +19.6). It says the series is sensitive to how mappers draw cycleways and to the method version, and that these are changes in what is mapped (see the Berlin plan page below).

### Sanity maps (run 743, OSM 2026-01-01)

`data/` is git-ignored, so the maps are not committed; the links work in a local checkout.

- [overlay_v1](../../data/maps/berlin_overlay_v1_2026-01-01.png): Vorrangnetz 225 of 873 km matched, Ergänzungsnetz 332 of 1,507 km. Matches follow the main radial and ring roads. Long unmatched stretches are mostly streets whose tracks are drawn as separate ways beyond 12 m.
- [overlay_v2](../../data/maps/berlin_overlay_v2_2026-01-01.png): 312 / 418 km matched. The 282 km of side pieces matched only at 25 m are orange; they run along the network roads' own sidepaths. [Zoomed crops of four areas](../../data/maps/berlin_overlay_v2_crops.png) show the doubtful pieces are short stubs at junctions.
- [overlay_v3](../../data/maps/berlin_overlay_v3_2026-01-01.png) (new for this review): 316 / 423 km matched. The 58 km of side pieces that v3 keeps and v2 drops are magenta (25.8 km Vorrangnetz, 32.7 km Ergänzungsnetz, equal to the v3 − v2 difference in the table). They lie as short pieces inside runs that are already matched, mostly in the inner districts, and not as new isolated lines. The script is the scratchpad `overlay_map_v3.py`, run read-only against the database in about 50 s. It is not the lost v1/v2 script, so its "matched" network km may be counted slightly differently (judgement call 19).

![overlay_v3 sanity map](../../data/maps/berlin_overlay_v3_2026-01-01.png)

## Counters

### Index per city (`counter_index`, read-only)

Index of counts recorded at counter sites, 2019 = 100 (Madrid: 2020 = 100; Barcelona: index of average daily intensity). The number of qualifying sites is in brackets. For the base year, that is the number of sites with 90 % complete days in 2019 (Barcelona: all twelve months). For every other year, it is the number of sites in that year's link with the neighbouring year towards the base. "none" means fewer than 3 such sites, or a broken chain. **2020 is the COVID year.** A step into or out of it is no trend.

| year | Berlin | Paris | Vienna | Helsinki | Madrid | Oslo | Barcelona |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2003 |  |  |  |  |  | none (0) |  |
| 2004 |  |  |  |  |  | none (0) |  |
| 2005 |  |  |  |  |  | none (0) |  |
| 2006 |  |  |  |  |  | none (0) |  |
| 2007 |  |  |  |  |  | none (0) |  |
| 2008 |  |  |  |  |  | none (0) |  |
| 2009 |  |  |  |  |  | none (0) |  |
| 2010 |  |  |  |  |  | none (0) |  |
| 2011 |  |  |  |  |  | none (0) |  |
| 2012 | none (0) |  |  |  |  | none (0) |  |
| 2013 | none (1) |  | 71.7 (10) |  |  | none (0) |  |
| 2014 | none (1) |  | 88.1 (12) | 87.6 (5) |  | none (0) |  |
| 2015 | none (1) |  | 87.5 (12) | 91.1 (8) |  | none (0) |  |
| 2016 | 93.8 (14) | 75.9 (7) | 93.9 (12) | 92.2 (13) |  | none (2) |  |
| 2017 | 89.6 (23) | 76.9 (6) | 93.0 (12) | 90.8 (12) |  | 92.4 (5) | 89.2 (19) |
| 2018 | 101.3 (20) | 66.9 (8) | 99.2 (13) | 104.4 (13) |  | 108.7 (7) | 95.8 (31) |
| 2019 | 100.0 (21) | 100.0 (31) | 100.0 (13) | 100.0 (13) | none (0) | 100.0 (11) | 100.0 (127) |
| **2020 (COVID year)** | 114.6 (21) | 130.2 (26) | 112.0 (13) | 106.2 (13) | 100.0 (33) | 128.3 (9) | 91.8 (114) |
| 2021 | 102.2 (22) | 141.3 (49) | 113.3 (13) | 85.6 (13) | none (0) | 103.5 (8) | 119.3 (164) |
| 2022 | 102.0 (23) | 165.2 (49) | 113.8 (13) | 79.0 (9) | none (0) | 113.6 (10) | 132.9 (165) |
| 2023 | 98.5 (23) | 186.5 (48) | 116.9 (18) | 85.6 (10) | none (0) | 117.2 (13) | 135.8 (174) |
| 2024 | 101.6 (29) | 191.5 (60) | 122.5 (17) | 85.9 (8) | none (0) | 124.7 (14) | 135.3 (191) |
| 2025 | 100.3 (29) | 205.2 (74) | 121.6 (16) | 84.2 (9) |  | 140.6 (15) | 140.3 (207) |
| 2026 |  | none (0) |  | none (0) |  | none (0) |  |

Base year and series: berlin 2019 = 100 (`counts`); paris 2019 = 100 (`counts`); vienna 2019 = 100 (`counts`); helsinki 2019 = 100 (`counts`); madrid 2020 = 100 (`counts`); oslo 2019 = 100 (`counts`); barcelona 2019 = 100 (`avg_daily_intensity`).

Reading it:

- **Paris doubles** (205.2 in 2025), and its site count grows from 31 to 74.
- **Oslo** reaches 140.6, **Barcelona** 140.3 and **Vienna** 121.6. **Berlin** is flat at about 100.
- **Helsinki** falls to about 85 from 2021. Its 2024 and 2025 links rest on 8–9 sites, two of which step down during works (judgement call 1): without them, 2024 is 93.9 and 2025 is 99.9, and the ×1.5 rule gives 101.8 for 2025.
- **Madrid** has only its base year (judgement call 10).
- **Oslo 2016** and **Berlin 2013–15** have values from fewer than 3 sites, so they show none.

The per-city portal research, fixtures and rules are in `docs/review/m8-counters.md`.

### Counter page (`content/counters.yaml`)

*Page title: What the counters record*

Seven of our cities publish open bike-counter data, and the Counts tab sets an index of it beside our mapped km. It is context: it shows how many bicycles were recorded at counter sites, not how much cycling a city has.

#### What a counter measures (dimension: measure)

A permanent counter records each bicycle that crosses its counting line, quoted below [1]. It says nothing about trips elsewhere or who rides. Oslo's sites are the state's counters, on state and county roads and a few municipal ones [2]. Barcelona's files give one average value per gauge, month and type of day [3], indexed as a separate series.

> “An den Dauerzählstellen werden alle Fahrräder, welche die Erfassungsquerschnitte der Zählstellen überfahren, gezählt.”
>
> *(At the permanent counting stations, every bicycle that crosses a station's counting cross-section is counted.)*
>
> — Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt Berlin [1]

#### Where counters stand (dimension: selection)

Each city chooses where its counters stand, so the sites speak for themselves, not for the city's streets. The set changes as counters are added, switched off for works or break down, quoted below [4]. The index therefore compares only sites complete on nine days in ten (Barcelona: all twelve months) in both years of each step, chained from 2019 (Madrid: 2020). A year with fewer than three such sites has no value.

> “Le nombre de compteurs évolue au fur et à mesure des aménagements cyclables. Certains compteurs peuvent être désactivés pour travaux ou subir ponctuellement une panne.”
>
> *(The number of counters changes as cycling facilities are added. Some counters may be switched off for works or occasionally break down.)*
>
> — Ville de Paris, Direction de la Voirie et des Déplacements [4]

#### The COVID year (dimension: covid)

2020 was the COVID year. Counts recorded at counter sites moved away from their 2019 level in every city with both years; Berlin's index stood at 114.6. Charts mark the year, and a step into or out of it is no trend.

#### Breaks in a series (dimension: breaks)

A portal can change how it measures. Madrid's files hold no data from July 2021 to August 2022; the portal reports a change of detectors in that time and advises against comparing data across it, quoted below [5]. Its index has a value for 2020 only.

> “Se advierte a que la comparación de estos conjuntos de datos no es recomendable al haberse cambiado los parámetros y tecnología de medición con objeto de mejorar la calidad de la información obtenida.”
>
> *(Users are warned that comparing these datasets is not advisable, as the measurement parameters and technology were changed to improve the quality of the information obtained.)*
>
> — Ayuntamiento de Madrid [5]

#### Counts beside mapped km (dimension: side_by_side)

Both lines are indexes, so their shapes can be read together. They describe different things: a few street sections against a whole city's mapped network. A rise in both can coincide without one explaining the other.

**Facts** (printed in the text; value as evaluated now against the DB and config)

| id | expression | printed | evaluates to | match |
|---|---|---:|---:|---|
| `berlin-2020` | `counter.berlin.2020` | 114.6 | 114.552 | yes |

**Sources**

1. `berlin-zaehlstellen`: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt Berlin: [Zählstellen und Fahrradbarometer: Fahrradverkehr in Zahlen](https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrsplanung/radverkehr/weitere-radinfrastruktur/zaehlstellen-und-fahrradbarometer/) (official, de)
2. `vegvesen-trafikkdata`: Statens vegvesen: [Trafikkdata (dataset)](https://dataut.vegvesen.no/dataset/trafikkdata) (official, nb)
3. `barcelona-aforaments-detall`: Ajuntament de Barcelona, Open Data BCN: [Detall dels aforaments de mobilitat de la ciutat de Barcelona (dataset aforaments-detall)](https://opendata-ajuntament.barcelona.cat/data/ca/dataset/aforaments-detall) (official, ca)
4. `paris-comptage-velo`: Ville de Paris, Direction de la Voirie et des Déplacements: [Comptage vélo - Données compteurs (dataset information)](https://opendata.paris.fr/explore/dataset/comptage-velo-donnees-compteurs/information/) (official, fr)
5. `madrid-aforos-bicicletas`: Ayuntamiento de Madrid: [Aforos de peatones y bicicletas (dataset 300321-0-aforos-peatones-bicicletas)](https://datos.madrid.es/dataset/300321-0-aforos-peatones-bicicletas) (official, es)
