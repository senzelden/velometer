# Trust review index (M5)

This index is for the golden sign-off. Each new country has:

- a golden page, where every sample carries a verdict marked "proposed:". The user accepted every
  proposed verdict for NL, ES, SE, NO, FI, HU, CZ and SI on 2026-10-03 (Task 13c), so their
  fixtures carry `confirmed: true`. The three CZ `soft_lane` ways expect classifier v3
  (`min_classifier: v3`) and are compared from Task 14 on. SK (Bratislava, Task 13c) is still
  proposed only;
- a diagnostics file `<CC>.md`, holding the generated block and the hand-written breach notes.

**Thresholds** (`config/trust.yaml`, from the pilots, ×1.25, 3 places):

| threshold | value |
|---|---|
| unrecognised | 0.1 % |
| excluded | 60.7 % |
| B of A+B | 78.4 % |
| boundary diff | 5 % |

The unrecognised threshold is a ruling. The pilots' maximum ×1.25 is 0.0045 %, which rounds to 0. The schema refuses 0, so 0.1 % is used.

The diagnostics come from the current LAU runs on classifier v2, config 7416d3c8c103, OSM 2026-10-02 for the new cities. Task 13c re-ran Oslo and Helsinki on GISCO LAU, added Bratislava, and re-ran Madrid, Barcelona, Lyon, Strasbourg and Bordeaux so their runs carry the cited population (unchanged km).

## New countries (pending)

| country | golden page | samples | city (run) | unrecognised | excluded | B of A+B | boundary diff | breaches |
|---|---|---|---|---|---|---|---|---|
| NL | [NL_golden.md](NL_golden.md) | 12 | amsterdam (217) | 0.00% | 18.5% | 2.4% | 0.12% | none |
| | | | utrecht (218) | 0.00% | 25.0% | 5.2% | 0.54% | none |
| ES | [ES_golden.md](ES_golden.md) | 11 | madrid (244) | 0.00% | 16.2% | 10.9% | 0.08% | none |
| | | | barcelona (245) | 0.00% | 25.0% | 4.6% | 2.29% | none |
| SE | [SE_golden.md](SE_golden.md) | 12 | stockholm (221) | 0.08% | 15.4% | 23.3% | 2.12% | none |
| NO | [NO_golden.md](NO_golden.md) | 11 | oslo (241) | 0.01% | 9.3% | 82.1% | 5.31% | b_share_of_ab, boundary_diff_pct ([notes](NO.md)) |
| FI | [FI_golden.md](FI_golden.md) | 10 | helsinki (242) | 0.00% | 26.3% | 53.6% | 69.09% | boundary_diff_pct ([note](FI.md)) |
| HU | [HU_golden.md](HU_golden.md) | 10 | budapest (238) | 0.00% | 37.9% | 29.1% | 0.04% | none |
| CZ | [CZ_golden.md](CZ_golden.md) | 12 | prague (239) | 0.77% | 19.8% | 63.8% | 0.13% | unrecognised_share ([note](CZ.md)) |
| SK | [SK_golden.md](SK_golden.md) | 13 | bratislava (243) | 0.02% | 10.7% | 34.2% | 0.09% | none |
| SI | [SI_golden.md](SI_golden.md) | 10 | ljubljana (240) | 0.00% | 12.0% | 81.3% | 0.10% | b_share_of_ab ([note](SI.md)) |

Oslo and Helsinki are back on GISCO LAU (Task 13c, the ADR 0004 default): the area the OSM relation adds is Oslofjord water and sea area. Their `boundary_diff_pct` notes give the measured numbers. Bratislava's admin boundary is the union of its 17 borough LAU (367.88 km² against OSM relation 1702499, 367.53 km²).

**Samples per page.** Each page has:

- the longest way-side of the country's six highest-km rules;
- up to three of the top unmatched tag signatures;
- the `--extra-way` picks.

The extra ways are the longest way-side of country-relevant rules that the six-rule draw missed: cycle streets, advisory lanes, bus lanes, side tracks, shared paths and shoulders. Their ids were taken from the snapshot classification, not typed.

**Verdicts.** Every sample is "ok" except three CZ `soft_lane` ways, where the verdict is "wrong: should be D advisory" (accepted, v3). SK (proposed, awaiting your decision): 10 of 13 are "ok"; three are "wrong" on mistagged values that v2 leaves unrecognised: `cycleway:right=shared_busway` (should be E, a misspelling of `share_busway`) and two `cycleway[:side]=advisory` (should be D advisory, the same value as Oslo's 0.44 km).

## Pilot-country checks (FR, PL; DE, AT, DK)

| country | city (run) | unrecognised | excluded | B of A+B | boundary diff | breaches |
|---|---|---|---|---|---|---|
| DE | berlin (147) | 0.00% | 48.6% | 26.1% | 0.19% | none |
| FR | paris (148) | 0.00% | 41.3% | 6.0% | 0.03% | none |
| FR | lyon (246) | 0.01% | 32.9% | 15.2% | 0.12% | none |
| FR | strasbourg (247) | 0.00% | 29.9% | 29.3% | 0.12% | none |
| FR | bordeaux (248) | 0.04% | 37.5% | 18.0% | 0.99% | none |
| AT | vienna (149) | 0.00% | 37.0% | 30.2% | 0.18% | none |
| DK | copenhagen (150) | 0.00% | 42.3% | 14.4% | 0.43% | none |
| PL | wroclaw (151) | 0.00% | 8.8% | 62.7% | 0.38% | none |
| PL | warsaw (236) | 0.01% | 23.1% | 33.4% | 0.05% | none |
| PL | krakow (237) | 0.00% | 33.1% | 78.4% | 0.01% | b_share_of_ab, 0.7843 against 0.784 ([note](PL.md)) |

## v3 proposals

[v3-proposals.md](v3-proposals.md) has one proposal:

1. `cycleway[:side]=soft_lane` becomes tier D advisory. It affects only CZ: Prague gains 58.8 km in D. The pilots and the headline don't change.

Seven small mistag values (all under 2.2 km) were considered and not proposed.

Map data © OpenStreetMap contributors, ODbL 1.0
