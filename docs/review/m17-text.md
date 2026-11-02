# M17 reader-facing text for review

Every new reader-facing sentence of M17, en and de, collected for the user's review (plan Task 5
step 6, spec §4.8 settled 6). Nothing here ships before that review.

## Terms registry and glossary (Task 13)

### Inventory

Taken from the rendered static export of the real data (`velometer app export`, build 1289b08,
2026-11-02, 799 files), not from the sources: the text of `<main>` on every HTML page, outside
`script`, `style`, `svg`, `code`, `pre` and `template`, searched for upper-case tokens and `X+Y`
forms. Count = occurrences, pages = pages that show it (both editions).

Registered (spec §4.8 list, plus the tier sums and spellings the export shows):

| Short form | Occurrences | Pages | Note |
|---|---:|---:|---|
| OSM | 2,616 | 201 | |
| LAU | 1,971 | 199 | also in compounds: `LAU-Polygon`, `GISCO-LAU` |
| QECIO | 1,909 | 99 | |
| A+B | 1,668 | 201 | also `A+B-km` (de) |
| FUA | 1,244 | 191 | |
| NUTS3 | 353 | 51 | spellings `NUTS-3` (22, de) and `NUTS 3` (6, quotes and tables) registered as forms |
| A+B+C+D | 131 | 89 | the QECIO tiers; not in the spec's list, found in the export |
| A+B+E | 42 | 42 | comparison basis for BikeNetKit |
| C+D | 42 | 42 | comparison with QECIO's cycle lanes; not in the spec's list, found in the export |
| COROP | 4 | 2 | Amsterdam; the `<i lang="nl">COROP-gebied</i>` mark is skipped, the plain use is marked |
| tier letters A–E | — | — | counted only after the word for tier: "tier A", "tiers A–E", "Stufe B", "Stufen C+D" (the sum wins there) |

Not terms (left plain):

- File formats and technical names: CSV (196), PDF (288), PNG (84), MD5 (21), URL, API, WFS,
  HTTP, README, UTC, EPSG (3, in "EPSG:25833").
- Country codes (DE, PL, GB, IT, ES, FR, NL, AT, CZ, DK, FI, HU, NO, SE, SI, SK, EU) and region
  codes (FR101, DE300, NL329, ES511, …).
- Names of organisations and datasets, spelled out where they appear: ECF (1,137 on 53 pages),
  GISCO, INSEE, INE, CBS, KSH, GUS, SCB, BKK, ADFC, BUND, NDW, ZDM, BCN, CONEBI, BOE.
- Internal references: ADR (94), milestones and rulings (M1–M13, R8–R19), roman numerals.
- Street and counter names in capitals (Barcelona's counter list: GRAN VIA, DIAGONAL, MERIDIANA,
  …), and other words in capitals (COVID, MTB, NERDS, GISRUK).

For the user to decide: ECF is the most frequent unregistered abbreviation. It is an
organisation's name and is spelled out on the sources and organisation pages, so it is left out
for now; adding it would be one registry entry.

### UI strings (glossary heading and lead)

| Key | en | de |
|---|---|---|
| `page.methodology.terms` | Terms and abbreviations | Begriffe und Abkürzungen |
| `page.methodology.terms_lead` | The abbreviations and tier letters the pages use. On each page, the first use of each one links here. | Die Abkürzungen und Stufenbuchstaben, die die Seiten verwenden. Auf jeder Seite führt die erste Verwendung jeder Abkürzung hierher. |

### Expansions and explanations (`content/terms.yaml`)

The tier letters' expansions are the existing tier labels (`tier.A` … `tier.E` without their
letter), so they are not new text. Every other expansion and every explanation is new.

#### Tier A
- en: A cycle track: beside the road (`cycleway=track`), a cycleway not tagged as open to
  pedestrians, or a path where walking and cycling have separate parts (`segregated=yes`). Tier A
  counts in the headline, A+B.
- de: Ein baulich getrennter Radweg: neben der Fahrbahn (`cycleway=track`), ein Radweg, der nicht
  als für den Fußverkehr offen erfasst ist, oder ein Weg mit getrennten Teilen für Fuß- und
  Radverkehr (`segregated=yes`). Stufe A zählt zur Hauptkennzahl A+B.

#### Tier B
- en: A path shared with pedestrians, without separate parts, such as a cycleway or path for
  cycling that people may also walk on, a pavement designated for cycling, or a track tagged
  `cycleway:segregated=no`. Tier B counts in the headline, A+B.
- de: Ein Weg, den Rad- und Fußverkehr ohne getrennte Teile teilen, etwa ein Radweg oder Weg für
  den Radverkehr, der auch zu Fuß benutzt werden darf, ein für den Radverkehr bestimmter Gehweg
  oder ein Radweg mit `cycleway:segregated=no`. Stufe B zählt zur Hauptkennzahl A+B.

Note for the user: docs/methodology.md (and .de.md) still say a designated foot-and-cycle path
with `segregated=yes` is tier B. Classifier v4 (`A_segregated`) and the v4 amendment in ADR 0002
make it tier A; the glossary follows v4. The generated methodology prose is stale on this point.

#### Tier C
- en: A cycle lane physically buffered from motor traffic. Tier C is measured but not counted in
  the headline.
- de: Ein Radfahrstreifen mit baulicher Trennung zum Kfz-Verkehr. Stufe C wird gemessen, zählt
  aber nicht zur Hauptkennzahl.

#### Tier D
- en: A painted lane, including advisory lanes. Tier D is measured but not counted in the
  headline.
- de: Ein markierter Radfahrstreifen, einschließlich Schutzstreifen. Stufe D wird gemessen, zählt
  aber nicht zur Hauptkennzahl.

#### Tier E
- en: A cycle street, or a bus lane open to cyclists. Tier E is measured but not counted in the
  headline.
- de: Eine Fahrradstraße oder vergleichbare Straße, oder eine für den Radverkehr freigegebene
  Busspur. Stufe E wird gemessen, zählt aber nicht zur Hauptkennzahl.

#### A+B
- expansion en: tiers A and B: separated tracks and shared foot and cycle paths
- expansion de: Stufen A und B: baulich getrennte Radwege sowie Geh- und Radwege
- en: The headline: the length of tiers A and B, per road side, per 100 km of main roads
  excluding motorways. Lanes (C and D) and cycle streets and bus lanes (E) are measured but left
  out of it.
- de: Die Hauptkennzahl: die Länge der Stufen A und B, je Straßenseite, je 100 km
  Hauptverkehrsstraßen ohne Autobahnen. Radfahrstreifen (C und D) sowie Fahrradstraßen und
  Busspuren (E) werden gemessen, gehen aber nicht in sie ein.

#### A+B+E
- expansion en: tiers A, B and E, with cycle streets and bus lanes
- expansion de: Stufen A, B und E, mit Fahrradstraßen und Busspuren
- en: A comparison basis only, for sources that include cycle streets, such as BikeNetKit's
  bicycle network. It is not our headline.
- de: Nur eine Vergleichsbasis, für Quellen, die Fahrradstraßen mitzählen, etwa das Radnetz von
  BikeNetKit. Sie ist nicht unsere Hauptkennzahl.

#### A+B+C+D
- expansion en: tiers A to D, with protected and painted lanes
- expansion de: Stufen A bis D, mit geschützten und markierten Radfahrstreifen
- en: The tiers QECIO counts. The `ecf_qecio` preset sums them on the QECIO basis, where one-way
  infrastructure counts half, and divides by main roads including motorways. It is a comparison,
  not our headline.
- de: Die Stufen, die QECIO zählt. Die Kennzahlvariante `ecf_qecio` summiert sie auf der
  QECIO-Basis, auf der Anlagen für nur eine Fahrtrichtung zur Hälfte zählen, und bezieht sie auf
  die Hauptverkehrsstraßen einschließlich Autobahnen. Sie dient dem Vergleich und ist nicht
  unsere Hauptkennzahl.

#### C+D
- expansion en: tiers C and D: protected and painted lanes
- expansion de: Stufen C und D: geschützte und markierte Radfahrstreifen
- en: Cycle lanes on the road, physically buffered (C) or painted (D). We compare them with
  QECIO's cycle lanes; they are not in the headline.
- de: Radfahrstreifen auf der Fahrbahn, baulich abgetrennt (C) oder markiert (D). Wir vergleichen
  sie mit den Radfahrstreifen von QECIO; zur Hauptkennzahl zählen sie nicht.

#### OSM
- expansion en/de: OpenStreetMap
- en: The open map every velometer figure is measured from. Its km are mapped km: what is mapped
  in OpenStreetMap at the snapshot date, not what was built.
- de: Die offene Karte, aus der jede Zahl von velometer gemessen wird. Ihre km sind kartierte km:
  was zum Stichtag in OpenStreetMap erfasst ist, nicht, was gebaut wurde.

#### LAU
- expansion en: local administrative unit, the city proper
- expansion de: lokale Verwaltungseinheit, die Kernstadt
- en: The city boundary of the headline: the Eurostat GISCO local administrative unit of 2024.
  Where a city has no clean LAU polygon, the OpenStreetMap administrative relation replaces it.
- de: Die Stadtgrenze der Hauptkennzahl: die lokale Verwaltungseinheit (<i lang="en">local
  administrative unit</i>) von Eurostat GISCO, Stand 2024. Fehlt ein sauberes LAU-Polygon, tritt
  die administrative Relation aus OpenStreetMap an seine Stelle.

#### FUA
- expansion en: functional urban area, the city with its commuting zone
- expansion de: funktionaler Stadtraum, die Stadt mit ihrem Pendlereinzugsgebiet
- en: A robustness check beside the city proper. Results are only compared within the same
  boundary kind, and the FUA has no population, so no per-100k figure.
- de: Der funktionale Stadtraum (<i lang="en">functional urban area</i>) dient als
  Robustheitsprüfung neben der Kernstadt. Verglichen wird nur innerhalb derselben Grenzart, und
  für den FUA gibt es keine Einwohnerzahl, also keinen Wert je 100.000 Einwohner.

#### QECIO
- expansion en/de: Quantifying Europe's Cycling Infrastructure using OSM (the source's own title,
  `qecio-methodology`; on German pages in `lang="en"`)
- en: The European Cyclists' Federation's (ECF) measure of cycling infrastructure from
  OpenStreetMap, here version 2.10. Our tiers derive from its tag logic, with documented
  differences, and the `ecf_qecio` preset follows its definition on our data. QECIO reports by
  NUTS3 region. [cites qecio-methodology]
- de: Das Maß der <span lang="en">European Cyclists' Federation</span> (ECF) für Radinfrastruktur aus OpenStreetMap,
  hier in Version 2.10. Unsere Stufen leiten sich aus seiner Tag-Logik ab, mit dokumentierten
  Abweichungen, und die Kennzahlvariante `ecf_qecio` bildet seine Definition mit unseren Daten
  nach. QECIO berichtet je NUTS-3-Region. [zitiert qecio-methodology]

#### NUTS3
- expansion en: Nomenclature of territorial units for statistics, level 3 (the source's
  wording, `qecio-methodology/nuts3`)
- expansion de: Systematik der Gebietseinheiten für die Statistik, Ebene 3 (the excerpt's
  `gloss_de`)
- en: Regions at the third level of this statistical classification. QECIO gathers its data per
  NUTS3 region and clips each way at the region's boundary, so where the region is larger than
  the city, its figures describe another area. [cites qecio-methodology]
- de: Regionen der dritten Ebene dieser statistischen Gliederung. QECIO erhebt seine Daten je
  NUTS-3-Region und schneidet jeden Weg an deren Grenze ab; ist die Region größer als die Stadt,
  beschreiben seine Zahlen ein anderes Gebiet. [zitiert qecio-methodology]

#### COROP
- expansion en: Dutch regional level between municipalities and provinces (from
  `cbs-regionale-economie-2018-begrippen/corop-level`; the source does not spell out the
  letters, so neither do we)
- expansion de: niederländische regionale Ebene zwischen Gemeinden und Provinzen
- en: A regional level of the Netherlands, between municipalities and provinces. QECIO reports
  Amsterdam for the COROP region Groot-Amsterdam, which is larger than the city. [cites
  cbs-regionale-economie-2018-begrippen]
- de: Eine regionale Ebene der Niederlande zwischen Gemeinden und Provinzen. QECIO berichtet für
  Amsterdam die COROP-Region Groot-Amsterdam, die größer ist als die Stadt. [zitiert
  cbs-regionale-economie-2018-begrippen]

## Tier diagrams (Task 14)

Five drawn street cross-sections, one per tier, in `src/velometer/app/templates/_tier_diagram.html`
(spec §4.8; the geometry is the builder's proposal, settled 5). The methodology glossary shows each
tier's diagram in its entry, with one note above the entries that the classifier rules decide.
Tasks 15 and 16 reuse the same partial. Captions restate the methodology and change no
definition. The headline sentence ("counts" or "measured, not in the headline") is chosen from the
headline preset in `config/presets.yaml`, not written per tier.

### What each drawing shows

Seen along the street, building side on the left, about 24 units to the metre with kerbs drawn
higher than they are. Each one has the footway, the cycle facility in its tier's chart colour, and
the road with a car.

- **A:** the footway, then the track one step lower, a raised verge, and the road with the car.
- **B:** one raised surface in the tier colour with a person walking and a person cycling on it,
  then a verge and the road.
- **C:** the footway, then the lane at road level, a low kerb separator with a bollard, and the
  traffic lane.
- **D:** the footway, then the lane at road level, a painted line, and the car right next to it.
- **E:** two panels. On the left, a cycle street: its whole carriageway is in the tier colour, two
  people cycle side by side, a car follows, and a sign with a bicycle stands on the footway. On the
  right, a bus lane in the tier colour with a person cycling and a bus, beside a general lane with
  a car.

### Screenshots

These show the methodology glossary's tier entries from the local app on the real database.

| | light | dark |
|---|---|---|
| en, 1280 px | [png](m17-diagrams/glossary-en-light-1280.png) | [png](m17-diagrams/glossary-en-dark-1280.png) |
| en, 390 px | [png](m17-diagrams/glossary-en-light-390.png) | [png](m17-diagrams/glossary-en-dark-390.png) |
| de, 1280 px | [png](m17-diagrams/glossary-de-light-1280.png) | [png](m17-diagrams/glossary-de-dark-1280.png) |
| de, 390 px | [png](m17-diagrams/glossary-de-light-390.png) | [png](m17-diagrams/glossary-de-dark-390.png) |

### UI strings

| Key | en | de |
|---|---|---|
| `tier.diagram_name.A` | Cross-section, tier A: separated track | Querschnitt, Stufe A: baulich getrennter Radweg |
| `tier.diagram_name.B` | Cross-section, tier B: shared foot/cycle path | Querschnitt, Stufe B: Geh- und Radweg |
| `tier.diagram_name.C` | Cross-section, tier C: protected lane | Querschnitt, Stufe C: geschützter Radfahrstreifen |
| `tier.diagram_name.D` | Cross-section, tier D: painted lane | Querschnitt, Stufe D: markierter Radfahrstreifen |
| `tier.diagram_name.E` | Cross-section, tier E: cycle street and bus lane | Querschnitt, Stufe E: Fahrradstraße und Busspur |
| `tier.caption.A` | A cycle track between the footway and the road, set apart from both by a kerb or a change in level. | Ein Radweg zwischen Gehweg und Fahrbahn, von beiden durch einen Bordstein oder einen Höhenunterschied getrennt. |
| `tier.caption.B` | One path for walking and cycling, without separate parts, apart from the road. | Ein gemeinsamer Weg für Fuß- und Radverkehr ohne getrennte Teile, abseits der Fahrbahn. |
| `tier.caption.C` | A cycle lane on the road, with bollards or a kerb separator between it and the traffic. | Ein Radfahrstreifen auf der Fahrbahn, durch Poller oder eine Trennschwelle vom Verkehr getrennt. |
| `tier.caption.D` | A cycle lane or advisory lane on the road, with only a painted line between it and the traffic. | Ein Radfahrstreifen oder Schutzstreifen auf der Fahrbahn, nur durch eine markierte Linie vom Verkehr getrennt. |
| `tier.caption.E` | Left, a cycle street, a street signed for cycling; right, a bus lane open to cyclists. | Links eine Fahrradstraße, eine für den Radverkehr ausgewiesene Straße; rechts eine für den Radverkehr freigegebene Busspur. |
| `tier.diagram_counts` | Counts in the headline. | Zählt zur Hauptkennzahl. |
| `tier.diagram_measured` | Measured, not in the headline. | Gemessen, nicht in der Hauptkennzahl. |
| `tier.diagram_rules` | A typical case is drawn; the [classifier rules] decide which tier each street side or path gets. | Gezeichnet ist der typische Fall; welche Stufe eine Straßenseite oder ein Weg erhält, entscheiden die [Regeln des Klassifikators]. |

The name is the drawing's accessible name and the caption's bold start. The link in
`tier.diagram_rules` goes to the methodology's "Classification rules" section. The German texts
use no English term, so they carry no `lang` mark.

For the user to decide:

- The geometry: proportions, the A track one step below the footway, and C drawn with one bollard
  on a kerb separator.
- Whether the glossary should show each diagram in its tier entry (as built), or the row of five
  (`tier_diagrams()`) above the entries.

## Home lead (Task 15)

A lead section on the home page, between the dek and the definition box, above the ranking
(spec §4.8, third person). It replaces nothing: the h1, dek, definition and key facts stay where
they were. Its last sentence is the §4.2 home sentence, computed from the ranking the home table
shows (`ranking_ends` in `src/velometer/app/main.py`); with fewer than two ranked cities it is left
out. Strings: `page.index.lead.*` in `content/ui/en.yaml` and `content/ui/de.yaml`. Below as
rendered on the real data (links in brackets: where they go).

### English (155 words)

> velometer is an open, independent comparison of cycling infrastructure in 21 European cities,
> built from OpenStreetMap. It answers one question: how much of a city's main road network has a
> cycle path you don't share with cars? It counts [separated tracks](/methodology#term-tier-a) and
> [shared foot/cycle paths](/methodology#term-tier-b), both apart from the road. Cycle lanes on the
> road don't count, whether painted or protected. Together, the two counted types are called A+B
> here. All lengths are **mapped km**: what mappers recorded in OpenStreetMap, not what was built.
> A city's figure can change when the mapping catches up.
>
> Here a reader can see the [ranking](#ranking), read [a city's story](/cities) or [the stories
> across all cities](/stories), [compare cities](/compare) and [check the method](/methodology).
> The [Zählwerk Berlin Datalab](https://zaehlwerk-datalab.de/) maintains velometer. Its
> [code](https://github.com/senzelden/velometer) and [data](/data/all.csv) are open. In the current
> run, Helsinki has the highest headline value, 262.3 A+B km per 100 km of main roads (excl.
> motorways), and Budapest the lowest, 22.3.

### German (149 words)

> velometer ist ein offener, unabhängiger Vergleich der Radinfrastruktur in 21 europäischen
> Städten, erstellt aus OpenStreetMap. Er beantwortet eine Frage: Wie viel vom Hauptstraßennetz
> einer Stadt hat einen Radweg, den man nicht mit Autos teilt? Gezählt werden [baulich getrennte
> Radwege](/de/methodology#term-tier-a) und [gemeinsame Geh- und Radwege](/de/methodology#term-tier-b),
> beide abseits der Fahrbahn. Radfahrstreifen auf der Fahrbahn zählen nicht, ob markiert oder
> geschützt. Die beiden gezählten Arten heißen hier zusammen A+B. Alle Längen sind **kartierte
> km**: was Kartierende in OpenStreetMap erfasst haben, nicht was gebaut wurde. Die Zahl einer Stadt
> kann sich ändern, wenn die Kartierung aufholt.
>
> Hier lässt sich die [Rangfolge](#ranking) ansehen, [die Geschichte einer Stadt](/de/cities) oder
> [die Geschichten über alle Städte](/de/stories) lesen, [Städte vergleichen](/de/compare) und
> [die Methode prüfen](/de/methodology). Das [Zählwerk Berlin Datalab](https://zaehlwerk-datalab.de/)
> betreut velometer. [Code](https://github.com/senzelden/velometer) und [Daten](/data/all.csv) von
> velometer sind offen. Im aktuellen Lauf hat Helsinki die höchste Hauptkennzahl, 262,3 A+B-km je
> 100 km Hauptstraßen (ohne Autobahnen), und Budapest die niedrigste, 22,3.

City names, values and the city count come from the data; the rest is fixed text. The first
`A+B` gets the glossary link from the first-use wrapper (Task 13).

### Builder's calls, for review

- **Links, not diagrams, beside "what counts".** Both rendered at 390 px
  (`m17-home/home-diag-{en,de}-light-390.png` shows the diagram variant). The two figures add
  about 390 px, split the lead in two and push the ranking a further screen down; the links keep
  the lead one read and lead to the glossary entries, which show the same diagrams.
- **Placement:** after the dek, before the definition box. The h1 and dek stay the page's head;
  the definition box then restates the short form the lead has just introduced.
- **"painted or protected":** the spec's list says "painted lanes don't". Tier C (protected lanes)
  doesn't count either, so the lead names both, to avoid suggesting that protected lanes count.
- **The home sentence's measure** is the headline unit as the site names it ("A+B km per 100 km of
  main roads (excl. motorways)"), with the top city's value in full and the bottom's as a number.
- With a tie at the top or bottom (not the case today), the table's order decides and the sentence
  would read "highest … lowest" with equal values.

### Renders

Top of the home page down to the ranking's third row, real data, public site values:

- `m17-home/home-{en,de}-{light,dark}-390.png`
- `m17-home/home-{en,de}-{light,dark}-1280.png`
- `m17-home/home-diag-{en,de}-light-390.png` (the rejected diagram variant)

![en, light, 390](m17-home/home-en-light-390.png)
![de, dark, 1280](m17-home/home-de-dark-1280.png)

## City story as one scroll on phones (Task 16)

Below the 62rem breakpoint, `/city/<id>` now reads top to bottom (spec §4.8): the head and key
numbers, the tab bar (kept as a link row), the narrative, the headline chart (the aside box, as
before), then three new `.phone-only` blocks:

1. **Road types:** the tier composition of the latest snapshot (LAU, the headline boundary) as
   one stacked column, its table and Cite, the five tier diagrams with their captions, and a link
   to the tier map on the Tiers tab.
2. **Tier composition over time (LAU):** the Tiers tab's chart, with its table and Cite.
3. **More on {city}:** a link to every other tab the city has (Bezirke and Counts only where
   present).

The "Read on" box stays last. The blocks are hidden at 62rem and wider, so the desktop page is
unchanged: the 1280 px renders before and after are pixel-identical. Their charts draw only when
a phone shows them, from the same `/data/series.json` the tab pages use; the tier map is linked,
never embedded.

### UI strings

| Key | en | de |
|---|---|---|
| `page.story.road_types` | Road types | Radwegtypen |
| `page.story.more` | More on {city} | Mehr zu {city} |
| `js.chart.tiers_now_of` (the column chart's accessible name) | Stacked column: mapped km by tier, {where}, {label} | Gestapelte Säule: kartierte km nach Stufe, {where}, {label} |

Everything else on the blocks reuses reviewed strings: "Tiers, mapped km now", "Tier composition
over time ({kind})", "Table: mapped km by tier ({kind})", "Tier map" and the tab names.

### Builder's calls, for review

- **"Over time" is the tier composition over time,** not the headline over time. The headline
  over time is already the chart just above (the aside box); showing it twice would repeat it.
  The Over time tab's flagged years stay one link away.
- **A plain stacked scroll,** not the `/stories` sticky pattern: each block is a box like the
  headline box, so the page reads as one column of cards.
- **The latest snapshot as one full-width column.** The tier chart's code draws it (one label:
  a stacked column instead of an area), so colours, legend, tooltip and download are the same.
- **German heading "Radwegtypen":** E (Fahrradstraße, Busspur) is not strictly a Radweg; an
  alternative is "Arten von Radinfrastruktur".

### Renders

Real data, local app (`public=True`), headless Chrome at 390 px scrolled to the bottom so every
chart is drawn, then shot from the top; split into parts. Ljubljana is the small city without
Bezirke (and without counter data).

| | parts |
|---|---|
| Berlin, en, light, 390 | [1](m17-city/berlin-en-light-390-1.png) · [2](m17-city/berlin-en-light-390-2.png) · [3](m17-city/berlin-en-light-390-3.png) |
| Berlin, en, dark, 390 | [1](m17-city/berlin-en-dark-390-1.png) · [2](m17-city/berlin-en-dark-390-2.png) · [3](m17-city/berlin-en-dark-390-3.png) |
| Berlin, de, dark, 390 | [1](m17-city/berlin-de-dark-390-1.png) · [2](m17-city/berlin-de-dark-390-2.png) · [3](m17-city/berlin-de-dark-390-3.png) · [4](m17-city/berlin-de-dark-390-4.png) |
| Ljubljana, en, light, 390 | [1](m17-city/ljubljana-en-light-390-1.png) · [2](m17-city/ljubljana-en-light-390-2.png) · [3](m17-city/ljubljana-en-light-390-3.png) |
| Ljubljana, en, dark, 390 | [1](m17-city/ljubljana-en-dark-390-1.png) · [2](m17-city/ljubljana-en-dark-390-2.png) · [3](m17-city/ljubljana-en-dark-390-3.png) |
| Ljubljana, de, light, 390 | [1](m17-city/ljubljana-de-light-390-1.png) · [2](m17-city/ljubljana-de-light-390-2.png) · [3](m17-city/ljubljana-de-light-390-3.png) · [4](m17-city/ljubljana-de-light-390-4.png) |
| Berlin desktop, 1280, before / after | en light [before](m17-city/berlin-en-light-1280-before.png) / [after](m17-city/berlin-en-light-1280-after.png) · en dark [before](m17-city/berlin-en-dark-1280-before.png) / [after](m17-city/berlin-en-dark-1280-after.png) · de light [before](m17-city/berlin-de-light-1280-before.png) / [after](m17-city/berlin-de-light-1280-after.png) |

![Berlin, en, light, 390, part 2](m17-city/berlin-en-light-390-2.png)
![Berlin, en, light, 390, part 3](m17-city/berlin-en-light-390-3.png)
