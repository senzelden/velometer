# Golden samples: CZ

Open each way, compare the tags with our tier and rule, write the verdict (ok, or what is wrong), then set `confirmed: true` in the yaml for the ways you agree with.

| way | city | tags | our tier / rule | verdict |
|---|---|---|---|---|
| [27074770](https://www.openstreetmap.org/way/27074770)  | prague | `cycleway:both=no`<br>`highway=secondary` | left: excluded / X_no<br>right: excluded / X_no | confirmed: ok: excluded. cycleway:both=no |
| [1422461231](https://www.openstreetmap.org/way/1422461231)  | prague | `highway=track` | self: excluded / X_private | confirmed: ok: excluded. access=private |
| [917953378](https://www.openstreetmap.org/way/917953378)  | prague | `highway=construction` | self: excluded / X_lifecycle | confirmed: ok: excluded. highway=construction |
| [25464752](https://www.openstreetmap.org/way/25464752)  | prague | `bicycle=designated`<br>`highway=cycleway`<br>`segregated=no` | self: B / B_cycleway_foot | confirmed: ok: B. Shared foot/cycle path, foot=designated, segregated=no |
| [320297312](https://www.openstreetmap.org/way/320297312)  | prague | `bicycle=no`<br>`highway=path` | self: excluded / X_bicycle_no | confirmed: ok: excluded. bicycle=no |
| [1361268398](https://www.openstreetmap.org/way/1361268398)  | prague | `highway=cycleway` | self: A / A_cycleway | confirmed: ok: A. highway=cycleway |
| [135706932](https://www.openstreetmap.org/way/135706932) Hartigova | prague | `cycleway:right=soft_lane`<br>`highway=secondary` | no output (v2)<br>v3: right: D / D_soft_lane | confirmed: wrong under v2: should be D advisory right; v3 gives it. cycleway:right=soft_lane is the (rejected 2014) value for a dashed lane with pictograms, i.e. ochranný jízdní pruh = cycleway:lane=advisory; v3 proposal 1 |
| [762313241](https://www.openstreetmap.org/way/762313241) Ocelkova | prague | `cycleway:right=soft_lane`<br>`highway=tertiary` | no output (v2)<br>v3: right: D / D_soft_lane | confirmed: wrong under v2: should be D advisory right; v3 gives it. Same soft_lane case; v3 proposal 1 |
| [821229572](https://www.openstreetmap.org/way/821229572) Novovysočanská | prague | `cycleway=soft_lane`<br>`highway=secondary` | no output (v2)<br>v3: left: D / D_soft_lane<br>right: D / D_soft_lane | confirmed: wrong under v2: should be D advisory both sides; v3 gives it. cycleway=soft_lane; v3 proposal 1 |
| [129259688](https://www.openstreetmap.org/way/129259688)  | prague | `cycleway:left=lane`<br>`cycleway:left:lane=advisory`<br>`cycleway:left:oneway=-1`<br>`cycleway:right=shared_lane`<br>`cycleway:right:lane=pictogram`<br>`highway=tertiary`<br>`oneway:bicycle=no` | left: D / D_lane_advisory<br>right: excluded / X_shared_lane | confirmed: ok: left D advisory (contraflow ochranný pruh); right excluded (cyklopiktokoridor = shared_lane pictogram) |
| [715769616](https://www.openstreetmap.org/way/715769616) Strakonická | prague | `bicycle=yes`<br>`cycleway:right=share_busway`<br>`highway=primary` | right: E / E_bus | confirmed: ok: E right. Bus lane open to cycles |
| [4052180](https://www.openstreetmap.org/way/4052180) Podolské nábřeží | prague | `cycleway:right=lane`<br>`cycleway:right:lane=exclusive`<br>`highway=tertiary` | right: D / D_lane | confirmed: ok: D right. Exclusive painted lane (cycleway:right:lane=exclusive) |

Map data © OpenStreetMap contributors, ODbL 1.0
