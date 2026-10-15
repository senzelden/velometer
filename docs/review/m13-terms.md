# M13 Task 6: original national terms, source lookup

This is the lookup table for Task 7. It lists every in-scope hit from
`.superpowers/followups/original-terms-inventory.md` (Cmp. Y). For each hit it gives the
excerpt id `<source>/<excerpt>` that carries the original term, or "none found". Lines are
English files at m13 d609ebc, under `content/`. The German twin has the same walk path in its
`de/` file. Terms are quoted exactly as the excerpt prints them; Task 7 may need another
grammatical form, and that form must be one the excerpt supports.

Accessed 2026-10-15. Nothing was archived. All new excerpts are 60 words or fewer.

## New sources and excerpts (this task)

| Hit | Official page | Excerpt id | Excerpt (verbatim) |
|---|---|---|---|
| S2, S3, S4 | https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/lan-och-kommuner/ | `scb-lan-och-kommuner/21-lan` | "Här redovisas koder, namn och indelningsändringar för län och kommuner. SCB ansvarar för att förteckna regionala indelningar och ange koder för dessa. Sverige har idag 21 län och 290 kommuner." |
| S2, S4 | https://www.lansstyrelsen.se/stockholm/om-oss/om-lanet.html | `lansstyrelsen-stockholm-om-lanet/26-kommuner` | "Stockholms län har 26 kommuner" |
| S2, S3 | same page | `lansstyrelsen-stockholm-om-lanet/largest-lan` | "Sett till befolkningsmängd är vi landets största län. I dagsläget bor drygt två miljoner människor, en femtedel av Sveriges befolkning, i länets 26 kommuner." |
| NL5 | https://longreads.cbs.nl/regionale-economie-2018/begrippenlijst/ | `cbs-regionale-economie-2018-begrippen/groot-amsterdam` | "In deze publicatie zijn de grote steden gedefinieerd als kerngemeente plus omliggend gebied. Amsterdam betreft COROP-gebied Groot-Amsterdam" |
| NL5 | same page | `cbs-regionale-economie-2018-begrippen/corop-level` | "De COROP-indeling is een regionaal niveau tussen gemeenten en provincies in." |
| FR5 (Lyon) | https://www.insee.fr/fr/information/7929497 | `insee-collectivites-statut-particulier/metropole-de-lyon` | "Pour les collectivités territoriales à statut particulier, une numérotation spécifique a été introduite. La Ville de Paris (75C) Le Département-Région de Mayotte (976R) La Métropole de Lyon (69M)" |
| FR5 (Strasbourg) | https://www.strasbourg.eu/ville-eurometropole | `strasbourg-ville-eurometropole/two-institutions` | "La Ville et l'Eurométropole de Strasbourg sont deux institutions distinctes. Elles ont la particularité d'avoir à leur service une seule administration et un siège commun." |
| FR5 (Bordeaux) | https://www.bordeaux-metropole.fr/metropole/linstitution-territoire/que-fait-bordeaux-metropole | `bordeaux-metropole-que-fait/epci-28-communes` | "Bordeaux Métropole est un Établissement Public de Coopération Intercommunale ( EPCI ). Au service des 28 communes qui la composent" |
| FR7 | https://www.insee.fr/fr/metadonnees/definition/c1762 | `insee-departement/definition` | "Création de la Révolution (loi du 22 décembre 1789), le département est une circonscription administrative de l’État. Le Préfet représente les différentes administrations de l’État au niveau territorial. C’est aussi, par la loi du 10 août 1871, une collectivité locale autonome avec un organe délibérant et un exécutif élus." |
| ES4 | https://www.boe.es/buscar/act.php?id=BOE-A-1983-6317 | `boe-estatuto-autonomia-madrid/territory` | "Artículo 2. El territorio de la Comunidad de Madrid es el comprendido dentro de los límites de la provincia de Madrid." |
| ES8 | https://www.diba.cat/en/web/ladiputacio/institucio | `diba-institucio/provincia-311` | "La Diputació de Barcelona és una institució de govern local que impulsa el progrés i el benestar dels ciutadans del seu àmbit territorial: la província de Barcelona, 311 municipis en xarxa" |
| PL1 | https://stat.gov.pl/metainformacje/slownik-pojec/pojecia-stosowane-w-statystyce-publicznej/813,pojecie.html | `gus-pojecie-gmina/definition` | "Gmina Nazwa angielska: Gmina Definicja: Podstawowa jednostka najniższego szczebla zasadniczego trójstopniowego podziału terytorialnego państwa." |
| G8 | https://www.parlament-berlin.de/adosservice/19/Haupt/vorgang/h19-0389.A-v.pdf (existing source, PDF p. 17) | `berlin-fortschrittsbericht-2021/main-road-facilities` | "Im Jahr 2021 wurden im Berliner Radverkehrsprogramm 18,7 Kilometer Radverkehrsanlagen an Hauptverkehrsstraßen gebaut." |

Bordeaux: Task 7 cites `bordeaux-metropole-que-fait/epci-28-communes` with `[@…]` and does not
quote it. Its text keeps "( EPCI )" with spaces because that is how the page text reads once
normalised: EPCI is an `<abbr>` element.

`berlin-fortschrittsbericht-2021`: `accessed` moved from 2026-10-07 to 2026-10-15. Today's PDF
download is byte-identical (`cmp`) to the copy checked in this task. Both the existing `halved`
excerpt and the new `main-road-facilities` excerpt are found in its `pdftotext` text.

What I tried and could not use:
- ES4: every comunidad.madrid page tried (`/administracion-local/municipios-comunidad-madrid`,
  `/servicios/municipios`, `/taxonomy/term/2032`, a 2026 news page, the Estatuto page and a
  transparency PDF) returns 404 to the project's fetcher, although WebFetch reads
  `/taxonomy/term/2032`. `content --check --online` could never match those pages, so I used the
  Estatuto's consolidated text on BOE, the State's official gazette.
- FR5 Lyon: grandlyon.com times out for the project's fetcher. The existing source
  `lyon-grandlyon-circuler-a-velo` already fails the same way at baseline. I used Insee instead.
- FR5 Bordeaux: `/metropole`, `/metropole/communes-metropole` and
  `/metropole/fonctionnement-de-la-metropole` on bordeaux-metropole.fr return 404.
- ES8: `diba.cat/en/nova-home` returns 404. NL5: the CBS 2017 news page ("vier grote steden")
  returns 404.
- G8: no HTML page on berlin.de names Radverkehrsanlagen an Hauptverkehrsstraßen. I checked the
  Radverkehrsnetz and Radverkehrsplan pages, and gesetze.berlin.de renders no text without
  JavaScript. The excerpt therefore sits in the PDF that the sentence already cites. See the
  online-check note below.

## Lookup for Task 7 (every in-scope hit)

Type (from the inventory): P = English paraphrase only; O = the original term appears bare or
with a comma gloss; R = English first with the original in parentheses.

| Hit | file:line(s) (en) | Original term (as the excerpt prints it) | Excerpt id | Notes |
|---|---|---|---|---|
| N2 | narratives/oslo.yaml:14 | gang- og sykkelveier | `oslo-sykkelkart/map-contents` | O |
| N3 | narratives/oslo.yaml:19-20 | markerte sykkelfelt | `oslo-ey-evaluering-2024/mostly-lanes` | P |
| N5 | narratives/oslo.yaml:34-35 | gang- og sykkelveier, sykkelfelt og sykkelveier; sykkelveinett | `oslo-sykkelkart/map-contents`, `oslo-sykkelkart/network-290` | P |
| N6 | counters.yaml:14 | statlige og fylkeskommunale vegnett; kommunale veger | `vegvesen-trafikkdata/road-network` | Done in M12. **English side already has the original first** ("statlige og fylkeskommunale vegnett (state and county road network)", "kommunale veger (municipal roads)"). No English work. |
| D1 | narratives/copenhagen.yaml:30,32; explainer.yaml:26 | cykelsti | `copenhagen-mobilitetsredegorelse-2026/cykelsti-2025`, `copenhagen-cykelfokus-2024/cykelsti-definition` | O |
| D2 | narratives/copenhagen.yaml:32-33; explainer.yaml:27; organisations/copenhagen_kommune.yaml:18-19,32-33 | cykelbane(r) | `copenhagen-mobilitetsredegorelse-2026/cykelbaner-row`, `copenhagen-cykelfokus-2024/cykelbane-definition`, `copenhagen-cykelfokus-2024/cykelbaner-fraraades` | P |
| D3 | organisations/copenhagen_kommune.yaml:18 (R); :21, :28 (P) | cykelstier / cykelsti | as D1 | R/P |
| D10 | narratives/copenhagen.yaml:2 (title) | cykelsti | as D1 | Borderline: the body means tier A. Task 7 decides. |
| S1 | narratives/stockholm.yaml:30-31 | egna cykelbanor, kombinerade gång- och cykelbanor och cykelfält | `stockholm-cykelvagar/network-117-mil` | P |
| S2 | narratives/stockholm.yaml:34 | Stockholms län; län | **new** `lansstyrelsen-stockholm-om-lanet/26-kommuner`, `scb-lan-och-kommuner/21-lan` | German done in M12 ("einen Verwaltungsbezirk"). **English still needs work**: "Stockholms län, a county" is O; it needs the original first with a gloss. |
| S3 | narratives/combined.yaml:100 | län | **new** `scb-lan-och-kommuner/21-lan` (also `lansstyrelsen-stockholm-om-lanet/largest-lan`) | German done in M12 ("einen Verwaltungsbezirk"). **English still needs work**: "covers a county" is P. |
| S4 | explainer.yaml:101 | Stockholms län | **new** `lansstyrelsen-stockholm-om-lanet/26-kommuner` | O. Bare in both editions (de/explainer.yaml has "Stockholms län hat 4.946 km"). |
| F1 | narratives/helsinki.yaml:38-39 | erillisiä pyöräväyliä | `helsinki-priorisointiohjelma-2021/network-1200` | P |
| F2 | narratives/helsinki.yaml:40-41 | baanoja / baana | `helsinki-pyorailykatsaus-2021/baana-2020` | O |
| NL1 | narratives/amsterdam.yaml:31 | fietspad | `amsterdam-maps-fietsnetten/fietspad-definition` | O |
| NL2 | narratives/utrecht.yaml:29 | fietspad, fietsstrook | `utrecht-oud-utrecht-fietsstad/km-2012` | P |
| NL3 | narratives/utrecht.yaml:31 | hoofdfietspaden | `utrecht-actieplan-fietst-2015/gritting-400` | P |
| NL4 | narratives/utrecht.yaml:33 | provincie (Utrecht) | `utrecht-rtv-fietsersbond-2025/narrow-paths` | P |
| NL5 | narratives/amsterdam.yaml:35 | COROP-gebied Groot-Amsterdam | **new** `cbs-regionale-economie-2018-begrippen/groot-amsterdam` (also `/corop-level`) | O |
| FR3 | narratives/paris.yaml:31-32 | piste, voie verte, bande, couloir bus ouverts aux vélos, … doubles sens cyclable | `paris-opendata-lineaire-km/definition` | P; the English drops "voie verte". |
| FR5 | narratives/lyon.yaml:34; narratives/bordeaux.yaml:28-29; narratives/strasbourg.yaml:32 | Métropole de Lyon; Bordeaux Métropole (an EPCI); Eurométropole de Strasbourg | **new** `insee-collectivites-statut-particulier/metropole-de-lyon`, `bordeaux-metropole-que-fait/epci-28-communes`, `strasbourg-ville-eurometropole/two-institutions` | O. These excerpts also print the legal names: `lyon-plan-velo-2024/target-2000km` ("La Métropole de Lyon"), `bordeaux-crc-plan-velo-2025/network-2024` ("Bordeaux Métropole") and `strasbourg-velostras/velostras` ("L’Eurométropole de Strasbourg"). The first two are PDFs. |
| FR6 | narratives/lyon.yaml:34-35 | double sens cyclable, voie verte, accotement revêtu | `lyon-plan-velo-2024/breakdown-2023` | P. The German twin keeps "Voies vertes" bare. |
| FR7 | narratives/lyon.yaml:36; narratives/strasbourg.yaml:36; narratives/bordeaux.yaml:32 | département | **new** `insee-departement/definition` | O |
| FR8 | narratives/bordeaux.yaml:27 | couloirs bus | `bordeaux-ville-circuler-a-velo/city-378` | P |
| FR9 | narratives/bordeaux.yaml:29-30 | voies de circulation apaisée, voies piétonnes; zones apaisées | `bordeaux-plan-velo-2021-2026/network-2021`, `bordeaux-crc-plan-velo-2025/network-basis` | P |
| ES2 | narratives/madrid.yaml:32 | ciclocarril(es) | `madrid-opendata-infraestructura-ciclista/ciclocarril` | O |
| ES4 | narratives/madrid.yaml:37 | Comunidad de Madrid (territory = provincia de Madrid) | **new** `boe-estatuto-autonomia-madrid/territory` | O |
| ES5 | narratives/barcelona.yaml:30 | xarxa de carrils bici | `barcelona-premsa-42km-2025/network-268` | P. The German twin loses "lane". |
| ES6 | narratives/barcelona.yaml:34-35 | xarxa de vies ciclables amb carrers a velocitats de 30, 20 o 10 km/h | `barcelona-ara-32km-2021/itineraris-1150` | P |
| ES8 | narratives/barcelona.yaml:36 | província de Barcelona (Catalan) | **new** `diba-institucio/provincia-311` | P. The source is Catalan. No Spanish-language "provincia de Barcelona" excerpt was added. |
| G1 | narratives/berlin.yaml:22,25; narratives/combined.yaml:71,74-75; ui/en.yaml:494 (grep "Bezirke" at d609ebc also matches narratives/berlin.yaml:80,84, narratives/combined.yaml:216,226 and ui/en.yaml:269,602) | Bezirke(n) | `infravelo-organisation/responsibility` (also `berlin-mobg-page/collaboration`, `infravelo-faq/quarterly`) | O |
| G2 | organisations/abgeordnetenhaus.yaml:17; organisations/infravelo.yaml:14,18,21,24,29,34,40; organisations/senmvku.yaml:12,27,34,50 | Bezirke(n) | as G1 | P |
| G4 | narratives/berlin.yaml:35,40; explainer.yaml:46; organisations/abgeordnetenhaus.yaml:16,41,48; plans/berlin.yaml:5,22,24,51,53 | Radvorrangnetz / Vorrangnetz; Ergänzungsnetz; Nebennetz | `berlin-drs-19-25987/vorrangnetz-target`, `berlin-fortschrittsbericht-2025/network-share` (Vorrangnetz, Ergänzungsnetz), `berlin-mobg-amendment-2026/deadline-2030-2035` (Nebennetz) | German abgeordnetenhaus "Nebennetz" done in M12. **English still needs work**: abgeordnetenhaus.yaml:41 says "the secondary network"; the source term is "Nebennetz". No source shows Nebennetz to be the same as the Ergänzungsnetz, so keep the two terms apart. |
| G6 | organisations/abgeordnetenhaus.yaml:9,23; organisations/infravelo.yaml:22; organisations/senmvku.yaml:25 | Landes Berlin (Land Berlin) | `infravelo-faq/funding` | O |
| G6 (borderline) | organisations/abgeordnetenhaus.yaml:11 ("what the Land's money is spent on") | Landes Berlin | `infravelo-faq/funding` | Borderline: it refers back to "the Land Berlin" two lines earlier, in the same paragraph. If Task 7 glosses line 9, line 11 can stay as it is. |
| G7 | organisations/abgeordnetenhaus.yaml:42 | Hauptverkehrsstraßen | `berlin-radverkehrsplan-2021/not-in-table-3` | P. HIGH: the Berlin legal category differs from velometer "main roads". |
| G8 | plans/berlin.yaml:18 | Radverkehrsanlagen an Hauptverkehrsstraßen | **new** `berlin-fortschrittsbericht-2021/main-road-facilities` | P. The sentence already cites this source. |
| G9 | organisations/senmvku.yaml:22,39; organisations/abgeordnetenhaus.yaml:20 | Streckenlänge | `berlin-radfortschrittsbericht-page/streckenlaenge` | P. The inventory's other G9 lines (plans/berlin.yaml, explainer.yaml, narratives/berlin.yaml, narratives/combined.yaml) no longer contain "route length" at d609ebc. Task 7 should re-grep them. |
| G13 | organisations/abgeordnetenhaus.yaml:20 | planerisches Zielnetz | `berlin-drs-19-25987/vorrangnetz-target` | P |
| G13 (Changing Cities) | organisations/changing_cities.yaml:18-19 (scope), 29-30 (paragraph, "Its target network of 2,699.8 km") | Berliner Radnetz (bis 2030) | `berlin-changing-cities-monitor/target-network` ("2.699,8 Kilometer: So lang soll das Berliner Radnetz bis 2030 sein.") | P. This is the NGO monitor's own target figure, not the Senate's Zielnetz, and its source never says "Zielnetz". Task 7 must not attach "Zielnetz" here; the only source term is "Berliner Radnetz". |
| A1 | narratives/vienna.yaml:29-30; organisations/mobilitaetsagentur_wien.yaml:20,27,31-32 | Hauptradverkehrsnetz | `vienna-radwegeausbau-bilanz-2025/started-not-completed` | P |
| A2 | narratives/vienna.yaml:27-28 | Radfahren gegen die Einbahn; Verkehrsberuhigter Bereich; Radroute | `vienna-radverkehrsnetz-fakten/types-mixed`, `vienna-radverkehrsnetz-fakten/types-calmed` | P |
| PL1 | narratives/warsaw.yaml:22; narratives/wroclaw.yaml:20 | gmina (GUS: "Nazwa angielska: Gmina") | **new** `gus-pojecie-gmina/definition` | O. Statistics Poland's official English name for the unit is "Gmina", left untranslated. The German twins also leave "construction"/"cycleway" in English (inventory note). |
| PL3 | narratives/warsaw.yaml:29-30 | pasów i kontrapasów | `warsaw-zdm-sezon-2018/composition-544km` | P |
| PL4 | narratives/krakow.yaml:27-28 | chodniki z dopuszczonym ruchem rowerowym; kontraruch rowerowy | `krakow-250km-2022/definition` | P |
| PL5 | narratives/wroclaw.yaml:27-28 | trasy „przyjazne rowerzystom”; kontrapasy; strefy uspokojonego ruchu | `wroclaw-wroclife-nik-2023/friendly-routes` | P |
| CZ1 | narratives/prague.yaml:33-35 | trasy / cyklotras | `prague-ipr-system-cyklotras-2021/routes-not-facilities` (also `/expansion-goal`: "základní sítě pražských cyklotras") | P. The inventory's "Systém celoměstských cyklotras" is in no excerpt. Use only the forms quoted here, or add an excerpt first. |
| SK1 | narratives/bratislava.yaml:32-33 | ochranných pruhov | `bratislava-city-infra-2025/breakdown-total` | German done in M12 ("Angebotsstreifen"). **English still needs work**: "advisory lanes" is P. The source has only the genitive plural "ochranných pruhov". |
| HU1 | narratives/budapest.yaml:32 | fővárosi kezelésű kerékpárútszakasz / kerékpársávszakasz | `budapest-bkk-kfht-helyzetertekeles-2022/city-managed-235km` | P |
| HU2 | narratives/budapest.yaml:32-33 | főhálózat | `budapest-bkk-kfht-helyzetertekeles-2022/main-network-800km` | P |
| SI1 | narratives/ljubljana.yaml:32-33 | kolesarskih pasov na pločniku ali vozišču, ločenih kolesarskih stez ter skupnih poti za pešce in kolesarje | `ljubljana-mol-hoja-in-kolesarjenje/over-350km` | P |

Every in-scope hit has an excerpt; none is "none found".

## Checks

- `uv run velometer content --check`: `ok`.
- The online check, run on the new sources only, uses the project's own `check_online` function
  and its own fetcher. It returns no problems for all 12 new excerpts on the 10 new HTML
  sources.
- `uv run velometer content --check --online` over the whole registry fails, as it did at
  baseline. The failures were already there before this task. Every excerpt from a PDF source
  fails because the checker reads `resp.text` and never extracts text from a PDF; 143 such
  lines appeared at baseline. grandlyon.com also times out. The run after this task adds exactly
  one line, `berlin-fortschrittsbericht-2021: excerpt not found online: main-road-facilities`,
  from the PDF excerpt for G8. I checked that excerpt against `pdftotext -layout` output of the
  same PDF, normalised with the checker's own `_squash`: it is found. So is the existing
  `halved` excerpt.
