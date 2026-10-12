# German glossary (velometer)

The terms of the German edition: every German UI string and every German content file uses
them. Built from `docs/methodology.de.md`, which wins where it is more specific; the cases
where a short UI form is used beside the methodology's longer one are listed under the table.

## Terms

| English | German | Note |
|---|---|---|
| **Methodology** | | |
| tier, tiers A–E | Stufe, Stufen A–E | "Stufe A", never "Tier A" |
| A separated track | A baulich getrennter Radweg | methodology tier table |
| B shared foot/cycle path | B Geh- und Radweg | long form: "Geh- und Radweg (gemeinsam oder getrennt)" |
| C protected lane | C geschützter Radfahrstreifen | long form: "Radfahrstreifen mit baulicher Trennung zum Kfz-Verkehr" |
| D painted lane | D markierter Radfahrstreifen | long form adds "einschließlich Schutzstreifen" |
| E cycle street / bus lane | E Fahrradstraße / Busspur | long form: "Fahrradstraße sowie für den Radverkehr freigegebene Busspuren" |
| mapped km | kartierte km, kartierte Kilometer | ADR 0006; never "gebaute" |
| not built km | keine gebauten km | only in the fixed formula "kartierte km, nicht gebaute km" |
| headline | Hauptkennzahl | the A+B per 100 km figure |
| metric | Kennzahl | generic; a Compare metric |
| preset | Kennzahlvariante | |
| length basis | Längenbasis | |
| per side | je Seite, je Straßenseite | |
| denominator, road class | Bezugsgröße, Straßenklasse | |
| main roads | Hauptstraßen | methodology long form: "Hauptverkehrsstraßen" |
| main roads (excl. motorways) | Hauptstraßen (ohne Autobahnen) | |
| all public roads | alle öffentlichen Straßen | |
| run | Lauf | |
| snapshot | Stand | yearly: "Jahresstand"; "aktueller Stand" for the current run |
| as of 1 January | Stand zum 1. Januar | short in tables: "Jan. 2024" |
| reference date | Stichtag | |
| classifier | Klassifikator | |
| flagged year | markiertes Jahr | the flag itself: "Prüfhinweis" |
| explanation | Erklärung | |
| provenance | Herkunft | |
| boundary | Gebietsgrenze, Grenze | |
| **Places and counters** | | |
| city proper (LAU) | Kernstadt (LAU) | methodology: "Stadtgrenze" for the LAU line itself |
| metro area (FUA) | Funktionaler Stadtraum (FUA) | methodology: "funktionaler Stadtraum (Functional Urban Area)" |
| Bezirk, Bezirke | Bezirk, Bezirke | Berlin's districts, the same word |
| subarea | Teilgebiet | |
| counter, counter site | Zählstelle | |
| counter index | Zählstellenindex | |
| counts | Zählwerte | |
| base year | Basisjahr | |
| index (first year = 100) | Index (erstes Jahr = 100) | |
| COVID year | Corona-Jahr | methodology |
| residents | Einwohner | |
| **Sources and actions** | | |
| published figure | veröffentlichte Zahl | |
| reported figure | gemeldete Zahl | a plan's progress figure |
| source | Quelle | |
| cite | Zitieren | the disclosure label |
| download | Herunterladen | |
| copy link | Link kopieren | |
| licence | Lizenz | |
| retrieved | abgerufen | |
| **Pages and tabs** | | |
| Overview | Überblick | |
| Compare | Vergleich | |
| Cities | Städte | |
| Stories | Geschichten | the page across all cities |
| Story (city tab) | Geschichte | |
| Over time | Zeitverlauf | |
| Figures (city tab) | Zahlen | |
| Counts (city tab) | Zählstellen | |
| Plans | Pläne | |
| Organisations | Organisationen | |
| Sources | Quellen | |
| Methodology | Methodik | |
| Why the figures differ | Warum die Zahlen abweichen | |

## Style rules

- Neutral, journalistic German. No direct address: no "Sie", no "du". Controls use the
  infinitive ("Link kopieren", "Filter anwenden").
- German number formats: `1.639,8`, `−3,2` (U+2212), `12,3 %` with a narrow no-break space
  (U+202F) before `%`. Dates in words on pages: "12. Oktober 2026"; month-year labels "Jan. 2026".
- Quotes are never translated. Markers (`[@source]`, `[#ref]`, `` `code` ``) stay byte for byte.
- For OSM figures "kartiert", never a construction verb: none of `gebaut`, `baute`, `bauten`,
  `errichtet`, `eröffnet`, `entfernt`, `zurückgebaut` outside quotes (the fixed formula
  "nicht gebaute km" is the one exception, in UI and map strings).
- Labels stay as short as the English where they sit in the nav, tabs and table headers (they
  must fit at 320 px).

## Where the UI and the methodology differ

- "main roads": the UI says "Hauptstraßen" (short, binding for M12); the methodology's running
  text says "Hauptverkehrsstraßen". Both name the same road classes.
- "city proper (LAU)": the UI says "Kernstadt (LAU)"; the methodology calls the LAU line the
  "Stadtgrenze". The methodology is unchanged.
- "headline": the spec's term list names "Kennzahl"; the methodology says "Hauptkennzahl" for the
  headline and "Kennzahl" generically. The methodology wins: "Hauptkennzahl".
