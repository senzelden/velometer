# Golden samples: NO

Open each way, compare the tags with our tier and rule, write the verdict (ok, or what is wrong), then set `confirmed: true` in the yaml for the ways you agree with.

| way | city | tags | our tier / rule | verdict |
|---|---|---|---|---|
| [119146754](https://www.openstreetmap.org/way/119146754)  | oslo | `bicycle=designated`<br>`highway=cycleway`<br>`segregated=no` | self: B / B_cycleway_foot | proposed: ok: B. Gang- og sykkelvei (shared foot/cycle path), segregated=no |
| [27071517](https://www.openstreetmap.org/way/27071517) Grefsenkollveien | oslo | `bicycle=yes`<br>`cycleway:both=no`<br>`highway=unclassified` | left: excluded / X_no<br>right: excluded / X_no | proposed: ok: excluded. cycleway:both=no |
| [160459177](https://www.openstreetmap.org/way/160459177) Sognsveien | oslo | `cycleway=lane`<br>`highway=secondary` | left: D / D_lane<br>right: D / D_lane | proposed: ok: D both sides. Sykkelfelt (painted lane) |
| [130447630](https://www.openstreetmap.org/way/130447630)  | oslo | `bicycle=dismount`<br>`highway=path` | self: excluded / X_bicycle_no | proposed: ok: excluded. bicycle=dismount |
| [118364891](https://www.openstreetmap.org/way/118364891) Tour de Finance | oslo | `bicycle=designated`<br>`highway=cycleway`<br>`segregated=yes` | self: A / A_cycleway | proposed: ok: A. Cycleway with segregated=yes |
| [142320283](https://www.openstreetmap.org/way/142320283)  | oslo | `highway=footway` | self: excluded / X_area | proposed: ok: excluded. area=yes footway |
| [1262980246](https://www.openstreetmap.org/way/1262980246) Frysjaveien | oslo | `bicycle:lanes:backward=yes`<br>`bicycle:lanes:forward=yes|designated`<br>`cycleway:lanes:forward=no|lane`<br>`cycleway:left=no`<br>`cycleway:right=advisory`<br>`cycleway:right:marking=dashed_line`<br>`cycleway:surface=asphalt`<br>`cycleway:surface:colour=red`<br>`highway=tertiary` | left: excluded / X_no | proposed: ok, with a gap: left excluded (no) is right; right side is not counted because cycleway:right=advisory is no documented value (meant cycleway:right=lane + cycleway:right:lane=advisory, a D advisory lane); 0.44 km, too small for a rule |
| [136540510](https://www.openstreetmap.org/way/136540510)  | oslo | `bicycle=designated`<br>`highway=footway` | self: B / B_path | proposed: ok: B. Sidewalk with bicycle=designated: shared with pedestrians |
| [863615478](https://www.openstreetmap.org/way/863615478) Grefsenveien | oslo | `cycleway=track`<br>`highway=secondary` | left: A / A_track_side<br>right: A / A_track_side | proposed: ok: A both sides. cycleway=track (sykkelvei langs veg) |
| [4361293](https://www.openstreetmap.org/way/4361293) Ryenbergveien | oslo | `cycleway:left=no`<br>`cycleway:right=shoulder`<br>`highway=residential` | left: excluded / X_no<br>right: excluded / X_shoulder | proposed: ok: excluded. Shoulder is not cycling infrastructure (v2 X_shoulder); left no |
| [3426698](https://www.openstreetmap.org/way/3426698) Geitmyrsveien | oslo | `cycleway:both=shared_lane`<br>`cycleway:both:lane=pictogram`<br>`cycleway:left:oneway=-1`<br>`highway=residential`<br>`oneway:bicycle=no` | left: excluded / X_shared_lane<br>right: excluded / X_shared_lane | proposed: ok: excluded. shared_lane with pictograms (sykkelpiktogram), no own space |

Map data © OpenStreetMap contributors, ODbL 1.0
