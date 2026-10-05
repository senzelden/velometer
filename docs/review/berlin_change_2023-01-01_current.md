# Berlin: mapped cycling infrastructure change

From run 740 (OSM 2023-01-01T00:00:00Z) to run 713 (OSM 2026-10-03T20:20:50Z); classifier v4, boundary sha `760d04d86a75`.

All figures are mapped km (ADR 0006): a gain is a way newly mapped as cycling infrastructure, not a construction.
Categories: mapped gained / lost / retiered / redrawn, and geometry (the same way-side and tier, its length changed by more than 1 m; km is the signed length change). A redrawn way-side lies within 15 m of replaced way-sides of the same tier for at least 80 % of its length, and the new way-sides together cover 80 % of each one they replace; a way-side split off an existing way-side of the same tier (a new way id on the length that way-side lost) counts as redrawn too. A redrawn row's km is the new way-side's.

## Totals (per_side mapped km, recomputed and checked against both runs)

The net change (to − from) is the change in mapped km per tier. The categories below do not sum to it: a redrawn or retiered row carries only its `to` km, and a split way's persisting piece shows its shortening as a negative geometry row, which its split-off (redrawn) pieces offset.

| tier | from | to | net change (to − from) |
|---|---:|---:|---:|
| A | 1228.181 | 1275.380 | +47.199 |
| B | 286.900 | 275.296 | -11.603 |
| C | 20.401 | 28.857 | +8.456 |
| D | 441.563 | 461.493 | +19.930 |
| E | 87.235 | 116.907 | +29.672 |
| **A–E** | 2064.279 | 2157.933 | +93.654 |

## Mapped km per category

| | gained | lost | retiered | redrawn | geometry |
|---|---:|---:|---:|---:|---:|
| Charlottenburg-Wilmersdorf | 47.166 | 32.740 | 6.566 | 93.896 | -32.568 |
| Friedrichshain-Kreuzberg | 18.502 | 17.098 | 5.320 | 27.625 | -19.660 |
| Lichtenberg | 21.547 | 19.631 | 0.558 | 29.108 | -15.769 |
| Marzahn-Hellersdorf | 19.627 | 18.954 | 1.345 | 29.198 | -13.784 |
| Mitte | 56.712 | 30.550 | 8.408 | 54.020 | -30.265 |
| Neukölln | 20.102 | 15.193 | 1.203 | 34.719 | -23.845 |
| Pankow | 38.084 | 36.943 | 1.597 | 50.379 | -38.247 |
| Reinickendorf | 46.860 | 35.353 | 1.827 | 62.512 | -30.138 |
| Spandau | 35.558 | 20.642 | 1.244 | 50.803 | -32.714 |
| Steglitz-Zehlendorf | 39.705 | 27.542 | 9.271 | 106.784 | -60.609 |
| Tempelhof-Schöneberg | 45.102 | 23.081 | 5.040 | 65.751 | -37.270 |
| Treptow-Köpenick | 52.443 | 39.367 | 5.034 | 51.103 | -29.451 |
| Outside the 12 Bezirke (LAU edge) | 0.903 | 3.147 | 0.000 | 0.009 | -0.046 |
| **Berlin** | 442.311 | 320.242 | 47.413 | 655.905 | -364.365 |

## gained: 6111 way-sides (top 20 by mapped km)

| way (from) | way (to) | side | tier | mapped km |
|---|---|---|---|---:|
| [23110217](https://www.openstreetmap.org/way/23110217) | [23110217](https://www.openstreetmap.org/way/23110217) | self | untiered → B | 2.566 |
| – | [24403109](https://www.openstreetmap.org/way/24403109) | left | – → D | 1.924 |
| [897616698](https://www.openstreetmap.org/way/897616698) | [897616698](https://www.openstreetmap.org/way/897616698) | self | untiered → B | 1.842 |
| – | [1218406753](https://www.openstreetmap.org/way/1218406753) | self | – → A | 1.811 |
| – | [25156778](https://www.openstreetmap.org/way/25156778) | self | – → B | 1.640 |
| – | [1429258104](https://www.openstreetmap.org/way/1429258104) | self | – → B | 1.575 |
| – | [1521472339](https://www.openstreetmap.org/way/1521472339) | self | – → B | 1.473 |
| – | [1450028883](https://www.openstreetmap.org/way/1450028883) | self | – → A | 1.440 |
| – | [1147616981](https://www.openstreetmap.org/way/1147616981) | self | – → A | 1.434 |
| [8008611](https://www.openstreetmap.org/way/8008611) | [8008611](https://www.openstreetmap.org/way/8008611) | self | untiered → A | 1.334 |
| – | [1300651165](https://www.openstreetmap.org/way/1300651165) | self | – → A | 1.331 |
| – | [1545690468](https://www.openstreetmap.org/way/1545690468) | self | – → A | 1.268 |
| [899453864](https://www.openstreetmap.org/way/899453864) | [899453864](https://www.openstreetmap.org/way/899453864) | self | untiered → A | 1.261 |
| – | [1234291514](https://www.openstreetmap.org/way/1234291514) | self | – → A | 1.235 |
| [1120570022](https://www.openstreetmap.org/way/1120570022) | [1120570022](https://www.openstreetmap.org/way/1120570022) | self | untiered → A | 1.209 |
| – | [1391160892](https://www.openstreetmap.org/way/1391160892) | self | – → A | 1.209 |
| [25731621](https://www.openstreetmap.org/way/25731621) | [25731621](https://www.openstreetmap.org/way/25731621) | self | untiered → B | 1.193 |
| [1004141243](https://www.openstreetmap.org/way/1004141243) | [1004141243](https://www.openstreetmap.org/way/1004141243) | self | untiered → B | 1.133 |
| [246086794](https://www.openstreetmap.org/way/246086794) | [246086794](https://www.openstreetmap.org/way/246086794) | self | untiered → A | 1.097 |
| – | [1462142363](https://www.openstreetmap.org/way/1462142363) | self | – → A | 1.094 |

## lost: 3596 way-sides (top 20 by mapped km)

| way (from) | way (to) | side | tier | mapped km |
|---|---|---|---|---:|
| [902030369](https://www.openstreetmap.org/way/902030369) | [902030369](https://www.openstreetmap.org/way/902030369) | self | B → excluded | 3.792 |
| [42721613](https://www.openstreetmap.org/way/42721613) | [42721613](https://www.openstreetmap.org/way/42721613) | self | B → untiered | 2.296 |
| [169076535](https://www.openstreetmap.org/way/169076535) | [169076535](https://www.openstreetmap.org/way/169076535) | self | B → untiered | 2.083 |
| [40506012](https://www.openstreetmap.org/way/40506012) | [40506012](https://www.openstreetmap.org/way/40506012) | self | B → untiered | 2.048 |
| [185867136](https://www.openstreetmap.org/way/185867136) | [185867136](https://www.openstreetmap.org/way/185867136) | self | B → untiered | 1.923 |
| [169678702](https://www.openstreetmap.org/way/169678702) | [169678702](https://www.openstreetmap.org/way/169678702) | self | B → untiered | 1.795 |
| [515470948](https://www.openstreetmap.org/way/515470948) | [515470948](https://www.openstreetmap.org/way/515470948) | self | B → excluded | 1.632 |
| [24872481](https://www.openstreetmap.org/way/24872481) | [24872481](https://www.openstreetmap.org/way/24872481) | right | A → excluded | 1.388 |
| [22946307](https://www.openstreetmap.org/way/22946307) | [22946307](https://www.openstreetmap.org/way/22946307) | self | A → untiered | 1.331 |
| [383987239](https://www.openstreetmap.org/way/383987239) | [383987239](https://www.openstreetmap.org/way/383987239) | right | A → excluded | 1.250 |
| [144884824](https://www.openstreetmap.org/way/144884824) | [144884824](https://www.openstreetmap.org/way/144884824) | left | A → excluded | 1.223 |
| [144884824](https://www.openstreetmap.org/way/144884824) | [144884824](https://www.openstreetmap.org/way/144884824) | right | A → excluded | 1.223 |
| [31099696](https://www.openstreetmap.org/way/31099696) | [31099696](https://www.openstreetmap.org/way/31099696) | left | A → excluded | 1.106 |
| [31099696](https://www.openstreetmap.org/way/31099696) | [31099696](https://www.openstreetmap.org/way/31099696) | right | A → excluded | 1.106 |
| [1040332443](https://www.openstreetmap.org/way/1040332443) | [1040332443](https://www.openstreetmap.org/way/1040332443) | self | B → excluded | 1.076 |
| [33338053](https://www.openstreetmap.org/way/33338053) | [33338053](https://www.openstreetmap.org/way/33338053) | left | A → excluded | 1.049 |
| [33338053](https://www.openstreetmap.org/way/33338053) | [33338053](https://www.openstreetmap.org/way/33338053) | right | A → excluded | 1.049 |
| [144063891](https://www.openstreetmap.org/way/144063891) | [144063891](https://www.openstreetmap.org/way/144063891) | self | B → untiered | 1.049 |
| [24047259](https://www.openstreetmap.org/way/24047259) | – | left | A → – | 0.946 |
| [169678701](https://www.openstreetmap.org/way/169678701) | [169678701](https://www.openstreetmap.org/way/169678701) | self | B → untiered | 0.937 |

## retiered: 698 way-sides (top 20 by mapped km)

| way (from) | way (to) | side | tier | mapped km | tags changed |
|---|---|---|---|---:|---|
| [4424237](https://www.openstreetmap.org/way/4424237) | [4424237](https://www.openstreetmap.org/way/4424237) | left | D → C | 1.918 | `cycleway`: lane → –; `cycleway:both`: – → lane; `cycleway:both:bicycle`: – → designated; `cycleway:both:buffer:both`: – → no; `cycleway:both:lane`: – → exclusive; `cycleway:both:marking:left`: – → solid_line; `cycleway:both:oneway`: – → yes; `cycleway:both:separation:left`: – → no; `cycleway:both:separation:right`: – → kerb; `cycleway:both:surface:colour`: – → none; `cycleway:both:traffic_sign`: – → DE:237; `cycleway:both:width`: – → 2; `cycleway:lane`: exclusive → –; `cycleway:left:mapillary`: – → 2181707595626449; `cycleway:right:mapillary`: – → 1444239860262996; `lane_markings`: – → yes; `parking:both`: – → no; `smoothness`: – → good; `source:cycleway:both:width`: – → infra3D; `source:cycleway:left:traffic_sign:mapillary`: – → 1384022712821733; `source:cycleway:right:traffic_sign:mapillary`: – → 10073018142806216; `width`: – → 12.5; `zone:traffic`: – → DE:urban |
| [25475257](https://www.openstreetmap.org/way/25475257) | [25475257](https://www.openstreetmap.org/way/25475257) | self | B → A | 0.848 | `check_date:surface`: – → 2026-04-24; `cycleway:surface`: – → paving_stones; `footway:surface`: – → paving_stones; `is_sidepath`: – → no; `segregated`: – → yes; `smoothness`: – → good |
| [28819507](https://www.openstreetmap.org/way/28819507) | [28819507](https://www.openstreetmap.org/way/28819507) | right | A → D | 0.661 | `cycleway:right`: track → lane; `cycleway:right:lane`: – → exclusive; `cycleway:right:traffic_sign`: – → DE:237; `parking:left`: – → no; `parking:right`: – → lane; `parking:right:fee`: – → no; `parking:right:orientation`: – → parallel; `sidewalk`: right → –; `sidewalk:left`: – → no; `sidewalk:right`: – → separate; `zone:traffic`: – → DE:urban |
| [285484255](https://www.openstreetmap.org/way/285484255) | [285484255](https://www.openstreetmap.org/way/285484255) | left | A → B | 0.633 | `cycleway:both:oneway`: – → yes; `cycleway:both:segregated`: – → no; `cycleway:both:surface`: – → asphalt; `cycleway:both:surface:colour`: – → none; `cycleway:both:traffic_sign`: – → none; `cycleway:both:width`: – → 1.3; `cycleway:left:mapillary`: – → 497674123403483; `cycleway:left:separation:left`: – → kerb; `cycleway:left:separation:right`: – → greenery; `cycleway:right:mapillary`: – → 1800010087214276; `cycleway:right:separation:left`: – → kerb; `cycleway:right:separation:right`: – → greenery; `parking:both`: – → no; `parking:both:restriction`: – → no_parking; `source:cycleway:both:width`: – → infra3D |
| [285484255](https://www.openstreetmap.org/way/285484255) | [285484255](https://www.openstreetmap.org/way/285484255) | right | A → B | 0.633 | `cycleway:both:oneway`: – → yes; `cycleway:both:segregated`: – → no; `cycleway:both:surface`: – → asphalt; `cycleway:both:surface:colour`: – → none; `cycleway:both:traffic_sign`: – → none; `cycleway:both:width`: – → 1.3; `cycleway:left:mapillary`: – → 497674123403483; `cycleway:left:separation:left`: – → kerb; `cycleway:left:separation:right`: – → greenery; `cycleway:right:mapillary`: – → 1800010087214276; `cycleway:right:separation:left`: – → kerb; `cycleway:right:separation:right`: – → greenery; `parking:both`: – → no; `parking:both:restriction`: – → no_parking; `source:cycleway:both:width`: – → infra3D |
| [27361815](https://www.openstreetmap.org/way/27361815) | [27361815](https://www.openstreetmap.org/way/27361815) | self | A → B | 0.565 | `is_sidepath`: – → no; `oneway`: – → no; `segregated`: yes → no |
| [914162667](https://www.openstreetmap.org/way/914162667) | [914162667](https://www.openstreetmap.org/way/914162667) | self | B → A | 0.389 | `cycleway:surface`: – → asphalt; `cycleway:surface:colour`: – → none; `cycleway:width`: – → 1.1; `is_sidepath`: – → yes; `oneway`: yes → –; `oneway:bicycle`: – → yes; `segregated`: no → yes; `source:cycleway:width`: – → infra3D; `traffic_sign`: – → DE:240 |
| [967256183](https://www.openstreetmap.org/way/967256183) | [967256183](https://www.openstreetmap.org/way/967256183) | self | A → B | 0.386 | `bicycle`: – → designated; `foot`: – → designated; `highway`: cycleway → path; `is_sidepath`: – → yes; `note`: Zeichen 237 "nur" am Ortseingang → –; `oneway`: – → yes; `oneway:bicycle`: yes → –; `segregated`: – → no; `smoothness`: – → good; `traffic_sign`: DE:237 → DE:240 |
| [857752725](https://www.openstreetmap.org/way/857752725) | [857752725](https://www.openstreetmap.org/way/857752725) | left | D → C | 0.383 | `cycleway:both:marking:left`: – → double_solid_line; `cycleway:both:separation:right`: – → kerb; `cycleway:both:traffic_sign`: – → DE:237; `cycleway:left:width`: – → 1.4; `cycleway:right:buffer:right`: – → 0.5; `cycleway:right:marking:right`: – → solid_line; `cycleway:right:width`: – → 1; `foot`: – → use_sidepath; `lane_markings`: – → yes; `maxspeed:conditional`: – → 30 @ (Mo-Fr 07:00-18:00); `sidewalk`: both → –; `sidewalk:both`: – → separate; `source:cycleway:left:width`: – → Luftbild 2025; `source:cycleway:right:width`: – → Luftbild 2025; `source:maxspeed`: – → sign; `traffic_sign`: – → DE:136-10;274-30,1042-33[Mo-Fr 07:00-18:00]; `width`: – → 10 |
| [208089047](https://www.openstreetmap.org/way/208089047) | [208089047](https://www.openstreetmap.org/way/208089047) | left | D → C | 0.381 | `cycleway`: lane → –; `cycleway:both`: – → lane; `cycleway:both:buffer:right`: – → 0.6; `cycleway:both:lane`: – → advisory; `cycleway:both:marking:both`: – → dashed_line; `cycleway:both:oneway`: – → yes; `cycleway:both:separation:left`: – → no; `cycleway:both:separation:right`: – → kerb; `cycleway:both:surface`: – → asphalt; `cycleway:both:surface:colour`: – → no; `cycleway:both:traffic_sign`: – → none; `cycleway:both:width`: – → 1.3; `foot`: – → use_sidepath; `lane_markings`: – → yes; `mapillary:backward`: – → 1111765597481004; `parking:both`: – → separate; `parking:condition:both`: residents → –; `parking:lane:both`: perpendicular → –; `parking:lane:both:perpendicular`: on_street → –; `source:cycleway:both:width`: – → Messung aus Punktwolke (Infra3DViewer); `width`: – → 11.1 |
| [376269506](https://www.openstreetmap.org/way/376269506) | [376269506](https://www.openstreetmap.org/way/376269506) | right | A → D | 0.367 | `cycleway:right`: track → lane; `cycleway:right:buffer:left`: – → 0.9; `cycleway:right:lane`: – → exclusive; `cycleway:right:oneway`: – → yes; `cycleway:right:separation:left`: – → no; `cycleway:right:surface`: – → asphalt; `cycleway:right:surface:colour`: – → red; `cycleway:right:traffic_sign`: – → DE:237; `cycleway:right:traffic_sign:mapillary`: – → 523689916958350; `cycleway:right:width`: – → 1.5; `foot`: – → use_sidepath; `layer`: 3 → 1; `parking:both`: – → no; `parking:condition:right`: no_parking → –; `parking:lane:both`: no → –; `parking:left:restriction:reason`: – → dual_carriage; `parking:right:restriction`: – → no_parking; `parking:right:restriction:reason`: – → cycleway; `smoothness`: – → good; `source:cycleway:right:width`: – → Messung aus Punktwolke (Infra3DViewer) |
| [4592292](https://www.openstreetmap.org/way/4592292) | [4592292](https://www.openstreetmap.org/way/4592292) | right | A → D | 0.366 | `cycleway:right`: track → lane; `cycleway:right:buffer:left`: – → 0.9; `cycleway:right:lane`: – → exclusive; `cycleway:right:oneway`: – → yes; `cycleway:right:separation:left`: – → no; `cycleway:right:surface`: – → asphalt; `cycleway:right:surface:colour`: – → red; `cycleway:right:traffic_sign`: – → DE:237; `cycleway:right:traffic_sign:mapillary`: – → 542137464976146; `cycleway:right:width`: – → 1.5; `foot`: – → use_sidepath; `layer`: 3 → 1; `parking:both`: – → no; `parking:condition:right`: no_parking → –; `parking:lane:both`: no → –; `parking:left:restriction:reason`: – → dual_carriage; `parking:right:restriction`: – → no_parking; `parking:right:restriction:reason`: – → cycleway; `source:cycleway:right:width`: – → Messung aus Punktwolke (Infra3DViewer) |
| [335487059](https://www.openstreetmap.org/way/335487059) | [335487059](https://www.openstreetmap.org/way/335487059) | right | C → D | 0.364 | `cycleway:right:separation:left`: vertical_panel → no; `cycleway:right:traffic_sign`: – → DE:237; `description:covid19`: Pop-up-Radweg → –; `foot`: – → use_sidepath; `lane_markings`: – → no; `lanes`: 2 → –; `parking:left:reason`: – → dual_carriage; `parking:right:reason`: – → cycleway; `sidewalk`: right → –; `sidewalk:left`: – → no; `sidewalk:right`: – → separate; `sidewalk:right:surface`: paving_stones → –; `was:lanes`: 3 → – |
| [169738742](https://www.openstreetmap.org/way/169738742) | [169738742](https://www.openstreetmap.org/way/169738742) | right | C → D | 0.340 | `cycleway:right:buffer:left`: – → yes; `cycleway:right:separation:left`: vertical_panel → no; `cycleway:right:traffic_sign`: – → DE:237; `description:covid19`: Pop-up-Radweg → –; `foot`: – → use_sidepath; `lane_markings`: – → no; `lanes`: 2 → –; `parking:left:reason`: – → dual_carriage; `parking:right:reason`: – → cycleway; `sidewalk`: right → –; `sidewalk:left`: – → no; `sidewalk:right`: – → separate; `sidewalk:right:surface`: paving_stones → –; `smoothness`: – → good; `was:lanes`: 3 → – |
| [10710969](https://www.openstreetmap.org/way/10710969) | [10710969](https://www.openstreetmap.org/way/10710969) | self | B → A | 0.335 | `check_date:surface`: – → 2024-05-24; `cycleway:surface`: – → asphalt; `footway:surface`: – → asphalt; `is_sidepath`: – → no; `oneway`: – → no; `segregated`: – → yes; `traffic_sign`: DE:240 → DE:241-30;241-31 |
| [996075251](https://www.openstreetmap.org/way/996075251) | [996075251](https://www.openstreetmap.org/way/996075251) | self | B → A | 0.333 | `check_date:surface`: – → 2023-08-04; `cycleway:surface`: – → concrete; `cycleway:width`: – → 1; `footway:surface`: – → concrete; `segregated`: no → yes; `source:cycleway:width`: – → Luftbild 2025; `traffic_sign`: DE:240 → DE:241 |
| [660945466](https://www.openstreetmap.org/way/660945466) | [660945466](https://www.openstreetmap.org/way/660945466) | left | A → D | 0.294 | `cycleway:both`: track → lane; `cycleway:both:buffer`: – → no; `cycleway:both:lane`: – → exclusive; `cycleway:both:marking:left`: – → solid_line; `cycleway:both:oneway`: – → yes; `cycleway:both:separation`: bollard → –; `cycleway:both:separation:left`: – → bollard; `cycleway:both:surface`: – → asphalt; `cycleway:both:surface:colour`: – → none; `cycleway:both:traffic_sign`: – → none; `cycleway:both:width`: – → 2.5; `cycleway:left:mapillary`: – → 3984367038452716; `cycleway:right:mapillary`: – → 730154349965094; `parking:both`: – → no; `sidewalk`: both → –; `sidewalk:both:surface`: – → paving_stones; `sidewalk:left`: – → separate; `sidewalk:right`: – → yes; `smoothness`: – → good; `source:cycleway:both:width`: – → infra3D |
| [660945466](https://www.openstreetmap.org/way/660945466) | [660945466](https://www.openstreetmap.org/way/660945466) | right | A → C | 0.294 | `cycleway:both`: track → lane; `cycleway:both:buffer`: – → no; `cycleway:both:lane`: – → exclusive; `cycleway:both:marking:left`: – → solid_line; `cycleway:both:oneway`: – → yes; `cycleway:both:separation`: bollard → –; `cycleway:both:separation:left`: – → bollard; `cycleway:both:surface`: – → asphalt; `cycleway:both:surface:colour`: – → none; `cycleway:both:traffic_sign`: – → none; `cycleway:both:width`: – → 2.5; `cycleway:left:mapillary`: – → 3984367038452716; `cycleway:right:mapillary`: – → 730154349965094; `parking:both`: – → no; `sidewalk`: both → –; `sidewalk:both:surface`: – → paving_stones; `sidewalk:left`: – → separate; `sidewalk:right`: – → yes; `smoothness`: – → good; `source:cycleway:both:width`: – → infra3D |
| [23213546](https://www.openstreetmap.org/way/23213546) | [23213546](https://www.openstreetmap.org/way/23213546) | right | A → E | 0.287 | `cycleway:right`: track → share_busway; `cycleway:right:oneway`: – → yes; `cycleway:right:traffic_sign`: – → DE:245,1022-10,Zusatzzeichen; `cycleway:right:width`: – → 2.7; `foot`: – → use_sidepath; `lanes`: 2 → 2+1 Busspur; `parking:both`: – → no; `parking:left:reason`: – → dual_carriage; `parking:right:restriction`: – → no_stopping; `parking:right:restriction:reason`: – → bus_lane; `smoothness`: – → good; `source:cycleway:right:traffic_sign:mapillary`: – → 357912689094570; `source:cycleway:right:width`: – → Luftbild 2024 |
| [996075256](https://www.openstreetmap.org/way/996075256) | [996075256](https://www.openstreetmap.org/way/996075256) | self | B → A | 0.278 | `check_date:surface`: – → 2023-08-04; `cycleway:surface`: – → concrete; `footway:surface`: – → concrete; `segregated`: no → yes; `traffic_sign`: DE:240 → DE:241 |

## redrawn: 13487 way-sides (top 20 by mapped km)

| way (from) | way (to) | side | tier | mapped km |
|---|---|---|---|---:|
| [1036290000](https://www.openstreetmap.org/way/1036290000) | [1164639569](https://www.openstreetmap.org/way/1164639569) | self | B | 1.613 |
| [86571257](https://www.openstreetmap.org/way/86571257) | [1435863277](https://www.openstreetmap.org/way/1435863277) | self | A | 1.134 |
| [16942408](https://www.openstreetmap.org/way/16942408) | [1316352013](https://www.openstreetmap.org/way/1316352013) | self | B | 1.058 |
| [331318342](https://www.openstreetmap.org/way/331318342) | [1211938430](https://www.openstreetmap.org/way/1211938430) | self | A | 1.039 |
| [941966168](https://www.openstreetmap.org/way/941966168) | [1149394829](https://www.openstreetmap.org/way/1149394829) | self | A | 1.009 |
| [26614075](https://www.openstreetmap.org/way/26614075) | [1444499536](https://www.openstreetmap.org/way/1444499536) | self | A | 1.003 |
| [166645719](https://www.openstreetmap.org/way/166645719) | [1447126278](https://www.openstreetmap.org/way/1447126278) | self | A | 0.908 |
| [909222808](https://www.openstreetmap.org/way/909222808) | [1271161544](https://www.openstreetmap.org/way/1271161544) | self | A | 0.853 |
| [1038272616](https://www.openstreetmap.org/way/1038272616) | [1226718529](https://www.openstreetmap.org/way/1226718529) | self | A | 0.829 |
| [30243828](https://www.openstreetmap.org/way/30243828) | [1445755359](https://www.openstreetmap.org/way/1445755359) | self | A | 0.817 |
| [4581781](https://www.openstreetmap.org/way/4581781) | [1297394261](https://www.openstreetmap.org/way/1297394261) | self | A | 0.813 |
| [27714624](https://www.openstreetmap.org/way/27714624) | [1229576358](https://www.openstreetmap.org/way/1229576358) | self | A | 0.799 |
| [24869967](https://www.openstreetmap.org/way/24869967) | [1229499378](https://www.openstreetmap.org/way/1229499378) | self | A | 0.789 |
| [4484024](https://www.openstreetmap.org/way/4484024) | [508112391](https://www.openstreetmap.org/way/508112391) | self | A | 0.776 |
| [169079399](https://www.openstreetmap.org/way/169079399) | [1188469367](https://www.openstreetmap.org/way/1188469367) | self | A | 0.698 |
| [60077029](https://www.openstreetmap.org/way/60077029) | [1443462078](https://www.openstreetmap.org/way/1443462078) | self | A | 0.684 |
| [112408882](https://www.openstreetmap.org/way/112408882) | [1223440779](https://www.openstreetmap.org/way/1223440779) | self | A | 0.669 |
| [25414231](https://www.openstreetmap.org/way/25414231) | [1229450882](https://www.openstreetmap.org/way/1229450882) | self | A | 0.656 |
| [5117633](https://www.openstreetmap.org/way/5117633) | [1391160882](https://www.openstreetmap.org/way/1391160882) | self | A | 0.654 |
| [370405123](https://www.openstreetmap.org/way/370405123) | [915348997](https://www.openstreetmap.org/way/915348997) | self | A | 0.650 |

## geometry: 5929 way-sides (top 20 by mapped km)

| way (from) | way (to) | side | tier | mapped km |
|---|---|---|---|---:|
| [886496559](https://www.openstreetmap.org/way/886496559) | [886496559](https://www.openstreetmap.org/way/886496559) | self | A | -2.618 |
| [909222808](https://www.openstreetmap.org/way/909222808) | [909222808](https://www.openstreetmap.org/way/909222808) | self | A | -1.648 |
| [1036290000](https://www.openstreetmap.org/way/1036290000) | [1036290000](https://www.openstreetmap.org/way/1036290000) | self | B | -1.613 |
| [5000365](https://www.openstreetmap.org/way/5000365) | [5000365](https://www.openstreetmap.org/way/5000365) | right | A | -1.405 |
| [110149631](https://www.openstreetmap.org/way/110149631) | [110149631](https://www.openstreetmap.org/way/110149631) | right | D | -1.299 |
| [899567891](https://www.openstreetmap.org/way/899567891) | [899567891](https://www.openstreetmap.org/way/899567891) | self | A | 1.299 |
| [989743121](https://www.openstreetmap.org/way/989743121) | [989743121](https://www.openstreetmap.org/way/989743121) | self | A | -1.239 |
| [989744644](https://www.openstreetmap.org/way/989744644) | [989744644](https://www.openstreetmap.org/way/989744644) | self | A | -1.195 |
| [52513361](https://www.openstreetmap.org/way/52513361) | [52513361](https://www.openstreetmap.org/way/52513361) | left | A | -1.120 |
| [52513361](https://www.openstreetmap.org/way/52513361) | [52513361](https://www.openstreetmap.org/way/52513361) | right | A | -1.120 |
| [30962289](https://www.openstreetmap.org/way/30962289) | [30962289](https://www.openstreetmap.org/way/30962289) | right | A | -1.082 |
| [25199872](https://www.openstreetmap.org/way/25199872) | [25199872](https://www.openstreetmap.org/way/25199872) | left | A | -1.081 |
| [25199872](https://www.openstreetmap.org/way/25199872) | [25199872](https://www.openstreetmap.org/way/25199872) | right | A | -1.081 |
| [941966168](https://www.openstreetmap.org/way/941966168) | [941966168](https://www.openstreetmap.org/way/941966168) | self | A | -1.073 |
| [989761830](https://www.openstreetmap.org/way/989761830) | [989761830](https://www.openstreetmap.org/way/989761830) | self | A | -1.069 |
| [24615396](https://www.openstreetmap.org/way/24615396) | [24615396](https://www.openstreetmap.org/way/24615396) | right | A | -1.007 |
| [4071975](https://www.openstreetmap.org/way/4071975) | [4071975](https://www.openstreetmap.org/way/4071975) | right | D | -0.935 |
| [779835107](https://www.openstreetmap.org/way/779835107) | [779835107](https://www.openstreetmap.org/way/779835107) | right | A | -0.934 |
| [137928859](https://www.openstreetmap.org/way/137928859) | [137928859](https://www.openstreetmap.org/way/137928859) | left | A | -0.920 |
| [137928859](https://www.openstreetmap.org/way/137928859) | [137928859](https://www.openstreetmap.org/way/137928859) | right | A | -0.920 |

_Map data © OpenStreetMap contributors, ODbL 1.0_
