# Classifier v4 impact (M6 Task 14)

v3 against v4 on the same OSM extract (2026-10-03T20:20:50Z), LAU boundary, all 21 cities. Lengths
are mapped km per side in each city's EPSG (ADR 0006). The headline is `ours_headline` (A+B km
per 100 km of main roads excl. motorways), ranked 1 = highest.

**Note (2026-10-05).** The run ids on this page are partly from a scratch copy of the DB: the v3
column's runs 714–734 and Berlin's v4 run 713 below are scratch-DB ids (in `velometer.sqlite`,
714–734 are the v4 current FUA runs). The report's real v4 current LAU runs are 693–697, 713 and
1113–1127; 698–712 are superseded (failed, "superseded by 1113–1127", see ADR 0005). The user
took the decision this page asked for on 2026-10-05: the v4 impact is accepted, and Berlin's LAU
edge outside the 12 Bezirke became an explicit remainder row (`docs/superpowers/rulings-m6.md`,
"User decisions"). The table and text below are unchanged.

**How this was made.**
- v4 runs 693–712 are the real v4 runs in `velometer.sqlite`.
- The real Berlin v4 run (692) failed the Bezirk sum check (see "Berlin" below). Berlin's v4
  numbers come from run 713 in a scratch copy of the DB. A city total does not depend on the
  Bezirke.
- The v3 column re-runs v3 on the same extract, as runs 714–734 in that scratch copy. This
  isolates the classifier change from one day of OSM edits. The v3 report runs 270–290 are on the
  2026-10-02 extract.
- X_mtb_trail km by highway value classify each city's LAU snapshot with v4 and clip it to the
  LAU. Berlin's sum, 124.84 km, matches the run's `excluded/mtb` row.
- The scratch scripts are not committed.

<!-- v4-impact:start -->

| city | v3 run | v4 run | A v3 | A v4 | ΔA | B v3 | B v4 | ΔB | A+B v3 | A+B v4 | Δ A+B | headline v3 | headline v4 | rank v3 → v4 | X_mtb_trail km (path / footway / cycleway) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| berlin | 714 | 713 | 1,151.3 | 1,275.4 | +124.0 | 406.7 | 275.3 | -131.4 | 1,558.0 | 1,550.7 | -7.3 | 109.6 | 109.1 | 7 → 7 | 117.7 / 7.2 / 0.0 |
| paris | 715 | 693 | 335.2 | 332.5 | -2.7 | 21.4 | 24.1 | +2.7 | 356.6 | 356.6 | +0.0 | 63.1 | 63.1 | 14 → 14 | 0.2 / 0.0 / 0.0 |
| vienna | 716 | 694 | 474.7 | 314.0 | -160.8 | 205.1 | 351.7 | +146.6 | 679.8 | 665.7 | -14.2 | 91.0 | 89.1 | 9 → 9 | 56.7 / 2.7 / 0.3 |
| copenhagen | 717 | 695 | 498.5 | 492.7 | -5.8 | 83.9 | 89.1 | +5.2 | 582.4 | 581.8 | -0.5 | 238.1 | 237.9 | 3 → 3 | 4.9 / 0.0 / 0.5 |
| wroclaw | 718 | 696 | 148.4 | 258.1 | +109.7 | 250.4 | 140.7 | -109.7 | 398.8 | 398.8 | +0.0 | 95.3 | 95.3 | 8 → 8 | 9.5 / 0.0 / 0.0 |
| amsterdam | 719 | 697 | 841.3 | 650.4 | -190.9 | 20.3 | 211.3 | +190.9 | 861.6 | 861.6 | +0.0 | 203.0 | 203.0 | 4 → 4 | 7.3 / 0.0 / 0.0 |
| utrecht | 720 | 698 | 343.8 | 316.9 | -27.0 | 19.0 | 43.6 | +24.6 | 362.8 | 360.5 | -2.3 | 194.8 | 193.6 | 5 → 5 | 2.6 / 0.0 / 0.1 |
| madrid | 721 | 699 | 318.3 | 273.3 | -45.0 | 39.1 | 79.7 | +40.6 | 357.4 | 353.0 | -4.4 | 43.1 | 42.5 | 18 → 18 | 104.7 / 4.5 / 0.1 |
| barcelona | 722 | 700 | 232.4 | 231.5 | -0.9 | 11.2 | 12.2 | +0.9 | 243.6 | 243.6 | -0.0 | 55.1 | 55.1 | 16 → 16 | 43.1 / 0.0 / 0.0 |
| stockholm | 723 | 701 | 769.1 | 414.7 | -354.4 | 232.2 | 576.6 | +344.3 | 1,001.3 | 991.3 | -10.0 | 263.7 | 261.0 | 1 → 2 | 32.8 / 3.7 / 1.2 |
| oslo | 724 | 702 | 61.9 | 59.8 | -2.1 | 284.1 | 281.6 | -2.6 | 346.1 | 341.4 | -4.7 | 71.8 | 70.8 | 13 → 13 | 868.6 / 6.5 / 4.6 |
| helsinki | 725 | 703 | 595.4 | 336.0 | -259.4 | 688.4 | 943.2 | +254.8 | 1,283.8 | 1,279.2 | -4.6 | 263.2 | 262.3 | 2 → 1 | 514.6 / 28.6 / 4.6 |
| lyon | 726 | 704 | 95.8 | 93.1 | -2.7 | 17.2 | 19.9 | +2.7 | 113.0 | 113.0 | +0.0 | 52.3 | 52.3 | 17 → 17 | 0.6 / 1.6 / 0.0 |
| strasbourg | 727 | 705 | 170.5 | 172.0 | +1.5 | 70.6 | 69.1 | -1.5 | 241.1 | 241.1 | -0.0 | 136.1 | 136.1 | 6 → 6 | 1.4 / 0.0 / 0.0 |
| bordeaux | 728 | 706 | 53.7 | 48.7 | -5.0 | 11.7 | 16.7 | +5.0 | 65.4 | 65.4 | +0.0 | 40.3 | 40.3 | 19 → 19 | 0.0 / 0.0 / 0.0 |
| warsaw | 729 | 707 | 508.5 | 598.0 | +89.4 | 255.1 | 164.7 | -90.4 | 763.6 | 762.7 | -0.9 | 82.4 | 82.3 | 10 → 10 | 24.4 / 0.0 / 0.2 |
| krakow | 730 | 708 | 65.0 | 191.6 | +126.6 | 236.0 | 104.5 | -131.5 | 301.0 | 296.1 | -4.9 | 73.8 | 72.6 | 12 → 12 | 24.1 / 0.0 / 0.9 |
| budapest | 731 | 709 | 164.6 | 162.1 | -2.5 | 67.6 | 69.4 | +1.8 | 232.2 | 231.5 | -0.7 | 22.4 | 22.3 | 21 → 21 | 40.1 / 0.0 / 0.0 |
| prague | 732 | 710 | 106.7 | 44.7 | -62.0 | 188.3 | 244.5 | +56.2 | 295.0 | 289.3 | -5.8 | 30.2 | 29.6 | 20 → 20 | 165.2 / 2.0 / 2.1 |
| ljubljana | 733 | 711 | 46.4 | 208.7 | +162.3 | 202.2 | 36.3 | -165.9 | 248.6 | 245.0 | -3.5 | 74.6 | 73.5 | 11 → 11 | 24.9 / 1.1 / 0.0 |
| bratislava | 734 | 712 | 117.8 | 89.7 | -28.0 | 61.6 | 82.4 | +20.8 | 179.3 | 172.1 | -7.2 | 61.2 | 58.7 | 15 → 15 | 33.8 / 0.0 / 0.0 |

<!-- v4-impact:end -->

**Largest movers.**

- **The headline barely moves.** Every city is within 2.7 points: Stockholm 263.7 → 261.0,
  Bratislava 61.2 → 58.7, Vienna 91.0 → 89.1. The only rank change is the top pair.
  Helsinki (262.3) now leads Stockholm (261.0); under v3 Stockholm led by 0.5.
- **A and B swap km in both directions.** The unified facility rule decides by facility, not by
  highway value.
  - **Explicit foot access, A → B.** Cycleways where pedestrians are explicitly allowed now rate
    `B_shared`: Stockholm A −354 / B +344 km, Helsinki −259 / +255, Amsterdam −191 / +191,
    Vienna −161 / +147, Prague −62 / +56.
  - **Segregated sidepaths, B → A.** Segregated footway or path sidepaths now rate
    `A_segregated`: Ljubljana A +162 / B −166 km, Krakow +127 / −132, Berlin +124 / −131,
    Wroclaw +110 / −110, Warsaw +89 / −90.
- **The MTB exclusion removes many km, but few were counted.** Excluded X_mtb_trail km:
  - Oslo 880, Helsinki 548, Prague 169, Berlin 125, Madrid 109.
  - A+B falls by at most 14.2 km (Vienna). Most explicitly MTB-tagged trails were not A or B
    under v3 either.

**Berlin, Bezirk sums.** The 12 Bezirke leave 7.30 km² of the generalised LAU uncovered. In
v4 run 713 the Bezirk sums fall short of the city by more than the spec's 0.5 % in six rows:
- B per_side by 1.16 % (3.03 of 262.41 km);
- B qecio_weighted by 1.26 %;
- excluded/mtb by 1.33 % and 1.38 %;
- excluded/bicycle_no by 0.55 % (both bases).

A is short by 0.006 %, and every road-class denominator by 0.36 % or less. This needs a decision
before Task 16.

Map data © OpenStreetMap contributors, ODbL 1.0
