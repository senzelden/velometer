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
- Klassifikator der Auswertung: **v2** (`config/classifier/v2.yaml`)
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
| `X_separate` | `excluded` | separate | road_side | `cycleway=separate` |
| `A_cycleway` | `A` |  | standalone | `highway=cycleway and (foot not in [designated] or segregated=yes)` |
| `B_track_shared` | `B` | shared | road_side | `cycleway=track and cycleway:segregated=no` |
| `A_track_side` | `A` |  | road_side | `cycleway=track` |
| `B_cycleway_foot` | `B` |  | standalone | `highway=cycleway and foot=designated` |
| `A_path_cycle_only` | `A` |  | standalone | `highway=path and bicycle=designated and foot in [no]` |
| `B_path_segregated` | `B` | segregated | standalone | `highway in [path, footway, pedestrian] and bicycle=designated and segregated=yes` |
| `B_path` | `B` |  | standalone | `highway in [path, footway, pedestrian] and bicycle=designated` |
| `B_sidewalk_designated` | `B` | sidewalk | road_side | `sidewalk_bicycle=designated and cycleway not in [lane, share_busway]` |
| `B_share_sidewalk` | `B` | sidewalk | road_side | `cycleway=share_sidewalk` |
| `C_lane_physical` | `C` |  | road_side | `cycleway=lane and cycleway:separation:traffic in <physical_separation>` |
| `D_lane_advisory` | `D` | advisory | road_side | `cycleway=lane and cycleway:lane in [advisory, pictogram]` |
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

Verglichen wird nur innerhalb derselben Grenzart. Die Einwohnerzahl der LAU stammt von Eurostat. Fehlt dort ein Wert, liefert ihn die deckungsgleiche NUTS-3-Einheit [ADR 0004]. Für alle Stichjahre gilt derselbe Einwohnerwert von 2024 [M3-Spezifikation, Entscheidung 2]. FUA-Läufe führen keine Einwohnerzahl; für die FUA gibt es daher keinen Wert je 100.000 Einwohner [M4-Spezifikation §4.4].

Die Tabelle nennt je Stadt und Grenzart die OSM-Zeitstempel der hier verwendeten Läufe, den Verlaufsdatensatz und die Einwohnerzahl.

<!-- generated:cities -->
| Stadt | Grenzart | Aktueller Lauf (OSM-Zeitstempel) | Verlaufsdatensatz | Jahresstände (OSM-Zeitstempel) | Einwohner (Jahr) |
|---|---|---|---|---|---|
| Berlin | `lau` | 2026-09-30T20:22:42Z | `c3335f42f17f` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 3.782.202 (2024) |
| Berlin | `fua` | 2026-09-30T20:22:42Z | `1308e2c9638e` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| København | `lau` | 2026-09-30T20:22:42Z | `be41de5bf657` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 659.350 (2024) |
| København | `fua` | kein aktueller Lauf | keiner | keine historischen Läufe | keine, kein Wert je 100.000 Einwohner |
| Paris | `lau` | 2026-09-30T20:22:42Z | `7db1f306301e` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 2.084.894 (2024) |
| Paris | `fua` | 2026-09-30T20:22:42Z | `df7be7ff6768` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | keine, kein Wert je 100.000 Einwohner |
| Wien | `lau` | 2026-09-30T20:22:42Z | `1254c077e90d` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 2.005.760 (2024) |
| Wien | `fua` | kein aktueller Lauf | keiner | keine historischen Läufe | keine, kein Wert je 100.000 Einwohner |
| Wrocław | `lau` | 2026-09-30T20:22:42Z | `fda036caffd1` | 2018-01-01T00:00:00Z, 2019-01-01T00:00:00Z, 2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z, 2022-01-01T00:00:00Z, 2023-01-01T00:00:00Z, 2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z, 2026-01-01T00:00:00Z | 673.743 (2024) |
| Wrocław | `fua` | kein aktueller Lauf | keiner | keine historischen Läufe | keine, kein Wert je 100.000 Einwohner |
<!-- /generated:cities -->

## Jahresstände

Die Jahresstände werden jeweils zum 1. Januar, 00:00 Uhr UTC, aus Geofabrik-Dateien mit vollständiger Versionsgeschichte gebildet. `osmium time-filter` schneidet den Stand zu diesem Zeitpunkt heraus, anschließend wird er auf die Gebietsgrenze zugeschnitten [ADR 0005]. Ein Verlaufsdatensatz ist die Gruppe der Regionsdateien, die eine Gebietsgrenze abdecken; seine Prüfsumme kennzeichnet die Dateien, aus denen eine Reihe entstanden ist [M3 R8]. Jede Stadt hat außerdem einen aktuellen Stand aus öffentlichen Geofabrik-Extrakten; für eine FUA können mehrere Extrakte zusammengeführt werden [M4-Spezifikation §3.2]. Ein aktueller Stand schließt nur dann an eine Reihe an, wenn er im selben Jahr liegt wie der letzte Jahresstand.

<!-- generated:snapshots -->
Stichtage: 2018-01-01, 2019-01-01, 2020-01-01, 2021-01-01, 2022-01-01, 2023-01-01, 2024-01-01, 2025-01-01, 2026-01-01, dazu ein aktueller Stand je Stadt und Grenzart.
<!-- /generated:snapshots -->

## Prüfhinweise

Ein Zuwachs an kartierten Kilometern bedeutet nicht unbedingt Bau. Der Kartierungsaufwand wird daher diagnostiziert, nicht herausgerechnet [ADR 0006]. Für jedes Jahr zählt velometer die Bearbeitungen an Radverkehrs-Tags im Jahr vor dem Stichtag, die Zahl der Kartierenden und den Anteil der aktivsten Person. Kennungen oder Namen von Kartierenden werden nicht gespeichert. Außerdem misst velometer die Kilometer mit veralteten Tags und die Kilometer von Straßenseiten mit Radverkehrs-Tags, die keine Regel erkennt.

Regeln über diese Werte markieren ein Jahr zur Prüfung. Ein Prüfhinweis ändert keine Zahl. Änderungsregeln vergleichen nur aufeinanderfolgende Stände, nie über ein fehlendes Jahr hinweg. Für den aktuellen Stand werden die Kilometer-Mindestwerte und die Spitzenschwelle mit dem bereits vergangenen Anteil des Jahres skaliert [M3 R14].

<!-- generated:flags -->
- `km_jump`: Die Kilometer der Stufen A+B ändern sich um mindestens 10 % des Vorwerts und um mindestens 25 km.
- `activity_spike`: Die Zahl der Bearbeitungen im Jahr erreicht mindestens das 2-Fache des Medians der Jahre der Reihe.
- `campaign_suspected`: `km_jump` und `activity_spike` im selben Jahr.
- `single_mapper`: ein Jahr mit `km_jump`, in dem der Anteil der aktivsten Person an den Bearbeitungen mindestens 0,5 beträgt.
- `tag_drift`: Die Kilometer mit veralteten Tags oder die nicht erkannten Kilometer ändern sich um mindestens 50 % und um mindestens 5 km.

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

## Herkunft der Zahlen

Jede Zahl lässt sich auf einen Lauf zurückführen. Ein Lauf speichert den Git-Commit, die Klassifikatorversion mit ihren Parametern, eine Prüfsumme der Konfiguration von Klassifikator, Kennzahlvarianten und Aktivitätsregeln, den OSM-Zeitstempel, die Prüfsumme der Gebietsgrenze und die Quelldateien [ADR 0001; ADR 0005; M4-Spezifikation §3.1]. Eine Auswertung zeigt nur Läufe des Auswertungsklassifikators und der vorliegenden Konfiguration. Eine geänderte Konfiguration erfordert daher neue Läufe, und alte Läufe werden nicht beigemischt.

## Bekannte Einschränkungen

<!-- generated:limitations -->
- Alle OSM-Längen sind kartierte Kilometer, keine gebauten Kilometer. Ein Zuwachs kann auf Bau zurückgehen, aber auch auf eine Kartierungsaktion, einen Import oder eine geänderte Erfassungspraxis. Keine der Zahlen hier besagt, was eine Stadt gebaut hat [ADR 0006].
- Die Einwohnerzahl ist der LAU-Wert 2024. Fehlt er, wie bei französischen Gemeinden, gilt der Wert der deckungsgleichen NUTS-3-Einheit [ADR 0004]. Derselbe Wert gilt für jedes Stichjahr. Werte je 100.000 Einwohner bilden Bevölkerungsänderungen daher nicht ab [M3-Spezifikation, Entscheidung 2].
- FUA-Läufe führen keine Einwohnerzahl. Für die FUA gibt es daher keinen Wert je 100.000 Einwohner [M4-Spezifikation §4.4; `city_boundary` in `sources/boundaries.py` liefert eine Einwohnerzahl nur für die LAU]. Die FUA dient als Robustheitsprüfung [ADR 0004].
- Die Stufen berücksichtigen weder Breite noch Oberfläche. Ein schmaler oder holpriger Radweg zählt wie jeder andere Weg seiner Stufe. Der Längenanteil mit `width`, `surface` und `segregated` wird je Stufe nur als Diagnose erfasst [ADR 0002, ADR 0006].
- Erfassungen, die der Klassifikator erkennt, aber nicht als Radverkehrsanlage wertet, etwa `cycleway=shoulder` oder ein `cycleway=yes` ohne Typ, gelten als ausgeschlossen und zählen in keiner Kennzahlvariante (siehe Regeltabelle). Straßenseiten mit Radverkehrs-Tags, auf die keine Regel passt, werden als nicht erkannte Kilometer ausgewiesen. Sie fließen in keine Stufe ein [M3 R11; Klassifikator v2, nach M3 entschieden].
- Clean Cities 2025 hat für die meisten Städte von den Städten gemeldete Zahlen verwendet und OSM nur ersatzweise. Die Kennzahlvariante `clean_cities_2025` bildet diese Ersatzmethode nach, nicht die veröffentlichten Zahlen [ADR 0001, ADR 0003]. QECIO v2.10 veröffentlicht Ergebnisse nur je NUTS-3-Region, Stand Januar 2024. Eine NUTS-3-Region muss nicht mit der Stadtgrenze übereinstimmen [ADR 0001].
- Jeder Lauf speichert den Git-Commit, mit dem er erstellt wurde. Gab es dabei nicht committete Änderungen im Arbeitsverzeichnis, trägt der Commit die Endung `-dirty` und legt den Code nicht genau fest. Die meisten historischen Läufe aus M3 (Klassifikator v1) tragen diese Endung, weil Dokumentation und Skripte während der Läufe nicht committet waren [M3 R19]. Sie sind durch die Läufe aus M4 ersetzt und werden nicht gezeigt; kein Lauf in diesem Bericht trägt die Endung [M4-Spezifikation §3.4].
- Die Jahresstände werden aus Geofabrik-Dateien mit vollständiger Versionsgeschichte geschnitten. Diese enden am Tag ihres Downloads. Der aktuelle Lauf liest öffentliche Extrakte, deren OSM-Zeitstempel ein anderes Datum haben kann. Die Kartierungsaktivität des aktuellen Stands endet dort, wo die Verlaufsdatei endet [M3 R9]. Ein aktueller Lauf aus mehreren zusammengeführten Regionen trägt den ältesten Zeitstempel der Regionen [M4-Spezifikation §3.2].
<!-- /generated:limitations -->

## Lizenzen

Kartendaten © OpenStreetMap-Mitwirkende. Die abgeleiteten Daten (Stufenlängen, Kennzahlen und Exporte) stehen unter der Open Database License (ODbL) 1.0. Der Code steht unter der MIT-Lizenz. Externe Vergleichszahlen werden mit Quelle zitiert und nicht über das Zitatrecht hinaus weitergegeben [ADR 0008].
