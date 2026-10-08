# M8 follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the M8 follow-ups that are defects or drift risks and need no method decision, so
the next milestone starts from a clean base.

**Architecture:** Small, independent fixes grouped by area: app notes and attribution, counter
config as the single source of the index thresholds, plan chart, colour tokens, DB/adapter
hygiene, content-check hygiene, docs. No new data, no new OSM runs, no method version changes.

**Tech Stack:** Python 3 (uv, FastAPI/Starlette, Jinja2, pytest, ruff), plain ES modules with
`node --test`, SQLite.

**Spec:** `docs/superpowers/specs/2026-10-07-velometer-m8-design.md` (binding) and the Follow-ups
list in `docs/superpowers/rulings-m8.md` (the defects this plan closes).

## Global Constraints

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest && node --test "src/velometer/app/static/js/tests/*.test.mjs"`. Network tests are `@pytest.mark.slow`.
- OSM lengths are **mapped km** (ADR 0006). No construction verb for OSM figures outside quotes.
- Counters are context: "recorded at counter sites", no causal wording between counts and km.
- No new OSM runs, no writes to `velometer.sqlite` (the stored numbers must not change; every
  check — `timeseries`, `reconcile`, `trust`, `report methodology`, `content`, `counters` — still
  exits 0 with identical output values).
- No method changes: overlay rows stay overlay_v4, counter index rule stays spec §2.13. A change
  that would move a stored or displayed number is out of scope; stop and report it.
- The app stays on 127.0.0.1, read-only, CSP unchanged (only external host
  `tile.openstreetmap.org`). No npm packages, no build step.
- Tests assert the rule they exist for, not today's value; each fix has a test that fails without
  it (red-proof by breaking the rule).
- Commits: explicit paths, one trailer line `Assisted-by: Claude:claude-opus-5-5`. Never push.

## Review Focus

- A city whose counter base year is not 2019 drawn on Compare: the unit text must not claim
  "2019 = 100" for it (Task 1).
- A broken or missing data file (`retrieved.json`, `counters.yaml`, source registry) must produce a
  visible note, not a silently thinner page (Task 2).
- A future plan whose targets are cumulative or total km must not be drawn under a "per year"
  axis (Task 4).
- An empty overlay rerun must not leave the previous rows looking current (Task 6).
- Dark mode: every new colour token has a dark-mode value with enough contrast (Task 5).

---

### Task 1: Compare counter metric: footnote, unit, parity

Follow-ups: "Compare: the footnote … shown for the counter index metric"; "`compare.py`
`COUNTER_UNIT` ('2019 = 100', wrong for a base-2020 city drawn as a line)"; "the compare counter
title and footnote are duplicated outside the parity test"; "py/js counter computations are
hand-mirrored without shared cases".

**Files:**
- Modify: `src/velometer/app/compare.py` (`COUNTER_UNIT` ~69, `counter_lines` ~197),
  `src/velometer/app/templates/compare.html:69`, `src/velometer/app/static/js/compare.js`,
  `src/velometer/app/static/js/counter-model.js`
- Create: `tests/counter_cases.json` (shared py/js cases, same pattern as `tests/compare_cases.json`)
- Test: `tests/test_app_m8_counts.py`, `src/velometer/app/static/js/tests/counter-model.test.mjs`

- [ ] **Step 1:** Failing tests: (a) server-rendered `/compare?m=counter_index` has no "flagged
  year" and no "Headline:" text in its footnote, while `/compare?m=headline` still has both;
  (b) the counter unit text names the base year from each drawn city's data: if every drawn city
  has base 2019, "2019 = 100"; if a drawn city's base differs, the note names that city's base
  year (build a payload fixture with one base-2020 city); (c) the JS footnote and title for the
  counter metric equal the Python ones (extend the existing py/js parity test so title and footnote
  are inside it).
- [ ] **Step 2:** Run, confirm each fails for the stated reason.
- [ ] **Step 3:** Implement: the footnote is metric-aware (counter metric gets its own short
  footnote: index base and "counters are context"); the unit/base text is computed from the
  payload's per-city base year in both py and js; move counter title/footnote strings to one place
  per language that the parity test covers.
- [ ] **Step 4:** Shared cases: write `tests/counter_cases.json` with inputs and expected outputs
  for the py/js mirrored counter computations (index line points, notes, unit text); a pytest and a
  node test both load it. Red-proof by changing one expected value.
- [ ] **Step 5:** Run focused tests, then the gate. Commit
  `fix(app): counter metric footnote and base-year unit on Compare, shared counter cases`.

### Task 2: Visible notes for broken inputs and missing licences

Follow-ups: final review M3/M4 ("planned-network line names no licence"; "a corrupt
`retrieved.json` silently removes the measures licence"; "a source-registry load error removes the
plan page's text and quotes without a note"); "a `counters.yaml` ConfigError makes the no-data note
vanish silently".

**Files:**
- Modify: `src/velometer/app/plans_pages.py` (`measures_retrieved` ~208),
  `src/velometer/app/templates/plans_berlin.html`, `src/velometer/app/main.py` (`plan_page` ~791,
  counters config use ~576 and ~913), `src/velometer/app/counts.py` (`counters_config`)
- Test: `tests/test_app_m8.py`, `tests/test_app_m8_counts.py`

- [ ] **Step 1:** Failing tests: (a) `/plans/berlin` names the licence of the planned-network
  layer, read from `retrieved.json` (never typed); (b) with a corrupt `retrieved.json` the page
  shows a "data source record unreadable" note instead of dropping licence lines; (c) with a source
  registry load error, `/plans/berlin` shows the same `content_error` note pattern `/organisations`
  uses; (d) with a malformed `config/counters.yaml` the Figures tab and Compare show a "counter
  configuration unreadable" note instead of silently omitting the no-data note.
- [ ] **Step 2:** Run, confirm red.
- [ ] **Step 3:** Implement with the existing `content_error` / note patterns; no new styles unless
  needed.
- [ ] **Step 4:** Focused tests, gate. Commit `fix(app): notes for unreadable inputs, planned-network licence`.

### Task 3: One source for counter thresholds, base years and overlay version in prose

Follow-ups: final review M1-tail ("the base year prints 100 whatever its number of qualifying
sites (`counters/index.py:122`)"), M5–M7 and Task 11 ("`counts.html`, `content/counters.yaml` and
`compare.py` spell out `MIN_VALID`, `MIN_SITES` and the base years by hand"; "the methodology's
Madrid and Helsinki bullets hard-code facts outside the generated blocks"; "the methodology takes
the latest overlay version from config, the page and the facts from `plan_overlay`";
"`berlin_context` derives the 1 January 2022 baseline from the plan's first target year instead of
a named constant").

**Files:**
- Modify: `src/velometer/counters/index.py` (~122), `src/velometer/app/templates/city/counts.html`,
  `content/counters.yaml`, `src/velometer/report/methodology.py`,
  `src/velometer/report/templates/methodology.en.md.j2`, `.de.md.j2`, `docs/methodology.md`,
  `docs/methodology.de.md` (regenerated), `src/velometer/app/plans_pages.py` (`berlin_context`
  ~323-336)
- Test: `tests/test_counters.py`, `tests/test_methodology.py`, `tests/test_app_m8.py`,
  `tests/test_content_m8.py`

- [ ] **Step 1:** Failing tests: (a) a base year with fewer than `MIN_SITES` qualifying sites gets
  no index value (spec §2.13) — synthetic input; the real data are unaffected (every base year has
  ≥ 9 sites; assert the real `counters --check` output is unchanged); (b) the Counts page and
  methodology render `MIN_VALID`/`MIN_SITES`/base years from the constants/config (test by
  monkeypatching the constant and seeing the text follow); content prose that states these values
  goes through a fact (`counter.*`) instead of literal text, and the content check refuses a
  literal threshold in counter prose; (c) Madrid and Helsinki methodology bullets are generated
  from config/data so `report methodology --check` fails when the config changes and the doc does
  not; (d) the methodology overlay version is read from `plan_overlay` (latest stored version), the
  same source as the page; (e) `berlin_context` uses a named constant `MAPPED_BASELINE =
  date(2022, 1, 1)` (spec §4.4), not the plan's first target year.
- [ ] **Step 2:** Run, confirm red.
- [ ] **Step 3:** Implement. Regenerate `docs/methodology*.md` with the project's report command;
  values must be identical to today's.
- [ ] **Step 4:** Focused tests, `report methodology --check`, `content --check`, `counters
  --check`, gate. Commit `refactor(counters): thresholds, base years and overlay version from one source`.

### Task 4: Plan chart axis and off-scale targets, counts key wrap

Follow-ups: "the axis label always says 'per year', so `km_cumulative`/`km_total` targets would
draw wrongly"; "`plans_berlin.html` key links depend on berlin.yaml dimension values, untested";
"`plan-chart.test.mjs` pins the chart margins 44/10"; "the counts key wraps at 390 px with a
leading '·'"; "the Counts/Intensity short names are duplicated in `counts.html` and `city.js`".
Controller observation (2026-10-08): on the Berlin Ergänzungsnetz chart the 2028–2030 targets
(350–450 km per year) set the y-domain, so the real data sit flat near 0.

**Files:**
- Modify: `src/velometer/app/static/js/plan-chart.js` (~117-174), `src/velometer/app/templates/plans_berlin.html`,
  `src/velometer/app/templates/city/counts.html:11`, `src/velometer/app/static/js/city.js:70`,
  `src/velometer/app/static/app.css`
- Test: `src/velometer/app/static/js/tests/plan-chart.test.mjs`, `tests/test_app_m8.py`,
  `tests/test_app_m8_counts.py`

- [ ] **Step 1:** Failing tests: (a) the y label follows the target quantity: per-year targets
  "km per year"; `km_cumulative` "km, cumulative"; `km_total` "km, total"; a chart mixing per-year
  targets with a cumulative quantity draws them on separate panels or refuses (pick the simpler;
  state it); (b) off-scale targets: when a target exceeds `OFFSCALE_FACTOR` (3) × the largest
  data value (reported, completed or mapped), the y-domain is set from the data and the nearer
  targets, and each off-scale target is drawn as a capped marker at the top edge with its value
  labelled (e.g. "↑ 450"); every target value stays readable in the table below; (c) every key link
  in `plans_berlin.html` points to an anchor that exists on the page (rule over all key links);
  (d) margin test asserts the rule it exists for (labels fit inside the SVG) instead of 44/10;
  (e) the counts key items are list items without a typed separator, so wrapping never starts a
  line with "·"; the Counts/Intensity short names come from one place (server passes them to JS or
  JS reads them from the DOM).
- [ ] **Step 2:** Run, confirm red.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Render `/plans/berlin` and one Counts tab at 1280 and 390 px with headless Chrome
  (as M8 Task 11 did); no horizontal scroll, console errors or CSP violations; screenshots outside
  the repo, paths in the report.
- [ ] **Step 5:** Gate. Commit `fix(app): plan chart axis by quantity, off-scale targets, counts key`.

### Task 5: Colour tokens

Follow-up: "`app.css` hard-codes `#eda100`, `#1baf7a` and the Counts key colours `#2a78d6` /
`#eb6834` … instead of `:root` tokens; the mapped amber is close to `--flag`".

**Files:**
- Modify: `src/velometer/app/static/app.css`, `src/velometer/app/static/js/data.js` (`PALETTE`) if
  needed, chart JS that reads colours
- Test: `tests/test_app_m8.py` (or a CSS test file in the same style)

- [ ] **Step 1:** Failing test: no hex colour literal in `app.css` outside `:root` and its
  dark-mode blocks (rule over the whole file); every token defined in `:root` light has a dark
  value; the mapped colour differs from `--flag` by at least a stated hue distance (ΔE or hue
  degrees — state the threshold and why).
- [ ] **Step 2:** Run, confirm red.
- [ ] **Step 3:** Add tokens (`--mapped`, `--completed`, counter key tokens tied to `PALETTE`),
  pick a mapped colour clearly apart from `--flag`, update rules to `var(...)`.
- [ ] **Step 4:** Render `/plans/berlin` light and dark (prefers-color-scheme) at 1280; screenshots
  in the report. Gate. Commit `style(app): colour tokens for mapped, completed and counter keys`.

### Task 6: DB, adapter and fetch hygiene

Follow-ups: Task 1 DB helpers ("`replace_plan_overlay` with empty rows leaves stale rows";
"`replace_*` do not check `city_id`"; "the migration row-count test populates only `runs`";
"`_optional_rows` detects a missing table by matching the error message"); M8 code structure
("`load_city` writes `counter_daily` itself while `db.upsert_counter_daily` is used only by
tests"); counters ("Oslo data directory derived as `Path(out_dir).parents[1]`"; "`user_agent()`
duplicated"; "`content --check --online` fetches with the httpx User-Agent, which Open Data BCN
answers with 502"); Berlin WFS ("duplicate ids within one page are not refused"; "a missing
`sort_by` property gives a misleading 'repeated' error").

**Files:**
- Modify: `src/velometer/db.py` (~1058-1140, `_optional_rows`), `src/velometer/counters/__init__.py`,
  `src/velometer/counters/adapters/__init__.py:38`, `src/velometer/sources/download.py:16`,
  `src/velometer/counters/adapters/oslo.py`, the content online-check fetch, `src/velometer/plans/berlin.py`
- Test: `tests/test_db_m8.py`, `tests/test_counters.py`, `tests/test_counters_more.py`,
  `tests/test_overlay.py`, `tests/test_content_m8.py`

- [ ] **Step 1:** Failing tests: `replace_plan_overlay(conn, city, [])` for a given version clears
  that city's rows for that version (state the replace scope used by the overlay CLI and keep it);
  `replace_*` raise on a row whose `city_id` differs from the argument; the migration test
  populates every pre-v9 table it claims to preserve; `_optional_rows` checks `sqlite_master`;
  `load_city` goes through `db.upsert_counter_daily` (assert via behaviour: one code path, test the
  replace semantics the loader needs); one `user_agent()` used by downloads, counter adapters and
  the online check (assert the online check's request carries it); Oslo takes its data dir as a
  parameter; WFS refuses duplicate ids within a page, and a missing sort property gives an error
  naming the property.
- [ ] **Step 2:** Run, confirm red.
- [ ] **Step 3:** Implement. Do not touch `velometer.sqlite`; tests use temp DBs.
- [ ] **Step 4:** Focused tests, `counters --check`, gate. Commit `fix(db,counters,plans): replace scope, city checks, one user agent, WFS errors`.

### Task 7: Content check and test hygiene

Follow-ups: Task 2 ("`_plan` reloads the plans files per fact"; "`_external_url` says 'source url'
for organisation urls"; "`_check_explainer` duplicates `_read_dimensions`"; "a CLI test's exit-code
assertion does not discriminate"; "`_figure_pairs` does not catch UnicodeDecodeError"); M8 code
structure ("`_COUNTER_WORDS` matches the verb 'count'"); Content ("German document title …
reads ambiguously"; "the quote-break test's `next(...)` raises StopIteration";
"`content/plans/berlin.yaml` has lines over 100 characters"); Task 11 ("`test_app_m8_counts.py`
repeats function-local imports").

**Files:**
- Modify: `src/velometer/content/facts.py` (`_plan` ~386), `src/velometer/content/check.py` (~48,
  ~213-260, ~454), `content/organisations/abgeordnetenhaus.yaml`, `content/plans/berlin.yaml`,
  `tests/test_app_m8_counts.py`, the quote-break test, the CLI exit-code test
- Test: `tests/test_content_m8.py`, `tests/test_content_facts.py`

- [ ] **Step 1:** Failing tests: plans files are loaded once per evaluate call (count loader
  calls); organisation url problems say "organisation url"; `_figure_pairs` turns undecodable
  input into a problem, not a crash; the causal check fires on "due to" near a counter noun and
  not on the verb "count" alone (a sentence like "we count the km, due to …" without a counter
  noun passes); the quote-break test fails with a clear assertion message instead of
  StopIteration; the CLI test asserts the specific exit code of the failure it provokes.
- [ ] **Step 2:** Run, confirm red.
- [ ] **Step 3:** Implement; `_check_explainer` reuses `_read_dimensions`; the German title gets
  italics (markdown `*…*`, as the page renders markdown — check) with the translation in
  parentheses; wrap `berlin.yaml` to ≤ 100 characters without changing text; hoist the repeated
  imports.
- [ ] **Step 4:** `content --check`, gate. Commit `fix(content): check messages, causal rule, loader reuse, test hygiene`.

### Task 8: Docs

**Files:**
- Modify: `docs/review/m8-overlay.md`, `docs/superpowers/rulings-m8.md`, `HANDOVER.md`, `CLAUDE.md`

- [ ] **Step 1:** `m8-overlay.md`: the "1,082 km on the two networks" figure is printed by
  `scripts/overlay_false_positives.py` (add the print) or the sentence is removed; the "~10 %
  stop threshold" says it was set by the controller.
- [ ] **Step 2:** `rulings-m8.md` Follow-ups: mark each item closed by this plan with its commit;
  what stays open (index v2, overlay v5, Paris in-service granularity, Starlette warning, the
  unexplained `test_overlay_facts` failure, M7 Figures-table scroll, process notes) stays listed.
  Add the rulings made while executing this plan.
- [ ] **Step 3:** HANDOVER §9: one line under M8 for the follow-up pass; CLAUDE.md latest line
  mentions it. All six checks exit 0; gate. Commit `docs(m8): follow-up pass closed`.
