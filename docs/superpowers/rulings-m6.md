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
