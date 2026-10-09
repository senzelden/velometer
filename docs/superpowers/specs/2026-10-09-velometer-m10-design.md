# velometer M10: polish and accessibility (design)

Status: approved by the user on 2026-10-09 (conversation design, sections 1–8 below).
Follows M9, the static edition (main at 83eeef1). Roadmap: M9 spec §2.

## 1. Purpose

Make the reader app comfortable and usable by everyone who reads it. That means a dark theme
that follows the reader's OS, wide tables that work on a phone, and WCAG 2.1 AA conformance,
proven page by page. The main readers are still journalists and researchers, so nothing they
use today may get worse: compare, tables, CSV and methodology.

## 2. User decisions (2026-10-09)

- **Dark theme trigger:** follow the OS (`prefers-color-scheme`) only. There is no toggle.
- **Tier colours:** one palette, defined once. The tier-map PNGs are re-rendered with it.
- **Phone tables:** below 600 px, wide tables stack into cards.
- **Audit:** axe-core, dev-only and never shipped, plus pytest rule tests and a manual
  keyboard pass.

## 3. Decisions

1. **Theme by tokens and the OS.**
   - `app.css` keeps one custom property per colour role on `:root`.
   - A `@media (prefers-color-scheme: dark)` block redefines every colour token, and `:root`
     declares `color-scheme: light dark`.
   - The dark values start from the draft in commit 08cd96a and must pass decision 7's
     contrast rules.
   - The raw `rgb(0 0 0 / x)` shadows become a `--shadow` token (one value per theme).
   - No colour literal remains outside the two token blocks, and the existing hex rule
     extends to `rgb()`/`hsl()`.
2. **JS colours come from CSS.**
   - These become tokens that the JS reads from computed style when it draws:
     - the series palette (`PALETTE`, data.js);
     - the tier colours (`TIER_COLOURS`, chart.js);
     - the context grey (`CONTEXT`, compare.js);
     - the axis and label greys and the white halo in chart.js;
     - the counter-map markers (countermap.js).
   - The series palette is `--series-1` … `--series-8`, the tiers `--tier-a` … `--tier-e`.
   - Charts and maps redraw when `matchMedia('(prefers-color-scheme: dark)')` changes.
   - A chart's SVG carries resolved colour values, so a saved SVG looks as it did on screen
     (this matters for M11 downloads).
3. **One tier palette.**
   - `velometer.report.charts.TIER_COLOURS` is the single source.
   - The light-theme tier tokens in `app.css` must equal it (a test, like the existing
     series-palette test).
   - The dark tier tokens exist only in CSS.
   - The Leaflet tier map reads the tokens; main.py stops sending tier colours in the map
     config.
   - The palette is chosen by rule, not by taste. Every tier is at least 3:1 against the map
     and chart background in both themes. Every pair of tiers is at least ΔE 20 apart
     (CIEDE2000, a 0–100 colour-difference scale) in normal vision and under simulated
     deuteranopia and protanopia. Adjacent tiers (A–B, B–C, C–D, D–E) must be at least
     ΔE 25 apart.
   - Today's JS chart palette and Python map palette disagree. After M10 the same tier has
     the same colour everywhere.
   - The change map's `CATEGORY_COLOURS` are fixed at their current values, independently
     of the tier palette. The change maps are therefore not regenerated and look the same.
   - The tier-map PNGs are re-rendered with `velometer report maps`. It reads the DB
     read-only, and `data/maps` is git-ignored. This is an operations step that HANDOVER
     records, alongside a check that every PNG is newer than the palette change.
4. **Images and tiles in dark.**
   - The server-rendered PNG maps stay light. In dark mode they sit on a light `--plate`
     background with a border so they read as figures.
   - The OSM tile layer gets a dark CSS filter (invert, hue-rotate, reduced brightness and
     contrast) in dark mode. Tier lines, outlines and markers stay at full colour above it.
   - No new host or tile provider.
5. **Phone tables stack into cards.**
   - Below 600 px, wide data tables render each row as a card of `label: value` lines.
   - Templates put the column header on each cell as `data-label` (server-side, no JS),
     generalising the existing `.diffs` pattern. JS-built tables (compare table view) set
     the same attribute.
   - This covers:
     - the three Figures tables;
     - the overview key numbers and rankings;
     - the compare table view;
     - the city year tables behind charts (`Table: …` details);
     - plans, counts and counter-site tables, whose current phone rules are replaced by the
       one pattern.
   - Prose tables in methodology and explainers keep their scroll box. They are the only
     tables allowed to scroll sideways.
   - Sorting, `aria-sort` and table semantics stay intact: the cards are CSS, not new
     markup.
6. **WCAG 2.1 AA fixes.**
   - **Skip link and target.** A skip link is the first focusable element and targets
     `<main id="main">`.
   - **Focus ring.** A visible `:focus-visible` ring on every focusable element, from a
     `--focus` token with at least 3:1 contrast against adjacent colours in both themes.
   - **Live announcements.** One polite `aria-live` region announces city-panel loading and
     load errors and compare redraws ("Showing 3 cities, A+B km, indexed").
   - **Data behind every chart.** Every chart has its data as a table in the page (a
     `Table: …` details block or an adjacent table). The chart's SVG keeps its `<title>`.
   - **Not colour alone.**
     - Flagged rows and points carry the flag text marker as well as the colour.
     - Ups and downs carry a sign.
     - Tier lines in charts have a key, and tier-map sides name their tier in the popup.
   - **Headings.** The panel fragment and stories have no skipped heading levels and one
     `h1` per page.
   - **Language.** German passages outside `/methodology/de` (quotes in narratives) carry
     `lang="de"`. The content renderer keeps a `lang` attribute on quotes
     (`<blockquote lang="…">`, `<q lang="…">`), and every existing non-English quote in
     `content/` is marked. The content check fails if a `lang` value is not a BCP 47 tag.
   - **Reflow.** Every page works at 320 CSS px wide (WCAG 1.4.10) and with the 1.4.12 text
     spacing overrides, without loss of content.
   - **Tabs.** The city and compare tabs stay links with `aria-current="page"`. That is a
     valid navigation pattern, so they do not become ARIA tabs.
   - **Carried in from M9.** The 404 page's heading spacing matches other pages.
7. **Proof.**
   - **pytest rule tests (in the gate):**
     - contrast of every text/background token pair used in `app.css`, in both themes:
       4.5:1 for text, 3:1 for large text and non-text (borders of inputs, focus ring, chart
       lines, tiers against map and chart backgrounds);
     - the tier palette rule (decision 3);
     - the light tier tokens equal `charts.TIER_COLOURS`;
     - no colour literal outside the token blocks;
     - every page has the skip link, `main#main` and landmarks;
     - every chart container on every page has a data table;
     - every cell of a stacking table (decision 5) has `data-label`, equal to its column
       header.
   - **node tests:** charts resolve colours from tokens, and a theme change triggers a
     redraw.
   - **axe-core:** vendored at one exact version into `tools/axe/` with its MPL-2.0 licence
     and a VERSION file. It is never served by the app and never exported (the export copies
     only `static/`; the reference scan and a test prove it).
   - **Render-pass tool:** `tools/render_pass.py` (kept in the repo, reusable for M11 and
     M12) drives headless Chrome over the DevTools protocol (`websocket-client` as a uv
     dev-dependency group). It runs on the exported static edition served by
     `python -m http.server`, over every page type × {light, dark} × {1280, 390, 320} px.
     It records:
     - axe violations for the `wcag2a`, `wcag2aa`, `wcag21a` and `wcag21aa` tags, which must
       be zero;
     - sideways scroll, which must be none apart from prose tables;
     - console errors, CSP violations, and hosts other than 127.0.0.1 and
       `tile.openstreetmap.org`, which must all be absent;
     - screenshots of every page in both themes, shown to the user at the end.
   - **Manual pass:** keyboard only, through the nav, a city's tabs, compare (selection, view
     switch, panel open and close, Escape), a tier map and the counter map. Text spacing
     and 200% zoom spot checks.
   - The render pass needs Chrome, so it stays out of the gate, as in M9.
8. **Unchanged.**
   - No displayed number, run, classifier or DB change.
   - No new runtime host, no npm package and no JS build step.
   - The ODbL / OSM attribution stays on every page.
   - The live app and the static edition keep the same templates. M10 changes both in the
     same way.

## 4. Components

- `static/app.css`: dark token block, new tokens (`--series-3..8`, `--tier-a..e`, `--focus`,
  `--plate`, `--shadow`, axis and halo greys), card tables, skip link, focus ring, tile
  filter.
- `static/js/theme.js` (new): `token(name)` and `onThemeChange(fn)`. data.js, chart.js,
  compare.js, map.js, changemap.js and countermap.js use it.
- `static/js/live.js` (new) or an addition to an existing module: `announce(text)` into the
  page's live region.
- Templates: `base.html` (skip link, `main#main`, live region), table templates (`data-label`),
  panel fragment and stories headings, the 404 page.
- `report/charts.py`: the chosen `TIER_COLOURS`. `report/change.py`: its own fixed
  `CATEGORY_COLOURS`. main.py: the tier map config without colours.
- `tools/axe/`, `tools/render_pass.py`, `pyproject.toml` dev group.
- Tests: a new `tests/test_a11y.py` (contrast, palette, skip link, landmarks, chart tables,
  `data-label`), extended CSS rules in the existing tests, node tests for `theme.js`.

## 5. Error handling

- If a token is missing when JS reads it, the JS throws a named error in development tests.
  In the page it falls back to the light value and logs once to the console. The render pass
  treats any console message as a failure, so a missing token cannot ship.
- If the live region is missing, `announce` is a no-op (pages without dynamic content).

## 6. Testing

See decision 7. Every fix has a test that fails without it. Contrast and palette tests assert
the rule (ratios and distances), not today's colour values, except the one equality between
the Python palette and the light tier tokens, which is the single-source rule.

## 7. Global constraints (unchanged project rules that bind M10)

- OSM figures are "mapped km" (ADR 0006); no construction verbs for OSM figures.
- The app's only external host stays `tile.openstreetmap.org`; no npm packages, no build step.
- Licences (ADR 0008): attribution unchanged; axe-core's MPL-2.0 licence ships with it in
  `tools/axe/`.
- Never write `velometer.sqlite`; its md5 is unchanged by the whole milestone.
- Tests assert rules, not today's values; each fix has a test that fails without it.

## 8. Out of scope

A theme toggle; dark PNG maps; the export's size; M11 reader features (cite, downloads,
permalinks, search); M12 German UI.
