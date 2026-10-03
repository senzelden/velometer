# Golden samples: SE

Open each way, compare the tags with our tier and rule, write the verdict (ok, or what is wrong), then set `confirmed: true` in the yaml for the ways you agree with.

| way | city | tags | our tier / rule | verdict |
|---|---|---|---|---|
| [24404271](https://www.openstreetmap.org/way/24404271)  | stockholm | `bicycle=designated`<br>`cycleway:surface=asphalt`<br>`highway=cycleway`<br>`segregated=yes` | self: A / A_cycleway | proposed: ok: A. Gång- och cykelbana with segregated=yes: cyclists have their own part |
| [151884980](https://www.openstreetmap.org/way/151884980) Söderledstunneln | stockholm | `bicycle=no`<br>`cycleway:both=no`<br>`highway=trunk` | left: excluded / X_no<br>right: excluded / X_no | proposed: ok: excluded. Tunnel trunk road, bicycle=no |
| [39822770](https://www.openstreetmap.org/way/39822770)  | stockholm | `bicycle=designated`<br>`highway=cycleway`<br>`segregated=no` | self: B / B_cycleway_foot | proposed: ok: B. Gång- och cykelbana, foot=designated, segregated=no |
| [1367954012](https://www.openstreetmap.org/way/1367954012)  | stockholm | `bicycle=no`<br>`highway=path` | self: excluded / X_bicycle_no | proposed: ok: excluded. bicycle=no |
| [249421858](https://www.openstreetmap.org/way/249421858) Bogårdsvägen | stockholm | `cycleway:both=separate`<br>`highway=tertiary` | left: excluded / X_separate<br>right: excluded / X_separate | proposed: ok: excluded (separate). Cycle track mapped as its own way, counted there |
| [81126534](https://www.openstreetmap.org/way/81126534) Skärholmstunneln (Förbifart Stockholm) | stockholm | `highway=construction` | self: excluded / X_lifecycle | proposed: ok: excluded. Under construction (Förbifart Stockholm) |
| [806880345](https://www.openstreetmap.org/way/806880345) Svartlösavägen | stockholm | `cycleway=path`<br>`highway=tertiary` | no output | proposed: ok: not counted. cycleway=path is no documented value (likely a separately mapped path, i.e. separate); 2.13 km |
| [4079732](https://www.openstreetmap.org/way/4079732) Askrikegatan | stockholm | `cycleway:left=exclusive`<br>`cycleway:left:oneway=-1`<br>`highway=residential`<br>`oneway:bicycle=no` | no output | proposed: ok: not counted. cycleway:left=exclusive is a mistag of cycleway:left=lane + cycleway:left:lane=exclusive (a D contraflow lane); 0.40 km, too small for a rule |
| [233028188](https://www.openstreetmap.org/way/233028188) Storängsvägen | stockholm | `cycleway=segregated`<br>`highway=unclassified` | no output | proposed: ok: not counted. cycleway=segregated is no documented value; 0.32 km |
| [149487167](https://www.openstreetmap.org/way/149487167) Gamla Tyresövägen | stockholm | `cycleway:both=track`<br>`highway=tertiary` | left: A / A_track_side<br>right: A / A_track_side | proposed: ok: A both sides. cycleway:both=track |
| [198689124](https://www.openstreetmap.org/way/198689124) Sockenvägen | stockholm | `bicycle=yes`<br>`cycleway:right=lane`<br>`highway=tertiary` | right: D / D_lane | proposed: ok: D right. Painted lane |
| [120132761](https://www.openstreetmap.org/way/120132761)  | stockholm | `bicycle=designated`<br>`highway=path`<br>`oneway:bicycle=yes`<br>`segregated=yes` | self: B / B_path_segregated | proposed: ok: B. highway=path, foot=designated, segregated=yes: side-by-side foot/cycle path (B_path_segregated) |

Map data © OpenStreetMap contributors, ODbL 1.0
