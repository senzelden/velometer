# Golden samples: SI

Open each way, compare the tags with our tier and rule, write the verdict (ok, or what is wrong), then set `confirmed: true` in the yaml for the ways you agree with.

| way | city | tags | our tier / rule | verdict |
|---|---|---|---|---|
| [1513714682](https://www.openstreetmap.org/way/1513714682) Črna vas | ljubljana | `bicycle=designated`<br>`highway=path`<br>`segregated=yes` | self: B / B_path_segregated | proposed: ok: B. highway=path, foot=designated, segregated=yes: kolesarska steza beside the footway on one surface (B_path_segregated) |
| [706908809](https://www.openstreetmap.org/way/706908809) Cesta v Kresnice | ljubljana | `cycleway:both=no`<br>`highway=tertiary` | left: excluded / X_no<br>right: excluded / X_no | proposed: ok: excluded. cycleway:both=no |
| [32976406](https://www.openstreetmap.org/way/32976406) Ob dolenjski železnici | ljubljana | `cycleway=lane`<br>`highway=tertiary` | left: D / D_lane<br>right: D / D_lane | proposed: ok: D both sides. Kolesarski pas (painted lane) |
| [649256821](https://www.openstreetmap.org/way/649256821)  | ljubljana | `bicycle=no`<br>`highway=path` | self: excluded / X_bicycle_no | proposed: ok: excluded. bicycle=no |
| [553808731](https://www.openstreetmap.org/way/553808731)  | ljubljana | `highway=cycleway` | self: A / A_cycleway | proposed: ok: A. highway=cycleway |
| [551327799](https://www.openstreetmap.org/way/551327799) Zasavska cesta | ljubljana | `bicycle=designated`<br>`highway=path`<br>`segregated=no` | self: B / B_path | proposed: ok: B. Shared path, segregated=no |
| [3283481](https://www.openstreetmap.org/way/3283481) Derčeva ulica | ljubljana | `cycleway=lane`<br>`cycleway:lane=advisory`<br>`highway=residential` | left: D / D_lane_advisory<br>right: D / D_lane_advisory | proposed: ok: D advisory both sides |
| [1028502896](https://www.openstreetmap.org/way/1028502896) Cesta Dolomitskega odreda | ljubljana | `cycleway:right=track`<br>`highway=tertiary` | right: A / A_track_side | proposed: ok: A right. cycleway:right=track with segregated:right=yes |
| [1119247786](https://www.openstreetmap.org/way/1119247786) Jamova cesta | ljubljana | `bicycle:backward=use_sidepath`<br>`cycleway:left=track`<br>`cycleway:right=lane`<br>`cycleway:right:lane=advisory`<br>`highway=tertiary` | left: A / A_track_side<br>right: D / D_lane_advisory | proposed: ok: left A (track), right D advisory |
| [13027280](https://www.openstreetmap.org/way/13027280) Ižanska cesta | ljubljana | `bicycle=use_sidepath`<br>`cycleway=separate`<br>`highway=secondary` | left: excluded / X_separate<br>right: excluded / X_separate | proposed: ok: excluded. cycleway=separate: the path is its own way, counted there |

Map data © OpenStreetMap contributors, ODbL 1.0
