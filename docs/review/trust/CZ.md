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

<!-- trust:begin -->
## Diagnostics CZ (generated)

Classifier v3, config 0237b5b5c432. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.10%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| prague | 288 | 7645.0 | 0.00% | 19.8% | 63.8% | 0.1% | none |

### prague: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- none

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
