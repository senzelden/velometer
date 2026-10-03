# Golden samples: NL

Open each way, compare the tags with our tier and rule, write the verdict (ok, or what is wrong), then set `confirmed: true` in the yaml for the ways you agree with.

| way | city | tags | our tier / rule | verdict |
|---|---|---|---|---|
| [517771727](https://www.openstreetmap.org/way/517771727) Gooilandseweg | amsterdam | `highway=cycleway` | self: A / A_cycleway | confirmed: ok: A. Separate cycleway (sign G12a, fiets/bromfietspad); mopeds may use it, but it is separated from motor traffic |
| [81041300](https://www.openstreetmap.org/way/81041300) Ringkade | utrecht | `cycleway:both=no`<br>`highway=unclassified` | left: excluded / X_no<br>right: excluded / X_no | confirmed: ok: excluded. cycleway:both=no states no provision |
| [30686463](https://www.openstreetmap.org/way/30686463)  | amsterdam | `bicycle=no`<br>`highway=track` | self: excluded / X_private | confirmed: ok: excluded. access=no and bicycle=no |
| [350999663](https://www.openstreetmap.org/way/350999663)  | amsterdam | `bicycle=no`<br>`highway=path` | self: excluded / X_bicycle_no | confirmed: ok: excluded. bicycle=no |
| [37614919](https://www.openstreetmap.org/way/37614919) De loper | amsterdam | `bicycle=yes`<br>`highway=pedestrian` | self: excluded / X_area | confirmed: ok: excluded. area=yes pedestrian plaza, not a linear route |
| [7062188](https://www.openstreetmap.org/way/7062188) Rijksstraatweg | utrecht | `cycleway=lane`<br>`cycleway:surface=asphalt`<br>`cycleway:width=1.50`<br>`highway=residential` | left: D / D_lane<br>right: D / D_lane | confirmed: ok: D both sides. Plain cycleway=lane on a two-way road is a painted lane each side |
| [790330137](https://www.openstreetmap.org/way/790330137) Koivistokade | amsterdam | `cycleway=use`<br>`highway=residential` | no output | confirmed: ok: not counted. cycleway=use is no documented value (likely meant use_sidepath); unrecognised, 0.13 km |
| [1527660171](https://www.openstreetmap.org/way/1527660171) Veeteeltstraat | amsterdam | `cycleway:left=right`<br>`highway=residential` | no output | confirmed: ok: not counted. cycleway:left=right is a mistag; 0.01 km |
| [7056827](https://www.openstreetmap.org/way/7056827) Jutfaseweg | utrecht | `cyclestreet=yes`<br>`highway=residential` | self: E / E_cycle_street | confirmed: ok: E. Fietsstraat, cyclestreet=yes (NL wiki convention) |
| [7010586](https://www.openstreetmap.org/way/7010586) Maliesingel | utrecht | `cycleway:both=lane`<br>`cycleway:both:lane=advisory`<br>`highway=tertiary` | left: D / D_lane_advisory<br>right: D / D_lane_advisory | confirmed: ok: D advisory both sides. Fietsstrook with dashed line = cycleway:lane=advisory |
| [1525558445](https://www.openstreetmap.org/way/1525558445) Nedereindseweg | utrecht | `cycleway=shared_lane`<br>`cycleway:surface:colour=red`<br>`highway=tertiary` | left: excluded / X_shared_lane<br>right: excluded / X_shared_lane | confirmed: ok: excluded. Red fietssuggestiestrook; the NL community tags it cycleway=shared_lane (wiki Key:cycleway:lane): no legal lane |
| [1505076700](https://www.openstreetmap.org/way/1505076700) Uitdammerdijk | amsterdam | `bicycle=designated`<br>`highway=cycleway`<br>`segregated=no` | self: B / B_cycleway_foot | confirmed: ok: B. Onverplicht fietspad, foot=designated, segregated=no: shared foot/cycle path |

Map data © OpenStreetMap contributors, ODbL 1.0
