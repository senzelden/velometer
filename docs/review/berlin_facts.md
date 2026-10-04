# Berlin and comparison cities: reported-figure candidates (M6 Task 14 Step 4)

These are candidate `ExternalFigure` rows for your verdict. Nothing here is loaded into `config/external/figures.csv`.
Retrieval date for every source below: 2026-10-05. Every URL was fetched in this session; where a page was read through the fetch tool's summary or a PDF text extraction, the quoted sentence is as returned and is worth a glance on the live page.
No figure here is a claim that OSM-mapped km equal any reported km.

## Awaiting a source URL (rows already in figures.csv)

These are `config/external/figures.csv` lines 20-23 (blank `source_url`). Row values are as in the CSV.

### Row line 20: official / new_cycle_infra_km / 21.2 km / whole_network / unknown

- Found URL: https://www.nordkurier.de/regional/brandenburg/bericht-senat-liess-viele-mittel-fuer-radverkehr-liegen-4840670 (dpa text, published 08.09.2026). Same dpa text: https://www.tagesspiegel.de/berlin/dpa-fahrrad-fortschrittsbericht-16031059.html (08.09.2026; the fetch returned a summary with "Mit 21,2 Kilometern ..." and "2022 waren es noch 32,4 Kilometer").
- Classification: SECONDARY (dpa reporting on the Senate's Fahrrad-Fortschrittsbericht to the Hauptausschuss). The report itself was not reached; the berlin.de Radfortschrittsbericht page returned no document list.
- Verbatim: "Das hatte zur Folge, dass mit 21,2 Kilometern deutlich weniger neue Fahrradwege fertiggestellt wurden als in den Vorjahren. 2022 waren es noch 32,4 Kilometer, seither ist die Länge jedes Jahr gesunken."
- Basis (Streckenlänge or Reallänge) not stated in the article. Keep `unknown`.
- Verdict:

### Row line 21: official / new_cycle_infra_km / 20.5 km / whole_network / unknown ("Senate preliminary, Dec 2025")

- Found URL: https://www.tagesspiegel.de/berlin/senat-hangt-eigenem-ziel-hinterher-205-kilometer-neue-radwege-in-berlin-gebaut-15065944.html (19.12.2025). Also echoed in https://www.entwicklungsstadt.de/rueckzug-vom-rad-wie-berlin-den-ausbau-der-fahrradinfrastruktur-systematisch-herunterfaehrt/ (02.01.2026: "Für das Jahr 2025 meldete die Senatsverwaltung 20,5 Kilometer neue Radwege").
- Classification: SECONDARY (dpa query answered by the Senate transport administration; no Senate document reached).
- Verbatim: "Im laufenden Jahr wurden 35 Radwege-Projekte mit einer Gesamtlänge von 20,5 Kilometern gebaut, teilte die Senatsverwaltung für Verkehr auf Anfrage der Deutschen Presse-Agentur mit."
- Note: stated on 19 Dec 2025, so the year was not complete ("im laufenden Jahr"); the reference_date 2025-12-31 in the CSV is a year-end label, not the statement date. Basis not stated.
- Verdict:

### Row line 22: official / new_cycle_infra_km / 17.3 km / vorrangnetz_ergaenzungsnetz / unknown ("infraVelo")

- Found URL: NOT FOUND.
- No fetched page contains 17.3 km. See "Not found".
- Verdict:

### Row line 23: changing_cities / new_cycle_infra_km / 25.2 km / whole_network / unknown

- Found URL: https://changing-cities.org/kampagnen/verkehrswende-monitor/
- Classification: PRIMARY (Changing Cities' own monitor).
- Verbatim: "25,2 Kilometer wurden 2025 neu geschaffen." The page says Changing Cities measure it themselves ("Wir messen selbst nach!") and the data stand is 31 Dec 2025 (as returned by the fetch tool).
- Note: the same page gives 183.6 km built since 2018 (6.8% of the planned network); that is a different base from the Senate's "gut 140 km, 5.8%, 2017-2025".
- Verdict:

## Candidates

Common fields: retrieved_at 2026-10-05; Verdict empty on all. `source` proposals: `official` where a Senate or city-government document is the origin, else flagged NEW.

### C1. Vorrangnetz implemented km

- city_id berlin; source `official`; metric_name `vorrangnetz_implemented_km` (NEW); value 78.2; unit km
- reference_date 2026-05-20 (date of the Senate answer, "derzeit"); network_scope `vorrangnetz`; length_basis `unknown`
- source_url https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-25987.pdf
- PRIMARY (Drucksache 19/25987, Schriftliche Anfrage Tino Schopf, SPD, of 27.04.2026; answer of the Senate administration of 20.05.2026; the Senate asked infraVelo for input)
- Verbatim (Antwort zu 18): "Insgesamt sind 78,2 km des Radvorrangnetzes umgesetzt worden."
- Confidence: high for the value. Basis unstated for implemented km; the target network is given as "Streckenlänge" (see C1b).
- Verdict:

### C1b. Vorrangnetz target km

- city_id berlin; source `official`; metric_name `vorrangnetz_target_km` (NEW); value 870 (approx.); unit km; reference_date 2026-05-20; network_scope `vorrangnetz`; length_basis `streckenlaenge`
- source_url same Drucksache as C1; PRIMARY
- Verbatim (Antwort zu 14): "Das Radvorrangnetz umfasst als planerisches Zielnetz ca. 870 km Streckenlänge."
- Confidence: high; "ca." value. Optional row; useful as denominator for C1.
- Verdict:

### C1c. Vorrangnetz km implemented in 2025 (optional, same Drucksache)

- city_id berlin; source `official`; metric_name `new_cycle_infra_km`; value 7.5; unit km; reference_date 2025-12-31; network_scope `vorrangnetz`; length_basis `unknown`
- source_url same Drucksache; PRIMARY
- Source is the table in Antwort zu 17, row "Summe": "Summe 10,1 5,1 9,6 7,5" (2022, 2023, 2024, 2025 in km). The table carries no sentence form; the row label text is the quote.
- Confidence: high for the extraction; the table header reads "Vorrangnetz [Km]".
- Verdict:

### C2. 2025 money spent

- city_id berlin; source `official` (the report is the Senate's, but only dpa was reached; see classification); metric_name `budget_spent_eur` (NEW); value 27000000 ("knapp"); unit eur; reference_date 2025-12-31; network_scope `whole_network` (all budget lines, includes federal funds); length_basis `unknown`
- source_url https://www.nordkurier.de/regional/brandenburg/bericht-senat-liess-viele-mittel-fuer-radverkehr-liegen-4840670
- SECONDARY (dpa on the Fahrrad-Fortschrittsbericht)
- Verbatim: "Inklusive Bundesmitteln flossen 2025 knapp 27 Millionen Euro in den Berliner Radverkehr, wie aus dem Fahrrad-Fortschrittsbericht der zuständigen Verkehrssenatsverwaltung für den Hauptausschuss im Abgeordnetenhaus hervorgeht."
- Confidence: medium; "knapp 27" so the exact value is below 27.0M. Also "flossen" (flowed), and the article says about 4 M less than the previous year.
- Verdict:

### C3. 2025 money available

- city_id berlin; source `official` (see C2); metric_name `budget_available_eur` (NEW); value 82400000; unit eur; reference_date 2025-12-31; network_scope `whole_network` (all Haushaltstitel); length_basis `unknown`
- source_url same Nordkurier article; SECONDARY
- Verbatim: "Dem Bericht zufolge standen im vergangenen Jahr über alle Haushaltstitel hinweg rund 82,4 Millionen Euro für den Radverkehr zur Verfügung."
- Context sentence: "In der Abteilung Verkehr wurden demnach nur ein Drittel der verfügbaren Mittel ausgegeben. In der Abteilung Tiefbau waren es 80 Prozent."
- Confidence: medium. Note C2 and C3 may not be like-for-like: 27 M "flossen ... inklusive Bundesmitteln" versus 82.4 M "zur Verfügung". The article itself does not give a spent/available ratio for the total.
- Verdict:

### C4. Network completed 2017-2025 (three values from one sentence)

- city_id berlin; source `official` (see C2); network_scope `whole_network` (planned Radverkehrsnetz); length_basis `unknown`; reference_date 2025-12-31
- Metrics (all NEW): `radverkehrsnetz_completed_km` 140 km ("gut 140"); `radverkehrsnetz_target_km` 2400 km; `radverkehrsnetz_completed_share_pct` 5.8 pct
- source_url https://www.nordkurier.de/regional/brandenburg/bericht-senat-liess-viele-mittel-fuer-radverkehr-liegen-4840670 ; SECONDARY
- Verbatim: "Von den 2.400 Kilometern Strecke, die aktuell im Berliner Radverkehrsnetz vorgesehen sind, wurden zwischen 2017 und 2025 lediglich gut 140 Kilometer oder rund 5,8 Prozent fertiggestellt."
- Confidence: medium. 140/2400 = 5.83%. Tagesspiegel (02.07.2026, see C5) gives the network as "gut 2.370 Kilometern", so the denominator varies between sources.
- Verdict:

### C5. Mobilitätsgesetz amendment: target years

- city_id berlin; source NEW proposal (`news_secondary`) or no row (narrative only); metric_name `vorrangnetz_target_year` (NEW) value 2030, and `nebennetz_target_year` (NEW) value 2035; unit year; reference_date 2026-07-02 (article date); network_scope `vorrangnetz` / `nebennetz`; length_basis `unknown`
- source_url https://www.entwicklungsstadt.de/mobilitaetsgesetz-in-berlin-warum-die-kritik-an-der-novelle-waechst/ (02.07.2026) and https://www.tagesspiegel.de/berlin/landesparlament-gesetz-erlaubt-weniger-tempo-beim-radnetz-ausbau-in-berlin-15789369.html (02.07.2026). Both SECONDARY. No Abgeordnetenhaus Drucksache for the amendment was reached.
- Verbatim (entwicklungsstadt): "Nach dem bisherigen Gesetz sollte das Radverkehrsnetz samt Beschilderung bis 2030 entstehen. Die Novelle unterscheidet nun zwischen Radvorrangnetz bis 2030 und Nebennetz bis 2035."
- Verbatim fragments (Tagesspiegel, as returned by the fetch tool): "das sogenannte Radvorrangnetz mit einer Gesamtlänge von 865 Kilometern" and "mit einer Länge von gut 2.370 Kilometern und entsprechender Beschilderung nun bis 2035 zur Verfügung stehen".
- Confidence: low-medium for "enacted". Entwicklungsstadt says the vote was scheduled for 3 July 2026, and both articles are dated 2 July, i.e. before the vote. The fetch summary of Tagesspiegel called the law "passed" but that is not confirmed by any dated post-vote source. This is a date, not a length; consider a narrative note rather than a row.
- Verdict:

### C6. Kantstraße rollback cost

- city_id berlin; source NEW proposal (`news_secondary`); metric_name `kantstrasse_rollback_cost_eur` (NEW); value 2400000 ("rund"); unit eur; reference_date 2026-03-31 ("Stand März 2026"); network_scope `single_project`; length_basis `unknown`
- source_url https://www.entwicklungsstadt.de/kantstrasse-in-charlottenburg-so-viel-kostet-der-radweg-rueckbau/ (21.08.2026); SECONDARY
- Verbatim: "Die Gesamtkosten der Maßnahme werden nach Angaben des Senats mit Stand März 2026 auf rund 2,4 Millionen Euro beziffert."
- Status context (not row values): DUH filed an Eilantrag at the Verwaltungsgericht on 07.09.2026 (https://www.duh.de/presse/pressemitteilungen/pressemitteilung/berliner-kantstrasse-deutsche-umwelthilfe-zieht-mit-eilantrag-gegen-den-autovernarrten-berliner-sena/ ; heading "Montag, 07.09.2026"). Entwicklungsstadt 15.09.2026: the Senate committed to the court that works would not begin before 30 Sep 2026. Entwicklungsstadt 24.09.2026 (https://www.entwicklungsstadt.de/radweg-oder-busspur-in-der-kantstrasse-gericht-erhoeht-druck-im-streit/): marking work scheduled "ab dem 1. Oktober", no final stop and no approval yet. The "postponed to 7 Oct 2026" claim was NOT found (see Not found).
- Confidence: medium for the cost (a Senate figure reported by a local news site). Likely a narrative item, not a figure row.
- Verdict:

### C7. Titel 72016 (Kap. 0730), 2025 and from 2026

- city_id berlin; source NEW proposal (`adfc_berlin`) for the 6.5 M and 0.5 M values; metric_name `titel_72016_budget_eur` (NEW); unit eur; network_scope `whole_network` (budget title, "Verbesserung der Infrastruktur für den Radverkehr"); length_basis `unknown`
- Row a: value 6500000, reference_date 2025-12-31; Row b: value 500000 per year from 2026, reference_date 2026-01-01
- source_url https://berlin.adfc.de/artikel/500000-euro-fuer-den-radverkehr-mehr-gibt-es-nicht (ADFC Berlin, 20.01.2025). SECONDARY (advocacy group describing the Senate's draft budget).
- Verbatim (as returned by the fetch tool): "6,5 Millionen vorgesehen" for 2025 and "reduziert der Senat diesen Posten ab 2026 auf 500.000 Euro pro Jahr".
- Confidence: LOW for the 2026 value. The ADFC text predates the adopted double budget. Drucksache 19/2627-3 (17.12.2025, a Greens amendment motion to the Haushaltsgesetz 2026/27) lists Titel 72016 with "Ansatz bisher" 5.725.000 (2026) and 5.750.000 (2027), and proposed 6.500.000 / 6.525.000. See Notes.
- Verdict:

### C8. Copenhagen: cycling trip share

- city_id copenhagen; source `official` (Københavns Kommune, Teknik- og Miljøforvaltningen); metric_name `cycling_trip_share_pct` (NEW); value 28; unit pct; reference_date 2025-12-31; network_scope `whole_city_trips`; length_basis `unknown` (not an infrastructure figure)
- source_url https://byudvikling.kk.dk/sites/default/files/2026-07/Mobilitetsredeg%C3%B8relse%202026_opt-a.pdf (PDF; text extracted locally)
- PRIMARY
- Verbatim: "I 2025 blev 26 % af alle ture i København foretaget i bil mens 25 % af turene blev foretaget til fods, 28 % på cykel og 21 % blev tilbagelagt med kollektiv transport. Sammenlignet med 2024 er turandelen i bil faldet med tre procentpoint, turandelen for cykler faldet med ét procentpoint, ..."
- Confidence: high.
- Verdict:

### C8b. Copenhagen: cycled km, weekdays

- city_id copenhagen; source `official`; metric_name `cycling_traffic_change_pct` (NEW); value -6; unit pct; reference_date 2025-12-31; network_scope `whole_city_traffic_volume`; length_basis `unknown`
- source_url same Mobilitetsredegørelse 2026; PRIMARY
- Verbatim: "Tilsvarende blev der tilbagelagt 2,48 mio. km på cykel og 1,01 km til fods (TU). Det er et fald i cykeltrafikken på 6 % og en stigning i km til fods på 6 % fra året før."
- Note: HANDOVER says "cycle km -6%". The source's km are kilometres cycled by traffic on weekdays (traffic volume, 2.48 million km), NOT kilometres of cycle infrastructure. Naming the metric `cycle km` would mislead; the metric name above avoids it.
- Verdict:

### C8c. Copenhagen: cycle track km (optional)

- city_id copenhagen; source `official`; metric_name `cycle_track_km` (NEW); value 401; unit km; reference_date 2025-12-31; network_scope `cykelsti` (as defined by the municipality; definition not read); length_basis `unknown`
- source_url same Mobilitetsredegørelse 2026; PRIMARY
- Verbatim: "I 2025 var der 401 km cykelsti i København." (Mobilitetsredegørelse section "Cykelstier og cykelparkering")
- Confidence: medium; the municipal definition of "cykelsti" was not checked. Clean Cities in figures.csv has Copenhagen at 397 km protected for May 2025; these are different definitions and dates.
- Verdict:

### C9. Vienna: Radwegeausbau 2025 (projects started)

- city_id vienna; source NEW proposal (`mobilitaetsagentur_wien`) or `official` if you accept the agency as city government; metric_name `radwegeausbau_started_km` (NEW); value 20.447; unit km; reference_date 2025-12-31; network_scope `hauptradverkehrsnetz`; length_basis `unknown` (the document says lengths are measured "von Beginn bis Endpunkt ... jede Radfahranlage für sich")
- source_url https://www.fahrradwien.at/wp-content/uploads/sites/2/2026/01/Radwegoffensive_2025_Bilanz.pdf (PDF; text extracted locally). Host is fahrradwien.at; that it belongs to the city's mobility agency was not checked against a wien.gv.at page. Treat as primary-by-agency, owner unverified.
- Verbatim: "Die Bilanz zum Radwegeausbau 2025 enthält 53 Radinfrastrukturprojekte im Hauptradverkehrsnetz, mit deren Realisierung im Jahr 2025 begonnen wurde. Es handelt sich um 20,4 Kilometer, die im Jahr 2025 gestartet wurden." Header of the document: "53 Projekte 20.447 m Länge".
- Note: these are projects STARTED in 2025, not completed; it is not the same measure as Berlin's "neu fertiggestellt". Same document: "Im Jahr 2025 wurden 57 Mio. in die Radinfrastruktur investiert (inklusive Planung, Beleuchtung etc)."
- Confidence: high for the value; the metric must not be named `new_cycle_infra_km`.
- Verdict:

### Context only, no row: Clean Cities 2025

- Already loaded as `clean_cities_2025` rows with URLs. Berlin in figures.csv: protected_km 925, network_km 5350, protected_share_pct 17. HANDOVER's "17% (925 km)" matches. Every other city share in HANDOVER §11 also equals its figures.csv row (Paris 48, Helsinki 48, Copenhagen 43, Amsterdam 34, Wroclaw 20, Barcelona 19, Oslo 17, Warsaw 15, Lyon 14, Vienna 14 and the corrected 22.0, Madrid 8, Prague 6, Budapest 4). Not re-fetched; only compared with the CSV.

### Context only, no row: EU Urban Mobility Indicators

- No city_id; no row proposed.
- Fetched: https://transport.ec.europa.eu/transport-themes/urban-transport/sustainable-urban-mobility-planning-and-monitoring_en. As returned by the fetch tool it says the revised TEN-T Regulation requires an Implementing Act setting out a limited number of indicators and "The Implementing Act requires Member States to submit the data by 31 December 2027." The page text returned contained no "C(2026) 4676" and no statement that cycling appears only as mode share.
- C(2026) 4676 of 9 Jul 2026 was NOT found. The HANDOVER wording (cycling only as trip mode share, no infrastructure indicator) is unverified here.

## Not found

- infraVelo 17.3 km (Vorrang + Ergänzungsnetz) for 2025.
  - Queries: "infraVelo 2025 17,3 Kilometer Vorrangnetz Ergänzungsnetz fertiggestellt Bilanz"; "infraVelo Jahresbilanz 2025 Kilometer Radinfrastruktur fertiggestellt Vorrangnetz Ergänzungsnetz 17,3 km"; "\"17,3 Kilometer\" Radwege Berlin 2025 infraVelo".
  - Pages checked: entwicklungsstadt.de articles of 27.04.2026, 02.01.2026 (contain no 17.3), the Tagesspiegel 19.12.2025 article. Search results listed infraVelo pages (infravelo.de/aktuelles/, "Bezirklicher Fortschritt in Zahlen") and the Hauptausschuss reports h19-1733.B-1-v.pdf (28.01.2025) and h19-1733.C-v.pdf (24.06.2025), but I did not fetch them and no result snippet gave 17.3. The search snippet about the June 2025 report (priority network 10.8 km, Ergänzungsnetz 9.6 km) was not verified by a fetch and is not used.
  - A similar number exists but is a different thing: Tagesspiegel (older article) "Nur 17,5 Kilometer für 2025 geplant" is a plan, not a result. Not fetched.
- Primary document for 21.2 km / 82.4 M / ~27 M / 140 km (the Fahrrad-Fortschrittsbericht 2025 itself, Hauptausschuss).
  - Queries: "Fortschrittsbericht Radverkehrsplan Berlin 2025 Hauptausschuss Rote Nummer Bericht SenMVKU September 2026 pdf"; "Fortschrittsbericht Radverkehr Berlin 2025 21,2 Kilometer ...".
  - Page checked: https://www.berlin.de/sen/uvk/mobilitaet-und-verkehr/verkehrsplanung/radverkehr/radprojekte/radfortschrittsbericht/ (no document list in the fetched text). The Drucksache 19/25987 answer points to that page for the Fortschrittsberichte.
- Kantstraße "Senate postponed works to 7 Oct 2026" and "no ruling yet": the latest dated source found is 24.09.2026 (works not before 30 Sep, markings from 1 Oct). No source with 7 Oct or any court ruling found. Queries: "Kantstraße Berlin Radweg Rückbau Verwaltungsgericht Eilantrag Deutsche Umwelthilfe 7. Oktober". Other search hits (taz, Berliner Zeitung, presseportal, newzs) were not fetched.
- Titel 72016 "conflicting €4.75M for 2025": no source found. Queries: "Berlin Haushalt 2026/27 Radverkehr Titel 72016 4,75 Millionen Euro 2025"; "ADFC Berlin Titel 72016 Haushalt 6,5 Millionen 2025 0,5 Millionen 2026 Radverkehr". ADFC page does not contain 4.75. A search snippet mentioned an Hauptausschuss item (h19-2026.AM-v.pdf) giving "between approximately 6,000,000 € and a maximum of 6,648,074.89 €" for 2025 Bindungen; that document was not fetched and the snippet is not used as a value.
- Copenhagen "no Cykelregnskab since the switch": absence cannot be shown from a page. byudvikling.kk.dk/mobilitet/mobilitetsredegoerelse (as summarised by the fetch tool) lists Cykelredegørelser to 2020 and Mobilitetsredegørelse from 2021, and says the report collects strategies that expired at end of 2025. The wording "Cykelregnskab" was not found on the pages checked.
- EU C(2026) 4676 (see above). Queries: "EU Urban Mobility Indicators Commission Recommendation C(2026) 4676 cycling modal share first data 2027" and three follow-ups. EUR-Lex hits C/2026/04668 and others were different documents.
- Berlin Mobilitätsgesetz amendment primary text (Drucksache, Gesetz- und Verordnungsblatt) and confirmation of the vote outcome: not reached.

## Notes

- Titel 72016 conflict. ADFC Berlin (20.01.2025) says 6.5 M for 2025 and 0.5 M per year from 2026. Drucksache 19/2627-3 of 17.12.2025 (Greens amendment motion to HG 26/27, based on the Hauptausschuss recommendation Drs. 19/2828 of 10.12.2025) shows Titel 72016 in column "bisher" at 5,725,000 (2026) and 5,750,000 (2027), with the Greens proposing 6,500,000 and 6,525,000. So the ADFC "0.5 M from 2026" does not match the Hauptausschuss version, and the adopted budget was not read here. Recommend not loading the 0.5 M value without the adopted Haushaltsplan. The €4.75 M figure was not found anywhere, so the €6.5 M vs €4.75 M conflict cannot be resolved from these sources.
- Four 2025 versions of new km: 21.2 (dpa on the Senate Fortschrittsbericht, 08.09.2026), 20.5 (Senate to dpa, 19.12.2025, year not over), 25.2 (Changing Cities own measurement), 17.3 (unsourced). The Senate answer in Drs. 19/25987 gives Vorrangnetz alone at 7.5 km for 2025 (C1c), which cannot be reconciled with the 17.3 km "Vorrang + Ergänzungsnetz" claim without the Ergänzungsnetz figure.
- 78.2 km (Vorrangnetz implemented) sits against ca. 870 km target in the same Drucksache, a different network from the 140 of 2,400 km (whole Radverkehrsnetz, 2017-2025) in the dpa report. Network totals vary: 870 (Drs.), 865 (Tagesspiegel, July 2026), 2,400 (dpa), "gut 2.370" (Tagesspiegel). Handover's "~870 km" is the Drucksache value.
- Changing Cities' 183.6 km since 2018 versus the Senate's 140 km since 2017 are not comparable (different counting and start year).
- All three Berlin money and 140 km items (C2, C3, C4) and the 21.2 km row come from dpa text; the underlying report is the Senate's, but "official" is a statement about origin, not about what was read. If you want strict marking, use a NEW source id such as `dpa_senate_report`.
- Copenhagen's "cycle km -6%" is cycled traffic volume, and the trip share is -1 percentage point. Vienna's 20.4 km are projects started, not completed. Neither should share the metric name `new_cycle_infra_km` with the Berlin rows.
- Berlin Clean Cities 17% / 925 km match figures.csv; nothing to load.
