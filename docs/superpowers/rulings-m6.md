# M6 rulings

## Task 1a

Items of the M5 known follow-ups closed by ruling instead of a fix (one line each: item, why,
cost).

- T11, English Status column: no change. The cell already prints the country's `status` from
  `trust.yaml` (`CountryFact.status`), and the table lists trusted countries only, so the value is
  "trusted" by design (a pending country must not appear in the published methodology, M5 spec
  section 3.3). Cost: none; the follow-up described a state the code had already left.
- T6, "the reconcile `--check` assertion is weak": `tests/test_report_data.py` has no `--check`
  assertion, so the nearest one was tightened instead: `test_reconcile_check_exits_1_until_the_gap_is_explained`
  now matches the whole stderr line `missing explanation: ### berlin/cc_network_km`, not the bare key
  (the exit code was already asserted). Cost: if the follow-up meant another test, it stays open.

## Task 1b

- T15, geometry in the GeoJSON: a way that crosses the boundary is clipped, so a feature's geometry
  is a `LineString` or, when the boundary cuts it into parts, a `MultiLineString`; a side with
  nothing inside is dropped. The `km` property is unchanged (it was already clipped). Cost: a
  consumer that assumes `LineString` breaks; the app only hands the file to Leaflet, which draws both.
- T15, one clip function for two CRSs: `clip_feature` is CRS-agnostic. The GeoJSON clips in WGS84
  against the boundary file's geometry (as the brief names it); the PNG clips in the city EPSG
  against the projected outline, so drawn km equal counted km to 1e-6 (the test). Cost: a WGS84
  clip of a long edge differs from the projected one by centimetres, invisible on a map.
- T13c: the `.htm` guard checks the URL path (`urlparse`), not the string end, because the JS page
  URL ends in `?t=2881` and a plain `endswith(".htm")` would pass it. The human-readable page stays
  in the `cities.yaml` header; `docs/methodology*.md` still show the old URL until `report` is
  regenerated (they are generated, not edited here).
- Construction-label test: the "Cause:" paragraph (up to the first blank line) is what is searched
  for `**construction**`, since a cause line may wrap. No committed explanation uses the label
  today, so the test is a guard; it was red-proofed with a temporary edit.

## Task 14b: explicit remainder row (user decision, 2026-10-05)

(changed 2026-10-05 by user decision after Task 14: explicit remainder row)

- Why: Berlin's 12 OSM Bezirke cover the OSM city relation, but the generalised GISCO LAU (1:1M)
  the run clips to holds 7.30 km² outside their union (892.35 km² LAU, 890.69 km² union). On the
  real v4 run six rows missed the 0.5 % sum check (B per_side 1.16 %, excluded/mtb 1.33 %).
- Rule: the city boundary minus the union of the subarea polygons is attributed to one derived
  row, `subarea_id = 'remainder'` (a slug `SubareasConfig` now refuses). Subareas plus remainder
  must equal the city per tier row and road class within 0.01 km absolute, replacing 0.5 %
  relative; the `> 0.01 km` skip for tiny city rows is gone, since the absolute rule covers them.
  An empty remainder writes no rows; `runs.subarea_sha` still covers the subarea files only.
- Label: `Outside the {n} Bezirke (LAU edge)` with n from the configured relation count, as a
  constant keyed on the section title "Bezirke" (`config.REMAINDER_LABELS`), not a new
  `cities.yaml` field; other section titles fall back to `Outside the subareas (boundary edge)`.
  Cost if wrong: a second subarea city needs its section title added to the constant.
- Read surfaces show it last and set apart (CLI separator line, an italic row with a rule above
  in the app, last per run in the CSV, last above the city total in the change table); the
  timeseries and the small multiples leave it out. `timeseries --check` now counts only
  non-remainder rows as subarea rows.

## User decisions (2026-10-05, after Task 14)

1. The v4 impact (`docs/review/trust/v4-impact.md`) is accepted: largest headline move −2.7
   (Stockholm), one rank swap (Helsinki and Stockholm, places 1 and 2), MTB exclusion largest in
   Oslo (880 km per side).
2. All 6 retiered golden samples re-signed for v4 (notes record the previous tier rule).
3. Berlin's LAU edge outside the 12 Bezirke is an explicit remainder row (Task 14b above).
4. HANDOVER §11, length rows only: 21.2, 20.5 and 25.2 kept with the source URLs found; 17.3
   dropped (no source); C1, C1b, C1c, C4, C8c and C9 loaded; C2, C3, C5, C6, C7, C8 and C8b
   skipped.

## Rulings by task

One line each: what was decided, why, and what it costs if wrong.

- **Setup.** No worktree; the work ran on branch `m6` in the main checkout, because Part 2
  needs the git-ignored `data/` (about 20 GB) and `velometer.sqlite` (as in M5 R2). Cost:
  isolation only.
- **Pre-flight P1.** Task 1a's stored-boundary EPSG test reads `data/boundaries` read-only and
  skips with a reason when it is absent (M5 spec §5.3 design). Cost: a test that runs only on a
  machine with data.
- **Pre-flight P2.** The real-DB `timeseries --check` was allowed to be red from Task 13 to
  Task 16, while the Berlin report runs had no subarea rows (as M5 R16). Cost: no gate on the
  real DB in that window; the pytest gate was unaffected. Green again from Task 17.
- **Task 2.** `test_report_classifier_is_a_shipped_classifier` was relaxed until Task 15, which
  restored the "newest shipped classifier" assertion. Cost: a weaker guard for Tasks 2–14.
- **Task 2.** v4 rates `footway`/`pedestrian` + `bicycle=designated` + `foot=no` as A (v3: B,
  since `A_path_cycle_only` covered `path` only), following spec decision 3 (no pedestrians on
  the surface → A). Cost: a small B→A move, named in v4-impact.
- **Task 3.** The "awaiting re-sign" note prefix uses the golden file's own
  `classifier_version` (e.g. v2 for `no.yaml`), not a literal "v3". Cost: wording only.
- **Task 5.** Unchecked subarea files left after a failed check are caught at run time: each run
  verifies every loaded subarea file's sha256 against its `subareas` row (written only after the
  checks pass). Cost: one DB lookup per run.
- **Task 6.** Shared-edge double count fixed: `attribute_subareas` scales a way's per-subarea
  lengths so they never exceed its city-clipped length; an edge-lying way splits evenly.
  Cost: a slightly arbitrary even split for ways that lie on a Bezirk border.
- **Task 8.** `missing_subarea_runs` checks only the latest history set plus the latest current
  run, because older sets can never turn green. Cost: no guard on superseded sets.
- **Task 9.** A lost side counts as redrawn only if its matched gained sides cover ≥ 80 % of it
  within 15 m, and road sides match only the same side value (spec decision 15). Cost: some
  genuine partial redraws show as lost plus gained.
- **Task 9.** Two refusals were added: a boundary sha that differs from the runs'
  `boundary_sha256`, and `run_from` not older than `run_to`. Cost: two extra refusal paths.
- **Task 9.** One standalone sidepath replacing tracks on both road sides counts both old sides
  as redrawn (they share the centreline), stated in the `change_map_mapped` limitation.
  Cost: up to one side's km understated as lost in that pattern.
- **Task 10.** The Bezirk change table is extracted by the shared `BEZIRK_HEADING`, not by
  markers (Task 9 writes none). Cost: a heading rename breaks it; mitigated by the constant.
- **Task 11.** Split into 11a (page list; a blank URL reads "no source URL recorded") and 11b
  (the loader refuses a blank or non-http(s) `source_url`), moved to Task 15 after the user's
  verdict on the unsourced rows. Removing those rows had been blocked as destructive.
  Cost: unsourced rows stayed loadable until Task 15.
- **Task 12.** The rules diff in the methodology is shown only for report classifier ≥ v4
  (`RULES_DIFF_FROM = 4`), so v3 output is unchanged. Cost: one constant.
- **Task 13.** `check_subareas` compares the union with the LAU by area (≤ 1 %, the spec's
  wording); the symmetric difference is reported as `symdiff_pct`, not enforced; the run-time
  sum check is the binding sliver guard. Cost: an equal-area misplaced union passes this check;
  the sum check still catches a material one.
- **Task 14.** v4-impact compares v4 with v3 re-run on the same extract (2026-10-03) in a scratch
  DB, not with the v3 runs 270–290 (2026-10-02 extract), to isolate the classifier change.
  Cost: the scratch v3 runs are not in the real DB; the table says so.
- **Task 14b.** Remainder label constant keyed on the "Bezirke" section title; the remainder
  shows headline and A share but is never ranked or charted; `timeseries --check` ignores it.
- **Task 15.** The controller wrote the `prague/b_share_of_ab` trust note (B share 0.845 > 0.784
  on run 1125; v3 0.638): the breach follows directly from the accepted v4 rule (Prague A −62 /
  B +56 km was in the reviewed table). The breach itself was not put to the user separately.
  Cost if wrong: CZ untrusted and Prague hidden until re-reviewed.
- **Task 16.** The 15 current LAU runs 698–712 were `-dirty` (Task 14 files written to the tree
  during the run). They were force re-run on a clean tree as 1113–1127, with identical tier km;
  `--force` marked the old rows failed ("superseded by run N"). Cost: none found.
- **Task 17.** Ljubljana LAU 2022 and 2023 cause label changed from tag drift to campaign (v4
  keeps the cycleway→path retag inside `A_segregated`). The Madrid and Bratislava current
  windows end 2026-10-03. The reconciliation intro states QECIO's track rule from its Table 2
  (p. 15). Cost: wording only.
- **Task 18.** The reported-figures source notes moved to their own full-width row (the long
  notes squeezed the link column to one word per line on the Berlin page). Cost: none.
- **Final fix wave (whole-branch review C1, I1, M2–M8; controller rulings).** C1 fixed, not
  reworded: a still-unmatched gained side of a new way id that lies ≥ 80 % within 15 m of the
  `from` geometry of a same-tier way-side whose id persists and whose length fell counts as
  redrawn; a shrunk side absorbs at most its lost length + 20 % + 15 m; the change page gives the
  net change per tier; the `change_map_mapped` limitation (EN/DE) says so. I1: the page, the
  GeoJSON and the app name both runs, and the app notes when the change map ends before the
  latest current LAU run. M1 parked (a rule change is a new version); the invariance test gained
  `foot=permissive` only (green on v4). M2–M8 fixed as reviewed (M4 by a dated note). Cost: the
  split matcher only considers new way ids, so a retagged existing way along a split stays a gain.

## Run set and verification (Tasks 16–18)

- 420 done v4 runs, one `config_sha256`, one subarea sha, none `-dirty`: current LAU 693–697,
  713, 1113–1127; current FUA 714–734; history LAU 735–923; history FUA 924–1112. Wall clocks
  and peaks are in the ADR 0005 and 0007 M6 notes (largest: Paris FUA history 2026, 5.36 GB).
- Berlin change map 2023-01-01 → current (runs 740 → 713), after the final fix wave (split-off
  pieces count as redrawn): gained 442.3, lost 320.2, retiered 47.4, redrawn 655.9, geometry
  −364.4 mapped km; net A–E +93.7 (2,064.3 → 2,157.9). Before the fix, gained was 797.2 and
  redrawn 301.0. The Bezirk rows plus the remainder sum to the city.
- Render check: 24 pages at 1280 and 390 px; network hosts only the app and OSM tiles; the only
  error was a favicon 404. The Berlin, Ljubljana, Stockholm and Vienna headlines (109.1, 73.5,
  261.0, 89.1) and the Neukölln, Pankow and Treptow-Köpenick rows match `velometer results`.

## Known follow-ups

- The change-map PNG has large vertical whitespace above and below the map.
- No Content-Security-Policy header; the app's no-third-party-script policy is held by
  inspection only.
- Sub-figures carried over in explanations that were not reproduced on v4 are listed in the
  appendix below.
- `docs/review/trust/v4-golden/` holds pre-re-sign copies; `docs/review/trust/README.md` is
  still the M5 record.
- ADR 0002's `B_shared` wording is narrower than `config/classifier/v4.yaml` for paths.
- The change page cannot be reconciled by a reader: the categories sum to the net change per
  tier (within 0.015 km), but only with the replaced km of redrawn sides (296.4 km for Berlin
  2023 → current) and the old km of retiered sides, which the page does not show.
- Split-off pieces are matched against the shrunk way's whole old geometry, not only the part it
  lost; 5.8 of 354.9 km (210 pieces) lie mostly along the kept part. The 1.2× lost-length cap
  bounds this.
- The change-map caption counts way-sides ("6111 mapped gained") without saying so.
- Deferred minors from the task reviews (test gaps and small refactors), by task:
  - **1a:** `observed_tiers` returns a defaultdict; `golden_paths` re-parses `trust.yaml`;
    `golden_not_found` ignores a missing `.osm`.
  - **1b:** construction-label test vacuous today; MultiLineString draw branch untested.
  - **3:** a retiered way's reviewer note is overwritten in the proposal; no test with a way
    retiered on both sides.
  - **4:** the schema table test lacks the three v8 tables.
  - **5:** LAU area 0 raises ZeroDivisionError; `--subareas` ignores `--kind`.
  - **7:** subarea load runs once per history year.
  - **8:** duplicated tier-km helpers in `cli.py` and `timeseries.py`; untested error paths.
  - **9:** change CLI tests skip without osmium; `check_runs` date parse errors not wrapped.
  - **10:** "no change map" message hidden when the md exists without GeoJSON.
  - **12:** a DE methodology line over 100 characters.
  - **14b:** dead `_scaled` helper in `tests/test_measure.py`; an exactly empty remainder has no
    area floor.
  - **2:** third-party `StarletteDeprecationWarning` in the suite output.

## Appendix: Task 17 figures kept but not reproduced on v4

Format: doc · heading · figure · value in the doc · drafter's measurement (drafting group). Three
items of the drafters' list are resolved and left out: berlin/lau/2022 now gives the measured
196–209 km; utrecht/fua/2020 dropped the v3 figure; QECIO's track rule is quoted from Table 2.

- timeseries · amsterdam/fua/2022, berlin/lau/2019, berlin/lau/2026, berlin/fua/2022, utrecht/fua/2020 (cycle streets), vienna/lau/2025 · legacy/contraflow breakdowns, changeset and mapper counts, way examples · as in M5 · not re-derived; classifier-independent (G1)
- reconciliation · amsterdam/qecio_shared_km, utrecht/qecio_shared_km · residual: path location vs retagging since 2024 · not attributed · not checked, no NL329/NL310 polygon in repo (G1)
- timeseries · barcelona/fua/2021 · municipality split (83 municipalities, Barcelona 41.2 km), one-mapper share 52.5%, April-June peak 94.6 km · v3 set 216.3 km · v4 set 215.6 km; parts not recomputed (G2)
- timeseries · lyon/fua/2026 · new-geometry sub-parts 44.2 / 19.2 / 11.2 / 6.2 km; new-id A/B ways 61.1 km by 84 mappers, none above 18% · v3 values · own 10 m matching gives v3 90.7 vs doc 90.1; parts may be off by up to 1.7 km (G2)
- reconciliation · madrid/bnk_network_km · A/B/E matched groups · 334.1 km (v3) · 333.6 km (v3, own method); only the v3->v4 delta (4.5 km, inferred `X_mtb_trail`) applied (G2)
- reconciliation · barcelona/bnk_network_km · matched groups · 233.8 km · 232.2 km (own method; v3 = v4) (G2)
- reconciliation · bordeaux/lyon/strasbourg QECIO entries · QECIO region areas · 10,086.4 / 3,258.7 / 4,797.4 km² · 10,082.6 / 3,258.7 / 4,797.9 km² (G2)
- reconciliation · barcelona/qecio_lanes_km · gap · −1.8% · −1.6% from rounded inputs (G2)
- timeseries · lyon/fua/2021 (NEW) · cause label mapping activity for 2020 track tagging · no official source checked · no spike limit, no mapper/municipality attribution (G2)
- timeseries · bratislava/fua/2022 · retag stats · 31.9 km, 83 ways, 32 changesets, 9 mappers, top share 0.66, 40 in Oct 2021 · 29.1 km on 35 ways (stricter match); changesets/mappers not recomputed (G3)
- timeseries · bratislava/fua/2022 · retagged into A/B · 12.8 km · 13.5 km, same in v3 and v4 (G3)
- timeseries · krakow/lau/2024, krakow/fua/2021, krakow/fua/2023, warsaw/fua/*, prague/*/2020 · v3-era sub-components (e.g. 232 segregated paths +10.5, 418 new cycleways 113.7, 136 designated paths 43.4) · as in M5 · grouping not reproduced; only v3->v4 deltas checked or applied (G3)
- timeseries · wroclaw/fua/2023 · Wrocław part · 14.8 km · 14.2 km (midpoint attribution, v3 and v4) (G3)
- reconciliation · bratislava/qecio_lanes_km · D-gain breakdown · sums to 18.7 (2026-10-02) · total +18.9 on 2026-10-03; `cycleway=advisory` 0.3 km not re-derived (G3)
- reconciliation · prague/qecio_lanes_km · "since then" components · 24.1 / 12.0 / 1.8 / ~6 km · not re-derived on 2026-10-03; C+D still 94.9 (G3)
- reconciliation · warsaw/cc_network_km, wroclaw/cc_network_km · network km and overshoots · 898.4 km, Wrocław +19.5%, Kraków +15.5%, 1,729.6 km · method not reproduced; no one-day change for Warsaw (G3)
- reconciliation · bratislava QECIO entries · SK010 area · 2,051.7 km² · 2,051.3 km² (relation 388265 polygon) (G3)
- timeseries · ljubljana/*, oslo/* · per-key edit breakdowns (641/875 `highway`, 692/793 `cycleway:surface`, 280 `segregated`, 4,669/5,731 Oct-Dec, 2,154 March, 1,037/2,874/2,785 changesets, top-changeset shares) · as in M5 · not re-derived; classifier-independent (G4)
- reconciliation · helsinki/*, oslo/*, stockholm/* · v3 comparison totals (1,760.6, 2,519.1, 90.6, 1,176.8, 3,801.8, 231.9, 3,756.1, 5,581.5) · quoted from M5 text · v3->v4 differences reproduced way by way, not by v3 runs (G4)
- reconciliation · stockholm/qecio_main_km · SE110 area and limited-access roads · 7,072.8 km², 294.6 km · QECIO file not re-opened (G4)
