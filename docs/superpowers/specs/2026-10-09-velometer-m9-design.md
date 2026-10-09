# velometer M9 — the static edition (design)

Status: approved by the user 2026-10-09 (conversation design, sections 1–8 below).
Follows M8 and its follow-up pass (main at 484e9d8).

## 1. Purpose

Make the reader app publishable without publishing it. M9 produces a static edition of the whole
app — HTML, JSON, CSV, PNG, GeoJSON and assets — that any static host can serve under any path,
built from the existing FastAPI app so there is one template set and no drift. Nothing is uploaded
anywhere (HANDOVER §12 Q4 stays open: the user decides later when and where it goes live).

Main reader for M9–M12: journalists and researchers (desktop, depth: compare, tables, CSV,
methodology). The static edition must keep everything they use today working.

## 2. Roadmap this milestone opens (user decision 2026-10-09)

Four milestones in sequence, each with its own spec, plan and reviews; later ones are built and
tested inside the static edition:

- **M9** static edition (this spec).
- **M10** polish and accessibility: full dark theme with a render pass of every page, Figures
  tables usable on phones, WCAG 2.1 AA audit with fixes.
- **M11** reader features: "cite this figure" blocks, chart download (SVG/PNG plus the rows
  behind it as CSV), permalinks to state on city pages, search / jump to city.
- **M12** German edition: German UI strings and German narratives, explainers and profiles
  beside English under `/de/`; Claude drafts, the user reviews the German text at one stop; the
  content check runs per language; quotes stay in their original language.

## 3. Decisions

1. **Export by rendering the app.** `velometer app export --out <dir> [--base <path>]` renders
   every exported URL through the FastAPI app in-process (Starlette TestClient, no network, no
   server) and writes the response bodies to files. There is no second renderer.
2. **Directory-style files.** A page URL `/x/y` is written to `<out>/x/y/index.html`; `/` to
   `<out>/index.html`. Non-HTML responses keep their URL path as the file path
   (`/data/series.json` → `<out>/data/series.json`, `/maps/berlin_2026.png` →
   `<out>/maps/berlin_2026.png`, `/data/berlin.csv` → `<out>/data/berlin.csv`). Static assets
   under `/static/` are copied as files. A `404.html` is written from the app's 404 response.
3. **Base path, not link rewriting.** Every internal URL in templates goes through one helper,
   `u(path)`, that prefixes the configured base path (default `/`). The live app runs with base
   `/` and its HTML is byte-identical to today apart from the CSP meta tag (decision 6). JS
   reads the base from `<meta name="velometer-base" content="…">` for every fetch
   (`data.js`, `panel.js`), every `history` URL (`compare.js`) and every link it builds. No
   post-render HTML rewriting. The base is normalised to start and end with `/`.
4. **The exported URL list comes from the data.** One function enumerates the URLs: `/`,
   `/cities`, `/compare`, `/stories`, `/differences`, `/organisations`, `/plans`,
   `/plans/<id>` for each city with a plan page, `/methodology`, `/methodology/de`,
   `/city/<id>` and `/city/<id>/<tab>` for every city and every tab the app serves for it,
   `/city/<id>/panel`, `/data/series.json`, `/data/all.csv`, `/data/<id>.csv` and
   `/data/<id>_subareas.csv` where the app serves them, and every map file the city pages
   reference. URLs the app answers with 404 (for example a tab a city does not have) are not
   written and are not linked.
5. **Completeness is proven, not assumed.** After writing, the export scans every exported HTML,
   CSS and JS file for internal references (href, src, fetch targets, CSS url()) and fails if
   any does not resolve to a file in `<out>`. External references other than
   `tile.openstreetmap.org` fail the export.
6. **CSP survives without headers.** `base.html` carries the app's policy as
   `<meta http-equiv="Content-Security-Policy" content="…">`, generated from the same constant
   the header middleware uses (directives a meta tag cannot carry, such as `frame-ancestors`,
   are left to the header and documented). The live app keeps sending the header.
7. **Query-string pages.**
   - **Compare** is exported with its default selection. With JavaScript, `compare.js`
     already rebuilds any `?…` state from the URL; the exported page must do the same under a
     non-root base. Without JavaScript the static edition shows the default selection and the
     lede says so in one line (the live app keeps its server-side form behaviour).
   - The compare form and the city header's compare form keep `method="get"` and point at
     `u("/compare")`, so a static host serves the default page and JS applies the query.
   - Internal URLs keep the app's paths without a trailing slash (`u("/city/berlin")`). A
     static host serves `/city/berlin` from `city/berlin/index.html` by its directory redirect,
     which keeps the query string; the render pass checks this with `python -m http.server`
     and the deployment note in HANDOVER states the requirement for other hosts.
   - **City panels** (`/city/<id>/panel`) are exported as static fragments fetched by
     `panel.js`.
8. **Build stamp.** The export writes `<out>/build.json` with the git commit (short and full),
   whether the tree was dirty, the classifier version(s), the OSM snapshot timestamps of the
   exported runs, the base path and the build time (UTC). Every exported page's footer shows
   one line: "Static edition · build <short commit>". The live app shows no such line.
9. **Read-only.** The export opens `velometer.sqlite` read-only (as the app does) and never
   writes it; its md5 is unchanged by an export. It refuses to write into a non-empty `<out>`
   unless `--clean` is given, and `--clean` removes only a directory that contains a
   `build.json` written by a previous export (never an arbitrary directory).
10. **No hosting in M9.** No upload, no CI deploy, no domain. `dist/` stays git-ignored.

## 4. Components

- `src/velometer/app/urls.py` (new): base-path normalisation and `u()`; the Jinja global; the
  `velometer-base` meta value.
- `src/velometer/app/export.py` (new): URL enumeration (decision 4), rendering through
  TestClient, path mapping (decision 2), asset copy, reference scan (decision 5), `build.json`
  (decision 8), `--clean` guard (decision 9).
- `src/velometer/cli.py`: `app export` command (options `--out`, `--base`, `--clean`, `--db`).
- `src/velometer/app/main.py`: app factory takes `base_path` (default `/`), registers `u()`,
  exposes the CSP constant for the meta tag.
- Templates: every internal `href`/`src`/`action` through `u()`; `base.html` gets the two meta
  tags and the static-edition footer line (only when the app is built for export).
- JS: one `base()` helper (in `state.js` or a new tiny module) used by `data.js`, `panel.js`,
  `compare.js`, `nav.js` and any script that builds an internal URL.

## 5. Error handling

- An exported URL that answers anything but 200 (other than the deliberate 404 page) fails
  the export with the URL and status.
- A broken input that the app already turns into a visible note (M8 follow-ups Task 2) is
  exported as that note, not as a failure.
- A missing `velometer.sqlite` or wrong schema version fails with the app's existing message.
- The reference scan lists every unresolved reference with the file that contains it.

## 6. Testing

- Unit: base normalisation; `u()`; path mapping; URL enumeration against a fixture DB (every
  enumerated URL returns 200; a city without a tab does not get that tab).
- Equality: for every exported HTML page in the fixture export, the file equals the live app's
  response for the same URL with base `/`, apart from the static-edition footer line.
- Base path: an export with `--base /velometer/` has no internal reference that starts with
  `/` without that base (rule over all exported files); the reference scan passes.
- CSP: every exported HTML file carries the meta tag, equal to the header policy minus
  header-only directives.
- JS (`node --test`): the base helper; fetch and history URLs built under a non-root base.
- Read-only: md5 of the fixture DB unchanged by an export; `--clean` refuses a directory
  without a previous `build.json`.
- Render pass (headless Chrome, not in the gate): serve the real export with
  `python -m http.server --bind 127.0.0.1` under base `/velometer/`; every page type at 1280
  and 390 px; no horizontal scroll, no console errors, no CSP violations, no request to a host
  other than 127.0.0.1 and `tile.openstreetmap.org`; compare with a `?…` state in the URL draws
  that state; a city panel opens from compare.

## 7. Global constraints (unchanged project rules that bind M9)

- No pipeline, classifier, run or DB change; no displayed number changes.
- OSM figures are "mapped km" (ADR 0006); no construction verbs for OSM figures.
- The app's only external host stays `tile.openstreetmap.org`; no npm packages, no build step
  for JS/CSS (the export is a copy, not a bundle).
- Licences (ADR 0008): the static edition carries the same attribution lines as the app; the
  ODbL / OSM attribution in the footer stays on every page.
- Tests assert rules, not today's values; each fix has a test that fails without it.

## 8. Out of scope

Hosting and publishing; embeds and chart downloads (M11); dark theme and accessibility (M10);
German UI (M12); server-side compare states in the static edition beyond the default; search.
