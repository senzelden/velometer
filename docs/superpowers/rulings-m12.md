# M12 rulings

German edition (spec `docs/superpowers/specs/2026-10-12-velometer-m12-design.md`, plan
`docs/superpowers/plans/2026-10-12-velometer-m12.md`). The pre-flight review and the SDD ledger are
in `.superpowers/sdd/2026-10-12-velometer-m12/`. This file records the user's rulings, the German
review (Task 10), the pre-flight and plan rulings, every ruling of the SDD ledger by task, the
Task 11 proof (render passes and the English export diff) and the follow-ups. Each ruling reads:
Ruling — why — cost.

## User rulings

- Ruling: data-reference captions stay English. Every data-ref label (`data_refs.<id>`, e.g.
  "velometer reconciliation, vienna/cc_km") shows the English label on German pages, inside
  `lang="en"`. This reverses pre-flight ruling 3.1 (data-ref labels translated) and restores spec
  §4.4 (data references come only from the English file, so they can never disagree). It is
  structural: `translate.walk` yields no data-ref path, so `merge`, `stamp`, the completeness
  check and `tools/review_rows.py` never see one; the translation models reject a `data_refs`
  key (the content check reports the file), so a stale German copy cannot linger; the 121 German
  labels were removed from the 24 translation files and the files re-stamped — the labels are
  identifiers of our own data, and one English form avoids two captions per reference — cost:
  German readers see 101 short English captions, marked `lang="en"`.
- Ruling: the English label on a German page sits in `<span lang="en">` without `data-fallback`
  — it is the design, not a missing translation, so the "no fallback on German pages" test keeps
  meaning "nothing is missing" — cost: none. The leak test gains a `data_refs` phrase source, so
  an English label outside `lang="en"` on a German page fails it.
- Ruling: the user accepted all other German rows as drafted.
- Ruling: Oslo's road classes name the source's own Norwegian terms first, the translation in
  parentheses, in both editions: English "on the statlige og fylkeskommunale vegnett (state and
  county road network) and a few kommunale veger (municipal roads)", German "an Straßen des
  statlige og fylkeskommunale vegnett (staatliches und regionales Straßennetz) und an einigen
  kommunale veger (Gemeindestraßen)" (`content/counters.yaml`, `content/de/counters.yaml`, source
  `vegvesen-trafikkdata/road-network`). A recorded exception to "English edition unchanged"; the
  excerpt's `gloss_de` stays. The glossary's Task 10 row (fylkesvei → regionale Straße) becomes
  the general rule: a country-specific official category keeps the source's original term first,
  the translation in parentheses, in both editions — cost: the English `/city/<id>/counts` pages
  change (English export diff below); the other comparability hits wait for the follow-up.
- Ruling: three German translation errors are fixed to match their English and cited sources —
  Stockholms län is "ein Verwaltungsbezirk" (English "a county"), not "eine Provinz", in
  `narratives/de/stockholm.yaml` and `narratives/de/combined.yaml` (where "eine ganze Provinz"
  becomes "einen Verwaltungsbezirk"; the explainer already says only "Stockholms län"); the
  Mobilitätsgesetz amendment's "secondary network" is "Nebennetz", the act's word
  (`berlin-mobg-amendment-2026`), not "Ergänzungsnetz", which the repo does not show to be the
  same network (`organisations/de/abgeordnetenhaus.yaml`); Bratislava's "advisory lanes"
  ("ochranných pruhov") are "Angebotsstreifen", not the German StVO term "Schutzstreifen"
  (`narratives/de/bratislava.yaml`) — cost: none; English unchanged.

## Review notes

One line per reviewed row: row id — mark / note — how handled.

- `content/de/explainer.yaml#sections.5.paragraphs.1` — fine — unchanged.
- `content/de/explainer.yaml#sections.0.paragraphs.1` — fine — unchanged.
- `content/de/explainer.yaml#intro.1` — fine — unchanged.
- `content/de/explainer.yaml#sections.2.paragraphs.0` — fine — unchanged.
- `content/de/explainer.yaml#sections.2.paragraphs.1` — fine — unchanged.
- `content/de/explainer.yaml#sections.1.paragraphs.0` — fine — unchanged.
- `content/de/explainer.yaml#sections.3.paragraphs.1` — fine — unchanged.
- `content/de/counters.yaml#sections.0.paragraphs.0` — change: "Not sure what a county represents
  in Finland. My first intuition would be 'regionalen Straßen'" — the sentence is about Oslo
  (Norway; fylkesvei = county road). "an Staats- und Provinzstraßen" became "an staatlichen und
  regionalen Straßen"; re-stamped. For consistency the Trafikkdata `gloss_de` in
  `content/sources/counters.yaml` now reads "dem regionalen Straßennetz der Fylker" (was "dem der
  Fylker (Provinzen)"), and `docs/glossary.de.md` gains "county road (fylkesvei) → regionale
  Straße". "Provinz" is kept where it means a province, län or NUTS region (Stockholm, Utrecht,
  Barcelona, the limitations).

No English text changed.

## Pre-flight rulings

These are the controller's rulings on the pre-flight scan
(`.superpowers/sdd/2026-10-12-velometer-m12/preflight.md`), applied throughout:

**Gate and CLI:**
- Ruling: the gate stays green at the end of every task. — Red is never handed to the next
  task. — Cost: some tests move between tasks.
- Ruling: `content --check` prints English problems exactly as today and German problems with a
  `[de] ` prefix. While the gate is off, German completeness notes are returned but not printed,
  and `--online` is gated only on problems, never on notes. — The existing exact-output tests
  (`test_content_m8.py:602/604`, `test_content_check.py:327`) stay unchanged. — Cost: notes are
  visible only through the API.
- Ruling: there is no process-wide switch.
  - `require_de` is an explicit check parameter. It defaults to
    `i18n.german_required(content_dir)`, which is `GERMAN_CONTENT_REQUIRED` for the shipped tree
    and False for any other tree.
  - The `gloss_de` rule lives in the check, not in a Pydantic validator.
  - — Synthetic `Source`s and hand-built trees in existing tests stay valid after Task 9 flips
    the constant. — Cost: the gate is a path comparison.

**Leak and sniff tests:**
- Ruling: Task 5's function-word sniff covers only config-derived text, scoped through
  `config.reader_prose()` (the `_de` values themselves). — Prose stays out until Tasks 7–8. —
  Cost: the sniff does not look at pages; the config phrase source of the leak test does.

**Routes and pages:**
- Ruling: fragments (`/city/{id}/panel`) carry `lang` on their root element, and the twin test
  checks `<html lang>` for full pages and the root `lang` for fragments. — A fragment has no
  `<html>`. — Cost: one attribute in the English panel, listed in the English diff.
- Ruling: the footer is catalogued in Task 2. — `/methodology/de` gets German chrome in Task 2,
  and its footer links must stay German. — Cost: Task 2 drafts a few German strings before the
  glossary; Task 3 reviews them against it.
- Ruling: the language comes from route registration, never from slicing the path. — A slice
  with `base_path` breaks every `/velometer/` export. — Cost: a small registration helper.
- Ruling: the 404 handler takes its language from a `/de` path prefix, else `en`, renders both
  language blocks anyway, and supplies `here="/"`. — No route ran for a 404. — Cost: none.
- Ruling: `strip_lang("/methodology/de")` is `/methodology`. — Its alternates must resolve. —
  Cost: none.
- Ruling: every Python-built page href (`main.py:866,882` and others) goes through the
  language-aware helper, and a test scans `/de/` pages for links to English twins. — A German
  page must not lead back to English except through the switch. — Cost: none.

**JS, formats and downloads:**
- Ruling: `localised(series, lang)` lives in `static/js/data.js`, has node tests, and is used by
  compare, the city charts and downloads. It lands in Task 7, which owns all `series.json`
  `_de` fields. — A shared static file needs a client-side swap. — Cost: German names in
  JS-drawn charts wait until Task 7.
- Ruling: `fmt.parse` is part of `fmt.js`, `tableCsv` takes the locale explicitly, and `slug`
  maps ß to "ss". — These are missing interfaces. — Cost: none.
- Ruling: the image source line ("OSM mapped km, not built km") has a German catalogue form.
  Only the CSV preamble stays English. — Spec §4.5. — Cost: none.
- Ruling: `tableCsv` never changes English CSV output, and rewrites number cells to dot
  decimals only when the locale is `de`. `download.test.mjs:105` stays as it is. — The English
  edition is unchanged. — Cost: none.
- Ruling: the Python↔JS "same key" mirror test is dropped. Separate tests check that the Python
  counter keys exist in the catalogue and that the JS keys exist. — Python and JS keys live in
  different families. — Cost: none.

**Content check and names:**
- Ruling: `check_content_all` takes `history`, and the staleness tests pass it explicitly. —
  Test trees are not git repositories. — Cost: none.
- Ruling: `load_cities(path)` is the real signature (`config.py:329`). — Cost: none.
- Ruling: the country key family is sourced from the countries of `config/cities.yaml`, because
  the names themselves move into the catalogue. — `names.COUNTRY_NAMES` is removed. — Cost:
  none.

**Tests and fixtures:**
- Ruling: the exonym snapshot test, `tests/city_names.json` and `tests/ui_js_strings.json` are
  accepted. — The first is the spec's list; node cannot read YAML without npm; tests keep the
  JSON fixtures equal to their sources. — Cost: fixtures to regenerate.
- Ruling: there is one shared `make_source` factory and one app builder (`app_for`) in
  `tests/conftest.py`. German month names come only from `i18n`, and the JS fixture is generated
  from it. — No duplicated helpers or data. — Cost: none.
- Ruling: `DYNAMIC_FAMILIES` declares every id-built key family, each sourced from its live
  config, model or code tuple.
  - Tables hold ids, not keys, and a test asserts that every composed key prefix in the code is
    a declared family.
  - Month names are not catalogue keys at all: `js_strings` injects them from `i18n`.
  - — The "every defined key is used" test is neither red nor leaky. — Cost: a code-scanning
    test.

**Constraints:**
- Ruling: data-ref labels are translated strings in the translation file, and the data-ref
  structure stays shared. — They are visible link text. — Cost: a refinement of spec §4.4.
- Ruling: page URLs go through `u()` and data URLs through `data_u()`. The search meta uses
  `data_u('/data/search.json', lang)`. — There is one rule per kind of URL. — Cost: a mechanical
  template migration in Task 2.
- Ruling: the construction-verb constraint states the rule actually checked (see Global
  Constraints). — Cost: none.

## Rulings the plan made

**Config and data:**
- Ruling: `presets.yaml` gets no `basis_de`. — Its bytes are run identity, and its values are
  ids. — Cost: the spec is amended.
- Ruling: `figures.csv` `note_de` is read beside the DB, keyed by the English note text. — The
  DB is never written. — Cost: one cached CSV read.
- Ruling: plan titles get `title_de` only for Vienna and Copenhagen. — Only those mix in English.
  — Cost: two optional fields.
- Ruling: `ROAD_CLASS_TEXT`, `TIER_LABEL` and `HEADLINE_UNIT` stay as English CLI constants,
  guarded by a test. — CLI outputs are English (spec §9). — Cost: a guarded duplicate.
- Ruling: external-figure ids are translated on German pages only. — English shows raw ids
  today. — Cost: the editions differ in form there.
- Ruling: the QECIO and BikeNetKit loader notes stay English inside `lang="en"`. — Translating
  them needs a DB rewrite. — Cost: a few tagged English lines on German pages.

**Content check and translations:**
- Ruling: `content` becomes a Typer group, and `content stamp` also stamps the explanations
  file. — `timeseries` is a single command, and one stamp tool is simpler. — Cost: the help
  output changes shape.
- Ruling: the German construction-verb family mirrors only built/constructed/opened/removed. —
  Parity with the English rule. — Cost: prose rephrases distances.
- Ruling: an English decimal point in German prose is always reported. — It is the one input
  that misreads silently. — Cost: none.

**UI strings and formats:**
- Ruling: the catalogue sits at the fixed path `content/ui`, cached by mtime. — The CLI needs it
  without the app. — Cost: the same packaging limit as today's `Path("content")` defaults.
- Ruling: German chart CSV cells use dot decimals under a German header. — Spec §4.5. — Cost:
  none.
- Ruling: the citation's accessed date stays ISO. — It is a machine field shared with CSL. —
  Cost: a mixed-format line.
- Ruling: unit and format symbols are allowlisted in the literal guard. — They read the same in
  both languages. — Cost: a short allowlist.

**Routes and pages:**
- Ruling: the methodology `.langs` line is removed. — The nav switch replaces it. — Cost: one
  English diff category.
- Ruling: `/methodology/de` gets German chrome and a canonical link. — It shows German text. —
  Cost: one English diff category.
- Ruling: `tools/render_pass.py` imports `velometer.i18n`. — The leak step must use the same
  phrase and visibility rules as the pytest. — Cost: the tool is no longer stdlib-only;
  `tools/README.md` says so.

## Ledger rulings by task

**Before Task 1:**
- Ruling: `presets.yaml` gets no `basis_de` (spec amended 133a206). — Its bytes are run identity
  (`selection.py` `config_sha256`) and the basis values are ids. — Cost: none.
- Ruling: `require_de = i18n.german_required(content_dir)`: the gate applies only to the shipped
  tree. — Hand-built test trees stay valid. — Cost: a path-identity rule.
- Ruling: month names come from `i18n`, not catalogue keys. — One source. — Cost: none.

**Task 1:**
- Ruling: a value that rounds to zero prints unsigned in both languages ("0.0"). — "-0.0" is a
  wart, and no page used the i18n formatters yet. — Cost: the English "−0.0" disappears where
  these formatters are adopted.

**Task 2:**
- Ruling: render-pass typing of `de/city` (keyed by language and slug) belongs to Task 11 Step 1.
  — It is not a one-line regex. — Cost: about 17-minute render passes until then.
- Ruling: fix the six review minors and add a render-once a11y fixture in fix round 1. — Cheap,
  and it speeds every later gate. — Cost: one round.

**Task 3:**
- Ruling: Task 7 owns the German `timeseries.provenance_line`. — It renders German content on the
  same tab data path, and no brief named an owner. — Cost: one more string in Task 7.
- Ruling: park review findings 1-3 (the 2+-word literal guard, the templates-only guard, the
  4+-word leak threshold). — Thresholds trade coverage for false positives, and the Task 11 leak
  check is the net. — Cost: a missed short English label surfaces at the Task 10 review or in
  Task 11.
- Ruling: finding 6 is handled by carrying the `LEAK_DEFERRED` removal into Task 5 and the
  `LEAK_EXCLUDED` and filter removal into Task 7. — Each set goes with the task that empties it.
  — Cost: none.

**Task 4:**
- Ruling: accept "A+B km per 100 km of main roads" in `CONTENT_SHARED`. — The pinned guard works
  as designed, and Task 7 removes the set. — Cost: none.
- Ruling: accept the English tier-map popup gaining a thousands separator at 1,000 km and more.
  — It matches the en-GB numbers elsewhere (Python gives 1,639.8). — Cost: a visible English
  change, on a runtime popup only.
- Ruling: park the unused `lang` parameter of `citeText`. — Documented and harmless. — Cost: one
  dead parameter.
- Ruling: the English map side count reads "31,842". — Consistent with the tier-popup ruling. —
  Cost: none.

**Task 5:**
- Ruling: accept `CONFIG_SHARED` (pinned, four phrases). — Same pattern as `CONTENT_SHARED`;
  Task 7 deletes it with `LEAK_EXCLUDED`. — Cost: none.
- Ruling: accept `successor_de` and `unit_de` in `plans.yaml` and the `KEY_CALL` regex change. —
  Needed for complete German config prose. — Cost: the reviewer checks them.
- Ruling: unowned English on German pages: the `reconcile.yaml` gap notes and the `reports.csv`
  suspect notes get German siblings drafted in Task 9 and rendered by Task 7's mechanism; the
  `reports.csv` locators and publisher names (Budapest) stay original as source citations, inside
  `lang="<source>"` where marked. — They cite sources, as quotes do. — Cost: a few more strings in
  Tasks 7 and 9.
- Ruling: the stiff counters notes (finding 3) go to the Task 10 review; the English
  `figure.scope` values (finding 4) are harmless. — Cost: none.

**Task 6:**
- Ruling: accept the implementer's rulings (`task-6-report.md`): `check_translation` takes
  `content_dir` and `sources`; partial translations are notes, not schema errors (null list
  items, optional titles and headings); German rules check only German strings; non-German
  quotations stay out of the German number check; German "neun von zehn" has no middle word;
  "not stated by the source" is "von der Quelle nicht angegeben"; the English language-attribute
  check skips `de/` files and German files get it with `[de]`; a broken German file is an error
  under `de/<stem>` with a full English fallback; `content stamp` accepts only `*/de/*.yaml` with
  an English twin or `m3_timeseries.de.md`; an empty English explanation has the stamp of "",
  and the stale explanation message has no "was:" line. — They keep the brief's interfaces and
  fill the gaps it left. — Cost: rework if one conflicted with the spec (none did).
- Ruling: park review finding 5. — Translation files are machine-written and comment-free, and
  the docstring says so. — Cost: a hand comment is dropped on stamp.
- Ruling: stale German keeps rendering until the Task 9 gate makes staleness an error. — Cost:
  none once the gate is on.

**Task 7:**
- Ruling: the German tier PNGs live in git-ignored `data/` like the English ones. — Same as the
  existing map flow. — Cost: a fresh checkout runs `report maps` (HANDOVER §8).
- Ruling: keep the catalogue key `search.story_city` over the brief's `story_of`. — It exists. —
  Cost: none.
- Ruling: Task 11 runs `report maps` before the export and documents it. — Cost: none.
- Ruling: English editorial parentheticals in source titles ("(report)", "(scanned PDF, excerpts
  transcribed …)") get German siblings in Task 9, and the sniff then covers Figures. — They are
  our text, not original titles; publisher and licence names and data-ref ids stay original. —
  Cost: more Task 9 strings.
- Ruling: Task 9 removes the sniff's Figures exclusion; Task 11 extends the sniff to every `/de/`
  page and widens the word list. — Cost: none at the time.

**Task 8:**
- Ruling: accept the `test_m12_render.py` fix (an `_english_only` tmp tree). — The rule is
  unchanged; the tests had asserted today's tree. — Cost: none.
- Ruling: "Strasbourg" stays. — The local-name rule, and the user's exonym list is exactly five.
  — Cost: the user may prefer Straßburg.
- Ruling: finding 6 (source-title parentheticals) stays with Task 9. — Per the Task 7 ruling. —
  Cost: none.

**Task 9:**
- Ruling: the two German overflows (`/de/city/berlin` h2 at 320 px, `/de/sources` table at 1280
  px) are fixed in Task 9's fix round, not deferred. — The review page should show a clean
  edition. — Cost: one more fix item.
- Ruling: `test_shipped_german_content_is_complete` counts only `[de]` problems and notes. — The
  English facts need the real DB. — Cost: none.
- Ruling: accept the eleventh review-row key `quote` and four commits. — Cost: none.

**Task 10:** the user rulings above.

**Task 11:**
- Ruling: the English-word sniff lives in `i18n.english_words` (with `ENGLISH_WORDS` and
  `PROPER_NAMES`), shared by `tests/test_m12_leak.py` and the render pass, and covers every `/de/`
  page. — The Chrome step and the pytest must judge English the same way; the render pass also
  sees text the JS writes. — Cost: the tool imports `velometer.i18n`.
- Ruling: the word list holds common English words that are no German word ("in", "an", "so",
  "was", "will", "also", "man", "die", "per", "see" and OSM values such as "no" stay out); words in
  capitals (codes: AT, NO), words joined by `/`, `_` or `-` (ids) and the pinned proper names are
  passed over. — A name keeps its own form (OrganisationTr; the local-name rule), and a code is
  no prose. — Cost: the sniff is a heuristic; `PROPER_NAMES` (ten names) must grow when a new
  English-named body or title appears, and a test fails on a name no shipped file holds.
- Ruling: Oslo's counter attribution gets `source_de` ("Statens vegvesen (staatliche
  Zählstellen)"), Warsaw's portal list `checked_de`, and two plan publishers `publisher_de`
  ("… und …", "… für die …"); `series.json` carries `source_de` for the German compare and
  `data.js`. — "(state counters)", "counter viewer", "and" and "for the" are our words beside a
  name, not the name. — Cost: three optional config fields, set only where needed.
- Ruling: the German methodology renders our own words in the stored provenance strings in
  German ("union of 17 LAU" → "Vereinigung von 17 LAU", "(sum of 17 LAU)" → "(Summe von 17
  LAU)") by a filter; the strings in the DB stay as written. — The DB is read-only and the
  strings are run identity. — Cost: a pattern table to extend if new provenance wording appears.
- Ruling: the three Leaflet maps set the attribution prefix with `js.map.leaflet_title`, whose
  English value is Leaflet's own title. — Leaflet's English link title ("A JavaScript library
  for interactive maps") is read to German readers; the English DOM stays the same. — Cost: one
  catalogue key.
- Ruling: a German figure Cite names a metric without a label by its id, as the table's code cell
  does. — The de-underscored id ("incl traffic calmed restricted access") reads as English. —
  Cost: underscores in a few German citation titles.
- Ruling: the render pass's language rule is the app's (`urls.lang_of`), so the legacy
  `/methodology/de` must be German. — The first full pass wanted `en` there. — Cost: none.
- Ruling: a page without alternates is not an error for the render pass; every alternate a page
  has must resolve. — Synthetic test sites have none; every exported page has three. — Cost:
  none.
- Ruling: the German SVG check asks for German month labels (a German short month and year,
  "Okt. 2026", and no English one), not literally "Jan." as the brief wrote. — The tier chart's
  axis labels the 1 January snapshots by year; only the current snapshot carries a month. The
  German CSV rows do read "Jan. 2018". — Cost: none.
- Ruling: the German switch step ticks a Compare city box with the box's own `click()`. — On a
  phone the boxes sit in a closed panel; the step tests the switch, not the tick. — Cost: none.
- Ruling: saved downloads are kept as `[de-]saved-<theme>-<width>.<ext>`. — The page screenshot
  `download-<theme>-<width>.png` overwrote the saved PNG of the same name. — Cost: none.
- Ruling: the base export (60f5bf8) reads its own `content/` and, through a temporary link, the
  main checkout's `data/plans`; `--maps`, `--docs` and the DB come from the main checkout. — The
  base code rejects the M12 content (`title_de`: extra inputs not permitted), which put error
  notes on the before pages, and the CLI reads plans data from the working directory. — Cost:
  the before state is the base's own English content, which is the comparison that matters.
- Ruling: the 404 page's German line is accepted in the English diff. — One `404.html` serves
  both editions on a static host, so it carries the German line in `lang="de"`. — Cost: one file. Ratified in the Task 11 review.
- Ruling: the `app.css` change is accepted in the English diff. — It removes the `.langs` rule
  with its paragraph and adds `:lang(de)` rules, which select nothing on English pages. — Cost:
  one file. Ratified in the Task 11 review.

**Task 12** (content fix before the final review):
- Ruling: the Norwegian terms carry no `lang="no"` markup. — Content prose has one language
  markup only, the quotation (`<q lang>`, `<blockquote lang>`), which prints quotation marks and
  claims the words verbatim ("vegnett" is not: the source says "vegnettet"); no plain language
  span exists, and the brief says not to invent one. — Cost: screen readers read the Norwegian
  words with the page's language; the follow-up may add a span.
- Ruling: Bratislava's advisory lanes are "Angebotsstreifen". — It renders "advisory" (an offered
  lane) and is no current German StVO term, while "Radfahrstreifen mit Schutzfunktion" contains
  "Radfahrstreifen", the StVO's mandatory lane (Zeichen 237), the opposite of an advisory lane;
  the repo already uses "Angebotsstreifen" for the Dutch advisory lane
  (`fietssuggestiestroken`, `content/sources/north.yaml`). — Cost: the excerpt glosses
  (`gloss_de`) of the Slovak and Czech sources still say "Schutzstreifen"; they were not in scope.
- Ruling: "Verwaltungsbezirk" for a län, without "ganze" in `combined.yaml`. — The English says
  "covers a county"; "Bezirk" alone is Berlin's districts in the glossary. — Cost: none.
- Ruling: the glossary gains rows for län, advisory lane and Berlin's Nebennetz beside the
  general rule. — The fixed terms should not drift back. — Cost: none.
- Ruling: the counters explainer's word budget (M8 plan: 150–300 words; asserted in
  `test_counter_explainer_length_wording_and_facts`) gains 10 words, to 310. — The user's Oslo
  wording adds the Norwegian terms beside their translation: 298 words before, 306 after; trimming
  other English sentences would break "English unchanged" beyond the ruled sentence. Red-proof:
  a bound of 305 fails at 306. — Cost: the budget is a little looser; the original-terms
  follow-up may need the same allowance for other documents.

## English export diff (Task 11)

Base 60f5bf8 (merge-base with main) against the M12 head, both exported under `/velometer/` from
the same read-only DB; commit hashes and generation timestamps normalised; `de/` and `*.de.png`
left out. 272 files before, 275 after, 153 differ. Per category (files):

| Category | Files |
| --- | --- |
| Language switch, alternate and canonical links, `velometer-search` meta, `#ui-strings` block, `lang-switch.js`/`strings.js`/`fmt.js` tags (every full page, `404.html` included) | 104 |
| `lang` on the panel fragment root | 21 |
| Removed `.langs` paragraph of `/methodology` | 1 |
| `/methodology/de` with German chrome (German by ruling) | 1 |
| `404.html` German line (ruled above) | 1 |
| `data/series.json`: additive `_de` fields only (`name_de`, `country_name_de` ×21, `headline_unit_de`, `presets_de`, `counters.none_de`, `counters.cities.oslo.source_de`, `explanations_de`; equal to the base without them) | 1 |
| `data/search.json`: city `terms` gaining name forms (4 entries, each a superset) | 1 |
| New static JS (`fmt.js`, `lang-switch.js`, `strings.js`) | 3 |
| Other static JS files | 22 |
| of which English CSV cells (pre-flight 3.4: `tableCsv` in `download.js`; English output unchanged by ruling, German rewrites number cells to dot decimals) | (1) |
| `static/app.css` (ruled above) | 1 |
| `data/*.csv` | 0 |

Nothing else differs.

**Task 12 (Oslo road classes, user ruling above).** One more category, measured against an
export of 72d9b2f (the head before Task 12) under `/velometer/` from the same read-only DB, commit
hashes and timestamps normalised: 441 files both, and outside `de/` exactly 7 English files differ
(plus `build.json`), each in one line only — the Oslo sentence of the counters document, which
every counter city's Counts tab embeds (there is no separate `/counters` page):

| Category | Files |
| --- | --- |
| The Oslo sentence of "What the counters record" names the source's Norwegian road classes, on `/city/<id>/counts` for barcelona, berlin, helsinki, madrid, oslo, paris and vienna | 7 |

The same 7 files already differ from 60f5bf8 through the first row above (language switch and
links), so the total of 153 differing files is unchanged.

## Render passes (Task 11)

On the export of eb0f87c (441 files) under `/velometer/`: `--pages all --themes light,dark
--widths 1280,390,320` — 1230 visits (618 German), 0 findings, exit 0; `--pages types --interact
--keyboard --flip` — 173 visits (87 German), 0 findings, exit 0. The first full pass found the
two Task 11 fixes above (the Vienna figure Cite title, the legacy methodology's language); the
probe passes before it found Leaflet's English title and the German month check. After the
download file-name fix (40cd926, tool only), the interactions were re-run in both themes at 1280
px: 16 visits, 0 findings.

## Follow-ups

- Proper names are passed over by a pinned list; tagging names with their language (a `lang`
  field on organisations, counter publishers and plan titles) would let the sniff drop the list.
- The English-word sniff is a heuristic: it catches common English words, not every English
  phrase; the phrase sources cover the catalogue, the content, the config prose and the
  data-reference labels.
- German pages were not checked with a screen reader.
- Parked from earlier tasks: `signed()` of a value rounding to zero prints "+0.0"/"+0,0"
  (Task 1); `citeText`'s unused `lang` (Task 4); the German number-check thresholds in
  `RULES["de"]` are drafts (Task 6); "Strasbourg" may become "Straßburg" if the user asks.
- The export is about 272 MB, mostly tier-map GeoJSON (the M9 hosting follow-up still stands).
- Original national terms in both editions (48 comparability hits, sources looked up where
  missing) — separate milestone after M12; inventory in
  `.superpowers/followups/original-terms-inventory.md`.
