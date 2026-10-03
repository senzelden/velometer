# Golden samples: FI

Open each way, compare the tags with our tier and rule, write the verdict (ok, or what is wrong), then set `confirmed: true` in the yaml for the ways you agree with.

| way | city | tags | our tier / rule | verdict |
|---|---|---|---|---|
| [31719831](https://www.openstreetmap.org/way/31719831)  | helsinki | `bicycle=no`<br>`highway=footway` | self: excluded / X_bicycle_no | proposed: ok: excluded. Sidewalk with bicycle=no (Finnish sidewalks forbid cycling for adults; mapped this way across Helsinki, 876 km) |
| [55109739](https://www.openstreetmap.org/way/55109739)  | helsinki | `bicycle=designated`<br>`highway=cycleway`<br>`segregated=no` | self: B / B_cycleway_foot | proposed: ok: B. Yhdistetty pyörätie ja jalkakäytävä (combined path), foot=designated, segregated=no |
| [36816610](https://www.openstreetmap.org/way/36816610)  | helsinki | `highway=cycleway` | self: A / A_cycleway | proposed: ok: A. highway=cycleway with foot=yes (permission, not designation), as v2 reads it; a park route used as a ski track in winter |
| [55445809](https://www.openstreetmap.org/way/55445809)  | helsinki | `highway=pedestrian` | self: excluded / X_area | proposed: ok: excluded. area=yes pedestrian apron |
| [639244857](https://www.openstreetmap.org/way/639244857) Viilarintie | helsinki | `bicycle=use_sidepath`<br>`cycleway:left=no`<br>`cycleway:right=separate`<br>`highway=secondary` | left: excluded / X_no<br>right: excluded / X_separate | proposed: ok: excluded. Left no; right separate (the path is its own way, counted there) |
| [410524766](https://www.openstreetmap.org/way/410524766)  | helsinki | `highway=track` | self: excluded / X_private | proposed: ok: excluded. access=private |
| [443801797](https://www.openstreetmap.org/way/443801797) Koirasaarentie | helsinki | `cycleway:right=lane`<br>`highway=tertiary` | right: D / D_lane | proposed: ok: D right. Painted lane on a one-way road |
| [127178977](https://www.openstreetmap.org/way/127178977)  | helsinki | `bicycle=designated`<br>`highway=footway`<br>`segregated=no` | self: B / B_path | proposed: ok: B. Footway with bicycle=designated, segregated=no: shared path |
| [107325048](https://www.openstreetmap.org/way/107325048) Kulosaaren puistotie | helsinki | `bicycle=designated`<br>`cyclestreet=yes`<br>`highway=tertiary` | self: E / E_cycle_street | proposed: ok: E. Pyöräkatu (cyclestreet=yes) |
| [370089006](https://www.openstreetmap.org/way/370089006) Kivikonlaita | helsinki | `bicycle=use_sidepath`<br>`cycleway:left=no`<br>`cycleway:right=separate`<br>`highway=unclassified` | left: excluded / X_no<br>right: excluded / X_separate | proposed: ok: excluded. Left no; right separate |

Map data © OpenStreetMap contributors, ODbL 1.0
