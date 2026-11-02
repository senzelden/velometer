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
