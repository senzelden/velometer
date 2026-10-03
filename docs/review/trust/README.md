# Trust review index (M5)

This index is for the golden sign-off. Each new country has:

- a golden page, where every sample carries a verdict marked "proposed:". Nothing is confirmed
  yet; `confirmed: true` is set only after your sign-off;
- a diagnostics file `<CC>.md`, holding the generated block and the hand-written breach notes.

**Thresholds** (`config/trust.yaml`, from the pilots, ×1.25, 3 places):

| threshold | value |
|---|---|
| unrecognised | 0.1 % |
| excluded | 60.7 % |
| B of A+B | 78.4 % |
| boundary diff | 5 % |

The unrecognised threshold is a ruling. The pilots' maximum ×1.25 is 0.0045 %, which rounds to 0. The schema refuses 0, so 0.1 % is used.

The diagnostics come from the current LAU runs on classifier v2, config 7416d3c8c103, OSM 2026-10-02 for the new cities.

## New countries (pending)

| country | golden page | samples | city (run) | unrecognised | excluded | B of A+B | boundary diff | breaches |
|---|---|---|---|---|---|---|---|---|
| NL | [NL_golden.md](NL_golden.md) | 12 | amsterdam (217) | 0.00% | 18.5% | 2.4% | 0.12% | none |
| | | | utrecht (218) | 0.00% | 25.0% | 5.2% | 0.54% | none |
| ES | [ES_golden.md](ES_golden.md) | 11 | madrid (219) | 0.00% | 16.2% | 10.9% | 0.08% | none |
| | | | barcelona (220) | 0.00% | 25.0% | 4.6% | 2.29% | none |
| SE | [SE_golden.md](SE_golden.md) | 12 | stockholm (221) | 0.08% | 15.4% | 23.3% | 2.12% | none |
| NO | [NO_golden.md](NO_golden.md) | 11 | oslo (222) | 0.01% | 9.4% | 82.2% | 0.00%* | b_share_of_ab ([note](NO.md)) |
| FI | [FI_golden.md](FI_golden.md) | 10 | helsinki (232) | 0.00% | 26.3% | 53.2% | 0.00%* | none |
| HU | [HU_golden.md](HU_golden.md) | 10 | budapest (238) | 0.00% | 37.9% | 29.1% | 0.04% | none |
| CZ | [CZ_golden.md](CZ_golden.md) | 12 | prague (239) | 0.77% | 19.8% | 63.8% | 0.13% | unrecognised_share ([note](CZ.md)) |
| SK | none | 0 | none | | | | | not onboarded: Bratislava has no LAU 2024 municipality |
| SI | [SI_golden.md](SI_golden.md) | 10 | ljubljana (240) | 0.00% | 12.0% | 81.3% | 0.10% | b_share_of_ab ([note](SI.md)) |

\* Oslo and Helsinki use the OSM relation as their admin boundary, so their boundary diff is 0. Against GISCO LAU it was:

- Oslo: 5.31 %, LAU 454.98 km² against OSM 480.48 km². The difference is Oslofjord water.
- Helsinki: 69.1 %, LAU 221.69 km² against OSM 717.28 km². The difference is sea area.

See the `cities.yaml` header.

**Samples per page.** Each page has:

- the longest way-side of the country's six highest-km rules;
- up to three of the top unmatched tag signatures;
- the `--extra-way` picks.

The extra ways are the longest way-side of country-relevant rules that the six-rule draw missed: cycle streets, advisory lanes, bus lanes, side tracks, shared paths and shoulders. Their ids were taken from the snapshot classification, not typed.

**Proposed verdicts.** Every sample is "ok" except three CZ `soft_lane` ways, where the verdict is "wrong: should be D advisory".

## Pilot-country checks (FR, PL; DE, AT, DK)

| country | city (run) | unrecognised | excluded | B of A+B | boundary diff | breaches |
|---|---|---|---|---|---|---|
| DE | berlin (147) | 0.00% | 48.6% | 26.1% | 0.19% | none |
| FR | paris (148) | 0.00% | 41.3% | 6.0% | 0.03% | none |
| FR | lyon (233) | 0.01% | 32.9% | 15.2% | 0.12% | none |
| FR | strasbourg (234) | 0.00% | 29.9% | 29.3% | 0.12% | none |
| FR | bordeaux (235) | 0.04% | 37.5% | 18.0% | 0.99% | none |
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
