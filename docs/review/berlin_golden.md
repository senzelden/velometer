# Berlin golden set: review sheet

Source: Overpass API, fetched 2026-10-01T13:55:17Z; © OpenStreetMap contributors, ODbL 1.0. Classifier: v1.

For each way, check the proposed `side:tier (rule)` against the tags and the OSM link, then set `confirmed: true` (and fix `proposed`) per way in `tests/fixtures/berlin_golden.yaml`. Map: `berlin_golden.png`.

## kantstrasse (8)

| way | name | highway | key cycling tags | proposed |
|---|---|---|---|---|
| [4396016](https://www.openstreetmap.org/way/4396016) | Kantstraße | secondary | `cycleway:both=lane`<br>`cycleway:both:buffer:left=no`<br>`cycleway:both:buffer:right=0.6`<br>`cycleway:both:lane=advisory`<br>`cycleway:both:marking:both=dashed_line`<br>`cycleway:both:oneway=yes`<br>`cycleway:both:separation:left=no`<br>`cycleway:both:surface=asphalt`<br>`cycleway:both:surface:colour=none`<br>`cycleway:both:traffic_mode:right=parking`<br>`cycleway:both:traffic_sign=none`<br>`cycleway:left:mapillary=4810484855717531`<br>`cycleway:left:width=1.4`<br>`cycleway:right:mapillary=1673163466359852`<br>`cycleway:right:width=1.5`<br>`foot=use_sidepath`<br>`sidewalk:both=separate` | left:D (D_lane_advisory)<br>right:D (D_lane_advisory) |
| [4396321](https://www.openstreetmap.org/way/4396321) | Kantstraße | secondary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:bicycle=designated`<br>`cycleway:right:buffer:left=no`<br>`cycleway:right:buffer:right=yes`<br>`cycleway:right:lane=advisory`<br>`cycleway:right:marking:left=dashed_line`<br>`cycleway:right:marking:right=no`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:separation:both=none`<br>`cycleway:right:traffic_mode:right=psv`<br>`cycleway:right:traffic_sign=none`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane_advisory) |
| [28658322](https://www.openstreetmap.org/way/28658322) | Kantstraße | secondary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:bicycle=designated`<br>`cycleway:right:buffer:both=no`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:marking:both=dashed_line`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:separation:both=no`<br>`cycleway:right:surface:colour=red`<br>`cycleway:right:traffic_sign=DE:237`<br>`cycleway:right:width=2.5`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane) |
| [28658323](https://www.openstreetmap.org/way/28658323) | Kantstraße | secondary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:bicycle=designated`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:marking:left=solid_line`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:separation:right=parking_lane`<br>`cycleway:right:traffic_sign=DE:237`<br>`cycleway:right:width=2.2`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane) |
| [28658327](https://www.openstreetmap.org/way/28658327) | Kantstraße | secondary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:bicycle=designated`<br>`cycleway:right:buffer:left=no`<br>`cycleway:right:buffer:right=yes`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:marking:left=solid_line`<br>`cycleway:right:marking:right=dashed_line`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:separation:both=none`<br>`cycleway:right:traffic_mode:right=parking`<br>`cycleway:right:traffic_sign=DE:237`<br>`cycleway:right:width=2`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane) |
| [32909622](https://www.openstreetmap.org/way/32909622) | Kantstraße | secondary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:bicycle=designated`<br>`cycleway:right:buffer:left=1`<br>`cycleway:right:buffer:right=no`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:mapillary=770197652601018`<br>`cycleway:right:marking:left=solid_line`<br>`cycleway:right:marking:right=no`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:surface:colour=none`<br>`cycleway:right:temporary=yes`<br>`cycleway:right:traffic_mode:left=parking`<br>`cycleway:right:traffic_sign=DE:237`<br>`cycleway:right:width=2`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane) |
| [32909623](https://www.openstreetmap.org/way/32909623) | Kantstraße | secondary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:bicycle=designated`<br>`cycleway:right:buffer:left=1`<br>`cycleway:right:buffer:right=no`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:mapillary=1119661527022341`<br>`cycleway:right:marking:left=solid_line`<br>`cycleway:right:marking:right=no`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:surface:colour=none`<br>`cycleway:right:temporary=yes`<br>`cycleway:right:traffic_mode:left=parking`<br>`cycleway:right:traffic_sign=DE:237`<br>`cycleway:right:width=2`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane) |
| [32909627](https://www.openstreetmap.org/way/32909627) | Kantstraße | secondary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:bicycle=designated`<br>`cycleway:right:buffer:left=1`<br>`cycleway:right:buffer:right=no`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:mapillary=1514931503284233`<br>`cycleway:right:marking:left=solid_line`<br>`cycleway:right:marking:right=no`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:surface:colour=none`<br>`cycleway:right:temporary=yes`<br>`cycleway:right:traffic_mode:left=parking`<br>`cycleway:right:traffic_sign=DE:237`<br>`cycleway:right:width=2`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane) |

## ollenhauerstrasse (6)

| way | name | highway | key cycling tags | proposed |
|---|---|---|---|---|
| [23125889](https://www.openstreetmap.org/way/23125889) | Ollenhauerstraße | secondary | `cycleway:left=no`<br>`cycleway:right=share_busway`<br>`cycleway:right:conditional=share_busway @ (Mo-Fr 06:00-09:00)`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:width=2.8`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:E (E_bus) |
| [37304507](https://www.openstreetmap.org/way/37304507) | Ollenhauerstraße | secondary | `cycleway:both=no`<br>`cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:buffer:both=no`<br>`cycleway:right:lane=crossing`<br>`cycleway:right:marking:both=dashed_line`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:surface:colour=none`<br>`cycleway:right:traffic_sign=none`<br>`cycleway:right:width=1.5`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane) |
| [39965120](https://www.openstreetmap.org/way/39965120) | Ollenhauerstraße | secondary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:buffer:both=no`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:marking:both=solid_line`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:surface:colour=none`<br>`cycleway:right:traffic_sign=none`<br>`cycleway:right:width=2`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane) |
| [39965422](https://www.openstreetmap.org/way/39965422) | Ollenhauerstraße | secondary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:lane=advisory`<br>`cycleway:right:marking:left=dashed_line`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:surface:colour=none`<br>`cycleway:right:traffic_sign=none`<br>`cycleway:right:width=1.5`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane_advisory) |
| [39965423](https://www.openstreetmap.org/way/39965423) | Ollenhauerstraße | secondary | `cycleway:left=no`<br>`cycleway:right=separate`<br>`cycleway:right:lane=advisory`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:excluded (X_separate) |
| [39965424](https://www.openstreetmap.org/way/39965424) | Ollenhauerstraße | secondary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:buffer:both=no`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:marking:both=solid_line`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:surface:colour=none`<br>`cycleway:right:traffic_sign=none`<br>`cycleway:right:width=2`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane) |

## unter_den_eichen (6)

| way | name | highway | key cycling tags | proposed |
|---|---|---|---|---|
| [4484276](https://www.openstreetmap.org/way/4484276) | Unter den Eichen | primary_link | `cycleway=no`<br>`foot=no`<br>`oneway=yes`<br>`sidewalk=no` | right:excluded (X_no) |
| [4484277](https://www.openstreetmap.org/way/4484277) | Unter den Eichen | primary | `cycleway:left=no`<br>`cycleway:right=separate`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:excluded (X_separate) |
| [4484278](https://www.openstreetmap.org/way/4484278) | Unter den Eichen | primary | `cycleway:both=no`<br>`oneway=yes`<br>`sidewalk=no` | left:excluded (X_no)<br>right:excluded (X_no) |
| [4484279](https://www.openstreetmap.org/way/4484279) | Unter den Eichen | primary | `cycleway:both=no`<br>`oneway=yes`<br>`sidewalk=no` | left:excluded (X_no)<br>right:excluded (X_no) |
| [7744347](https://www.openstreetmap.org/way/7744347) | Unter den Eichen | residential | `cycleway:both=no`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:excluded (X_no) |
| [14851818](https://www.openstreetmap.org/way/14851818) | Unter den Eichen | primary_link | `cycleway:left=no`<br>`cycleway:right=separate`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:excluded (X_separate) |

## karl_marx_allee (6)

| way | name | highway | key cycling tags | proposed |
|---|---|---|---|---|
| [4615614](https://www.openstreetmap.org/way/4615614) | Karl-Marx-Allee | primary | `bicycle=use_sidepath`<br>`cycleway:left=no`<br>`cycleway:right=separate`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:excluded (X_separate) |
| [4615777](https://www.openstreetmap.org/way/4615777) | Karl-Marx-Allee | primary | `bicycle=use_sidepath`<br>`cycleway:left=no`<br>`cycleway:right=separate`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:excluded (X_separate) |
| [4782480](https://www.openstreetmap.org/way/4782480) | Karl-Marx-Allee | primary | `bicycle=use_sidepath`<br>`cycleway:left=no`<br>`cycleway:right=separate`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:excluded (X_separate) |
| [28133482](https://www.openstreetmap.org/way/28133482) | Karl-Marx-Allee | living_street |  | - |
| [29177662](https://www.openstreetmap.org/way/29177662) | Karl-Marx-Allee | primary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:bicycle=designated`<br>`cycleway:right:buffer:left=2.5`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:marking:left=barred_area`<br>`cycleway:right:separation:left=no`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:surface:colour=red`<br>`cycleway:right:traffic_sign=DE:237`<br>`cycleway:right:width=2.3`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane) |
| [29183328](https://www.openstreetmap.org/way/29183328) | Karl-Marx-Allee | service |  | - |

## fahrradstrasse (4)

| way | name | highway | key cycling tags | proposed |
|---|---|---|---|---|
| [4083461](https://www.openstreetmap.org/way/4083461) | Holsteiner Ufer | unclassified | `bicycle=designated`<br>`bicycle_road=yes`<br>`cycleway:both=no`<br>`oneway=no`<br>`sidewalk:left=no`<br>`sidewalk:right=separate`<br>`sidewalk:right:surface=paving_stones` | self:E (E_cycle_street)<br>left:excluded (X_no)<br>right:excluded (X_no) |
| [4395584](https://www.openstreetmap.org/way/4395584) | Prinzregentenstraße | residential | `bicycle=designated`<br>`bicycle_road=yes`<br>`foot=use_sidepath`<br>`sidewalk=separate` | self:E (E_cycle_street) |
| [4492002](https://www.openstreetmap.org/way/4492002) | Fasanenplatz | residential | `bicycle=designated`<br>`bicycle_road=yes`<br>`cycleway:both=no`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`oneway:bicycle=no`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | self:E (E_cycle_street)<br>left:excluded (X_no)<br>right:excluded (X_no) |
| [4492007](https://www.openstreetmap.org/way/4492007) | Fasanenstraße | residential | `bicycle=designated`<br>`bicycle_road=yes`<br>`cycleway:both=no`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`oneway:bicycle=no`<br>`sidewalk=separate` | self:E (E_cycle_street)<br>left:excluded (X_no)<br>right:excluded (X_no) |

## hochbord_shared (4)

| way | name | highway | key cycling tags | proposed |
|---|---|---|---|---|
| [106652853](https://www.openstreetmap.org/way/106652853) |  | footway | `bicycle=designated`<br>`foot=designated`<br>`footway=sidewalk`<br>`oneway=no`<br>`segregated=no` | self:B (B_path) |
| [233227500](https://www.openstreetmap.org/way/233227500) | Walter-Nicklitz-Promenade | footway | `bicycle=designated`<br>`foot=designated`<br>`footway=sidewalk`<br>`oneway=no`<br>`segregated=no` | self:B (B_path) |
| [403679183](https://www.openstreetmap.org/way/403679183) |  | footway | `bicycle=designated`<br>`cycleway:lanes=2`<br>`cycleway:surface=asphalt`<br>`cycleway:surface:colour=none`<br>`cycleway:width=3`<br>`footway=sidewalk`<br>`footway:surface=paving_stones`<br>`oneway=no`<br>`segregated=yes` | self:B (B_path_segregated) |
| [479700952](https://www.openstreetmap.org/way/479700952) |  | footway | `bicycle=designated`<br>`cycleway:surface=asphalt`<br>`cycleway:surface:colour=none`<br>`cycleway:width=1.4`<br>`foot=designated`<br>`footway=sidewalk`<br>`footway:surface=sett`<br>`oneway:bicycle=yes`<br>`segregated=yes` | self:B (B_path_segregated) |

## sidewalk_cycleway (2)

| way | name | highway | key cycling tags | proposed |
|---|---|---|---|---|
| [1083897477](https://www.openstreetmap.org/way/1083897477) |  | cycleway | `cycleway=sidewalk`<br>`oneway=yes` | self:A (A_cycleway) |
| [1164113868](https://www.openstreetmap.org/way/1164113868) |  | cycleway | `cycleway=sidewalk`<br>`oneway=yes` | self:A (A_cycleway) |

## protected_lane (4)

| way | name | highway | key cycling tags | proposed |
|---|---|---|---|---|
| [25778031](https://www.openstreetmap.org/way/25778031) | Wisbyer Straße | primary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:lane=advisory`<br>`cycleway:right:separation=dashed_line`<br>`cycleway:right:surface:colour=green`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:D (D_lane_advisory) |
| [71282500](https://www.openstreetmap.org/way/71282500) | Hauptstraße | primary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:marking:right=no`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:separation=flex_post`<br>`cycleway:right:separation:left=dashed_line`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:traffic_sign=none`<br>`cycleway:right:width=2.6`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:C (C_lane_physical) |
| [71401494](https://www.openstreetmap.org/way/71401494) | Hauptstraße | primary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:marking:right=no`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:separation=flex_post`<br>`cycleway:right:separation:left=dashed_line`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:traffic_sign=none`<br>`cycleway:right:width=2.6`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:C (C_lane_physical) |
| [110450330](https://www.openstreetmap.org/way/110450330) | Hauptstraße | primary | `cycleway:left=no`<br>`cycleway:right=lane`<br>`cycleway:right:lane=exclusive`<br>`cycleway:right:marking:right=no`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:separation=flex_post`<br>`cycleway:right:separation:left=dashed_line`<br>`cycleway:right:surface=asphalt`<br>`cycleway:right:traffic_sign=none`<br>`cycleway:right:width=2.6`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:C (C_lane_physical) |

## busway (4)

| way | name | highway | key cycling tags | proposed |
|---|---|---|---|---|
| [4377785](https://www.openstreetmap.org/way/4377785) | Hardenbergstraße | secondary | `cycleway:left=no`<br>`cycleway:right=share_busway`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:traffic_sign=DE:245,1022-10,Zusatzzeichen`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:E (E_bus) |
| [4389412](https://www.openstreetmap.org/way/4389412) | Kurfürstendamm | secondary | `cycleway:left=no`<br>`cycleway:right=share_busway`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:separation:left=no`<br>`cycleway:right:surface:colour=no`<br>`cycleway:right:traffic_sign=DE:245,Zusatzzeichen`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:E (E_bus) |
| [4395698](https://www.openstreetmap.org/way/4395698) | Potsdamer Straße | primary | `cycleway:left=no`<br>`cycleway:right=share_busway`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:traffic_sign=DE:245,1022-10,1026-30,1024-14`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:E (E_bus) |
| [4395950](https://www.openstreetmap.org/way/4395950) | Martin-Luther-Straße | primary | `cycleway:left=no`<br>`cycleway:right=share_busway`<br>`cycleway:right:oneway=yes`<br>`cycleway:right:traffic_sign=DE:245,1022-10,Zusatzzeichen`<br>`cycleway:right:width=3.2`<br>`foot=use_sidepath`<br>`oneway=yes`<br>`sidewalk:left=no`<br>`sidewalk:right=separate` | left:excluded (X_no)<br>right:E (E_bus) |

## separate (4)

| way | name | highway | key cycling tags | proposed |
|---|---|---|---|---|
| [4067883](https://www.openstreetmap.org/way/4067883) | Jafféstraße | secondary | `cycleway:both=separate`<br>`foot=use_sidepath`<br>`sidewalk:left=separate`<br>`sidewalk:right=no` | left:excluded (X_separate)<br>right:excluded (X_separate) |
| [4068188](https://www.openstreetmap.org/way/4068188) | Wasgensteig | residential | `cycleway:both=separate`<br>`sidewalk=separate` | left:excluded (X_separate)<br>right:excluded (X_separate) |
| [4071972](https://www.openstreetmap.org/way/4071972) | Klemkestraße | tertiary | `bicycle=optional_sidepath`<br>`cycleway:both=separate`<br>`foot=use_sidepath`<br>`sidewalk:both=separate` | left:excluded (X_separate)<br>right:excluded (X_separate) |
| [4316780](https://www.openstreetmap.org/way/4316780) | Spanische Allee | secondary | `bicycle=optional_sidepath`<br>`cycleway:both=separate`<br>`sidewalk:both=separate` | left:excluded (X_separate)<br>right:excluded (X_separate) |
