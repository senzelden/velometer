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

<!-- trust:begin -->
## Diagnostics CZ (generated)

Classifier v2, config 7416d3c8c103. Km are OSM mapped km (ADR 0006); shares are of cycling km, the per-side km of sides whose way carries cycling tags.

Limits: unrecognised 0.1%, excluded 60.7%, B of A+B 78.4%, boundary diff 5%.

| city | run | cycling km | unrecognised | excluded | B of A+B | boundary diff | over limit |
|---|---|---|---|---|---|---|---|
| prague | 239 | 7645.0 | 0.8% | 19.8% | 63.8% | 0.1% | unrecognised_share |

### prague: top unmatched tag signatures (OSM 2026-10-02T20:21:34Z)

- `cycleway:right=soft_lane;highway=secondary`: 16.91 km
- `cycleway:right=soft_lane;highway=tertiary`: 8.69 km
- `cycleway=soft_lane;highway=secondary`: 6.17 km
- `cycleway=soft_lane;highway=tertiary`: 3.35 km
- `cycleway:left=no;cycleway:right=soft_lane;highway=primary`: 2.30 km

Map data © OpenStreetMap contributors, ODbL 1.0
<!-- trust:end -->
