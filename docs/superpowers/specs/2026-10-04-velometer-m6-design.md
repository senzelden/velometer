# velometer M6 design: classifier v4 and the Berlin deep-dive

- **Date:** 2026-10-04
- **Scope:** a milestone after HANDOVER §9 (which ends at M5). It has three parts:
  - classifier v4, resolving the three design points in `docs/superpowers/rulings-m5.md`
    ("Classifier design points left for later");
  - a per-Bezirk view of Berlin, the series' centrepiece;
  - the M5 known follow-ups (T1–T16 and the re-review residuals).
- **Inputs:**
  - `HANDOVER.md` §1, §5, §10, §11;
  - ADRs 0001–0008;
  - the M5 spec and `docs/superpowers/rulings-m5.md`;
  - the v4 impact measurement of 2026-10-04 (§3.1).

## 1. Intent

**Outcome:**
- The report rests on a classifier whose A/B line follows the facility, whether pedestrians share
  the surface, rather than the `highway` value a mapper chose. It runs for all 21 cities and all
  years.
- Berlin can be read per Bezirk: its headline, tiers and mapped-km change per district over time,
  plus a change map for a chosen window. All of it carries the same provenance as the city figures.
- The HANDOVER §11 reference facts sit in the DB as cited comparison rows.

**Acceptance:**
- Classifier v4 is the `report_classifier`. Every city has done v4 runs:
  - current LAU and current FUA;
  - 2018–2026 history on LAU and FUA.

  That makes 420 runs, none `-dirty`. v1–v3 and their runs are unchanged.
- ADR 0002 carries an M6 amendment recording the v4 rules and the divergences they replace.
- Every trusted country has `classifier_reviewed: v4`. Each golden sample whose tier v4 changes
  has been re-signed by you.
- Berlin has 12 Bezirk rows for each of its 10 v4 LAU runs (current plus 2018–2026). In every run
  and tier, the Bezirk km sum to the city km within 0.5 %.
- `velometer report change --city berlin` writes the default-window change map and its per-Bezirk
  table.
- The §11 facts you signed off are loaded as `ExternalFigure` rows with source URLs.
- `reconcile --check`, `timeseries --check`, `report methodology --check` and `trust check` all
  exit 0.
- `velometer serve` renders every page, and the Berlin page shows the Bezirk section.
- T1–T16 and the re-review residuals are each fixed or carry a ruling.

**Success:**
- Retagging `foot=yes` → `foot=designated`, or `highway=cycleway` ↔ `path` with the same access
  tags, no longer moves km between A and B.
- Any city can gain subareas through config alone. Only Berlin does in M6.

## 2. Decisions

### Taken with the user (2026-10-04)

1. **M6 thrust:** the Berlin deep-dive.
2. **Classifier:** v4 resolves all three design points, amending ADR 0002.
3. **A/B rule, the unified facility rule** (§3.2). On any standalone cycle-designated way:
   - `segregated=yes` → A;
   - pedestrians permitted on the same surface and not segregated → B;
   - otherwise → A.
4. **MTB trails:** excluded when they carry explicit MTB tags (§3.3). Surface is not used.
5. **Berlin pieces:** a per-Bezirk yearly series, a change map, and the §11 facts as figures. The
   Vorrangnetz overlay is out of scope.
6. **Bezirk boundaries:** the 12 OSM `admin_level=9` relations, queried from the Berlin extract,
   behind a generic `subareas` mechanism. Attribution happens inside the run and goes to new
   tables (schema v8).
7. **Publishing:** the app stays private on 127.0.0.1 (HANDOVER §12 Q4 stays open).
8. **Follow-ups:** all of them, as one hardening task at the start.

### Taken in design (each stands unless you object at spec review)

9. **Implicit pedestrian access follows the highway value.** On `highway=path|footway|pedestrian`
   a missing `foot` tag means pedestrians are permitted (OSM default). On `highway=cycleway` it
   means they are not. So "otherwise → A" applies to cycleways with no `foot` tag or `foot=no`,
   and to paths with `foot=no`. The 3,515 km of untagged cycleways stay A.
10. **Road-side tracks are unchanged.** `cycleway:<side>=track` stays A, and `B_track_shared`
    (`cycleway:<side>:segregated=no`) stays B. v4 changes standalone ways only, plus the MTB
    exclusion.
11. **The QECIO "tracks" comparison follows v4.** Today it is A + B[segregated]. Under v4,
    segregated shared paths are A, so it becomes A alone. `config/reconcile.yaml` and the
    methodology rules table are updated, and the `segregated` subtype of `B_path_segregated`
    disappears with the rule.
12. **v4 impact is a stop before the full rerun.** The 21 current LAU runs on v4 go first. Their
    per-city A, B and A+B deltas against v3, with the changed golden samples, are put to you in one
    review, together with the §11 fact rows. This mirrors M5's single sign-off stop.
13. **Bezirk attribution: LAU only, for cities with `subareas` configured.** FUA runs and other
    cities do not get the step. Subareas use the run's own snapshot and EPSG and record their own
    boundary sha, so provenance is unchanged.
14. **The change map is recomputed, not stored.** `report change` re-reads the two cached
    snapshots behind two done runs with the report classifier. It refuses to write unless its
    recomputed tier totals equal the stored run totals (to 0.01 km). No way-level geometry goes
    into SQLite (ADR 0007 stays as is).
15. **Redrawn ways are not churn.** A way-side lost and one gained, of the same tier, within 15 m
    and with at least 80 % overlap (the dedupe overlap measure, `_share_within` in `pipeline/dedupe.py`), count as `redrawn`,
    not as one loss plus one gain. Ljubljana 2021 shows why: redrawing sidepaths as separate ways
    would otherwise read as building.
16. **Bezirk and change-map figures are mapped km (ADR 0006).** Every surface says so. The change
    map never says "built" or "removed", only "mapped gained / lost / retiered / redrawn".
17. **The default change window is 2023-01-01 → current.** It roughly spans the CDU–SPD Senate
    (in office from April 2023), at snapshot resolution. The window is a CLI option and a
    `report.yaml` default. The pipeline attaches no political label; the narrative does.
18. **§11 facts are researched, not typed.** Each row needs a primary source URL, a retrieval date,
    `network_scope` and `length_basis` (`unknown` where unstated). Facts without a verifiable
    source are left out and listed as such. Kantstraße (no ruling yet) and the conflicting
    Titel 72016 figures go in as separate rows with notes, never merged (HANDOVER §10.5 pattern).
19. **One commit range per phase, sequential runs, a clean tree for runs.** M5's rulings R2
    (main checkout, not a worktree) and R13/R19 (dirty runs superseded) carry over.

## 3. Classifier v4

### 3.1 Measured impact (v3, current LAU snapshots, 2026-10-04)

The measurement used the project's `read_ways` / `classify_ways` on the `*_lau_20261002_*`
snapshots, clipped to the LAU, per_side km. These are upper bounds before overlap between the
rules is removed.

| point | v3 behaviour | km affected (21 cities) | largest |
|---|---|---:|---|
| 1 segregated shared path | `path/footway/pedestrian` + `segregated=yes` → B | 728.9 | Ljubljana 170.2, Kraków 154.8, Berlin 125.8, Wrocław 111.7, Warsaw 97.0 |
| 1 (precedent) | `cycleway` + `foot=designated` + `segregated=yes` → A | 705.5 | Helsinki 255.1, Stockholm 122.0, Vienna 91.7 |
| 3 `foot=yes` cycleway | `cycleway` + `foot=yes` → A | 1,440.6 | Stockholm 424.0, Helsinki 275.8, Vienna 212.8, Amsterdam 203.0 |
| 3 `foot=permissive` | → A | 12.9 | |
| 2 MTB trail | `A_path_cycle_only`, any trail indicator | 25.7 | Vienna 12.1, Bratislava 7.2 |

Points 1 and 3 move km between A and B only, so A+B is unchanged. Point 2 removes km from A+B.

### 3.2 Unified facility rule

The standalone A/B rules of v3 (`A_cycleway`, `B_cycleway_foot`, `A_path_cycle_only`,
`B_path_segregated`, `B_path`) are replaced. They apply to standalone ways with
`highway=cycleway`, or `highway=path|footway|pedestrian` + `bicycle=designated`, that survive the
exclusions:

| rule | condition | tier |
|---|---|---|
| `A_segregated` | `segregated=yes` | A |
| `B_shared` | pedestrians permitted: `foot` ∈ {designated, yes, permissive}, or no `foot` tag on path/footway/pedestrian (decision 9) | B |
| `A_cycle_only` | otherwise (cycleway with no `foot` tag or `foot=no`; path with `foot=no`) | A |

- The rules are evaluated in this order. Any `;`/`,`-separated part counts, as in v2.
- Designated crossings (`highway=footway` + `footway=crossing` + `bicycle=designated`) stay B through
  a new `B_crossing` rule ahead of these. v1–v3 had no separate rule; they counted crossings through
  `B_path`, so v4 keeps their tier.
- The rule ids change, so every classification records its v4 `rule_id`. The rule-level
  diagnostics and trust metrics are keyed by tier and stay comparable across versions.

### 3.3 MTB exclusion

`X_mtb_trail` is an excluded rule (subtype `mtb`) on standalone `highway=path|cycleway|footway`.
It fires when any of these is present:
- `mtb:scale` or any `mtb:scale:*` key;
- `mtb` ∈ {yes, designated, permissive};
- an `mtb:type` key;
- `cycling=mtb`.

It sits with the other exclusions, before the tier rules. Surface and `route=mtb` membership are
not used: the reader keeps dropping relations, and unpaved surface would catch park paths. The
build reports X_mtb_trail km per city, including on cycleways and footways, which §3.1 did not
measure. These go into the decision 12 stop.

### 3.4 Fixtures, golden sets and trust

- `config/classifier/v4.yaml` = v3 with §3.2 and §3.3. Its header records the decisions and the
  date, as v2 and v3 do.
- New fixtures pin every row of §3.2, decision 9, and the MTB exclusion (each key, plus `mtb=no`
  not firing). Existing fixtures run against v1–v3 unchanged. Where a v4 expectation differs from
  v3, the v4 expectation is a separate case.
- **Golden sets:** the Berlin set (48 ways) and the 9 country sets run against v4. Each sample
  whose tier changes is listed in `docs/review/trust/v4-changes.md` with the old and new tier and
  rule, for re-signing at the stop. Samples you re-sign get `min_classifier: v4` expectations, as
  in R17.
- `trust.yaml`: every trusted country moves to `classifier_reviewed: v4` only after the stop. The
  R18 shortcut (zero-km change) does not apply, because v4 moves km in every country.
- ADR 0002 gets a dated "M6 amendment" section. It records:
  - the facility rule;
  - the dropped divergences (segregated paths in B; `foot!=designated` as the A test on cycleways);
  - the kept divergence: QECIO halving still lives in `qecio_weighted`;
  - the MTB exclusion.

  The ADR's earlier text stays as the record of v1–v3.

## 4. Subareas and the Berlin Bezirke

### 4.1 Config and boundaries

- `cities.yaml` gains an optional
  `subareas: {source: osm_admin, admin_level: 9, relations: [{id, name}]}`.
  - Berlin's 12 relation ids are **queried** from the Berlin extract (`osmium tags-filter` on
    `boundary=administrative` + `admin_level=9`, member of the Berlin relation). The query and its
    date go in the file header.
- `velometer boundaries fetch --city berlin --subareas` assembles each polygon offline, as the
  `osm_admin` fallback does (`osmium getid -r` + `export`, `make_valid`). It writes
  `data/boundaries/berlin_sub_<slug>.geojson` and a `subareas` table row per area: city_id,
  subarea_id, name, relation id, area_km2 in the city EPSG, sha256.
- **Checks on write:**
  - the union is within 1 % of the LAU area;
  - pairwise overlaps total under 0.1 % of the LAU area;
  - a polygon that fails either check raises with the measured values.
  - The results go into ADR 0004's M6 notes.

### 4.2 Attribution in the run (schema v8)

- **New tables:**
  - `subarea_tier_lengths` (run_id, city_id, subarea_id, tier, subtype, basis, length_km, n_ways);
  - `subarea_road_lengths` (run_id, city_id, subarea_id, class, length_km).
- Each table has the same keys and bases as its city-level twin.
- **After `measure`**, for a LAU run of a city with `subareas`:
  - each way-side and denominator road is clipped to each subarea polygon, in the run's EPSG;
  - dual-carriageway halving carries through, so the Bezirk denominators sum to the city's.
- The run row stores the subarea set's combined sha (`runs.subarea_sha`, nullable).
- **Invariant**, checked in the run, which fails on a breach: per tier and road class, the sum
  over subareas equals the city value within 0.5 %. The gap is boundary slivers between the LAU
  and the OSM relations.
- **Migration v7 → v8** uses the M5 pattern (R14 / spec §5.2), with a copy test and an
  interrupted-step test. The DB is backed up first (`data/velometer-pre-v8.sqlite`).
- `runs` gets no new key field, so idempotency is unchanged. A v4 Berlin LAU run without subarea
  rows (for example, one made before the subareas were fetched) is a `timeseries --check` failure,
  not a silent gap.

### 4.3 Read surfaces

- **`velometer results --city berlin --subareas`:** one row per Bezirk, giving the three presets
  where their denominators exist per Bezirk, tier km A–E and A/B split.
  - Per-100k needs Bezirk population, which is not in scope, so it is omitted with a reason.
- **`velometer timeseries --city berlin --subareas`:** a yearly series per Bezirk. Flags are not
  computed per Bezirk; city-level flags and explanations stay the gate.
- **The app's Berlin page** gains a "Bezirke" section:
  - a table for the current run;
  - small multiples of the headline per Bezirk over 2018–current, sharing one y-axis;
  - the change map (§4.4) with its per-Bezirk table.

  Untrusted cities never show subareas (DE is trusted).
- **CSV:** `/data/berlin_subareas.csv` gives the per-Bezirk rows for every v4 LAU run, with run
  provenance columns.

### 4.4 Change map (`velometer report change`)

- **Invocation:** `velometer report change --city berlin [--from 2023-01-01] [--to current]`. It
  takes the done report-classifier LAU runs for the two dates and re-reads their snapshots.
- **Matching:** way-sides match on (way id, side). Unmatched pairs then go through the redrawn
  matcher (decision 15).
- **Categories, per_side km:**
  - `gained`: new way-side, or from untiered/excluded into A–E;
  - `lost`;
  - `retiered`: tier changed, with from → to;
  - `redrawn`;
  - `geometry` (same id and tier, length changed by more than 1 m).
- **Output:**
  - `docs/review/berlin_change_<from>_<to>.md`: per-Bezirk km per category and the top 20 ways
    per category, linked to openstreetmap.org;
  - a GeoJSON under `data/` for the app's map;
  - a static PNG in `docs/review/`.
- **The totals check** (decision 14) runs first and is printed with both run ids.
- **Retiering caused by the classifier** cannot occur: both runs are on the same report
  classifier. Retiering caused by retagging shows up, with the tags that changed in the review
  table.

### 4.5 §11 facts as `ExternalFigure` rows

- Candidate rows for each §11 bullet go in `docs/review/berlin_facts.md`. Each row carries:
  - value and unit;
  - reference date;
  - `network_scope` and `length_basis`;
  - the primary source URL and retrieval date;
  - a confidence note;
  - the verbatim sentence the value comes from.
- Secondary reporting is marked as secondary, and a primary source is preferred where one exists.
- Signed-off rows are appended to `data/external/...` figures CSV in the existing format and
  loaded with `velometer external load`. Rows not signed off stay listed as "not loaded" with
  the reason.
- No new reconcile comparison is added. These are narrative rows (HANDOVER §11), shown on the
  Berlin page under "Official and reported figures".

## 5. Hardening (T1–T16 and residuals)

One task, first, before any v4 or subarea code. Each item in rulings-m5 "Known follow-ups" is
either fixed with a test that fails without the fix, or closed with a ruling saying why not.
Notable ones:
- **T15:** map PNGs clip way geometry to the boundary, so drawn and counted km agree. A test
  covers a way crossing the boundary.
- **T2:** the peak tests assert a real bound, and the `PeakRss` docstring carries the R3 caveats.
- **T10:** the cached CSV recomputes `git_commit()` and its "generated" time per request, or
  states that it is cached.
- **T13c:** Madrid and Barcelona get a stable `source_url` (the API URL), not the JS page.
- The two over-wide explanation lines are re-wrapped, and the construction-label test checks every
  entry whose cause is construction.

## 6. Methodology

- **The rules table** shows v4, with a short "changed from v3" note per rule.
- **New limitation entries, EN and DE:**
  - `subareas_osm`: Bezirk polygons come from OSM relations; slivers against the LAU are under 0.5 %.
  - `change_map_mapped`: the change map shows mapped change; redrawn and retagged ways are separated
    out, but a gain is not a construction.
  - `mtb_excluded`: MTB-tagged trails are excluded, and trails without MTB tags stay counted.
- **Updated:** `classifier_gaps_excluded`.
- **Unchanged:** the `trust_gate` entry, apart from the reviewed version.

## 7. Execution order

| Phase | Work | Stops for you |
|---|---|---|
| 1. Harden | §5; gate green | — |
| 2. Build | v4 yaml and fixtures; subareas config, boundaries, attribution, schema v8; `report change`; results/timeseries/app/CSV; methodology code paths; all offline and tested | — |
| 3. Onboard | query the Berlin relations, fetch subareas, run the checks; back up the DB, migrate to v8 | — |
| 4. v4 impact | current LAU runs, all 21 on v4; the delta table against v3; X_mtb_trail km; golden changes (`v4-changes.md`); §11 fact research (`berlin_facts.md`) | **One review: v4 impact, golden re-signing, §11 rows** |
| 5. Switch | `report_classifier: v4`; `classifier_reviewed: v4` for every trusted country; ADR 0002 amendment; load the signed-off §11 rows | — |
| 6. Full run | current FUA, history LAU and FUA on v4 (399 more runs, about 3 h on the M5 rate); Berlin LAU runs attribute Bezirke; clean tree; DB backed up first | — |
| 7. Explain | `timeseries --write`, `reconcile --write`. Explanations whose flag or gap no longer fires are removed. New or changed ones are written in full prose against run rows and way-level evidence (M5 decision 2), with the A/B moves named | — |
| 8. Report | charts, maps, methodology EN and DE, `report change` for the default window; all four checks; serve; screenshot every page at 1280 and 390 px; the Berlin and Bezirk numbers spot-checked against the CLI; an M6 entry in HANDOVER §9 and the "Latest delivered" line in `CLAUDE.md`; `docs/superpowers/rulings-m6.md`; final whole-branch review | final review |

## 8. Testing

- **Offline and fast, as before.** Real data appears only in phases 3–8.
- **v4:**
  - every §3.2 row;
  - decision 9's implicit-access cases;
  - each MTB key, and `mtb=no` not firing.
  - Red-proofing: v3 on the same fixture gives the v3 tier.
  - The cycleway ↔ path retag invariance: the same access tags on both highway values give the
    same tier.
- **Subareas:**
  - a synthetic city split into two subareas: the sums equal the city within the tolerance, and a
    breach fails the run;
  - dual-carriageway halving per subarea;
  - the union and overlap checks raise.
  - A city without `subareas` gets no rows.
- **Migration:** v7 → v8 copy, an interrupted step leaving v7, and `subarea_sha` null on old runs.
- **Change map:**
  - fixture snapshot pairs for each category, including a redrawn split way;
  - the totals mismatch refuses to write;
  - a non-done run is refused.
- **Surfaces:**
  - the Berlin page renders the Bezirk section on a fixture DB;
  - the CSV has provenance columns;
  - an untrusted city shows no subareas.
- **§11:** loaded rows round-trip with scope and basis, and a row without `source_url` is refused
  by the loader.

## 9. Out of scope

- The Vorrangnetz/Radverkehrsnetz overlay.
- LOR Planungsräume, or any finer unit.
- Bezirk population and per-100k per Bezirk.
- Subareas for cities other than Berlin. The mechanism is generic; only Berlin is configured.
- Public hosting (HANDOVER §12 Q4).
- New cities, Copenhagenize figures, new official figures beyond §11, an ohsome cross-check and a
  lane-length view.
- Changes to road-side track rules or the QECIO halving rule.
