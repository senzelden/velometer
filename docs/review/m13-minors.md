# M13 minors ledger

Every open, unmarked minor in the Follow-ups of `docs/superpowers/rulings-m8.md` … `rulings-m12.md`,
triaged by the M13 spec §4.8 rule:

- **fix**: a defect, a drift risk or a misleading test, fixed with a red-first test;
- **close**: obsolete or already fixed;
- **keep**: a deliberate trade-off.

Tasks 9 and 10 add the M9, M11, M10 and M12 sections.

## M8

### How the M8-N numbers map

`docs/superpowers/rulings-m8.md`, section "Follow-ups", read top to bottom. Each open, unmarked
part of a bullet gets the next number, so a bullet can give more than one: the Counters bullet
gives 3 (Paris in-service) and 4 (the km-only branch). Exception: each bullet under "Opened by the
follow-up pass" gets one number, split into a, b, … in the table below. Bullets whose parts are
all marked "closed `sha`" get no number. These are Colours, Compare (`f0684ed`), DB helpers
(Task 1), Berlin WFS fetch, Attribution and error notes (M3, M4), and Code structure (M8, M9).
Under "Opened by the final review", I2 is closed (`10f9865`) and gets no number either. The
numbers:

| N | Bullet in rulings-m8 Follow-ups |
|---|---|
| 1 | Overlay method (v3 bends, v4 turning networks) |
| 2 | Plan chart: cumulative mapped line on the per-year axis |
| 3 | Counters (first open part): Paris in-service day-granular, rolling UTC export |
| 4 | Counters (second open part): the km-only Counts chart branch unreachable |
| 5 | Content checks (Task 2): unexplained `test_overlay_facts` failure |
| 6 | Content: no test that Copenhagen 37 and Strasbourg 52 are suspect |
| 7 | Counter index (M1, M2): a mean-per-day link (index v2) |
| 8 | Prose restating config: the Madrid detector clause |
| 9 | Task 11 minors: phone-width CSS tests assert the rule, not the cascade |
| 10 | Gate: Starlette `httpx` deprecation warning |
| 11 | Process notes (Task 7 gate, Task 10 tests written after the code) |
| 12 | Figures-tab tables scroll horizontally at 390 px |
| 13 | Dark mode: no dark theme |
| 14 | Opened by the follow-up pass: Compare and counters (Task 1) |
| 15 | Notes and licences (Task 2) |
| 16 | One source (Task 3) |
| 17 | Plan chart (Task 4) |
| 18 | Colours (Task 5) |
| 19 | DB and fetch (Task 6) |
| 20 | Content checks (Task 7) |
| 21 | Final review M1: `EM_MARK` pairs two OSM wildcards |
| 22 | Final review M2: spec §5.4 base-year wording |
| 23 | Final review M3: `_optional_rows` trusts its caller's table name |
| 24 | Final review M5: `plan-chart.js` "%, share" axis text |
| 25 | Final review M6: `RULES` typed by hand in `test_content_m8.py` |
| 26 | Final review M9: counters fetch `ValueError` names no file |

This matches every item the Task 8 brief names: 2 = cumulative axis, 4 = km-only branch,
6 = Copenhagen/Strasbourg, 8 = Madrid clause, 11 = process notes, 13 = dark theme, 14 = the
compare tooltip and `compare.py` `line`, 19 and 26 = the `cli.py` ValueError, 20 =
`_madrid_year`, 21 = EM_MARK, 22 = spec §5.4, 23 = `_optional_rows`, 24 = "%, share", and 25 =
`RULES`. No number was ambiguous. Bullets 14 to 20 each hold several items, so the table below
gives them one row per item (14a, 14b, …).

### Items

| id | item | ruling | reason | commit |
|---|---|---|---|---|
| M8-1 | Overlay v3 bends / v4 drop along turning networks (v5 question) | close | M13 Task 3 measured v4's real loss and closed v5 as not built | `2996d19`, `c487671` |
| M8-2 | Cumulative mapped line shares the "km per year" axis | fix | The mapped line now has its own labelled right axis, with its 0 aligned to the per-year 0. A second panel would have changed the chart's height, margins and label fitting. The off-scale cap rule still counts the mapped values, so the targets near the line stay on the scale. | `7da510e` |
| M8-3 | Paris in-service by day; rolling UTC export | close | M13 Task 1 made in-service hourly (Paris, Helsinki) | `4466d9d` |
| M8-4 | Unreachable km-only Counts chart branch | fix | Removed. `countsChart` returns null without a line, as the tab draws no chart then. The test now asserts that. | `ff2bb02` |
| M8-5 | Unexplained `test_overlay_facts` failure | keep (Task 10) | Spec §4.8: Task 10 runs it 200 times, then fixes it or closes it | n/a |
| M8-6 | No test that Copenhagen 37 / Strasbourg 52 are suspect | fix | The test asserts the rule on a fixture figure: the `suspect` column of `reports.csv` gives the mark and the note exactly when it is set, both ways | `a8789f5` |
| M8-7 | Mean-per-day link (counter index v2) | close | M13 Task 2 built index v2 | `b5b76dd` |
| M8-8 | Madrid detector clause hand-written inside a generated block | fix | `note:` / `note_de:` on the Madrid entry in `config/counters.yaml`, rendered from the facts. A changed note makes the committed methodology stale. `require_de` enforces the German clause, and `reader_prose` lists it. | `ff80efe` |
| M8-9 | Phone-width CSS tests assert the rule, not the cascade | close | M13 Task 5 added browser tests for the phone cascade | `d609ebc` |
| M8-10 | Starlette `httpx` deprecation warning | keep (Task 10) | Spec §4.8: Task 10 | n/a |
| M8-11 | Process notes (Task 7 gate, Task 10 test order) | close | Process notes, not code (brief ruling) | n/a |
| M8-12 | Figures tables scroll at 390 px | close | M13 Task 5: the tables stack below 700 px | `d609ebc` |
| M8-13 | No dark theme | close | Delivered in M10 (brief ruling) | n/a |
| M8-14a | Counter tooltip lost "2019 = 100; 2020 is the COVID year" | fix | The counter tooltip never carried a unit. The "each city's base year = 100" text in `metric_info` is not shown for the counter metric, because the subtitle uses the payload unit. The tooltip now names the city's base year = 100, and on the COVID point "2020 is the COVID year" (`counterTip`). | `dc1a231` |
| M8-14b | "Counters are context" stated twice on the counter Compare view | fix | Dropped from the footnote (`counts.foot`, `js.counts.foot`, en and de). The subtitle keeps it, and the test counts it once per page. | `dc1a231` |
| M8-14c | Static import mid-file in `counter-model.test.mjs` | fix | Moved to the top (hygiene, with the tooltip test) | `dc1a231` |
| M8-14d | `test_app_m8_counts.py` pins today's footnote string | fix | The pin ("recorded at counter sites") is gone. The test asserts the rule: the footnote is `COUNTER_FOOT` and the context is said once. | `dc1a231` |
| M8-14e | `compare.py` raises on a city without `line` | fix | `.get("line")`, which skips the city as `counter-model.js` does | `dc1a231` |
| M8-14f | `metric_info` counter unit built from an empty payload | close | Not reader-visible: the counter subtitle, table and tooltip use the payload's unit (see 14a) | n/a |
| M8-15a | Unreadable-record note says the retrieval date cannot be shown, while the network line shows its stored date | fix | The note now says "their licences and the measures dataset's retrieval date cannot be shown" (en and de) | `cc692ad` |
| M8-15b | Measures line takes the licence without checking its layer | fix | `layer_licence(record, MEASURES_LAYER)`, like the planned-network line. An unlisted layer reads "licence not recorded". | `cc692ad` |
| M8-15c | `counters.yaml` read error logged per city per cached build | keep | Log volume only. Each build reads the file again, so a fixed config shows at once. Caching the error would hide that. | n/a |
| M8-16a | Latest-overlay-version logic and the Berlin city constant duplicated | fix | One `latest_overlay` (in `content/facts.py`, also used by the facts) and one `plans.berlin.CITY`. An identity test pins the function. | `e3bd69a` |
| M8-16b | Methodology re-implements `has_line` / `_days`, and asks for gaps under another condition | fix | `counters.model.has_line` and `ReportData.counter_day_counts` serve both. The methodology now asks for gaps on the stored series, as the Counts tab does. | `28dfa32` |
| M8-16c | `DEFAULT_BASE_YEAR` / `COVID_YEAR` imported by name; test covers the template side only | close | One constant, read where it is used. The facts carry its value, and the existing test drives the template from the facts. No second copy exists to drift. | n/a |
| M8-16d | Hand-written "the plan's first target year" beside the generated `MAPPED_BASELINE` | fix | A test asserts the claim: `MAPPED_BASELINE` is 1 January of the current Berlin plan's first target year | `a62531f` |
| M8-17a | `counter-model.js` literal fallbacks "Counts" / "Mapped km" | close | Already `t("js.counts.short_*")` since M12 | n/a |
| M8-17b | `labelSpot` ignores cap segments; adjacent cap labels untested for overlap | fix | `labelSpot` now gets the cap lines too. Cap values thin out, every other one counted from the last, when even the compact form is wider than a band. Before, they overlapped at 358 px with ten years. | `6d347bf` |
| M8-17c | Date-label test relaxed from inside-plot to inside-svg | fix | The test asserts inside the plot again | `6d347bf` |
| M8-17d | `_key_line_colour` docstring says `<p class="chart-key">` | fix | Docstring now says `<ul>` | `6d347bf` |
| M8-17e | Section roles computed twice in `plans_berlin.html` | keep | The same expression twice in one template, with nothing that can drift between them. A Jinja macro cannot read the later `set` without passing it, which costs more than it saves. | n/a |
| M8-17f | The every-target-in-table test is a guard | keep | A regression guard that asserts a rule ("every target is in the table"). It is not misleading. | n/a |
| M8-18a | Hue-distance test has no chroma floor | fix | `--mapped` must have CIELAB chroma ≥ 20, and greys are skipped by chroma. Red: a grey `--mapped` (`#7f7b7d`) passed the old test. | `0eee6fe` |
| M8-18b | `rgb(...)` shadow colours outside `:root` | close | Now the `--shadow` tokens in `:root` (light and dark) | n/a |
| M8-18c | Key test's "table" check is loose | fix | Matches the words "the table under the chart" | `0eee6fe` |
| M8-19a | Counters fetch `ValueError` catch has no CLI test | fix | A CLI test with Oslo answering HTML: exit 1, and the message names the URL (see M8-26) | `a372e6a` |
| M8-19b | `_print_city_metrics` reads through `_open_schema` after a write | keep | Harmless (rulings-m8). One extra schema check, no wrong value. | n/a |
| M8-19c | WFS treats a JSON-null id as a missing property (wording) | fix | The message now reads "no value for its 'gisid' property (missing or null)". Both cases are tested. | `70b7539` |
| M8-19d | Six adapters take an ignored `data_dir` | keep | Documented. It keeps one adapter signature (Oslo needs it). | n/a |
| M8-20a | `_madrid_year` hard-codes the 2020 clock-change dates | fix | Dates come from `ZoneInfo(<madrid timezone>)`. The test covers 2020 and 2021. | `e6953cf` |
| M8-20b | Plan-file cache in `facts.py` unbounded, shares mutable lists | keep | One entry per config directory, refreshed on a byte change. Only `_plan` reads the lists and never mutates them. | n/a |
| M8-20c | "Nine of the sites" case uses a number that is not a rule value | close | Intended: it checks that "nine" outside "nine … in ten" is not read as `min_valid` (and that "three districts" is not `min_sites`) | n/a |
| M8-20d | Threshold phrasings the check misses: "2019 (= 100)", "relative to 2019", "90% coverage" | fix ("2019 (= 100)") / keep (the other two) | "2019 (= 100)" is now read as a base year (en "(= 100)", de as well). "Relative to 2019" and "90% coverage" also describe comparisons and network coverage, so matching them would flag correct prose. The check stays a literal-statement heuristic. | `0063cde` |
| M8-20e | `_seed_report` depends on the fixture flagging at least one gap | close | It asserts that dependency itself (`assert marker and gaps, first`), so it fails loudly, not silently | n/a |
| M8-20f | Source and data-ref substitutions run inside code spans | fix | `[@id]` / `[#id]` inside backticks stay text | `c17a68a` |
| M8-20g | "counts" as a verb triggers the causal check | keep | This can reject correct prose. Kept on cost: the author rewords the sentence (for example "tallies", "records"), while telling the verb from the noun needs part-of-speech tagging. No shipped prose trips it today. | n/a |
| M8-20h | `archive_url` error says "source url" | fix | The error names the field: "source archive_url must be …" | `6bf1a1b` |
| M8-21 | `EM_MARK` pairs two OSM wildcards outside backticks | fix | A star after "=" neither opens nor closes an italic. A renderer test covers it, and the `<i lang>` term mark still renders. | `2909e74` |
| M8-22 | Spec §5.4 "the index base year equals 100" | fix | M8 spec §5.4 now states the `MIN_SITES` condition (doc-only) | `0a9ecd0` |
| M8-23 | `_optional_rows` trusts its caller's table name | fix | A ValueError when `table` is not a word of the SQL | `0838310` |
| M8-24 | `plan-chart.js` "%, share" axis text | fix | `js.plan.share_in` gives "share in %" / "Anteil in %". The not-drawn note uses the same measure text. | `e12b115` |
| M8-25 | `RULES` typed by hand for the shipped-page test | fix | The test uses `counter_rule_values(config)` and compares declared rule facts with those found. Red: with `MIN_SITES` = 4 the old test passed and the new one fails. | `e6953cf` |
| M8-26 | Counters fetch: HTML answer gives "Expecting value" without the file | fix | Oslo `_graphql` raises `CounterFormatError(url, "answer is not JSON (<content type>) …")`. The error names the URL it came from, which is the source for a network fetch: Oslo is the only adapter that parses JSON at fetch time, and the file-based adapters name the file. | `a372e6a` |

### Logged here, owned elsewhere

These came up in the areas this task touched. They are not fixed here.

| id | item | ruling | owner |
|---|---|---|---|
| M13-T1a | The rolling-export test passes under both in-service rules (day and hour) | fix candidate | controller (Task 1 follow-up) |
| M13-T1b | The outage test has no red-proof | fix candidate | controller (Task 1 follow-up) |
| M13-T2a | `_signed_pct` prints −0.0 % | fix candidate | Task 10 |
| M13-T2b | Unclosed sqlite connection in `tests/test_counter_index_v2.py` (~1702) | fix candidate | Task 10 |

## M9

### How the M9-N numbers map

`docs/superpowers/rulings-m9.md`, section "Follow-ups", read top to bottom. Each bullet under
"Deferred review minors, by task" (T1 to T4, the "(noted)" one included) gets the next number,
1 to 18. Under "Hosting and later work", the size bullet is the publishing question (HANDOVER §12
Q4), not a minor. The live-vs-main identity bullet is marked "done, clean". Of the render-pass
observations, the 390 px tables and the dark theme and accessibility check name M10 as their
owner. None of these gets a number. The one left, the Compare address keeping its slash after the
directory redirect, gets 19. The numbers:

| N | Bullet in rulings-m9 Follow-ups |
|---|---|
| 1 | T1: `urls._is_external` takes letters-only schemes (`web+foo:` raises) |
| 2 | T1: the `unit` filter's lambda parameter `u` shadows `u()` |
| 3 | T2: the literal-route rule misses a bare `"/"` and more; add a comment |
| 4 | T2: `base.test.mjs` finds `url_cases.json` by six `../` |
| 5 | T2: a `base.test.mjs` assertion (around line 87) does not match its test name |
| 6 | T2: `base()` queries the DOM on every `url()` call |
| 7 | T3: `plans_data_dir` has no CLI option |
| 8 | T3: the test map regex copies the implementation's (M-5) |
| 9 | T3: the test follows redirects and the code does not (M-6) |
| 10 | T3: every page is rendered twice (M-8) |
| 11 | T3: the `validate_base` regex's `$` accepts a trailing newline |
| 12 | T3: rollback catches `OSError` only (Ctrl-C mid-swap) |
| 13 | T3: a failed rollback leaves the old export in a directory no message names |
| 14 | T3: `out.mkdir` runs before the `try` |
| 15 | T4: the Leaflet guard ignores `L.geoJSON`'s default marker for Point features |
| 16 | T4: the JS scan skips lines starting with `*` as comments |
| 17 | T4: an `export.py` docstring line is about 140 characters |
| 18 | T4 (noted): the JS scan checks only literal `url()` paths |
| 19 | Render pass: Compare shows `/velometer/compare/?…` until the first change |

This matches every item the Task 9 brief names, 1 to 19. No number was ambiguous.

### Items

| id | item | ruling | reason | commit |
|---|---|---|---|---|
| M9-1 | `_is_external` takes letters-only schemes | fix | Python `u()` and JS `url()` both treat any RFC 3986 scheme (`[A-Za-z][A-Za-z0-9+.-]*:`) as external. The shared `url_cases.json` gains `web+foo:bar` and `a1.b-c+d:x` as untouched, and `1a:b` and `+x:y` as refused. | `61dab4e` |
| M9-2 | Lambda parameter `u` shadows `u()` | fix | Renamed to `unit` (no behaviour, so no red test) | `1919ac5` |
| M9-3 | Literal-route rule misses a bare `"/"` | fix | A comment says what the rule covers and what it does not. A second rule fails a bare root literal (`"/"`, `"/?…"`, `"/#…"`) outside `url()` and string-method separators (`.join("/")`, …), read with `js-literals.mjs`, so comments do not count. Red: a planted `"/"` in `nav.js`. | `6b22f99` |
| M9-4 | `base.test.mjs` finds `url_cases.json` by six `../` | fix | `tests/repo.mjs` walks up from `import.meta.url` to `pyproject.toml`. All six node tests that read `tests/*.json` use it now, with a test that it finds the root from a deep path and throws without one. | `6b22f99` |
| M9-5 | An assertion does not match its test name | fix | The "this file sits in `js/tests`" assertion is its own test, named for what it checks. It also checks the exact path, not just a `js` prefix. | `6b22f99` |
| M9-6 | `base()` queries the DOM on every `url()` | fix | One read per document (a `WeakMap`), with `_resetBase()` for tests. Red: without the cache the test counts two queries. | `6b22f99` |
| M9-7 | No `--plans-data-dir` option | fix | `app export` and `serve` take `--plans-data-dir`, default `data/plans`. `serve` passed nothing before, so the app used its own default. | `173896c` |
| M9-8 | Test map regex copies the implementation's | close | Already fixed in M9's fix round: the test's `/maps/[^"'\s)<>]+` is independent of `_map_refs` | `b0ba484` |
| M9-9 | Test follows redirects, the code does not | fix | The rest of the export tests now ask with `follow_redirects=False`. Red: the live-app equality test asked `/de`, was redirected to `/de/`, and passed. It now asks each page by the URL the export rendered. | `4046b32` |
| M9-10 | Every page rendered twice | fix | A contained change: `export_urls` hands its responses to `_write_site`, which renders only what it lacks. Red: a request-counting middleware saw 31 URLs asked twice. | `1cc3293` |
| M9-11 | `validate_base` `$` accepts a trailing newline | fix | `fullmatch`; `/a\n` and `/a\n/b` are refused | `e14129e` |
| M9-12 | Ctrl-C mid-swap leaves `out` half-swapped | fix | The swap rolls back on any `BaseException` and raises it again. The test interrupts the second move-in with a monkeypatched `os.rename`/`os.replace`. | `a3abb1e` |
| M9-13 | A failed rollback names no directory | fix | `ExportError` names the set-aside directory, and that directory keeps the previous export. The test fails the move-in and the move-back. Fix round: an interrupt during the rollback is reported the same way. Each name is noted before its move, so a move whose note an interrupt cut off is undone too. The error names the set-aside directory only while it exists. Monkeypatched tests cover each case. | `a3abb1e`, fix round |
| M9-14 | `out.mkdir` before the `try` | fix | `mkdir` and the set-aside `mkdtemp` are inside the `try`. A new `out` is removed when the set-aside cannot be made (test: `mkdtemp` raises). | `a3abb1e` |
| M9-15 | Leaflet guard ignores `L.geoJSON`'s default marker | fix | The guard fails on any `L.geoJSON(…)` call without `pointToLayer`. The three calls (tier map boundary and tiers, change map) now draw a Point as a canvas circle. Red: the guard failed on all three. | `3ce08a4` |
| M9-16 | JS scan skips any line starting with `*` | close | Fixed in M9 (`9c50b1c`): `JS_COMMENTS` strips `//` lines and `/* … */` blocks only, and the fail-closed plants include a `*fetch(…)` continuation line | `9c50b1c` |
| M9-17 | `export.py` docstring line of 140 characters | close | Wrapped in M9 (`9c50b1c`). No docstring line in `export.py` is over 100 characters now. | `9c50b1c` |
| M9-18 | JS scan checks only literal `url()` paths | fix (documented) | The scan cannot know which ids a run-time URL will use. `_js_refs` now says so, and names what covers those URLs: `export_urls` writes every city page and panel, which `test_export_urls_are_what_the_app_serves` asserts per city. | `1f4a13f` |
| M9-19 | Compare keeps `/compare/?…` until the first change | close | Cosmetic and recorded: both addresses open the same state, and the first change rewrites it | n/a |

## M11

### How the M11-N numbers map

`docs/superpowers/rulings-m11.md`, section "Follow-ups", read top to bottom. Each bullet under
"Parked minors, from the ledger" gets the next number, 1 to 7. Bullets with several parts are split
into a, b, … below. "Fixed in final wave" and "M10 follow-ups this milestone resolved" are marked
done, so they get no number. "M10 follow-ups left open" belong to the M10 section (Task 10). Under
"New in M11 and open", the German interface bullet was delivered by M12 and gets no number. The
other four get 8 to 11. The numbers:

| N | Bullet in rulings-m11 Follow-ups |
|---|---|
| 1 | End labels for line charts with more than 8 series |
| 2 | The `[hidden] + .download` adjacency rule |
| 3 | Two-line headline charts cite only the LAU run |
| 4 | `-1e-5` / `-.5` over-neutralised in CSVs (a); the key wrap width is estimated (b) |
| 5 | The story `remember` decision could move to `permalink.js` |
| 6 | Search: "No match" is an `li` in the listbox (a); key dispatch untested (b); stale `orgs` pyright hint (c) |
| 7 | Sources: silent on `ContentError` (a); synthetic fixture owners (b); quoted entries only (c); loose series-id check (d) |
| 8 | HTML legends other than the tier key are not in downloads |
| 9 | Search does not cover narrative text or quotes |
| 10 | The render pass's permalink step does not require two boundaries |
| 11 | A reader pan within the 200 ms resize debounce is not written to `at=` |

This matches every item the Task 9 brief names, 1 to 11. No number was ambiguous.

### Items

| id | item | ruling | reason | commit |
|---|---|---|---|---|
| M11-1 | End labels for more than 8 series | fix | With more than 8 lines only the focus (coloured) series are labelled, at every width. The grey context lines stay unlabelled, and their names are in the tooltip and the table. Before, a wide chart labelled every line. Red: the node test failed at 900 px, its first wide width (10 end labels instead of 2). | `e04ae5e` |
| M11-2 | `[hidden] + .download` rule untested | fix | A Chrome test (`test_layout_browser.py`): on Compare's table view the hidden chart's next sibling is its Download control, and it computes to `display: none`. On the lines view it shows. Red: without the CSS rule, `block`. | `1faee4b` |
| M11-3 | Two-line headline charts cite only the LAU run | fix | The time and story tabs' headline Cite names both boundaries ("city proper (LAU) and metro area (FUA)"). Its snapshot note names each run and its OSM snapshot (`cite.snapshot_two`, en and de), with no single run id. A city without a FUA run keeps the LAU title and run. The existing rule test now accepts a both-boundary title only when it cites both runs of one city. Fix round: `cite.snapshot_two` was defined twice in each catalogue. The second copy is gone, and the catalogue loader now refuses a key defined twice. | `7ccb6bc`, fix round |
| M11-4a | `-1e-5` / `-.5` over-neutralised in CSVs | keep | Safe: the cell gets a leading `'` and is read as text. It can never run as a formula. The pattern stays the same in `safeCell` and `safe_cell`. Telling exponent and bare-decimal numbers from formula starters would widen a security rule for two number forms the tables never print. | n/a |
| M11-4b | Key wrap width estimated | fix | The download measures each key label with `getComputedTextLength` (11px, in a hidden SVG) and wraps by that width. It falls back to the estimate where the browser cannot measure. Red: two 40-character labels measured at 60 px still wrapped. | `9a8aa07` |
| M11-5 | Story `remember` decision in `story.js` | fix | `permalink.js` `stepMemory(steps, hash)`, node-tested. `story.js` only writes the hash it returns. | `cc15046` |
| M11-6a | "No match" is an `li` inside the listbox | fix | A `<p class="search-status" role="status">` under the box, outside the listbox, says it. The list stays closed and empty. The render pass's keyboard step checks it in Chrome. Fix round: every way out (Escape, blur, a click outside) clears the status. An empty status stays rendered (no box, never `display:none`) so its live region is in the accessibility tree. "No match" is also said through `#live`. Node tests cover each exit and the announcement; the keyboard pass checks Escape. | `8bb0e53`, fix round |
| M11-6b | Key dispatch untested outside `--keyboard` | fix | Node tests drive the keydown handler: Down/Up wrap, Enter goes, the first Escape closes, the second clears. With no match, Down does nothing. Red: without ArrowUp handling the test fails. | `8bb0e53` |
| M11-6c | Stale `orgs` pyright hint in `search.py` | fix | `orgs` and `narratives` are typed empty defaults before the `try`, not reassigned untyped in the `except`. pyright 1.1.411 reports nothing. | `8bb0e53` |
| M11-7a | Sources check silent on `ContentError` | fix | When a file it needs cannot be read, the "How they measure" check says it was not checked and names the file and error, in the check's problem list. The English check has no notes channel. A cause the coverage check already said, word for word, is not repeated (figures.csv, reconcile.yaml), so a broken file there is one problem. Known exception: a broken `differences.yaml` is said by the explainer, each profile and this line, one per reader. The dedupe matches message text, so a reworded side shows up as a double report in `test_content_m8`, never as silence. | `05966e7`, `7e75c01` |
| M11-7b | Fixture owners are synthetic | keep | The fixtures test the rule. The shipped content is checked by `test_shipped_figure_sources_have_complete_cited_dimensions`. | n/a |
| M11-7c | The content check covers quoted entries only | keep | By design: only a quoted source has a Sources row (`test_an_unquoted_mapping_entry_is_not_checked`) | n/a |
| M11-7d | Series-id check is loose | fix | It reads the exact keys the scripts use: `series.presets` ids and each point's `headline` / `ecf_qecio` / `clean_cities`. Red: a renamed point key passed the old string search. | `05966e7` |
| M11-8 | HTML legends other than the tier key not in downloads | fix (documented) | One form is read, `.legend .chip` inside the container, the one `chart.js` draws. `keyOf` says so, a node test pins `renderTiers`' form, and another pins `keyOf`'s reading of it. The Counts and plan keys sit beside their charts, outside the container, and are not in the image (open idea below). | `9a8aa07` |
| M11-9 | Search over narrative text and quotes | keep | Brief ruling: a new feature that would change search scope and index size. Recorded as an open idea. | n/a |
| M11-10 | Permalink step does not require two boundaries | fix | The step reads the boundaries the tier page lists with a map (its file list, independent of the radios). The map must offer exactly those. Where the page has LAU and FUA, the step restores FUA, the non-default one. | `7d2e5ed` |
| M11-11 | A pan within the resize debounce is lost | fix | `readerMoves` records the view a resize leaves. The next `moveend` is the resize's only when it shows that same view (as `at=` writes it), so a pan or zoom inside the 200 ms is written at once. Node test. | `28aaa59` |

### Open ideas (not built)

- Search over narrative text and quotes (M11-9).
- The Counts and plan keys in a downloaded image (M11-8). They are HTML lists beside the chart,
  and their glyphs are lines, rings and dots, not the tier key's swatches.
