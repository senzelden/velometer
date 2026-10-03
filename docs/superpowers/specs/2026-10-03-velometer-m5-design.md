# velometer M5 design: scale to 21 cities

- **Date:** 2026-10-03
- **Scope:** HANDOVER §9 milestone M5, plus the items carried in from M4 (`docs/superpowers/rulings-m4.md`, "Carried into M5").
- **Inputs:**
  - `HANDOVER.md` §5, §6, §9 (M5) and §10;
  - ADRs 0001–0008;
  - the M4 spec and `docs/superpowers/rulings-m4.md`.

## 1. Intent

**Outcome:** the report, app and methodology cover all 21 cities on the same footing as the 5 pilots. They have one report classifier, LAU and FUA boundaries, 2018–2026 history and comparison layers, and every gap and flag is explained. No city enters the report before its country's tagging has been checked.

**The 21 cities:**
- Berlin, Paris, Vienna, Copenhagen and Wrocław (the pilots);
- Amsterdam, Utrecht, Madrid, Barcelona, Stockholm, Oslo, Helsinki, Lyon, Strasbourg, Bordeaux, Warsaw, Kraków, Budapest, Prague, Bratislava and Ljubljana (16 new cities).

**Acceptance:**
- Every one of the 21 cities has, on the report classifier:
  - a current LAU run;
  - a current FUA run;
  - LAU history for 2018–2026;
  - FUA history for 2018–2026.
- Each of the 9 new countries (NL, ES, SE, NO, FI, HU, CZ, SK, SI) has passed the trust gate (§3): its diagnostics are within thresholds or explained, and you have signed off its golden sample.
- `reconcile --check`, `timeseries --check`, `report methodology --check` and the new `trust --check` all exit 0. That means every reconcile gap over 20 % and every flagged city/kind/year across all 21 cities has a hand-written explanation (decision 2).
- `velometer serve` renders all 21 city pages, and the index charts are readable at 21 cities.

**Success:**
- Adding a city needs config, a trust pass and runs, and no code change.
- Every number still traces to its run row: commit, classifier, config sha, OSM timestamp and boundary sha.

## 2. Decisions

### Taken with the user (2026-10-03)

1. **Trust gate:** automated per-country diagnostics with thresholds in config, plus a golden sample of about 12 way-sides per new country that you sign off, as with the Berlin golden set. A city enters the report only after its country passes.
2. **Explanations:** full hand-written prose for every city, to the pilots' standard. This covers every reconcile gap over 20 % and every flagged year, on LAU and FUA, with way-level analysis wherever the cause isn't plain from the run rows. The `--check` gates stay hard.
3. **FUA:** current and history runs for all 21 cities. `history.yaml` `required_kinds.default` becomes `[lau, fua]`.
4. **Charts at 21:** focus on Berlin, with a picker. All cities are drawn as thin grey lines; Berlin and a configured comparison set are coloured. In the app, a city picker colours more cities. The tier chart becomes small multiples.

### Taken in design (each one stands unless you object at spec review)

5. **Waves and ordering.** Onboarding runs per country, and the classifier is settled **before** the expensive runs (§6). Current LAU runs and the trust gate come first. A classifier v3, if one is needed, comes next. Only after that do the history and FUA runs start, so there is never a second pass of about 420 runs.
6. **Classifier v3 only if the trust gate finds real gaps.** If it does, v3 becomes `report_classifier` and all 21 cities, pilots included, rerun on it, so the report keeps one classifier (ADR 0005). A v3 rule change is put to you together with the golden sign-off. Without v3, the pilots' 70 v2 runs are reused, and only their missing FUA runs are added (Vienna, Copenhagen and Wrocław: current plus 2018–2026).
7. **Golden samples cover the 9 new countries only.** FR, PL, AT and DK were accepted through M2 reconciliation. New French and Polish cities still get the automated diagnostics, compared against their pilot city in the same country (Paris and Wrocław).
8. **Comparison layers for every city:**
   - Clean Cities 2025 where it publishes a figure;
   - QECIO v2.10 by NUTS3, with a recorded flag saying whether the NUTS3 unit equals the city;
   - BikeNetKit.

   No new official city figures; the existing Berlin rows stay. A city with no published figure gets no row and is shown as absent (§4.2), never as zero.
9. **Population fallback.** Some French communes have no LAU population and no identical NUTS3 unit (Lyon, Strasbourg and Bordeaux, where NUTS3 is the département). Their population comes from Eurostat Urban Audit city population (`urb_cpop1`, the city `…C` code). It is stored with its year and source, and checked to show that the Urban Audit city is the commune. A new limitation entry records this.
10. **Carried items:** all of them are in scope (§5) except public publishing. The app stays private, bound to 127.0.0.1.
11. **Streaming classification is gated by measurement.** Every run records its peak RSS. If any run goes over ADR 0007's 8 GB threshold, streaming classification is built before the full run (§5.1). If none does, the measured peaks go into ADR 0007 and the carried item is closed as not needed.
12. **Runs stay sequential.** There is no `--jobs`. The full run is an unattended overnight job; parallel runs would make peak memory and provenance harder to reason about. (Estimate: about 350 new runs; FUA history at the M3 rate of 35–130 s per year is the bulk, roughly 6–8 h.)
13. **The report files stay single files.** `docs/reconciliation.md` and `docs/review/m3_timeseries.md` grow but keep their structure, so the tooling and markers stay unchanged.

## 3. Trust gate

### 3.1 Diagnostics (`velometer trust diagnose --country XX`)

These are computed from each city's current LAU run on the report classifier. Nothing new is fetched.

| Metric | Definition |
|---|---|
| `unrecognised_share` | unrecognised km over all way-side km that carry cycling tags |
| `excluded_share_by_rule` | km per exclusion rule over cycling-tagged km |
| `tier_mix` | share of A, B, C, D and E in A–E per_side km |
| `b_share_of_ab` | B over A+B (shared-path inflation, HANDOVER §10.1) |
| `completeness` | the existing width, surface and segregated shares per tier |
| `top_unmatched_tags` | the 20 most frequent tag combinations on unrecognised and excluded sides, by km |
| `boundary_check` | GISCO LAU area against the OSM admin relation area |

- **Thresholds** live in a new `config/trust.yaml`. Initial values come from the pilots' distribution: the largest pilot value plus a margin, set during build and recorded with the pilot values that justify them.
  - `boundary_check` fails at a difference of more than 5 %. This covers the ADR 0004 cases (Oslo, Ljubljana, Bratislava). On a fail, the OSM admin fallback is used, with its relation id, and the decision is recorded in `cities.yaml`.
- Output: `docs/review/trust/<country>.md`, generated between markers, with hand-written notes outside them. It holds every metric per city, pass or fail per threshold, and the top unmatched tags.

### 3.2 Golden sample (`velometer trust sample --country XX`)

- About 12 way-sides per country, chosen by query from the country's current snapshot, not from memory and not from Overpass:
  - the most-km way-sides of each of the country's 6 highest-km rules (6 to 8);
  - the top unmatched tag combinations (2 to 4);
  - one or two country hotspots found in the diagnostics.
- The ways are extracted with `osmium getid` into `tests/fixtures/golden/<country>.osm`, each with an ODbL note (ADR 0008). Expected tiers go in `tests/fixtures/golden/<country>.yaml`, which carries `status: pending` until you sign off.
- The review page `docs/review/trust/<country>_golden.md` lists, for each sample: the way id linked to openstreetmap.org, the tags, our tier and rule, and an empty verdict column (`ok`, or the correct tier with a reason) for you to fill in.
- `tests/test_golden_countries.py` runs every signed-off country's fixtures against the report classifier. A pending file is skipped with a visible reason, never silently passed.

### 3.3 Trust state

- `config/trust.yaml` holds, per country: `status` (`pending` or `trusted`), `classifier_reviewed` and `signed_off` (a date). It also holds a pointer to the golden files, and one to the pilot reference for FR and PL.
- Report surfaces use only cities whose country is `trusted`; DE, FR, AT, DK and PL are trusted from the start. Untrusted cities can still be run and diagnosed. They appear in `velometer results`, marked as untrusted.
- `velometer trust --check` exits 1 when:
  - a trusted country's golden fixtures fail;
  - a trusted country's diagnostics break a threshold without a note under `### <country>/<metric>` in its review file;
  - `classifier_reviewed` differs from `report_classifier`.

  Under the last condition, a v3 switch forces a re-review: you confirm, sample by sample, that the tiers you signed off still hold.

## 4. Report and app at 21 cities

### 4.1 Charts (decision 4)

- `config/report.yaml` gains `highlight: [berlin]` and `comparison_set: [...]`. The default comparison set is Paris, Copenhagen, Amsterdam and Vienna; you can change it in config.
- `headline_over_time`:
  - every city's LAU line drawn thin in grey;
  - highlight and comparison cities coloured and labelled at the line end;
  - a Vega-Lite selection parameter bound to a dropdown in the app (no new JS: it's built into vega-embed);
  - the PNG export shows the static highlight and comparison colouring.
  - FUA is dropped from this chart; it lives on the city page, because 21 dashed lines are noise.
- `rankings_flip`: the same grey-and-highlight treatment. Each column's header states `n` (the number of cities ranked).
- `tier_composition` on the index becomes small multiples in a 7×3 grid with a shared y-axis. The city page keeps the single-city chart.

### 4.2 Gaps in the rankings (carried)

- A city with no value under a ranking source has no point in that column. Its line is broken there and does not run straight across.
- Ranks are computed among the cities that have a value, and the tooltip says "not published".
- Tests: a city missing from the middle column produces two line segments, and the ranks in that column are dense over the cities present.

### 4.3 QECIO ratio scope (carried)

- `external_ratio` rankings gain a required `scope` (and the NUTS3 match flag from decision 8). The ratio uses only figures with that scope. Two figures for the same metric and scope raise a `ConfigError`; the first one is no longer taken silently.
- Cities whose NUTS3 unit is not the city get a marker in the column footnote and in the reconcile rows.

### 4.4 App performance (carried)

- `report/data.py` results are cached in-process, keyed on the DB file's (`st_mtime_ns`, `st_size`) and the config sha. The app stays read-only, and the first request after a DB change recomputes.
- Target: every page under 500 ms warm, at 21 cities, measured with TestClient on a fixture DB of 21 synthetic cities and recorded in the test output (not asserted, so CI timing doesn't flake). A test asserts that a second request does not call the query layer (a call counter on the cached function).

### 4.5 Methodology

- City facts are generated as before and grow automatically.
- New limitation entries (EN and DE):
  - the trust gate and its golden samples per country;
  - the Urban Audit population fallback;
  - QECIO NUTS3 ≠ city for the affected cities.
- The rules table lists `trust.yaml`'s reviewed classifier.

## 5. Pipeline and data changes

### 5.1 Peak memory (carried, decision 11)

- `run_city` records `peak_rss_kb` from `resource.getrusage(RUSAGE_SELF)` (schema v7), measured around the classify step. The run executes in a fresh subprocess, so the value is per run.
- If the gate trips, streaming classification follows. The classifier yields way-sides from a pyosmium handler pass and keeps only geometry plus the attributes the measure, dedupe and dual-carriageway steps need. Tag dicts are dropped for ways no rule touches. Dedupe and dual-carriageway still need spatial candidates, so they keep an STRtree over the A–D sides and main roads only. The output must be bit-identical to the non-streaming path on every pilot snapshot; a test pins this on fixtures, and execution checks it on real data.
- `report maps` reuses the same path.

### 5.2 Migration minors (carried, R14)

- Every migration step sets `user_version` inside the same explicit transaction, with no implicit commit before it. A test interrupts after the DDL and asserts the DB is still at the old version.
- `migrate` on a DB whose `activity` table is empty doesn't require `--activity-sha`.
- Schema v7 (`peak_rss_kb`, nullable for old runs) uses the corrected pattern.

### 5.3 City config

- Each new entry in `cities.yaml` gets `osm_relation_id`, `lau_code`, `fua_code`, `nuts3_code`, `epsg` and `geofabrik_region`, **queried, never typed from memory**. The query and its date go in the file's header comment, as for the pilots.
- `epsg` is the ETRS89/UTM zone of the boundary centroid. A test asserts that rule for every configured city: the zone computed from the stored LAU centroid equals `epsg - 25800`. It runs over the boundaries present, so a fresh checkout without `data/` skips it with a reason.
- Cities can share a country region extract: Madrid and Barcelona are in different Spanish regions, Amsterdam and Utrecht in different Dutch provinces. `regions_for` already resolves the covering sets.

### 5.4 External figures

- **Clean Cities 2025:** entered from the report table (and its annex) for every one of the 21 cities that has a figure, in the `figures.csv` format with page references.
- **QECIO v2.10:** loaded for the 21 cities' `nuts3_code`. Its rows carry `note` with the NUTS3/city match.
- **BikeNetKit:** loaded for all 21 cities through the existing loader, matched by city name and country.

## 6. Execution order

| Phase | Work | Stops for you |
|---|---|---|
| 1. Build | §4, §5.2, §5.3 tests, trust tooling (§3), `peak_rss_kb`; all offline and tested | — |
| 2. Onboard | the 16 config entries (queried); boundaries; boundary checks; current LAU runs on v2; external figures; `trust diagnose` and `trust sample` for the 9 countries; the FR and PL comparison | **Golden sign-off for all 9 countries in one review**, plus any proposed v3 rules |
| 3. Classifier | if v3: rules, fixtures, golden re-run, `report_classifier: v3`, re-review of changed samples | only if v3 changes a sample you signed off |
| 4. Memory gate | current FUA runs for all 21, peak RSS read; streaming only if one run tops 8 GB | — |
| 5. Full run | the remaining history runs, LAU and FUA, for all 21 cities (pilots too if v3); overnight; clean tree (no `-dirty`) | — |
| 6. Explain | `timeseries --write`, `reconcile --write`; full-prose explanations for every flag and gap, written by subagents per country against run rows and way-level evidence, reviewed before commit | — |
| 7. Report | charts, maps, methodology (EN and DE), all four `--check`s; serve; screenshot every page at 1280 and 390 px; numbers spot-checked against the CLI | final review |

The DB is backed up before each migration and before phase 5 (`data/velometer-pre-v7.sqlite`, `data/velometer-pre-m5-run.sqlite`).

## 7. Testing

- Offline and fast, as before. Real data appears only in phases 2–7.
- Trust:
  - diagnostics on a fixture DB give the expected shares;
  - a threshold breach without a note fails `--check`, and adding the note passes it;
  - a pending golden file is skipped visibly;
  - a `classifier_reviewed` mismatch fails;
  - an untrusted city is absent from every report surface (index, CSV, charts, methodology) and present in `results`.
- Charts:
  - the highlight and comparison sets come from config (red-proofed by changing them);
  - the rankings-gap test from §4.2;
  - the PNG is non-empty at 21 cities.
- QECIO scope: two figures with the same scope raise an error; a figure with a different scope is ignored.
- App cache: hit, invalidation when the DB changes, and every route at 200 for 21 synthetic cities.
- Migrations: the v6→v7 copy test, an interrupted step leaving the old version, and an empty-activity DB without `--activity-sha`.
- EPSG rule and peak RSS: recorded and non-null on a fake run.
- Streaming (only if built): identical results to the batch path on every classifier fixture.

## 8. Out of scope

- Public hosting, publishing and authentication (HANDOVER §12, Q4 stays open).
- New official city figures beyond the existing Berlin rows.
- Copenhagenize figures.
- A German app UI.
- Parallel runs.
- Golden samples for FR, PL, AT and DK.
- Cities beyond the 21.
