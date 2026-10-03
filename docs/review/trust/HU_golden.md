# Golden samples: HU

Open each way, compare the tags with our tier and rule, write the verdict (ok, or what is wrong), then set `confirmed: true` in the yaml for the ways you agree with.

| way | city | tags | our tier / rule | verdict |
|---|---|---|---|---|
| [158264567](https://www.openstreetmap.org/way/158264567) Lőrinci út | budapest | `cycleway:both=no`<br>`highway=tertiary` | left: excluded / X_no<br>right: excluded / X_no | confirmed: ok: excluded. cycleway:both=no |
| [263646527](https://www.openstreetmap.org/way/263646527)  | budapest | `highway=cycleway` | self: A / A_cycleway | confirmed: ok: A. highway=cycleway, no foot designation |
| [220990755](https://www.openstreetmap.org/way/220990755) Nagy-Káros-híd dűlő | budapest | `highway=track` | self: excluded / X_private | confirmed: ok: excluded. access=private |
| [328672666](https://www.openstreetmap.org/way/328672666) Újszász utca | budapest | `cycleway=lane`<br>`highway=tertiary` | left: D / D_lane<br>right: D / D_lane | confirmed: ok: D both sides. Plain cycleway=lane on a two-way road |
| [6172172](https://www.openstreetmap.org/way/6172172) Álmos utca | budapest | `cycleway:both=shared_lane`<br>`cycleway:both:lane=pictogram`<br>`cycleway:left:oneway=-1`<br>`highway=residential`<br>`oneway:bicycle=no` | left: excluded / X_shared_lane<br>right: excluded / X_shared_lane | confirmed: ok: excluded. Sharrow pictograms (shared_lane + pictogram), no own space |
| [278008760](https://www.openstreetmap.org/way/278008760) Monspart Sarolta Futókör | budapest | `bicycle=no`<br>`highway=footway` | self: excluded / X_bicycle_no | confirmed: ok: excluded. Running track, bicycle=no |
| [81401180](https://www.openstreetmap.org/way/81401180)  | budapest | `bicycle=designated`<br>`highway=cycleway`<br>`segregated=no` | self: B / B_cycleway_foot | confirmed: ok: B. Shared foot/cycle path, foot=designated, segregated=no |
| [125067709](https://www.openstreetmap.org/way/125067709) Soroksári út | budapest | `cycleway=share_busway`<br>`highway=primary` | right: E / E_bus | confirmed: ok: E right. Bus lane open to cycles (share_busway) on a one-way carriageway |
| [152908559](https://www.openstreetmap.org/way/152908559) Kossuth Lajos utca | budapest | `cycleway=lane`<br>`cycleway:lane=advisory`<br>`highway=tertiary` | left: D / D_lane_advisory<br>right: D / D_lane_advisory | confirmed: ok: D advisory both sides. Painted lane with cycleway:lane=advisory |
| [114787033](https://www.openstreetmap.org/way/114787033) Ferihegyi repülőtérre vezető út | budapest | `cycleway:left=no`<br>`cycleway:right=separate`<br>`highway=primary` | left: excluded / X_no<br>right: excluded / X_separate | confirmed: ok: excluded. Left no; right separate |

Map data © OpenStreetMap contributors, ODbL 1.0
