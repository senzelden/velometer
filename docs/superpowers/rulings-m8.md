# M8 rulings

## Task 8: user review stop (2026-10-07)

The user reviewed `docs/review/m8-content-review.md` (commit 1e96c54) and the overlay_v3 sanity map,
and gave one verdict per item class:

- Profiles (9 organisations): approved, with one fix: the Abgeordnetenhaus profile gives the German
  title "Acht Jahre Mobilitätsgesetz – …" instead of a translated title in quotation marks.
- Plans (21 plans, 118 Berlin rows, the Berlin plan page): approved, with fixes:
  - the Berlin plan page's quotes are placed after the paragraph they belong to (the `after`
    indices were counted with the intro);
  - Copenhagen 37 and Strasbourg 52 are marked suspect, because their sources count funded or
    under-construction work, or a forecast, as implemented; the page flags them;
  - the unstored Radverkehrsnetz + Hauptverkehrsstraßen rows (1733 C 22.7 / 69.9, 1733 E 20.1 /
    156.9) are listed in the research log's "Not stored" list;
  - each downloaded plan document records "licence: not stated" instead of the general § 5 UrhG
    sentence;
  - Drs 19/27049 Ergänzungsnetz 2023 55.1 stays suspect; the five expired plans without a
    successor show "no successor found" (Task 9).
- Overlay: overlay_v3 ships as the latest method (superseded on 2026-10-08, below), with the caveat that the series measures what is
  mapped, depends on how OSM draws ways, and moves when ways are redrawn. Before shipping, the
  v3-only pieces are checked on a zoomed map for crossing-street false positives.
- Counters: the index rule of spec §2.13 stays as recorded. Helsinki 2025 stays 84.2; the Counts
  tab notes the two sites whose counts step down during works (Kaivokatu from April 2024,
  Pitkäsilta west from May 2025) and the index without them (99.9) (Task 10). The other counter
  rulings are approved: Oslo completeness from byHour, a zero-total day is an outage, the Paris
  in-service rule, and Madrid without an index line.

The other judgement calls listed in the review document stand as written there.

The SDD ledger's controller rulings of Tasks 1–7 are also listed in the review document's
"Judgement calls" section (19 items); they stand as approved above and are repeated by task below.

## User decision on resume (2026-10-08)

- The Task 8 fix round found 6.5 km (11.0 %) of the v3-only overlay pieces lying past a network
  line's end, over the controller-set 10 % stop line. User decision: build `overlay_v4` = v3 plus
  "drop pieces lying past a network line's end" as a new version (spec §2.11); the page shows v4.
  v1-v3 rows stay in `plan_overlay`.

## Pre-flight and process

- T3 writes registry sources to `content/sources/orgs.yaml`, T4 to `content/sources/plans.yaml`
  (new files), so parallel research never edits the same file. Cost: nothing.
- T3 and T4 ran in parallel as research only (no commits, disjoint files; the controller committed
  each), as M7 Task 5. Cost: a re-run had they collided.
- The T1 v8 fixture DB is `create_schema` on a fresh DB with the five new tables dropped and
  `user_version` 8; no stored v8 artefact. Cost: nothing.
- No worktree: branch `m8` in the main checkout, because tasks need the git-ignored `data/`
  snapshots and `velometer.sqlite`. Cost: isolation only.
- Overlapping starts, each on disjoint files with explicit-path staging: T3/T4 research during the
  T2 review (cost: a content touch-up had a model field changed); T5 code during T3/T4 research,
  its berlin.yaml step deferred to a follow-up (cost: one extra dispatch); T6 during the T5
  re-review (cost: a hand merge in `cli.py`); the T6 follow-up beside T5s6 (cost: a re-commit had
  a gate seen the other's half-edit); T9 during the overlay_v4 review (cost: nothing unless v4 had
  been rejected wholesale).
- T3 and T4 files were committed together once T3 landed, so the committed tree passes
  `content --check` (Berlin publishers need the T3 profiles). Cost: nothing.
- A fresh agent finished T3 from the files of the agent lost in the crash instead of redoing the
  research; the audit and the online check cover what the lost agent left unverified. Cost: a
  missed gap if the audit was shallow.
- The T3 online check was accepted: the new sources pass; the failures were the checker's PDF
  blindness and outages on sources outside T3, and every PDF excerpt was re-checked with pdftotext.
  Cost: a follow-up if the PDF gap hides a wrong excerpt.
- T2b finding 2 (old `reports.csv` header at the committed head) closed with the T3+T4 data commit,
  without a code change: the test asserts the rule, the data were pending. Cost: one red
  intermediate commit. T2b finding 8 (suspect rows shown as flagged revisions) went to Task 9.
- The interrupted Task 11 render fixes (c2c1b64) were kept, not redone: they target the logged
  render findings and the Task 11 review covers them. Cost: a revert had they been wrong.

## Task 2

- Profiles carry no `sources:` field (spec §3.3 example); `config/organisations.yaml` is the single
  source-to-organisation mapping. Why: two places would drift. Cost: a reverse lookup in the app.
- Accepted the implementer's rulings: the causal check runs on all prose; overlay facts use the
  latest `overlay_version` and the OSM timestamp's date; plan rules are not gated. Why: consistent
  with spec §2.12 and §4.5. Cost: a check tweak if a narrative trips it.
- The causal counter regex matches "counters" (plural) too; the plan's regex missed it and spec
  §5.5 means any counter mention. Cost: nothing.
- Fix round 1 also took three minors: overlay facts restricted to LAU runs; an ambiguous doc suffix
  or duplicate doc rows refused; malformed figures or reconcile input reported as a problem, not a
  KeyError. Why: cheap, and the content tasks would exercise them. Cost: one short round.

## Task 2b and Task 4 (plan data model)

- Tests asserting that shipped `config/plans` files are empty were wrong (they pinned today's
  value); they now assert "loads; header equals the model fields". Cost: nothing.
- `ReportRow.suspect`: a suspect row is never current while a non-suspect row exists. Drs 19/27049
  Ergänzungsnetz 2023 55.1 is suspect, kept and shown as a flagged revision. Why: spec §2.8 makes
  the latest current, but an evident typo as the headline misleads; the user confirmed it at the
  review stop. Cost: a one-flag change if the user prefers the printed value as current.
- `ReportRow.cumulative_from`: required for `implemented_cumulative`; the Summe column of Drs
  19/27049 (from 2022) is stored. Why: documents count cumulative km from different start years
  (2017, 2022). Cost: one column.
- On equal `doc_date`, current prefers `drucksache`/`rote_nummer` over report over web; a web
  edition is dated by the date it states, else by its parliamentary edition's date. Why: a PDF
  creation date is not a publication date. Cost: a tie-break rule.
- `current_and_revisions` groups by (plan, item, year, quantity, cumulative_from), and a `plan.*`
  fact on such a key without a doc suffix is ambiguous (FactError) unless there is one base. Why:
  cumulative figures from different start years measure different periods. Cost: one key field.
- The 5 network-total rows without a start year were dropped (logged in `docs/review/m8-plans.md`).
  Why: inventing a base year is worse than omitting. Cost: those 5 figures.

## Task 5 (overlay)

- `overlay_v2`: buffer by geometry kind, 12 m for way-sides tagged on the road centreline and 25 m
  for separately mapped ways; v1 rows stay, the app and facts use the latest version. Why: v1's
  falling series (473 -> 315 km on the Vorrangnetz) measured Berlin's move from centreline tags to
  separate ways, not the network; spec §2.11 makes a parameter change a new version. Cost: a rerun
  and a false-positive risk on parallel side streets, shown on the sanity map.
- Page wording says the on-network series is sensitive to how OSM draws cycleways and that
  redrawing moves it; the v2 -> v3 jump in the change (17-22 km, Ergänzungsnetz changing sign) is
  carried into that wording with the version named. Cost: nothing.
- `overlay_v3`: `min_part_m` tested on kept pieces merged across touching way-sides of one tier,
  not per way-side. Why: the per-side rule made the result depend on how finely OSM splits ways,
  which grows over time (Vorrangnetz short-way km 4.0 -> 24.3). Cost: a rerun.
- Fix round 1 also took WFS paging guards (sortBy, numberMatched, duplicate ids, page cap),
  `--version` defaulting to the latest config, and a meaningful side-key test. Why: the paging
  guards stop silent truncation. Cost: one round.
- T5s6 fix round also took the rounding-note and "mapped km" label minors (ADR 0006 wording).
  Cost: nothing.

## Task 6 and Task 7 (counters)

- Accepted the T6 implementer's rulings: Berlin orange-fill cells are missing hours; `site_aliases`
  for 6 renumbered Berlin ids; Paris sums renumbered counters per site and skips the unlabelled
  total row; a zero-total day is an outage in every city; Vienna's Opernring sum column is
  excluded; a load replaces a city's daily rows. Cost: an index shift if a real 0 day exists.
- All six T6 minors went to a follow-up before Task 7, because two change index inputs (a site-hour
  needs every counter of the site that reported that year). Result: Berlin unchanged, Paris
  2023-2025 moved by the in-service rule. Cost: one short round.
- Oslo completeness follows the spec ("all local hours present"), taken from `byHour`, not from
  coverage = 100. Why: the spec rule; a byHour spot check found no coverage threshold exact. Cost:
  an API pass (base sites 8 -> 11, 2025 133.6 -> 140.6).
- Helsinki's step-down sites (Kaivokatu 2024, Pitkäsilta west 2025) are not excluded from the
  index; both values went to the user, who kept the §2.13 rule with a page note. Why: a generic
  step-change rule alters the recorded index decision. Cost: a reload if the rule is wanted later.
- T7 fix round 1 also took a latent None in the Madrid adapter, the Madrid gap wording, a
  near-zero sentence in the log, and an uncited Barcelona claim in `content/counters.yaml` (a §2.6
  breach). Cost: nothing.

## Task 8 and Task 8b (review fixes, overlay_v4)

- The Abgeordnetenhaus quote stayed at `after: 3` unless the review flagged it; the review did, and
  fix round 2 moved it to the paragraph it supports. Cost: a one-line move.
- The Task 8 Important (false-positive classifier not reproducible) was fixed inside the v4 task:
  `scripts/overlay_false_positives.py` is committed with stated parameters and reruns v3 and v4.
  Why: one owner avoids a race on `m8-overlay.md`. Cost: a combined re-review.
- Fix round 2 took three minors: the quote-placement test pinned today's placement (the user's
  "tests assert the rule" rule), a break case tied to one index, and the quote placement. Cost: one
  round.
- v4's directional free-end rule (a network turn over 30° at a junction is a free end) was
  accepted: it reuses `max_angle_deg`, and a point-only rule left most false positives. Cost: a v5
  if real turns are shown to be clipped materially (the log puts real along-network km lost at
  about 0.5 to 3 km on 2026-01-01).
- T8b fix round 1 took the class-boundary figure made reproducible from the committed script and a
  docstring. Cost: nothing.

## Task 9 (organisations and plans pages)

- Accepted T9's edit of the approved `copenhagen_kommune.yaml` (quote `after: 3` -> 2, the
  paragraph citing its source): the extended placement rule found a real misplacement; reported to
  the user. Cost: nothing.
- The completed-projects series sums `streckenlaengeN` by `netz_artN`; the feature total is 0 on
  312 of 332 features and has no class. Cost: a re-sum if infraVelo fills the total later.
- The mapped series is drawn as the cumulative change since 2022-01-01 (spec §4.4, binding), not as
  per-year bars. Cost: a small chart change.
- Fix round 1 took the "mapped km" labels (ADR 0006), a y-axis bug at -100 and a profile
  paragraph matched inside its own section. Cost: one short round.

## Task 10 (counts tab, compare, no-data note)

- Accepted T10's rulings: Madrid in Compare reads "no counter index line (one index year only; see
  its Counts tab)", not the brief's "no open counter data" (Madrid's data are open, so that wording
  would be false); an index line needs at least 2 years with a value (a data rule, not a Madrid
  case); the Helsinki alternative is computed from config `step_downs` and worded as our reading.
  Cost: a wording change.
- The spec §5.1 "no open counter data found" note with the portals checked had no task; it went
  into T10 fix round 1 with three minors ("a few sites" wording, a compare summary contradiction, a
  missing `step_downs` site as a check problem). Cost: one round.

## Task 11 (render check, docs)

- Overlay table column: "Difference from 1 Jan 2022" for every snapshot, not blank cells before
  2022 (controller finding b). Why: the value is meaningful on both sides of the baseline and the
  label reads right for both. Cost: a header change if blank cells are preferred.
- Counts chart end labels use short names ("Counts", "Intensity", "Mapped km") whenever the full
  name would be cut, and a key under the chart gives the full names in the line colours. Cost:
  nothing.
- Phone-width exceptions to the M7 rule "tables overflow into their scroll box": below 600 px the
  plan tables, the counts table and the counter-sites table wrap headers and break long cell text,
  and the plan documents table stacks with labels. Why: the controller logged the cut-off plan
  table as a defect; the exceptions are scoped to those tables, so the M7 rule still holds
  elsewhere. Cost: wrapped headers on phones.
- The plan chart's snapshot date label moves (above-right, below-left, below-right) when its
  default place crosses a target step or leaves the plot. Why: at 390 px it ran across the
  Ergänzungsnetz 2025 step. Cost: nothing.
- The methodology gets two sections (overlay, counter index) whose overlay parameters and counter
  cities are generated from config, so `report methodology --check` fails when a new overlay
  version or counter city lands without a regeneration. Cost: two generated blocks.

## Follow-ups

- Overlay method: v3 contact is tested on simplified chords and may miss runs meeting at a bend
  (bounded by the residual drop); v4 drops some km along a turning network (about 0.5 to 3 km on
  2026-01-01, not a strict bound), a v5 question; the log's "1,082 km on the two networks" is not
  printed by the script; the "~10 % stop threshold" in `m8-overlay.md` should say it was set by the
  controller.
- Plan chart: the axis label always says "per year", so `km_cumulative`/`km_total` targets would
  draw wrongly (Berlin only today); the cumulative mapped line shares the "km per year" axis with
  per-year targets (disclosed in the y label); `plans_berlin.html` key links depend on berlin.yaml
  dimension values, untested.
- Colours: `app.css` hard-codes `#eda100`, `#1baf7a` and now the Counts key colours `#2a78d6` /
  `#eb6834` (a test ties the latter to `PALETTE` in `js/data.js`) instead of `:root` tokens; the
  mapped amber is close to `--flag`.
- Compare: the footnote under the chart ("flagged year", "Headline: ...") is shown for the counter
  index metric too, where neither applies.
- Counters: Paris in-service is day-granular (a counter's first and last day in a file count as
  incomplete) and the rolling UTC export is not scanned for in-service by local day; the Oslo data
  directory is derived as `Path(out_dir).parents[1]`; `user_agent()` is duplicated in
  `counters/adapters/__init__.py` and `sources/download.py`; `content --check --online` fetches with
  the httpx User-Agent, which Open Data BCN answers with 502; a `counters.yaml` ConfigError makes
  the no-data note vanish silently; py/js counter computations are hand-mirrored without shared
  cases (they agree today); the km-only Counts chart branch is unreachable from the tab; the compare
  counter title and footnote are duplicated outside the parity test.
- DB helpers (Task 1): `replace_plan_overlay` with empty rows leaves stale rows; `replace_*` do not
  check `city_id` against the rows' `city_id`; the migration row-count test populates only `runs`;
  `_optional_rows` detects a missing table by matching the error message.
- Content checks (Task 2): `_plan` reloads the plans files per fact; `_external_url` says "source
  url" for organisation urls; `_check_explainer` duplicates `_read_dimensions`; a CLI test's
  exit-code assertion does not discriminate; `_figure_pairs` does not catch UnicodeDecodeError;
  one unexplained `test_overlay_facts` failure (no order or timing dependence found).
- Berlin WFS fetch: duplicate ids within one page are not refused, and a missing `sort_by` property
  gives a misleading "repeated" error.
- Content: the Abgeordnetenhaus profile's German document title, without quotation marks or
  italics, reads ambiguously; no test asserts that Copenhagen 37 and Strasbourg 52 are suspect; the
  quote-break test's `next(...)` raises StopIteration if a page cites the source in every
  paragraph; `content/plans/berlin.yaml` has lines over 100 characters (cosmetic).
- Gate: the Starlette `httpx` deprecation warning (pre-existing) stays in the pytest output.
- Left as M7 behaviour: the Figures-tab tables scroll horizontally inside their box at 390 px.
