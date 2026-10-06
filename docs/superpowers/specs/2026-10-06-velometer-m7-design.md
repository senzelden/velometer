# velometer M7 design: the reader app, narratives and external sources

- **Date:** 2026-10-06
- **Scope:** a milestone after M6. It has four parts:
  - the app rebuilt as the "hybrid" chosen from the M7 UX spike (§3);
  - city and combined narratives whose quotes come only from external sources (§4);
  - "Why the figures differ": how our mapped km relate to what cities, NGOs and indices report
    (§5);
  - the investigation of eight shifts the spike found unexplained (§6).
- **Inputs:**
  - the UX spike of 2026-10-05/06: three prototypes (Atlas, Workbench, Story-first), 21 draft
    narratives and one combined draft. Reference screenshots are in
    `docs/superpowers/specs/m7-reference/`; the prototype code is kept locally (git-ignored) in
    `.superpowers/m7-prototypes/`;
  - `HANDOVER.md` §1, §10, §11, §12; ADRs 0003, 0006, 0008;
  - the M6 spec and `docs/superpowers/rulings-m6.md` (follow-ups).

## 1. Intent

**Outcome:**
- A reader can find any city, compare any set of cities on one interactive line chart, and read
  what happened in each city and across all 21, without scrolling through one 9,000 px page.
- Every quotation in the app comes from an external source (a city, a parliament, an NGO, an
  index, the press), verbatim, with publisher, date and link. Our own documents are cited as data
  and method, never quoted.
- Where our mapped km and an external figure disagree, the reader sees why: what each counts, how
  it measures length, for which date and area, and whether it reports infrastructure built,
  planned or mapped.

**Acceptance:**
- `velometer serve` renders every route in §3.1 for all 21 cities at 1280 and 390 px with no
  horizontal page scroll and no console error; the only network hosts are the app and OSM tiles.
- The Compare page shows any subset of the 21 cities as lines, small multiples, ranks or a table,
  for every metric in §3.3, LAU or FUA, absolute or indexed (2018 = 100), with the state in the
  URL. Without JavaScript it still shows the table.
- Every city has a narrative and a "Why the figures differ" section; the combined narrative is the
  Stories page. `velometer content --check` exits 0 (§4.4).
- Every quote in `content/` matches a stored excerpt of an external source in
  `content/sources.yaml`, and no source in that file is a velometer document.
- The eight shifts of §6 each have a written explanation or a recorded "no cause found".
- The gate passes, now including `node --test` (§3.5), and the four existing `--check`s exit 0.

**Success:**
- A number in a narrative can never silently disagree with the data: when a rerun moves it,
  `content --check` names the narrative and the fact.
- Adding a city's narrative or a source is a content edit, not a code change.

## 2. Decisions

### Taken with the user (2026-10-05/06)

1. **Layout: the hybrid.** Option A's page structure (top navigation, breadcrumbs, a city page
   with tabs, a dedicated Compare page) is the backbone. Compare gets option B's views (Lines,
   Small multiples, Rank, Table) and its city slide-over panel. Option C's scrolling story is the
   Stories page.
2. **Quotes only from external sources.** Project documents (`docs/`, `HANDOVER.md`, ADRs,
   explanations) may be cited for data and method, never quoted.
3. **External quotes by web research, stored as excerpts.** Per city: official city or national
   reports and parliamentary answers, the Clean Cities 2025 and QECIO reports, and quality press.
   Each quote is a short verbatim excerpt with URL, publisher, publication and access date,
   committed in `content/sources.yaml`. CI checks quotes against the stored excerpts, offline. A
   city with nothing found gets no quote, never an internal one.
4. **Differences between sources: a per-city section plus a general explainer page** (§5).
5. **The unexplained shifts are investigated** way by way (§6).
6. **Charts: our own SVG module with `node:test`**, no npm packages (§3.5).
7. **English only** for narratives and new pages in M7.

### Taken in design (each stands unless you object at spec review)

8. **Server-rendered first.** Every route is a Jinja page with real paths that works without
   JavaScript (tables, text, sources). JS enhances: charts, filters, the slide-over, story steps.
   This keeps the M4 read-only FastAPI app and its cache.
9. **One JSON endpoint for charts:** `/data/series.json`, the spike's `data.json` shape (series
   per city and boundary, tiers, presets, flags, Bezirk series), cached by the existing
   fingerprint. The CSV downloads stay as they are.
10. **Vega leaves the app.** City charts move to the new module; the three vendored Vega bundles
    and the `vega` macro are removed from `static/` and templates. altair stays for the PNG
    charts in `docs/review/` (Python side, unchanged).
11. **A Content-Security-Policy header** on every response (`default-src 'self'`, images also
    from `tile.openstreetmap.org`, no inline script). This closes the M6 follow-up; inline
    `<script>` blocks move to static files.
12. **Narratives are content, not code:** `content/narratives/<city_id>.yaml`,
    `content/narratives/combined.yaml`, `content/sources.yaml`, validated by Pydantic models.
13. **Numbers in narratives are declared facts.** Each narrative lists the facts it uses (an
    expression into the report data and the value as printed). `content --check` recomputes them
    from the database and fails when one no longer rounds to the printed value. Every number in a
    paragraph must be a declared fact, a year, or inside a quote (§4.3).
14. **The same wording rules as ADR 0006, now enforced in content:** outside quotes, no
    construction verb for OSM figures ("built", "constructed", "opened", "removed"). Inside a quote
    the source's words stand, attributed.
15. **A review stop before the app work.** After research, investigation and drafting, the
    source registry, the eight shift findings and all 22 narratives go to you in one review, as
    M6's Task 14 did. Nothing is drafted twice: the app tasks only render what you approved.
16. **Excerpts are short and attributed** (quotation right): at most 60 words per excerpt, the
    full citation always shown. ADR 0008 gets an M7 note. Full page texts are never committed.
17. **The app stays private on 127.0.0.1** (HANDOVER §12 Q4 stays open). M7 does not publish.
18. **The prototype code is a reference, not a source.** Implementers port behaviour and layout
    from `.superpowers/m7-prototypes/`, but every line in `src/` is written to the repo's
    standards and tested.

## 3. The app

### 3.1 Routes and navigation

Top navigation on every page: **Overview · Compare · Cities ▾ · Stories · Methodology**, with
breadcrumbs and a marked current item. The Cities menu groups cities by country and filters as you
type; on phones it sits in a menu button.

| route | content |
|---|---|
| `/` | Overview: the headline ranking, key numbers across the 21 cities, cards leading to Compare, Stories and the cities |
| `/compare` | the comparison tool (§3.3); query params `c, m, b, mode, view, hl` |
| `/cities` | all cities by country, each with a sparkline and its headline |
| `/city/<id>` | the city page, tab **Story** (narrative, key numbers, small headline chart) |
| `/city/<id>/time` | tab **Over time**: headline and tiers per year, LAU and FUA, flagged years with their explanations |
| `/city/<id>/tiers` | tab **Tiers**: tier composition over time, the tier map |
| `/city/<id>/figures` | tab **Figures**: "Why the figures differ" (§5), the reconciliation table, official and reported figures, sources |
| `/city/<id>/bezirke` | tab **Bezirke** (cities with subareas only): Bezirk table, small multiples, change map |
| `/city/<id>/panel` | HTML fragment for the Compare slide-over (no layout) |
| `/stories` | the combined narrative as a scrolling story (§3.4) |
| `/differences` | the general explainer (§5.2) |
| `/methodology`, `/methodology/de` | unchanged |
| `/data/*.csv`, `/data/series.json` | downloads and chart data |

`/city/<id>` keeps its URL, so links to today's pages still land. The city header (name, country,
residents, five key numbers) is compact on phones (one line of numbers, scrollable).

### 3.2 City pages

The Story tab sets the narrative beside a key-numbers box and a small headline chart that links to
Over time. Every tab has a "Compare this city with…" control that opens Compare with this city and
the chosen ones. The Bezirke tab takes over M6's Bezirk section and change map unchanged in
content (the remainder row rules stay as recorded in M6).

### 3.3 Compare

- **Filters** (a bar on wide screens, a sheet on phones): cities (checkboxes by country; quick
  sets All, Pilot 5, Nordic, DACH, West & South, Central & East), metric (headline; A+B km; each
  tier A–E; QECIO method; Clean Cities method; A+B km per 100k residents, LAU only), boundary
  LAU/FUA, mode absolute or indexed 2018 = 100.
- **Views:** Lines, Small multiples (shared or own y scale), Rank (rank per year among the
  selected cities, saying that ranks depend on the selection), Table (sortable; the no-JS
  fallback).
- **Lines:** up to 8 cities in colour, more as grey context with up to 8 highlighted; a city
  keeps its colour while others change; end labels that never overlap; hover dims the others and
  shows the exact value; ringed points mark flagged years, and clicking one opens its explanation.
  The x axis is 2018…2026 plus "Oct 2026" for the current run.
- **Slide-over:** clicking a line or city opens `/city/<id>/panel` beside the chart (tiers chart,
  key numbers, flagged years, link to the full page); Escape and Back close it.
- Near every chart: "Mapped km in OpenStreetMap, not built km" and the headline definition.

### 3.4 Stories

The combined narrative as a long read with a sticky chart that changes per section (all cities →
leaders → the tail → indexed growth → jumps → Berlin Bezirke). Each section in
`combined.yaml` names its chart step explicitly (`step:`), so text and chart never drift (the
spike assigned them by position). Every step has "Explore this chart", which opens Compare with
the same state. `prefers-reduced-motion` turns transitions off; without JS the sections render as
text with static tables.

### 3.5 The chart module and its tests

- `static/js/chart.js`: lines, small multiples, rank and sparkline layouts as pure functions
  (data in → SVG description out) plus a thin DOM layer. `static/js/compare.js` keeps the URL in
  sync with the filters; `static/js/story.js` drives the steps; `static/js/panel.js` the
  slide-over.
- `node --test src/velometer/app/static/js/tests/` covers the pure parts: scales and ticks, index
  computation (2018 = 100, missing years), rank computation with ties, end-label de-overlap,
  colour stability, URL state parse/serialise round trip. Node's built-in runner only; no
  `package.json`, no dependencies.
- Python tests cover routes, templates, the panel fragment, the JSON endpoint, CSP and the no-JS
  content of every page.

## 4. Narratives and sources

### 4.1 The source registry, `content/sources.yaml`

Each source: `id`, `publisher`, `title`, `url`, `published` (date or null), `accessed` (date),
`language`, `kind` (`official` | `parliament` | `ngo` | `index` | `press`), `archive_url`
(Wayback Machine copy when one exists or can be made) and `excerpts`. Each excerpt: `id`, `text`
(verbatim, ≤ 60 words, original language), `gloss_en` (English rendering when not English),
`locator` (page, section or paragraph). The model refuses a `url` or `id` pointing into this repo
or to velometer pages.

The existing `config/external/figures.csv` notes that hold verbatim official text (Berlin Senate,
dpa, Tagesspiegel, Copenhagen, Vienna) become registry entries; the CSV keeps its figures.

### 4.2 Research

Web research per city, by region in parallel: city and national cycling reports and plans,
parliamentary answers, Clean Cities 2025 and QECIO v2.10/2.1 (definitions), and quality press.
Each excerpt is copied from the fetched page and checked against it at research time; the
researcher records `accessed`. Sources that need a login or were not reached are listed in the
review with the reason, never quoted from memory or from a secondary paraphrase.

### 4.3 Narrative files

`content/narratives/<city_id>.yaml` (and `combined.yaml`): `title`, `dek`, `sections` (each:
optional `heading`, optional `step` for the story, `paragraphs`), `quotes` (each: `excerpt` id,
`after` paragraph), `facts` (each: `id`, `expr`, `printed`), and `data_refs` (citations of our own
data or method: run set, explanation heading, reconciliation row; rendered as "velometer data"
citations, never as quotes). Paragraph text uses `[@source_id]` for external citations and
`[#data_ref]` for our data; numbers are written as printed and must be declared facts.

`expr` is a small, safe path language over the report data, for example
`series.berlin.lau.current.headline`, `series.berlin.lau.2018.ab_km`,
`index.krakow.lau.current.ab_km` (2018 = 100), `rank.berlin.lau.current.headline`,
`denominator.warsaw.lau.2025` (A+B km ÷ headline × 100), `bezirk.berlin.neukoelln.current.headline`,
`change.berlin.default.gained`. Unknown paths are an error.

Every narrative includes, besides the development since 2018, a short paragraph on how its
figures relate to external ones (pointing to the Figures tab), and states a cause for a jump only
where an explanation (ours, cited as data) or an external source supports it.

### 4.4 `velometer content --check`

Read-only, exits 1 on any failure, listing each:
- schema errors; unknown source, excerpt or data-ref ids; a quote whose text is not exactly its
  excerpt; a registry source inside the repo;
- a fact whose recomputed value no longer rounds to `printed`; an undeclared number in a
  paragraph (years 2000–2099, ordinals, and numbers inside quotes are exempt);
- construction verbs outside quotes (§2.14);
- a city without a narrative, a narrative without a Figures paragraph, a `step` the story does
  not define.

A `--online` mode (marked `slow`, deselected by default) re-fetches each source URL and reports
excerpts no longer found, for a re-verification pass before any publication.

## 5. Why the figures differ

### 5.1 Per city (`/city/<id>/figures`)

For each external figure about the city (Clean Cities, QECIO, BikeNetKit, official and reported
figures), one row: our closest figure, theirs, the gap, and the drivers of the gap along fixed
dimensions:

| dimension | what differs | example |
|---|---|---|
| what is counted | network scope and infrastructure types | Berlin's Vorrangnetz (≈ 870 km planned) vs all cycle infrastructure; Clean Cities counts protected infrastructure only |
| what kind of km | built/completed, planned/target, mapped | Senate "completed in 2025" vs mapped km in OSM at a date |
| how length is measured | per road side, centreline, route length (Streckenlänge) | per side vs centreline roughly halves two-sided streets |
| when | reference date and counting date | completion year vs the date a mapper drew it; Clean Cities May 2025 vs our Oct 2026 |
| where | boundary | QECIO NUTS3 region vs city proper |
| who measured | city-submitted, survey, OSM-derived | Clean Cities used city figures for most cities |

The drivers come from data where possible (`network_scope`, `length_basis`, `reference_date`,
the reconciliation `basis`), classified in a small `config/differences.yaml` (metric → kind of km;
basis → length method). Each city narrative's `figures` section adds the prose, quoting the
external source's own definition where one exists. Where a source states no basis, the page says
"basis not stated by the source".

For Berlin the section sets out, side by side: the Senate's yearly "new cycle infrastructure" km,
the Vorrangnetz implemented and target km, the Radverkehrsnetz completed share, Changing Cities'
count, and our mapped change for 2023 → current (gained, redrawn, net). It explains that the
Senate counts completed projects in a defined network as route length at completion, while we
count all mapped infrastructure per road side when mappers record it, so the two answer different
questions and neither confirms or refutes the other.

### 5.2 The explainer page (`/differences`)

The six dimensions once, each with a worked example from the 21 cities and the external sources'
own definitions as quotes (QECIO Table 2, the Clean Cities method, the Senate's definitions where
published). It links to every city's Figures tab.

## 6. The eight shifts

Investigated way by way from the cached snapshots, like the M3–M6 explanations:

| shift | observed |
|---|---|
| Bratislava LAU 2019 → 2020 | A+B 132 → 113 km |
| Stockholm LAU 2018 → current | A 315 → 415 km while B 629 → 577 km |
| Budapest LAU 2023 → 2024 | D 118 → 153 km |
| Ljubljana LAU 2026-01-01 → current | A+B 228 → 245 km |
| Amsterdam LAU 2024 → 2025 | about 44 km from A to B, A+B flat |
| Copenhagen LAU 2025 | B dips to 74 km and recovers in 2026 |
| Warsaw LAU 2024 → 2025 | main-road km 1,039 → 946 (headline up 14 % on A+B +4 %) |
| Helsinki LAU 2024 → 2025 | main-road km 467 → 484 (headline down, A+B flat) |

Findings go to `docs/review/shifts.md` (one `###` heading each, the explanation style of
`m3_timeseries.md`). Narratives cite them as data. Whether main-road (denominator) jumps should
become a flag rule is recorded as a follow-up; M7 does not change flag rules.

## 7. Execution order

1. Content models, the fact path language, `content --check` (with fixtures), `config/differences.yaml`.
2. Source research per region (four groups in parallel), registry entries, migration of the
   figures.csv quotes.
3. The eight shift investigations.
4. Narratives: 21 cities and the combined one, drafted against the registry and the data.
5. **Review stop:** registry, shift findings, narratives.
6. The chart module and its `node:test` suite.
7. App: navigation and base layout, Overview, Cities, city tabs, Figures and the explainer, the
   JSON endpoint, CSP, Vega removal.
8. App: Compare (views, filters, slide-over) and Stories.
9. Render check at 1280 and 390 px, docs (HANDOVER §9 M7 entry, CLAUDE.md gate and latest line,
   ADR 0008 note, rulings), final review.

## 8. Testing

- `content --check` red-proofed per rule: an altered quote, an internal source, a stale fact, an
  undeclared number, a construction verb, a missing narrative, an unknown step.
- Fact paths: every path family against the fixture DB, including `denominator` and `index`.
- Routes: every route for a fixture city and for Berlin (Bezirke tab), at least one city without
  subareas (no Bezirke tab), 404s for unknown cities and tabs; the panel fragment has no layout.
- CSP present on every response; no inline script in any template.
- No-JS: each page's essential content (tables, narrative, sources) is in the HTML.
- `node --test`: the pure chart functions as listed in §3.5, each with a boundary case.
- The render check is manual (screenshots), as in M5 and M6.

## 9. Out of scope

- Publishing the app (HANDOVER §12 Q4), German narratives, new cities.
- New flag rules (the denominator flag is a follow-up), classifier changes (the M6 `foot`
  gap stays parked for v5).
- Changes to the pipeline, runs or the database schema beyond what the content check reads.
