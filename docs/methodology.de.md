> Erzeugt mit `velometer report methodology` aus der Konfiguration und der Datenbank. Nicht von Hand bearbeiten; `velometer report methodology --check` schlägt fehl, wenn diese Datei veraltet ist. English version: [methodology.md](methodology.md).

# Methodik

velometer misst geschützte Radverkehrsanlagen in europäischen Städten anhand von OpenStreetMap (OSM). Gemessen wird für jährliche Stände und für einen aktuellen Stand. Die Ergebnisse werden veröffentlichten Ranglisten und amtlichen Zahlen gegenübergestellt. Die eigene Auswertung ist die Primärquelle aller veröffentlichten Zahlen. Externe Zahlen dienen nur dem Vergleich und werden nie mit den eigenen Zahlen vermischt [ADR 0001].

Alle OSM-Längen sind **kartierte Kilometer**, keine gebauten Kilometer. Sie zeigen, was in OSM erfasst ist, nicht, was gebaut wurde [ADR 0006].

## Was gemessen wird

Klassifiziert wird jede **Seite** eines Wegs, nicht der Weg als Ganzes. Jede Straße wird in eine linke und eine rechte Seite zerlegt. Grundlage sind die Tags `cycleway`, `cycleway:both`, `cycleway:left` und `cycleway:right` sowie die älteren Tags `cycleway=opposite*` und `sidewalk:*:bicycle`. Eigenständig erfasste Wege, etwa ein `highway=cycleway`, werden als solche klassifiziert [ADR 0002].

Jede Seite erhält eine Stufe oder wird ausgeschlossen:

| Stufe | Bedeutung |
|---|---|
| A | baulich getrennter Radweg |
| B | Geh- und Radweg (gemeinsam oder getrennt) |
| C | Radfahrstreifen mit baulicher Trennung zum Kfz-Verkehr |
| D | markierter Radfahrstreifen, einschließlich Schutzstreifen |
| E | Fahrradstraße sowie für den Radverkehr freigegebene Busspuren |
| `excluded` (ausgeschlossen) | für die Diagnose erfasst, in keiner Kennzahlvariante gezählt |

Die Stufen leiten sich aus der Tag-Logik der ECF-Methode QECIO ab, mit dokumentierten Abweichungen. So gilt ein Geh- und Radweg mit `segregated=yes` (getrennter Geh- und Radweg) hier als Stufe B, während QECIO ihn als Radweg zählt [ADR 0002].

Für jede Seite werden zwei Längen gespeichert. Auf der Basis **`per_side`** zählt jede Straßenseite mit ihrer vollen Länge; eine Straße mit Radwegen auf beiden Seiten zählt also doppelt. Auf der Basis **`qecio_weighted`** zählen Anlagen für nur eine Fahrtrichtung zur Hälfte, wie bei QECIO [ADR 0002]. Längen werden im projizierten Koordinatensystem der jeweiligen Stadt berechnet, nie in Grad.

Die Regeln sind Daten, kein Code. Jede Regeländerung ergibt eine neue Klassifikatorversion, und jeder Lauf speichert die verwendete Version [ADR 0005].

<!-- generated:classifier -->
- Klassifikator der Auswertung: **v4** (`config/classifier/v4.yaml`)
- Parameter `plain_cycleway_on_oneway`: `traffic_side`
- Trennzeichen zwischen Werten: `;`, `,`
<!-- /generated:classifier -->

### Klassifikationsregeln

Die Regeln gelten in der aufgeführten Reihenfolge; die erste passende Regel entscheidet. Regeln für `road_side` gelten für Straßenseiten, Regeln für `standalone` für eigenständig erfasste Wege, Regeln für `any` für beide. Auf einer Straßenseite sind `cycleway` und `cycleway:*` die Tags der Seite selbst, `sidewalk_bicycle` ist ihr Wert für `sidewalk:*:bicycle`, und `road:*` sind Tags der Straße. Namen in spitzen Klammern sind Wertelisten der Klassifikatordatei.

<!-- generated:rules -->
| Regel | Stufe | Untertyp | Gilt für | Bedingung |
|---|---|---|---|---|
| `X_lifecycle` | `excluded` | lifecycle | standalone | `highway in [construction, proposed]` |
| `X_construction_tag` | `excluded` | lifecycle | standalone | `construction=yes` |
| `X_area` | `excluded` | area | standalone | `area=yes` |
| `X_road_area` | `excluded` | area | road_side | `road:area=yes` |
| `X_private` | `excluded` | private | standalone | `access in [private, no] and bicycle not in [yes, designated, permissive]` |
| `X_road_private` | `excluded` | private | road_side | `road:access in [private, no] and road:bicycle not in [yes, designated, permissive]` |
| `X_road_construction` | `excluded` | lifecycle | road_side | `(road:construction=yes or cycleway in [construction, proposed])` |
| `X_bicycle_no` | `excluded` | bicycle_no | standalone | `bicycle in [no, dismount]` |
| `X_mtb_trail` (geändert gegenüber v3) | `excluded` | mtb | standalone | `highway in [path, cycleway, footway] and (mtb:scale* present or mtb in [yes, designated, permissive] or mtb:type present or cycling=mtb)` |
| `X_separate` | `excluded` | separate | road_side | `cycleway=separate` |
| `B_track_shared` | `B` | shared | road_side | `cycleway=track and cycleway:segregated=no` |
| `A_track_side` | `A` |  | road_side | `cycleway=track` |
| `B_crossing` (geändert gegenüber v3) | `B` |  | standalone | `highway=footway and footway=crossing and bicycle=designated` |
| `A_segregated` (geändert gegenüber v3) | `A` |  | standalone | `segregated=yes and (highway=cycleway or highway in [path, footway, pedestrian] and bicycle=designated)` |
| `B_shared` (geändert gegenüber v3) | `B` |  | standalone | `(highway=cycleway and foot in [designated, yes, permissive] or highway in [path, footway, pedestrian] and bicycle=designated and foot not in [no])` |
| `A_cycle_only` (geändert gegenüber v3) | `A` |  | standalone | `(highway=cycleway or highway in [path, footway, pedestrian] and bicycle=designated and foot in [no])` |
| `B_sidewalk_designated` | `B` | sidewalk | road_side | `sidewalk_bicycle=designated and cycleway not in [lane, share_busway]` |
| `B_share_sidewalk` | `B` | sidewalk | road_side | `cycleway=share_sidewalk` |
| `C_lane_physical` | `C` |  | road_side | `cycleway=lane and cycleway:separation:traffic in <physical_separation>` |
| `D_lane_advisory` | `D` | advisory | road_side | `cycleway=lane and cycleway:lane in [advisory, pictogram]` |
| `D_soft_lane` | `D` | advisory | road_side | `cycleway=soft_lane` |
| `D_advisory` | `D` | advisory | road_side | `cycleway=advisory` |
| `D_lane` | `D` |  | road_side | `cycleway=lane` |
| `E_cycle_street` | `E` | cycle_street | standalone | `(bicycle_road=yes or cyclestreet=yes or cycle_street=yes)` |
| `E_bus` | `E` | bus | road_side | `cycleway=share_busway` |
| `X_no` | `excluded` | no | road_side | `cycleway in [no, none]` |
| `X_shared_lane` | `excluded` | shared_lane | road_side | `cycleway in [shared_lane, shared]` |
| `X_sidewalk_bicycle_permitted` | `excluded` | sidewalk_permitted | road_side | `sidewalk_bicycle in [yes, permissive]` |
| `X_use_sidepath` | `excluded` | use_sidepath | road_side | `cycleway=use_sidepath` |
| `X_shoulder` | `excluded` | shoulder | road_side | `cycleway=shoulder` |
| `X_crossing` | `excluded` | crossing | road_side | `cycleway=crossing` |
| `X_untyped` | `excluded` | untyped | road_side | `cycleway=yes` |

Entfallen seit v3: `A_cycleway`, `A_path_cycle_only`, `B_cycleway_foot`, `B_path` und `B_path_segregated`.
<!-- /generated:rules -->

## Hauptkennzahl und Kennzahlvarianten

Die Hauptkennzahl ist die Länge der Stufen A und B, je Seite gezählt, je 100 km Hauptverkehrsstraßen ohne Autobahnen [ADR 0003]. Hauptverkehrsstraßen sind Straßen der Klassen trunk, primary, secondary und tertiary samt ihren Zu- und Abfahrten (`*_link`). Autobahnen bleiben außen vor, weil sie für den Radverkehr nicht nutzbar sind. Eine Straße mit getrennten Richtungsfahrbahnen zählt einmal.

„Geschützt“ wird als frei wählbare Summe von Stufen ausgewiesen, als sogenannte Kennzahlvariante. Jede Kennzahlvariante legt die gezählten Stufen, die Längenbasis und die Straßenklasse als Bezugsgröße fest. So lassen sich die Definitionen anderer Veröffentlichungen mit den eigenen Daten nachbilden [ADR 0002, ADR 0003]:

- `ours_headline` ist die Hauptkennzahl.
- `ecf_qecio` folgt ECF QECIO v2.10. Sie zählt die Stufen A bis D auf der QECIO-Basis und bezieht sie auf die Hauptverkehrsstraßen einschließlich Autobahnen. Straßen mit getrennten Richtungsfahrbahnen zählen dabei wie bei QECIO je Fahrbahn.
- `clean_cities_2025` folgt der OSM-Ersatzmethode von Clean Cities 2025. Sie bezieht die Stufen A und B auf alle öffentlichen Straßen.

<!-- generated:presets -->
| Kennzahlvariante | Stufen | Längenbasis | Bezugsgröße |
|---|---|---|---|
| `ours_headline` | A+B | per_side | `main_excl_motorway` |
| `ecf_qecio` | A+B+C+D | qecio_weighted | `main_incl_motorway_raw` |
| `clean_cities_2025` | A+B | per_side (Parameter `clean_cities_basis`) | `all_public` |
<!-- /generated:presets -->

Eine Kennzahlvariante, deren Basis ein Parameter ist, wird auf beiden Basen berechnet und gespeichert. Der Parameter wählt nur die ausgewiesene Basis [ADR 0003; M2 R15]. Neben den Quoten werden absolute Kilometer und Kilometer je 100.000 Einwohner ausgewiesen.

## Gebietsgrenzen und Einwohnerzahl

Jede Stadt wird auf zwei Gebietsgrenzen berechnet [ADR 0004]:

- **LAU** ist die Stadtgrenze: die lokale Verwaltungseinheit von Eurostat GISCO, Stand 2024. Sie ist der Standard. Fehlt ein sauberes LAU-Polygon, tritt die administrative OSM-Relation an seine Stelle.
- **FUA** ist der funktionale Stadtraum (Functional Urban Area), also die Stadt mit ihrem Pendlereinzugsgebiet. Er dient als Robustheitsprüfung.

Verglichen wird nur innerhalb derselben Grenzart. Die Einwohnerzahl der LAU stammt von Eurostat. Besteht eine Stadt aus mehreren LAU (`lau_codes`), gilt die Summe ihrer Werte, und nur, wenn jede einen Wert hat. Fehlt der LAU-Wert, liefert ihn die amtliche Einwohnerzahl des nationalen Statistikamts, mit Jahr und URL belegt in `config/cities.yaml` (`population_override`). Fehlt auch diese, liefert ihn die deckungsgleiche NUTS-3-Einheit [ADR 0004]. Der Code kann außerdem auf die Einwohnerzahl der Städtestatistik Urban Audit von Eurostat zurückgreifen (`urb_cpop1`, je Stadt als `population_urau` gesetzt), doch keine konfigurierte Stadt nutzt das: Die Urban-Audit-Städte erwiesen sich als erweiterte Städte, nicht als die Gemeinde [Entscheidung zur Einwohnerzahl vom 3. Oktober 2026, `docs/superpowers/rulings-m5.md`; `population` in `sources/boundaries.py`]. Für alle Stichjahre gilt derselbe Einwohnerwert [M3-Spezifikation, Entscheidung 2]. FUA-Läufe führen keine Einwohnerzahl; für die FUA gibt es daher keinen Wert je 100.000 Einwohner [M4-Spezifikation §4.4].

Die Tabelle nennt je Stadt und Grenzart die OSM-Zeitstempel der hier verwendeten Läufe, den Verlaufsdatensatz und die Einwohnerzahl.

<!-- generated:cities -->
| Stadt | Grenzart | Aktueller Lauf (OSM-Zeitstempel) | Verlaufsdatensatz | Jahresstände (OSM-Zeitstempel) | Einwohner (Jahr) |
|---|---|---|---|---|---|
| Amsterdam | `lau` | 2026-10-03T20:20:50Z | `2a652dc280f7` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 931.298 (2024) |
| Amsterdam | `fua` | 2026-10-03T20:20:50Z | `3ba1483e25bf` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Barcelona | `lau` | 2026-10-03T20:20:50Z | `9a77f00a5c1c` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 1.731.649 (2025) |
| Barcelona | `fua` | 2026-10-03T20:20:50Z | `9a77f00a5c1c` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Berlin | `lau` | 2026-10-03T20:20:50Z | `c3335f42f17f` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 3.782.202 (2024) |
| Berlin | `fua` | 2026-10-03T20:20:50Z | `1308e2c9638e` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Bordeaux | `lau` | 2026-10-03T20:20:50Z | `cb15813480d4` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 267.991 (2023) |
| Bordeaux | `fua` | 2026-10-03T20:20:50Z | `5f5d0d9f2e4f` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Bratislava | `lau` | 2026-10-03T20:20:50Z | `2e7369e09a0d` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 478.040 (2024) |
| Bratislava | `fua` | 2026-10-03T20:20:50Z | `2e7369e09a0d` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Budapest | `lau` | 2026-10-03T20:20:50Z | `0a58443e8e3f` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 1.686.222 (2024) |
| Budapest | `fua` | 2026-10-03T20:20:50Z | `0a58443e8e3f` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| København | `lau` | 2026-10-03T20:20:50Z | `be41de5bf657` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 659.350 (2024) |
| København | `fua` | 2026-10-03T20:20:50Z | `be41de5bf657` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Helsinki | `lau` | 2026-10-03T20:20:50Z | `78321316cf46` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 674.500 (2024) |
| Helsinki | `fua` | 2026-10-03T20:20:50Z | `78321316cf46` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Kraków | `lau` | 2026-10-03T20:20:50Z | `81a148c253e9` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 806.201 (2024) |
| Kraków | `fua` | 2026-10-03T20:20:50Z | `81a148c253e9` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Ljubljana | `lau` | 2026-10-03T20:20:50Z | `81ef23ad74c1` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 297.575 (2024) |
| Ljubljana | `fua` | 2026-10-03T20:20:50Z | `81ef23ad74c1` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Lyon | `lau` | 2026-10-03T20:20:50Z | `1404a50e78ba` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 519.127 (2023) |
| Lyon | `fua` | 2026-10-03T20:20:50Z | `1404a50e78ba` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Madrid | `lau` | 2026-10-03T20:20:50Z | `323b467bcce8` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 3.506.730 (2025) |
| Madrid | `fua` | 2026-10-03T20:20:50Z | `f0e3c8ec3ba7` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Oslo | `lau` | 2026-10-03T20:20:50Z | `47a4f74ce955` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 717.710 (2024) |
| Oslo | `fua` | 2026-10-03T20:20:50Z | `47a4f74ce955` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Paris | `lau` | 2026-10-03T20:20:50Z | `7db1f306301e` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 2.084.894 (2024) |
| Paris | `fua` | 2026-10-03T20:20:50Z | `df7be7ff6768` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Praha | `lau` | 2026-10-03T20:20:50Z | `6d1585485eb4` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 1.384.732 (2024) |
| Praha | `fua` | 2026-10-03T20:20:50Z | `678529b28752` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Stockholm | `lau` | 2026-10-03T20:20:50Z | `149b52577e9b` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 988.943 (2024) |
| Stockholm | `fua` | 2026-10-03T20:20:50Z | `149b52577e9b` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Strasbourg | `lau` | 2026-10-03T20:20:50Z | `9c8283eccd88` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 293.771 (2023) |
| Strasbourg | `fua` | 2026-10-03T20:20:50Z | `8bfe6202deab` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Utrecht | `lau` | 2026-10-03T20:20:50Z | `b0b39792e1fd` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 374.238 (2024) |
| Utrecht | `fua` | 2026-10-03T20:20:50Z | `b37cd68d61fb` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Wien | `lau` | 2026-10-03T20:20:50Z | `1254c077e90d` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 2.005.760 (2024) |
| Wien | `fua` | 2026-10-03T20:20:50Z | `1254c077e90d` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Warszawa | `lau` | 2026-10-03T20:20:50Z | `e910fce2f1b6` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 1.861.599 (2024) |
| Warszawa | `fua` | 2026-10-03T20:20:50Z | `72a9a41ebdf0` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Wrocław | `lau` | 2026-10-03T20:20:50Z | `fda036caffd1` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 673.743 (2024) |
| Wrocław | `fua` | 2026-10-03T20:20:50Z | `fda036caffd1` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
<!-- /generated:cities -->

Bei der Freigabe je Land (siehe unten) wird die Fläche des GISCO-LAU-Polygons mit der Fläche der administrativen OSM-Relation der Stadt verglichen. Weichen beide stärker voneinander ab, als der Schwellenwert in `config/trust.yaml` zulässt, kann die Stadt auf die OSM-Relation umgestellt werden; `admin_boundary` in `config/cities.yaml` hält diese Wahl fest [M5-Spezifikation §3.1]. Die folgende Tabelle nennt je Stadt die Quelle der Verwaltungsgrenze und der Einwohnerzahl, so wie sie mit der Gebietsgrenze und den Läufen gespeichert sind.

<!-- generated:sources -->
| Stadt | Verwaltungsgrenze (LAU) | Quelle der Einwohnerzahl |
|---|---|---|
| Amsterdam | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Barcelona | Eurostat GISCO LAU 2024 (1:1M) | INE Revisión del Padrón Municipal 2025 (1 Jan 2025) (https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/2861?nult=1) |
| Berlin | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Bordeaux | Eurostat GISCO LAU 2024 (1:1M) | INSEE populations de référence 2023, population municipale (https://www.insee.fr/fr/statistiques/8643952?geo=COM-33063) |
| Bratislava | Eurostat GISCO LAU 2024 (1:1M), Vereinigung von 17 LAU | GISCO LAU 2024 POP_2024 (Summe von 17 LAU) |
| Budapest | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| København | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Helsinki | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Kraków | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Ljubljana | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Lyon | Eurostat GISCO LAU 2024 (1:1M) | INSEE populations de référence 2023, population municipale (https://www.insee.fr/fr/statistiques/8643952?geo=COM-69123) |
| Madrid | Eurostat GISCO LAU 2024 (1:1M) | INE Revisión del Padrón Municipal 2025 (1 Jan 2025) (https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/2881?nult=1) |
| Oslo | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Paris | Eurostat GISCO LAU 2024 (1:1M) | Eurostat demo_r_pjangrp3 FR101 2024 |
| Praha | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Stockholm | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Strasbourg | Eurostat GISCO LAU 2024 (1:1M) | INSEE populations de référence 2023, population municipale (https://www.insee.fr/fr/statistiques/8643952?geo=COM-67482) |
| Utrecht | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Wien | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Warszawa | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
| Wrocław | Eurostat GISCO LAU 2024 (1:1M) | GISCO LAU 2024 POP_2024 |
<!-- /generated:sources -->

## Freigabe je Land

Eine Stadt kommt erst in die Auswertung, wenn ihr Land in `config/trust.yaml` freigegeben ist. Städte anderer Länder lassen sich berechnen und prüfen, erscheinen aber in keinem Teil der Auswertung [M5-Spezifikation §3.3]. Vor der Freigabe eines Landes stehen zwei Prüfungen:

- **Diagnose.** Sie wird aus dem aktuellen LAU-Lauf jeder Stadt mit dem Klassifikator der Auswertung berechnet. Gemessen werden der Anteil der Kilometer mit Radverkehrs-Tags, die keine Regel erkennt, der ausgeschlossene Anteil, der Anteil der Stufe B an A+B und der Flächenunterschied zwischen dem GISCO-LAU-Polygon und der OSM-Relation. Die Schwellenwerte stehen in `config/trust.yaml`. Liegt ein Wert darüber, muss die Prüfdatei des Landes ihn schriftlich begründen [M5-Spezifikation §3.1].
- **Referenzstichprobe.** Für jedes neue Land werden etwa 12 Wege per Abfrage aus dem aktuellen Stand des Landes ausgewählt. Die Stufen jedes Wegs werden von Hand geprüft und abgezeichnet. Ein Test stellt danach sicher, dass der Klassifikator der Auswertung diese Wege weiterhin so einstuft [M5-Spezifikation §3.2].

`velometer trust check` schlägt fehl, wenn

- ein Schwellenwert für einen Anteil in `config/trust.yaml` noch auf dem Platzhalter 1,0 steht;
- ein freigegebenes Land mit Städten in der Konfiguration keine Diagnosedatei hat, seine Diagnose eine seiner Städte auslässt oder auf einem Lauf beruht, der nicht mehr der aktuelle LAU-Lauf der Stadt ist;
- ein Diagnosewert seinen Schwellenwert ohne Begründung in der Prüfdatei des Landes überschreitet;
- ein freigegebenes Land mit einem anderen Klassifikator geprüft wurde als dem der Auswertung oder keinen nennt (`classifier_reviewed`);
- bei einem Land mit Referenzstichprobe Referenzwege unbestätigt sind oder der Klassifikator der Auswertung bestätigte Wege anders einstuft [M5-Spezifikation §3.3].

Deutschland braucht keine Diagnosedatei: Es stützt sich auf die Berliner Referenzstichprobe aus M1, die älter ist als die Freigabe je Land. Frankreich, Polen, Österreich und Dänemark wurden über den Abgleich mit veröffentlichten Zahlen in M2 freigegeben und haben keine eigene Stichprobe [M5-Spezifikation, Entscheidung 7].

<!-- generated:trust -->
| Land | Status | Grundlage | Geprüfter Klassifikator | Abgezeichnet am | Bestätigte Referenzwege |
|---|---|---|---|---|---|
| AT | freigegeben | Abgleich mit veröffentlichten Zahlen (M2) | v4 | – | keine |
| CZ | freigegeben | Referenzstichprobe und Tagging-Diagnose (M5) | v4 | 2026-10-03 | 12 von 12 |
| DE | freigegeben | Berliner Referenzstichprobe (M1) | v4 | – | keine |
| DK | freigegeben | Abgleich mit veröffentlichten Zahlen (M2) | v4 | – | keine |
| ES | freigegeben | Referenzstichprobe und Tagging-Diagnose (M5) | v4 | 2026-10-03 | 11 von 11 |
| FI | freigegeben | Referenzstichprobe und Tagging-Diagnose (M5) | v4 | 2026-10-03 | 10 von 10 |
| FR | freigegeben | Abgleich mit veröffentlichten Zahlen (M2) | v4 | – | keine |
| HU | freigegeben | Referenzstichprobe und Tagging-Diagnose (M5) | v4 | 2026-10-03 | 10 von 10 |
| NL | freigegeben | Referenzstichprobe und Tagging-Diagnose (M5) | v4 | 2026-10-03 | 12 von 12 |
| NO | freigegeben | Referenzstichprobe und Tagging-Diagnose (M5) | v4 | 2026-10-03 | 11 von 11 |
| PL | freigegeben | Abgleich mit veröffentlichten Zahlen (M2) | v4 | – | keine |
| SE | freigegeben | Referenzstichprobe und Tagging-Diagnose (M5) | v4 | 2026-10-03 | 12 von 12 |
| SI | freigegeben | Referenzstichprobe und Tagging-Diagnose (M5) | v4 | 2026-10-03 | 10 von 10 |
| SK | freigegeben | Referenzstichprobe und Tagging-Diagnose (M5) | v4 | 2026-10-03 | 13 von 13 |
<!-- /generated:trust -->

## Jahresstände

Die Jahresstände werden jeweils zum 1. Januar, 00:00 Uhr UTC, aus Geofabrik-Dateien mit vollständiger Versionsgeschichte gebildet. `osmium time-filter` schneidet den Stand zu diesem Zeitpunkt heraus, anschließend wird er auf die Gebietsgrenze zugeschnitten [ADR 0005]. Ein Verlaufsdatensatz ist die Gruppe der Regionsdateien, die eine Gebietsgrenze abdecken; seine Prüfsumme kennzeichnet die Dateien, aus denen eine Reihe entstanden ist [M3 R8]. Jede Stadt hat außerdem einen aktuellen Stand aus öffentlichen Geofabrik-Extrakten; für eine FUA können mehrere Extrakte zusammengeführt werden [M4-Spezifikation §3.2]. Ein aktueller Stand schließt nur dann an eine Reihe an, wenn er im selben Jahr liegt wie der letzte Jahresstand.

<!-- generated:snapshots -->
Stichtage: 2018-01-01, 2019-01-01, 2020-01-01, 2021-01-01, 2022-01-01, 2023-01-01, 2024-01-01, 2025-01-01, 2026-01-01, dazu ein aktueller Stand je Stadt und Grenzart.
<!-- /generated:snapshots -->

## Prüfhinweise

Ein Zuwachs an kartierten Kilometern bedeutet nicht unbedingt Bau. Der Kartierungsaufwand wird daher diagnostiziert, nicht herausgerechnet [ADR 0006]. Für jedes Jahr zählt velometer die Bearbeitungen an Radverkehrs-Tags im Jahr vor dem Stichtag, die Zahl der Kartierenden und den Anteil der aktivsten Person. Kennungen oder Namen von Kartierenden werden nicht gespeichert. Außerdem misst velometer die Kilometer mit veralteten Tags und die Kilometer von Straßenseiten mit Radverkehrs-Tags, die keine Regel erkennt.

Regeln über diese Werte markieren ein Jahr zur Prüfung. Ein Prüfhinweis ändert keine Zahl. Änderungsregeln vergleichen nur aufeinanderfolgende Stände, nie über ein fehlendes Jahr hinweg. Für den aktuellen Stand werden die Kilometer-Mindestwerte und die Spitzenschwelle mit dem bereits vergangenen Anteil des Jahres skaliert [M3 R14].

<!-- generated:flags -->
- `km_jump`: Die Kilometer der Stufen A+B ändern sich um mindestens 10 % des Vorwerts und um mindestens 25 km.
- `activity_spike`: Die Zahl der Bearbeitungen im Jahr erreicht mindestens das 2-Fache des Medians der Jahre der Reihe.
- `campaign_suspected`: `km_jump` und `activity_spike` im selben Jahr.
- `single_mapper`: ein Jahr mit `km_jump`, in dem der Anteil der aktivsten Person an den Bearbeitungen mindestens 0,5 beträgt.
- `tag_drift`: Die Kilometer mit veralteten Tags oder die nicht erkannten Kilometer ändern sich um mindestens 50 % und um mindestens 5 km.

| Schwellenwert (`config/activity.yaml`) | Wert |
|---|---|
| `km_jump_pct` | 10 |
| `km_jump_min_km` | 25 |
| `activity_spike_factor` | 2 |
| `single_mapper_share` | 0,5 |
| `tag_drift_pct` | 50 |
| `tag_drift_min_km` | 5 |
<!-- /generated:flags -->

## Vergleich mit veröffentlichten Zahlen

Die eigenen Zahlen werden Clean Cities 2025, ECF QECIO v2.10, dem Datensatz BikeNetKit und amtlichen Zahlen der Städte gegenübergestellt. Jede externe Zahl wird mit Quelle, Netzumfang, Längenbasis (soweit bekannt) und Abrufdatum gespeichert [ADR 0001, ADR 0006, ADR 0008]. Der Vergleich weist Abweichungen aus und erklärt sie; er mittelt sie nicht weg. Clean Cities 2025 hat überwiegend von den Städten gemeldete Zahlen verwendet, und QECIO veröffentlicht Ergebnisse nur je NUTS-3-Region. Die Ranglisten unterscheiden sich daher in Definition, Bezugsgröße und Gebiet, nicht nur in den Daten.

## Überlagerung mit dem Berliner Plannetz

Die Berliner Planseite stellt die eigenen kartierten Kilometer dem geplanten Radverkehrsnetz der Stadt gegenüber: der WFS-Ebene `radverkehrsnetz` der Senatsverwaltung mit ihren beiden Klassen Vorrangnetz und Ergänzungsnetz, in EPSG:25833 wie geliefert. Für jeden Berliner LAU-Lauf des Berichtsklassifikators wird der zwischengespeicherte OSM-Stand neu gelesen und neu klassifiziert; die neu berechneten Stufensummen müssen den gespeicherten Laufsummen entsprechen. Ein neuer OSM-Lauf entsteht dabei nicht [M8-Spezifikation, Entscheidung 10]. Eine Wegseite der Stufe A oder B zählt als auf dem Netz für die Teile, die innerhalb eines Puffers um eine Netzlinie liegen, deren Richtung höchstens um einen Grenzwinkel von der eigenen abweicht; Teile unter einer Mindestlänge entfallen. Die Parameter sind Daten. Eine Parameteränderung ist eine neue Überlagerungsversion, und die Zeilen früherer Versionen bleiben in der Datenbank [M8-Spezifikation, Entscheidung 11]. Die Seite zeigt die neueste Version.

<!-- generated:overlay -->
Version `overlay_v4`, aus `config/plans/overlay_v4.yaml`:

| Parameter | Wert |
|---|---|
| Puffer, auf der Straßenachse erfasste Wegseiten | 12 m |
| Puffer, separat erfasste Wege | 25 m |
| Grenzwinkel zur Netzlinie | 30° |
| Mindestlänge eines Teils | 20 m |
| Mindestlänge geprüft an | den über sich berührende Wegseiten zusammengefassten Teilen einer Stufe |
| Treffer enden an einem freien Ende einer Netzlinie | ja |
<!-- /generated:overlay -->

Das Verfahren hat vier Versionen, alle auf denselben Ständen gerechnet. `overlay_v1` verwendete einen einzigen Puffer von 12 m. Über die Jahresstände wechselte ein großer Teil der Berliner Stufen A und B von Merkmalen an der Straßenachse zu separat erfassten Wegen, die weiter von der Netzlinie entfernt liegen; v1 maß daher eher diesen Wandel der Erfassungspraxis als das Netz. `overlay_v2` gibt separat erfassten Wegen einen Puffer von 25 m. `overlay_v3` prüft die Mindestlänge an den über sich berührende Wegseiten zusammengefassten Teilen einer Stufe, sodass das Ergebnis nicht mehr davon abhängt, wie fein OSM seine Wege teilt. `overlay_v4` beendet einen Treffer am freien Ende einer Netzlinie, sodass Begleitwege der kreuzenden oder weiterführenden Straße nahe diesem Ende nicht mehr zählen; ein Ende ist frei, sofern keine andere Linie derselben Klasse innerhalb von 1 m an es anschließt und den Knoten innerhalb des Grenzwinkels verlässt. Die Zahlen jeder Version und die Prüfungen dahinter stehen in `docs/review/m8-overlay.md`.

Die Reihe auf der Seite ist die Veränderung der kartierten A+B-Kilometer je Seite auf jeder Netzklasse seit dem 1. Januar 2022, dem ersten Zieljahr des Plans, mit einem Punkt je Stand [M8-Spezifikation §4.4]. Der Bestand ist mit dem Plan nicht vergleichbar: Er enthält Infrastruktur, die älter ist als der Plan, und kartierte Kilometer sind keine nach dem Standard des Mobilitätsgesetzes fertiggestellten Kilometer [ADR 0006]. Die Reihe hängt davon ab, wie Kartierende Radwege zeichnen, und vom Zuordnungsverfahren. Sie verändert sich, wenn Wege neu gezeichnet werden, und mit jeder Verfahrensversion; Teile an Knoten können fälschlich zugeordnet oder verworfen werden. Das Protokoll beziffert beide Fehlerarten für v4.

## Zählstellenindex

Zählstellendaten sind Kontext, kein Ergebnis. Sie erfassen die Fahrräder, die die Standorte der Zählstellen passieren, nicht den Radverkehr einer ganzen Stadt, und nichts hier verknüpft Zählwerte und kartierte Kilometer als Ursache und Wirkung [M8-Spezifikation, Entscheidung 12]. Die Städte der folgenden Tabelle veröffentlichen offene, lizenzierte Zählstellendaten; die kostenpflichtige Eco-Counter-API wird nicht verwendet [M8-Spezifikation, Entscheidung 2]. Portal, Lizenz und Abrufzeit werden je heruntergeladener Datei festgehalten, und der Reiter „Zählstellen“ jeder Stadt nennt seine Quelle.

<!-- generated:counters -->
| Stadt | Herausgeber | Lizenz | Basisjahr (= 100) | Reihe |
|---|---|---|---|---|
| Berlin | Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt Berlin | dl-de-zero-2.0 | 2019 | Zählwerte |
| Paris | Ville de Paris, Direction de la Voirie et des Déplacements | ODbL | 2019 | Zählwerte |
| Wien | Stadt Wien | CC BY 4.0 | 2019 | Zählwerte |
| Helsinki | City of Helsinki, Urban Environment Division (Helsingin kaupunkiympäristön toimiala) | CC BY 4.0 | 2019 | Zählwerte |
| Madrid | Ayuntamiento de Madrid | CC BY 4.0 | 2020 | Zählwerte |
| Oslo | Statens vegvesen (staatliche Zählstellen) | NLOD | 2019 | Zählwerte |
| Barcelona | Ajuntament de Barcelona | CC BY 4.0 | 2019 | durchschnittliche tägliche Verkehrsstärke |

Für die übrigen 14 Städte wurden keine offenen Zählstellendaten gefunden; ihr Reiter „Zahlen“ nennt die geprüften Portale.

Indexregel: Eine Zählstelle geht in die Verkettung zweier Jahre ein, wenn beide Jahre mindestens 90 % gültige Tage haben. Das Kettenglied ist das Verhältnis der summierten Zählwerte dieser Zählstellen, und die Glieder werden vom Basisjahr aus verkettet. Ein Glied mit weniger als 3 solchen Zählstellen hat keinen Wert, und kein späteres Jahr der Kette hat dann einen.
<!-- /generated:counters -->

Eine bekannte Eigenschaft dieser Regel: Die Zählwerte einer Zählstelle werden nur über ihre gültigen Tage summiert, sodass eine Zählstelle mit weniger gültigen Tagen in einem Jahr eines Kettenglieds als im anderen das Verhältnis um diesen Unterschied der Abdeckung verschiebt. Die 90-%-Regel begrenzt den Effekt. Gemessen an den gespeicherten Tageswerten gegen einen Mittelwert je gültigem Tag derselben Zählstellen verschieben sich die meisten Glieder um weniger als 0,5 %; die größten Abweichungen sind +2,1 % (Paris, 2019 auf 2020) und −2,0 % (Helsinki, 2024 auf 2025) [M8-Abschlussprüfung, `docs/superpowers/rulings-m8.md`]. Barcelonas Monatsreihe ist nicht betroffen, da eine Zählstelle alle zwölf Monate braucht.

Stundenwerte werden zu Tagen summiert. Ein Tag ist gültig, wenn er jede Ortsstunde seines Datums enthält (23, 24 oder 25), und ein Zählstellentag mit der Summe 0 ist ein Ausfall, kein Zählwert. Zählstellen, die ein Portal unter zwei Kennungen führt, etwa eine umnummerierte Zählstelle oder die beiden Seiten einer Brücke, werden als eine Zählstelle summiert. Das Basisjahr ist 2019 oder, wenn die Daten einer Stadt später beginnen, das erste volle Jahr; die Tabelle nennt es je Stadt [M8-Spezifikation, Entscheidung 13]. Jedes Zählstellendiagramm markiert 2020 als Corona-Jahr. Der Reiter „Zählstellen“ stellt den Index neben den Index der kartierten A+B-Kilometer im Stadtgebiet (Stände zum 1. Januar, gleiches Basisjahr).

Je Stadt:

- Paris: Eine Stunde einer Zählstelle liegt nur vor, wenn jeder Zähler der Zählstelle, der an diesem Tag in Betrieb ist, sie meldet; ein Zähler ist von seinem ersten bis zu seinem letzten gemeldeten Tag einer Datei in Betrieb.
- Oslo: Die Zählstellen sind staatliche Zählstellen von Statens vegvesen, beschränkt auf Standorte innerhalb der LAU-Grenze der Stadt [M8-Spezifikation, Entscheidung 15]. Ein Tag ist vollständig, wenn die Stundenwerte jeder Ortsstunde ein Verkehrsaufkommen zuweisen; der tägliche Abdeckungsanteil der API wird nicht verwendet, da in einer Stichprobe kein Schwellenwert darauf dieser Regel entsprach.
- Madrid: Die Daten beginnen im September 2019, das Basisjahr ist daher 2020. Die Dateien enthalten von Juli 2021 bis August 2022, während die Detektoren getauscht wurden, keine Zählwerte. Nur 2020 hat einen Indexwert, daher wird keine Indexlinie gezeichnet.
- Barcelona veröffentlicht die monatliche durchschnittliche tägliche Verkehrsstärke je Zählstelle und Tagestyp, keine Zählwerte. Sein Index verwendet den Mittelwert einer Zählstelle über die zwölf Werktagsmonate, wobei eine Zählstelle in einem Jahr nur mit allen zwölf gültig ist, und heißt durchschnittliche tägliche Verkehrsstärke [M8-Spezifikation, Entscheidung 14].
- Helsinki: Der Index behält jede Zählstelle, die die Regel erfüllt. Die Zählwerte zweier Zählstellen fallen ab, während sie weiterzählen (Kaivokatu ab April 2024, Pitkäsilta länsipuoli ab Mai 2025). Der Reiter „Zählstellen“ gibt als unsere Lesart der Tageswerte den Index ohne sie ab diesen Jahren an [Entscheidung vom 7. Oktober 2026 zu den Zählstellen, `docs/superpowers/rulings-m8.md`].

## Herkunft der Zahlen

Jede Zahl lässt sich auf einen Lauf zurückführen. Ein Lauf speichert den Git-Commit, die Klassifikatorversion mit ihren Parametern, eine Prüfsumme der Konfiguration von Klassifikator, Kennzahlvarianten und Aktivitätsregeln, den OSM-Zeitstempel, die Prüfsumme der Gebietsgrenze und die Quelldateien [ADR 0001; ADR 0005; M4-Spezifikation §3.1]. Eine Auswertung zeigt nur Läufe des Auswertungsklassifikators und der vorliegenden Konfiguration. Eine geänderte Konfiguration erfordert daher neue Läufe, und alte Läufe werden nicht beigemischt.

## Bekannte Einschränkungen

<!-- generated:limitations -->
- Alle OSM-Längen sind kartierte Kilometer, keine gebauten Kilometer. Ein Zuwachs kann auf Bau zurückgehen, aber auch auf eine Kartierungsaktion, einen Import oder eine geänderte Erfassungspraxis. Keine der Zahlen hier besagt, was eine Stadt gebaut hat [ADR 0006].
- Die Einwohnerzahl ist der LAU-Wert 2024. Fehlt er, wie bei französischen Gemeinden, gilt der unten beschriebene, belegte Wert des nationalen Statistikamts, ersatzweise der Wert der deckungsgleichen NUTS-3-Einheit [ADR 0004]. Derselbe Wert gilt für jedes Stichjahr. Werte je 100.000 Einwohner bilden Bevölkerungsänderungen daher nicht ab [M3-Spezifikation, Entscheidung 2].
- FUA-Läufe führen keine Einwohnerzahl. Für die FUA gibt es daher keinen Wert je 100.000 Einwohner [M4-Spezifikation §4.4; `city_boundary` in `sources/boundaries.py` liefert eine Einwohnerzahl nur für die LAU]. Die FUA dient als Robustheitsprüfung [ADR 0004].
- Die Stufen berücksichtigen weder Breite noch Oberfläche. Ein schmaler oder holpriger Radweg zählt wie jeder andere Weg seiner Stufe. Der Längenanteil mit `width`, `surface` und `segregated` wird je Stufe nur als Diagnose erfasst [ADR 0002, ADR 0006].
- Erfassungen, die der Klassifikator erkennt, aber nicht als Radverkehrsanlage wertet, etwa `cycleway=shoulder`, ein `cycleway=yes` ohne Typ oder ein Weg mit ausdrücklicher Mountainbike-Kennzeichnung (`mtb:scale`, `mtb`, `mtb:type`, `cycling=mtb`), gelten als ausgeschlossen und zählen in keiner Kennzahlvariante (siehe Regeltabelle). Straßenseiten mit Radverkehrs-Tags, auf die keine Regel passt, werden als nicht erkannte Kilometer ausgewiesen. Sie fließen in keine Stufe ein [M3 R11; Klassifikator v2, nach M3 entschieden].
- Clean Cities 2025 hat für die meisten Städte von den Städten gemeldete Zahlen verwendet und OSM nur ersatzweise. Die Kennzahlvariante `clean_cities_2025` bildet diese Ersatzmethode nach, nicht die veröffentlichten Zahlen [ADR 0001, ADR 0003]. QECIO v2.10 veröffentlicht Ergebnisse nur je NUTS-3-Region, Stand Januar 2024. Eine NUTS-3-Region muss nicht mit der Stadtgrenze übereinstimmen [ADR 0001].
- Jeder Lauf speichert den Git-Commit, mit dem er erstellt wurde. Gab es dabei nicht committete Änderungen im Arbeitsverzeichnis, trägt der Commit die Endung `-dirty` und legt den Code nicht genau fest. Die meisten historischen Läufe aus M3 (Klassifikator v1) tragen diese Endung, weil Dokumentation und Skripte während der Läufe nicht committet waren [M3 R19]. Sie sind durch die Läufe aus M4 ersetzt und werden nicht gezeigt; kein Lauf in diesem Bericht trägt die Endung [M4-Spezifikation §3.4].
- Die Jahresstände werden aus Geofabrik-Dateien mit vollständiger Versionsgeschichte geschnitten. Diese enden am Tag ihres Downloads. Der aktuelle Lauf liest öffentliche Extrakte, deren OSM-Zeitstempel ein anderes Datum haben kann. Die Kartierungsaktivität des aktuellen Stands endet dort, wo die Verlaufsdatei endet [M3 R9]. Ein aktueller Lauf aus mehreren zusammengeführten Regionen trägt den ältesten Zeitstempel der Regionen [M4-Spezifikation §3.2].
- Die Freigabe je Land prüft die Erfassungspraxis, nicht die Vollständigkeit der Karte. Ihre Schwellenwerte schlagen an bei Radverkehrs-Tags, die der Klassifikator nicht erkennt oder ausschließt, bei einem ungewöhnlich hohen Anteil der Stufe B an A+B und bei einer Verwaltungsgrenze, die von der OSM-Relation abweicht [M5-Spezifikation §3.1]. Die Referenzstichprobe umfasst etwa 12 Wege für jedes neue Land. Das reicht nicht, um jede örtliche Erfassungsgewohnheit abzudecken [M5-Spezifikation §3.2]. Frankreich, Polen, Österreich und Dänemark haben keine eigene Referenzstichprobe: Sie wurden über den Abgleich ihrer Pilotstädte in M2 freigegeben [M5-Spezifikation, Entscheidung 7].
- Für einige Städte gibt es keine LAU-Einwohnerzahl, und weder ihre NUTS-3-Einheit (eine Provinz oder ein Département) noch ihre Urban-Audit-Stadt (eine erweiterte Stadt) deckt sich mit der Gemeinde. Ihr Einwohnerwert ist die amtliche Zahl des nationalen Statistikamts, mit Jahr und URL belegt in `config/cities.yaml` (`population_override`) [Entscheidung zur Einwohnerzahl vom 3. Oktober 2026, `docs/superpowers/rulings-m5.md`]. Das Jahr muss nicht 2024 sein; ihre Werte je 100.000 Einwohner können sich daher auf ein anderes Jahr stützen als die der übrigen Städte. Jahr und Quelle jedes Werts stehen in den Tabellen oben. Das betrifft Barcelona (INE Revisión del Padrón Municipal 2025 (1 Jan 2025)), Bordeaux (INSEE populations de référence 2023, population municipale), Lyon (INSEE populations de référence 2023, population municipale), Madrid (INE Revisión del Padrón Municipal 2025 (1 Jan 2025)) und Strasbourg (INSEE populations de référence 2023, population municipale).
- QECIO v2.10 veröffentlicht Ergebnisse je NUTS-3-Region. Ist diese Region nicht die Stadt, bezieht sich die QECIO-Zahl auf ein anderes Gebiet als die eigenen Läufe. Die QECIO-Vergleichszeilen der Stadt tragen dann den Hinweis „NUTS-3-Einheit ist nicht die Stadt“, und das Ranglistendiagramm kennzeichnet die Stadt mit † [M5-Spezifikation §4.3]. Das betrifft Amsterdam, Barcelona, Bordeaux, Bratislava, København, Helsinki, Ljubljana, Lyon, Madrid, Stockholm, Strasbourg und Utrecht.
- Die Bezirksgrenzen sind die 12 administrativen OSM-Relationen (admin_level 9), abgefragt aus dem Berliner Extrakt. Kilometer innerhalb der LAU-Grenze, aber außerhalb jedes Bezirks (die LAU ist im Maßstab 1:1 Mio. generalisiert), werden als eigene Zeile „außerhalb der Bezirke“ ausgewiesen, sodass die Bezirkszeilen und diese Zeile zusammen die Summe der Stadt ergeben.
- Die Änderungskarte vergleicht zwei Stände mit demselben Klassifikator. Ein Zugewinn ist ein Weg, der neu als Radverkehrsanlage kartiert ist, ein Verlust ein Weg, der nicht mehr so kartiert ist. Neu gezeichnete und neu getaggte Wege werden getrennt ausgewiesen; ein Stück, das von einem bestehenden Weg abgetrennt wurde (eine neue Weg-ID entlang eines Wegs, der kürzer wurde, bis etwa zu der Länge, die er verlor), zählt als neu gezeichnet, nicht als Zugewinn. Die Seite nennt auch die Nettoänderung je Stufe. Nichts davon belegt einen Bau (ADR 0006). Ein einzelner neuer Weg, der Radwege auf beiden Seiten einer Straße ersetzt, zählt auf beiden Seiten als neu gezeichnet; die neu gezeichneten Kilometer können daher eine tatsächliche Verringerung von zwei Seiten auf eine enthalten.
- Wege mit ausdrücklicher Mountainbike-Kennzeichnung (mtb:scale, mtb, mtb:type, cycling=mtb) sind ausgeschlossen. Pfade ohne solche Tags bleiben gezählt.
<!-- /generated:limitations -->

## Lizenzen

Kartendaten © OpenStreetMap-Mitwirkende. Die abgeleiteten Daten (Stufenlängen, Kennzahlen und Exporte) stehen unter der Open Database License (ODbL) 1.0. Der Code steht unter der MIT-Lizenz. Externe Vergleichszahlen werden mit Quelle zitiert und nicht über das Zitatrecht hinaus weitergegeben [ADR 0008].
