# M5 rulings

## History run wall clock (ADR 0005 table)

Run on 2026-10-03 (16:57–19:33 UTC), classifier `v3` (`plain_cycleway_on_oneway: traffic_side`), one machine,
Geofabrik internal-server full-history files (published md5s of 2026-09-25 builds). 378 history runs,
21 cities × 2 boundary kinds × 9 years (2018–2026), runs 314–691, all `done`; none `-dirty`. (Run 313, a Berlin LAU
2018 row orphaned when its launcher was stopped and relaunched detached, is marked `failed`.)
Berlin and Paris LAU ran at commit 9a545a2; every other series at 0b4e0f2, which only changes how a
broken published md5 is handled (below), not what a run measures (`config_sha256` is the same).

- **Invocation wall:** one `velometer run --cities <c> --years 2018-2026 [--boundary fua]` per city and kind, run sequentially; includes the boundary, index, md5 checks and the per-city history extract, but not the downloads (prefetched with `osm fetch-history`), except Vienna FUA, which downloaded `austria` itself (about 4 min of its 594 s).
- **Run walls:** `finished_at − started_at` of the 9 run rows (snapshot, read, classify, persist).
- **Peak:** the largest `runs.peak_rss_kb` of the 9 years.
- LAU runs overlapped the downloads of later cities (network-bound); FUA runs ran alone.

| city | kind | runs | history set | invocation wall (s) | sum of run walls (s) | per year mean (min–max) | max peak RSS (GB) | commit |
|---|---|---|---|---:|---:|---|---:|---|
| berlin | lau | 314–322 (9, done) | `c3335f42` | 290 | 246 | 27 (16–51) | 2.43 | 9a545a2 |
| paris | lau | 323–331 (9, done) | `7db1f306` | 71 | 58 | 6 (4–11) | 0.97 | 9a545a2 |
| vienna | lau | 683–691 (9, done) | `1254c077` | 113 | 94 | 10 (8–13) | 0.98 | 0b4e0f2 |
| copenhagen | lau | 332–340 (9, done) | `be41de5b` | 33 | 27 | 3 (1–4) | 0.41 | 0b4e0f2 |
| wroclaw | lau | 341–349 (9, done) | `fda036ca` | 86 | 71 | 8 (6–10) | 0.75 | 0b4e0f2 |
| amsterdam | lau | 350–358 (9, done) | `2a652dc2` | 114 | 94 | 10 (8–15) | 0.68 | 0b4e0f2 |
| utrecht | lau | 359–367 (9, done) | `b0b39792` | 51 | 39 | 4 (3–5) | 0.45 | 0b4e0f2 |
| madrid | lau | 368–376 (9, done) | `323b467b` | 108 | 94 | 10 (8–14) | 0.92 | 0b4e0f2 |
| barcelona | lau | 377–385 (9, done) | `9a77f00a` | 59 | 46 | 5 (2–8) | 0.64 | 0b4e0f2 |
| stockholm | lau | 386–394 (9, done) | `149b5257` | 62 | 47 | 5 (4–7) | 0.56 | 0b4e0f2 |
| oslo | lau | 395–403 (9, done) | `47a4f74c` | 91 | 79 | 9 (6–12) | 0.74 | 0b4e0f2 |
| helsinki | lau | 404–412 (9, done) | `78321316` | 131 | 108 | 12 (10–14) | 0.97 | 0b4e0f2 |
| lyon | lau | 413–421 (9, done) | `1404a50e` | 39 | 25 | 3 (2–4) | 0.50 | 0b4e0f2 |
| strasbourg | lau | 422–430 (9, done) | `9c8283ec` | 29 | 19 | 2 (1–3) | 0.38 | 0b4e0f2 |
| bordeaux | lau | 431–439 (9, done) | `cb158134` | 24 | 17 | 2 (1–2) | 0.32 | 0b4e0f2 |
| warsaw | lau | 440–448 (9, done) | `e910fce2` | 182 | 150 | 17 (10–25) | 1.45 | 0b4e0f2 |
| krakow | lau | 449–457 (9, done) | `81a148c2` | 95 | 76 | 8 (6–12) | 0.80 | 0b4e0f2 |
| budapest | lau | 458–466 (9, done) | `0a58443e` | 100 | 79 | 9 (6–11) | 0.78 | 0b4e0f2 |
| prague | lau | 467–475 (9, done) | `6d158548` | 141 | 119 | 13 (10–18) | 1.03 | 0b4e0f2 |
| ljubljana | lau | 476–484 (9, done) | `81ef23ad` | 44 | 31 | 3 (2–5) | 0.52 | 0b4e0f2 |
| bratislava | lau | 485–493 (9, done) | `2e7369e0` | 64 | 50 | 6 (4–7) | 0.61 | 0b4e0f2 |
| berlin | fua | 494–502 (9, done) | `1308e2c9` | 535 | 463 | 51 (32–82) | 3.69 | 0b4e0f2 |
| paris | fua | 503–511 (9, done) | `df7be7ff` | 969 | 861 | 96 (67–130) | 4.86 | 0b4e0f2 |
| vienna | fua | 512–520 (9, done) | `1254c077` | 594 | 358 | 40 (30–48) | 2.46 | 0b4e0f2 |
| copenhagen | fua | 521–529 (9, done) | `be41de5b` | 286 | 246 | 27 (16–35) | 1.55 | 0b4e0f2 |
| wroclaw | fua | 530–538 (9, done) | `fda036ca` | 167 | 136 | 15 (12–19) | 1.09 | 0b4e0f2 |
| amsterdam | fua | 539–547 (9, done) | `3ba1483e` | 502 | 411 | 46 (33–59) | 1.99 | 0b4e0f2 |
| utrecht | fua | 548–556 (9, done) | `b37cd68d` | 178 | 135 | 15 (12–19) | 0.91 | 0b4e0f2 |
| madrid | fua | 557–565 (9, done) | `f0e3c8ec` | 362 | 317 | 35 (26–46) | 2.24 | 0b4e0f2 |
| barcelona | fua | 566–574 (9, done) | `9a77f00a` | 313 | 280 | 31 (18–46) | 2.17 | 0b4e0f2 |
| stockholm | fua | 575–583 (9, done) | `149b5257` | 265 | 230 | 26 (18–32) | 1.69 | 0b4e0f2 |
| oslo | fua | 584–592 (9, done) | `47a4f74c` | 339 | 310 | 34 (19–46) | 2.07 | 0b4e0f2 |
| helsinki | fua | 593–601 (9, done) | `78321316` | 365 | 318 | 35 (26–44) | 2.41 | 0b4e0f2 |
| lyon | fua | 602–610 (9, done) | `1404a50e` | 245 | 208 | 23 (17–31) | 1.61 | 0b4e0f2 |
| strasbourg | fua | 611–619 (9, done) | `8bfe6202` | 131 | 97 | 11 (8–13) | 0.83 | 0b4e0f2 |
| bordeaux | fua | 620–628 (9, done) | `5f5d0d9f` | 182 | 143 | 16 (12–19) | 1.05 | 0b4e0f2 |
| warsaw | fua | 629–637 (9, done) | `72a9a41e` | 418 | 339 | 38 (21–57) | 2.63 | 0b4e0f2 |
| krakow | fua | 638–646 (9, done) | `81a148c2` | 197 | 167 | 19 (12–27) | 1.43 | 0b4e0f2 |
| budapest | fua | 647–655 (9, done) | `0a58443e` | 218 | 184 | 20 (14–27) | 1.51 | 0b4e0f2 |
| prague | fua | 656–664 (9, done) | `678529b2` | 281 | 229 | 25 (19–32) | 1.62 | 0b4e0f2 |
| ljubljana | fua | 665–673 (9, done) | `81ef23ad` | 236 | 211 | 23 (17–28) | 1.57 | 0b4e0f2 |
| bratislava | fua | 674–682 (9, done) | `2e7369e0` | 130 | 104 | 12 (8–15) | 0.94 | 0b4e0f2 |

Totals: LAU invocations 1,927 s (run walls 1,569 s), FUA invocations 6,913 s (run walls 5,747 s);
the whole task, downloads included, took 2 h 36 min of wall clock. Per-year time grows with the size of
the clipped area: Strasbourg/Bordeaux LAU 2 s, Paris FUA 96 s (M3 v1: 98 s). The largest per-year
peak is Paris FUA 2026 (run 511) at 5,092,652 kB (4.86 GB), under the 8 GB gate.

Region sets (`regions_for`), all with `uncovered_km2` 0.0: as Task 15's current FUA merges
(paris 6, amsterdam 4, madrid 3, bordeaux 2, prague 2, strasbourg 2, utrecht 2, warsaw 2), plus
berlin FUA = brandenburg; every other series is the city's own region (vienna = austria,
copenhagen = denmark, budapest = hungary, bratislava = slovakia, ljubljana = slovenia,
helsinki = finland, stockholm = sweden, oslo = ostlandet, krakow = malopolskie,
wroclaw = dolnoslaskie, lyon = rhone-alpes, barcelona = cataluna).

- **R1** A published md5 equal to the md5 of zero bytes (`d41d8cd9…`) counts as no published md5: the download is verified by its computed md5 (`md5_source: computed`). Why: on 2026-10-03 Geofabrik's `.md5` sidecars for austria, hungary and slovakia (regenerated 11:29 UTC) held that value beside unchanged, non-empty files (Last-Modified 2026-09-25), so every fetch failed. The austria download's computed md5 equals the md5 Geofabrik published on 2026-10-01 (`ce458253…`), so its history set is M3's `1254c077`. Cost: these three files rest on a computed, not a published, checksum.

## Rulings and user decisions, by task

Decisions made while building and running M5, each with why and what it costs if wrong. The M5
spec (`docs/superpowers/specs/2026-10-03-velometer-m5-design.md`) and the ADRs win where they
differ, except where a user decision below says it supersedes the spec.

### Setup

- **R2** M5 was built on branch `m5` in the main checkout, not in a git worktree. Why: the
  execution tasks (13–18) need the git-ignored `data/` (about 20 GB of extracts and histories) and
  `velometer.sqlite`, which a worktree lacks. Cost: a less isolated tree; nothing else.
- **User decision (2026-10-03):** unsandboxed Bash is allowed for this repo, because the
  sandbox cannot start on this machine (`apply-seccomp`: nested user namespaces are restricted).
  A later decision the same day allowed the controller and agents to run the regeneration
  commands (`report charts`, `maps`, `methodology`, `csv`; `reconcile --write` and
  `timeseries --write`) inside the repo, on the condition that each commit's diff changes only
  the generated blocks.

### Task 2: per-run peak memory (`runs.peak_rss_kb`, schema v7)

- **R3** The sampling mechanism. `velometer.memory.PeakRss` is a context manager around the run
  block. It samples the process RSS on entry and on exit, and a daemon thread samples it every
  0.2 s in between; the run stores the highest sample. It replaced `getrusage`'s `ru_maxrss`,
  which never goes down within a process and so cannot give a per-run peak when one invocation
  runs several cities or years. Its caveats:
  - **Lower bound under a long GIL hold.** The sampler thread cannot run while one C call holds
    the GIL. Pure-Python loops release it every 5 ms (the interpreter switch interval), and the
    entry and exit samples bracket the step, so only a peak inside one long C call can be missed.
  - **Process-wide baseline.** The sample is the RSS of the whole process, so in a multi-run
    invocation a run's peak includes memory still held from earlier runs.
  - **Cross-check.** Task 15 ran Paris FUA (the largest run) alone under `/usr/bin/time -v`:
    3,384,384 kB against `peak_rss_kb` 3,387,384 kB, within 0.1 %.

  Why: good enough for an 8 GB gate with the ways list alive throughout the run. Cost: a peak
  under-read near the threshold. The peaks and the gate result are in ADR 0007's M5 notes.

### Task 3: boundary EPSG check

- **R4** `check_epsg` runs in `write_boundary` for the `lau` and `osm_relation` kinds only. Where
  test fakes wrote synthetic polygons far from the city, the fakes were moved into the city's UTM
  zone; the rule was not weakened. Why: the rule must hold for every real write. Cost: a few
  fixture edits.
- **R5** Copenhagen keeps EPSG 25832 through an explicit `CityConfig.epsg_exception` with a
  reason text. `check_epsg` accepts it only when the configured zone is adjacent to the centroid's
  zone. Why: 25832 is the Danish national standard; the centroid (12.57° E) is only 0.57° into
  zone 33, a scale error of about 0.06 %; and changing it would silently diverge from the 70
  recorded pilot runs, because the EPSG is not part of the run key. Cost: Copenhagen lengths off
  by under 0.1 %.

### Task 6: trust gate on report surfaces

- **R6** The static `note` texts of the rankings in `config/report.yaml`, which named pilot NUTS3
  codes, became generic ("NUTS3 region per city; marked cities: NUTS3 is not the city"). The
  per-city NUTS3≠city marker (the † on the QECIO axis) is generated from `cities.yaml`
  (spec §4.3). Why: static notes would name untrusted or new cities and do not scale to 21.
  Cost: one subtitle line.
- **R7** `reconcile --write` and `timeseries --write` leave untrusted cities out of the generated
  blocks. Why: report surfaces show trusted cities only (spec §3.3). Cost: an untrusted city's
  block reappears once it is trusted, which is the intended flow.

### Task 7: trust diagnostics

- **R8** The pilot comparison block in `trust diagnose` applies to any country whose `trust.yaml`
  entry sets `pilot`, not only France and Poland. Why: the field is data; FR and PL just happen
  to be the only ones that set it. Cost: none.

### Task 9: charts for 21 cities

- **R9** The city page gains `headline_city(data, city_id)`: one city's headline over time, LAU
  solid and FUA dashed. Why: the index headline chart became LAU-only, and spec §4.1 says FUA
  "lives on the city page", which until then showed only tier charts. Cost: one extra chart per
  city page.
- **R10** The "Highlight a city" picker's parameter is hoisted by altair to the top-level
  `params` of the spec, and the tests accept it there. Why: that is altair's output shape, not a
  design choice. Cost: none.

### Task 10: caching and the 21-city chart

- **R11** The grey "other" layer and the comparison end labels were verified visually on real
  data in Task 18, not on the synthetic fixture, whose cities are copies of Berlin and overlap.
  Cost: a chart fix found late (see the Task 18 verification below).

### Task 13: onboarding the 16 cities

- **R12** `trust.yaml` `unrecognised_share_max` is 0.001. The pilot maximum × 1.25 is 0.0000452,
  which rounds to 0.0 at three places, and the schema refuses 0. Cost: more breaches to note than
  a tighter limit would give.
- **R13** The nine `-dirty` current runs 223–231 (a `trust diagnose` wrote untracked docs while
  the batch ran) stay in the DB, superseded by the clean reruns 232–240. Cost: none; history only.
- **User decisions (2026-10-03, the Task 13 sign-off stop):**
  - **Golden samples:** all proposed verdicts for NL, ES, SE, NO, FI, HU, CZ and SI were
    accepted. Classifier v3 = v2 + `cycleway[:side]=soft_lane` → tier D advisory, and v3 becomes
    the report classifier.
  - **Bratislava:** the admin layer is the union of its 17 GISCO LAU borough polygons, and its
    population is the sum of their `POP_2024`.
  - **Population for Lyon, Strasbourg, Bordeaux, Madrid and Barcelona:** national statistics
    (INSEE populations de référence, INE padrón), cited in `cities.yaml` as
    `{value, year, source, source_url}`, with a methodology limitation naming them. This
    supersedes spec decision 9 (`urb_cpop1`), whose Urban Audit "city" codes turned out to be
    greater cities, not the commune.
  - **Oslo and Helsinki:** back to GISCO LAU, the ADR 0004 default; the boundary difference is
    water.
- **R14** The boundary check stays an area comparison of LAU against the OSM relation. A breach
  caused by water is explained by a reviewed `### <city>/boundary_diff_pct` note (Oslo in
  `NO.md`, Helsinki in `FI.md`), not by an automatic switch of the admin layer. Why: there is no
  offline land/water layer to compute a land-only area, and the note is the trust gate's existing
  mechanism. Cost: the "land area" wording given to the user is implemented as a reviewed note,
  not a computed metric.

### Task 13b: LAU unions and cited populations (code)

- **R15** `cities.lau_code` in the DB stays NULL for a `lau_codes` city (Bratislava). Why: nothing
  downstream reads it (only `upsert_cities` writes it); the codes live in `cities.yaml` and in the
  boundary's `source_version`. Cost: a SQL consumer sees no LAU code for Bratislava.

### Task 13c: finishing the onboarding

- **Disclosed, Oslo and Helsinki land loss.** The user's decision rested on "the difference is
  water". The area difference is water, but moving from the relation to the 1:1M GISCO LAU also
  drops tier A–E km on islands and shoreline that the LAU polygon leaves out: **Helsinki −23.1 km
  (−1.7 %)** and **Oslo −3.5 km (−0.7 %)**, measured by clipping the relation snapshot to the LAU
  (classifier v2). Both boundary notes say so; ADR 0004's M5 notes record the areas.
- **User decision (2026-10-03), Slovakia's golden sample:** v3 also adds
  `cycleway[:side]=advisory` → tier D advisory. `cycleway:right=shared_busway` (a misspelling of
  `share_busway`, 0.16 km) stays unrecognised, and its golden verdict is restated as
  unrecognised. SK is confirmed with the other countries.

### Task 14: classifier v3 and the trust sign-off

- **R16** After the switch to v3 the report surfaces temporarily lacked history and FUA, because
  v2-only runs are filtered out. This was planned: Task 15 ran FUA current for all 21 on v3 and
  Task 16 the full LAU and FUA history, and the methodology was regenerated afterwards. Cost:
  none; the v2 runs stay in the DB.
- **R17** Norwegian golden way 1262980246 (Frysjaveien), right side, now expects tier D advisory
  (`min_classifier: v3`). The user accepted all NO verdicts, whose text calls it "a D advisory
  lane", and approved the advisory rule. Cost: one golden expectation.
- **R18** France, Austria, Denmark and Poland got `classifier_reviewed: v3` on a zero-km-change
  basis: v3 adds only `soft_lane` and `advisory` values, which move 0 km in their cities on the
  same snapshot, and the Berlin golden set passes 48/48 on v3. Cost: a later rule that touches
  their tags would need the review this field claims happened.
- **R19** The dirty runs 249–269 (a doc edited while the batch ran) stay in the DB, superseded by
  the clean runs 270–290, as with 223–231.

### Task 15: current FUA runs and the memory gate

- **R20** The 8 GB gate was not tripped (largest current run Paris FUA, 3.26 GB; largest run of
  all, Paris FUA history 2026, 4.86 GB), so **Task 12, streaming classification, was skipped**,
  and the peaks are recorded in ADR 0007's M5 notes.
- **R21** Task 15 had no separate task review: its only commit, 9a545a2, is a regenerated
  methodology that passes `--check`. Cost: none; the final review covers it.

### Task 16: history runs

- **R22** The history run set spans two commits: Berlin and Paris LAU ran at 9a545a2, every
  other series at 0b4e0f2. The second commit touches download verification only (R1), and the
  `config_sha256` is the same. Cost: none.
- **R23** Run 313 is kept as a `failed` row with a note. It was a launcher kill, not a pipeline
  failure, and Berlin LAU 2018 is run 314. "No run may fail" is read as "no city-year lacks a done
  run", and none does. Cost: one row to delete if read literally.
- **The Geofabrik zero-byte md5 incident (2026-10-03).** Geofabrik regenerated the `.md5`
  sidecars for austria, hungary and slovakia at 11:29 UTC with `d41d8cd98f00b204e9800998ecf8427e`,
  the md5 of an empty input, next to unchanged, non-empty files (Last-Modified 2026-09-25,
  sizes unchanged). Every fetch of those regions failed the md5 check, correctly, but on an
  impossible checksum. The fix (R1, commit 0b4e0f2, with a test that fails without it) treats that
  value as "no published md5" and verifies by computed md5; a review round (commit 5735e7e) added
  a warning and a `Content-Length` size check on that path. Austria's computed md5 equals the md5
  Geofabrik published on 2026-10-01, so the file is byte-identical to M3's. Hungary and Slovakia
  were never downloaded before and rest on computed checksums only.

### Task 17: explanations

- **R24** The draft writers (eight agents, one per country group) wrote into workspace files, and
  one integrator edited `docs/review/m3_timeseries.md` and `docs/reconciliation.md`. Why: eight
  agents editing the same two tracked files would conflict and dirty the tree. Cost: one extra
  integration pass.
- **R25** Cause labels follow each doc's existing pilot vocabulary. The time series uses
  construction, campaign and tag drift, and falls back to mapping activity, classifier and
  boundary when nothing fits. The reconciliation uses definition, boundary and date, plus scope
  and mapping activity. The drafts' "tagging" became "tag drift", and each Explanations intro has
  a one-line legend. Why: one vocabulary per doc, consistent with the pilots; the plan's six-label
  list matched neither doc. Cost: label wording only.
- **R26** "Tag drift" is both a cause label (for retagging sweeps) and the name of the
  `tag_drift` flag, and the legend defines it. Why: it is the pilot vocabulary. Cost: possible
  reader confusion, fixable by a wording pass.
- **R27** QECIO's `boundary_mismatch` tag is derived from `cities.yaml` `nuts3_is_city: false`
  (in union with any explicit `reconcile.yaml` list), not hand-listed. Why: spec §4.3 generates
  the NUTS3≠city marker from `cities.yaml`; only Copenhagen was listed, while about 12 cities have
  `nuts3_is_city: false`. Cost: more tagged rows in the table.
- **R28** `config/reconcile.yaml` gains an explicit `not_in_source: {clean_cities_2025: [...]}`
  list with a reason (Utrecht, Stockholm, Strasbourg and Bordeaux are not in the 36-city ranking).
  `missing_required` skips listed cities, and the table says "not in source". Why: `required`
  could never be met for them, and an explicit list keeps "required" meaning "no forgotten data
  entry". Cost: one config list.
- **R29** Areas in the explanations cite our boundary polygon measured in the city's EPSG, not
  GISCO's `AREA_KM2` attribute, which is 4–9 % lower for Stockholm, Helsinki and Amsterdam (cause
  not checked). Why: lengths and areas are computed only in the city's projected EPSG. Cost: area
  shares off by a few per cent.

### Classifier design points left for later

Found while explaining the series. They are recorded here, not changed in M5, because a rule
change is a new classifier version (ADR 0005):

- **Ljubljana, cycleway against path:** the same tags give tier A on `highway=cycleway` and
  tier B on `highway=path`. About 100 km moved from A to B in 2021–23 with A+B unchanged.
- **Mountain-bike trails at tier A:** `highway=path` + `bicycle=designated` (+ `foot=no`) trails
  reach tier A through `A_path_cycle_only` (Bratislava 6.1 km; also at Myślenice).
- **Prague footways retagged as cycleways:** park and riverside footways retagged to
  `highway=cycleway` + `foot=yes` count as tier A (`A_cycleway`), about 20.5 km, because
  `foot=yes` is not `designated`.

## Task 18: report regeneration and verification (2026-10-03)

- **R30** `report charts` regenerated the three `docs/review/m4_*` charts for 21 cities;
  `report methodology` produced no diff (already current); `report maps` found all 42 maps
  unchanged (current runs unchanged since Task 15). `report csv` was written to the session
  scratchpad and not committed; M4 committed no CSV either, and the app serves it live.
- **R31** The visual check used headless Chrome (153, `--headless=new`) driven over the DevTools
  protocol from a scratch Node script, as in M4's R15, now with a live network log. All 23 pages
  (`/`, `/methodology`, 21 city pages) were screenshotted at 1280 and 390 px. No page scrolls
  horizontally at 390 px: wide tables and charts scroll inside their own boxes.
- **Network:** the browser requested only the app on 127.0.0.1 (pages, `/static/`,
  `/maps/*.geojson` and a 404 favicon) and `tile.openstreetmap.org`.
- **Picker:** choosing "Praha" in "Highlight a city" sets the `pick` selection to
  `{"city": ["Praha"]}` in the Vega view, and the Praha line is drawn highlighted.
- **Trust filter:** with SK set to `pending` in a scratch copy of `config/` (served with
  `--config-dir`), Bratislava is absent from the index and the CSV, and `/city/bratislava` and
  `/data/bratislava.csv` return 404. Its map GeoJSON was still served by URL at the time (the
  deferred Task 6 minor); Task 18b fixed it (R32).
- **Numbers:** the Berlin, Bratislava and Prague pages match `velometer results` (LAU and FUA): the
  three presets, tier km A–E and km per 100k residents.
- **Charts (R11's real-data check):** the grey "other" layer shows the 16 non-focus cities, Berlin
  is highlighted, and Paris, København, Wien and Amsterdam carry end labels; the QECIO axis marks
  the 12 cities whose NUTS3 region is not the city with †. Two layout defects were seen, and
  Task 18b fixed them (R32): the København and Amsterdam end labels run into the legend in the headline chart
  (the labels sit near the top of the y range, beside the legend), and the year labels of the
  21 small multiples in `m4_tiers.png` overlap. A third is ambiguity, not error: the † is drawn
  8 px above its point (`dy: -8`), so Strasbourg's mark (QECIO rank 13) reads as if it belonged to
  Paris (rank 12). The spec's data marks exactly the 12 `nuts3_is_city: false` cities. Task 18b
  fixed this as well (R32).

## Task 18b: chart fixes and the /maps trust filter (2026-10-03)

- **R32** Inserted after Task 18 to fix the defects its screenshots showed, before the final
  review. Why: they are visible in published charts, and `/maps` leaked untrusted cities. Cost:
  one extra task.
  - The headline legend moved below the plot, so the end labels no longer run into it; the
    21 small multiples show at most four year labels; the QECIO † sits on its own point, to the
    right (6e3a0d9, charts regenerated in 4ae54a8).
  - `/maps/*.png` and `/maps/*.geojson` return 404 for a city whose country is not trusted
    (84d2512).
  - The controller's re-render showed the end-label spread inverting the order (Wien above
    Berlin). Labels now keep their lines' order and are pushed down only (14b3673, charts
    regenerated in 7b8e80d).

## Final fix pass after the whole-branch review (2026-10-04)

- **R33** One fix dispatch took the review's three Important findings, its new minors 1–7, and
  the deferred items graded medium or published (base 7b8e80d). Rulings of the controller:
  `trust check` enforces `classifier_reviewed == report_classifier` for every trusted country,
  per spec §3.3 (the plan had narrowed it to countries with a golden set). The remaining low and
  trivial deferred minors are listed below as known follow-ups.
  - Rankings chart: the grey lines carry small grey points, so a city whose line breaks beside a
    column (no Clean Cities figure: Utrecht, Stockholm, Strasbourg, Bordeaux) shows its QECIO
    rank, and each † sits beside a point. A null rank draws no mark, so the subtitle names the
    cities each source does not publish a figure for. End labels stay above 0 (e379954;
    regenerated in 9ccfa69).
  - The nine golden `.osm` fixtures carry the ODbL note of their `.yaml` siblings, and
    `trust sample` writes it (c0d8332, ADR 0008). A test holds every golden way id to its
    `.osm` (e8ca430).
  - `trust check` also fails when a configured city of a trusted country is missing from its
    `<cc>.json`; the methodology lists both conditions under the command's real name,
    `velometer trust check` (29167b6).
  - Trust review files show shares below 1 % with 2 decimals; they were re-rendered from the
    committed `<cc>.json`, numbers unchanged (0dea1e5).
  - A history download without a published md5 must be an OSM PBF: a `text/html` response or a
    body without the `OSMHeader` blob raises `DownloadError` and leaves no file (0582111).
  - A test pins that `reconcile --write` and `timeseries --write` leave untrusted cities out
    (1472794).
  - Published text (a569047): the Urban Audit population fallback is marked as unused by any
    configured city; the national-statistics limitation cites the user decision of 2026-10-03
    (Task 13 sign-off, above), which has no R-number, instead of spec decision 9 and a task id;
    the German slips are fixed; the trust-gate bullets are parallel.
  - The time-series legend defines **construction** as new ways mapped, consistent with known
    construction, with an official source. No source is at hand for paris/lau/2020,
    paris/lau/2021 or paris/fua/2019, so they are now mapping activity in mapped km (03feef7).

### Known follow-ups (low or trivial, from the final review)

- T1 `create_schema` raises on `BEGIN` inside a caller's transaction (no call site).
- T2 The peak tests assert only `> 0`; the `PeakRss` docstring lacks the R3 caveats.
- T3 The CLI `needs_region` branch (`lau` + `osm_relation`) is untested; the ±1 adjacency is
  tested only through `check_epsg`, not `write_boundary`; the spec §5.3 stored-boundary EPSG test
  became a write-time check, so boundaries stored before M5 are not re-validated by a test.
- T4 `test_pilot_cities_carry_their_external_source_ids` pins config values; golden rows are
  compared with exact float equality.
- T5 A no-op `rankings[1:]` and an `object.__setattr__` mutation in `test_report_data.py`;
  `ranking_rows` recomputes city ids per ranking; the fixture hard-codes DE300/FR101.
- T6 A redundant assertion in `test_report_data.py`; the reconcile `--check` assertion is weak.
- T7 The cycling-tags filter in `diagnose_city` is only partly pinned.
- T8 The multi-city `osmium.merge` path of `trust sample` is untested; the skip reason of
  `check_country_golden` is not unit-tested; the classify→observed loop is duplicated three
  times; the per-city loading of `trust sample` lives in `cli.py`; mid-file imports in
  `tests/test_trust.py`.
- T9 `charts.py` uses the private `ReportData._city_fields()`; duplicate ids within `highlight`
  or `comparison_set` are not rejected; the rings-layer filter is asserted by substring.
- T10 The cached CSV freezes `git_commit()` and its "generated" time until the fingerprint
  changes; no threaded test for `PageCache.get`; `LazyData` forwards any attribute; the
  fingerprint is computed twice per request.
- T11 `_boundary_source` keys on the "OSM relation" prefix; the golden path is built two ways,
  and with a scratch `--config-dir` the golden counts silently show "none"; the English Status
  column is always "trusted".
- T13b The missing-code error test is not red-proofed; `lau_codes` + `osm_relation` is untested;
  a `# type: ignore` on `_positive`; the `lau_codes` config test is bundled.
- T13c The Madrid/Barcelona `source_url` is a JS-rendered page (the API URL is in the yaml
  header); `golden_util` filters with dict equality.
- T15 The map PNGs draw whole ways across the boundary while the km are clipped (M4 behaviour).
- T16 The timeseries shipped-config test ties to the default; the `history.yaml` regex assumes
  2-space indentation; the no-sidecar computed-md5 path logs nothing.
- Re-review residuals: two explanation lines break the 100-column wrapping (paris/lau/2021,
  ljubljana/fua/2025); the construction-label test checks only entries that start with
  "Cause: **construction**".
