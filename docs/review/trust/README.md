# Trust review index (M5)

This index records the golden sign-off. Each new country has:

- a golden page, where every sample carries a verdict marked "confirmed:". The user accepted the
  verdicts for NL, ES, SE, NO, FI, HU, CZ and SI on 2026-10-03 (Task 13c) and for SK on 2026-10-03
  (Task 14), so every fixture carries `confirmed: true`. Ways whose verdict needs classifier v3
  carry `min_classifier: v3`: the three CZ `soft_lane` ways, the two SK and one NO
  `cycleway[:side]=advisory` ways. All of them match v3, the report classifier since Task 14;
- a diagnostics file `<CC>.md`, holding the generated block and the hand-written breach notes.

**Thresholds** (`config/trust.yaml`, from the pilots, ×1.25, 3 places):

| threshold | value |
|---|---|
| unrecognised | 0.1 % |
| excluded | 60.7 % |
| B of A+B | 78.4 % |
| boundary diff | 5 % |

The unrecognised threshold is a ruling. The pilots' maximum ×1.25 is 0.0045 %, which rounds to 0. The schema refuses 0, so 0.1 % is used.

The diagnostics come from the current LAU runs on classifier v3, config 0237b5b5c432, OSM 2026-10-02T20:21:34Z for all 21 cities (runs 270–290, Task 14, 2026-10-03). The pilots' earlier v2 runs 147–151 used OSM 2026-09-30, so their figures moved slightly with OSM edits; on the same snapshot v3 changes km only in Prague (+58.8 km D advisory), Bratislava (+0.56 km) and Oslo (+0.44 km).

## New countries (trusted 2026-10-03, Task 14)

| country | golden page | samples | city (run) | unrecognised | excluded | B of A+B | boundary diff | breaches |
|---|---|---|---|---|---|---|---|---|
| NL | [NL_golden.md](NL_golden.md) | 12 | amsterdam (275) | 0.00% | 18.5% | 2.4% | 0.12% | none |
| | | | utrecht (276) | 0.00% | 25.0% | 5.2% | 0.54% | none |
| ES | [ES_golden.md](ES_golden.md) | 11 | madrid (277) | 0.00% | 16.2% | 10.9% | 0.08% | none |
| | | | barcelona (278) | 0.00% | 25.0% | 4.6% | 2.29% | none |
| SE | [SE_golden.md](SE_golden.md) | 12 | stockholm (279) | 0.08% | 15.4% | 23.3% | 2.12% | none |
| NO | [NO_golden.md](NO_golden.md) | 11 | oslo (280) | 0.00% | 9.3% | 82.1% | 5.31% | b_share_of_ab, boundary_diff_pct ([notes](NO.md)) |
| FI | [FI_golden.md](FI_golden.md) | 10 | helsinki (281) | 0.00% | 26.3% | 53.6% | 69.09% | boundary_diff_pct ([note](FI.md)) |
| HU | [HU_golden.md](HU_golden.md) | 10 | budapest (287) | 0.00% | 37.9% | 29.1% | 0.04% | none |
| CZ | [CZ_golden.md](CZ_golden.md) | 12 | prague (288) | 0.00% | 19.8% | 63.8% | 0.13% | none |
| SK | [SK_golden.md](SK_golden.md) | 13 | bratislava (290) | 0.01% | 10.7% | 34.2% | 0.09% | none |
| SI | [SI_golden.md](SI_golden.md) | 10 | ljubljana (289) | 0.00% | 12.0% | 81.3% | 0.10% | b_share_of_ab ([note](SI.md)) |

Oslo and Helsinki are back on GISCO LAU (Task 13c, the ADR 0004 default): the area the OSM relation adds is Oslofjord water and sea area. Their `boundary_diff_pct` notes give the measured numbers. Bratislava's admin boundary is the union of its 17 borough LAU (367.88 km² against OSM relation 1702499, 367.53 km²).

**Samples per page.** Each page has:

- the longest way-side of the country's six highest-km rules;
- up to three of the top unmatched tag signatures;
- the `--extra-way` picks.

The extra ways are the longest way-side of country-relevant rules that the six-rule draw missed: cycle streets, advisory lanes, bus lanes, side tracks, shared paths and shoulders. Their ids were taken from the snapshot classification, not typed.

**Verdicts.** Every sample is "ok" except the ways v2 left unrecognised: three CZ `soft_lane` ways and two SK `cycleway[:side]=advisory` ways (should be D advisory; v3 gives it), and one Oslo way whose right side is `cycleway:right=advisory` (v3 gives D advisory). The SK way with `cycleway:right=shared_busway` (a misspelling of `share_busway`) stays without output, by decision: it is an OSM mistag.

## Pilot-country checks (FR, PL; DE, AT, DK)

| country | city (run) | unrecognised | excluded | B of A+B | boundary diff | breaches |
|---|---|---|---|---|---|---|
| DE | berlin (270) | 0.00% | 48.6% | 26.1% | 0.19% | none |
| FR | paris (271) | 0.00% | 41.3% | 6.0% | 0.03% | none |
| FR | lyon (282) | 0.01% | 32.9% | 15.2% | 0.12% | none |
| FR | strasbourg (283) | 0.00% | 29.9% | 29.3% | 0.12% | none |
| FR | bordeaux (284) | 0.04% | 37.5% | 18.0% | 0.99% | none |
| AT | vienna (272) | 0.00% | 37.1% | 30.2% | 0.18% | none |
| DK | copenhagen (273) | 0.00% | 42.3% | 14.4% | 0.43% | none |
| PL | wroclaw (274) | 0.00% | 8.8% | 62.8% | 0.38% | none |
| PL | warsaw (285) | 0.01% | 23.1% | 33.4% | 0.05% | none |
| PL | krakow (286) | 0.00% | 33.1% | 78.4% | 0.01% | b_share_of_ab, 0.7843 against 0.784 ([note](PL.md)) |

## v3 proposals

Decided 2026-10-03 and shipped as `config/classifier/v3.yaml` (Task 14; see [v3-proposals.md](v3-proposals.md)):

1. `cycleway[:side]=soft_lane` → D advisory (`D_soft_lane`): Prague +58.8 km in D.
2. `cycleway[:side]=advisory` → D advisory (`D_advisory`): Bratislava +0.56 km, Oslo +0.44 km.

No other city's km change, pilots included, and the headline (A+B) doesn't move. The other small mistag values stay unrecognised.

Map data © OpenStreetMap contributors, ODbL 1.0
