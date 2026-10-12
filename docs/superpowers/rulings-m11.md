# M11 rulings

Reader features (spec `docs/superpowers/specs/2026-10-11-velometer-m11-design.md`, plan
`docs/superpowers/plans/2026-10-11-velometer-m11.md`). These are the controller and implementer
rulings from the SDD ledger (`.superpowers/sdd/2026-10-11-velometer-m11/progress.md`) and the task
reports, in readable form, by task. Each line reads: Ruling — why — cost.

## Pre-flight and Task 1 (Sources overview)

- Ruling: figure sources are figure-source ids mapped to organisations in
  `config/organisations.yaml`, not content Source records; the row group is derived (city `*` gives
  ranking, else city) instead of a new `group` field on sources, and the per-source dimension
  override is dropped (no organisation publishes two differing figure sources today) — spec
  decision 1 assumed the wrong data model, and a derivation cannot drift — cost: a future
  organisation with two differing figure sources needs the override added then.
- Ruling: group headings are "Cross-city rankings and datasets" and "City sources" (not "Official
  city reports") — changing_cities is an NGO monitor — cost: none.
- Ruling: a chart's CSV download is its data table as shown (display headers) plus the two-line
  preamble; the id-stable machine export stays the server CSVs — spec decision 4 said "same column
  ids where one exists", but chart tables do not carry ids and mapping them would add a second
  column vocabulary — cost: scripts should use `/data/*.csv` (documented in HANDOVER).
- Ruling: no "Breslau" alias for Wrocław (historically loaded); aliases only for common English
  exonyms — cost: none.
- Ruling: accept Task 1's red gate, limited to the 19 dangling `/sources` references; Task 2 had to
  turn them green — plan defect: Task 1 links to a page Task 2 creates, and reordering would cost
  more than one red commit on a feature branch — cost: one non-green commit in the m11 history.

## Task 1 (labels)

- Ruling: the overview preset columns are labelled "velometer headline", "QECIO method, our OSM
  data" and "Clean Cities method, our OSM data" in `config/report.yaml` — the label says whose
  method runs on our data — cost: none.
- Ruling: a preset without a configured label falls back to `<id>, our OSM data` — a new preset
  stays honest without a config edit — cost: a plain id as label until configured.
- Ruling: `PresetRanking.recomputes` names the figure source a column recomputes, validated against
  the figure sources — a typo fails at config load, not as a dead link — cost: none.
- Ruling: the Figures-tab `strip_ours` filter strips the `, our OSM data` suffix (it stripped an
  "Ours:" prefix before); Task 2 later fixed its regex for rows that append a basis — cost: the
  old tests asserting "Ours:" labels were updated.

## Task 2 (Sources page)

- Ruling: the anchor of a source with several organisations is `src-<source>-<org>`
  (`src-official-senmvku`, `src-official-copenhagen_kommune`); otherwise `source_anchor(source)` —
  two rows sharing one id would break the HTML and the a11y checks — cost: none.
- Ruling: "Cities" lists the cities whose Figures tab shows a row from that source, taken from
  `difference_rows` and filtered to the owning organisation, not "figure pairs" — QECIO and
  BikeNetKit figures come from the DB through reconcile, and raw external figures over-list (Paris
  has a Clean Cities figure but no run) — cost: a page build runs reconcile once per city (cached;
  the export takes about 10.5 s).
- Ruling: the recomputed column anchor is `col-<preset id>`; ours links to `col-ours_headline`, the
  others show "–" — cost: none.
- Ruling: the "ours" row links "every city" to `/cities` and has no citations — its cells are
  `differences.yaml` `ours` — cost: none.
- Ruling: `recomputes` is validated against the `source` ids of `organisations.yaml` directly in
  `config.py`, so `config.py` does not import the content loader — cost: none.
- Ruling: an h2 "What the cells cite" sits before the cited h3s — the page skipped from h1 to h3 and
  the M10 heading-level test failed — cost: none.
- Ruling: `strip_ours` is fixed to match "our OSM data" followed by a comma or the end — the
  end-anchored version never stripped a real Figures row, because gap rows append a basis — cost:
  none.
- Ruling: controller UX fix round from screenshots: the Cities column collapses to an "N cities"
  disclosure when there are more than 3, and "Recomputed by us" link text names the overview column
  label — rows 20 links tall hurt the meta-study reading — cost: a small round.

## Task 3 (citation fields and formats)

- Ruling: the security finding stands over the reviewer's "URL unescaped is correct" — `}` or `\`
  in a crafted query closes `\url{}` and injects LaTeX — `{ } \` and space are percent-encoded in
  the BibTeX URL, `%` and `#` stay literal (the `url` package), and `\ $ ~ ^` are escaped in title
  and note — cost: none.
- Ruling: fix round 1 was the security fix plus (I1) `None` returns, with `fields_for_cities`
  skipping runless cities, plus (I2) the commit cached per process, plus a multi-city unit test
  (range, same day, classifier join with natural sort), a note-escaping case and the rename of
  `_current_lau_row` — cost: one round.
- Ruling: slugs are `[^a-z0-9]+` collapsed to one `_`, edges trimmed, cut to 40, ASCII only, in both
  languages; the BibTeX and CSL key date is the accessed date, else the snapshot day — pinned in
  `tests/cite_cases.json` so Python and JS cannot drift — cost: none.
- Ruling: with no url there is no `howpublished`/`URL`; with no accessed date there is no
  "Accessed" in the note and no `accessed` in CSL; plain text drops the accessed date when there is
  no url — cost: none.
- Ruling: `fields_for_city` uses the LAU row labelled "current"; a city without a run gives `None`,
  so a page never 500s on it — cost: none.
- Ruling: `fields_for_cities` writes "OSM snapshots of A to B", or "OSM snapshot of A" when all are
  the same day, and joins classifiers with "/" in natural order (v9 before v10) — cost: none.

## Task 4 (Cite)

- Ruling: drop the `.scroll` wrapper for `.cite pre` (pre-wrap, plain) — the dispatch note assumed
  they scroll, and M10's rule is about regions that scroll; a focusable region that never scrolls
  is a useless tab stop — cost: none.
- Ruling: fix round 1 was (I1) a `multi` section in `cite_cases.json` consumed by Python and JS,
  (I2) the scroll-region fix, the slashless-path `absoluteUrl` case, compact CSL-JSON (date-parts on
  one line) and a key-number citation title that names only what it cites (the LAU run) or cites
  both runs — cost: one round; round 2 made the headline-chart titles name only the cited boundary.
- Ruling: the JSON `path` has no leading slash (`cite.json_fields`) — a root-relative string in
  page JSON is a URL the static export must resolve under the base; `absoluteUrl` already strips
  slashes — cost: none.
- Ruling: the Figures-rows test excludes `class="note-row"` rows, and the keynums test splits at the
  next heading because the Cite sits after the list (a non-listitem inside `role=list` breaks axe)
  — cost: none.
- Ruling: if Compare renders with no run for the selected cities there is no Cite until reload (no
  blob to rebuild) — cost: a missing Cite on a degenerate selection.
- Ruling: the ADR 0006 test forbids `build`, `built` and `construct*` in citation text — the ADR
  names only "built" — cost: none.

## Task 5 (downloads)

- Ruling: a chart's CSV is its data table as shown, with display header texts and a two-line
  preamble (see Task 1) — cost: scripts use `/data/*.csv`.
- Ruling: the CSV-injection finding of the security review stands — table text can carry OSM or
  content names — cells starting with `=`, `+`, `@`, TAB or CR get a leading `'`, and so does a `-`
  cell that is not a number (so `-3.2` stays numeric); the rule is `safeCell` in `download.js` and
  `safe_cell` in `report/csvexport.py`, which backs the live and static server CSVs and the CLI
  export, with shared cases tested on both sides — cost: a quote mark on odd text cells.
- Ruling: the downloaded image always uses the light theme (hex tokens from `theme_tokens`), carries
  the title, the source line (OSM date, classifier, commit) and the OpenStreetMap attribution, and
  contains no `var(`, class or style — a saved file leaves the page's CSS and theme behind — cost:
  extra written properties (stroke-width, dasharray, text-anchor) because CSS classes carried them.
- Ruling: `selfContained` walks the live SVG with computed styles, with its own serializer, not a
  clone — computed values are what the reader sees, and hidden elements are dropped — cost: none.
- Ruling: small-multiple containers (several SVGs) are stacked vertically with figcaption titles —
  cost: none.
- Ruling: an HTML key (the tier chart legend) is drawn into the SVG and PNG as a key row — the
  review found the image without it unreadable — cost: width estimated for wrapping.
- Ruling: the download control is not on the cities-page sparklines, and is hidden while its chart
  container is hidden (Compare) — cost: none.
- Ruling: named-colour fallbacks in the JS stay — the colour-literal guard targets hex values, and
  the fallbacks apply only when a token is missing — cost: a stray named colour if tokens go
  missing.

## Task 6 (permalinks)

- Ruling: `read(search, schema, ctx)` takes the allowed kinds as a third argument, not
  `read(search, hash, schema)` from the spec — the brief's signature wins; `ctx` carries the kinds
  — cost: none.
- Ruling: `at` parsing is stricter than the brief (exactly three plain decimal numbers; `1e1`,
  `0x10` and empty parts are rejected) — `Number("")` is 0, so `52,,10` would otherwise pass — cost:
  a hand-typed exotic form is ignored.
- Ruling: the tiers parse sorts and dedupes (`BA` equals `AB`) — a stable comparison against the
  fallback — cost: none.
- Ruling: `kind` is omitted from the URL when it is the first boundary — the default state gives a
  clean URL — cost: none.
- Ruling: the compare panel state helper is `panelOf` in `state.js`, not a `parseState` field —
  existing tests `deepEqual` `parseState` against DEFAULTS — cost: a separate call.
- Ruling: the Copy link fallback inserts a temporary `<pre>` with the address, selected when the
  clipboard is refused and removed on success — `copyText` only selects a matching `<pre>` — cost:
  a brief DOM flicker.
- Ruling: the city Story tab shows Copy link only in the history branch; the tiers one sits above
  the Tier map heading regardless of map presence — placement beside the state — cost: none.
- Ruling: `test_pages_load_our_chart_modules` gained `permalink-ui.js` in its base list — a new
  global module — cost: none.
- Ruling: the Task 5 `fileName` state slug is not passed — it is optional and needs no refactor of
  Task 5 — cost: file names do not follow permalink state.

## Task 7 (search)

- Ruling: `_search` lives in the `--keyboard` pass, not `--interact` — it needs real key events and
  the keyboard steps live there; the required command uses both flags — cost: running `--interact`
  alone does not exercise search.
- Ruling: Enter navigates with `url(\`/${entry.url.replace(/^\/+/, "")}\`)`, not `url(entry.url)` —
  `base.test.mjs` forbids `url()` on a non-literal — cost: a slightly odd expression, commented.
- Ruling: country entries link to `/cities#<iso2 lower>` — the cities page already has these ids on
  its country headings, so no template change — cost: none.
- Ruling: Enter with no active option opens the first result — it matches the Cities filter in
  `nav.js` and is faster; with no match it does nothing — cost: none.
- Ruling: Escape calls `preventDefault` — a `type=search` input clears itself on the first Escape in
  Chrome, which broke "close, then clear" (found by the render pass) — cost: none.
- Ruling: story labels are "The story across cities" (`/stories`) and "The story of <city>"
  (`/city/<id>`), only for trusted cities that have a narrative — a narrative for a city absent from
  the DB would 404 — cost: none.
- Ruling: the fold also maps ø đ ð æ œ ß þ ı explicitly besides ł — København does not decompose
  either — cost: none.
- Ruling: the selected option uses the `--paper` background plus an accent outline, not `--grid` —
  `--accent` and `--muted` on `--grid` fail 4.5:1 (`test_a11y` caught it) — cost: the fill
  difference is low contrast; the outline carries it.
- Ruling: on an index load failure the box is hidden again, the "Find a city" fallback link is
  shown, and one `console.error` is logged — per brief — cost: none.
- Ruling: `nav.js` is unchanged — it has no code that closes the phone menu on focus or Escape, so
  "stays open" holds by construction; the search Escape handler stops propagation so the Cities
  menu's Escape does not fire from the input — cost: none.

## Task 8 (render pass and docs)

- Ruling: the `--keyboard` search step grew to the brief's list (Enter lands on a city, "zzz" shows
  the "No match" option, axe with the list open) as `_search_again`, at 1280 and 320 px — cost: two
  more page loads per width and theme.
- Ruling: the search steps do not hard-code cities: they fetch the site's own `/data/search.json` in
  the page and use its first two cities (first three folded letters of the plain name), so the slow
  fixture test can fail on any search regression — the first version hard-coded Kraków and Vienna,
  which the fixture export lacks, and the test had been relaxed to ignore every `search` error
  (review of Task 8) — cost: a step fails if the index has fewer than two cities.
- Ruling: "No match" is a disabled option, and Down, Up and Enter on it do nothing, proven by a node
  test of the pure `keyAction` — cost: none.
- Ruling: the download step stays on `/city/berlin/tiers`, not `/city/berlin/time` as the brief says
  — that chart has an HTML key and a data table, so the step proves the key row, the CSV and the
  downloaded SVG all at once; Cite stays on `/city/berlin/time` — cost: none.

## Follow-ups

Parked minors, from the ledger:

- Width-dependent end labels for line charts with more than 8 series (the grey context lines are
  unlabelled).
- The `[hidden] + .download` adjacency rule.
- Two-line headline charts cite only the LAU run (the title says so); they could cite both runs.
- `-1e-5` and `-.5` are over-neutralised in the CSVs (safe); the key wrap width is estimated.
- The story `remember` decision could move to `permalink.js` with a node test (the DOM wiring is
  guarded only by the render pass).
- Search: "No match" is an `li` inside the listbox; key dispatch is untested outside `--keyboard`;
  a stale `orgs` pyright hint in `search.py`.
- Sources: the check is silent on `ContentError` by design; the fixture owners are synthetic; the
  content check covers quoted entries only; the series-id check is loose.

Fixed in final wave (after the final whole-branch review, `.superpowers/sdd/2026-10-11-velometer-m11/final-review.md`):

- Parked, now fixed: a cell that is exactly `-`, `–`, `—` or U+2212 is a no-data mark and keeps no
  `'` (`safeCell` and `safe_cell`, tested on both sides); `panel.js` history calls are wrapped in
  try/catch (node test with a refusing `history`); the Copy link box is itself `hidden` until
  `permalink-ui.js` reveals it, so there is no margin gap without JS; clearing the search input
  before the index loads closes the list (the empty-query check runs before the `!index` guard);
  an export-level test resolves every `data/search.json` url to an exported page and its anchor
  under `/velometer/`, and the anchor tests match parsed ids, not a substring `id="x"`.
- Review findings: a Compare or Stories download is titled from its Cite (metric, boundary,
  cities; the current step), else the drawn SVG's label, with the container's generic label last;
  a chart's download source line reads its own Cite (the first after the data table its
  description names, within its section), so a FUA chart names the FUA run; the Compare citation
  and `cite_runs` follow the boundary shown (`fields_for_cities(kind=)`, `RunRows.runs(kind)`,
  `cite_runs` keyed by kind); a citation of another page (the city panel on Compare) cites that
  page's own address without the current query; an open Cite labels its blocks with a `<p>`, not
  an `<h4>`, sets no id, and names each Copy button "Copy <format>, <figure title>"; a resize's
  `moveend` no longer writes `at=` (`readerMoves` in `permalink.js`, a render-pass resize step);
  the search index logs content it leaves out; focus moves to the fallback link when the index
  fails; the three button rules are one; the docs describe the render pass as built.
- Ruling: a generic container prefers its Cite's title over the drawn SVG's label — the Compare
  SVG names metric and boundary but not the cities, the Cite names all three — cost: none.
- Ruling: the render pass's tier-map permalink step reads the boundaries the site offers and
  restores the last one (FUA on the real data), instead of assuming `kind=fua` — the fixture site
  has a LAU tier map only, so the app rightly ignored `kind=fua` and the slow `--interact` test
  failed; its expectation now lists the M11 visits and requires zero errors — cost: on a site with
  one boundary the step proves `tiers` and `at`, not a non-default `kind`.
- Ruling: `absoluteUrl` appends the live query and hash only when the cited path is the page shown
  (`index.html` and slashes ignored) — one rule covers the panel and any future cross-page cite,
  without a template flag — cost: none.

M10 follow-ups this milestone resolved:

- The chart SVG kept axis and label colours on CSS classes, so a saved SVG would differ from the
  screen: resolved, the download writes computed light-theme values (Task 5).

M10 follow-ups left open:

- Light change-map colours under 3:1 on white; dark PNG maps; a colour-blind-safe series palette;
  the `report maps` `.run` marker ignoring palette changes; Figures tables at 200% zoom; screen
  reader testing; the deferred minors and the hosting size (see rulings-m10).
- `regions.py` tag counting inside `<script>` and comments, source-grep tests that could become
  behaviour tests, and `.sr-only` / `.visually-hidden` as one rule twice.

New in M11 and open:

- A German interface is M12.
- HTML legends other than the tier key (if a chart gains one) are not in the downloaded image
  unless they use `.legend .chip`.
- Search covers cities, countries, organisations, stories and pages only; it does not search
  narrative text or quotes.
