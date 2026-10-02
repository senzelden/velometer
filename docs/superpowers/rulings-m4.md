# M4 execution rulings

Decisions made while building M4, each with why and what it costs if wrong. The M4 spec and the ADRs win where they differ.

- **R1** Task 4's fixture DB is a shared test module, `tests/report_fixture.py`, with one `fixture_db` fixture in `tests/conftest.py`. Charts, methodology, maps and the app all reuse it. Why: the plan relied on "the Task 4 fixture DB" without naming a file. Cost: a refactor of test imports.
- **R2** `run`, `results`, `reconcile` and `timeseries` default `--classifier` to `report_classifier` in `config/report.yaml`. The single-file `classify` debug command is unchanged. Why: spec §3.3 covers every report surface, and `results` is one. Cost: a one-line default revert.
- **R3** The v5→v6 migration runs only through `velometer migrate --activity-sha <sha>` when the activity table has rows. On the real DB, the sha was the full sha256 of `config/activity.yaml` at 4e6a6a0 (`de066a28e74c…`), checked against the M3 marker prefix. Why: rows must never land under the wrong activity identity. Cost: one extra command per old DB.
- **R4** `Selector`, `run_selector` and `report_selector` live in a library module, `velometer.selection`, and `velometer.cli` re-exports them. A test asserts the report layer never imports the CLI. Why: charts, maps and the app must not pull in typer. Cost: none.
- **R5** Current FUA runs record and hash the Geofabrik **index ids** of their regions, as history sets do, not the download paths. Why: one vocabulary in `history_sets`. Cost: none.
- **R6** `tiers_small_multiples` was added (not in the plan) for `m4_tiers.png`, because the plan asks for small multiples of every city. Cost: none.
- **R7** The methodology is generated in English and German. The German review fixes were taken in the same round:
  - tier B is "Geh- und Radweg (gemeinsam oder getrennt)";
  - each citation is attached only to the claim its source makes;
  - "Kennzahlvariante" is used for preset.

  Why: it is published prose. Cost: wording edits.
- **R8** Charts strip `$schema` and embed with `mode: "vega-lite"`. The JS bundles are vendored at vega 6.4.0, vega-lite 6.4.1 and vega-embed 7.3.0 (altair 6.3.0), resolved from altair's major-only constants and recorded in `app/static/vendor/VERSIONS`. Why: the pages must reference no external URL. Cost: a version bump needs a new vendoring step.
- **R9** The "Clean Cities 2025 (published)" ranking uses the `whole_network` share (report of May 2025; Vienna 14 %). It does not use Vienna's July 2025 web correction (22 %, `incl_traffic_calmed_restricted_access`). Why: spec §4.2 fixes the scope; the correction adds traffic-calmed roads and is not like-for-like; and the chart states the scope. Cost: Vienna would rank third instead of last if the correction were taken.
- **R10** The real-data rerun used the stored Geofabrik cookie and the cached history files, after verifying each one's published md5. No credentials were read. No tracked file changed until all 70 runs had finished, so no run records `-dirty`.
- **R11** The `dirty_provenance_m3` limitation now describes the M3 runs as superseded and not shown, because no run in the report carries `-dirty`.
- **R12** The reconciliation evidence paragraph was rewritten for v2. The v1 history is kept as a measured delta. A side-by-side v1/v2 comparison on the snapshots behind two earlier way-level analyses (Paris QECIO shared paths, Wrocław BikeNetKit) found identical A–E tiers, so those analyses stand.
- **R13** The app labels our preset values with `config/report.yaml`'s ranking labels ("Ours: …"). The headline unit is "A+B km per 100 km of main roads (excl. motorways)" (ADR 0003), not a share. Why: the final review found that "share, %" headers and publisher names over our values read as the published figures (Berlin 27.7 under "Clean Cities 2025", where they publish 17). CSV column ids are unchanged (spec §4.3). Cost: none.
- **R14** The final fix wave also took several small hardening items:
  - TrustedHost limited to loopback hosts, against DNS rebinding;
  - a schema-version check on read-only opens, giving a 503 or exit 1 with a pointer to `migrate`;
  - `ConfigError` handling in `report csv` and `report charts`;
  - an LAU-only "Flagged years" count;
  - "mapped km" in the map footer.

  Not taken, as parked minors:
  - the v6 migration's implicit commit before `user_version` (the real DB has migrated, and a re-run loses nothing);
  - `migrate` requiring `--activity-sha` on a fresh DB;
  - the rest of the per-task minors the final review triaged as "can stay".

  Cost: a parked minor resurfaces in M5.
- **R15** The visual check used headless Chrome screenshots at 1280 px and 390 px, because the Chrome extension was not connected. Network isolation was checked from the served HTML: the only outside reference is the footer link to openstreetmap.org/copyright. Cost: no live network log of the browser session.

## Run effects (2026-10-02)

- 70 runs done and none failed: 5 current LAU, 2 current FUA, 45 LAU history, 18 FUA history. All ran on the report classifier v2 under schema v6.
- Berlin's FUA current run uses `[brandenburg]`. Paris's uses its 6 covering regions.
- The 68 runs that already existed on v2 came out bit-identical to their pre-migration counterparts. Only run ids, the config sha and the commit changed.
- No timeseries flag was added or removed. Reconciliation moved from v1 to v2, and only Berlin's figures changed (+0.1 km).
- DB backup before migration: `data/velometer-pre-v6.sqlite`.

## Decided after M4 (user, 2026-10-02)

- **Interactive tier map with public OSM tiles.**
  - The city page gets a zoomable Leaflet map of the current run's tiered sides, with a LAU/FUA switch, tier toggles and a popup per side (way id linked to openstreetmap.org, tier, rule, km, tags).
  - Its background tiles come from `tile.openstreetmap.org`. This lifts the M4 rule that the app makes no external request, for map tiles only. Scripts, styles and data still come from the local app, and Leaflet is vendored.
  - Light private use with the visible attribution follows the OSM tile usage policy.
  - The static PNG maps stay as a download and print version.
