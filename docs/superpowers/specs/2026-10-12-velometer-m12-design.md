# velometer M12: German edition (design)

Status: design approved 2026-10-12; spec and plan pre-approved by the user. Roadmap entry: the
M9 spec §2 ("German UI strings and German narratives, explainers and profiles beside English under
`/de/`; Claude drafts, the user reviews the German text at one stop; the content check runs per
language; quotes stay in their original language").

## 1. Purpose

The reader app becomes a complete German edition, served beside the English one. The edition is
for German-speaking journalists and researchers, the same readers as M9–M11. It has the same
pages, the same depth (compare, tables, CSV, citations, downloads, search) and the same guarantees:
every number in German prose is checked against the data like the English prose is. The edition
must never silently fall behind English. When an English sentence changes, its German twin is
reported stale until someone re-translates it.

## 2. User decisions (2026-10-12)

- **Scope: everything.** UI strings and all reader-visible prose: narratives, the explainer, the
  counters and plan explainers, organisation profiles, config prose, flagged-year explanations, and
  glosses for quotes.
- **Review: a side-by-side page.** A private review page shows English and German paragraph by
  paragraph, grouped by page. The user marks lines and leaves notes on it, and Claude reads the
  notes back from it. This is the single user stop of M12.
- **Formats: German on pages.** German pages, charts and downloaded images use German number and
  date conventions. CSV and JSON data and the CSV preamble stay machine-stable in both editions.
- **City names: common German exonyms.** Wien, Prag, Warschau, Kopenhagen, Krakau. Every other
  city keeps its current name. Search finds every form.

## 3. Facts this design rests on (survey of 2026-10-12)

- **Prose volume** (markers excluded, about 12,500 words):
  - narratives: about 8,000 words in 22 files;
  - `explainer.yaml`: 1,045;
  - `counters.yaml`: 320;
  - `plans/berlin.yaml`: 508;
  - nine organisation profiles: 2,636.
- **Quotes:** 345 excerpts. 99 are German, 76 English, 48 French, 23 Polish, and the rest in other
  languages. `gloss_en` is required whenever the language is not English, and totals about 6,800
  words.
- **Flagged-year explanations:** 57 `###` entries, about 7,700 words, in
  `docs/review/m3_timeseries.md`. They are read by `timeseries.py`, shown on city pages and shipped
  in `series.json`, where `compare.js` reads them.
- **UI text:**
  - templates: about 450 text nodes, about 48 `aria-label`/`title` attributes and 54 `data-label`s;
  - Python: about 160 strings that become page text (tabs, metric labels, months, country names,
    notes);
  - JavaScript: about 100 strings (chart labels, announcements, tier names, month names);
  - config prose: `differences.yaml` about 580 words, plus `report.yaml` labels, `presets.yaml`
    bases, plan notes in `config/plans/plans.yaml`, counter notes, and 65 notes in
    `config/external/figures.csv`.
- **Already bilingual:** the methodology, from two hand-written templates with German number
  filters in `report/methodology.py`, plus `limitations.yaml` (`en`/`de`) and `trust.yaml`
  (`basis_de`).
- **`content --check` reads numbers the English way.** In "78,2" it treats the comma as a
  thousands separator, giving 782. Its rule families (construction verbs, causal phrases, number
  words, rule statements) are English regexes.
- **Formatting is English throughout.** `main.py` `_num`/`_when`/`MONTHS`, a second `MONTHS` in
  `compare.py`, `counts.py` month names, and `plans_pages.num`. In JS, `chart-core.js`, `chart.js`,
  `compare.js` and `changemap.js` hard-code `"en-GB"`.
- **One served image carries text:** the tier-map PNG (`report/maps.py`, `/maps/{name}.png`), with
  an English title, legend and footer. The `report charts` and `change` PNGs are CLI outputs and
  are not served.

## 4. Decisions

1. **URLs.** Every HTML page has a German twin under `/de/`: `/de/`, `/de/cities`,
   `/de/city/berlin/time`, `/de/city/berlin/panel`, `/de/sources`, `/de/plans/berlin`,
   `/de/methodology`, and so on. English stays at the root.
   - **Routes.** Each page handler takes `lang` and is registered twice, with the prefixes `""` and
     `"/de"`. `request.state.lang` carries the language. The page-link helper in `urls.py` adds
     `/de` to page links, after the base path, and never to data links.
   - **Data is shared.** `/data/*.csv`, `/data/all.csv` and `/data/series.json` are the same files
     for both editions. `series.json` gains German explanations as an additive field
     (`explanations_de`), with the same keys as `explanations`. The search index is the one
     per-language data file: `/de/data/search.json`.
   - **Images.** The tier-map PNG has a German twin at `/maps/{name}.de.png` (decision 8).
   - **Methodology.** `/de/methodology` serves `methodology.de.md`. `/methodology/de` stays as a
     page that renders the same German text and carries `<link rel="canonical">` to
     `/de/methodology`, because a static site cannot redirect. The nav links to `/de/methodology`.
   - **404.** One `404.html` stays, because a static host serves only one. Its short text is given
     in both languages, each block with its own `lang`.
   - **Language switch.** A "Deutsch" / "English" link in the nav on every page leads to the same
     page in the other language. With JS, the link also carries the current query and hash, so
     permalinks survive a switch. Without JS, it is a plain link to the twin page.
   - **Head tags.** Every page has `<html lang="en|de">`, `<link rel="alternate" hreflang="en|de">`
     for both twins, and `hreflang="x-default"` pointing at English.
   - **Export.** The export writes both trees. Its reference scan and its CSP and host checks
     cover `/de/` exactly as they cover the root.

2. **UI strings.** All interface text lives in `content/ui/en.yaml` and `content/ui/de.yaml`.
   - **Keys** are flat and dotted (`nav.compare`, `city.tab.time`, `js.search.no_match`).
   - **Values** may hold `{name}` placeholders. Counted strings have `one`/`other` forms.
   - **Jinja** gets a global `t(key, **vars)` bound to the page language.
   - **Python** modules that produce page text (`main.py`, `story.py`, `compare.py`, `counts.py`,
     `sources.py`, `cite.py`, `search.py`, `names.py`, `regions.py`, `organisations.py`,
     `plans_pages.py`, `narrative.py`, `report/data.py` `HEADLINE_UNIT`, `report/charts.py`
     `TIER_LABEL` where served) take `lang` and look their text up through the same catalogue.
   - **Country names** move into the catalogue.
   - **JS** receives only the `js.*` keys, in the page language, through a
     `<script type="application/json" id="ui-strings">` block in `base.html`. A `strings.js`
     module provides `t(key, vars)`. Every hard-coded user-facing literal in `static/js` and
     `static/map.js` moves behind it: labels, `aria-label`s, `announce()` texts, tier names and
     month names.
   - **Rules, each a test:**
     - both catalogues have the same keys, the same placeholders per key and the same plural
       forms;
     - every key the code uses exists;
     - every defined key is used;
     - no template has a visible text node or `aria-label`/`title`/`alt`/`placeholder`/
       `data-label` value with letters outside a Jinja expression. This is checked by parsing the
       template source. The brand "velometer" and symbol-only text are allowlisted;
     - the JS catalogue block contains no root-relative URL strings (the M11 export-scan rule).

3. **Config prose.** Reader-visible English in config gets a German sibling, following the existing
   `basis_de` / `en:`+`de:` precedent. The schema requires the sibling wherever the English field is
   set.
   - `differences.yaml`: every label, `ours` and base text gets `_de`.
   - `report.yaml`: ranking `label_de` and `note_de`.
   - `presets.yaml` is not touched. Its bytes are part of every run's `config_sha256`, and its
     `basis` values are ids; the basis words readers see come from `differences.yaml`.
     (Amended 2026-10-12 after planning.)
   - `config/plans/plans.yaml`: `note_de` and `label_de`. German plan titles stay as they are.
   - `counters.yaml`: `note_de`.
   - `config/external/figures.csv`: a `note_de` column.
   - `cities.yaml`: an optional `name_de`, set only for vienna (Wien), prague (Prag), warsaw
     (Warschau), copenhagen (Kopenhagen) and krakow (Krakau). The German edition shows
     `name_de or name`.
   - **Compare group names** ("Nordic", "West & South") and every other label held in Python move
     to the UI catalogue.

4. **Prose content.** Each English content file gets a German translation file beside it:
   `content/narratives/de/<id>.yaml`, `content/de/explainer.yaml`, `content/de/counters.yaml`,
   `content/plans/de/berlin.yaml` and `content/organisations/de/<id>.yaml`.
   - **What a translation file holds.** Only the translatable text, in the English file's
     structure: title, dek, intro, section headings, paragraphs and organisation dimension values.
     It also holds its own `literals`, the exact German text spans the number check may accept.
   - **What it shares with English.** Facts, data references, quotes (`after: N`), roles, steps and
     ids all come from the English file. They are never repeated, so they can never disagree.
   - **Staleness stamp.** Every translated string is a mapping `{text: …, src: <hash>}`. `src` is
     the first 12 hex digits of the SHA-256 of the whitespace-normalised English string it was
     translated from. `velometer content stamp <file>` writes the hashes for a file that a
     translator has just updated. The command is run by whoever translated, never as a blanket
     fix for a failing check.
   - **Organisation names** are proper names and stay as they are. Source publishers, titles and
     locators stay in the source's language, as today.
   - **Quotes.** Excerpt text is never translated. Each excerpt gains `gloss_de`, which the schema
     requires when the excerpt language is not German. German quotes need no German gloss; they
     keep `gloss_en` for the English edition. A pullquote on a German page shows `gloss_de` under
     the quote. Inline `<q lang>` and `<blockquote lang>` work unchanged in German text.
   - **Flagged-year explanations.** These get `docs/review/m3_timeseries.de.md`, with the same `###`
     headings, each entry stamped with the hash of its English entry: an HTML comment
     `<!-- src: … -->` after the heading. `timeseries --check` requires both files to have the same
     heading set and no stale stamp. Any other `docs/` text shown on the site is handled the same
     way. The plan enumerates them by scanning the routes.

5. **Formats.**
   - **Python.** A shared `velometer/i18n.py` holds the number, sign, percentage, month and date
     formatters for `en` and `de`. It moves the German tables out of `report/methodology.py`,
     which then imports them, so the methodology output stays byte-identical. Every display
     formatter listed in §3 goes through it. The Jinja `num` filter, the signed `format(...)` calls
     in templates, `_when`, both `MONTHS` copies, `counts.py` month names and `plans_pages.num` are
     all affected.
   - **German conventions:**
     - `1.639,8`, `−3,2` (with U+2212, as the English pages already use);
     - `12,3 %` (a narrow no-break space before `%`);
     - `12. Oktober 2026`, `Jan. 2026` for month-year axis labels, and `Okt. 2026` for "current".
   - **JS.** A `fmt.js` takes the locale from `<html lang>` (`en-GB` or `de-DE`) and replaces every
     hard-coded `"en-GB"`, including the "k" abbreviation, which becomes "Tsd." in German.
   - **Downloads (M11).** SVG and PNG are drawn from the page, so they are German on German pages:
     axis, labels, key, title, source line. The attribution line has a German catalogue form. The
     chart CSV keeps machine formats. Its header row is the table's display header, which is German
     on German pages (the M11 ruling), but its number cells use dot decimals and its two-line
     preamble stays English. The server CSVs are unchanged.
   - **Citations (M11).** The plain-text citation follows a German template from the catalogue.
     BibTeX gets `language = {german}`, and CSL-JSON gets `"language": "de"`. The URL is the `/de/`
     address. Both editions share one `cite_cases.json` with cases per language.

6. **Content check per language.** `velometer content --check` checks English, then German, and
   names the language in every message.
   - **Numbers** in German text are parsed the German way: `.` and narrow or no-break spaces as
     thousands separators, `,` as the decimal comma, `−` or `-` for the sign, and `%` with or
     without a space. A German number is accepted when it is:
     - the German formatting of an English fact's value, at the same precision as that fact's
       English `printed`;
     - a German `literal`;
     - a year (20xx);
     - or a German ordinal (`1.`, `21.`) in date context.
     Anything else is reported as an "undeclared number", as in English.
   - **Rule families** get German counterparts, as data per language in the check module, each
     with tests:
     - construction verbs: gebaut, errichtet, eröffnet, entfernt, zurückgebaut…;
     - causal phrases: führte zu, wegen, aufgrund, infolge…;
     - number words: neun von zehn…;
     - rule statements: Messstellen, Tage, Basisjahr, Prozent….
   - **Parity.** A German paragraph must carry exactly the same multiset of `[#…]` and `[@…]`
     markers as its English twin. The number of sections and paragraphs must match.
   - **Completeness.** Every English file must have its German file. Every English
     translatable string must have a German string.
   - **Staleness.** A German string whose `src` differs from its English string's current hash
     fails, with the old and new English shown.
   - **Online check.** `--online` is unchanged, because excerpts are not translated.

7. **City names and search.**
   - **Names.** German pages show the German name (`name_de or name`) everywhere: titles, tables,
     charts, compare, citations and downloads.
   - **Search.** `/de/data/search.json` labels entries in German ("Die Geschichte von Krakau",
     "Methodik", German country names). Each city's terms hold every form: the German name, the
     local name, the English name and the `aliases`. "Krakow", "Kraków" and "Krakau" all land on
     the same city in both editions.
   - **Folding.** `fold` already handles ł/ø. German ß folds to "ss", and ä/ö/ü fold to a/o/u. The
     test runs over the real German names.

8. **The tier-map image.** `report maps` renders each map once per language: `{name}.png` and
   `{name}.de.png`. The German image has a German title, legend (tier names from the catalogue) and
   footer (the German attribution line and "kartierte km, nicht gebaute km", plus the timestamp and
   classifier). `tiers.html` on `/de/` links to the German image. The `report charts` and `change`
   PNGs stay English CLI outputs (§8).

9. **Methodology.** Generation is unchanged. Both files are hand-authored Jinja templates checked
   byte-for-byte by `report methodology --check`. Only the routes change (decision 1).

10. **Translation and the one review stop.**
    - **Glossary.** Claude drafts all German text. The terms follow `docs/glossary.de.md`, a
      spec-level deliverable built from `methodology.de.md`. It fixes, for example: "kartierte
      Kilometer" (mapped km), "Stufe A–E", "Kennzahl" (headline), "Hauptstraßen" (main roads),
      "Kernstadt (LAU)" and "Funktionaler Stadtraum (FUA)", "Lauf" (run), "Stand" (snapshot) and
      "Klassifikator".
    - **Style.** Neutral, journalistic German. No direct address (no "Sie" or "du"). Numbers in
      German format. Quotes untouched.
    - **Before review.** Drafting comes after the machinery: catalogue, formats, check and stamps.
      The draft must pass `content --check` (numbers, parity, completeness) before review starts.
    - **The review page** is a private artifact. Rows are grouped by page, then by section, and
      each row shows the English paragraph or string beside the German one. A row can be marked
      ("ok" / "change") and given a free-text note. The marks and notes are stored in the
      artifact's database, so Claude reads them back instead of copying them out of a chat.
      Glosses and UI strings are reviewable on the same page, in their own groups.
    - **After review.** Claude applies every note, re-stamps the changed files, re-runs all checks
      and the render pass, and lists in the rulings how each note was handled. A note that asks
      for a change in the English text is applied to both editions and listed separately.
    - **The single stop.** The review is the only user stop before the merge question. Work that
      does not depend on the German text may continue while it is open.

11. **Proof.**
    - **Render pass.** `tools/render_pass.py --pages all` covers every `/de/` page in both themes at
      1280, 390 and 320 px. Each page must have the right `lang` on `<html>`, alternate links that
      resolve, and no axe violations.
    - **No English left over.** On every `/de/` page, rendered in Chrome so that JS-drawn text
      counts, a step looks for any English catalogue value of four words or more whose German
      value differs. If one appears in the visible text or in an accessible name, it fails. A
      pytest version checks the server HTML of every `/de/` page.
    - **M11 controls in German.** The interaction steps (Cite, Download, permalinks, search,
      keyboard) run on `/de/` too. A German download is opened and checked for German labels and
      the German attribution.
    - **The English edition is unchanged** apart from the language switch, the alternate links and
      the movement of literals into the catalogue. An export diff of the English tree before and
      after M12 shows only those changes. It is proved once, at the end, and its result recorded.

12. **Unchanged.** The data, classifier, runs, CSV/JSON data and the English prose stay as they
    are. No ADR changes. The project's single external host stays tile.openstreetmap.org.

## 5. Components

| Unit | Responsibility |
| --- | --- |
| `velometer/i18n.py` | Languages, catalogue loading, `t()`, plural forms, number, sign, percent, month and date formatting |
| `content/ui/{en,de}.yaml` | All UI strings, including `js.*` |
| `app/urls.py` | Language-aware page links; data links stay unprefixed |
| `app/main.py` | Routes registered for `""` and `"/de"`; `lang` threaded through handlers and templates |
| `static/js/strings.js`, `static/js/fmt.js` | `t()` and locale formatting in the browser |
| `content/models.py`, `loader.py` | Translation models with `{text, src}` strings; `gloss_de`; loading by language |
| `content/check.py` | Per-language number parsing, rule families, parity, completeness, staleness |
| `cli.py` | `content stamp`; `content --check` over both languages; `report maps` in both languages |
| `report/maps.py` | Language-aware title, legend and footer |
| `app/export.py` | Both trees; `/de/data/search.json`; German map images |
| `tools/render_pass.py` | `/de/` pages, lang checks, English-leak step, M11 steps on `/de/` |
| `docs/glossary.de.md` | Fixed German terms |
| Review artifact | Side-by-side EN/DE rows with marks and notes in its database |

## 6. Error handling

- **Missing strings.** A missing catalogue key is a test failure. At run time, `t()` falls back to
  the English value and logs once, so a page never shows a raw key.
- **Missing translations.** A missing German content file or string is a check failure. At run
  time the page shows the English paragraph inside `lang="en"`, so the reader and the screen reader
  get the right language, and logs once. Proof fails on any such fallback.
- **Bad language prefixes.** An unknown language prefix (`/fr/…`) is an ordinary 404. A German
  route for a city without German content falls back as above and never returns a 500.

## 7. Testing

- **Unit tests:**
  - catalogue parity, placeholders and plurals;
  - used and defined keys;
  - the template literal guard;
  - German formatters, against the methodology's existing German cases and new ones;
  - German number parsing, including "78,2" → 78.2, "1.639,8" and "−3,2";
  - each German rule family;
  - parity, completeness and staleness, each red-proofed by breaking the rule;
  - `gloss_de` requirement; `name_de` use; search folding of German names; the German citation
    cases.
- **App tests:**
  - every page twin answers 200 under `/de/`;
  - `<html lang>` and hreflang links are correct;
  - the language switch targets the twin;
  - data links are unprefixed;
  - `/methodology/de` carries its canonical link;
  - the 404 page is bilingual;
  - no English leaks into the server HTML of `/de/` pages.
- **Export tests:** both trees, the reference scan over `/de/`, `/de/data/search.json`, and the
  German map images.
- **Node tests:** `strings.js`, `fmt.js` (`de-DE` and `en-GB`), and German labels in the download,
  cite and search modules.
- **The full gate, the six checks and the render pass,** as in M11.

## 8. Global constraints (project rules that bind M12)

- **Gate:** `uv run ruff format --check . && uv run ruff check . && uv run pytest && node --test
  "src/velometer/app/static/js/tests/*.test.mjs"`.
- **The six checks pass:** `counters --check`, `content --check` (now both languages),
  `report methodology --check`, `timeseries --check`, `reconcile --check`, `trust check`.
- **Never write `velometer.sqlite`.**
- **Tests assert rules, not today's values.** Each rule test is red-proofed once.
- **Never type OSM ids from memory.**
- **No npm, no build step, no new external host, the CSP holds.** No new Python dependency;
  formatting is our own code, not Babel.
- **Lengths only in the city's projected EPSG. OSM km are "mapped km" (ADR 0006).** In German:
  "kartierte km".
- **Quotes are never translated.**
- **Commits** carry the single trailer `Assisted-by: Claude:<model-id>`. Nothing is pushed.

## 9. Out of scope

- languages other than English and German;
- German CSV dialects;
- translated quotes;
- German `report charts` and `change` CLI images;
- translating `docs/` beyond the text the site shows;
- ADRs, HANDOVER and the README in German;
- hosting and publishing (HANDOVER §12 Q4).
