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
- Counter facts in the methodology (`report/methodology.py` `_counter_facts`) list only the cities
  the country trust gate reports, and "the other N cities" counts the same way. Why: the existing
  rule `test_untrusted_country_is_absent_from_every_report_surface`; the spec does not require
  listing held-back cities, and today all seven counter cities are reported. Cost: a counter city
  drops out of the methodology if its country loses trust.

## Final review and fix wave (2026-10-08)

- The final fix wave takes I1 (counter attribution on Compare, code and parity test) and the
  doc-only items (M11: these rulings and follow-ups made complete; the §5.3 link-ratio coverage
  bias recorded as a known property); the other final-review Minors become follow-ups below, not
  code changes. Why: none is a correctness defect per the reviewer, and one fix wave is the cap.
  Cost: those Minors stay open after the merge.
- HANDOVER's "delivered 2026-10-08" stands. Why: the merge, if approved, lands today. Cost: a date
  edit if the merge slips.
- I1: `/data/series.json` `counters.cities.<id>` carries `source` and `licence` (the
  `config/counters.yaml` entry, else the stored sites', as the Counts tab), and Compare's counter
  index adds one note per drawn city, "Counter data, <city>: <publisher>, licence <licence>",
  after the other notes, in the no-JS table and compare.js alike. A city whose index is not drawn
  (Madrid) shows no values and gets no attribution note. Why: ADR 0008's M8 note, attribution is a
  licence condition for CC BY 4.0, NLOD and ODbL. Cost: six more note lines on a full selection,
  which push the chart down at phone width.
- The coverage bias is measured against a mean per complete day pooled over the link's sites (the
  reviewer's estimator, reproduced exactly). Cost: a per-site mean gives other per-link values
  (Helsinki 2022→2023 −2.2 % instead of −1.8 %), the same order of magnitude.

## Follow-up pass (2026-10-08/09)

Plan `docs/superpowers/plans/2026-10-08-velometer-m8-followups.md`, branch `m8-followups`, commits
`4b30984..` (Tasks 1–8). It closes the Follow-ups below that are defects or drift risks without a
method change; each closed item is marked with its commit. No new OSM runs, overlay rows stay
overlay_v4, the counter index rule stays spec §2.13, and every stored number is unchanged: all six
checks (`counters`, `content`, `report methodology`, `timeseries`, `reconcile`, `trust`) exit 0
with the same values.

**DB hygiene discovery.** Before this pass, `reconcile` and `timeseries` (also without `--write`)
opened `velometer.sqlite` read-write through `create_schema`, which always began a transaction,
re-ran `CREATE ... IF NOT EXISTS`, repaired the done-key index and set `user_version`, then
committed: every check run changed the file's bytes (header change counter), though no stored
value. Found when the controller's own check run moved the md5 from `6008c28d` to `a5222dc4`;
pre-existing since M1. Since `e8b36d2` (Task 6), `results`, `reconcile`, `timeseries` and
`counters --check` open the DB read-only (`--write` rewrites only the markdown report), and a
test asserts identical DB bytes after each. The md5 has stayed `a5222dc4` since.

**Visible changes.**

- Counts tab and `content/counters.yaml`: the index rule reads "3 sites complete on at least 90%
  of days" (was "three sites complete on nine days in ten"); the numbers now come from
  `MIN_SITES`/`MIN_VALID` (`f5108be`). The meaning is identical, but the counters prose was
  user-approved content (Task 8 review). Cost: a wording revert if the user prefers the old
  phrasing.
- The methodology names the Helsinki step-down site by its config id "Pitkäsilta länsipuoli", as
  the Counts tab does, instead of a hand translation (`f5108be`). Why: a name map is the drift the
  task removes. Cost: a less readable name in the en/de methodology.
- The mapped colour on the plan chart (and its key) changed from amber to magenta (`#c2378f`,
  token `--mapped`; `08cd96a`). Why: amber was 28° of CIELAB hue from `--flag`; magenta is at
  least 60° from `--flag`, `--accent` and `--completed`. Cost: a colour change on two pages if the
  user prefers another hue.
- `/plans/berlin` names the planned-network layer's licence (dl-de-zero-2.0, from
  `retrieved.json`); Compare's counter-index footnote and unit text are metric-aware and name
  off-majority base years; notes replace silently missing parts on unreadable inputs (`f0684ed`,
  `3657d97`).

**Rulings.**

- Scope: the plan takes the follow-ups that are defects or drift risks without a method change.
  Left open for the user: counter index v2 (mean per day), overlay v5, Paris in-service
  granularity (all three move stored numbers), the M7 Figures-table scroll (recorded M7
  behaviour), the Starlette warning (a dependency change), the unexplained `test_overlay_facts`
  failure (no repro), and a test that Copenhagen 37 / Strasbourg 52 are suspect (a value pin adds
  little). Cost: those items stay open.
- Execution by subagent-driven development without asking (the user's standing instruction,
  "continue on your own"). Cost: nothing.
- Task 1 owns the base-year wording in Compare's unit text; Task 3 would only swap threshold
  numbers there (it found none). Cost: nothing in the end.
- Ergänzungsnetz chart: a data-led y-domain, with targets above `OFFSCALE_FACTOR` (3) × the
  largest figure capped at the top edge with their value labelled, and every value in the table
  (`6b4adec`). Factor 3 is kept although the Radverkehrsnetz chart caps 7 of 9 years: its targets
  (100–450 km) are 5–20× its largest figure (~22 km), so capping is the honest picture. Cost: a
  redesign if the user prefers a broken axis or log scale, or a factor tweak if it looks busy.
- Mixed per-year and cumulative/total targets in one chart are refused with a table note, not
  drawn on panels (no city has them today); the plan key became a list like the counts key.
  Cost: nothing.
- Task 4's two reader-visible Minors (a key entry for the capped marker; headroom so an on-scale
  target at the axis top does not share the caps' line) went into Task 5 (`08cd96a`, `ca40fb2`,
  with the follow-up fix `275702a`: caps only above the final axis top). Cost: a larger Task 5.
- Task 2: a "counter configuration unreadable" note also on the Counts tab (beyond the brief,
  same silent-vanish defect). A `retrieved.json` without a licence counts as unreadable; the
  planned-network licence is shown only when the record lists that layer, else "licence not
  recorded"; a licence is never inferred. Two blank screenshots of broken-input pages were
  accepted because HTML tests assert each note renders with the existing note style. Cost: one
  note string; a "not recorded" line if the record format changes; a missed layout defect on two
  broken-input pages.
- Task 3 placement: `MAPPED_BASELINE` (2022-01-01) in `plans/models.py`; counter constants and
  `data_gaps` in `counters/model.py`, re-exported from `app/counts.py`; the Madrid detector clause
  and the link-ratio figures stay hand-written text; the methodology says "no stored overlay" on
  an empty DB; two Madrid tests follow spec §2.13 (a base year with fewer than 3 sites has no
  value). Cost: nothing.
- Dark mode removed: Task 5 added a site-wide `prefers-color-scheme: dark` palette because the
  plan said every token needs a dark value, but the app had no dark mode, and the palette was
  rendered only on two pages (maps, compare, stories and JS-set colours untested). The block and
  its tests were dropped (`35f0876`); the tokens stay. Cost: no dark mode until it is its own task
  with a render pass of every page.
- The read-only-open discovery went into Task 6 (same DB-hygiene area; it broke the "no writes"
  constraint on every check run). Task 6's own rulings: `--write` also opens read-only;
  `replace_counter_daily(conn, city, rows)` replaces `upsert_counter_daily` and is what
  `load_city` uses; `replace_plan_overlay` takes the overlay version, and empty rows clear that
  version; a v5 DB with activity rows makes read-only commands say "run `velometer migrate`";
  adapters' `fetch` takes `data_dir`; the Berlin WFS sends the shared `user_agent()`;
  `VELOMETER_CONTACT`, when the user sets it, is appended to the counter fetch User-Agent as
  downloads already did. Cost: a User-Agent difference toward Open Data BCN if the contact suffix
  trips it (untested).
- Task 7 also took three test/check hygiene Minors (read-only CLI cases accepting any exit, the
  vacuous Madrid base-year test, literal-threshold false positives). `counters --check` is
  asserted as exit 1 ("no counter sites") in the read-only CLI test, since its rule is identical
  DB bytes. Cost: a larger Task 7; nothing.
- Prose renders `*title*` as italics (`narrative.py`), outside code spans only (`bf44c3d`), for
  the Abgeordnetenhaus profile's German title; a lone `*` stays text. Cost: a renderer quirk if
  prose later uses `*` otherwise.
- The literal-threshold content check matches English threshold phrases (before "sites", a
  percentage of days, "= 100", "base year", "chained from"); facts stay the primary guard. Cost: a
  paraphrase ("a trio of sites") slips through.
- "Counted" is a counter word again in the causal guard ("Counted trips drove demand" fails);
  the verb "count" alone passes (`bf44c3d`). Cost: one line.

## Follow-ups

Marks: "closed `sha`" by the follow-up pass (2026-10-08/09); unmarked parts stay open.

- Overlay method: v3 contact is tested on simplified chords and may miss runs meeting at a bend
  (bounded by the residual drop); v4 drops some km along a turning network (about 0.5 to 3 km on
  2026-01-01, not a strict bound), a v5 question (open). The log's "1,082 km on the two networks"
  is not printed by the script (closed by the pass's docs commit: `--checks` prints it); the "~10 %
  stop threshold" in `m8-overlay.md` should say it was set by the controller (closed, same
  commit).
- Plan chart: the axis label always says "per year", so `km_cumulative`/`km_total` targets would
  draw wrongly (closed `6b4adec`); the cumulative mapped line shares the "km per year" axis with
  per-year targets (disclosed in the y label; open); `plans_berlin.html` key links depend on
  berlin.yaml dimension values, untested (closed `6b4adec`).
- Colours: `app.css` hard-codes `#eda100`, `#1baf7a` and the Counts key colours `#2a78d6` /
  `#eb6834` instead of `:root` tokens; the mapped amber is close to `--flag` (closed `08cd96a`).
- Compare: the footnote under the chart ("flagged year", "Headline: ...") is shown for the counter
  index metric too, where neither applies (closed `f0684ed`).
- Counters: Paris in-service is day-granular (a counter's first and last day in a file count as
  incomplete) and the rolling UTC export is not scanned for in-service by local day (open); the
  Oslo data directory is derived as `Path(out_dir).parents[1]` (closed `e8b36d2`); `user_agent()`
  is duplicated in `counters/adapters/__init__.py` and `sources/download.py` (closed `e8b36d2`);
  `content --check --online` fetches with the httpx User-Agent, which Open Data BCN answers with
  502 (closed `e8b36d2`); a `counters.yaml` ConfigError makes the no-data note vanish silently
  (closed `3657d97`); py/js counter computations are hand-mirrored without shared cases (closed
  `f0684ed`, `tests/counter_cases.json`); the km-only Counts chart branch is unreachable from the
  tab (open); the compare counter title and footnote are duplicated outside the parity test
  (closed `f0684ed`).
- DB helpers (Task 1): `replace_plan_overlay` with empty rows leaves stale rows; `replace_*` do not
  check `city_id` against the rows' `city_id`; the migration row-count test populates only `runs`;
  `_optional_rows` detects a missing table by matching the error message (all closed `e8b36d2`).
- Content checks (Task 2): `_plan` reloads the plans files per fact; `_external_url` says "source
  url" for organisation urls; `_check_explainer` duplicates `_read_dimensions`; a CLI test's
  exit-code assertion does not discriminate; `_figure_pairs` does not catch UnicodeDecodeError
  (all closed `ec401ac`); one unexplained `test_overlay_facts` failure (no order or timing
  dependence found; open).
- Berlin WFS fetch: duplicate ids within one page are not refused, and a missing `sort_by` property
  gives a misleading "repeated" error (closed `e8b36d2`).
- Content: the Abgeordnetenhaus profile's German document title, without quotation marks or
  italics, reads ambiguously (closed `ec401ac`, `bf44c3d`); no test asserts that Copenhagen 37 and
  Strasbourg 52 are suspect (open, by scope ruling); the quote-break test's `next(...)` raises
  StopIteration if a page cites the source in every paragraph (closed `ec401ac`);
  `content/plans/berlin.yaml` has lines over 100 characters (closed `ec401ac`).
- Counter index (final review M1, M2): a link sums each qualifying site's counts over its complete
  days only, so a coverage difference between the two years moves the ratio (spec §2.13/§5.3 as
  recorded, kept by the user; now in the methodology as a known property). Against a pooled mean
  per complete day, 37 of the 49 daily-count links move by less than 0.5 %; the largest are
  +2.1 % (Paris 2019→2020), −2.0 % (Helsinki 2024→2025), −1.8 % (Helsinki 2022→2023), +1.6 %
  (Paris 2023→2024) and −1.3 % (Oslo 2018→2019); Berlin and Vienna stay within 0.7 %. A mean per
  day link is the natural index v2 question (open). The base year prints 100 whatever its number
  of qualifying sites (`counters/index.py:122`), although spec §2.13 gives a year with fewer than
  3 sites no value (closed `f5108be`, test made non-vacuous in `ebab4e7`; every stored base year
  has 11 or more sites, the index is unchanged).
- Attribution and error notes (final review M3, M4): the Berlin plan page's planned-network line
  names no licence, although `retrieved.json` covers both layers, and a corrupt `retrieved.json`
  silently removes the measures licence too (`plans_pages.measures_retrieved`); a source-registry
  load error removes the plan page's text and quotes without a note (`main.py` `plan_page` passes
  no `content_error`, unlike `/organisations`) (all closed `3657d97`).
- Prose restating config (final review M5, M6, M7; Task 11): `counts.html`, `content/counters.yaml`
  and `compare.py` `COUNTER_UNIT` ("2019 = 100", wrong for a base-2020 city drawn as a line) spell
  out `MIN_VALID`, `MIN_SITES` and the base years by hand (closed `f5108be`; `COUNTER_UNIT`
  closed `f0684ed`); the methodology's Madrid and Helsinki bullets hard-code facts outside the
  generated blocks, so `--check` is blind to their drift; the methodology takes the latest overlay
  version from config, the page and the facts from `plan_overlay`, so a new config file without a
  rerun makes them disagree; `berlin_context` derives the 1 January 2022 baseline from the plan's
  first target year instead of a named constant (all closed `f5108be`).
- Code structure (final review M8, M9): `counters/__init__.py` `load_city` writes `counter_daily`
  itself while `db.upsert_counter_daily` is used only by tests (closed `e8b36d2`);
  `content/check.py` `_COUNTER_WORDS` matches the verb "count", so a "due to" near it would fail
  the causal check for the wrong reason (closed `ec401ac`, `bf44c3d`).
- Task 11 minors: the Counts/Intensity short names are duplicated in `counts.html` and `city.js`
  (closed `6b4adec`); the phone-width CSS tests assert that a rule is present, not the resolved
  cascade (open); `plan-chart.test.mjs` pins the chart margins 44/10 (closed `6b4adec`);
  `test_app_m8_counts.py` repeats function-local imports (closed `ec401ac`); the counts key wraps
  at 390 px with a leading "·" (closed `6b4adec`); HANDOVER's "delivered 2026-10-08" needs a date
  edit if the merge slips (closed: M8 was merged on 2026-10-08).
- Gate: the Starlette `httpx` deprecation warning (pre-existing) stays in the pytest output (open).
- Process: the Task 7 full gate was not rerun after the last `oslo.py` reformat (moot: every gate
  since is green); Task 10's tests were written after the code (red shown against HEAD) (notes,
  open).
- Left as M7 behaviour: the Figures-tab tables scroll horizontally inside their box at 390 px
  (open).
- Dark mode (follow-up pass, Task 5): the app has no dark theme; the pass removed an untested one
  (`35f0876`). A dark theme needs dark values for every token and the JS-set chart and map
  colours, and a render pass of every page (open).

Opened by the follow-up pass (reviewers' deferred Minors, all open):

- Compare and counters (Task 1): the counter tooltip unit reads "each city's base year = 100" and
  lost "2019 = 100; 2020 is the COVID year" (text only); "Counters are context" is stated twice on
  the counter Compare view (subtitle and footnote); a static import mid-file in
  `counter-model.test.mjs` (~454); `test_app_m8_counts.py` (~800) pins today's footnote string;
  `compare.py` (~265) raises on a city without `line` where the JS skips it.
- Notes and licences (Task 2): the unreadable-record note on `/plans/berlin` says the retrieval
  date cannot be shown while the planned-network line still shows its DB date; the measures line
  takes the licence without checking that its layer is listed (the planned-network line does);
  with `retrieved.json` missing (fresh checkout) and the overlay shown, the planned-network line
  names no licence and shows no note; a `counters.yaml` read error is logged per city per cached
  build, not once.
- One source (Task 3): the latest-overlay-version logic and the Berlin city constant are
  duplicated (`methodology.py` ~1073, `plans_pages.py` ~250); the methodology re-implements
  `has_line`/`_days` from `app/counts.py` and computes gaps under a different condition;
  `DEFAULT_BASE_YEAR`/`COVID_YEAR` are imported by name and the test covers the template side
  only; the hand-written "the plan's first target year" still sits beside the generated
  `MAPPED_BASELINE` in the methodology templates.
- Plan chart (Task 4): `counter-model.js` (~124, ~126) keeps literal fallbacks "Counts" / "Mapped
  km" (a second copy of the short names); `labelSpot` ignores cap segments and adjacent cap labels
  are untested for overlap; the date-label test was relaxed from inside-plot to inside-svg; the
  `_key_line_colour` docstring still says `<p class="chart-key">` (now `<ul>`); section roles are
  computed twice in `plans_berlin.html`; the every-target-in-table test is a guard (passes
  without the change).
- Colours (Task 5): the hue-distance test has no chroma floor; `rgb(...)` shadow colours sit
  outside `:root` (the rule covers hex only); the key test's "table" check is loose.
- DB and fetch (Task 6): the counters fetch `ValueError` catch (`cli.py` ~2157) has no CLI test;
  `_print_city_metrics` (`cli.py` ~378) reads through `_open_schema` after a write (harmless); the
  WFS treats a JSON-null id as a missing property (wording only); six adapters take an ignored
  `data_dir` (documented).
- Content checks (Task 7): the plan-file cache in `facts.py` (~474) is unbounded and shares mutable
  lists; `_madrid_year` hardcodes the 2020 clock-change dates; the "Nine of the sites" test case
  uses a number that is not a rule value; threshold phrasings the check misses ("2019 (= 100)",
  "relative to 2019", "90% coverage"); `_seed_report` depends on the fixture flagging at least one
  gap; source and data-ref substitutions still run inside code spans (pre-existing); "counts" as
  a verb still triggers the causal check, and the `archive_url` error still says "source url".
