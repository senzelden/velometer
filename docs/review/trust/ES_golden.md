# Golden samples: ES

Open each way, compare the tags with our tier and rule, write the verdict (ok, or what is wrong), then set `confirmed: true` in the yaml for the ways you agree with.

| way | city | tags | our tier / rule | verdict |
|---|---|---|---|---|
| [306168597](https://www.openstreetmap.org/way/306168597)  | madrid | `cycleway:both=no`<br>`highway=motorway` | left: excluded / X_no<br>right: excluded / X_no | proposed: ok: excluded. Motorway, cycleway:both=no |
| [279328952](https://www.openstreetmap.org/way/279328952) Anillo Verde Ciclista | madrid | `highway=cycleway`<br>`segregated=yes` | self: A / A_cycleway | proposed: ok: A. Anillo Verde Ciclista, highway=cycleway with segregated=yes |
| [308379125](https://www.openstreetmap.org/way/308379125) Calle de Eduardo Barreiros | madrid | `cycleway:both=shared_lane`<br>`cycleway:both:lane=pictogram`<br>`highway=tertiary` | left: excluded / X_shared_lane<br>right: excluded / X_shared_lane | proposed: ok: excluded. Madrid ciclocarril (sharrow pictograms on a 30 km/h lane) = shared_lane: no separate space |
| [29023984](https://www.openstreetmap.org/way/29023984) Carretera Particular del Chalet | madrid | `highway=track` | self: excluded / X_private | proposed: ok: excluded. access=private |
| [285007057](https://www.openstreetmap.org/way/285007057) Gran Vía de Villaverde | madrid | `highway=pedestrian` | self: excluded / X_area | proposed: ok: excluded. area=yes pedestrian bridge |
| [177572223](https://www.openstreetmap.org/way/177572223) Calle de Alcalá de Henares | madrid | `highway=construction` | self: excluded / X_lifecycle | proposed: ok: excluded. highway=construction |
| [1413308046](https://www.openstreetmap.org/way/1413308046) Carrer dels Escultors Claperós | barcelona | `bicycle=yes`<br>`cycleway=pictogram`<br>`highway=living_street` | no output | proposed: ok: not counted. cycleway=pictogram is no documented value (= shared_lane + pictogram); would be excluded anyway; 0.07 km |
| [963354308](https://www.openstreetmap.org/way/963354308) Madrid Río | madrid | `bicycle=yes`<br>`highway=cycleway`<br>`segregated=no` | self: B / B_cycleway_foot | proposed: ok: B. Madrid Río, foot=designated, segregated=no: shared path |
| [3997433](https://www.openstreetmap.org/way/3997433) Calle de Aquitania | madrid | `cycleway:left=lane`<br>`highway=tertiary` | left: D / D_lane | proposed: ok: D left. Painted lane on the left of a one-way street |
| [294082522](https://www.openstreetmap.org/way/294082522) Carrer de Sants | barcelona | `bicycle=yes`<br>`cycleway:both=share_busway`<br>`highway=tertiary` | left: E / E_bus<br>right: E / E_bus | proposed: ok: E both sides. share_busway: cycling allowed in the bus lane |
| [87101690](https://www.openstreetmap.org/way/87101690)  | madrid | `cycleway:right=track`<br>`highway=primary` | right: A / A_track_side | proposed: ok: A right. cycleway:right=track |

Map data © OpenStreetMap contributors, ODbL 1.0
