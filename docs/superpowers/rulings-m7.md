# M7 rulings

## Task 8: user review stop (2026-10-06)

The user reviewed `docs/review/m7-content-review.md` (commit 857c18d) and gave one verdict per item
class:

- Sources (106 sources, 266 excerpts in `content/sources/*.yaml`): approved, including the Berlin
  Vorrangnetz 2025 correction 7.5 -> 9.8 km (commit 67ed739) and the hand-transcribed excerpts of the
  Berlin Fortschrittsbericht 2025.
- Shift findings (`docs/review/shifts.md`): approved.
- Narratives (21 cities and `combined.yaml`): approved; app work (Tasks 9-14) may start.
- Explainer (`content/explainer.yaml`): approved.

The 13 judgement calls listed in the review document stand as written there.

## Pre-flight and process

- No worktree; branch `m7` in the main checkout, because Task 6 needs the git-ignored snapshots and
  `velometer.sqlite` (as M5 R2 / M6). Cost: isolation only.
- P1: the real-repo `content --check` may fail from Task 3 until Task 7 lands the narratives (same
  pattern as M6 P2). Cost: no content gate on the real repo in that window; the pytest gate was
  unaffected.
- P2: Task 10 replaces every Vega embed, including the old city page's, with chart-module mounts
  plus server-rendered tables before deleting the bundles; Task 11 then split the city page into
  tabs. Why: the spec removes Vega and the gate had to stay green after Task 10. Cost: some
  throwaway city-page markup that Task 11 rewrote.
- Task 6 (read-only shift investigation, writes only `docs/review/shifts.md`) ran in parallel with
  Tasks 1-4 and the controller committed its file. Why: independent files, no git races. Cost: a
  re-run if wrong.
- Task 7 city drafters started in parallel with the Task 4 fix (they write only
  `content/narratives/*.yaml`, no commits; dimension ids were stable). Cost: a figures-section
  touch-up if row labels had changed.

## Task 2

- Gap family keys parse the city as head and the field as tail (rsplit); the middle is the gap key
  minus the city prefix and may contain dots. Why: four Berlin gap keys contain dots and every real
  gap must be addressable. Cost: a grammar tweak if authors want other syntax.
- A figure key takes an optional trailing selector, an ISO date or `{value:g}`. Why: Berlin's two
  `whole_network` figures share a reference date. Cost: a syntax change if authors find it
  confusing.

## Task 3

- Fix minors 1-3 now in one small round (headings and titles scanned for numbers, bare-number
  literal whitelist, space-grouped thousands). Why: the numbers rule applies to every rendered
  string and Task 7 narratives would hit "1 000"-style numbers. Cost: one short round.
- Parked: space grouping merges adjacent numbers ("Rank 3 100"), and the literal "5 m" matches the
  tail of "5,5 m". Why: both fail safe (an undeclared number is flagged and the author declares it).
  Cost: an occasional spurious problem.
- `figures.csv` Berlin Vorrangnetz `new_cycle_infra_km` corrected 7.5 -> 9.8 (commit 67ed739). Why:
  7.5 was the Ergänzungsnetz sum row; Vorrangnetz sum rows read 14,3 / 13,6 / 10,9 / 9,8 (Drucksache
  19/25987, p. 10), a transcription error and not a change to the 2026-10-05 load verdict. The DB
  was backed up, curated sources reloaded, `reconcile --write` rewrote one row, `--check` exit 0.
  Cost: a revert if the table is read differently.

## Task 4

- Dedupe keeps the reported row and drops the `ours=None` info gap with the same source, metric,
  value and date. Why: the reported row carries the length basis. Cost: nothing visible.
- Gap length drivers come from registry-backed source bases in `config/differences.yaml`, only when
  our value is not on that basis (spec §5 length dimension). Cost: one more yaml map.

## Task 5

- The Oslo EY evaluation stays `kind=official` (commissioned by the city; the title names the
  consultant). Why: the reader sees the commissioning body. Cost: a relabel to ngo/index if the user
  disagrees.
- Two excerpts rebuilt from reading order (Paris p. 8, Lyon p. 10) are kept. Why: order verified
  with `pdftotext -raw` and the locators disclose it. Cost: dropping two excerpts if only clean
  prose is wanted.

## Task 7

- Headline wording everywhere is "A+B km per 100 km of main roads" (literal "100 km"), not "%" or
  "share of main-road length". Why: it matches the project's headline definition and values above
  100 (Helsinki 264.7) read oddly as a share. Cost: a reword of the six west files.
- Explainer quote `after` counts section paragraphs in order, excluding the intro, as narratives
  do. Cost: Task 11 had to render it that way.
- One content fix round for all Important findings and the minors, except the explainer `after`
  bounds check (code, moved to Task 11). Why: Vienna 384 needs no prose change. Cost: one round.

## Task 9

- The gate's node step uses the glob `node --test "src/velometer/app/static/js/tests/*.test.mjs"`.
  Why: node 24 rejects a directory argument. Cost: none.
- Fix review minors 1-8 now (exact tooltip value, aria names, tiers tooltip position, label bound,
  isolated point, NaN, default metric, DOM test). Why: later tasks build on the module and the spec
  requires exact values on hover. Cost: one short round.
- Parked: NaN in small-multiples domain and tier totals, a redundant ghost check, `placeLabels`
  with bottom above top, no tier tooltip test. Why: data never carries NaN (series come from DB
  floats or null). Cost: nothing visible.

## Task 10

- Handed to a fresh sonnet implementer after three opus API 529 errors; continuity through the
  working tree and the brief. Cost: some re-reading.
- Fix minors 1-8 in one round before Task 11 (a 500 without CSP, the 390 px axis overlap, dead chart
  code, duplication); park 9 (`fmt: skip` lines) and 10 (not applicable). Cost: one round.
- Accepted: the methodology rules table still scrolls horizontally at 1280 px (the Match column is
  wider than the page).

## Task 11

- Data citations render as d1, d2 (markup shape kept) to separate them from source numbers. Why:
  the brief's literal numbering would confuse readers. Cost: a test string change.
- Fix the pull-quote escaping test, the three Berlin official rows, the unknown `length_basis` 500
  risk and minors 1-10 in one round. Cost: one round.

## Task 12

- Compare `c` order equals URL order (JS appends); a no-JS checkbox form may return country order.
  Why: checkbox forms cannot carry order. Cost: recolouring on a no-JS resubmit.
- The city panel is modal (aria-modal, inert, focus trap) only when it covers the viewport (phones);
  the desktop side panel stays non-modal. Why: matches the spec's slide-over. Cost: nothing.
- Fix round 2 waited until Task 13 committed. Why: both touch `main.py` and a working-tree race
  was likely. Cost: a short delay.
- Correction: the Berlin 500 was a real Task 12 bug (`city_panel` mutated the cached context per
  request), fixed inside commit 510abf9 with a test.
- Parked: HTML comments inside fenced code blocks are dropped by the md filter (cosmetic, no doc
  hits it); interactive DOM behaviour was driven by hand, not automated.

## Task 13

- Growth highlights are chosen by data rules so the chart matches the text. Final rule (Task 14):
  the 5 largest km gains, the 4 fastest risers, cities below their first year, capped at 8. Cost:
  one test; a city named in the text can be grey when the cap bites (Wrocław).
- Local city names (Wien, Praha) beside English text, and the reference's progress bar and baseline,
  are out of scope for M7. Why: names come from `config/cities.yaml` used app-wide. Cost: a known
  inconsistency.
- Parked: the jumps step's Explore link opens shared-scale small multiples (disclosed), and the
  observer band edge sits at 30-35 %.

## Final review fixes

- `tests/test_content_real.py` runs every DB-free content check (`check_content_offline`) over the
  real `content/` on each gate; facts are evaluated only by `content --check`, which needs the DB.
  App test fixtures pass `content_dir` explicitly. Why: a fresh checkout has no `velometer.sqlite`,
  so `content --check` alone never guarded the gate.
- Content loads per file: a broken narrative blanks only its own city (or `/stories` for
  `combined`), a broken explainer only `/differences`; a broken source registry still blanks all
  narratives (they cannot cite without it). Load errors are logged; pages show the standard note.
- `content --online` alone implies `--check` (stated in `--help`).
- The per-100k unit names the population years it divides by and that one population is held for
  every year; the Over-time preset table names the run's population year.
- Closed from the parked lists: shared small-multiple y domain and tier totals ignore non-finite
  values; `length_bases` equal to ours gives no driver (tested again); the header reads "LAU, none
  flagged" for a city without flags.

## Follow-ups

- Spelled-out and comparative claims in narratives ("seven city years", "top seven", "lowest of the
  21", "more than twice", "tripled") are not machine-checked; `content --check` covers digits only,
  so these may go stale after a rerun and need a read-through (or a declared rank/count fact kind).
- Denominator-change flag: Warsaw and Helsinki main-road reclassification in OSM changes the
  headline (km per 100 km of main roads) without any change in cycling km. A flag for denominator
  jumps, parallel to the km-jump flag, would let the stories and the Figures tab say so.
- M6 `foot` gap: v4 decides A versus B by whether pedestrians share the surface, but the `foot`
  invariance test covers `foot=permissive` only; other `foot` values (yes, designated, use_sidepath
  on paths) are not pinned by tests.
- Left open (final review): tier colour palette differs between the stacked chart and the tier map;
  `differences.yaml` uses the same label for completed and target metrics; the reconcile and reported
  tables show raw keys and CSV notes; the Bezirke change table shows 3 decimals; flagged-year notes
  are maintainer prose.
- Parked, not fixed: Task 1 minors (`INTERNAL_HOSTS` is a literal set so 127.0.0.2, 0.0.0.0 and
  private ranges pass; mutable lists inside frozen models; duplicate id validators and `Explainer`
  untested; explainer quote `after` not validated against paragraph count).
- Parked, not fixed: Task 3 and Task 9 minors above (adjacent-number merging, "5 m" tail match,
  NaN domains, redundant ghost check, `placeLabels` bound, no tier tooltip test); no CLI test for
  `content --check --online` or a missing DB; Task 3 tests were not red-first.
- Parked, not fixed: Task 4 `length_bases != ours` untested after a test was removed; Vienna's two
  CC rows differ only by a scope driver; "Ours:" prefix in the CC share label; Figures note clause
  shows CSV jargon ("primary"); a misplaced `strip_ours` comment in `main.py`; no hostile-note or
  host escaping test for the Figures tab.
- Parked, not fixed: Task 10 minor 9 (`fmt: skip` lines) and the methodology rules table scroll at
  1280 px.
