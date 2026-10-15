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
