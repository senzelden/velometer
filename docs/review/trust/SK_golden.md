# Golden samples: SK

Open each way, compare the tags with our tier and rule, write the verdict (ok, or what is wrong), then set `confirmed: true` in the yaml for the ways you agree with.

| way | city | tags | our tier / rule | verdict |
|---|---|---|---|---|
| [1279751700](https://www.openstreetmap.org/way/1279751700)  | bratislava | `highway=track` | self: excluded / X_private | proposed: ok: excluded. access=private (track) |
| [208087851](https://www.openstreetmap.org/way/208087851)  | bratislava | `highway=cycleway` | self: A / A_cycleway | proposed: ok: A. highway=cycleway; foot=yes is a permission, not a designated shared path (the way's fixme asks to verify pedestrian access) |
| [960705749](https://www.openstreetmap.org/way/960705749)  | bratislava | `bicycle=no`<br>`highway=footway` | self: excluded / X_bicycle_no | proposed: ok: excluded. bicycle=no (Lužný most footbridge) |
| [793056624](https://www.openstreetmap.org/way/793056624)  | bratislava | `highway=proposed` | self: excluded / X_lifecycle | proposed: ok: excluded. highway=proposed (proposed=cycleway) |
| [126367668](https://www.openstreetmap.org/way/126367668)  | bratislava | `cycleway:left=no`<br>`cycleway:right=separate`<br>`highway=tertiary` | left: excluded / X_no<br>right: excluded / X_separate | proposed: ok: excluded both. left cycleway=no; right separate (the path is mapped as its own way) |
| [177916468](https://www.openstreetmap.org/way/177916468) Devínska cesta | bratislava | `cycleway=lane`<br>`highway=tertiary` | left: D / D_lane<br>right: D / D_lane | proposed: ok: D both. Plain painted lane cycleway=lane |
| [1311124898](https://www.openstreetmap.org/way/1311124898) Hany Meličkovej | bratislava | `bicycle:lanes:forward=yes|designated`<br>`cycleway:right=shared_busway`<br>`highway=tertiary` | no output | proposed: wrong: should be E right. psv:lanes:forward and bicycle:lanes:forward (yes, designated) describe a bus lane open to cycles; cycleway:right=shared_busway misspells share_busway (0.16 km). A mistag to fix in OSM, not proposed for v3 (like the M5 "considered, not proposed" values) |
| [1050603989](https://www.openstreetmap.org/way/1050603989) Furdekova | bratislava | `cycleway:left=separate`<br>`cycleway:right=advisory`<br>`highway=tertiary` | left: excluded / X_separate | proposed: ok left (excluded, separate); right wrong: should be D advisory right. cycleway:right=advisory is not a cycleway value (wiki Key:cycleway); it means lane + cycleway:lane=advisory. Bratislava has 0.46 km of cycleway[:side]=advisory in its top unmatched signatures (Oslo 0.44 km, listed as considered, not proposed); a v3 rule is your call |
| [24836980](https://www.openstreetmap.org/way/24836980) Mamateyova | bratislava | `cycleway:left=advisory`<br>`highway=tertiary` | no output | proposed: wrong: should be D advisory left. Same cycleway:left=advisory case as Furdekova; not proposed for v3 unless you decide otherwise |
| [34609152](https://www.openstreetmap.org/way/34609152)  | bratislava | `bicycle=designated`<br>`highway=cycleway`<br>`segregated=no` | self: B / B_cycleway_foot | proposed: ok: B. Shared foot/cycle path, highway=cycleway + foot=designated, segregated=no |
| [223471544](https://www.openstreetmap.org/way/223471544) Pionierska | bratislava | `cycleway=lane`<br>`cycleway:lane=advisory`<br>`highway=tertiary` | left: D / D_lane_advisory<br>right: D / D_lane_advisory | proposed: ok: D both, advisory. cycleway=lane + cycleway:lane=advisory |
| [373209244](https://www.openstreetmap.org/way/373209244) Hodonínska | bratislava | `cycleway:left=share_busway`<br>`highway=primary` | left: E / E_bus | proposed: ok: E left. Bus lane open to cycles (cycleway:left=share_busway; lanes:psv:backward=1) |
| [227951535](https://www.openstreetmap.org/way/227951535) Zidiny | bratislava | `bicycle=designated`<br>`bicycle_road=yes`<br>`highway=residential` | self: E / E_cycle_street | proposed: ok: E. Cycle street, bicycle_road=yes (maxspeed:type SK:bicycle_road) |

Map data © OpenStreetMap contributors, ODbL 1.0
