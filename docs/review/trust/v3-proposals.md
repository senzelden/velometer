# Classifier v3 proposals (M5 trust gate)

Proposed on 2026-10-03 from the M5 diagnostics and golden samples, for your decision at the
golden sign-off. Nothing here is in `config/classifier/` yet. A rule change becomes `v3.yaml`
(ADR 0005), and only in Task 14.

Effects were measured with a scratch copy of `config/classifier/v2.yaml`, written to `$TMPDIR`,
with only the rule below added. Each city's current LAU snapshot was re-measured with v2 and with
the scratch copy. The pilots are Berlin 147, Paris 148, Vienna 149, Copenhagen 150 and Wrocław 151.
The 15 new cities are runs 217–222 and 232–240. Km are per-side mapped km (ADR 0006).

## Proposal 1: `cycleway=soft_lane` is an advisory lane (tier D)

- **Rule.** A new road-side rule `D_soft_lane`: tier D, subtype `advisory`, attrs
  `{advisory: true}`, `match: {cycleway: soft_lane}`. It sits before `D_lane`, so it is the
  same tier and subtype as `D_lane_advisory`.
- **Tag pattern.** `cycleway=soft_lane`, `cycleway:left|right|both=soft_lane` (exploded to the
  side as usual).
- **Why.** `soft_lane` comes from the 2014 proposal
  (https://wiki.openstreetmap.org/wiki/Proposed_features/cycleway=soft_lane), which was rejected.
  It means a lane marked with a dashed line and bicycle pictograms, which motor vehicles may
  cross. That is what `cycleway=lane` + `cycleway:lane=advisory` describes today (wiki
  Key:cycleway:lane). The Czech wiki (Cs:Key:cycleway) points to the same proposal for the
  "soft separation" lane. Under v2 these sides match no rule: they count as unrecognised and in no
  tier.
- **Countries and km affected.** CZ only: Prague gains +58.8 km in D, and the same 58.8 km leaves
  unrecognised (Prague's unrecognised share falls from 0.77 % to about 0 %). Every other city
  shows 0.0 km change.
- **Pilots' km.** No change in any tier for Berlin, Paris, Vienna, Copenhagen or Wrocław.
- **Presets.** The headline and Clean Cities presets count A+B, so they don't move. The QECIO
  preset counts A–D, so Prague's QECIO-method numerator rises by 58.8 km.
- **Golden evidence.** CZ ways 135706932, 762313241 and 821229572 are proposed "wrong: should be
  D advisory".

## Considered, not proposed

These are mistagged or undocumented values seen in the samples or the top unmatched signatures.
Each is under 2.2 km per city. A rule for them would encode one mapper's mistake, so v2 keeps
them unrecognised (not counted):

| value | city | km | likely meaning |
|---|---|---|---|
| `cycleway=path` | Stockholm | 2.13 | separately mapped path (`separate`) |
| `cycleway:left=exclusive` | Stockholm | 0.40 | `lane` + `lane=exclusive` (contraflow) |
| `cycleway=segregated` | Stockholm | 0.32 | unknown |
| `cycleway:right=advisory` | Oslo | 0.44 | `lane` + `lane=advisory` |
| `cycleway=use` | Amsterdam | 0.13 | `use_sidepath` |
| `cycleway=pictogram` | Barcelona | 0.07 | `shared_lane` + `lane=pictogram` (would be excluded anyway) |
| `cycleway:left=right` | Amsterdam | 0.01 | mistag |

Two breaches need no rule change, because the classifier reads the tags correctly:

- the B share of A+B in Oslo (gang- og sykkelvei);
- the B share of A+B in Ljubljana and Kraków (segregated foot/cycle paths).

See the `### <city>/<metric>` notes in `NO.md`, `SI.md` and `PL.md`.

Map data © OpenStreetMap contributors, ODbL 1.0
