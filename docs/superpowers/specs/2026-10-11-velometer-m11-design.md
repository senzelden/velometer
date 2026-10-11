# velometer M11: reader features (design)

Status: design approved by the user on 2026-10-11 (conversation, sections 1–8 below); the
written spec awaits review.
Follows M10, polish and accessibility (main at bf58670). Roadmap: M9 spec §2, plus the user's
2026-10-11 request for a sources overview.

## 1. Purpose

velometer is a meta-study. It sets the published cycling figures beside each other and beside
our own OpenStreetMap figures, and it says why they differ. M11 lets a reader:

- see in one place how every quoted report measures, and how our approach differs;
- cite exactly the figure they saw;
- download a chart as an image and as the rows behind it;
- link to the exact view they saw;
- jump to a city or page by name.

The main readers are still journalists and researchers. Nothing they use today may get worse:
compare, tables, CSV, methodology and the M10 accessibility bar.

## 2. User decisions (2026-10-11)

- **Sources overview rows:** every figure source that the app quotes. This covers the
  cross-city rankings and the official city reports. Plan bodies with no figure in the app stay
  on `/organisations` only.
- **Labels:** "method on our data". The headers become "velometer headline", "QECIO method,
  our OSM data" and "Clean Cities method, our OSM data".
- **Citation formats:** readable text, BibTeX and CSL-JSON.
- **Search reach:** cities (with alternative names), countries, organisations, stories and the
  main pages. It is not full text.
- **Approach:** everything works in the static edition. The browser does the interaction; the
  server renders the data behind it into the page or into small JSON files.

## 3. Decisions

1. **Sources page.**
   - The page is `/sources`, linked in the nav between Organisations and Methodology.
   - It holds one table.
     - The first row is **Our approach**. It reads from `config/differences.yaml` `ours`; its
       date cell is the run's OSM snapshot.
     - Then come two row groups: **Cross-city rankings** and **Official city reports**. Each has
       one row per figure source.
     - A source is a figure source if some city's Figures tab quotes one of its figures. This
       uses the same list that `report/differences.py` builds the Figures rows from.
     - The row group is a new required field on each figure source:
       `group: ranking | city_report`.
   - Columns:
     - the source (title, publisher, year, linked to its organisation profile);
     - the six dimensions, in `differences.yaml` order, with each header linking to
       `/differences#dim-<id>`;
     - **Cities**, linking to each city's Figures tab that quotes the source;
     - **Recomputed by us**, linking to the overview column for sources we recompute (QECIO,
       Clean Cities) and showing "–" otherwise.
   - **Where the cells come from:**
     - A source's dimension cells come from its organisation profile's "How they measure"
       `dimensions`, with the profile's citations.
     - A source may override any dimension with its own `dimensions:` block in
       `content/sources/*.yaml`, with citations. This covers one organisation that publishes
       reports that differ.
     - Citation markers render as on the profile pages, and the page ends with the cited-sources
       list (the `_cited.html` include).
   - **Content check:** `velometer content --check` fails if a figure source:
     - has no `group`;
     - lacks any of the six dimensions after the override is applied;
     - has a dimension value without a citation, other than "not stated by the source".
     So a new figure source cannot ship without its row.
   - Below 600 px the table is `table.stack`, like every M10 data table.
   - The overview gets a link to `/sources` and to "Why the figures differ" (`/differences`,
     which is otherwise reachable only from a Figures tab today).
   - `/organisations` and `/differences` are unchanged apart from the incoming links.
2. **Labels.**
   - The three `kind: preset` labels in `config/report.yaml` become:
     - "velometer headline";
     - "QECIO method, our OSM data";
     - "Clean Cities method, our OSM data".
   - The `kind: external` labels keep "… (published)".
   - Every column header for a preset or an external source links to that source's row on
     `/sources` (`/sources#src-<source id>`, or `#ours` for ours).
   - The ids in the CSV columns and in `series.json` do not change, so scripts keep working.
     Only display labels change.
   - The fallback in `report/data.py` ("Ours: <id>") becomes "<id>, our OSM data".
3. **Cite this figure.**
   - **Where it appears:** a "Cite" disclosure (`<details class="cite">`) sits beside:
     - every key number (the header keynums and the overview key numbers);
     - every chart;
     - every Figures row;
     - the compare view (one citation for the current state).
   - **Fields** (server side, from the run and build data already in the page context; rendered
     as JSON in the page):
     - the figure title, e.g. "Berlin, headline (A+B km per 100 km of main roads), city proper
       (LAU), Oct 2026";
     - the author: "velometer";
     - the OSM snapshot timestamp;
     - the classifier version and the run id;
     - the commit;
     - the publisher line "Map data © OpenStreetMap contributors, ODbL 1.0".
   - **What the browser adds:**
     - the access date (today, in ISO format);
     - the absolute URL, from the address the page is served at plus the current permalink
       state (decision 5).
   - **Formats:** readable text, BibTeX (`@misc`) and CSL-JSON (`type: dataset`).
     - Each format sits in its own `<pre>` with a "Copy" button.
     - Copying uses `navigator.clipboard`. If that fails, the text is selected and the reader is
       told to press Ctrl+C.
     - The result is announced through the M10 live region.
   - **Without JS:** the readable text renders server side, without the access date and with a
     relative URL. The BibTeX and CSL-JSON blocks need JS.
   - One pure module (`static/js/cite.js`) formats all three from the fields. A Python function
     does the same for the server-side text, and both are tested against shared cases in
     `tests/cite_cases.json` (the M9 `url_cases.json` pattern).
4. **Chart downloads.**
   - **Where:** a "Download" control (a disclosure with three buttons) sits on every chart that
     `chart.js` mounts:
     - overview;
     - city Over time, Tiers, Story, Counts and Bezirke;
     - compare (all views);
     - the panel;
     - Berlin plans.
   - **SVG:**
     - a self-contained file, cloned from the drawn chart;
     - every colour from a token or CSS class is resolved and written as an attribute, with no
       `var(`, no `class`-dependent styling and no external reference;
     - fonts become a generic family stack;
     - a title, a source line ("velometer · OSM <snapshot> · classifier vN · <commit>") and the
       ODbL attribution are added as text inside the image.
   - **Theme:** downloads always use the light theme, whatever the reader's OS theme, because
     they are for print and publication. The resolution reads the light token values.
   - **PNG:** the SVG drawn to a canvas at 2× and saved with `canvas.toBlob`. No external image
     is involved, so the canvas is never tainted.
   - **CSV:** the rows behind the chart, which are the same rows as its data table (M10 decision
     6).
     - Same column ids as the matching server CSV where one exists.
     - Same first line, `# velometer <commit> generated <time>`, followed by an attribution line.
   - **File names:** `velometer-<page>-<chart>-<state>.svg|png|csv`, ASCII, from the chart id
     and the permalink state.
   - Downloads are built in the browser from what the page already holds. There are no new
     server routes, and they work in the static edition.
   - Tier-map and change-map downloads are out of scope. The tier PNGs are already linked.
5. **Permalinks.**
   - Every control that changes what is shown writes its state to the URL with
     `history.replaceState`, which adds no history entries. Loading that URL restores the state.
   - **Covered state:**
     - the city tab (a path, already);
     - compare (a query, already);
     - the tier map: boundary, tiers shown, centre and zoom, as `?kind=&tiers=&at=lat,lon,z`;
     - the story step (`#step-<id>`);
     - the open city panel on compare (already a history state, now also in the URL).
   - **Bad input:** an unknown, malformed or stale value is ignored and that control keeps its
     default. The page never errors.
   - **Copy link:** a "Copy link" button sits beside "Cite" on stateful pages and copies the
     current absolute URL, with the same fallback and announcement as Cite.
   - **One module:** a pure `static/js/permalink.js` with `read(search, hash, schema)` and
     `write(state, schema)`. Each page declares a schema (allowed keys, parsers, defaults). The
     existing compare `state.js` stays and is not rewritten. Only new state uses `permalink.js`.
6. **Search and jump.**
   - **Where:** a search box in the nav, following the WAI-ARIA 1.2 combobox pattern with a
     listbox popup.
     - Arrow keys move through results, Enter opens one and Escape closes the list.
     - The result count is announced through the live region.
     - It works with the M10 phone menu.
   - **Index:** `/data/search.json`, rendered by the app and written by the export. Each entry
     is `{label, kind, url, terms[]}` for:
     - every city;
     - countries;
     - organisations;
     - stories (narratives);
     - the main pages: Overview, Compare, Cities, Stories, Plans, Organisations, Sources,
       Methodology, Methodology (de), Why the figures differ.
   - **Alternative names:**
     - City aliases are a new optional `aliases:` list per city in `config/cities.yaml`, e.g.
       "Vienna" for Wien and "Copenhagen" for København.
     - This is display data, not a classifier change.
     - Every one of the 21 cities with a common English name gets it.
   - **Matching** is accent- and case-insensitive (NFD with combining marks stripped, so
     "krakow" matches Kraków). Prefix matches rank above substring matches, cities rank first,
     and the list shows at most 8 results.
   - **Without JS:** the box is a link to `/cities`.
7. **Proof.**
   - **pytest rules (in the gate):**
     - every figure source has a `/sources` row with a group and six cited dimension cells;
     - every preset and external column header links to an existing row anchor;
     - the CSV column ids and `series.json` ids are unchanged from M10 (the rule is a fixed id
       list taken from the M10 export);
     - every citation's fields match the run and `build.json` data of the page;
     - the Python and JS citation formatting agree on `cite_cases.json`;
     - `search.json` holds every city, country, organisation, story and main page, and every URL
       in it resolves in the export;
     - every chart container has a Download control and a Cite disclosure;
     - an exported page that loads `search.json` still passes the M9 reference scan.
   - **node tests:**
     - `permalink.js` restores every schema it writes, and drops bad values to defaults;
     - `cite.js` formats all three formats;
     - search matching handles accents, ranking and the cap;
     - a downloaded SVG holds no `var(` and no `class=`, and carries the attribution text;
     - CSV output carries the preamble and the chart's rows.
   - **Render-pass steps** (`--interact` and `--keyboard`):
     - search and jump by keyboard;
     - a tier-map permalink restores the boundary, tiers and view;
     - open Cite, then copy;
     - trigger each download and check the blob type and size;
     - in both themes, zero axe violations and no console messages.
   - **Manual:** open a downloaded SVG and PNG and look at them. Paste a BibTeX entry into a
     BibTeX parser and a CSL-JSON entry into a CSL processor, if one is at hand.
8. **Unchanged.**
   - No displayed number, run, classifier or database change.
   - No new runtime host, no npm package and no build step.
   - The ODbL / OSM attribution stays on every page and is in every download.
   - The live app and the static edition keep the same templates and behave the same.
   - The M10 accessibility bar applies to every new control.

## 4. Components

- `templates/sources.html` (new), `_nav.html` (Sources link, search box), `index.html` (links to
  Sources and Differences; header links), the chart-bearing templates (Cite and Download
  controls), `city/_header.html` (keynum Cite).
- `src/velometer/app/sources.py` (new): builds the Sources rows from the sources registry, the
  organisation profiles, `differences.yaml` and the Figures data.
- `src/velometer/app/cite.py` (new): the citation fields and the server-side text.
- `main.py`: the `/sources` and `/data/search.json` routes; citation JSON in page contexts.
- `export.py`: the export URL list gains `/sources` and `/data/search.json`.
- `content/models.py` and `check.py`: `group` and optional `dimensions` on sources, plus the
  completeness check.
- `config/report.yaml` (labels), `config/cities.yaml` (aliases), and the model that reads it.
- `static/js/cite.js`, `download.js`, `permalink.js` and `search.js` (new), with node tests.
  `map.js` and `story.js` read and write permalink state. `chart.js` mounts the controls.
- `static/app.css`: the cite, download and search styles, from tokens.
- `tools/render_pass.py`: the new interact and keyboard steps.
- Tests: `tests/test_m11.py`, `tests/cite_cases.json`, and node tests per module.

## 5. Error handling

- A missing or broken source profile shows a note in its row ("profile could not be loaded"),
  never a 500. The content check already fails before that ships.
- A failed copy falls back to selecting the text, plus an announced instruction.
- A failed download (no canvas, blob error) is announced through the live region, with the
  error in the console. The other formats stay available.
- If `search.json` fails to load, the box still links to `/cities` and the failure is logged
  once.
- Bad permalink values fall back to defaults silently. That is the documented behaviour, not
  an error.

## 6. Testing

See decision 7. Every feature has a test that fails without it. Rule tests assert rules
(completeness, linkage, round-trips, self-containment), not today's values. The one exception
is the fixed id list that guards CSV and `series.json` compatibility, which is its purpose.

## 7. Global constraints (project rules that bind M11)

- OSM figures are "mapped km" (ADR 0006). No construction verbs for OSM figures, including in
  citation titles and download source lines.
- Licences (ADR 0008): ODbL attribution in every download and every citation.
- The app's only external host stays `tile.openstreetmap.org`. No npm packages, no build step.
- Never write `velometer.sqlite`. Its md5 is unchanged by the whole milestone.
- Never type OSM ids from memory.
- Tests assert rules, not today's values. Each feature has a test that fails without it.
- The M10 rules hold:
  - colours only as tokens;
  - 4.5:1 text and 3:1 non-text contrast;
  - `table.stack` for data tables;
  - a visible focus ring;
  - zero axe violations in the render pass.

## 8. Out of scope

Map downloads; full-text search; a configured canonical site URL (citations use the address the
page is served at); embeds/iframes; a print stylesheet; dark-theme downloads; German UI (M12).
