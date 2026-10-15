# velometer M8: organisations, plans and counters

Status: design approved in conversation 2026-10-07; this spec awaits review.
Builds on M7 (`docs/superpowers/specs/2026-10-06-velometer-m7-design.md`).
Feasibility research: `docs/review/m8-feasibility.md` (2026-10-07).

## 1. Intent

**Outcome:**
- A reader learns who produces each figure the app compares, how they measure it, and what role
  those figures play in political decisions on mobility.
- A reader sees each city's current cycling plan and its reported progress, and for Berlin can
  follow one plan item across every parliamentary document that reported it, beside the infraVelo
  project record and our mapped km on the planned network.
- A reader sees how much cycling the open counters record in the cities that publish them, set
  beside our mapped km, without the app implying that one caused the other.

**Acceptance:**
- `/organisations`, `/plans`, `/plans/berlin` and the city "Counts" tab render for every
  applicable city at 1280 and 390 px with no horizontal page scroll and no console error; the CSP
  of M7 is unchanged (no new external host).
- `velometer content --check` exits 0 and now also covers organisation profiles and plan data
  (§3.4, §4.5).
- `velometer plans overlay berlin` writes overlay rows for every Berlin LAU snapshot 2018–2026 of
  the report classifier; its recomputed tier totals equal the stored run totals (§4.3).
- `velometer counters load` stores daily totals for the seven cities of §5.1;
  `velometer counters --check` exits 0 (§5.4).
- The gate passes; `timeseries`, `reconcile`, `trust`, `report methodology` and `content` checks
  exit 0.
- User review of profiles, plan data, the overlay result and the counter interpretation is
  approved (review stop, §7).

**Success:**
- A revised figure in a later Drucksache is visible as a revision, not silently overwritten.
- Adding a plan document or a counter year is a data edit plus a reload, not a code change.

## 2. Decisions

### Taken with the user (2026-10-07)

1. One milestone, three parts, in this order: organisations, plans, counters.
2. Counters for every city with an open, licensed counter portal; the paid Eco-Counter API stays
   excluded (HANDOVER §6).
3. Plans: Berlin in depth, including our mapped km measured on the planned network geometry;
   one summary row per plan for the other 20 cities.
4. Organisation profiles for the bodies behind our figures (about 10), not every registry
   publisher.
5. Approved design (2026-10-07): overlay by buffer match with versioned parameters; counters for
   the seven cities with open data; one review stop.

### Taken in design (each stands unless you object at spec review)

6. **Quotes and claims stay external** (M7 decision). Every factual claim about an organisation
   (founding, funding, mandate, political effect) carries a registry citation; every quote is a
   registry excerpt. Our own reading of a source is written as our reading.
7. **"Per Drucksache" means per document.** Berlin's yearly progress reports are Hauptausschuss
   reports ("Rote Nummer"), not Drucksachen; the written questions (Schriftliche Anfragen) are
   Drucksachen. Both are tracked; each figure records its `doc_type` (`drucksache` or
   `rote_nummer`) and the page shows the type. Verordnungen (the Radverkehrsplan) are plan
   documents, not progress reports.
8. **Reported figures are stored as printed.** When two documents disagree for the same plan item
   and year, both are kept; the page shows the latest as current and the others as revisions. A
   figure that looks like a typo (Drs 19/27049, Ergänzungsnetz 2023: 55.1 against a 36.24 km
   total) is stored as printed with a `note`, never corrected silently.
9. **Three Berlin series, three words.** "Reported" (Senate documents), "completed projects"
   (infraVelo measures dataset, status `Abgeschlossen`), "mapped on the network" (ours). The page
   says what the third is not: mapped A+B km on the network are not km completed to the
   Mobilitätsgesetz standard and include infrastructure that predates the plan (ADR 0006). The
   comparable quantity is the change since 1 January 2022, not the level.
10. **Overlay is recomputed from cached snapshots** in the pattern of `report/change.py`
    (re-read, classify with the report classifier, check totals against the stored run), and its
    results are stored, because the app reads only the DB. No new OSM runs.
11. **Overlay parameters are data**: `config/plans/overlay_v1.yaml` (buffer metres, maximum angle,
    minimum covered share). A parameter change is a new version, as with classifier rules.
12. **Counters are context, not outcome.** Counts are "recorded at counter sites", never "cycling
    in <city>". The checker rejects causal wording between counts and km (§5.5). 2020 is marked
    as the COVID year on every counter chart.
13. **Counter index**: per city, base 2019 = 100 (Madrid, whose data start in September 2019:
    2020 = 100). Each year-on-year link uses only sites with at least 90 % valid days in both
    years; links are chained. A year with fewer than 3 qualifying sites has no index value.
14. **Barcelona is a separate series**: the portal publishes monthly average daily intensity per
    day type, not counts; it is indexed the same way but labelled "average daily intensity".
15. **Oslo counters are state counters** (Statens vegvesen), labelled so; no Oslo kommune data.
16. **Licences**: every counter and plan dataset records licence, URL and retrieval date; pages
    show attribution; ADR 0008 gets an M8 note (dl-de-zero-2.0, ODbL, CC BY 4.0, NLOD).
17. **No new cities, no German UI, no publishing** (as M7).

## 3. Organisations

### 3.1 Route

`/organisations`: one section per body, linked from the nav (beside Differences) and from each
Figures-tab row whose source has a profile (`source` → `organisation`).

### 3.2 Bodies

The bodies behind every (city, source) pair in `config/external/figures.csv` and every
reconcile source, plus the Berlin plan and progress publishers: Clean Cities Campaign, European
Cyclists' Federation (QECIO), the BikeNetKit authors, Changing Cities, the Berlin Senate
administration for mobility (SenMVKU, behind Berlin's `official` rows), infraVelo, the
Abgeordnetenhaus (the parliamentary documents), Mobilitätsagentur Wien and the City of Copenhagen
(its `official` row). The mapping is `config/organisations.yaml`: `(city or *, source) →
organisation`. Plan publishers of the other 20 cities and counter publishers are named and linked
on their pages but not profiled.

### 3.3 Profile file

`content/organisations/<id>.yaml`:

```yaml
id: clean_cities
name: Clean Cities Campaign
kind: ngo            # official | ngo | index | research | parliament | agency
sources: [clean_cities_2025]          # figures.csv source ids this body produces
sections:
  - heading: Who they are
    paragraphs: ["... [@cc_about] ..."]
  - heading: How they measure
    dimensions: {scope: ..., kind: ..., length: ..., date: ..., area: ..., method: ...}
    paragraphs: [...]
  - heading: Political role
    paragraphs: [...]
quotes: [{excerpt: cc_report_2025/method, after: 1}]
data_refs: [...]
```

The six dimensions reuse `config/differences.yaml` ids; values are free text, cited.

### 3.4 Checks

`content --check` adds: every profile parses; citations resolve; quotes match excerpts; no
internal source; every figures.csv (city, source) pair, reconcile source and Berlin plan publisher maps to a
profile; numbers obey the
M7 number rules (declared fact or literal).

## 4. Plans

### 4.1 Data

`config/plans/plans.yaml`, one entry per plan:

```yaml
- id: berlin_rvp_2021
  city: berlin
  title: Radverkehrsplan (Verordnung vo19-013)
  adopted: 2021-11-16
  status: current          # current | expired | replaced
  url: ...
  items:
    - id: vorrangnetz
      label: Vorrangnetz
      targets: {2022: 40, 2023: 60, 2024: 100, 2025: 150, 2026: 250, 2027: 250}
      target_kind: km_per_year    # km_per_year | km_cumulative | km_total | share | none
```

`config/plans/reports.csv`, one row per printed figure:
`plan_id, item_id, year, value, unit, quantity, doc_type, doc_id, doc_date, url, locator,
retrieved_at, note`. `quantity` is `implemented_in_year`, `implemented_cumulative`,
`under_construction` or `in_planning`. Berlin rows come from the documents listed in
`docs/review/m8-feasibility.md` §C, read at the page and verified against the PDF text.

The other 20 cities get one plan entry each with `status` and `target_kind` (`none` where the
plan states no km target) and at most a few report rows; a city with no current plan gets an entry
with `status: expired` or `replaced` and the successor named.

### 4.2 Berlin network data

`velometer plans fetch berlin` downloads both WFS layers once into `data/plans/berlin/` with the
retrieval timestamp: `radverkehrsnetz` (network class from `ist_radvorrangnetz`) and
`radverkehrsmassnahmen` (status, `netz_art1..5`, `streckenlaenge`, `bauende`). EPSG:25833 as
served.

### 4.3 Overlay

`velometer plans overlay berlin` (all Berlin LAU runs of the report classifier, 2018–2026):
1. Re-read each run's cached snapshot, classify, clip as `report/change.py` does; require the
   recomputed A–E totals to equal the stored run totals (abort otherwise).
2. For each network class, a way-side in A or B counts as "on the network" over the parts of its
   geometry within `buffer_m` of a network segment whose direction differs by at most
   `max_angle_deg`; a part shorter than `min_part_m` is dropped.
3. Store per run and class: mapped A km, mapped B km, network km (constant per fetch), and the
   overlay version.

Table `plan_overlay(run_id, city_id, network_class, tier, mapped_km, network_km,
overlay_version, network_retrieved_at)`.

### 4.4 Pages

- `/plans`: one row per city (plan, adopted, status, target, latest reported progress with doc
  link); expired plans and plans without a km target are labelled.
- `/plans/berlin`: per plan item, the yearly target against "reported" (each document as its own
  marker; revisions visible), "completed projects" (infraVelo km by `bauende` year) and
  "mapped on the network" (change since 2022-01-01 of A+B km on that class); a document table
  (type, number, date, what it reports, link); a short cited text on why the three differ.
- Berlin's city page links to `/plans/berlin`; the other cities' pages link to their `/plans` row.

### 4.5 Checks

`velometer content --check` (or `plans --check`) adds: every report row's plan and item exist;
targets and reports have units; every URL is https; every `doc_type` is known; Berlin report
rows name a profiled publisher (§3.4).

## 5. Counters

### 5.1 Cities and portals

| City | Portal | Licence | Grain | From |
|---|---|---|---|---|
| Berlin | Senate XLSX `gesamtdatei-stundenwerte.xlsx` | dl-de-zero-2.0 | hourly | 2012 |
| Paris | opendata.paris.fr yearly archives | ODbL | hourly | 2016 |
| Helsinki | City of Helsinki open data | CC BY 4.0 | hourly | 2014 |
| Madrid | datos.madrid.es | CC BY 4.0 | hourly | 2019-09 |
| Vienna | data.gv.at | CC BY 4.0 | daily | 2013 |
| Oslo | Statens vegvesen traffic API | NLOD | hourly | per site |
| Barcelona | Open Data BCN | CC BY 4.0 | monthly average daily intensity | 2017 |

Exact URLs are in `config/counters.yaml` (portal, licence, adapter). The other 14 cities get a
note "no open counter data found" with the portals checked (from the feasibility log).

### 5.2 Storage

Raw downloads in `data/counters/<city>/` (git-ignored). Tables:
`counter_sites(city_id, site_id, name, lat, lon, source, licence, first_day, last_day)` (lat/lon
nullable: Vienna) and `counter_daily(city_id, site_id, day, count, complete)`, where hourly data
are summed to days and `complete` means all 24 hours present. Barcelona goes to
`counter_monthly(city_id, site_id, month, day_type, avg_daily)`.

### 5.3 Index

Per §2.13: daily validity = `complete`; a site qualifies for a link when both years have at least
90 % valid days; link ratio = sum of qualifying sites' counts in year t over t−1; chained from the
base year. Stored per city and year with the number of qualifying sites.

### 5.4 `velometer counters --check`

Every configured city has sites and at least one index year; no site appears under two cities;
daily counts are non-negative; the index base year equals 100 when at least `MIN_SITES`
sites qualify in it, and has no value when fewer do (§2.13; amended in M13, M8-22).

### 5.5 Pages and wording

- City tab "Counts" (only for the seven cities): index chart beside the A+B mapped-km index
  (2019 = 100) with the COVID marker; site map where coordinates exist (OSM tiles, as M6), else a
  site list; attribution line; fixed text on what counters measure.
- Compare: new metric "counter index" for the seven cities (others shown as no data).
- `content --check` rejects causal verbs linking counts and km ("led to", "because of", "drove",
  "thanks to", "resulted in") in any prose that mentions counters.

## 6. Research

- Organisations: background, funding, methodology and political role per body, from external
  sources only, added to the registry as excerpts; log in `docs/review/m8-organisations.md`.
- Plans: read every Berlin document of the feasibility log §C at the page; confirm the 20 city
  plans (the log's lines are search snippets); log in `docs/review/m8-plans.md`.
- Counters: confirm URL, licence and history per portal by downloading; log in
  `docs/review/m8-counters.md`.

## 7. Execution order

1. Content models and checks for profiles and plans; `config/plans/` schema; DB tables.
2. Research: organisations and plans (in parallel), registry entries, profiles, plan data.
3. Berlin fetch and overlay; overlay rows written.
4. Counter adapters (one per portal), load, index, `counters --check`.
5. **Review stop:** profiles, plan data and Berlin documents, overlay result, counter index and
   wording.
6. Chart additions (node tests) and app: `/organisations`, `/plans`, `/plans/berlin`, Counts tab,
   compare metric.
7. Render check at 1280 and 390 px; docs (HANDOVER §9 M8, CLAUDE.md, ADR 0008 note, rulings);
   final review.

## 8. Testing

- Profile and plan checks red-proofed per rule (missing profile, bad citation, unknown plan item,
  unknown doc type, causal counter wording).
- Overlay on synthetic geometry: a parallel way inside the buffer counts, one outside or at a
  crossing angle does not, a short part is dropped; totals check aborts on mismatch.
- Each counter adapter against a small fixture file in its portal's real format; hourly-to-daily
  completeness; index chaining with a site that drops out; fewer than 3 sites gives no value.
- Routes and no-JS content for the new pages; CSP unchanged.
- Network fetches are `@pytest.mark.slow`.

## 9. Out of scope

- Counter data for cities without an open portal; the paid Eco-Counter API; counter data below
  daily resolution in the app.
- Overlays for cities other than Berlin; segment-level plan status (the network data carry none).
- Changes to approved M7 narratives; classifier changes; new runs; publishing.
