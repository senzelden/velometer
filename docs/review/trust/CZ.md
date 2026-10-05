# Trust review: CZ

Hand-written notes go here. Only the generated block below is replaced when `velometer trust diagnose` runs again; everything outside it is kept.

## Notes

### prague/unrecognised_share

Prague's unrecognised share is 0.77 % of 7645.0 cycling km, i.e. 58.8 km (run 239), against a
limit of 0.1 %. All of it is `cycleway[:right|:both]=soft_lane`: every one of the top
unmatched signatures is soft_lane, and the scratch rule below recognises the full 58.8 km. soft_lane is the 2014 proposal (rejected) for a dashed lane with pictograms, i.e. an
advisory lane (`cycleway=lane` + `cycleway:lane=advisory`; OSM wiki Key:cycleway:lane), the Czech
ochranný jízdní pruh. Golden ways 135706932, 762313241 and 821229572 show it. A scratch
classifier with one extra rule (`cycleway=soft_lane` -> D advisory) moves 58.8 km per side in
Prague from unrecognised to D and changes no other city's km, pilots included
(docs/review/trust/v3-proposals.md, proposal 1). Tier D is outside the protected headline, so
the headline does not move; the QECIO-method preset (lanes included) does.

Resolved by classifier v3 (Task 14, user decision 2026-10-03): rule `D_soft_lane` recognises the
58.8 km as D advisory. On run 288 Prague's unrecognised share is 0.0 % and it is within every
limit; this note stays as the record.

### prague/b_share_of_ab

Prague's B share of A+B is 0.845 on run 1125 (classifier v4, OSM 2026-10-03; it reran the
superseded run 710 with identical tier km), against a limit of
0.784. Under v3 on the same extract it was 0.638 (scratch run, docs/review/trust/v4-impact.md).
The breach comes from the v4 facility rule (ADR 0002, M6 amendment): a cycleway on which
pedestrians are explicitly allowed is now `B_shared`, not A. Prague moves A 106.7 → 44.7 km
and B 188.3 → 244.5 km per side, and A+B falls by 5.8 km. The share reflects how Prague's paths
are tagged under the v4 rule, not missing tags or a boundary problem: unrecognised is 0.00 % and
the boundary diff is 0.1 %. The A/B move behind it was part of the v4 impact the user accepted on
2026-10-05. The breach itself is a controller ruling (M6 Task 15) and was not put to the user
separately. A and B are always reported separately (HANDOVER §10.1).

<!-- trust:begin -->
## Diagnostics CZ (generated)

Classifier v4, config 22238ca57b73. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.10%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| prague | 1125 | 7650.3 | 0.00% | 22.0% | 84.5% | 0.1% | b_share_of_ab |

### prague: top unmatched tag signatures (OSM 2026-10-03T20:20:50Z)

- none

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
