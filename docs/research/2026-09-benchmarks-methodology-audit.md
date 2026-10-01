# European Cycling-Infrastructure Benchmarks: Methodology & Reproducibility Audit — Update, September 2026

**Bottom line:** Between mid-2025 and September 2026 no new edition of any major cross-city cycling-infrastructure benchmark came out, including Clean Cities, Copenhagenize and ECF/QECIO. The ranking Dennis cites (Clean Cities, May 2025) turns out on inspection to be mostly city-submitted data rather than OpenStreetMap, so nobody can reproduce it. What did change is the tooling and the politics: the ohsome API moved to a new, account-gated v2.0 (the old API is being shut down in 2026), Berlin's 2025 build-out fell to about 21 km, and Die Linke won the 20 September 2026 Berlin election. The defensible path is a self-built, versioned OSM pipeline, using ECF's published QECIO tag logic as the primary metric, cross-checked against official city figures.

## TL;DR
- **Clean Cities has no 2026 cycling ranking (UNCHANGED since July 2025).** The 2025 "Streets for Kids" protected-cycling indicator mostly uses city-submitted km. OSM, via ECF's tag filter, was only the fallback. The denominator is the entire public road network, and there is no published code or licence. You cannot reproduce Berlin's 17% / 925 km from OSM, and Vienna's figure was already revised after publication, from 14% to 22.0%.
- **The toolchain changed (NEW):** ohsome API 2.0 has a new backend and requires a user account. HeiGIT's 4 August 2026 roadmap update schedules "Decommissioning of the legacy ohsome API and the original OSHDB framework" for "November 31, 2026" (HeiGIT's wording; presumably end of November), with 2.0 due to be "stable" in October 2026. HeiGIT's ohsome-planet produces GeoParquet from OSM history files. Rebuild any 2018–2026 time series on full-history PBF plus ohsome-planet and DuckDB, not on old ohsome v1 scripts.
- **Berlin (NEW):** the Senate's progress report, reported by dpa/Tagesspiegel on 8 September 2026, gives 21.2 km built in 2025. It says "knapp 27 Millionen Euro" (just under €27M, including federal funds) was spent, against "rund 82,4 Millionen Euro" (about €82.4M) available across all budget lines, and that "only about 140km, or around 5.8%" of the planned 2,400 km network was completed between 2017 and 2025 (as The Berliner reports the Senate figure). Die Linke won with 25.7%, and Linke–Grüne–SPD talks (Sondierungen) were approved on 25 September. The Kantstraße rollback is before the Verwaltungsgericht, and work has been postponed to 7 October at the earliest.

## Key Findings (NEW vs. UNCHANGED at a glance)

| Item | Status since mid-2025 | Reproducible? |
|---|---|---|
| Clean Cities City Ranking 2025 (cycling) | UNCHANGED apart from the July 2025 Vienna correction; no 2026 ranking | No (city-submitted data, no code) |
| Clean Cities "Cities Speak" Barometer 2026 (27 Jan 2026) | NEW, but an opinion poll, not infrastructure | N/A |
| Clean Cities "State of Urban Transport 2026" (25 Mar 2026) | NEW, but no protected-cycling indicator | N/A |
| Copenhagenize Index 2025 (EIT Urban Mobility) | Published Nov 2025, i.e. NEW relative to mid-2025; no 2026 edition | No (qualitative scoring plus city data) |
| ECF QECIO 2.1 tracker | UNCHANGED (last changelog entry v2.10, Jan 2024) | Partly (tag logic published; results on ECF site) |
| Buczyński & Chavez-Pacheco, Springer (TRA 2024) | UNCHANGED; 2022 data snapshot | Partly (method described; code not verified) |
| EC report on the European Declaration on Cycling, COM(2025) 566 | NEW (30 Sep 2025) | N/A (policy report) |
| ohsome API | CHANGED: v2.0, account required, legacy API decommissioned by end Nov 2026 | Yes, but you must migrate |
| Eco-Counter Eco-Visio API | CHANGED (v1 → v2 migration reported) | Only with credentials |
| Copenhagen | Mobility Report 2026 NEW; no newer Bicycle Account than 2022 listed | Partly |
| Berlin Fortschrittsbericht (2025 data) | NEW (reported 8 Sep 2026) | Official figures; methodology break persists |

## 1. Clean Cities Campaign ranking

**Status (verified): UNCHANGED.** No 2026 cycling or city ranking exists. The site's ranking menu still lists only 2025, 2023 and 2022.\[1\] Clean Cities' outputs since September 2025 are:
- **"Cities Speak: Clean Cities Urban Mobility Barometer 2026"** (27 January 2026). OpinionWay polled 8,418 adults in nine capitals, Berlin and Warsaw among them, between 13 and 25 November 2025.\[2\]\[3\]
- **"State of Urban Transport 2026"** (25 March 2026). It benchmarks EVs, e-buses, shared bikes and zero-emission zones, and has no protected-cycling indicator.\[2\]\[4\]
- **"From Plan to Plug"** (19 May 2026), a guide to rolling out EV charging.\[2\]

One caveat: the research list covering June to September 2026 couldn't be fully loaded, so an unindexed publication can't be ruled out.

**What the 2025 edition actually measures** (from the report "Streets for Kids, Cities for All", published 5 May 2025, and its Annexes PDF):
- **Definition of "protected":** "any cycling infrastructure that is physically segregated (by a barrier, height difference or distance)". This explicitly *includes* shared foot and bike paths, pedestrian streets and greenways. It *excludes* painted lanes, cycle streets (Fahrradstraßen), living streets, shared spaces and shared bus lanes.\[5\] Including shared foot/bike paths inflates cities like Helsinki (48%) and German and Polish cities where shared paths are common.\[6\]
- **Data source:** "34 out of the 36 cities provided at least partial data". OSM was used only "in absence of official city data", as compiled by ECF with the QECIO filters: `highway=cycleway` & (`foot!=designated` | `segregated=yes`); `highway=footway|path|pedestrian` & `bicycle=designated` (segregated or not); `cycleway*=track|opposite_track`; `highway=cycleway` & `foot=designated` & `segregated!=yes`.\[5\]\[6\]
- **Unit:** the municipality with the same name. Berlin and Hamburg are "Municipality and State", London and Brussels are regions, and Antwerp excludes its port.\[5\]\[6\]
- **Normalisation:** protected km divided by *total public road network km*. That network includes motorways, trunk and regional roads and pedestrian zones, excludes private roads and footpaths, and counts each road once regardless of lanes or direction. The annex concedes that the ratio "is comparable to, but not equivalent to, the share of the road network" equipped, because paths away from roads count in the numerator.\[5\]
- **Scoring:** 10 points at a ratio of ≥0.50, with linear interpolation below that. The three indicators are weighted equally.\[5\]
- **Timing:** data was collected from December 2024 to 7 February 2025, with updates accepted until 4 April 2025.\[6\]
- **Who:** the analysis was done in-house by the "Clean Cities core team", with Martin Baierl as lead author and Jens Müller and Anka Sušická as contributors. It was EU-funded (CINEA).\[6\]\[7\]\[8\] This differs from the 2022 edition, which was commissioned from Ricardo Energy & Environment.\[9\]
- **Openness:** a data download exists alongside the executive summary and annexes. There is no licence beyond © Clean Cities/T&E, and no code.\[6\]\[8\]

**Internal inconsistencies to flag:**
- Denominators vary between tables in the same report. Helsinki's road network is 1,628 km in Table 5 but 977 km in Table 4, and Bratislava's is 1,490 km against 1,159 km.\[6\]
- Table footnotes show some cities reported only municipally managed roads, or only roads with a recorded speed limit.\[6\]
- **Vienna correction (July 2025):** after publication the city resubmitted data, taking protected km from 384.1 to 625.1 on a 2,844 km network. Its score went from 14% to 22.0%, and its cycling rank from 19th to 9th. The added km were "roads with restricted motor vehicle access that are part of the cycling network",\[8\] a category the official definition otherwise excludes.\[8\] The cited "Vienna 14%" is therefore superseded.

**Reproducibility verdict:** you can't rerun it. For most cities the numerator is whatever the administration supplied, under its own definition. Rerunning the ECF filter on current OSM data will give *different* numbers, and those differences are data about definitions, not errors. Present Clean Cities as advocacy benchmarking, not as a measurement.

## 2. Other benchmarks and indices

**Copenhagenize Index 2025 – EIT Urban Mobility Edition** (published November 2025, NEW relative to mid-2025; no 2026 edition found)
- **Scope:** 100 cities in 44 countries, picked from 150 pre-selected. The methodology is renewed and built on three pillars: *Safe and Connected Infrastructure*, *Usage and Reach*, *Policy and Support*.\[10\]\[11\]\[12\]\[13\]
- **Ranking:** Utrecht 1st, then Copenhagen, Ghent, Amsterdam, Paris.\[14\] The report's own scores are Utrecht 71.1, Copenhagen 70.8, Ghent 67.6, Amsterdam 66.6 and Paris 65.0, each a "simple average of its 13 indicator scores". The report also cites Copenhagen at "52 km of protected bicycle lanes per 100 km of roadway".
- **What's new in 2026:** only dissemination, such as an EIT session at MOBCO Paris on 9–11 June 2026.\[15\]
- **Reproducibility:** it mixes city-supplied quantitative data with expert qualitative scoring, and publishes no per-indicator dataset or code.\[12\] Use it as context only.
- **Report PDF:** https://www.eiturbanmobility.eu/wp-content/uploads/2025/11/INDEXReport_VFLight.pdf

**ECF Cycling Infrastructure Tracker (QECIO 2.x)** (UNCHANGED)
- **Coverage:** 37 countries at NUTS-3 level.\[16\]
- **Method:** Geofabrik regional PBFs processed with PyOsmium. Unidirectional infrastructure length is divided by two, and `cycleway:both` or left/right tags are split into two features.\[16\]
- **Indicators:**
  - segregated infrastructure (tracks + lanes + shared paths) ÷ *main roads* (motorway to tertiary, plus links)
  - "extended" infrastructure (adds bus lanes, cycle streets, limited-access roads) ÷ all public roads
  - tracks only ÷ main roads
  - share of one-way streets allowing contraflow
  - completeness of surface, smoothness and width tags\[16\]
- **Changelog:** the latest entry is v2.10 (11 January 2024), which introduced regional PBFs, `dual_carriageway` handling and private-access filtering.\[16\]
- **Openness:** the methodology (Annex II lists the tags) and metadata are public, and results have moved to ecf.com.\[17\] **Its definition differs from Clean Cities':** ECF's "segregated" *includes painted cycle lanes*.\[16\]
- **Links:** https://european-cyclists-federation.github.io/ and the methodology at https://european-cyclists-federation.github.io/Documents/Methodology.pdf

**Buczyński & Chavez-Pacheco, "Quantifying Cycling Infrastructure Investment Needs Across Europe Using OpenStreetMap Data"** (Springer Lecture Notes in Mobility, TRA 2024; UNCHANGED)
- **Coverage:** administrative borders of 423 TEN-T urban nodes.\[18\]
- **Findings:** 61,862 km of tracks, lanes and shared paths as of 2022. Using a simplified Sustainable Safety split between main and local roads, the authors estimate 97,000 km of need, with existing infrastructure covering about 40% on average. Coverage runs from under 10% in Malta, Greece, Portugal and Cyprus to over 80% in the Netherlands and Finland.\[18\]
- **Relationship to QECIO:** this is the QECIO 1.0 lineage, the same ECF authors.\[16\]
- **Follow-ups:** I found no replication. The closest follow-up is ECF-inspired barrier-effect work from an NTNU master's thesis (Cazaux).\[19\]
- **Link:** https://link.springer.com/chapter/10.1007/978-3-031-85578-8_21

**EU level (NEW):**
- The Commission published COM(2025) 566 on 30 September 2025, its first progress report on implementing the European Declaration on Cycling.\[20\]
- DG MOVE tendered a study in 2024 to "define a common methodology for the collection of relevant cycling data", set a baseline, and develop harmonised indicators for TEN-T urban nodes.\[21\]
- I could not verify whether that baseline dataset has been published. Treat it as the thing to watch, because it would become the quasi-official comparator.

**Eco-Counter / Eco-Visio (CHANGED):**
- The official API needs customer credentials. A reseller quotes limits of 100 requests per minute and 5,000 per day.\[22\]\[23\]
- A data-platform vendor (Huwise/Opendatasoft) reports that API v1 "will be deprecated by the end of the year", with connectors moving to v2; the exact date is unverified.\[24\]
- Public counter pages remain. The community-documented endpoints (bundesAPI/eco-visio-api) are unofficial and may break.\[25\]\[26\]
- **Implication:** scrape nothing you can't cite. Prefer city open-data exports.

**Copenhagen:**
- The city's cycling page still lists the **Bicycle Account 2022** as the latest. It promises one every two years, but I found no 2024 or 2026 Account.\[27\]
- A **Mobility Report 2026** was published around July 2026 (NEW), and the page cites about 400 km of cycle tracks.\[27\]
- Treat "was a 2026 Bicycle Account published?" as *no, not as of the city's own page*.

**Not re-verified in this update:** BIKE Index, BYPAD/PRESTO, CycleRAP, Eurostat, EEA, ITF, SUMI, and new 2025–2026 OSM-derived pan-European datasets. My search budget ran out before these could be checked, so don't cite any 2026 status for them without checking first. A useful *methodological analogue* is PeopleForBikes' US Bicycle Network Analysis 2026 update. It now treats paint-only lanes as low-stress only on roads at or below 20 mph, and it fixed OSM misclassifications such as golf-course paths and contraflow and two-way tracks.\[28\]\[29\] That is a template for LTS-style (Level of Traffic Stress) thresholds and for documenting method changes.

## 3. OSM methodology landscape

**Best-practice extraction:**
- Classify at the *way-side* level, not the way level. Explode `cycleway`, `cycleway:both`, `cycleway:left` and `cycleway:right` into sides.
- Treat `highway=cycleway` and `cycleway:*=track` as candidate "protected".\[30\]
- Treat `cycleway:*=lane` as painted unless `cycleway:*:separation` or `cycleway:*:buffer` indicates bollards or kerbs.
- Handle `highway=path|footway` with `bicycle=designated`, splitting on `segregated=yes/no`, as its own "shared path" class, never merged silently.
- Keep `bicycle_road=yes` and `cyclestreet=yes` separate, since both ECF and Clean Cities exclude or segregate them.\[5\]\[31\]
- Put "protected" into *tiered classes* (A: separated track; B: shared path; C: physically buffered lane; D: painted lane; E: cycle street), so readers can see the Clean Cities and ECF definitions as different sums of the same classes.
- Double-mapped infrastructure, where a separate `highway=cycleway` exists *and* `cycleway=separate` sits on the road, must be counted once.\[30\]

**Community differences:**
- German and Dutch mappers widely use sidewalk-style separate ways and `bicycle_road`.
- Finnish, German and Polish data carry a lot of shared foot/cycle paths (the Clean Cities report notes this).\[6\] QECIO's changelog records that its segregated/foot logic change "significantly affected the numbers for Finland".\[16\]
- Do not rely on community-level generalisations for French, Czech or Hungarian tagging without per-city tag-completeness checks. Compute share of km with `surface`, `width` and `segregated` present, as ECF does.\[16\]

**Full-history tooling (CHANGED):**
- HeiGIT is replacing OSHDB with ohsomeDB, a Postgres/PostGIS/Citus backend. The ohsome API 2.0 release candidate came in early August 2026, with public launch at State of the Map at the end of August 2026.\[32\]
- A user account is now required, and existing v1 queries "will no longer work". HeiGIT's 4 August 2026 roadmap update says 2.0 becomes "stable" in October 2026 ("No breaking changes are to be expected") and lists "November 31, 2026: Decommissioning of the legacy ohsome API and the original OSHDB framework". That replaces an earlier roadmap's "at the latest by August 2026".
- ohsomeNow moved to api.heigit.org with tokens on every request (September 2026).\[33\]\[34\]
- ohsome-planet converts OSM full-history PBFs into GeoParquet, which is the best fit for Dennis's DuckDB stack.\[35\]

**Defensible 2018–2026 time series:**
1. Take annual snapshots (1 January each year) from the full-history planet, or a Geofabrik internal full-history extract.
2. Apply one frozen, versioned tag classifier to every year.
3. Report *OSM-mapped km*, not "built km", and quantify mapping-effort artefacts, e.g. spikes coinciding with import or mapping campaigns, by checking changeset counts.
4. Publish the classifier and an ohsome-planet/DuckDB notebook.

## 4. Berlin (as of 27 September 2026)

**Fortschrittsbericht Radverkehr, 2025 data (NEW; reported by dpa on 8 September 2026):**
- **Km built:** 21.2 km of new cycle facilities in 2025, down every year since 32.4 km in 2022.\[36\] Entwicklungsstadt reports 20.5 km,\[37\] which I cannot reconcile. It may reflect Streckenlänge vs Reallänge or a preliminary figure, so ask the Senate which length basis is used.
- **Money:** dpa via Tagesspiegel reports "knapp 27 Millionen Euro" (just under €27M, including federal funds) spent, against "rund 82,4 Millionen Euro" available "über alle Haushaltstitel hinweg" (across all budget lines). That is almost €4M less than in 2024, according to Nordkurier/dpa. The Abteilung Verkehr spent only a third of its funds, Tiefbau about 80%.
- **Network:** The Berliner, citing the Senate report, says that of the 2,400 km of routes planned, "only about 140km, or around 5.8%, were completed between 2017 and 2025".
- **Vorrangnetz:** 78.2 km of about 870 km implemented by May 2026, according to Senate figures cited on Wikipedia.\[38\] This is secondary; get the primary source.
- **2026 plans:** about 8.1 km.\[39\]
- **Mobility Act:** amended in July 2026. Reportedly the priority network keeps its 2030 target while the full network moves to 2035;\[38\] this is secondary and should be verified against GVBl.
- The Reallänge/Streckenlänge methodology break from 2023 persists, so don't splice the pre- and post-2023 series.

**Election, 20 September 2026 (NEW, preliminary official result):**
- **Vote shares:** Linke 25.7%, CDU 18.8%, AfD 16.3%, Grüne 14.3%, SPD 12.1%, BSW 4.7% (out),\[40\] FDP 2.5%. Turnout was 74.2%.\[41\]\[42\]
- **Seats:** wahlrecht.de and German Wikipedia give 158 seats: Linke 47, CDU 34, AfD 29, Grüne 26, SPD 22.\[41\]\[43\] An English Wikipedia live page shows a conflicting 130-seat allocation,\[40\] so use the Landeswahlleiter figures.
- **Coalition:** Linke, Grüne and SPD together hold a majority.\[41\] A Linke party conference voted on 25 September to invite Grüne and SPD to Sondierungen (exploratory talks), and both signalled readiness.\[44\]\[45\]
- **Senate:** the CDU–SPD Wegner Senate remains in office on a caretaker basis, with CDU senator Ute Bonde running transport.\[37\]\[40\]\[46\]
- **Implication:** a probable reversal of rollbacks, but budget lines and a coalition agreement do not exist yet. Treat any "2027 cycling budget" as unknown.

**Kantstraße (NEW):**
- The Senate plans to replace the 2020 protected pop-up lane with a shared bus/bike lane. In its reply to a Schriftliche Anfrage (written parliamentary question) from Greens Oda Hassepaß and Antje Kapek, reported by Entwicklungsstadt, it put the cost "mit Stand März 2026 auf rund 2,4 Millionen Euro" (about €2.4M as of March 2026). infraVelo is implementing it.
- A DUH-backed urgent application was filed on 7 September 2026. The Senate assured the court no work would begin before 30 September. The court then refused the Senate's request to extend its filing deadline to 28 September, and on 25 September Bonde postponed marking work to 7 October.\[46\]\[47\]\[48\]
- DUH counted 236–278 cyclists per hour per direction on 25–27 August 2026 ("bis zu 278 Radfahrende je Stunde", per netz-trends.de). Its application also argues the bus lane is "teilweise nur 3,0 bis 3,25 Meter breit" (in places only 3.0–3.25 m wide) and carries "zwölf Linienbussen pro Stunde" (twelve scheduled buses per hour). Linke, Grüne and SPD lead candidates publicly oppose the rollback.

**Unter den Eichen:** on 4 May 2026 DUH announced legal action against the planned removal of the 2022 cycle lane.\[49\] I did not verify any ruling.

**Ollenhauerstraße:** in October 2023 the Verwaltungsgericht (administrative court) put the costs on Land Berlin, finding the closure likely unlawful, and the lane was opened. A structural rebuild was slated for "2026/2027".\[50\]\[51\]\[52\] I did not verify its current status.

**Budget:** I could not verify the Titel 72016 cut (€6.5M → €500k from 2026) in this update. The underspend figures above are the stronger story anyway.

**OSM vs Senate discrepancy:** there is no published reconciliation. Expect OSM km to exceed Senate km by a wide margin, because OSM counts all existing, including legacy, sidewalk-level cycle paths, while the Senate counts new or upgraded MobG-compliant facilities. They measure different things (stock vs flow).

**Counters:** the Senate/infraVelo counting stations publish via daten.berlin.de. I didn't re-check whether availability changed in 2026.

## 5. Comparator cities

**French municipal elections, 15 and 22 March 2026 (NEW):**
- **Paris:** Emmanuel Grégoire (PS) won with 50.52% in the runoff and took office on 29 March 2026. The majority is 103 of 163 seats (PS 53, EELV 36, PCF 14). This means continuity of Hidalgo's cycling policy, including the Vélopolitain network.\[53\]\[54\]\[55\] Plan Vélo 2021–2026 completion figures were not verified.
- **Lyon:** Grégory Doucet (Les Écologistes) was re-elected narrowly, 50.67% to 49.33%. The Voies Lyonnaises network continues.\[53\]\[56\]
- **Bordeaux:** Thomas Cazenave (Renaissance) beat Pierre Hurmic with 50.85% and took office on 27 March 2026. Coverage attributes part of the result to removing car parking.\[53\]\[57\]\[58\] This is the most likely French rollback or slow-down case, so watch it.
- **Strasbourg:** Jeanne Barseghian lost, and Catherine Trautmann is her successor.\[57\]\[59\] Early cycling decisions are not verified.

**Czechia (NEW):**
- The Babiš government is a coalition of ANO, SPD and Motoristé sobě. The transport minister is Ivan Bednárik, an SPD nominee.\[60\]\[61\]
- Motoristé ministers hold foreign affairs (Petr Macinka), sport/prevention/health (Boris Šťastný) and other portfolios.\[62\]\[63\]
- I found no verified change to national cycling policy.

**Not re-verified:** 2025–2026 data releases and current mayors for Vienna, Amsterdam, Utrecht, Oslo, Helsinki, Stockholm, Madrid, Barcelona, the Polish, Hungarian and Slovak cities, and Ljubljana. Check each city's official site before publishing names.

## 6. What this means for the project

**Primary methodology:**
- Build your own OSM pipeline and make it primary.
- Use ECF QECIO tag logic as the published base, so you can cite a prior method, but extend it into the tiered class scheme in section 3.
- Triangulate against three references, shown alongside rather than blended: (a) official city km, (b) Clean Cities 2025, (c) ECF's NUTS-3 figures.
- Differences between them are a *story*, the definitional politics of "protected", not noise.

**Effort:**
- *Reusing* Clean Cities or Springer results: about a day, but they are frozen snapshots (2022 and early 2025) under incompatible definitions. Good for context, useless for a time series.
- *Reproducing* from scratch with 2026 tooling: roughly 2–3 weeks for 21 cities × 9 annual snapshots, given your stack. Breakdown: Geofabrik or full-history extract, then ohsome-planet to GeoParquet, then DuckDB spatial classification, then Pydantic-validated outputs. Most of the time goes into way-side explosion, dedup logic and boundary handling.

**Headline metric:**
- Lead with **tier-A+B protected km per 100 km of *main-road* network**, following ECF's Sustainable Safety logic, because protection matters where traffic is fast and heavy.
- Also give **absolute km**, and **per 100k residents** as a secondary measure.
- Avoid Clean Cities' total-network denominator: it penalises cities with many calm residential streets. Avoid per-area measures, which are dominated by forests and water in Berlin, Oslo and Helsinki.
- Report modal share only from official travel surveys (e.g. SrV), with survey years stated.

**Pitfalls to disclose:**
- Admin boundaries vary: Berlin is a city-state, Paris is small inner communes. Consider a Functional Urban Area (FUA) robustness check.
- Shared foot/cycle paths inflate German, Polish and Finnish figures.
- OSM mapping effort is not construction.
- Double-mapping.
- Berlin's Reallänge/Streckenlänge break.
- Clean Cities' post-hoc city corrections (Vienna).
- Counter data from vendor APIs may change or disappear.

**Not publicly reproducible without extra steps:**
- Clean Cities' city-submitted raw data: ask the authors.
- Copenhagenize indicator scores.
- Berlin's project-level km behind the Fortschrittsbericht, and the Titel 72016 execution: IFG request to the SenMVKU and parliamentary questions (Schriftliche Anfragen).
- Eco-Visio time series for cities without open data: vendor or city agreement.
- The DG MOVE baseline, if unpublished: ask DG MOVE.

**v1 starter plan (4 weeks):**
- **Week 1:** pin boundaries (admin plus FUA). Write the classifier as a Pydantic-typed rule table covering tiers A–E, with unit tests on 50 hand-checked Berlin ways, including Kantstraße.
- **Week 2:** run on the current Geofabrik extract for 21 cities and reconcile against Clean Cities and ECF figures, with a table explaining every gap above 20%.
- **Week 3:** create 1 January snapshots for 2018–2026 via full-history plus ohsome-planet, and add tag-completeness and changeset-activity diagnostics.
- **Week 4:** publish the repo (uv, typer CLI, DuckDB, and FastAPI read-only endpoints) under ODbL for data and MIT for code. File IFG requests for Berlin, then write the Berlin-vs-peers piece around the September 2026 political break.

## Caveats
- Some Berlin figures (Vorrangnetz 78.2 km; Mobility Act 2035 target) come from secondary sources.
- The 21.2 km vs 20.5 km conflict is unresolved.
- Seat totals in the election result are preliminary.
- My search budget ran out before I could re-verify several items: BIKE Index, BYPAD, CycleRAP, Eurostat/EEA/SUMI, non-French mayors, and Titel 72016. They are labelled as such in the text.
- Copenhagenize overall scores now come from the report itself. Its per-indicator inputs are still not published.

## Sources

1. [Clean Cities Campaign - Clean Cities Campaign](https://cleancitiescampaign.org/)
2. [Research - Clean Cities Campaign](https://cleancitiescampaign.org/research/)
3. [Cities Speak: Clean Cities Urban Mobility Barometer 2026 - Clean Cities Campaign](https://cleancitiescampaign.org/research-list/cities-speak/)
4. <https://cleancitiescampaign.org/research-list/state-of-urban-transport-2026/>
5. <https://cleancitiescampaign.org/wp-content/uploads/2025/05/Annexes_City-Ranking_Streets-For-Kids-Cities-for-All.pdf>
6. <https://www.polisnetwork.eu/wp-content/uploads/2025/05/Report-Streets-For-Kids-Cities-For-All.pdf>
7. [Streets for Kids, Cities for All Ranking Europe’s cities on child-friendly urban mobility - Klimatyczna Baza Wiedzy](https://klimatycznabazawiedzy.org/raport/streets-for-kids-cities-for-all-ranking-europes-cities-on-child-friendly-urban-mobility/)
8. [City Ranking 2025: Streets for Kids Edition - Clean Cities Campaign](https://cleancitiescampaign.org/city-ranking-2025/)
9. [CLEAN CITIES Benchmarking European cities on creating the right conditions](https://cleancitiescampaign.org/wp-content/uploads/2022/02/Clean-Cities_-City-Ranking-Rating-briefing-2.pdf)
10. [Why Copenhagen Is Beating Amsterdam in Global Cycling Rankings](https://www.urborough.com/why-copenhagen-is-beating-amsterdam-in-global-cycling-rankings/)
11. [The Copenhagenize Index 2025 - EIT Urban Mobility Edition - EIT Urban Mobility](https://www.eiturbanmobility.eu/knowledge-hub/the-copenhagenize-index-2025-eit-urban-mobility-edition/)
12. [Copenhagenize Index 2025: Bike-Friendly Cities](https://www.scribd.com/document/951501208/INDEXReport-VFLight)
13. [Copenhagenize](https://www.copenhagenize.eu/projects/index)
14. [Copenhagenize Index 2025 ranks the most bicycle-friendly cities, including many POLIS members - POLIS Network](https://www.polisnetwork.eu/news/copenhagenize-index-2025-ranks-the-most-bicycle-friendly-cities-including-many-polis-members/)
15. [Press corner - EIT Urban Mobility](https://www.eiturbanmobility.eu/press-corner/eit-urban-mobility-at-mobco-paris-2026-lessons-from-the-copenhagenize-index-and-scaling-urban-mobility-innovation/)
16. [Our Methodology](https://european-cyclists-federation.github.io/Documents/Methodology.pdf)
17. [ECF Cycling Infrastructure Tracker](https://european-cyclists-federation.github.io/)
18. [Quantifying Cycling Infrastructure Investment Needs Across Europe Using OpenStreetMap Data](https://link.springer.com/chapter/10.1007/978-3-031-85578-8_21)
19. [The barrier effect for cyclists: Quantifying the negative impact of large transport infrastructure - ECF](https://www.ecf.com/en/news/the-barrier-effect-for-cyclists-quantifying-the-negative-impact-of-large-transport-infrastructure-/)
20. [data.consilium.europa.eu](https://data.consilium.europa.eu/doc/document/ST-13881-2025-INIT/de/pdf)
21. [1 Data on cycling use and cycling infrastructure](https://unece.org/sites/default/files/2024-05/Data%20on%20cycling%20use%20and%20cycling%20infra%20-%20DG%20MOVE.pdf)
22. [Eco-Counter API - Documentation](https://developers.eco-counter.com/)
23. [Eco-Visio API - AMRO BALTIC](https://www.amro.lv/en/shop/customer-service/people-counter-sensors/eco-visio-software/eco-visio-api/)
24. [The Eco-Counter connector is evolving 🚲](https://community.huwise.com/product-updates/the-eco-counter-connector-is-evolving-518)
25. [eco-visio-api/openapi.yaml at main · bundesAPI/eco-visio-api](https://github.com/bundesAPI/eco-visio-api/blob/main/openapi.yaml)
26. [Data Sharing & API](https://www.eco-counter.com/solutions/data-sharing-api)
27. [Copenhagen - The Best Cycling City in the World | Urban Development](https://urbandevelopmentcph.kk.dk/mobility-cycling/copenhagen-the-best-cycling-city-in-the-world)
28. [Rising Standards, Better Results: U.S. Cities Continue to Improve for Bicycling](https://www.peopleforbikes.org/news/2026-city-ratings-summary-report)
29. [2026 City Ratings Methodology Updates: What Is Changing and Why It Matters](https://www.peopleforbikes.org/news/2026-city-ratings-methodology)
30. [Key:cycleway - OpenStreetMap Wiki](https://wiki.openstreetmap.org/wiki/Key:cycleway)
31. [wiki.openstreetmap.org](https://wiki.openstreetmap.org/wiki/User:Supaplex030/Key:cycleway)
32. [Update of the roadmap toward the new ohsome API 2.0](https://heigit.org/update-of-the-roadmap-toward-the-new-ohsome-api-2-0/)
33. [ohsomeNow server update · Issue #7335 · hotosm/tasking-manager](https://github.com/hotosm/tasking-manager/issues/7335)
34. [feat: migrate ohsomeNow stats to HeiGIT API and proxy requests via backend by prabinoid · Pull Request #7338 · hotosm/tasking-manager](https://github.com/hotosm/tasking-manager/pull/7338)
35. [Moving to ohsomeDB](https://heigit.org/moving-to-ohsomedb/)
36. [Fahrrad-Fortschrittsbericht: Bericht: Senat ließ viele Mittel für Radverkehr liegen](https://www.tagesspiegel.de/berlin/dpa-fahrrad-fortschrittsbericht-16031059.html)
37. [Rückläufige Zahlen: Immer weniger neue Radwege in Berlin](https://www.entwicklungsstadt.de/rueckzug-vom-rad-wie-berlin-den-ausbau-der-fahrradinfrastruktur-systematisch-herunterfaehrt/)
38. [Cycling in Berlin](https://en.wikipedia.org/wiki/Cycling_in_Berlin)
39. [Radwegausbau stagniert: Fördermittel werden nicht ausgenutzt](https://www.entwicklungsstadt.de/berlins-radwegausbau-stagniert-verkehrsverwaltung-schoepft-foerdermittel-nicht-aus/)
40. [2026 Berlin state election](https://en.wikipedia.org/wiki/2026_Berlin_state_election)
41. [Wahl zum Abgeordnetenhaus von Berlin 2026](https://de.wikipedia.org/wiki/Wahl_zum_Abgeordnetenhaus_von_Berlin_2026)
42. [Ergebnisse Wahl zum 20. Abgeordnetenhaus von Berlin am 20. September 2026 in Berlin](https://www.wahlen-berlin.de/wahlen/BE2026/Afspraes/agh/index.html)
43. [Abgeordnetenhauswahl in Berlin am 20. September 2026](https://www.wahlrecht.de/news/2026/abgeordnetenhauswahl-berlin-2026.html)
44. [Berliner Linke stimmt für Sondierungen mit Grünen und SPD](https://www.berliner-zeitung.de/article/linke-strebt-koalition-mit-spd-und-gruene-an-10432127)
45. [Berlin: Linke lädt Grüne und SPD zu Sondierungen ein](https://www.zdfheute.de/politik/deutschland/linke-berlin-sondierung-gruene-spd-100.html)
46. [Streit um Radweg an der Berliner Kantstraße: Gericht setzt Verkehrsverwaltung unter Druck](https://www.tagesspiegel.de/berlin/streit-um-radweg-an-der-berliner-kantstrasse-gericht-setzt-verkehrsverwaltung-unter-druck-16090301.html)
47. [Eilantrag auf Erhalt des Radwegs auf der Kantstraße: Senat teilt Gericht mit, keine Baumaßnahme vor 30. September zu beginnen - Deutsche Umwelthilfe fordert Moratorium bis zur Regierungsneubildung](https://www.presseportal.de/pm/22521/6352422)
48. [Radinfrastruktur in Berlin: Ringen um den Radweg in der Kantstraße](https://taz.de/Radinfrastruktur-in-Berlin/!6216378/)
49. [DUH will Abschaffung des Berliner Radwegs „Unter den Eichen“ vor Gericht verhindern](https://www.duh.de/presse/pressemitteilungen/pressemitteilung/berliner-radwegestopp-deutsche-umwelthilfe-will-abschaffung-des-radwegs-unter-den-eichen-vor-geri/)
50. [Radweg Ollenhauerstraße wird freigegeben - Berlin.de](https://www.berlin.de/sen/uvk/presse/pressemitteilungen/2023/pressemitteilung.1346382.php)
51. [Sperrung des Radwegs Ollenhauerstraße rechtswidrig: Gericht verpflichtet Land Berlin zur Übernahme der Verfahrenskosten](https://www.presseportal.de/pm/22521/5625091)
52. [Sperrung des Radwegs Ollenhauerstraße rechtswidrig: Gericht verpflichtet Land Berlin zur Übernahme der Verfahrenskosten](https://www.duh.de/presse/pressemitteilungen/pressemitteilung/sperrung-des-radwegs-ollenhauerstrasse-rechtswidrig-gericht-verpflichtet-land-berlin-zur-uebernahme-d/)
53. [Municipales 2026 : comment le vélo fait-il gagner les élections ? - Citycle](https://www.citycle.com/74141-municipales-2026-velo-elections/)
54. [2026 Paris municipal election](https://en.wikipedia.org/wiki/2026_Paris_municipal_election)
55. [Council of Paris](https://en.wikipedia.org/wiki/Council_of_Paris)
56. [2026 Lyon municipal election](https://en.wikipedia.org/wiki/2026_Lyon_municipal_election)
57. [Strasbourg, Poitiers, Bordeaux... Les maires écologistes battus dans la plupart des villes](https://reporterre.net/Strasbourg-Poitiers-Bordeaux-Les-maires-ecologistes-battus-dans-la-plupart-des-villes)
58. [Thomas Cazenave](https://en.wikipedia.org/wiki/Thomas_Cazenave)
59. [Jeanne Barseghian](https://en.wikipedia.org/wiki/Jeanne_Barseghian)
60. [Babiš zveřejnil seznam ministrů. Turek má vést resort životního prostředí, prezident ho ale ve vládě nechce](https://www.irozhlas.cz/zpravy-domov/babis-zverejnil-seznam-ministru-sefem-diplomacie-ma-byt-misto-turka-macinka_2511261439_mst)
61. [PŘEHLEDNĚ: Babišova patnáctka a rošáda u Motoristů. Kdo jsou navržení ministři](https://publico.cz/politika/prehledne-babisova-vlada)
62. [Ministři za Motoristy rozpočet podpoří, uvedl Macinka](https://www.ceskenoviny.cz/zpravy/-ministri-za-motoristy-rozpocet-podpori-uvedl-macinka/2876955)
63. [Babiš uvedl ministry do úřadů - ČT24](https://ct24.ceskatelevize.cz/clanek/domaci/babis-uvadi-ministry-do-uradu-368301)
