# M13 minors ledger

Every open, unmarked minor in the Follow-ups of `docs/superpowers/rulings-m8.md` … `rulings-m12.md`,
triaged by the M13 spec §4.8 rule:

- **fix**: a defect, a drift risk or a misleading test, fixed with a red-first test;
- **close**: obsolete or already fixed;
- **keep**: a deliberate trade-off.

Tasks 9 and 10 add the M9, M11, M10 and M12 sections. Task 10 also adds the M13 carry-overs.

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
| M8-2 | Cumulative mapped line shares the "km per year" axis | fix (user review: panel) | The mapped line is a second panel below the per-year chart, on the same years (one x scale): its own labelled axis ("mapped km since 1 Jan {year}"), a zero line, nice ticks over the change from below 0 to above it. The per-year panel has one axis again; the right axis, `alignZero` and `thinTicks` are gone. The panel is an image with its own name. Cap rule (`OFFSCALE_FACTOR`, unchanged): targets up to 3× the largest plotted figure, including the mapped change, stay on scale; kept so Vorrangnetz's 60/100 km targets do not become caps. First built as a right axis (`7da510e`). | `7da510e`, `f317a19` |
| M8-3 | Paris in-service by day; rolling UTC export | close | M13 Task 1 made in-service hourly (Paris, Helsinki) | `4466d9d` |
| M8-4 | Unreachable km-only Counts chart branch | fix | Removed. `countsChart` returns null without a line, as the tab draws no chart then. The test now asserts that. | `ff2bb02` |
| M8-5 | Unexplained `test_overlay_facts` failure | close | No repro in 200 runs: 100 alone and 100 inside `tests/test_content_m8.py` in shuffled order, 0 failures (commands below). A reader opened before a write cannot read stale data: the database uses a rollback journal and Python's sqlite3 holds no read transaction between statements. A new test opens the reader first, evaluates, writes twice and evaluates after each write. The one failure mode found needs a reader that keeps a statement open: then the write waits 5 s and fails with "database is locked". Red-proof: the test fails that way when it keeps a cursor open. Nothing in the test's path keeps one. | `e91150f` |
| M8-5b | The writer-lock failure mode found under M8-5 | keep | A reader that keeps a statement open makes the next write wait 5 s and fail with "database is locked". This is kept as recorded, not fixed (review 10). It fails loudly and never as a stale read. It needs an unexhausted cursor, and `ReportData` reads with `.fetchone()` / `.fetchall()` on temporary cursors (`report/data.py`), which CPython finalises at once. App reads and CLI writes run in separate processes. | — |
| M8-6 | No test that Copenhagen 37 / Strasbourg 52 are suspect | fix | The test asserts the rule on a fixture figure: the `suspect` column of `reports.csv` gives the mark and the note exactly when it is set, both ways | `a8789f5` |
| M8-7 | Mean-per-day link (counter index v2) | close | M13 Task 2 built index v2 | `b5b76dd` |
| M8-8 | Madrid detector clause hand-written inside a generated block | fix | `note:` / `note_de:` on the Madrid entry in `config/counters.yaml`, rendered from the facts. A changed note makes the committed methodology stale. `require_de` enforces the German clause, and `reader_prose` lists it. | `ff80efe` |
| M8-9 | Phone-width CSS tests assert the rule, not the cascade | close | M13 Task 5 added browser tests for the phone cascade | `d609ebc` |
| M8-10 | Starlette `httpx` deprecation warning | fix | `httpx2` is in the dev group. Starlette 1.7's TestClient takes it, so `pytest tests/test_app.py -W error::DeprecationWarning` passes, and the gate's pytest output has no warning. The export keeps its targeted `catch_warnings`: `httpx2` is a dev dependency only, and an install without the dev group falls back to `httpx` and warns. Tests: the TestClient imports with no warning (red: with `httpx2` uninstalled), and the export imports with no warning while `httpx2` is blocked (red: without the filter). In a dev install the export also renders through the `httpx2` TestClient, because `export.py` imports `fastapi.testclient`. So this changes the client under the export, not only under the tests. The export tests and the 442-file German export run cover it. `content --check --online` still fetches: 147 lines against the baseline of 143 (142 not found, as before; 3 "cannot fetch" from the remote hosts: telex.hu 403, grandlyon timeout, cityramag 503, with 2 continuation lines). Task 13b's online counts: M13-l. | `5ee00fe` |
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
| M13-T1a | The rolling-export test passes under both in-service rules (day and hour) | fixed: new test `test_paris_rolling_export_counter_starting_mid_day_keeps_the_first_local_day` (a counter first reported at 14:00 local on the export's first day); red under the day rule, green under the hour rule | final fix round (`af16650`) |
| M13-T1b | The outage test has no red-proof | fixed: red-proofed by weakening the rule to `reporting >= 1`; `test_an_hour_missing_inside_the_span_is_still_an_outage` fails (`assert not True`), as do the in-service-span and fold tests; no code change needed | final fix round (`af16650`, test only) |
| M13-T2a | `_signed_pct` prints −0.0 % | fixed in Task 10, see the M13 carry-overs section | Task 10 (`e7dc007`) |
| M13-T2b | Unclosed sqlite connection in `tests/test_counter_index_v2.py` (~1702) | fixed in Task 10, see the M13 carry-overs section | Task 10 (`900b980`) |

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
| M11-8 | HTML legends other than the tier key not in downloads | fix (user review: panel) | Two forms are read: `.legend .chip` inside the container (chart.js), and a list beside the chart that the container names in `data-download-key` (the plan page key, a Counts tab key). Each entry's mark gives its glyph (`glyphOf`: line, dashed line, dot, ring or swatch) and a label wider than the image wraps. Node tests pin both readings and the glyphs; pytest pins that each plan and Counts chart names its key. | `9a8aa07`, `b645570` |
| M11-9 | Search over narrative text and quotes | keep | Brief ruling: a new feature that would change search scope and index size. Recorded as an open idea. | n/a |
| M11-10 | Permalink step does not require two boundaries | fix | The step reads the boundaries the tier page lists with a map (its file list, independent of the radios). The map must offer exactly those. Where the page has LAU and FUA, the step restores FUA, the non-default one. | `7d2e5ed` |
| M11-11 | A pan within the resize debounce is lost | fix | `readerMoves` records the view a resize leaves. The next `moveend` is the resize's only when it shows that same view (as `at=` writes it), so a pan or zoom inside the 200 ms is written at once. Node test. | `28aaa59` |

### Open ideas (not built)

- Search over narrative text and quotes (M11-9).

### M8-5: the commands

The 200 runs used a worktree at `8c18c5b` (`data/scratch-m13/t10/wt`, removed after), so later
edits could not change the code under test. The script is
`data/scratch-m13/t10/shuffle_m8.py` (git-ignored). It collects the node ids with
`uv run pytest tests/test_content_m8.py --collect-only -q` (81 ids), then runs:

- 100 times `uv run pytest -q -p no:cacheprovider tests/test_content_m8.py::test_overlay_facts`;
- 100 times `uv run pytest -q -p no:cacheprovider <the 81 ids>`, shuffled with
  `random.Random(i)` for run `i` = 0 … 99.

Result: `{'isolated': 0, 'shuffled': 0}`. All 200 runs exited 0.

## M10

### How the M10-N numbers map

`docs/superpowers/rulings-m10.md`, section "Follow-ups", read top to bottom, plus the bullet that
`rulings-m11.md` lists under "M10 follow-ups left open" beyond those of rulings-m10. Each bullet
gets the next number. Two kinds of bullet get none:

- a bullet marked as out of scope: "Dark PNG maps were not made (out of scope)". Its own text
  says what would reopen it (a page that embeds a PNG). No page does.
- the M11 bullet that repeats rulings-m10 ("Light change-map colours …; the deferred minors and
  the hosting size (see rulings-m10)"). It adds nothing new.

The numbers:

| N | Bullet |
|---|---|
| 1 | Light change-map colours under 3:1 on white |
| 2 | Series palette: normal-vision ΔE only |
| 3 | `report maps` `.run` marker ignores palette changes |
| 4 | Figures tables scroll at 200 % zoom on a 1280 px screen |
| 5 | Missing-token fallback wording (spec §5 versus the ruling) |
| 6 | Screen-reader testing with real assistive technology was not done |
| 7 | Deferred minors (split a, b, … below) |
| 8 | Render-pass cost: `--pages all` with `--interact` takes about an hour |
| 9 | From rulings-m11: `regions.py` tag counting inside `<script>` and comments (a); source-grep tests that could become behaviour tests (b); `.sr-only` / `.visually-hidden` as one rule twice (c) |

This matches every number the Task 10 brief names: 5 = missing-token wording, 7 = the deferred
minors, 8 = render-pass cost, 9 = `regions.py` and the hiding rule. No number was ambiguous.

### Items

| id | item | ruling | reason | commit |
|---|---|---|---|---|
| M10-1 | Light change-map colours under 3:1 | close | M13 Task 4: the change colours are ≥ 3:1 on all three light grounds, and the PNGs are regenerated | `ffa9675` |
| M10-2 | Series palette normal-vision only | close | M13 Task 4: the rule holds under normal vision, deuteranopia and protanopia, in both themes | `ffa9675` |
| M10-3 | `.run` marker ignores the palette | close | M13 Task 4: the marker holds a palette hash | `ffa9675` |
| M10-4 | Figures tables scroll at 200 % zoom | close | M13 Task 5: they stack below 700 px | `d609ebc` |
| M10-5 | Missing-token fallback wording | fix (doc) | The behaviour stays: a neutral grey and one `console.error`, which fails the render pass. M10 spec §5 now describes it, with a dated note saying why the spec's "light value" was not built. | `5360161` |
| M10-6 | No screen-reader test | keep (owned by spec §4.7) | M13 spec §4.7 is the screen-reader pass (or its labelled AX-tree fallback), a task of its own | n/a |
| M10-7a | The `importlib` loader copied into the tests | fix | `tests/helpers.load_script(rel_path)`. All six copies use it now. A guard test finds no other `spec_from_file_location(` in `tests/`. Red: the guard listed five test files before the change. | `cfcf9a5` |
| M10-7b | `lab()` white point off by about 0.01 | close | Done in M13 Task 4 | `ffa9675` |
| M10-7c | `ciede2000` unannotated, unused 3-digit hex branch | close | Done in M13 Task 4 | `ffa9675` |
| M10-7d | `CITY_COLOURS[:7]` leaves series 8 unused | close | Done in M13 Task 4: `CITY_COLOURS == SERIES_COLOURS` (8) | `ffa9675` |
| M10-7e | Text-colour scanner sees inline attributes only; its hex regex could hit `#add` | fix (regex) | The JS colour-literal scan (`tests/test_app.py`) takes a hex colour only as 3, 4, 6 or 8 digits standing alone. It passes over the string argument of a selector call (`querySelector`, `closest`, `matches`), where `"#add"` is an id. Tested both ways: `querySelector("#add")` is no colour, and `el.style.fill = "#add"` is one. Red: the old regex flagged `querySelector("#add")`. The computed-fill side is covered by the Chrome render pass (axe colour contrast on drawn charts). | `0e3ca8e` |
| M10-7f | A chart redraw resets the hover state | fix | `renderLines` and `renderTiers` keep the hovered series and point (lines) or year (tiers) per element. A redraw shows it again until the pointer leaves, and a redraw without that series shows nothing. Node tests. Red: after the redraw the hover line was hidden and the tip was empty. | `62aa785` |
| M10-7g | `regions.py` reads double-quoted wrappers only; a nested `.scroll` gets its own stop | fix | Single or double quotes. A wrapper inside a wrapper gets no stop of its own: one per scroller, as for a table inside one. Red: no stop for `class='wide scroll'`, and three stops for the nested case (the guard was also broken by hand to show it). | `aa5591b` |
| M10-7h | `panel.js` draw/load test seams | keep | `createPanel(root, {draw, load})` takes the two functions as options that default to the real ones. This is how the node test checks the release of charts without a DOM chart or a fetch. The seams are documented in the file, and pages never pass them. | n/a |
| M10-7i | `QUOTE_MARK` before `CODE_MARK` can misnest | fix | `_Numbering.inline` splits the code spans first and holds each as a numbered slot while the quotation and term marks are read. A mark holds whole code spans or none, and a mark inside a code span stays text. Renderer test. Red: `<q lang="de">a `b</q>` c` gave `<q …><code>b</q></code>`. | `ca37a45` |
| M10-7j | Tier key and popup tests grep the source | fix | The popup is now a module, `static/js/tier-popup.js` (`tierPopup(p, cfg)`), and `map.js` imports it. A node test asserts its DOM: the first child is the tier's full name, then the rows, the way link and the tags as text. The tier key's node test already existed (`chart.test.mjs` "renderTiers keys every tier by name …"), so both Python source greps are removed. Red: the module did not exist. | `870574b` |
| M10-7k | The plans "suspect" alt text is unproven | fix | A test asserts that the mark of a suspect figure is the word `page.plans.suspect` in the page's language, inside the row (en and de). Red: with the word removed from the template, both cases failed. | `05937a4` |
| M10-7l | The axe interact test asserts a list only | fix | `r["axe"] == []` for every visit. Red: an image without alt planted on every exported page failed it (`image-alt`, critical). The old assertion passed in that case. Slow test, run here: 1 passed in 205 s. | `5d0a962` |
| M10-8 | Render-pass cost (about an hour) | keep | Runtime cost, recorded. The gate runs the fast tests; the full pass runs on demand. | n/a |
| M10-9a | `regions.py` counts tags inside `<script>` and comments | fix | Each script and each comment is blanked, at the same length, before the parse, and the edits go into the page at the same indices. Red: a `</div>` in a script string and a `<div class="scroll">` in a comment gave 5 stops instead of 2. | `aa5591b` |
| M10-9b | Source-grep tests that could be behaviour tests | fix | The same tests as M10-7j | `870574b` |
| M10-9c | `.sr-only` and `.visually-hidden` as one rule twice | fix | One rule with both selectors. A test asserts that exactly one rule names either. Red: two rules. | `aa5591b` |

## M12

### How the M12-N numbers map

`docs/superpowers/rulings-m12.md`. The section "Follow-ups" is read top to bottom, and the "Parked
from earlier tasks" bullet gives one number per part. After it come the three costs that
the Task 12 rulings leave to a follow-up, under "Ledger rulings by task". Each item gets the next
number. These get none:

- "The English-word sniff is a heuristic …": a statement of what the sniff is (its phrase sources
  are listed), not an open item;
- the export size, which is the M9 hosting follow-up (HANDOVER §12 Q4), as in the M9 section;
- the original national terms, which M13 Tasks 6 and 7 delivered (`0734764`).

The numbers:

| N | Item |
|---|---|
| 1 | Proper names passed over by a pinned list; a `lang` field would let the sniff drop it |
| 2 | German pages were not checked with a screen reader |
| 3 | `signed()` of a value rounding to zero prints "+0.0"/"+0,0" (Task 1) |
| 4 | `citeText`'s unused `lang` (Task 4) |
| 5 | The German number-check thresholds in `RULES["de"]` are drafts (Task 6) |
| 6 | "Strasbourg" may become "Straßburg" if the user asks |
| 7 | Task 12: the Norwegian terms carry no `lang="no"` markup |
| 8 | Task 12: the Slovak and Czech `gloss_de` still say "Schutzstreifen" |
| 9 | Task 12: the counters explainer's word budget is 310 (an allowance) |

This matches every number the Task 10 brief names: 1, 3, 4 and 5, 8 = Schutzstreifen and
9 = the allowance. No number was ambiguous.

### Items

| id | item | ruling | reason | commit |
|---|---|---|---|---|
| M12-1 | Proper names passed over by a pinned list | fix | New BCP 47 fields: `lang` on organisations (all nine shipped profiles), `source_lang` on counter entries and `title_lang` on plans. A title or publisher that holds our own words beside the name gets none: Oslo's "(state counters)", and the Vienna, Copenhagen and Lyon titles. A name that ends in a bracketed form takes the lead name's language. Where the bracket is in another language, a `bracket_lang` field (`source_bracket_lang` on counter entries) puts the bracket in its own `<span lang>` inside the name's element. This works in both directions: Helsinki is `en` with a Finnish bracket (`fi`), and Copenhagen is `da` with an English bracket (`en`). The fix round after review 10 added this; before it, the English words "City of Copenhagen" were tagged Danish. Pages write the language as the element's `lang`: the organisations list and headings, the publisher links, the Sources page, the plan titles and the counts attribution. A German `title_de` or `source_de` is ours, so it gets none. The search options carry the language too: `search.json` organisation entries have `lang` and `bracket_lang`, and `search.js` (`optionLabel`) writes them on the option's label. Before the review-10 fix round they had none, so the browser-built dropdown showed the Copenhagen name untagged. The sniff skips other-language subtrees (`visible_text`). `PROPER_NAMES` drops "Københavns Kommune (City of Copenhagen)" and "Plan for sykkelveinettet i Oslo". Copenhagen's entry is not restored: its English bracket is now in `lang="en"` wherever the name shows, on the pages and in the search options. That is the ledger's own criterion for leaving the list, and the sniff skips the bracket because it is declared English. The other eight stay, because each also shows without a `lang`: in prose (IT University of Copenhagen, Networks, Data and Society, Points of Interest, Streets for Kids, Cities for All, Sykkelstrategi for Oslo), in a source excerpt gloss (Confederation of the European Bicycle Industry), in the methodology tables and the Compare counters note the browser builds (City of Helsinki, Urban Environment Division), or in the population source of the methodology (INSEE …). Red: the models had no field. The sniff of the real German export finds no English word on 123 pages. Review-10 fix round: a test now pins a plan title without a web link as `<span lang>` (red: drop `lang_attr` from either template's no-URL branch). | `75df53b`, `56b7615` |
| M12-2 | German pages not checked with a screen reader | keep (owned by spec §4.7) | As M10-6 | n/a |
| M12-3 | `signed()` of a value rounding to zero prints "+0.0" | fix | `_localise` drops a `+` as it drops a `-` when no digit is non-zero. Python test over 0, −0, ±0.04 and ±1e-9 in both languages, plus `percent(signed=True)`. The JS `signed` already did this, and a node test now pins it. Red: `signed(0, "en")` was "+0.0". One methodology test pinned "+0.0 %" for a 0.0 % change; it now reads "0.0 %". No committed methodology line held "+0.0". Follow-through: the up/down class (overview Change column, the city header's change) follows the printed sign through `i18n.tone`, so a change printed as zero is neither. The full gate caught this: an `up` cell read "0.0". `test_every_up_and_down_value_carries_a_sign` now also checks the zero side; the fixture's changes all print as zero, so before it found nothing to check. Review-10 fix round: the a11y test now checks a nonzero change, up on `/` and down on `/de/` with the first-year headline moved, separately from the fixture's zeros (red: the template's class removed, or up and down swapped). | `e7dc007`, `ffb59c6`, `c56dcab` |
| M12-4 | `citeText`'s unused `lang` | fix | Removed, with the call in `cite-ui.js`. A node test pins the parameters `(f, accessed, url)`. Red: it read four. | `ec66aef` |
| M12-5 | `RULES["de"]` thresholds are drafts | fix (confirmed) | Confirmed against the German corpus. With its rule facts the German counters page has no literal rule statement (no false positive). With the facts taken away, every rule it states is caught. German twins of all 15 English seeded cases (6 that must pass, 9 that must be caught) behave as the English ones do. No pattern needed a change, so the rules are no longer drafts. Red: with "Zählstellen" taken out of `sites_after`, 4 of the 16 tests failed. | `231d1ef` |
| M12-6 | "Strasbourg" may become "Straßburg" | keep | Only if the user asks (rulings-m12) | n/a |
| M12-7 | Norwegian terms without `lang` markup | close | M13 Task 7 added the term mark `<i lang="nb">…</i>`, and the Oslo terms use it in both editions | `0734764` |
| M12-8 | Slovak and Czech `gloss_de` say "Schutzstreifen" | close | Done in M13 Task 7 | `0734764`, `4df09ac` |
| M12-9 | Counters explainer word budget 310 | keep | An allowance, recorded in rulings-m12. The budget test asserts it (150–310). | n/a |

## M13 carry-overs

Items an earlier M13 task or the controller deferred to Task 10 (M13-T2a and M13-T2b are listed
in the M8 section's "Logged here" table). The leak test change is in this section too: Task 7's
term mark left it open.

| id | item | ruling | reason | commit |
|---|---|---|---|---|
| M13-a (T2b) | Unclosed sqlite connections in `tests/test_counter_index_v2.py` | fix | The v1/v2 reader test closes its connection (`closing`), and the four check tests use a `check_conn` fixture that closes. A guard test runs the rest of the file in a subprocess with `-W always::ResourceWarning` and finds no "unclosed database". Red: the guard failed on the four check tests after the first fix, and the first test alone gave 1 warning before and 0 after. | `900b980` |
| M13-b (T2a) | `_signed_pct` prints "−0.0 %" | fix | At `8c18c5b` it printed "0.0 %" for a small negative, because `i18n.signed` already dropped the minus, but "+0.0 %" for a small positive. With M12-3, all of 0, −0, ±0.04 and ±1e-9 print "0.0 %" / "0,0 %". Test in `test_methodology.py`. Red: `+0.0 %`. | `e7dc007` |
| M13-c | `tools/pick_palette.py` defaults to seed 13, which does not reproduce the pick | fix | `SEEDS = {"series-light": 2, "series-dark": 1, "change-light": 1, "change-dark": 1}`, checked against the Task 4 report. `search` and `main` use the palette's seed unless one is given. Fast test: `main([])` runs each palette at its `SEEDS` seed, and `--seed` overrides (red: no `SEEDS`). Slow test (`@slow`, 3 to 4 minutes a palette): each default search returns the committed palette, `charts.SERIES_COLOURS`, the dark `--series-*` tokens, `change.CATEGORY_COLOURS` and the dark `--change-*` tokens. Run here: 4 passed, 193 to 236 s each. | `ef6b33e` |
| M13-d | The 700 px Figures block copies the 600 px card rules | fix (test) | A test asserts that the card declarations of the two blocks are the same line for line, with the table selector written as one name. Red: one changed declaration in the Figures block failed it. | `bb29349` |
| M13-e | Browser tests: Compare at 390 px, Figures at 701 px | fix (test) | Chrome: the compare table cells are `block` at 390 px, and the Figures cells are `table-cell` at 701 px. Red: with the Figures media query at 701 px and the 600 px `td` rule dropped, both failed. | `f1988a2` |
| M13-f | `_phone_rules`' 700 px regex reads the compare-filters block | fix | It reads the 600 px blocks and the 700 px block that opens with `table.stack.figures`. A test asserts that `.country-grid` and `.filters-body` are not among its selectors. Red: with the old regex they were. | `bb29349` |
| M13-g | A malformed mark passes `content --check` | fix | `malformed_marks` (in `content/check.py`): every tag outside code spans must be an exact renderer mark, `<q|i|blockquote lang="<BCP 47>">` with its closing tag, properly nested. Anything else is a "malformed mark" problem of the document, in both languages (`_check_document`). It reads the parsed text, so a tag that a re-stamp broke across lines is the same YAML and reads as one line. Red: 9 malformed forms (`<i lang="da" >`, `<I …>`, a bare `<i>`, single quotes, `lang="d a"`, unclosed, a close alone, `<span lang>`, crossed marks) all passed before. Review-10 fix round: it also refuses a `<blockquote>` that is not the whole paragraph, and a mark opened inside the same mark (`<q>` in `<q>`). Both are now in the parametrised test, and `content --check` stays clean. | `454eca9`, `fdc850b` |
| M13-h | The leak test's content phrases keep `<i lang>` markup | fix | `i18n._NOT_PROSE` splits at an original term as at a quotation (`<q|blockquote|i …>…</…>`, across line breaks). Before, a sentence holding a term kept its markup, so the phrase could never match a page and caught nothing. Red: one sentence with `<i lang="da">` came back whole. | `5b19885` |
| M13-i (user review: index-wording) | Two names for the counter index's day ("valid day", "complete day") | fix | One term: "complete day" / "vollständiger Tag". The methodology's index rule and its day definition now say "complete days" / "vollständige Tage" and "A day is complete when …" / "Ein Tag ist vollständig, wenn …"; content and UI strings already used it. A test reads the rendered methodology (en, de), every `content/**/*.yaml`, the app scripts and the app templates for "valid day(s)", "day is valid", "gültige(n) Tag(e)" and "Tag ist gültig". Red: 2 hits in the English template. Code names (`min_valid_pct`) stay. | `5743a5a`, `c1da90f` |
| M13-j (G1) | The Bezirke remainder label has no gloss in English | fix | `subarea.remainder` (en): "Outside the {n} Bezirke (districts), at the LAU edge", the original term first, then the excerpt's gloss in brackets (`infravelo-organisation/responsibility`, "the districts"), as Task 7's UI labels do. German unchanged. The Berlin change page is regenerated (runs 740 → 713; only that row differs, the PNG is byte-identical), so `test_german_bezirk_table_parses_back_to_the_english_values` still parses the shipped page with the new label, unchanged. | `e64a0eb`, `e7cb62f` |
| M13-k (G7 pointer) | `[#main-roads]` links to the top of the methodology | fix | Methodology h2/h3 headings carry ids, the slug of the English heading at the same position, so both editions share them (`/methodology#headline-and-presets`, `/de/methodology#headline-and-presets`). The data reference's route names that id. Tests: both files have the same heading outline; the en and de pages carry the same ids; every link into the methodology on every exported page lands on an id of that edition (red: no ids). | `7654970` |
| M13-l | `content --check --online`: PDF sources unread, a timeout counted as a failure of the excerpt | fix | A PDF (content type or `%PDF-`) is read by `pdftotext`, in reading order and in content-stream order (`-raw`), each run with a 60 s timeout; its text is not stripped as markup and is compared with all whitespace removed (pdftotext drops the spaces of justified text). HTML: an inline element's tag (`a`, `span`, `sup`, `em`, …) is dropped without a space, any other tag is a space; HTML is not compared without whitespace ("21 47 km" must not match "2 147 km"). Without `pdftotext` a PDF's excerpts print "skipped: no PDF reader" and do not fail the check; a pdftotext timeout or failure is "cannot read PDF". A timeout of the fetch is retried once (30 s, then 90 s); a host that still does not answer is "unreachable (network problem)", not "excerpt not found". Tests use four hand-built PDFs and monkeypatched `httpx.get` / `subprocess.run`. Real run: 143 lines at `main` (brief), 145 at the start of Task 13b (all "not found"; every host answered), 36 after the PDF reading, **14** after the review fixes (all "not found", 0 unreachable, 0 skipped, 0 cannot read). The review round also showed one excerpt copied with the old tag-space artefact (Bordeaux `epci-28-communes`, "( EPCI )"); it now reads "(EPCI)" as printed. The 14, by cause: scanned PDF pages with no text layer (Fortschrittsbericht 2025 ×6, 2023 ×1) 7; PDF table label and value in different columns (TSK ročenka) 3; running header inside the sentence (EU act, "4 EN") 1; soft hyphen at a line break (Amsterdam MJP) 1; PDF text boxes interleaved (Lyon `breakdown-2023`) 1; list bullets between the excerpt's items (Bordeaux plan) 1. (The first count of 36 filed 18 HTML tag artefacts and 2 JSON-escaped lines; all 20 were tag artefacts, the Paris pair a `<sup>er</sup>`, and 2 "interleaved" PDF lines were missing spaces.) None is a wrong excerpt. | `f3cd6b4`, `cde667a`, `c36c87e`, `b629e92`, `2a5ad84` |
| M13-m (Task 11 review) | Panel heading unguarded; R1/R3 reasons; `orca_pass` passes three variables through | fix | The banner test also asserts each panel fragment has its `<h2>` (red: `<h2>` made a `<p>`). The screen-reader log names the run's process locale for R1 (`LANG=en_US.UTF-8`, renderer `--lang=en-US`) and no longer claims what a German voice does; R3 gives Orca's reason (an unfocused ancestor dialog is spoken by its text, the "Loading…" placeholder, modal or not). `DROP` adds `SSH_AUTH_SOCK`, `GPG_AGENT_INFO`, `GTK_MODULES` (red: the isolation test with them set). | `06c6b29` |
| M13-n (Task 13a) | Downloaded chart images do not wrap the title and the meta lines | fix | The title (15 px, 600) and the source and attribution lines wrap at spaces inside the image, by the width the page measures (`getComputedTextLength`, as the key does) or an estimate; the chart moves down by the extra title lines. Node tests at 390 px (red: the title stayed one line, and no measure was handed over). Rendered: the German plan download at 390 px has three title lines and four meta lines, all inside. | `1296721` |
