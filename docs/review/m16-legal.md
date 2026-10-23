This review is not legal advice. It is a builder's reading of primary sources, written so that a lawyer can check it quickly.

# M16 legal review (research part)

- Date: 2026-10-21. Every source below was read on that date.
- Scope: spec `docs/superpowers/specs/2026-10-21-velometer-m16-design.md` §4.1, §4.4 and §4.9 item 1.
- Setup reviewed: velometer and the Zählwerk Berlin Datalab main page, both on one Hetzner Cloud
  server in Germany behind Caddy, TLS from Let's Encrypt. Basemap: a self-hosted Protomaps PMTiles
  extract (Tasks 4 and 5), so `tile.openstreetmap.org` is treated as being removed. Statistics: Caddy
  JSON access logs with the client IP masked to IPv4 /24 and IPv6 /48, kept 14 days, read by
  GoAccess, countries optionally from DB-IP Lite Country. The Datalab page self-hosts Martian Mono
  and Public Sans.
- Operator: not decided. Private person, e.V. and company are all covered.
- State of the site: the M15 export at `data/scratch-m15/site` (793 files, 248 HTML pages). HEAD has
  only documentation commits since that export, so it shows what the code produces today.
- Verdicts (ruling P3): `ok` / `fix in M16` / `decision for the user` / `question for a lawyer`.
  A decided user decision gets ` (decided YYYY-MM-DD: …)` appended to its verdict line.

## How the sources were read

Each source was fetched on 2026-10-21. Statute pages were downloaded with `curl` and turned into
text, so the quotations are verbatim. Pages where WebFetch returned short quotes are marked
"(WebFetch)". Three primary sources could not be read the normal way:

- **EUR-Lex** answered every automated request (curl and WebFetch) with HTTP 202 and an empty body,
  a bot challenge. The GDPR and the two CJEU judgments were read instead from the EU Publications
  Office, which serves the same official text by CELEX number
  (`http://publications.europa.eu/resource/celex/32016R0679`, `…/62014CJ0582`, `…/62023CJ0413`,
  English XHTML).
- **MStV:** the Berlin portal (`gesetze.berlin.de`) returned only its title, because the text is
  rendered by script, and the Brandenburg portal (`bravors.brandenburg.de`) returned 503. The text
  was read from the official Saxon PDF (`https://recht.sachsen.de/vorschrift_gesamt/18790/45657.pdf`,
  "Fassung vom 01.07.2023"). The MStV is the same in every Land. That version still refers to "§§ 5
  und 6 des Telemediengesetzes" in § 18 Abs. 2. A search result (lxgesetze.de, not a primary source)
  says the current version refers to the DDG instead. **Not verified** from a primary source.
- **DSK, Orientierungshilfe Digitale Dienste**
  (`https://datenschutzkonferenz-online.de/media/oh/OH_Digitale_Dienste.pdf`) returned 403. It is
  not quoted anywhere below.

The CURIA site renders by script, so the judgments were taken from the Publications Office as
noted above.

## Contents (38 topics, one verdict each)

| § | Topic | Verdict |
|---|---|---|
| 1.1a | OSM credit on pages and interactive maps | ok |
| 1.1b | OSM licence notice in downloads (CSV, GeoJSON, PNG, JSON) | fix in M16 |
| 1.1c | ODbL share-alike and offering the derivative database (4.4, 4.6) | decision for the user |
| 1.2a | GISCO boundaries: the EuroGeographics credit | fix in M16 |
| 1.2b | GISCO boundaries: the non-commercial condition | decision for the user |
| 1.3 | Population: Eurostat, INSEE, INE | fix in M16 |
| 1.4a | Berlin counters (dl-de/zero-2.0) | ok |
| 1.4b | Paris counters (ODbL) | ok |
| 1.4c | Vienna, Helsinki, Madrid, Barcelona counters (CC BY 4.0) | fix in M16 |
| 1.4d | Oslo counters (NLOD) | ok |
| 1.5 | Berlin WFS layers (dl-de/zero-2.0) | ok |
| 1.6 | BikeNetKit | fix in M16 |
| 1.7 | Protomaps basemap | fix in M16 |
| 1.8 | protomaps-leaflet and Leaflet (code) | fix in M16 |
| 1.9 | Datalab fonts (OFL) | fix in M16 |
| 1.10 | DB-IP Lite Country | ok |
| 2.1 | Single comparison figures and the database right | question for a lawyer |
| 2.2 | Quotations (§ 51 UrhG) | ok |
| 2.3 | Plan documents: cited, not redistributed | ok |
| 3 | Statements of fact (press law) | decision for the user |
| 4.1 | Impressum: which rules apply, content per operator form | decision for the user |
| 4.2 | Verantwortlicher nach § 18 Abs. 2 MStV | decision for the user |
| 4.3 | Address, including a c/o service | question for a lawyer |
| 4.4 | Electronic contact | decision for the user |
| 4.5 | Where the Impressum lives | fix in M16 |
| 5.1 | Information under Art. 13 GDPR (Datenschutzerklärung) | fix in M16 |
| 5.2 | Legal basis for logs and statistics; the /24 judgement | ok |
| 5.3 | Masking in every Caddy log | fix in M16 |
| 5.4 | Retention: 14 days, in the logs and in the reports | fix in M16 |
| 5.5 | § 25 TDDDG (terminal equipment) | ok |
| 5.6 | Hetzner as processor (AVV) | decision for the user |
| 5.7 | Let's Encrypt | ok |
| 5.8 | Data subject rights and the supervisory authority | fix in M16 |
| 5.9 | No page loads anything from another host | fix in M16 |
| 6.1 | Accessibility (BFSG) | ok |
| 6.2 | OSM tile usage policy | ok |
| 6.3 | Names and marks of the organisations quoted | ok |
| 6.4 | Image rights on the Datalab page | ok |

Totals: ok 15, fix in M16 14, decision for the user 7, question for a lawyer 2.

## How the export was checked

Run from the repo root on 2026-10-21 (output pasted as printed):

```sh
S=data/scratch-m15/site
for p in "OpenStreetMap contributors" "openstreetmap.org/copyright" "EuroGeographics" "Eurostat" \
         "INSEE" "INE Revisión" "BikeNetKit" "dl-de-zero-2.0" "CC BY 4.0" "NLOD" "Ville de Paris" \
         "Protomaps" "tile.openstreetmap.org" "fonts.googleapis.com"; do
  printf '%-28s html=%-4s files=%s\n' "$p" "$(grep -rlF --include='*.html' "$p" $S | wc -l)" \
         "$(grep -rlF "$p" $S | wc -l)"
done
grep -lF 'OpenStreetMap' $S/maps/*_lau.geojson $S/maps/*_fua.geojson | wc -l   # tier GeoJSON with a credit
grep -lF 'opendatacommons.org' $S/data/*.csv | wc -l                          # CSV with the ODbL URI
grep -liE '^#.*(eurostat|insee|ine )' $S/data/*.csv | wc -l                   # CSV naming a population source
grep -rLF --include='*.html' "openstreetmap.org/copyright" $S                  # pages without the OSM link
```

```
html pages: 248
OpenStreetMap contributors   html=124  files=149
openstreetmap.org/copyright  html=206  files=206
EuroGeographics              html=0    files=0
Eurostat                     html=3    files=3
INSEE                        html=3    files=3
INE Revisión                 html=3    files=3
BikeNetKit                   html=51   files=53
dl-de-zero-2.0               html=7    files=8
CC BY 4.0                    html=11   files=12
NLOD                         html=5    files=6
Ville de Paris               html=25   files=26
Protomaps                    html=0    files=0
tile.openstreetmap.org       html=206  files=207
fonts.googleapis.com         html=0    files=0
tier GeoJSON with any attribution: 0 of 42
CSV with ODbL URI: 0 of 23
CSV naming a population source: 0
```

The 124 English pages say "OpenStreetMap contributors" and the 124 German pages say
"OpenStreetMap-Mitwirkende". The 42 pages without the copyright link are all `city/*/panel/` HTML
fragments, which are loaded into a page that has the footer.

---

## 1. Data licences, source by source

### 1.1a OSM credit on pages and interactive maps

*Rule.* ODbL 1.0 §4.3, https://opendatacommons.org/licenses/odbl/1-0/ (read 2026-10-21):
"if you Publicly Use a Produced Work, You must include a notice associated with the Produced Work
reasonably calculated to make any Person that uses, views, accesses, interacts with, or is otherwise
exposed to the Produced Work aware that Content was obtained from the Database, Derivative Database,
or the Database as part of a Collective Database, and that it is available under this License."
OSMF Attribution Guidelines, https://wiki.osmfoundation.org/wiki/Licence/Attribution_Guidelines
(read 2026-10-21): "Attribution must also make it clear that the data is available under the Open
Database License. This may be done by making the text “OpenStreetMap” a link to
openstreetmap.org/copyright" and "For a browsable map (e.g., embedded in a web page or application),
the credit should typically appear in a corner of the map."

*Our state.* Every full page has the footer credit `site.footer.attribution` ("Map data ©
OpenStreetMap contributors, ODbL 1.0", linked to openstreetmap.org/copyright;
`content/ui/en.yaml:13`). The three Leaflet maps put "© OpenStreetMap contributors", linked to the
copyright page, in the corner (`src/velometer/app/static/map.js:40`, `changemap.js:30`,
`countermap.js:22`). Figures carry the credit in their cite block (`content/ui/en.yaml:643`).

**Verdict:** ok

*Fix.* None. Task 5 must keep the corner credit when the tile layer changes (see 1.7).

### 1.1b OSM licence notice in downloads (CSV, GeoJSON, PNG, JSON)

*Rule.* ODbL 1.0 §4.2 (URL above): "If You Publicly Convey this Database, any Derivative Database, or
the Database as part of a Collective Database, then You must: … b. Include a copy of this License
(or, as applicable, a license permitted under Section 4.4) or its Uniform Resource Identifier (URI)
with the Database or Derivative Database, including both in the Database or Derivative Database and
in any relevant documentation; … d. If it is not possible to put the required notices in a particular
file due to its structure, then You must include the notices in a location (such as a relevant
directory) where users would be likely to look for it." OSMF Attribution Guidelines (URL above), for
static media: "The URL to openstreetmap.org/copyright must be printed out."

*Our state.*
- CSV (`data/*.csv`, 23 files): the preamble is
  `# Map data © OpenStreetMap contributors, ODbL 1.0 — OSM mapped km, not built km`
  (`src/velometer/report/csvexport.py:43`). It names the licence but gives no URI: 0 of 23 files
  contain `opendatacommons.org`.
- Tier-map GeoJSON (`maps/<city>_<lau|fua>.geojson`, 42 files): **no notice at all**. The
  FeatureCollection's `properties` hold only `run_id`, `osm_timestamp` and `classifier`
  (`src/velometer/report/maps.py:351-357`).
- Change-map GeoJSON: `"attribution": "Map data © OpenStreetMap contributors, ODbL 1.0"`, no URI
  (`src/velometer/report/change.py:679`).
- Tier-map PNGs: footer "Map data © OpenStreetMap contributors, ODbL 1.0 · …"
  (`content/ui/en.yaml:505`, `de.yaml:496`), with no printed URL.
- `data/series.json`: no notice.

**Verdict:** fix in M16

*Fix (Task 2).* One notice text for every download, carrying both URIs. Suggested:
`Map data © OpenStreetMap contributors (https://www.openstreetmap.org/copyright), ODbL 1.0
(https://opendatacommons.org/licenses/odbl/1-0/)`. It goes in the CSV preamble line, a top-level
`"attribution"` member in the tier-map and change-map FeatureCollections, `series.json`, and the PNG
footers of tier maps and charts (in the PNGs, at least the printed `openstreetmap.org/copyright`).
The German text uses the same URIs.

### 1.1c ODbL share-alike and offering the derivative database (4.4, 4.6)

*Rule.* ODbL 1.0 §4.4 a (URL above): "Any Derivative Database that You Publicly Use must be only
under the terms of: i. This License; ii. A later version of this License similar in spirit to this
License; or iii. A compatible license." §4.6: "If You Publicly Use a Derivative Database or a
Produced Work from a Derivative Database, You must also offer to recipients of the Derivative
Database or Produced Work a copy in a machine readable form of: a. The entire Derivative Database; or
b. A file containing all of the alterations made to the Database or the method of making the
alterations to the Database (such as an algorithm), including any additional Contents, that make up
all the differences between the Database and the Derivative Database." The copy must be "free of
charge if distributed over the internet."

*Our state.* ADR 0008 licenses the derived data under ODbL 1.0 (`docs/adr/0008-licences.md`), so
§4.4 is met. For §4.6, the site offers the per-city tier GeoJSON for the current snapshot and the
per-year km in CSV. The methodology page prints the full classifier rule table of v4, its parameters
and the length bases. The code is MIT, but the repository has no remote (`git remote -v` prints
nothing) and the site links to no source code. The yearly classified snapshots are not offered.

Whether the printed rules plus the GeoJSON already make "the method of making the alterations" is
arguable. Publishing the repository settles §4.6(b) without argument.

**Verdict:** decision for the user (decided 2026-10-23: publish the repository, MIT code and classifier rules, on a public remote and link it from the methodology page; the lede stays)

*Fix.* The user chooses one of: (A) publish the repository (MIT code, `config/classifier/*.yaml`)
and link it from the methodology page (recommended); (B) offer the classified way data per snapshot
as a download; (C) rely on the methodology rule table and the GeoJSON, and ask a lawyer (see
"Questions for a lawyer", Q1).

### 1.2a GISCO boundaries: the EuroGeographics credit

*Rule.* Eurostat GISCO, statistical units, "Copyright information",
https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units (read 2026-10-21; the geodata page
https://ec.europa.eu/eurostat/web/gisco/geodata says "there are specific rules that apply to some of
the following datasets … See our administrative units and statistical units for more details"):
"the source will be acknowledged. A copyright notice, as specified below, must be visible on any
printed or electronic publication using the data downloaded from this page." For "local
administrative units (LAU)" and "cities and functional urban areas": "In any printed or electronic
publication, in addition to any other rules that apply to the Eurostat website, the data source must
be acknowledged in the legend of the map and in the introductory page of the publication with the
following copyright notice: EN: © EuroGeographics for the administrative boundaries … DE: ©
EuroGeographics bezüglich der Verwaltungsgrenzen". And: "For publications in languages other than
English, French or German, the translation of the copyright notice in the language of the
publication must be used."

*Our state.* The tier maps draw the GISCO LAU or FUA outline (the `boundary` member of each map's
GeoJSON; `src/velometer/report/maps.py:357`), and every city figure is computed on a GISCO boundary.
"EuroGeographics" appears in 0 exported files. The methodology page names "Eurostat GISCO LAU 2024
(1:1M)" as a source but gives no copyright notice. The credit exists only in
`docs/review/m2_results.md:91`. ADR 0008 does not mention GISCO.

The tier-map GeoJSON also puts the GISCO outline inside a file that is licensed as ODbL. ODbL §4.4 d:
"You must not add Contents to Derivative Databases under Section 4.4 a that are incompatible with the
rights granted under this License." GISCO data may not be used commercially (1.2b), and ODbL allows
commercial use. The way out is ODbL §4.5 a: "You are not required to license Collective Databases
under this License if You incorporate this Database or a Derivative Database in the collection". So
the file must say that the `boundary` member is GISCO data under GISCO's terms and not under ODbL.

**Verdict:** fix in M16

*Fix (Task 2, kept by Task 5 per ruling P1).* Use the exact notice. EN: `© EuroGeographics for the
administrative boundaries`; DE: `© EuroGeographics bezüglich der Verwaltungsgrenzen`. **The plan's
German key value "© EuroGeographics für die Verwaltungsgrenzen" is not the prescribed wording and
must be replaced by the GISCO text.** Put it:
- in the tier-map attribution (`map.attributionControl.addAttribution`, ruling P1);
- in the site footer beside the OSM credit, which meets "the introductory page of the publication",
  since the footer is on the home page and on every page;
- in the tier-map PNG footer;
- in the tier-map GeoJSON, as the attribution plus a note that the `boundary` member is Eurostat
  GISCO data © EuroGeographics under GISCO's terms, not ODbL;
- in the CSV preamble, since every figure is computed on these boundaries;
- in the methodology/sources credit block.

ADR 0008 gains GISCO, with the non-commercial condition.

### 1.2b GISCO boundaries: the non-commercial condition

*Rule.* Same page: "The permission to use the data is granted on condition that: the data will not
be used for commercial purposes" and "If you intend to use the data commercially, please contact
EuroGeographics for information about their licence agreements."

*Our state.* velometer is free, has no ads and sells nothing. The operator form is open. A company
operator, or any later paid offer, could count as commercial use. The term is not defined on the page.

**Verdict:** decision for the user (decided 2026-10-23: velometer and the Datalab stay non-commercial: no ads, no paid service, no sale of data)

*Fix.* The user confirms that velometer and the Datalab stay non-commercial (no ads, no paid
service, no sale of data). If a company operates the site, or anything commercial is planned, ask
EuroGeographics for a licence or a lawyer (Q2) first. The fallback is to use OSM administrative
boundaries, which the pipeline already supports (`admin_boundary: osm_relation`). That changes stored
numbers and is out of scope for M16.

### 1.3 Population: Eurostat, INSEE, INE

*Rule.*
- Eurostat copyright notice, https://ec.europa.eu/eurostat/web/main/help/copyright-notice (read
  2026-10-21): "Reuse of statistical data, metadata, publications, and other dissemination tools
  published on this website for commercial or non-commercial purposes is authorised provided the
  source is acknowledged." And: "When reuse involves translations of publications or modifications to
  the data or text, this must be stated clearly to the end user of the information. A disclaimer
  regarding the non-responsibility of Eurostat shall be included."
- INSEE, Mentions légales, https://insee.fr/fr/information/2008466 (read 2026-10-21, WebFetch; the
  page says "Dernière mise à jour le : 13/04/2026"): the data are under the Licence Ouverte 2.0;
  "Cette licence autorise la réutilisation libre, y compris à des fins commerciales" "sous réserve de
  mentionner la source sous la forme « Source : Insee »" and "de mentionner la date de dernière mise à
  jour des données lorsque celle-ci est connue".
- INE, Aviso legal, https://ine.es/dyngs/AYU/es/index.htm?cid=125 (read 2026-10-21, WebFetch): "La
  licencia de uso general a aplicar a la información estadística de este sitio web" "es la Creative
  Commons Reconocimiento 4.0 (CC BY 4.0)"; source wording "Fuente: Sitio web del INE: www.ine.es"
  without processing, or "Elaboración propia con datos extraídos del sitio web del INE: www.ine.es"
  with processing.

*Our state.* Population comes from GISCO LAU 2024 `POP_2024`, Eurostat `demo_r_pjangrp3`, and the
overrides for Lyon, Strasbourg, Bordeaux (INSEE) and Madrid, Barcelona (INE) (`config/cities.yaml`,
header lines 38-53 and the `population_override` blocks). The methodology page's table names each
city's population source, with URL for INSEE and INE (3 pages per term). The CSVs carry
`population_value` and the derived km per 100,000 residents, but 0 of 23 CSVs name a population
source. The site shows no Eurostat non-responsibility line, although we derive per-capita figures.

**Verdict:** fix in M16

*Fix (Task 2).*
- The CSV preamble names the population source of the rows it holds, not only "Eurostat". For
  example: `# Population: Eurostat (GISCO LAU 2024, demo_r_pjangrp3); FR: Source : Insee, populations
  de référence 2023; ES: Elaboración propia con datos extraídos del sitio web del INE: www.ine.es`.
  Per-city files list only their own source.
- The methodology/sources credit block adds: "Per-capita figures are computed by velometer; Eurostat,
  INSEE and INE bear no responsibility for them."
- The plan's single line `# Boundaries © EuroGeographics; population: Eurostat` is wrong for the five
  FR/ES cities.

### 1.4a Berlin counters (dl-de/zero-2.0)

*Rule.* Datenlizenz Deutschland – Zero – Version 2.0, https://www.govdata.de/dl-de/zero-2-0 (read
2026-10-21): "Jede Nutzung ist ohne Einschränkungen oder Bedingungen zulässig."

*Our state.* `config/counters.yaml` (berlin). The Counts tab credits the Senatsverwaltung with links
to the dataset and the licence (`src/velometer/app/templates/city/counts.html:55`;
`city/berlin/counts/index.html`).

**Verdict:** ok

*Fix.* None. The credit is courtesy, not a duty.

### 1.4b Paris counters (ODbL)

*Rule.* ODbL 1.0 §§4.2-4.6, as in 1.1b and 1.1c.

*Our state.* `config/counters.yaml` (paris, licence ODbL). Counts tab: "Counter data: Ville de Paris,
Direction de la Voirie et des Déplacements, licence ODbL", linked to the dataset and the licence. The
derived index is ODbL under ADR 0008. The counter index is not offered as a download, so §4.2 does
not reach a file. The §4.6 question is the same as in 1.1c: the index method is described on the
methodology page.

**Verdict:** ok

*Fix.* None beyond 1.1c. If a counts download is ever added, it takes the ODbL notice with URI.

### 1.4c Vienna, Helsinki, Madrid, Barcelona counters (CC BY 4.0)

*Rule.* CC BY 4.0 Legal Code, §3(a)(1),
https://creativecommons.org/licenses/by/4.0/legalcode.en (read 2026-10-21): "If You Share the
Licensed Material (including in modified form), You must: retain the following if it is supplied by
the Licensor with the Licensed Material: identification of the creator(s) …; a copyright notice; a
notice that refers to this Public License; a notice that refers to the disclaimer of warranties; a URI
or hyperlink to the Licensed Material to the extent reasonably practicable; indicate if You modified
the Licensed Material and retain an indication of any previous modifications; and indicate the
Licensed Material is licensed under this Public License, and include the text of, or the URI or
hyperlink to, this Public License." §3(a)(2): "You may satisfy the conditions in Section 3(a)(1) in
any reasonable manner based on the medium, means, and context".

*Our state.* `config/counters.yaml` (vienna, helsinki, madrid, barcelona). The Counts tab credit names
the publisher, links the dataset and the licence, and gives the retrieval date. Example:
`city/vienna/counts/index.html`: "Counter data: Stadt Wien, licence CC BY 4.0, retrieved 2026-10-07."
What is shown is an index and totals computed by velometer: modified material. The credit line does
not say so, and only the surrounding prose ("sets an index of it") implies it.

**Verdict:** fix in M16

*Fix (Task 2).* Append to the counter credit, in both catalogues (`content/ui/*.yaml`,
`counts.attribution`, `js.counts.attribution`, and the template string used in `counts.html:55`):
EN "; index and totals computed by velometer", DE "; Index und Summen von velometer berechnet". This is
new reader-facing wording, so the user sees it with Task 2's diff.

### 1.4d Oslo counters (NLOD)

*Rule.* NLOD 2.0, §5, https://data.norge.no/nlod/en/2.0 (read 2026-10-21): "The licensee shall
attribute the licensor as specified by the licensor and include a reference to this licence. To the
extent practically possible, the licensee shall provide a link to both this licence and the source of
the information." The guidance on the same page says the attribution "need not be placed on the same
page as the information".

*Our state.* Counts tab: "Counter data: Statens vegvesen (state counters), licence NLOD", linked to
the dataset and to `https://data.norge.no/nlod/no`.

**Verdict:** ok

*Fix.* None.

### 1.5 Berlin WFS layers (dl-de/zero-2.0)

*Rule.* As in 1.4a.

*Our state.* `config/plans/sources.yaml` (radverkehrsnetz, radverkehrsmassnahmen, licence
dl-de-zero-2.0). `plans/` page: "Measures dataset: Radverkehrsmaßnahmen, Berlin geoportal, licence
dl-de-zero-2.0, retrieved …".

**Verdict:** ok

*Fix.* None.

### 1.6 BikeNetKit

*Rule.* The Zenodo record https://zenodo.org/api/records/22271229 (read 2026-10-21) has
`"license": None` and describes the files as "OpenStreetMap data sets from 403 European cities". The
code repository https://github.com/BikeNetKit/dataexport is AGPL-3.0 (GitHub licence API, read
2026-10-21). The data are OSM extracts, so ODbL §4.4 binds them whatever the record says, and our use
(single km figures shown on figures pages) is a Produced Work under §4.3.

*Our state.* Figures pages name "BikeNetKit's bicycle network (simplified OpenStreetMap network)" with
the DOI link (51 pages), and the page footer carries the OSM credit. ADR 0008 says: "BikeNetKit
(Zenodo 22271229) is also ODbL". The record does not state that.

**Verdict:** fix in M16

*Fix (Task 2, ADR 0008).* Reword to: "BikeNetKit (Zenodo 22271229) states no licence; its files are
OSM extracts and therefore under ODbL by share-alike. We use single figures from it, cited with the
DOI." No change on the site.

### 1.7 Protomaps basemap

*Rule.*
- protomaps/basemaps README, https://raw.githubusercontent.com/protomaps/basemaps/main/README.md (read
  2026-10-21): "The tilesets that power the Protomaps basemap are Produced Works of the OpenStreetMap
  dataset under the Open Database License. Web maps and native apps that use this Produced Work must
  visibly attribute © OpenStreetMap - for example, in the corner of the map display." Also: "If you
  distribute a modified “fork” of these basemap styles or tilesets, or provide a tiles API based on
  them, you must name your product or service something different from Protomaps. Free and unmodified
  redistributions of tiles and styles are permitted to use the name."
- LICENSE_DATA.md, https://raw.githubusercontent.com/protomaps/basemaps/main/LICENSE_DATA.md (read
  2026-10-21): "If displaying the `landcover` basemap layer, landcover is derived from the ESA
  WorldCover dataset, available under CC-BY 4.0 DEED." Natural Earth: "Crediting the authors is
  unnecessary."
- docs.protomaps.com/basemaps/downloads (read 2026-10-21): the basemap is "distributed as an Open
  Database License Produced Work (OpenStreetMap attribution required)".

*Our state.* Not built yet (Tasks 4 and 5). "Protomaps" appears in 0 exported files. The extract will
be served at `/tiles/velometer.pmtiles` and is therefore downloadable.

**Verdict:** fix in M16

*Fix (Task 5).*
- The map credit names "© OpenStreetMap contributors" (linked to openstreetmap.org/copyright) and
  "Protomaps" (requested, not required).
- Either do not draw the `landcover` layer, or add "ESA WorldCover (CC BY 4.0)" to the credit.
  Recommended: do not draw it. This must be checked in the flavour used, not assumed.
- The extract is served only for our own maps and is not offered as a tile service under the
  Protomaps name. `build.json` records the build date.

### 1.8 protomaps-leaflet and Leaflet (code)

*Rule.* protomaps-leaflet LICENSE (BSD-3-Clause),
https://raw.githubusercontent.com/protomaps/protomaps-leaflet/main/LICENSE (read 2026-10-21):
"Redistributions in binary form must reproduce the above copyright notice, this list of conditions
and the following disclaimer in the documentation and/or other materials provided with the
distribution." Leaflet is BSD-2-Clause, the repo's own copy at
`src/velometer/app/static/vendor/leaflet.LICENSE`, with the same binary-form clause.

*Our state.* Leaflet: `leaflet.js` keeps its `@preserve` header, and `leaflet.LICENSE` is exported at
`static/vendor/leaflet.LICENSE`. protomaps-leaflet is not vendored yet.

**Verdict:** fix in M16

*Fix (Task 5).* Vendor `protomaps-leaflet.LICENSE` beside the bundle, export it, keep any header
comment in the minified file, and add the entry in `static/vendor/VERSIONS`. ADR 0008 (Task 2) names
both libraries and their licences.

### 1.9 Datalab fonts (OFL)

*Rule.* SIL OFL 1.1, https://openfontlicense.org/open-font-license-official-text/ (read 2026-10-21):
"Original or Modified Versions of the Font Software may be bundled, redistributed and/or sold with any
software, provided that each copy contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or in the appropriate
machine-readable metadata fields within text or binary files as long as those fields can be easily
viewed by the user." And: "No Modified Version of the Font Software may use the Reserved Font Name(s)
unless explicit written permission is granted".
- Martian Mono, https://raw.githubusercontent.com/evilmartians/mono/main/OFL.txt (read 2026-10-21):
  "Copyright 2021 The Martian Mono Project Authors (https://github.com/evilmartians/mono)". No
  Reserved Font Name is declared.
- Public Sans, https://raw.githubusercontent.com/uswds/public-sans/develop/LICENSE.md (read
  2026-10-21): "users of this Modified Version (Public Sans) should use Public Sans according to the
  terms of the SIL Open Font License, Version 1.1"; "Copyright 2015 The Public Sans Project Authors".
  No Reserved Font Name is declared.

*Our state.* The spike page loads both fonts from Google Fonts
(`…/scratchpad/datalab/datalab-entwuerfe.html`: `fonts.googleapis.com`, `fonts.gstatic.com`).
Nothing is built yet (Task 6).

**Verdict:** fix in M16

*Fix (Task 6).* Self-host the woff2 files. Put each family's `OFL.txt`, with its copyright line,
beside the fonts and publish it. Subsetting is a Modified Version, but with no Reserved Font Name
declared, the subsets may keep their names. No request goes to Google (see 5.9).

### 1.10 DB-IP Lite Country

*Rule.* https://db-ip.com/db/download/ip-to-country-lite (read 2026-10-21): "The free IP to Country
Lite database by DB-IP is licensed under a Creative Commons Attribution 4.0 International License."
"You are free to use this IP to Country Lite database in your application, provided you give
attribution to DB-IP.com for the data." "In the case of a web application, you must include a link
back to DB-IP.com on pages that display or use results from the database".

*Our state.* Planned (spec §4.4, §4.9 item 6). The lookup runs on the server, offline, on the masked
address. The results appear only in the GoAccess report, which is not published (`data/stats/`,
git-ignored). CC BY obligations attach to sharing. An internal report is not shared, but the
attribution costs nothing.

**Verdict:** ok

*Fix.* Keep DB-IP. Task 8 puts "IP Geolocation by DB-IP (https://db-ip.com), CC BY 4.0" in the report
(GoAccess `html-report-title` or a footer line). ADR 0008 (Task 2) names it. The Datenschutzerklärung
(Task 6) says countries are derived offline from the masked address.

## 2. Comparison numbers and quotations

### 2.1 Single comparison figures and the database right

*Rule.* § 87a Abs. 1 UrhG, https://www.gesetze-im-internet.de/urhg/__87a.html (read 2026-10-21):
"Datenbank im Sinne dieses Gesetzes ist eine Sammlung von Werken, Daten oder anderen unabhängigen
Elementen, die systematisch oder methodisch angeordnet und einzeln mit Hilfe elektronischer Mittel
oder auf andere Weise zugänglich sind und deren Beschaffung, Überprüfung oder Darstellung eine nach
Art oder Umfang wesentliche Investition erfordert." § 87b Abs. 1 UrhG,
https://www.gesetze-im-internet.de/urhg/__87b.html: "Der Datenbankhersteller hat das ausschließliche
Recht, die Datenbank insgesamt oder einen nach Art oder Umfang wesentlichen Teil der Datenbank zu
vervielfältigen, zu verbreiten und öffentlich wiederzugeben. Der Vervielfältigung, Verbreitung oder
öffentlichen Wiedergabe eines nach Art oder Umfang wesentlichen Teils der Datenbank steht die
wiederholte und systematische Vervielfältigung, Verbreitung oder öffentliche Wiedergabe von nach Art
und Umfang unwesentlichen Teilen der Datenbank gleich, sofern diese Handlungen einer normalen
Auswertung der Datenbank zuwiderlaufen oder die berechtigten Interessen des Datenbankherstellers
unzumutbar beeinträchtigen." § 87c Abs. 1 Nr. 2 UrhG,
https://www.gesetze-im-internet.de/urhg/__87c.html, allows reproduction of a substantial part only
"zu Zwecken der wissenschaftlichen Forschung gemäß § 60c", not its public communication.

*Our state.* `config/external/figures.csv` holds 65 figures: 54 from the Clean Cities Campaign report
(Table 5, report p. 16), 9 official, 1 Changing Cities, 1 Mobilitätsagentur Wien. QECIO v2.10 totals
come from ECF's per-NUTS3 files. Each figure is stored with source URL and retrieval date, and the
pages cite it (ADR 0008). Single figures are facts and carry no copyright. The CSV downloads also
republish `ecf_qecio` and `clean_cities_2025` columns for every city and year (`data/*.csv`).

Clean Cities is the open point. We take several metrics from one table for 21 cities. A court might
see that as a substantial part of that table. It depends on how many rows and columns the table has
in total and what investment lies behind it; this review has not counted them. QECIO is very
unlikely to be a substantial part: we take 21 regions' totals from files that cover NUTS3 regions
across Europe (the region count was not checked for this review).

**Verdict:** question for a lawyer

*Fix.* None in M16. Q3 asks the lawyer. A conservative option is ready if the answer is no: drop the
`clean_cities_2025` column from the CSV downloads and keep the figures on the pages with citation.
That needs the user's go, since it changes a published download.

### 2.2 Quotations (§ 51 UrhG)

*Rule.* § 51 UrhG, https://www.gesetze-im-internet.de/urhg/__51.html (read 2026-10-21): "Zulässig ist
die Vervielfältigung, Verbreitung und öffentliche Wiedergabe eines veröffentlichten Werkes zum Zweck
des Zitats, sofern die Nutzung in ihrem Umfang durch den besonderen Zweck gerechtfertigt ist.
Zulässig ist dies insbesondere, wenn … 2. Stellen eines Werkes nach der Veröffentlichung in einem
selbständigen Sprachwerk angeführt werden". § 63 Abs. 2 UrhG,
https://www.gesetze-im-internet.de/urhg/__63.html: "In den Fällen der öffentlichen Wiedergabe nach den
§§ 46, 48, 51, … ist die Quelle einschließlich des Namens des Urhebers stets anzugeben, es sei denn,
dass dies nicht möglich ist."

*Our state.* Excerpts live in `content/sources/*.yaml`. Each is shown as a numbered footnote next to
the text that discusses it, with publisher, title, date and link, so the quotation serves our own
argument (Zitatzweck). The check below was run on 2026-10-21 with a script outside the repo
(`/tmp/claude-1000/-home-senzelden-code-bike-infrastructure/72d9e388-0647-45b7-bf69-8d0525c632a0/scratchpad/t1/excerpts.py`).
It counts the words of each excerpt (whitespace split) and checks that each source has publisher,
title, url and accessed, each excerpt a locator, and each non-English excerpt a gloss:

```
$ uv run python …/scratchpad/t1/excerpts.py content/sources
files=7 sources=155 excerpts=364
longest excerpt: 57 words (west.yaml:bordeaux-plan-velo-2021-2026/network-2021)
problems: 0
```

Most publishers are institutions (Abgeordnetenhaus, Senatsverwaltung, cities, NGOs). Where a person
is the author, § 63 asks for the author's name; the registry has no `author` field.

**Verdict:** ok

*Fix.* None required. Q4 asks whether naming the publishing institution suffices for official and NGO
documents without a named author.

### 2.3 Plan documents: cited, not redistributed

*Rule.* § 87b UrhG and § 51 UrhG as above. Official works may also be free under § 5 UrhG (not read
for this review).

*Our state.* ADR 0008: plan documents "are stored as printed figures with a citation, never
redistributed as files". The export contains no PDF (`find data/scratch-m15/site -name '*.pdf'` finds
none; the export's file types are HTML, CSS, JS, JSON, GeoJSON, CSV, PNG, one SVG, `.gz` siblings,
`_headers`, `VERSIONS` and `leaflet.LICENSE`).

**Verdict:** ok

*Fix.* None.

## 3. Statements of fact (press law)

Stub. Task 3 builds the candidate table (`docs/review/m16-press.md`, with a `Status` column, ruling
P2), and Task 10 takes it to the user. The rule that shapes the table is § 19 Abs. 1 MStV
(`https://recht.sachsen.de/vorschrift_gesamt/18790/45657.pdf`, read 2026-10-21): "Telemedien mit
journalistisch-redaktionell gestalteten Angeboten, in denen insbesondere vollständig oder teilweise
Inhalte periodischer Druckerzeugnisse in Text oder Bild wiedergegeben werden, haben den anerkannten
journalistischen Grundsätzen zu entsprechen. Gleiches gilt für andere geschäftsmäßig angebotene,
journalistisch-redaktionell gestaltete Telemedien, in denen regelmäßig Nachrichten oder politische
Informationen enthalten sind … Nachrichten sind vom Anbieter vor ihrer Verbreitung mit der nach den
Umständen gebotenen Sorgfalt auf Inhalt, Herkunft und Wahrheit zu prüfen." No reworded sentence ships
without the user's review (spec §4.1 item 3, ADR 0006 for "mapped km").

**Verdict:** decision for the user (decided 2026-10-23: the user reviewed all 96 rows of m16-press.md; every proposed rewording accepted, every keep kept)

*Fix.* Tasks 3 and 10.

## 4. Impressum

### 4.1 Which rules apply, and what each operator form must state

*Rule.*
- § 5 Abs. 1 DDG, https://www.gesetze-im-internet.de/ddg/__5.html (read 2026-10-21):
  "Diensteanbieter haben für geschäftsmäßige, in der Regel gegen Entgelt angebotene digitale Dienste
  folgende Informationen, die leicht erkennbar und unmittelbar erreichbar sein müssen, ständig
  verfügbar zu halten: 1. den Namen und die Anschrift, unter der sie niedergelassen sind, bei
  juristischen Personen zusätzlich die Rechtsform, den Vertretungsberechtigten und, sofern Angaben
  über das Kapital der Gesellschaft gemacht werden, das Stamm- oder Grundkapital … 2. Angaben, die
  eine schnelle elektronische Kontaktaufnahme und eine unmittelbare Kommunikation mit ihnen
  ermöglichen, einschließlich der Adresse für die elektronische Post, … 4. die Angabe des
  Handelsregisters oder ähnlicher Register, in das sie eingetragen sind, und die entsprechende
  Registernummer, … 6. in Fällen, in denen sie eine Umsatzsteueridentifikationsnummer nach § 27a
  Absatz 1 Satz 1, 2 oder 3 des Umsatzsteuergesetzes oder eine Wirtschafts-Identifikationsnummer nach
  § 139c Absatz 1 der Abgabenordnung besitzen, die Angabe dieser Nummer, 7. bei
  Aktiengesellschaften, Kommanditgesellschaften auf Aktien und Gesellschaften mit beschränkter
  Haftung, die sich in Abwicklung oder Liquidation befinden, die Angabe hierüber".
- § 18 Abs. 1 MStV (Saxon PDF above, read 2026-10-21): "Anbieter von Telemedien, die nicht
  ausschließlich persönlichen oder familiären Zwecken dienen, haben folgende Informationen leicht
  erkennbar, unmittelbar erreichbar und ständig verfügbar zu halten: 1. Name und Anschrift sowie 2.
  bei juristischen Personen auch Name und Anschrift des Vertretungsberechtigten."

*Reading.* velometer is free. Whether a free, non-commercial project is "geschäftsmäßig, in der Regel
gegen Entgelt" under § 5 DDG is not settled by the text. § 18 Abs. 1 MStV applies anyway, because
the site does not serve only personal or family purposes. So an Impressum is required in every
variant. The safe course is the full § 5 DDG content in every variant. What each form states:

| Item | Private person | e.V. | Company (e.g. GmbH/UG) |
|---|---|---|---|
| Name | full name | name of the Verein incl. "e.V." | Firma incl. Rechtsform |
| Anschrift | address where reachable (4.3) | Sitz address | Sitz address |
| Rechtsform | – | "eingetragener Verein" | e.g. "GmbH" |
| Vertretungsberechtigter | – | Vorstand (names, per § 26 BGB as registered) | Geschäftsführer (names) |
| Register | – | Vereinsregister, Amtsgericht, VR-Nr. | Handelsregister, Amtsgericht, HRB-Nr. |
| Kapital | – | – | only if stated anywhere; then with outstanding Einlagen |
| USt-IdNr. / W-IdNr. | if one exists | if one exists | if one exists |
| E-Mail + second fast channel | yes (4.4) | yes | yes |
| Verantwortlicher § 18 Abs. 2 MStV | yes (4.2) | yes | yes |
| Liquidation note | – | – | if in Abwicklung |

§ 5 Abs. 1 Nr. 3 and Nr. 5 (Aufsichtsbehörde, regulated professions) do not apply to any of the
three forms here.

*Our state.* `config/site.yaml` has `impressum_url: null` and `privacy_url: null`. There is no
Impressum page yet (Task 6 builds one variant block per form).

**Verdict:** decision for the user (decided 2026-10-23: operator is a private person)

*Fix.* The user picks the operator form (`sites/datalab/site.yaml` `operator_form`, spec §4.9 item 3).
Task 6 writes the three variant blocks from the table above.

### 4.2 Verantwortlicher nach § 18 Abs. 2 MStV

*Rule.* § 18 Abs. 2 MStV (Saxon PDF above): "Anbieter von Telemedien mit journalistisch-redaktionell
gestalteten Angeboten, in denen insbesondere vollständig oder teilweise Inhalte periodischer
Druckerzeugnisse in Text oder Bild wiedergegeben werden, haben zusätzlich zu den Angaben nach den §§
5 und 6 des Telemediengesetzes einen Verantwortlichen mit Angabe des Namens und der Anschrift zu
benennen. Werden mehrere Verantwortliche benannt, ist kenntlich zu machen, für welchen Teil des
Dienstes der jeweils Benannte verantwortlich ist. Als Verantwortlicher darf nur benannt werden, wer 1.
seinen ständigen Aufenthalt im Inland hat, 2. die Fähigkeit, öffentliche Ämter zu bekleiden, nicht
durch Richterspruch verloren hat, 3. unbeschränkt geschäftsfähig ist und 4. unbeschränkt strafrechtlich
verfolgt werden kann."

*Reading.* velometer publishes edited narratives, rankings and comment on public administration
(stories, city pages, differences). That is journalistic-editorial in character even without
reproducing a periodical. Treat § 18 Abs. 2 as applying. Q5 asks a lawyer to confirm.

*Our state.* Nothing named yet.

**Verdict:** decision for the user

*Fix.* The user names the Verantwortlicher (name and Anschrift; a person resident in Germany), one
for both sites or one per site. Task 6 renders "Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV:
[[Name]], [[Anschrift]]" in every variant.

### 4.3 Address, including a c/o service

*Rule.* § 5 Abs. 1 Nr. 1 DDG: "die Anschrift, unter der sie niedergelassen sind". § 18 Abs. 1 and 2
MStV: "Name und Anschrift".

*Reading.* For a company or e.V., the Sitz address answers this. For a private person, the home
address is the plain answer. Whether an "Impressum-Service" or c/o address, where post is accepted and
forwarded but the operator does not live or work, meets "Anschrift, unter der sie niedergelassen
sind" is not answered by the text. Court decisions on this were not read for this review.

*Our state.* No address chosen.

**Verdict:** question for a lawyer

*Fix.* Q6. Until it is answered, the private-person variant carries the placeholder `[[Anschrift]]`
with a comment that a c/o address needs the lawyer's yes.

### 4.4 Electronic contact

*Rule.* § 5 Abs. 1 Nr. 2 DDG: "Angaben, die eine schnelle elektronische Kontaktaufnahme und eine
unmittelbare Kommunikation mit ihnen ermöglichen, einschließlich der Adresse für die elektronische
Post".

*Our state.* No mailbox on the domain yet (spec §5: the user sets it up; go-live needs it). The
Datalab draft has the contact in the footer.

**Verdict:** decision for the user (decided 2026-10-23: e-mail on the domain only; whether that alone suffices stays Q7)

*Fix.* The user provides the contact address (`contact_email`). Q7 asks whether e-mail alone meets
"unmittelbare Kommunikation" or a second channel (phone number or a promptly answered form) is
needed. Task 6 leaves an optional `[[Telefon]]` slot.

### 4.5 Where the Impressum lives

*Rule.* § 5 Abs. 1 DDG and § 18 Abs. 1 MStV: "leicht erkennbar, unmittelbar erreichbar und ständig
verfügbar".

*Our state.* velometer's footer links `impressum_url` and `privacy_url` when set (`config/site.yaml`;
a public export requires all four values, M14). The Datalab site does not exist yet.

**Verdict:** fix in M16

*Fix (Task 6).* `/impressum` and `/datenschutz` on the apex. A footer link labelled "Impressum" and
"Datenschutz" on every Datalab page. `config/site.yaml` points velometer's footer at them (values set
at go-live). Both sites have the same operator, so one Impressum serves both, provided it names both
hostnames ("Diese Angaben gelten für <domain> und velometer.<domain>").

## 5. Datenschutz

### 5.1 Information under Art. 13 GDPR (Datenschutzerklärung)

*Rule.* GDPR Art. 13(1), official text (Publications Office, CELEX 32016R0679, read 2026-10-21): "the
controller shall, at the time when personal data are obtained, provide the data subject with all of
the following information: (a) the identity and the contact details of the controller …; (b) the
contact details of the data protection officer, where applicable; (c) the purposes of the processing
for which the personal data are intended as well as the legal basis for the processing; (d) where the
processing is based on point (f) of Article 6(1), the legitimate interests pursued by the controller
or by a third party; (e) the recipients or categories of recipients of the personal data, if any;
(f) where applicable, the fact that the controller intends to transfer personal data to a third
country". Art. 13(2): "(a) the period for which the personal data will be stored …; (b) the existence
of the right to request from the controller access to and rectification or erasure of personal data
or restriction of processing concerning the data subject or to object to processing as well as the
right to data portability; … (d) the right to lodge a complaint with a supervisory authority".
Art. 21(4): the right to object "shall be explicitly brought to the attention of the data subject and
shall be presented clearly and separately from any other information."

*Our state.* No Datenschutzerklärung exists. `privacy_url: null`.

**Verdict:** fix in M16

*Fix (Task 6).* `/datenschutz` in German, one controller block per operator form, then these items in
this order:
1. Verantwortlicher: name, Anschrift, E-Mail (per form, as in 4.1).
2. No Datenschutzbeauftragter is required (state it once; Art. 37 was not examined in detail; Q8).
3. What is processed when a page is called: the IP address in full only in the server's memory, for
   delivering the page. What is written: the masked address (IPv4 last 8 bits, IPv6 last 80 bits set
   to zero), date and time, requested path, HTTP method and status, bytes, referrer, browser
   (User-Agent), host name, protocol. Cookie and Authorization headers are not written.
4. Purposes: delivering the site, security (detecting and stopping attacks), error analysis,
   aggregate reach statistics (page views, approximate visitors, pages, referrers, countries,
   browsers and operating systems, downloads).
5. Rechtsgrundlage: Art. 6 Abs. 1 lit. f DSGVO. Berechtigtes Interesse: secure and error-free
   operation, and knowing the reach of a free public information offering (see 5.2).
6. Statistics: GoAccess on our own server; no cookies, no JavaScript, nothing stored in the browser;
   countries derived offline from the masked address with DB-IP Lite (if kept, 1.10); reports hold
   only aggregates (5.4).
7. Empfänger: Hetzner Online GmbH, Industriestr. 25, 91710 Gunzenhausen, as Auftragsverarbeiter
   (Art. 28 DSGVO); server location Germany. No transfer to a third country.
8. Speicherdauer: access logs 14 days, then deleted automatically. Reports keep no addresses.
9. Rights: Auskunft (Art. 15), Berichtigung (16), Löschung (17), Einschränkung (18), and
   Datenübertragbarkeit (20, only where it applies). Then, set apart under its own heading,
   **Widerspruchsrecht (Art. 21)**. Note Art. 11(2): with masked addresses we usually cannot tell
   which entries are a person's unless they give us more information.
10. Beschwerderecht bei einer Aufsichtsbehörde (5.8).
11. No obligation to provide data. No automated decision-making. Contact by e-mail: what is
    processed and for how long.
12. Stand: date.

### 5.2 Legal basis for logs and statistics; the /24 judgement (spec §4.9 item 1)

*Rule.*
- GDPR Art. 6(1)(f) (official text, as above): "processing is necessary for the purposes of the
  legitimate interests pursued by the controller or by a third party, except where such interests
  are overridden by the interests or fundamental rights and freedoms of the data subject which require
  protection of personal data, in particular where the data subject is a child."
- Recital 49: "The processing of personal data to the extent strictly necessary and proportionate
  for the purposes of ensuring network and information security … constitutes a legitimate interest
  of the data controller concerned. This could, for example, include preventing unauthorised access
  to electronic communications networks and malicious code distribution and stopping ‘denial of
  service’ attacks".
- Recital 47: "At any rate the existence of a legitimate interest would need careful assessment
  including whether a data subject can reasonably expect at the time and in the context of the
  collection of the personal data that processing for that purpose may take place."
- Recital 26: "Personal data which have undergone pseudonymisation, which could be attributed to a
  natural person by the use of additional information should be considered to be information on an
  identifiable natural person. To determine whether a natural person is identifiable, account should
  be taken of all the means reasonably likely to be used, such as singling out".
- Art. 5(1)(c) and (e): data "adequate, relevant and limited to what is necessary" and "kept in a
  form which permits identification of data subjects for no longer than is necessary".
- CJEU C-582/14 Breyer (official text, Publications Office, CELEX 62014CJ0582, read 2026-10-21),
  ruling 1: "a dynamic IP address registered by an online media services provider when a person
  accesses a website that the provider makes accessible to the public constitutes personal data …
  where the latter has the legal means which enable it to identify the data subject with additional
  data which the internet service provider has about that person." Ruling 2: "the objective aiming to
  ensure the general operability of those services may justify the use of those data after a
  consultation period of those websites."
- CJEU C-413/23 P EDPS v SRB, 4 September 2025 (CELEX 62023CJ0413, read 2026-10-21), para. 283
  (on Regulation 2018/1725, worded like the GDPR): "pseudonymised data must not be regarded as
  constituting, in all cases and for every person, personal data …, in so far as pseudonymisation
  may, depending on the circumstances of the case, effectively prevent persons other than the
  controller from identifying the data subject".

*Judgement.* **Yes: a /24-masked (IPv6 /48) access log kept 14 days fits Art. 6(1)(f) without
consent**, for the purposes listed in 5.1 item 4.
1. *Personal data or not.* After masking, the operator cannot ask an ISP to resolve a full address,
   because it no longer has one. On its own, a /24 prefix stands for up to 256 addresses. Combined
   with time, path and User-Agent, singling out a visitor on a low-traffic site is still conceivable
   (recital 26). EDPS v SRB supports a relative view, but it is not safe to rely on it. **Treat the
   masked log as pseudonymised personal data.** That is the design's position (spec §4.9 item 1),
   and it is the cautious one.
2. *Legitimate interest.* Security and operation are named in recital 49 and accepted in Breyer
   ruling 2. Knowing whether a free public information offering is read, and which pages are, is a
   legitimate interest of any publisher.
3. *Necessity.* No milder means gives the same result. Without JavaScript or cookies, server logs
   are the only source of these counts. Masking removes the part that identifies a line. 14 days
   covers a fortnightly report and the investigation of an incident. Only the counts of approximate
   unique visitors and countries need any part of the address. Page views, pages and referrers do
   not.
4. *Balancing.* No profiling, no tracking across sites, no cookies, nothing stored in the browser,
   no third party except the processor, no transfer outside the EU, deletion after 14 days, and only
   aggregates in the reports. Server logs are a commonly known, expected part of visiting a website
   (recital 47). The right to object is offered (Art. 21). Children are not a target audience.
5. *Weak points, each with a fix:*
   (a) the IPv6 /48 keeps more than the IPv4 /24 does. At some providers a /48 is the block of a
   single customer site (not verified here), so a /48 can be closer to one household than a /24 is.
   Q9 asks whether `ip_mask 24 32` (IPv6 /32) should be used instead, which changes the recorded
   design. Until then /48 stays and is named in the Datenschutzerklärung.
   (b) The GoAccess report lists hosts unless that panel is switched off (5.4).
   (c) Caddy's error log carries `remote_ip` (5.3).
   (d) Caddy rolls logs by size unless told otherwise, so "14 days" must be configured (5.4).

**Fallback** if the lawyer or the user disagrees: drop the address before it reaches the disk
(`request>remote_ip delete`, `request>client_ip delete`, the same in the error log) and keep the rest
of the line. GoAccess then counts unique visitors from date and User-Agent only, which is much less
accurate, and has no countries (drop DB-IP). The legal basis for the remaining fields stays Art.
6(1)(f), and the Datenschutzerklärung loses the masking paragraph.

*Our state.* Design only (spec §4.4, §4.9 item 1). No server yet.

**Verdict:** ok

*Fix.* None beyond 5.3 and 5.4.

### 5.3 Masking in every Caddy log

*Rule.* As in 5.2: an unmasked address on disk or in journald would be a full personal datum, kept
outside the stated retention. Caddy documentation, `log` directive,
https://caddyserver.com/docs/caddyfile/directives/log (read 2026-10-21): "ip_mask Masks IP addresses
in the field using a CIDR mask, i.e. the number of bits from the IP to retain, starting from the left
side. If the field is an array of strings (e.g. HTTP headers), each value in the array is masked."

*Our state.* No Caddyfile yet. The plan's Task 7 interface already masks `request>remote_ip` and
`request>client_ip` with `24 48` in each site log and in the default logger for `http.log.error`.

**Verdict:** fix in M16

*Fix (Task 7).*
- The same `ip_mask 24 48` filter on every field that can carry an address: `request>remote_ip`,
  `request>client_ip`, and also `request>headers>X-Forwarded-For` (a client can send it, and it is
  an array field the filter masks). Plus `remote_ip` on error entries, and `delete` for `Cookie` and
  `Authorization`.
- The default logger must not print access or error lines with an unmasked address to stdout, which
  journald stores.
- The test sends a request with a forged `X-Forwarded-For: 203.0.113.7` and asserts that `203.0.113.7`
  appears nowhere, in log files or in container output.

### 5.4 Retention: 14 days, in the logs and in the reports

*Rule.* Art. 5(1)(e) GDPR as above; Art. 13(2)(a) (the stated period must be true). Caddy docs (URL
above): "roll_interval … Default: disabled"; "roll_size … Default: 100MiB"; "roll_keep … Default:
10"; "roll_keep_for is how long to keep rolled files … Triggers when a new log file is created. The
current implementation supports day resolution"; "roll_at is a list of time values (in 24-hour
format) at which to roll the log file."

*Our state.* Plan Task 7 sets only `roll_keep_for 336h`. On a small site the file then never reaches
100 MiB and never rolls, so lines stay in the active file far beyond 14 days. And `roll_keep`'s
default of 10 would cut retention to 10 daily files. Plan Task 8 stores one GoAccess HTML per run in
`data/stats/` with no end date. GoAccess's hosts panel lists the (masked) addresses, so the reports
would keep them indefinitely.

**Verdict:** fix in M16

*Fix.*
- Task 7: each site log gets `roll_at 00:00` (or `roll_interval 24h`), `roll_keep 14` and
  `roll_keep_for 336h`, and a test asserts all three. If Caddy 2.11.4 lacks `roll_at`, use
  `roll_interval 24h`. Task 7 checks this against the pinned binary. The longest any line can live is
  then the day it was written plus 14 days. The Datenschutzerklärung says "14 Tage".
- Task 8: `deploy/goaccess.conf` sets `ignore-panel HOSTS` (and, if present, `REMOTE_USER`), so the
  reports carry only aggregates. A test greps a generated report for an IP pattern.

### 5.5 § 25 TDDDG (terminal equipment)

*Rule.* § 25 Abs. 1 TDDDG, https://www.gesetze-im-internet.de/ttdsg/__25.html (read 2026-10-21): "Die
Speicherung von Informationen in der Endeinrichtung des Endnutzers oder der Zugriff auf Informationen,
die bereits in der Endeinrichtung gespeichert sind, sind nur zulässig, wenn der Endnutzer auf der
Grundlage von klaren und umfassenden Informationen eingewilligt hat." Abs. 2 Nr. 2: no consent "wenn
die Speicherung von Informationen in der Endeinrichtung des Endnutzers oder der Zugriff auf bereits
in der Endeinrichtung des Endnutzers gespeicherte Informationen unbedingt erforderlich ist, damit der
Anbieter eines digitalen Dienstes einen vom Nutzer ausdrücklich gewünschten digitalen Dienst zur
Verfügung stellen kann."

*Our state.* No cookies, `localStorage`, `sessionStorage` or IndexedDB in velometer's own scripts
(`grep -rn "localStorage\|sessionStorage\|document.cookie\|indexedDB\|serviceWorker"
src/velometer/app/static --include=*.js`, vendor and tests excluded: no hits). The Datalab draft has
none either. Theme follows `prefers-color-scheme`, so nothing is remembered. The basic-auth lock
until go-live makes the browser keep the credentials. That is strictly necessary for the requested
access (Abs. 2 Nr. 2) and ends at go-live. The server reads only what the browser sends with every
request (address, User-Agent, Referer). Whether that counts as "Zugriff" under § 25 was not checked
against the DSK guidance, which could not be fetched. Reading it in the ordinary sense, nothing is
stored on or read from the device.

**Verdict:** ok

*Fix.* None. Any future feature that stores something in the browser needs this topic reopened.

### 5.6 Hetzner as processor (AVV)

*Rule.* GDPR Art. 28(3) (official text): "Processing by a processor shall be governed by a contract
or other legal act under Union or Member State law, that is binding on the processor with regard to
the controller". Hetzner Docs, Data privacy FAQ,
https://docs.hetzner.com/general/general-terms-and-conditions/data-privacy-faq/ (read 2026-10-21): "A
Data Processing Agreement (DPA) is required if Hetzner processes personal data on your behalf within
the scope of the products or services you have rented (Art. 28 (3) GDPR)." "We do not create or sign
individual Data Processing Agreement (DPA)s." "You can conclude the data processing agreement
directly in your customer account: [ https://accounts.hetzner.com/account/dpa ]", with texts at
`https://www.hetzner.com/AV/DPA_de.pdf`. On US locations: "Only the data stored on your cloud server
is transferred to the USA, provided you have chosen this product location." The page
`https://www.hetzner.com/legal/order-processing/` returned only navigation and was not used.

*Our state.* No server, no DPA. The planned location is `nbg1` or `fsn1` (spec §4.2).

**Verdict:** decision for the user

*Fix.* The user concludes the DPA in the Hetzner account before go-live, choosing the data
categories (web server logs with masked IP addresses) and data subjects (website visitors), and
records the date. The server stays in a German location. This step is the user's, outside the repo.

### 5.7 Let's Encrypt

*Rule.* ISRG / Let's Encrypt privacy policy, https://letsencrypt.org/privacy/ ("Last updated: July 6,
2026", read 2026-10-21). For subscribers: "That information includes the IP addresses from which you
access the Let’s Encrypt service; all resolved IP addresses for any requested identifiers; server
information related to any validation requests". "This information may be made public in a number of
ways, including via public API, public repositories such as Certificate Transparency (CT) logs". For
relying parties: "When you use an HTTPS web site … your browser (or TLS client) may query Let’s
Encrypt to check whether the certificate has been revoked. If your browser makes such a request, our
servers may automatically record your IP address, browser, and operating system in temporary server
log files."

*Our state.* Caddy obtains certificates. No visitor data are sent to Let's Encrypt by us. Two
corrections to the spec's "sees the domain only": Let's Encrypt also sees the server's addresses, and
the hostnames become public in CT logs as soon as certificates are issued, which is before go-live.
The lock still holds. A visitor's own browser may contact Let's Encrypt to check revocation. That is
the browser's doing, not a page loading a resource.

**Verdict:** ok

*Fix.* None. The user should know that `velometer.<domain>` and `www.<domain>` show up in public CT
logs from the first deploy on.

### 5.8 Data subject rights and the supervisory authority

*Rule.* GDPR Art. 13(2)(b), (d) and Art. 21(4) as in 5.1. Art. 11(2): "Where, in cases referred to in
paragraph 1 of this Article, the controller is able to demonstrate that it is not in a position to
identify the data subject, the controller shall inform the data subject accordingly, if possible. In
such cases, Articles 15 to 20 shall not apply except where the data subject, for the purpose of
exercising his or her rights under those articles, provides additional information enabling his or
her identification." Berlin authority, https://www.datenschutz-berlin.de/impressum/ (read
2026-10-21, WebFetch): "Berliner Beauftragte für Datenschutz und Informationsfreiheit", "Alt-Moabit
59-61", "10555 Berlin", "+49 30 13889-0", "mailbox@datenschutz-berlin.de".

*Our state.* No text yet.

**Verdict:** fix in M16

*Fix (Task 6).* The rights block of 5.1 item 9, with Widerspruch under its own heading. A visitor may
complain to any supervisory authority, in particular where they live or work (Art. 77). The
Datenschutzerklärung names the authority competent for the controller, which follows the operator's
seat or residence: the BlnBDI with the data above **if the operator is in Berlin**; otherwise the
authority of that Land. Task 6 makes this a field per operator variant (`[[Aufsichtsbehörde]]`,
defaulting to the BlnBDI text), not a fixed string.

### 5.9 No page loads anything from another host

*Rule.* The design's own rule (spec §1, §4.3), which keeps 5.1 item 7 true. Every outside host would
be a further recipient of the visitor's full IP address.

*Our state.* 206 of 248 exported HTML files reference `tile.openstreetmap.org` (tier, change and
counter maps). The CSP admits it in `img-src` (`src/velometer/app/main.py:116`, `:135`; `_headers`).
The Datalab draft loads `fonts.googleapis.com` and `fonts.gstatic.com`. Outbound links
(`rel="noopener noreferrer"`) are not loads. `Referrer-Policy: strict-origin-when-cross-origin`
limits what a followed link discloses.

**Verdict:** fix in M16

*Fix.* Task 5 removes the OSM tile host from the CSP, the maps and the render-pass allowance. Task 6
self-hosts the fonts under the same CSP. The render-pass foreign-host audit (both editions, both
themes) shows 0 foreign hosts, and its report is kept in the records.

## 6. Other duties

### 6.1 Accessibility (BFSG)

*Rule.* § 1 Abs. 3 BFSG, https://www.gesetze-im-internet.de/bfsg/__1.html (read 2026-10-21): "Dieses
Gesetz gilt für folgende Dienstleistungen, die für Verbraucher nach dem 28. Juni 2025 erbracht werden:
… 5. Dienstleistungen im elektronischen Geschäftsverkehr." § 2 Nr. 26 BFSG,
https://www.gesetze-im-internet.de/bfsg/__2.html: "„Dienstleistungen im elektronischen
Geschäftsverkehr“ digitale Dienste nach § 1 Absatz 4 Nummer 1 des Digitale-Dienste-Gesetzes, die über
Webseiten und über Anwendungen auf Mobilgeräten angeboten werden und elektronisch und auf individuelle
Anfrage eines Verbrauchers im Hinblick auf den Abschluss eines Verbrauchervertrags erbracht werden".

*Our state.* Neither site leads to a consumer contract (no shop, no subscription, no paid service).
The BFSG does not apply. velometer already checks contrast and keyboard use in its render pass. That
is good practice, not a legal duty here. BITV 2.0 binds public bodies only (not read).

**Verdict:** ok

*Fix.* None. If a paid offer or a donation-with-consideration flow is ever added, reopen.

### 6.2 OSM tile usage policy

*Rule.* https://operations.osmfoundation.org/policies/tiles/ (read 2026-10-21): "heavy or
inappropriate use harms others’ ability to edit and view the map. We may block access, without
notice". It also lists among things not to do: "Set a restrictive Referrer-Policy that prevents the
HTTP Referer header being sent."

*Our state.* After Task 5, no page requests `tile.openstreetmap.org`, and the policy no longer
applies. Until then, the M15 headers (`strict-origin-when-cross-origin`) do send a Referer origin, so
nothing was in breach.

**Verdict:** ok

*Fix.* None (moot after Task 5).

### 6.3 Names and marks of the organisations quoted

*Rule.* § 23 Abs. 1 Nr. 3 and Abs. 2 MarkenG,
https://www.gesetze-im-internet.de/markeng/__23.html (read 2026-10-21): the owner may not forbid a
third party to use "die Marke oder die geschäftliche Bezeichnung zu Zwecken der Identifizierung oder
zum Verweis auf Waren oder Dienstleistungen als die des Inhabers der Marke", "nur dann …, wenn die
Benutzung durch den Dritten den anständigen Gepflogenheiten in Gewerbe oder Handel entspricht."
§ 23 applies "im geschäftlichen Verkehr". A non-commercial site naming an organisation to identify it
is further from trademark use still.

*Our state.* Organisations (Clean Cities, ECF, Changing Cities, the Senate administrations and others)
are named in text, to identify the source of a figure or a quotation. No logo of any organisation is
in the export: the only images are our own maps (`maps/*.png`, 84) and one file in `static/`. No page
suggests endorsement.

**Verdict:** ok

*Fix.* None. Keep logos out. The project's own name, "Zählwerk Berlin Datalab", was not checked
against the DPMA or EUIPO registers. That is listed as Q10, not as a blocker.

### 6.4 Image rights on the Datalab page

*Rule.* § 51 and § 63 UrhG as above, and the general rule that a photo needs the rights holder's
permission (not separately quoted).

*Our state.* The Datalab draft (`…/scratchpad/datalab/datalab-entwuerfe.html`) contains no `<img>`,
one inline SVG of our own, and no photo. Its numbers come from velometer's export.

**Verdict:** ok

*Fix.* None. A photo added later needs a licence note beside it.

---

## Fixes for M16

| # | Topic | What | Task |
|---|---|---|---|
| F1 | 1.1b | One OSM notice with both URIs (openstreetmap.org/copyright, opendatacommons.org/licenses/odbl/1-0/) in CSV preamble, tier-map and change-map GeoJSON (`attribution` member), `series.json`, tier-map and chart PNG footers | Task 2 |
| F2 | 1.2a | EuroGeographics notice, exact text: EN `© EuroGeographics for the administrative boundaries`, DE `© EuroGeographics bezüglich der Verwaltungsgrenzen` (replaces the plan's "für die"), in the tier-map attribution (P1), site footer, tier-map PNG, tier-map GeoJSON (plus "the `boundary` member is GISCO data under GISCO terms, not ODbL"), CSV preamble, methodology/sources block; ADR 0008 adds GISCO with its non-commercial condition | Task 2 (kept by Task 5) |
| F3 | 1.3 | Population credits per source: Eurostat; "Source : Insee" (FR); "Elaboración propia con datos extraídos del sitio web del INE: www.ine.es" (ES); in the CSV preamble per city and the methodology block, plus the non-responsibility line for derived per-capita figures; ADR 0008 entry (Eurostat, INSEE, INE) | Task 2, Task 2 (ADR) |
| F4 | 1.4c | Counter credit adds "; index and totals computed by velometer" / "; Index und Summen von velometer berechnet" (user sees the wording) | Task 2 |
| F5 | 1.6 | ADR 0008: BikeNetKit "states no licence; OSM extracts, so ODbL by share-alike" | Task 2 |
| F6 | 1.7 | Map credit: © OpenStreetMap contributors (linked) + Protomaps; no `landcover` layer (or ESA WorldCover CC BY 4.0 credit); extract not offered as a tile service; ADR 0008 entry (Protomaps basemap: ODbL produced work; ESA WorldCover if landcover is drawn) | Task 5, Task 2 (ADR) |
| F7 | 1.8 | Vendor and export `protomaps-leaflet.LICENSE`, `VERSIONS` entry; ADR 0008 names Leaflet (BSD-2) and protomaps-leaflet (BSD-3) | Task 5, Task 2 (ADR) |
| F8 | 1.9 | Self-hosted woff2 with each family's `OFL.txt` published beside them; ADR 0008 names the fonts | Task 6, Task 2 (ADR) |
| F9 | 4.5 | `/impressum`, `/datenschutz` on the apex, linked in every footer; one Impressum naming both hostnames | Task 6 |
| F10 | 5.1, 5.8 | Datenschutzerklärung with the twelve items of 5.1, Widerspruch set apart, authority as a per-variant field | Task 6 |
| F11 | 5.3 | `ip_mask 24 48` on `remote_ip`, `client_ip`, `X-Forwarded-For`, error-log `remote_ip`; Cookie/Authorization deleted; no unmasked address on stdout; test with a forged `X-Forwarded-For` | Task 7 |
| F12 | 5.4 | `roll_at 00:00` (or `roll_interval 24h`), `roll_keep 14`, `roll_keep_for 336h`, tested | Task 7 |
| F13 | 5.4 | `goaccess.conf`: `ignore-panel HOSTS`; test that a report contains no IP pattern | Task 8 |
| F14 | 5.9 | CSP without `tile.openstreetmap.org`; fonts self-hosted; render-pass audit 0 foreign hosts | Task 5, Task 6 |
| F15 | 1.10 | DB-IP credit line in the GoAccess report; ADR 0008 entry | Task 8, Task 2 (ADR) |

F13 and F15 fall to Task 8, which owns `goaccess.conf`. Each implementing task owns a test that fails without its fix.

## Decisions for the user (block go-live until decided)

1. 1.1c: how §4.6 ODbL is met. Publish the repository (recommended), offer the snapshot data, or ask.
2. 1.2b: confirm non-commercial use of the GISCO boundaries (no ads, no paid service, no sale of
   data).
3. 3: review the press-law table (Tasks 3 and 10).
4. 4.1: the operator form.
5. 4.2: the Verantwortlicher nach § 18 Abs. 2 MStV (resident in Germany).
6. 4.4: the contact mailbox (and whether to add a phone number, pending Q7).
7. 5.6: conclude the Hetzner DPA in the account and record the date.

## Questions for a lawyer

1. **ODbL §4.6.** Does printing the complete classifier rules and parameters on the methodology page,
   plus per-city GeoJSON of the current snapshot, satisfy "the method of making the alterations",
   or must the code or the yearly classified data be offered?
2. **GISCO "commercial purposes".** Does free publication by a company (or an e.V. with membership
   fees) count as commercial use of the GISCO LAU/URAU boundaries and the `POP_2024` values from the
   same download? Is labelling the boundary member of an ODbL GeoJSON as separately licensed
   (ODbL §4.5 a, collective database) enough to avoid the §4.4 d conflict?
3. **Database right (§ 87b UrhG).** Are 54 values from Table 5 of the Clean Cities 2025 report (21
   cities, several metrics) a "nach Art oder Umfang wesentlicher Teil", and does republishing them
   in CSV downloads change the answer?
4. **§ 63 UrhG.** For official and NGO documents without a named author, does naming the publishing
   institution with title, date and link meet "die Quelle einschließlich des Namens des Urhebers"?
5. **§ 18 Abs. 2 MStV.** Is velometer (data pages with edited narratives about named
   administrations) "journalistisch-redaktionell gestaltet", so that a Verantwortlicher must be
   named?
6. **Address.** For a private operator, does a c/o or Impressum-service address meet "Anschrift,
   unter der sie niedergelassen sind" (§ 5 DDG) and "Anschrift" (§ 18 MStV)?
7. **Electronic contact.** Does an e-mail address alone meet § 5 Abs. 1 Nr. 2 DDG, or is a second
   fast channel needed?
8. **Data protection officer.** Confirm that none is needed for any of the three operator forms at
   this scale.
9. **IPv6 mask.** Is `/48` adequate for the Art. 6(1)(f) balancing, or should IPv6 be cut to `/32`
   (or less) to match the protection of the IPv4 `/24`?
10. **Own name.** Is a register search for "Zählwerk Berlin Datalab" (DPMA, EUIPO) advisable before
    go-live?
