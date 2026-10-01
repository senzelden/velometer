# Follow-up Verification: European Cycling-Infrastructure Benchmarks and Berlin Items (status 27 September 2026)

No newly found dataset should replace the planned self-built OSM pipeline. The two most useful new resources are Michael Szell's BikeNetKit Zenodo export (403 European cities, ODbL, 3 September 2026) and ECF's per-NUTS3 QECIO GeoPackages. Both should be used as validation layers. The EU's new Urban Mobility Indicators act, adopted 9 July 2026, contains no cycling-infrastructure indicator. On Berlin, the official 2025 build-out figure is 21.2 km, from the Senate's Fahrrad-Fortschrittsbericht as reported by dpa.\[1\] The competing figures come from different stages and definitions, not from errors: 20.5 km was the Senate's own preliminary December 2025 count, 17.3 km is the network-only infraVelo figure, and 25.2 km is Changing Cities' count.

## TL;DR
- **Benchmarks:** ECF QECIO has had no release since v2.10 (11 Jan 2024). The BIKE Index is a single 2026 academic paper covering 13 capitals with no code repository found. CycleRAP data is not open. The EU Urban Mobility Indicators implementing act (C(2026) 4676, 9 July 2026) counts cycling only as a trip mode share, with first data due end-2027. The only new pan-European open dataset is BikeNetKit (Zenodo, 403 cities, ODbL).
- **Berlin:**
  - The 2025 build-out was 21.2 km, against €82.4M available and about €27M spent.
  - The Mobilitätsgesetz amendment keeps 2030 for the priority network and moves the rest to 2035.
  - Kantstraße has no court decision yet; the Senate postponed markings to 7 October.
  - Unter den Eichen has no ruling.
  - The preliminary election result (158 seats: Linke 47, CDU 34, AfD 29, Grüne 26, SPD 22) is confirmed. I found no public confirmation of the final certified result.
- **Comparators:** Grégoire (Paris), Trautmann (Strasbourg) and the Tisza victory in Hungary (138/199 seats) are confirmed. Most of the other 19-city mayor checks, the city km releases, the Czech national-policy item and Bordeaux could not be verified in this pass. Treat them as open, not as confirmed.

## Key Findings

### A. Benchmarks and indices

**1. BIKE Index (Bicycle Integration Key Elements): verified from primary source (journal article)**
- It is not a recurring index. It is one peer-reviewed paper: Quintero-Gómez & Calvo-Bascones (Comillas Pontifical University, IIT Madrid), "BIKE (Bicycle Integration Key Elements) Index: Benchmarking urban bikeability and cycling readiness. Evidences from European capitals".\[2\]
  - Journal: *Sustainable Cities and Society* vol. 136, article 107096, online 5 January 2026.\[2\]
  - DOI: 10.1016/j.scs.2025.107096. Open access under CC BY-NC-ND 4.0.\[2\]
  - URL: https://www.sciencedirect.com/science/article/pii/S2210670725009667
- Four dimensions: Cycling Infrastructure; Cyclist Services; Environmental Constraints; Safety and Street Quality.\[2\]
- Method: 210 simulated OpenRouteService routes per city inside Local Administrative Unit (LAU) boundaries. Inputs are OSM, OpenRouteService, Eurostat, Google Maps and E-OBS climate data.\[2\]
- Coverage: 13 capitals — Amsterdam, Athens, Berlin, Brussels, Copenhagen, Dublin, Lisbon, Luxembourg, Madrid, Paris, Rome, Stockholm and Vienna. Amsterdam ranks best and Rome worst.\[3\]
- Overlap with the candidate set: Berlin, Vienna, Copenhagen, Amsterdam, Stockholm, Madrid, Paris.
- The paper describes itself as "open-data" and "reproducible", but no GitHub or Zenodo repository was found. HeiGIT published a use-case write-up on 5 February 2026.\[4\]
- No 2025–2026 update exists beyond the paper itself.
- Conclusion: cite it as an external comparator for the seven overlapping cities. Do not build on it.

**2. BYPAD and PRESTO: could not verify.**
- The search budget ran out before this item was reached.
- The prior audit's position stands unconfirmed: both are legacy EU-project tools with no evidence of 2025–2026 maintenance.
- For the project, treat them as historical references only.

**3. CycleRAP (iRAP): verified from primary source (iRAP news)**
- The methodology is unchanged in principle: risk is assessed from coded road and path attributes, without crash data.\[5\]
- In Europe it is increasingly delivered through Lane Patrol, a bike-mounted app that captures georeferenced images and uses vision models to code more than 40 features.\[6\]
- Recent milestones:
  - It won the ECF Road Safety Award at Velo-city Gdańsk in June 2025.\[7\]
  - Dublin application, July 2025.\[8\]
  - By February 2026, iRAP reported assessments "in 31 countries with the support of 14 Trusted Suppliers".\[9\]
  - May 2026: 75 km assessed across Ljubljana, Novo Mesto, Kranj, Koper and Velenje (AMZS, FIA grant).\[10\]
- Earlier Lane Patrol projects include Lisbon, Barcelona, Thessaloniki, Madrid, Copenhagen and Oxford. Madrid and Barcelona were also 2023 pilots.\[6\]\[11\]
- Data is not open. Results sit in iRAP's ViDA platform, where "project teams can determine who has access to results".\[8\]
- Conclusion: not usable as a cross-city dataset. Useful only as context or quotes for Madrid, Barcelona, Copenhagen and Ljubljana.

**4. Eurostat / EEA / ITF-OECD: only partly verified.**
- A May 2024 DG MOVE presentation to UNECE describes the Eurostat city-statistics variable "length of bicycle network (dedicated cycle paths and lanes)" as a "voluntary data collection, poor data availability".\[12\]
- I found no new Eurostat, EEA or ITF cross-city cycling-infrastructure release since mid-2025.
- The substantive new EU numbers come from DG MOVE's Cycling Counts work (see item 6), not from Eurostat.

**5. SUMI: could not verify current per-city publication.**
- In effect, SUMI has been superseded by the TEN-T Urban Mobility Indicators (item 6).
- The UMI act did not carry over a SUMI-style "opportunity for active mobility" infrastructure measure.

**6. DG MOVE cycling data study / TEN-T urban-node indicators: verified (primary for the implementing act; the baseline figure is from ECF)**
- **Implementing act adopted 9 July 2026:** Commission Implementing Regulation C(2026) 4676 under Regulation (EU) 2024/1679, Article 41.\[13\]\[14\]
  - News: https://transport.ec.europa.eu/news-events/news/commission-adopts-implementing-regulation-strengthen-sustainable-urban-mobility-through-harmonised-2026-07-09_en
  - Act: https://transport.ec.europa.eu/system/files/2026-07/C_2026_4676_1_EN_ACT_part1_v5_0.pdf
  - Annex: https://transport.ec.europa.eu/system/files/2026-07/C_2026_4676_1_EN_annexe_acte_autonome_part1_v2.pdf
- The Annex has 11 indicators. Cycling appears only in SU.1, trips per day split across five modes. Cyclist casualties are implicitly covered in SA.2 and SA.3 through the traffic-unit-type breakdown. **There is no cycling-infrastructure or network indicator.**\[14\]
- First data are due 31 December 2027, then every four years. Railway News reports a possible extension to end-2028; that is secondary and not checked against the act.\[13\]\[15\] The Official Journal publication date was not verified.
- **Baseline, via the Cycling Counts project (DG MOVE-commissioned, ECF partner):**
  - More than 340,000 km of dedicated cycling networks EU-wide, with 18 of 27 Member States working on national data standards (ECF, "2025: Shaping the road ahead", 18 December 2025).\[16\]
  - Per-country "Cycling data overview 2025" reports appeared on the EU Publications Office in 2026. Example: Hungary, DOI 10.2832/1426829, released 1 June 2026, which relies on OSM for network data.\[17\]
- **Follow-up to COM(2025) 566:** could not verify any further report.

**7. New 2025–2026 pan-European OSM datasets and tools: verified (Zenodo primary)**
- **BikeNetKit export:** "Bicycle networks, street networks, and POIs for 403 European cities".\[18\]
  - Authors: Michael Szell and Mariana Pessoa. Published 3 September 2026, v1, DOI 10.5281/zenodo.22271229, ODbL, 5.7 GB.\[18\]
  - Contains bike, street, "growable" and combined networks plus rail stations, schools and boundaries.\[18\]
  - Data: https://zenodo.org/records/22271229. Code: https://github.com/BikeNetKit/dataexport
  - **This is the single most relevant new find.**
- **Level of Traffic Stress (LTS) at European scale:** none found. The closest work is Denmark-wide:
  - Vierø et al., *Geographical Analysis* 2025, on open bicycle-network data quality.\[19\]
  - arXiv 2412.06083, on LTS-based bikeability. Code at github.com/anerv/dk_bicycle_network.\[20\]
- **BikeDNA:** no new pan-European application; the known outputs are from 2023.\[21\]
- **Overture transportation layer cycling attributes:** not checked.

**8. Buczyński & Chavez-Pacheco: verified from primary source; no code found**
- Published as a Springer chapter in *Transport Transitions* (Lecture Notes in Mobility), pp. 154–159, DOI 10.1007/978-3-031-85578-8_21, open access, first online 7 March 2025.\[22\]
- Scope and results (2022 data):
  - 423 TEN-T urban nodes, covering 449 administrative areas.\[22\]
  - 61,862 km of existing infrastructure: 38,913 km cycle tracks, 5,204 km cycle lanes and 17,745 km shared paths.\[22\]
  - 156,141 km of main roads.\[22\]
  - An estimated need of about 96,906 km, so existing infrastructure covers about 40% of needs.\[22\]
- No GitHub or Zenodo deposit was found. The paper refers readers only to the QECIO dashboard.
- No replication was found.

**9. ECF QECIO / Cycling Infrastructure Tracker: verified; no update after v2.10**
- The methodology PDF (https://european-cyclists-federation.github.io/Documents/Methodology.pdf) still ends at v2.10, dated 11 January 2024.\[23\]
- Naming is inconsistent: ecf.com says "QECIO 2.1", while the GitHub Pages site says "2.0".
- Results pages:
  - https://ecf.com/quantifying-europe-cycling-infrastructure-using-openstreetmap-qecio-2
  - https://www.ecf.com/en/resources/ecfs-cycling-infrastructure-tracker/
  - Both are script-rendered, so no refresh date could be read.
- **Downloadable data exists** (https://european-cyclists-federation.github.io/download.html):
  - Summary-all.csv.\[24\]
  - Per-country zip files of GeoPackages, one per NUTS3 region.\[24\]
  - Results are per NUTS3 region, not per city.
- No licence is stated. ODbL applies by derivation from OSM, but that is my inference, not something ECF says.

**10. Eco-Counter Eco-Visio API: partly verified (secondary)**
- Huwise, which runs the data-portal connector, says API v1 "will be deprecated by the end of the year". It also says existing connectors must be recreated with a **new v2 key generated from the Eco-Visio platform**.\[25\]
- The year of that notice and the exact cut-off date could not be confirmed.
- v2 (branded "API^Evo") remains a paid add-on per customer domain ("contact our sales team").\[26\]\[27\] Reseller-stated limits are 100 requests per minute and 5,000 per day.\[28\]
- No public or open-data programme change was found.
- Practical rule: use city open-data portals that republish Eco-Counter data, not the API.

**11. Clean Cities Campaign: could not verify** any June–September 2026 publication or a next ranking date. I found no evidence of a 2026 city ranking.

**12. Copenhagen: verified from primary source (kk.dk)**
- There is no new "Cykelregnskab". The city states that from 2021 onward the Cykelredegørelser were replaced by the annual Mobilitetsredegørelse.\[29\]
- **Mobilitetsredegørelse 2026** was published June 2026 with 2025 data, in Danish and English: https://byudvikling.kk.dk/mobilitet/mobilitetsredegoerelse \[30\]\[31\]
- Trip shares in 2025: car 26%, cycling 28% (−1 pp), walking 25%, public transport 21%.\[32\]
- Cycling kilometres fell 6% by the city's own counts (−5% by the national travel survey).\[32\]
- The cycle share of work and education trips fell from 46% to 43%, against the Cycle Strategy target of 50% by 2025.\[31\]
- Copenhageners own 754,200 bicycles; 10,700 shared bikes are permitted (+23%).\[31\]
- The 2025 report showed only about 1 km of new cycle track built in 2024 (Magasinet KBH).\[33\]
- The city's Budget 2026 page (kk.dk) includes "602,4 mio. kr. i en større cykelpakke". Line Barfod (EL), the city's Teknik- og miljøborgmester, called it "det største cykelbudget i København nogensinde" in a 4 September 2025 press release.

### B. Berlin

**13. Titel 72016: secondary source only.**
- ADFC Berlin states that Titel 72016 ("Verbesserung für den Radverkehr") falls from €6.5M in 2025 to €500,000 per year from 2026.\[34\]
- Conflict: other reporting (Berliner Zeitung, citing the Greens) puts the 2025 "Verbesserung der Radverkehrsinfrastruktur" line at €4.75M (−27%), and €7.2M in total for new cycle paths in 2026/27.\[35\]\[36\]
- The €6.5M versus €4.75M gap is most likely a difference between the budgeted amount and the amended figure, or between different lines. It is unresolved without the Haushaltsplan Einzelplan 07.
- No later amendment was found.

**14. The 2025 build-out conflict: resolved on sourcing; length basis unverified.**
- **Authoritative figure: 21.2 km.** Source: the Senate's Fahrrad-Fortschrittsbericht for the Hauptausschuss, reported by dpa on 8 September 2026.\[1\] The same report gives:
  - Spending of about €27M including federal funds, down about €4M year on year.\[1\]
  - €82.4M available across all budget lines.\[1\]
  - The Verkehr department spent only one third of its funds; the Tiefbau department spent 80%.\[1\]
  - 32.4 km built in 2022.\[1\]
  - About 140 km of the 2,400 km network (about 5.8%) completed in 2017–2025.\[1\]
- The other figures differ because they come from different sources and definitions:
  - The 20.5 km figure (also used by Entwicklungsstadt) is the Senate's own preliminary December 2025 count. Tagesspiegel/dpa quoted the Senatsverwaltung für Verkehr: "35 Radwege-Projekte mit einer Gesamtlänge von 20,5 Kilometern", with the caveat that "möglicherweise noch nicht alle tatsächlich umgesetzten Baumaßnahmen berücksichtigt sind". So 21.2 km is the later, more complete figure. Entwicklungsstadt also gives about 26 km for 2023, about 24 km for 2024, 53.6 km for 2020, and a planned **8.1 km for 2026**.
  - infraVelo data for the network only: 9.8 km Vorrangnetz plus 7.5 km Ergänzungsnetz, i.e. 17.3 km.\[37\]
  - Changing Cities' own street-level monitoring: 25.2 km in 2025 and 183.6 km since 2018, i.e. 6.8% of the network, as of 31 December 2025.\[38\]
- The basis of the 21.2 km (Streckenlänge vs Reallänge) could not be confirmed, and the PARDOK document was not located.
- Use 21.2 km, cite it as "Fortschrittsbericht, per dpa", and record the basis as unknown.

**15. Vorrangnetz: verified from primary source (Abgeordnetenhaus).**
- Drucksache 19/25987 is a Schriftliche Anfrage (written question) on PARDOK. The Senate's answer to Q18 says "Insgesamt sind 78,2 km des Radvorrangnetzes umgesetzt worden", and its answer to Q14 gives "ca. 870 km Streckenlänge".
- The Senate's "Netzumfang und Karte" page on berlin.de gives "rund 871 Kilometern" for the Vorrangnetz and "ca. 2.376 Kilometer" for the whole network.
- The same figures appear in Tagesspiegel (29 May 2026) and in Entwicklungsstadt citing infraVelo data.

**16. Mobilitätsgesetz amendment (July 2026): secondary source only.**
- rbb24 (2 July 2026): "Schwarz-Rot verschiebt Zieljahr des Berliner Radverkehrsnetzes um fünf Jahre".\[39\]\[40\]
- Entwicklungsstadt and Tagesspiegel report the content:
  - 2030 is kept for the priority network (Radvorrangnetz); the rest of the network moves to 2035.\[41\]\[42\]
  - Protected lanes at standard widths on main roads can be waived where space is lacking or a side-street alternative exists "im unmittelbaren Umfeld".\[42\]
  - The target of defusing 30 accident black spots per year is deleted.\[42\]
  - Systematic recording of citizen defect reports is abolished.\[42\]
- The Gesetz- und Verordnungsblatt (GVBl) entry and the Drucksache number were not verified.

**17. Ollenhauerstraße: secondary source, plus the primary 2023 Senate release.**
- Status (Entwicklungsstadt, 25 July 2026):
  - Tree felling (116 trees) is expected to start **1 October 2026**, with **construction from Q1 2027**.\[43\]
  - The existing on-road Radfahrstreifen will be replaced by a raised (Hochbord) cycle track.\[44\]
  - Local initiatives oppose the plan. Protests took place on 16 June and 8 July, and questions were put to the new Bezirksstadtrat Sebastian Pieper.\[44\]\[45\]
- This matches the 2023 Senate press release, which said "voraussichtlich 2026/2027 baulich verändert".\[46\]

**18. Unter den Eichen: no court ruling found.**
- 2 July 2026: the Abgeordnetenhaus rejected a motion to keep the lane.\[47\]
- A Senate removal order followed; WE RIDE NEWS dates it 3 August 2026.\[47\]
- The district (Stadtrat Urban Aykal, Greens) has legal concerns and says removal will not happen immediately: "Sobald das Geld da ist, schreiben wir aus".\[48\]\[49\]\[50\]
- DUH's campaign page says the final order is still pending.\[51\] That contradicts the 3 August date and is unresolved.
- DUH announced legal action on 4 May 2026.\[52\] I found no filing or ruling.

**19. Berlin counter data (daten.berlin.de): could not verify** the current year or format in this pass.

**20. Election: verified from secondary aggregators of the Landeswahlleiterin's preliminary result.**
- Seats: Linke 47, CDU 34, AfD 29, Grüne 26, SPD 22, total 158; majority is 80.\[53\]\[54\]
- Second-vote shares: Linke 25.7%, CDU 18.8%, AfD 16.3%, Grüne 14.3%, SPD 12.1%, BSW 4.7% (out), FDP 2.5% (out).\[54\]\[55\]
- I found no public confirmation of the final certified result, which normally follows a couple of weeks after the vote.
- Coalition talks: no update found after 25 September. The arithmetic:
  - Linke–Grüne–SPD: 95 seats.\[55\]
  - CDU–Grüne–SPD: 82 seats.\[55\]
  - Linke–CDU: 81 seats, but the CDU ruled this out before the vote.\[55\]

**21. Kantstraße: verified from DUH releases, Tagesspiegel and taz; no decision yet.**
- DUH filed the urgent application on 7 September 2026. DUH counts on 25–27 August showed 236–278 cyclists per hour per direction, against a guideline of about 150–200 for shared bus/bike lanes.\[51\]\[56\] The project costs about €2.4M.\[56\]\[57\]
- The Senate assured the court it would not start before 30 September.\[58\]
- The Senate then sought an extension to 28 September to file its papers. The court rejected the extension if the 1 October start was kept, and asked whether the plan still stands after the election.\[59\]\[60\]
- taz reports that Senator Bonde has **postponed the start of works to 7 October** to give the court time.\[61\]
- As of 27 September there is no court decision.

### C. Comparator cities

**22. Mayors: only partly verified.**
- **Paris:** Emmanuel Grégoire (PS) has been mayor since 29 March 2026. His majority is PS 53, EELV 36, PCF 14 out of 163 seats.\[62\]
- **Strasbourg:** Catherine Trautmann (PS) was elected 22 March 2026 and also presides over the Eurométropole.\[63\]\[64\]
- The other 19 cities, the Dutch March 2026 municipal elections and other local changes **could not be verified in this pass**. Do not publish any of them without a fresh check.

**23. City data releases: Vienna only.**
- The "Radwegoffensive 2025 Bilanz" (Mobilitätsagentur, January 2026) lists 20,447 m of projects: https://www.fahrradwien.at/wp-content/uploads/sites/2/2026/01/Radwegoffensive_2025_Bilanz.pdf \[65\]
- All other cities: could not verify.

**24. Paris Plan Vélo: partly verified.**
- Targets (primary Ville de Paris documents): €250M; 180 km of secure tracks (130 km new plus 52 km of coronapistes made permanent); 450 km of contraflow lanes.\[66\]\[67\]
- The completion percentage in the Paris en Selle observatory is script-rendered and could not be read. The underlying data is on opendata.paris.fr (dataset "plan-velo-2026").\[68\]
- Grégoire's early moves:
  - He promised more cycle tracks and 1,000 pedestrian streets.\[69\]
  - He announced a daytime bike lane on the Périphérique from 1 September 2026 in place of the carpool lane, tested on a few kilometres "probably until end 2026".\[70\] This is reported only by low-grade secondary sites; treat it as unconfirmed on implementation.

**25. Strasbourg and Bordeaux:**
- **Strasbourg (secondary):** no removals found.
  - Trautmann campaigned on not removing the Greens' cycle tracks while reviewing accident-prone spots, and on gradually imposing "pied à terre" (dismount) for cyclists in the centre.\[71\]
  - In office she relit street lighting, including on cycle paths (May 2026), and had a dangerous anti-scooter barrier on a new cycle path removed. The mobility deputy is Landdry Augier de Lajallet.\[72\]\[73\]
- **Bordeaux:** could not verify.

**26. Czech Republic / Prague: could not verify.**

**27. Hungary: election verified; cycling effects not verified.**
- Tisza won on 12 April 2026 with 54.3% and 138 of 199 seats, a two-thirds majority. Orbán conceded.\[74\]\[75\]
- The Commission's "Cycling data overview 2025 — Hungary" (1 June 2026) exists.\[17\]
- Changes to Budapest or national cycling funding were not verified.

**Related German federal context (secondary):** according to the trade association Zukunft Fahrrad (VeloTOTAL, 7 September 2026), the 2027 federal draft budget cuts cycling funding by nearly 10%, to €544M. The "Stadt und Land" programme falls from €281M to €276M, Bundesstraßen cycle paths stay at €100M (down from €120M), and about €43M is cut from Radschnellwege and cycle paths along federal waterways. Managing director Wasilis von Rauch: "Doch die Bundesregierung kürzt die dafür nötigen Mittel".

## Corrected summary table

| # | Item | Status Sept 2026 | Confidence |
|---|---|---|---|
| 1 | BIKE Index | One paper (SCS 2026), 13 capitals, no repo found | Verified (primary) |
| 2 | BYPAD/PRESTO | No evidence of maintenance | Could not verify |
| 3 | CycleRAP | 31 countries; Slovenia 2026; data closed | Verified (primary) |
| 4 | Eurostat/EEA/ITF | Eurostat bike-network variable voluntary, poor coverage | Partly (primary 2024) |
| 5 | SUMI | Superseded by UMI | Could not verify |
| 6 | UMI act / DG MOVE | Adopted 9 Jul 2026; cycling only as trip share; Cycling Counts baseline >340,000 km | Verified (primary / ECF) |
| 7 | New OSM datasets | BikeNetKit, 403 cities, ODbL, 3 Sep 2026 | Verified (primary) |
| 8 | Buczyński & Chavez-Pacheco | Open-access chapter; no code | Verified (primary) |
| 9 | QECIO | Still v2.10; per-NUTS3 GPKG downloads; no licence stated | Verified (primary) |
| 10 | Eco-Visio API | v1 end-of-year deprecation; v2 key required; paid | Secondary |
| 11 | Clean Cities | Nothing found for Jun–Sep 2026 | Could not verify |
| 12 | Copenhagen | No Cykelregnskab; Mobilitetsredegørelse 2026 | Verified (primary) |
| 13 | Titel 72016 | €6.5M → €0.5M per ADFC; conflicting €4.75M | Secondary; conflict |
| 14 | 2025 build-out | 21.2 km (Fortschrittsbericht) supersedes the Senate's preliminary 20.5 km (Dec 2025); basis unknown | Secondary (dpa of primary) |
| 15 | Vorrangnetz | 78.2 of ~870 km (Drs. 19/25987) | Verified (primary) |
| 16 | MobG amendment | 2030 priority network / 2035 rest | Secondary |
| 17 | Ollenhauerstraße | Felling 1 Oct 2026, build Q1 2027 | Secondary |
| 18 | Unter den Eichen | Order issued (date disputed); no ruling | Secondary |
| 19 | Counter data | — | Could not verify |
| 20 | Election | 158 seats confirmed (preliminary) | Secondary (official data) |
| 21 | Kantstraße | No decision; start moved to 7 Oct | Verified (DUH / press) |
| 22 | Mayors | Paris, Strasbourg only | Partly |
| 23 | City data | Vienna 20,447 m | Partly (primary) |
| 24 | Paris Plan Vélo | Targets confirmed; completion % not read | Partly |
| 25 | Strasbourg/Bordeaux | Strasbourg: no removals; Bordeaux open | Partly |
| 26 | Czech | — | Could not verify |
| 27 | Hungary | Tisza 138/199 | Verified (secondary) |

## Corrections to the prior audit
- **"Cycling Infrastructure Tracker has no downloadable data" (if assumed):** wrong. Per-NUTS3 GeoPackages and a summary CSV are downloadable. They are not per city, and no licence is stated.\[24\]
- **20.5 km for 2025:** this is not an error. It was the Senate's preliminary December 2025 figure (Tagesspiegel/dpa, with the caveat that "möglicherweise noch nicht alle tatsächlich umgesetzten Baumaßnahmen berücksichtigt sind"). The later Fortschrittsbericht figure of 21.2 km supersedes it.
- **Titel 72016 "~€6.5M":** flag the conflicting €4.75M figure for 2025.
- **Copenhagen:** there has been no Cykelregnskab edition since the switch to the Mobilitetsredegørelse. Do not look for one.
- **Election:** the seat numbers are correct, but they are preliminary. Label them so until the certified result is published.
- **Unter den Eichen:** an order exists, but its finality is disputed.

## Implications for methodology and the v1 plan
1. **Keep the self-built OSM pipeline and the headline metric** ("protected km per 100 km of main roads", with tiered protection classes using QECIO tag logic). Nothing published in 2025–2026 provides that metric per city. Buczyński & Chavez-Pacheco's needs model uses the same ingredients (cycle tracks, lanes and shared paths against main-road length), which supports the design choice.\[22\]
2. **Add BikeNetKit (Zenodo 22271229) as a validation layer.** Compare your per-city bike-network km against the BikeNetKit bike networks, and record the OSM snapshot date for both. Because it is ODbL, the attribution and share-alike obligations match your own OSM derivative.
3. **Add a QECIO cross-check at NUTS3 level.** Load the QECIO GeoPackages for Berlin and the comparator regions, and report any difference above about 10% as a methodology note. Store the ECF version string ("v2.10, 2024-01-11") and the download date in your SQLite/DuckDB provenance table.
4. **Do not wait for EU data.** UMI will give only cycling trip shares, with first data at end-2027. Use it later as a denominator or context field, never for infrastructure.
5. **For Berlin, model official figures as a separate source with a definition field.** Store 21.2 km (Fortschrittsbericht), 17.3 km (infraVelo network only) and 25.2 km (Changing Cities) as separate records with definition labels, rather than choosing one silently. A Pydantic `Source` model with `network_scope` and `length_basis` fields fits this well.
6. **Counts:** avoid building on the Eco-Visio API. It is paid and changes key regimes. Pull from open portals.
7. **Before publication, re-verify:** mayors for the remaining cities, city km releases, Czech policy, Bordeaux, the Clean Cities schedule, the Kantstraße ruling (expected around 7 October), and the certified Berlin election result.

## Sources

1. [Fahrrad-Fortschrittsbericht: Bericht: Senat ließ viele Mittel für Radverkehr liegen](https://www.tagesspiegel.de/berlin/dpa-fahrrad-fortschrittsbericht-16031059.html)
2. [BIKE (Bicycle Integration Key Elements) Index: Benchmarking urban bikeability and cycling readiness. Evidences from European capitals](https://www.sciencedirect.com/science/article/pii/S2210670725009667)
3. [BIKE (Bicycle Integration Key Elements) Index: Benchmarking urban bikeability and cycling readiness. Evidences from European capitals - TRID](https://trid.trb.org/View/2652582)
4. [Use-case: evaluating urban cycling across several European cities with openrouteservice – HeiGIT](https://heigit.org/use-case-evaluating-urban-cycling-across-several-european-cities-with-openrouteservice/)
5. [RAP in Europe - iRAP](https://irap.org/european-regional-support/?lang=ru)
6. [Lane Patrol CycleRAP assessments underway in Skopje - iRAP](https://irap.org/lane-patrol-cyclerap-assessments-underway-in-skopje/)
7. [CycleRAP Receives Prestigious ECF Road Safety Award - iRAP](https://irap.org/2025/06/cyclerap-receives-ecf-award/)
8. [Dublin’s Push for Safer Cycling Routes Supported by CycleRAP - iRAP](https://irap.org/2025/07/cyclerap-powers-dublins-push-for-safer-cycling-routes/)
9. [Transurban and Safe System Solutions Assess Risks for Cyclists, Supported by CycleRAP - iRAP](https://irap.org/2026/02/transurban-and-safe-system-solutions-assess-risks-for-cyclists-supported-by-cyclerap/)
10. [CycleRAP Supports Making Slovenia’s Cycling Infrastructure as Elite as its Cyclists - iRAP](https://irap.org/2026/05/cyclerap-supports-making-slovenias-cycling-infrastructure-as-elite-as-its-cyclists/)
11. [PTV Group to support new international project to map cycling safety](https://www.ptvgroup.com/en/resources/news/company/ptv-group-support-new-international-project-map-cycling-safety)
12. [1 Data on cycling use and cycling infrastructure](https://unece.org/sites/default/files/2024-05/Data%20on%20cycling%20use%20and%20cycling%20infra%20-%20DG%20MOVE.pdf)
13. [Commission adopts Implementing Regulation to strengthen sustainable urban mobility through harmonised indicators](https://transport.ec.europa.eu/news-events/news/commission-adopts-implementing-regulation-strengthen-sustainable-urban-mobility-through-harmonised-2026-07-09_en)
14. <https://transport.ec.europa.eu/system/files/2026-07/C_2026_4676_1_EN_annexe_acte_autonome_part1_v2.pdf>
15. [European Commission Approves Urban Mobility Data by 2027 - Railway News](https://railwaynews.net/european-commission-approves-urban-mobility-data-by-2027.html)
16. [2025: Shaping the road ahead](https://www.ecf.com/en/news/2025-shaping-the-road-ahead/)
17. [Cycling data overview 2025 - Publications Office of the EU](https://op.europa.eu/en/publication-detail/-/publication/8eaca272-5e7c-11f1-aa6d-01aa75ed71a1/language-en)
18. [Bicycle networks, street networks, and POIs for 403 European cities for BikeNetKit](https://zenodo.org/records/22271229)
19. [How Good Is Open Bicycle Network Data? A Countrywide Case Study of Denmark - Vierø - 2025 - Geographical Analysis - Wiley Online Library](https://onlinelibrary.wiley.com/doi/abs/10.1111/gean.12400)
20. [Network analysis of the Danish bicycle infrastructure: Bikeability across urban-rural divides](https://arxiv.org/pdf/2412.06083)
21. [Published December 29, 2023](https://zenodo.org/records/10443014)
22. [Quantifying Cycling Infrastructure Investment Needs Across Europe Using OpenStreetMap Data](https://link.springer.com/chapter/10.1007/978-3-031-85578-8_21)
23. <https://european-cyclists-federation.github.io/Documents/Methodology.pdf>
24. [QECIO (2.0) Downloads](https://european-cyclists-federation.github.io/download.html)
25. [The Eco-Counter connector is evolving 🚲](https://community.huwise.com/product-updates/the-eco-counter-connector-is-evolving-518)
26. [Eco-Counter API - Documentation](https://developers.eco-counter.com/)
27. [Data Sharing & API](https://www.eco-counter.com/solutions/data-sharing-api)
28. [Eco-Visio API - AMRO BALTIC](https://www.amro.lv/en/shop/customer-service/people-counter-sensors/eco-visio-software/eco-visio-api/)
29. [Verdens bedste cykelby](https://byudvikling.kk.dk/mobilitet/verdens-bedste-cykelby)
30. [Mobilitetsredegørelse](https://byudvikling.kk.dk/mobilitet/mobilitetsredegoerelse)
31. [Mobilitetsredegørelse 2026](https://byudvikling.kk.dk/sites/default/files/2026-07/Mobilitetsredeg%C3%B8relse%202026_opt-a.pdf)
32. [Mobilitetsredegørelse 2026](https://www.kk.dk/sites/default/files/agenda/b5ef762c-02eb-4fd0-9b7f-2c5bad9bab73/00b05ca2-e295-4734-b19f-53d82d81093d-bilag-3.pdf)
33. [Færre biler pr. københavner](https://www.magasinetkbh.dk/indhold/faerre-biler-lidt-plads-til-cykler-mobilitetsredegorelse-2025)
34. [500.000 Euro für den Radverkehr](https://berlin.adfc.de/artikel/500000-euro-fuer-den-radverkehr-mehr-gibt-es-nicht)
35. [Drastische Kürzungen im Doppelhauhalt von Berlin: Radfahrer und Fußgänger sind die großen Verlierer](https://www.berliner-zeitung.de/mensch-metropole/drastische-kuerzungen-im-doppelhauhalt-von-berlin-radfahrer-und-fussgaenger-sind-die-grossen-verlierer-li.2351755)
36. [Berlin kündigt Kürzungen bei Rad- und Fußverkehr an: Warum #unkürzbar sein müssen](https://www.verbandsbuero.de/berlin-kuendigt-kuerzungen-bei-rad-und-fussverkehr-an-warum-unkuerzbar-sein-muessen/)
37. [Radwege-Ausbau in Berlin: Nur wenige Bezirke kommen voran](https://www.entwicklungsstadt.de/radwege-ausbau-in-berlin-stockt-nur-wenige-bezirke-kommen-voran/)
38. [Verkehrswende-Monitor Berlin](https://changing-cities.org/kampagnen/verkehrswende-monitor/)
39. [Cycling in Berlin](https://en.wikipedia.org/wiki/Cycling_in_Berlin)
40. [Schwarz-Rot verschiebt Zieljahr des Berliner Radverkehrsnetzes um fünf Jahre](https://www.bundle.app/de/nachrichten/schwarz-rot-verschiebt-zieljahr-des-berliner-radverkehrsnetzes-um-funf-jahre-0E5738BB-3FF2-43FE-BC8D-57E8EE39BBE3)
41. [Mobilitätsgesetz in Berlin: Warum die Kritik an der Novelle wächst](https://www.entwicklungsstadt.de/mobilitaetsgesetz-in-berlin-warum-die-kritik-an-der-novelle-waechst/)
42. [„Radwegestopp 2.0“: Berliner Koalition streicht zentrale Ziele aus dem Mobilitätsgesetz](https://www.tagesspiegel.de/berlin/radwegestopp-20-berliner-koalition-streicht-zentrale-ziele-aus-dem-mobilitatsgesetz-15519293.html)
43. [Neuer Radweg, alte Bäume: Der Streit um die Ollenhauerstraße erklärt](https://www.entwicklungsstadt.de/ollenhauerstrasse-vor-dem-umbau-buerger-kaempfen-weiter-gegen-baumfaellungen/)
44. [Ollenhauerstraße, 116 Bäume, ein Radweg: Protest vorm Rathaus](https://www.entwicklungsstadt.de/ollenhauerstrasse-116-baeume-ein-radweg-protest-vorm-rathaus/)
45. [Ollenhauerstraße in Reinickendorf: Details verschärfen Debatte](https://www.entwicklungsstadt.de/ollenhauerstrasse-in-reinickendorf-neue-details-verschaerfen-debatte/)
46. [Radweg Ollenhauerstraße wird freigegeben - Berlin.de](https://www.berlin.de/sen/uvk/presse/pressemitteilungen/2023/pressemitteilung.1346382.php)
47. [Klimakrise: Berlin baut Unter den Eichen Radweg zurück!? - WE RIDE NEWS](https://www.weride.bike/news/berlin-baut-radweg-unter-den-eichen-zurueck/)
48. [Start](https://stadtrand-nachrichten.de/)
49. [Rückbau von Radwegen: Kulturkampf auf 600 Metern](https://taz.de/Rueckbau-von-Radwegen/!6176512/)
50. [Unter den Eichen: Radweg-Rückbau erfolgt nicht sofort](https://stadtrand-nachrichten.de/unter-den-eichen-radweg-rueckbau-erfolgt-nicht-sofort/)
51. [Petition: Berliner Verkehrswende verteidigen.](https://mitmachen.duh.de/verkehrswende-berlin/)
52. [DUH will Abschaffung des Berliner Radwegs „Unter den Eichen“ vor Gericht verhindern](https://www.duh.de/presse/pressemitteilungen/pressemitteilung/berliner-radwegestopp-deutsche-umwelthilfe-will-abschaffung-des-radwegs-unter-den-eichen-vor-geri/)
53. [Wahl zum Abgeordnetenhaus von Berlin 2026](https://de.wikipedia.org/wiki/Wahl_zum_Abgeordnetenhaus_von_Berlin_2026)
54. [Abgeordnetenhauswahl Berlin 2026 — Umfragen & Koalitionen](https://koalitions-rechner.de/abgeordnetenhauswahl-berlin-2026.html)
55. [Berlin Wahl 2026 Koalition: Diese Mehrheiten sind möglich](https://www.rhein-wied-news.com/berlin-wahl-2026-koalition-diese-mehrheiten-sind-moeglich/)
56. [Berliner Kantstraße: Deutsche Umwelthilfe zieht mit Eilantrag gegen den autovernarrten Berliner Senat wegen Rückbau des Radwegs vor Gericht](https://www.88energie.de/berliner-kantstra-e-deutsche-umwelthilfe-zieht-mit-eilantrag-gegen-den-autovernarrten-berliner-senat-wegen-r-ckbau-des-radwegs-vor-gericht-2271240.html)
57. [Kantstraße: Radweg oder Busspur? Gericht erhöht Druck im Streit](https://www.entwicklungsstadt.de/radweg-oder-busspur-in-der-kantstrasse-gericht-erhoeht-druck-im-streit/)
58. [Kantstraße: Radweg bleibt vorerst erhalten](https://www.entwicklungsstadt.de/kantstrasse-radweg-bleibt-vorerst-erhalten-gericht-prueft-rueckbau/)
59. [Radweg auf der Kantstraße: Verwaltungsgericht lehnt Fristverlängerungsantrag des Senats ab und verlangt umgehende Mitteilung, ob dieser an Rückbauplänen nach Berlin-Wahl festhält](https://www.presseportal.de/pm/22521/6357382)
60. [Streit um Radweg an der Berliner Kantstraße: Gericht setzt Verkehrsverwaltung unter Druck](https://www.tagesspiegel.de/berlin/streit-um-radweg-an-der-berliner-kantstrasse-gericht-setzt-verkehrsverwaltung-unter-druck-16090301.html)
61. [Radinfrastruktur in Berlin: Ringen um den Radweg in der Kantstraße](https://taz.de/Radinfrastruktur-in-Berlin/!6216378/)
62. [Council of Paris](https://en.wikipedia.org/wiki/Council_of_Paris)
63. [Eurom%C3%A9tropole de Strasbourg](https://en.wikipedia.org/wiki/Eurom%C3%A9tropole_de_Strasbourg)
64. [List of mayors of Strasbourg](https://en.wikipedia.org/wiki/List_of_mayors_of_Strasbourg)
65. [Radwegoffensive 2025 Bilanz](https://www.fahrradwien.at/wp-content/uploads/sites/2/2026/01/Radwegoffensive_2025_Bilanz.pdf)
66. [Engagements du Plan vélo - Observatoire du Plan Vélo de Paris](https://observatoire.parisenselle.fr/engagements/)
67. [La mairie dévoile son plan vélo pour un Paris 100 % cyclable en 2026](https://www.timeout.fr/paris/actualites/la-mairie-devoile-son-plan-velo-pour-un-paris-100-cyclable-en-2026-102621)
68. [Observatoire du Plan Vélo de Paris](https://observatoire.parisenselle.fr/)
69. [Conduire à Paris : que réserve le nouveau maire Emmanuel Grégoire aux automobilistes ? - L'argus](https://www.largus.fr/actualite-automobile/conduire-a-paris-que-reserve-le-nouveau-maire-e-gregoire-aux-automobilistes-dans-la-capitale-30046059.html)
70. [Vélos sur le périph’ et limitation à 30 km/h : la nouvelle annonce qui secoue Paris](https://www.voituremalin.com/articles/velos-sur-le-periph-et-limitation-a-30-km-h-la-nouvelle-annonce-qui-secoue-paris)
71. [Municipales à Strasbourg : les mobilités vues par Catherine Trautmann](https://www.rue89strasbourg.com/mobilites-catherine-trautmann-municipales-strasbourg-379971)
72. [Strasbourg rallume la nuit : Trautmann tient sa promesse](https://strasinfo.fr/2026/05/13/strasbourg-rallume-la-nuit-trautmann-tient-sa-promesse/)
73. [À Strasbourg, un aménagement dangereux sur une piste cyclable provoque colère et moqueries : actuelle et ancienne municipalité nient l'avoir décidé](https://france3-regions.franceinfo.fr/grand-est/bas-rhin/strasbourg-0/a-strasbourg-un-amenagement-dangereux-sur-une-piste-cyclable-provoque-colere-et-moqueries-actuelle-et-ancienne-municipalite-nient-l-avoir-decide-3405139.html)
74. [Hungary election 2026 results: Petér Magyar wins, Trump ally Viktor Orbán concedes landmark defeat](https://www.cnn.com/2026/04/12/world/live-news/hungary-election-orban-magyar)
75. [Just the Facts](https://www.europeanmovement.ie/just-the-facts-hungarian-elections/)
