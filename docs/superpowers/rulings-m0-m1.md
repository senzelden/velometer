# M0/M1 execution rulings

Decisions made while building M0+M1 (format: ruling — why — cost if wrong). R18 is superseded by R25 (user decision). ADRs and the spec §9 "As built" are authoritative where they differ.

- Ruling R1: work on branch feat/m0-m1 in place, no worktree — repo is brand new with nothing else in flight — cost if wrong: none (branch is isolated).
- Ruling R2: in T7, the `from pathlib import Path` for test_cli.py goes at file top, not mid-file — ruff E402 gate — cost if wrong: none.
- Ruling R3: subagent Bash calls must use dangerouslyDisableSandbox (bubblewrap nested-userns fails on every command here) — cost if wrong: commands run unsandboxed, still scoped to repo work.
- Ruling R4: Copenhagen = relation 2192363 (Københavns Kommune, excl. Frederiksberg) — municipality matches LAU/admin-default ADR 0004 and Clean Cities' "municipality with the same name" — cost if wrong: one id swap in cities.yaml before M2.
- Ruling R5: quote "no"/"yes" in v1.yaml value_lists (implementer deviation accepted) — PyYAML bools fail pydantic list[str] — cost: none.
- Ruling R6: ruff must exclude docs/ (ruff format rewrote python blocks in the plan markdown); added as finding to Task 1 fix round — cost if wrong: none.
- Ruling R7 (Task 4, plan-mandated finding): apply ;-split tag semantics to oneway and bicycle_road/cyclestreet/cycle_street checks in explode; keep whole-value test for opposite* on cycleway value — mixed values like "lane;opposite_lane" are ambiguous/rare and classify still matches parts — cost if wrong: rare mixed legacy values lose contraflow flag.
- Ruling R8: cycleway:both=opposite_<x> applies to both sides with contraflow (brief literal) — legacy/rare — cost if wrong: small overcount on rare legacy tagging.
- Ruling R9 (Task 5 #1): tier C judges only the TRAFFIC-side separation: explode emits `cycleway:separation:traffic` = undirected `<prefix>:separation` ∪ `<prefix>:separation:left` (for right side) / `:separation:right` (for left side), at first level having any; C_lane_physical matches that key — ADR 0002 C means buffer between lane and traffic — cost if wrong: lanes with only undirected/curb tagging shift C→D.
- Ruling R10 (Task 5 #2): new rule B_track_shared (`cycleway: track` + `cycleway:segregated: "no"`) before A_track_side — ADR 0002 says both tagging styles must give the same numbers and B = shared foot/cycle path — cost if wrong: German side-tagged shared paths move A→B (headline A+B unchanged; split changes).
- Ruling R11 (Task 5 #4): mutation tests compare (way, side, tier, subtype), not rule_id — rule_id comparison is near-tautological — cost: none.
- Ruling R12 (Task 5 minors, folded into fix): X_private also covers access=no (unless bicycle allowed); standalone `construction=yes` excluded; `highway=path + bicycle=designated + foot=no` → A (A_path_cycle_only); explode drops sidewalk_bicycle when sidewalk:<side>/both/plain = separate (avoids double count); is_bidirectional uses ;-split any-part — cost if wrong: small tier shifts on rare tags, each pinned by a fixture.
- Ruling R13 (Task 6 #1, plan-mandated): dual-carriageway direction test uses LOCAL bearings (w's bearing at w.project(partner midpoint) vs partner's bearing at its midpoint, ±10 m along line) instead of whole-way chords — split/curved carriageways must still pair — cost if wrong: slight extra compute.
- Ruling R14 (Task 6 #2, plan-mandated): dual_carriageway/oneway/name/ref use ;-split any-part semantics; groups keyed per part — global constraint — cost: none.
- Ruling R15 (Task 7): _public_roads uses ;-split any-part for access/area — global constraint — cost: none.
- Ruling R16 (I1): reject non-projected EPSG in Projector (shared validator with config.py) and CLI exits 1 — CLAUDE.md "lengths only in projected EPSG" — cost: none.
- Ruling R17 (I2, amends plan Task 8 group list): add golden groups for side tracks, standalone cycleways (foot absent / foot=designated), separate tracks along Karl-Marx-Allee & Unter den Eichen, sidewalk:right:bicycle=designated; one Overpass re-fetch — sign-off must cover headline numerator — cost: one extra fetch, review sheet grows.
- Ruling R18 (I3.1, PROVISIONAL, contradicts spec §4 — ask user): keep plain cycleway=<v> on oneway road → right side only (oneway=-1 → left side; junction=roundabout implies oneway) — matches OSM practice; spec said both sides — cost if wrong: oneway streets with plain cycleway tag undercounted by one side. Spec gets an "open question" note, not a silent amendment.
- Ruling R19 (I3.2): carry road:construction/road:proposed and add X_road_construction to v1 — spec §4 mandates carry; v1 unreleased/unsigned, so editing v1 instead of v2 — cost: none.
- Ruling R20 (I3.3): sidewalk_bicycle always carried, conflict resolved by rule order — behaviour-equivalent to spec, pinned by test — recorded in spec as-built note.
- Ruling R21 (I4): remove personal email from fetch User-Agent; optional VELOMETER_CONTACT env appended if set — user's context forbids sending email to unrelated services — note: Task 8 fetch already sent it to overpass-api.de; commit 9b4653a contains it (unpushed; history rewrite only if user asks).
- Ruling R22 (M2): access=no roads leave all denominators (mirror R12), ADR 0003 updated — cost: tiny denominator change.
- Ruling R23 (M10): parking-protected (traffic_mode=parking) stays D in v1 — Dennis decision at sign-off.
- Ruling R24: proposed=* on built ways does NOT exclude (road or standalone); only highway=construction|proposed, construction=yes, cycleway:<side>=construction|proposed — the fix dispatch's road:proposed rule excluded existing roads with planned upgrades — commit 518b568
- Ruling R25 (USER DECISION, supersedes R18): plain cycleway on oneway = tunable classifier parameter plain_cycleway_on_oneway (traffic_side default | both_sides), CLI override, per-run sensitivity report (MeasureResult.plain_oneway) — commit d526add. Default traffic_side chosen by me (user asked for tunability, not a default).

## Parked for M2

- Parked → M2 plan: user_version guard, connection closing, highway pre-filter in read.py, dedupe partner pre-filter (M12), FK/unique keys.
- Final re-review: all addressed (item 16 data pending Overpass). Parked minors: _closed_to_public KeyError on missing bicycle_allowed list; access=private denominator has no bicycle override (ADR 0003 documented); fetch script lacks --help. Final review: complete.
