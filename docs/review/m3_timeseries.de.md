# M3-Zeitreihe: Erklärungen der markierten Jahre

Deutsche Fassung der Erklärungen in `m3_timeseries.md`. Jeder Eintrag trägt nach der Überschrift
den Stempel seines englischen Eintrags; ändert sich das Englische, gilt der deutsche Eintrag als
veraltet.

## So ist das zu lesen

`tag_drift` greift, wenn sich `legacy_km` oder `unrecognised_km` um mindestens 50 % und um
mindestens 5 km ändert (`tag_drift_min_km`, für den aktuellen Datenpunkt hochgerechnet). Die
km-Untergrenze kam am 2. Oktober 2026 hinzu: Ohne sie waren in den fünf Pilotstädten 18 weitere
Stadtjahre wegen Verschiebungen von wenigen km oder weniger markiert, bis hinunter zu 0,1 -> 0,2 km.
Weg-Nummern sind OSM-Weg-IDs; Tag-Änderungen stehen als vorher -> nachher. Die Angaben zu den
Kartierenden sind aggregiert: Zahl der Bearbeitungen, Changesets und Kartierenden sowie der
Anteil des aktivsten Mappers; niemand wird namentlich genannt.

Verwendete Ursachen: **Bau** (neu kartierte Wege, die zu bekanntem Bau passen; der Eintrag nennt
die amtliche Quelle dieses Baus, ADR 0006), **Kampagne** (ein Schub von Kartierung oder
Umtaggung, meist keine Radinfrastruktur oder nichts Neues), **Umtaggung** (dieselben Wege neu
getaggt, was km zwischen Stufen oder Diagnosewerten verschiebt) und **Kartieraktivität**
(gewöhnliches Kartieren, das Radwege ergänzt oder neu zeichnet, wo keine amtliche Quelle einen Bau
belegt). Alle km sind kartierte km, keine gebauten km.

## Erklärungen

### amsterdam/fua/2022

<!-- src: 5a6f1342fb5d -->

Ursache: **Umtaggung** (Radfahren gegen die Einbahnrichtung neu getaggt). `legacy_km` fiel von
10,2 auf 2,1, weil `cycleway=opposite_lane` auf Einbahnstraßen im Lauf des Jahres 2021 von
7,10 km auf null zurückging. Von den 10,22 km Seiten mit veralteten Tags am 1. Januar 2021 bleiben 4,04 km
nach dem heutigen Schema in Stufe D (`cycleway:left=lane` + `oneway:bicycle=no`, etwa Weg 7373718
Eerste Helmersstraat, Weg 7409127 Meer en Boslaan), 1,61 km wurden zu
`cycleway:left=shared_lane` und sind ausgeschlossen (Weg 7408896 Blekersvaartweg), und 1,89 km
behielten nur `oneway:bicycle=no` ohne Streifen-Tag (Weg 26013236 Planetenlaan), sodass sie aus
Stufe D herausfallen. Die 2,07 km, die 2022 übrig sind, tragen `cycleway=opposite`. Die 101
Wege mit veralteten Tags wurden zuletzt in 44 Changesets von 20 Kartierenden bearbeitet, 47 davon im Februar
2021; das Jahr hatte 25.937 Bearbeitungen bei einem Anteil des aktivsten Mappers von 0,09, es
war also kein Durchgang einer einzelnen Person. Die Umtaggung betrifft nur Stufe D: A+B stieg
normal (4.101,1 -> 4.131,0 km), und D wuchs von 676,5 auf 726,2 km.

### barcelona/lau/2021

<!-- src: 60ee955f6ba1 -->

Ursache: **Kampagne** (Fußwegenetz, mit einer dominierenden kartierenden Person). 16.309 gezählte
Bearbeitungen im Jahr 2020 bei einem Grenzwert von 12.666 (Median 6.333). 13.722 davon legen
`highway=footway`-Wege an: Von den 13.819 neuen Gehwegen sind 6.976 Bürgersteige und 5.250
Querungen (etwa Weg 43210773). 8.716 der Bearbeitungen fallen in den Dezember 2020, und der
Anteil des aktivsten Mappers beträgt 0,76 (8.113 der Dezember-Bearbeitungen; 11.755 angelegte
Gehwege über das Jahr). Sie verteilen sich auf 1.176 Changesets, das größte Changeset hält
1,6 %. A+B stieg von 189,6 auf 214,4 kartierte km. Das sind +24,8 km, 0,2 km unter der
Sprung-Untergrenze von 25 km. Der Zuwachs stammt aus der Kartierung von Radwegen, nicht aus der
Gehwegarbeit: Stufe A gewann 21,7 km, mit 204 neuen `highway=cycleway`-Wegen (36,8 km, teils neu
gezeichnete Teilstücke älterer Wege), etwa Weg 871562924 an der Carrer d'Aragó (4,8 km) und Weg
766736025 an der Carrer de Bilbao. Nach Regeln aufgeschlüsselt stieg `A_segregated` um 39,6 km, und
`A_cycle_only` fiel um 17,3 km. Die meisten neuen Radwege tragen `segregated=yes` (30,0 km), und
17,7 km bestehender Radwege erhielten das Tag im Lauf des Jahres 2020 (etwa Weg 308033675), was
sie innerhalb von Stufe A verschiebt. Stufe E taucht auf (0,0 -> 10,0 km), durch Busspuren und
Fahrradstraßen, die neu auf Straßen getaggt wurden (siehe barcelona/fua/2021).

### barcelona/lau/2022

<!-- src: 22b5e2fe4043 -->

Ursache: **Kampagne**, die zweite Hälfte der Gehwegkartierung von barcelona/lau/2021 durch
dieselbe dominierende kartierende Person. 21.116 gezählte Bearbeitungen im Jahr 2021 bei einem
Grenzwert von 12.666: 18.335 legen `highway=footway` an (von 18.412 neuen Gehwegen sind 10.779
Bürgersteige und 6.348 Querungen; etwa Weg 49790703). 17.595 der Bearbeitungen fallen in die
Monate Januar bis März 2021, und der Anteil des aktivsten Mappers beträgt 0,86 (16.769 angelegte
Gehwege). 1.305 Changesets, das größte Changeset hält 1,7 %. A+B bewegte sich normal, von 214,4
auf 219,1 kartierte km: Stufe A +6,1 km. Die größten Zuwächse sind Weg 867922053 und Weg 867922054
am Passeig de la Zona Franca (+3,3 km), die von einem Lebenszyklus-Tag (ausgeschlossen) zu
`highway=cycleway` wechselten, sowie der neue Weg 914437793 (2,6 km). Nach Regeln aufgeschlüsselt stieg
`A_segregated` um 12,3 km, und `A_cycle_only` fiel um 6,4 km, weil 9,0 km bestehender Radwege im
Lauf des Jahres 2021 `segregated=yes` erhielten (etwa Weg 459464518), was sie in Stufe A hält.

### barcelona/fua/2021

<!-- src: 6702f3ec96c7 -->

Ursache: **Kartieraktivität** (nachgeholte Kartierung bestehender Radwege, zur Hälfte durch eine
einzelne Person). A+B stieg von 656,1 auf 832,6 kartierte km (+176,5; die Schwelle liegt bei
65,6). Nach Regeln aufgeschlüsselt: `A_cycle_only` +91,2 km, `A_segregated` +56,9, `B_shared` +33,1,
`A_track_side` −4,9. 25,3 km des Zuwachses bei `A_segregated` sind bestehende Radwege, die
`segregated=yes` erhielten, was sie innerhalb von Stufe A verschiebt. 215,6 km liegen auf Wegen,
die 2020 keiner Stufe angehörten, und 187,1 km davon auf Wegen, die 2020 erstmals gezeichnet
wurden. Gemessen an den v3-Stufen (0,7 km mehr) verteilen sie sich auf 83 Gemeinden: Barcelona
41,2 km, Sabadell 19,0, Viladecans 15,2, Sant Cugat del Vallès 11,5, L'Hospitalet de Llobregat
9,1. Eine einzelne Person zeichnete 52,5 % der km, verteilt über 70 Gemeinden. Das Zeichnen
erreichte von April bis Juni 2020 seinen Höhepunkt (94,6 km). Das ist eine netzweite Nachholung,
kein einzelner Ausbau. Dass es Nachholung und kein Neubau war, ist aus dieser Verteilung
geschlossen, vor Ort ist es nicht geprüft. Bestehende Wege wurden außerdem in Stufe B umgetaggt,
etwa Weg 127720993 und Weg 112450547 (`highway=footway` -> `path` + `bicycle=designated`, jetzt
`B_shared`). Die Aktivität war hoch, aber ohne Spitze: 32.541 Bearbeitungen (Grenzwert 46.004),
bei einem Anteil des aktivsten Mappers von 0,42 (unter der `single_mapper`-Schwelle von 0,5). Im
selben Jahr wuchs Stufe D (15,4 -> 40,3 km markierte Radfahrstreifen, etwa Weg 34048002) und
ebenso Stufe E (0,1 -> 13,9 km: Fahrradstraßen auf den Seitenfahrbahnen des Passeig de Gràcia,
etwa Weg 116343002, und Busspuren in der Carrer de Sants, Weg 45185735).

### berlin/lau/2019

<!-- src: 1165d8130647 -->

Ursache: **Umtaggung**. `legacy_km` stieg von 13,8 auf 24,7, weil Kartierende Hauptstraßen das
ältere Schema `sidewalk:*:bicycle=yes` hinzufügten (Regel `X_sidewalk_bicycle_permitted`, 4,3 ->
15,9 km), etwa Weg 144884824 und Weg 31099696 (Straßen der Kategorie secondary, die
`sidewalk:both:bicycle=yes` erhielten, 2,5 und 2,2 km). Diese Seiten sind von den Stufen
ausgeschlossen, die Hauptkennzahl bleibt also unberührt (A+B 1.640 -> 1.612 km, unter der
Sprungschwelle).

### berlin/lau/2022

<!-- src: b97f55bf41c3 -->

Ursache: **Kampagne** (Neukartierung straßenbegleitender Radwege und von Wegen „Gehweg, Radfahren
erlaubt“), kein Verlust an gebauter Infrastruktur. A+B fiel von 1.677,1 auf 1.494,4 kartierte km.
Rund 200 km Straßenseiten (196–209 km, je nachdem, wie umgetaggte Seiten zugeordnet werden)
wechselten von `cycleway=track` zu `cycleway=separate` (etwa Weg 155594970, Weg 193875622), und
nur ein Teil der separaten Wege war bis zum 1. Januar 2022 gezeichnet (+121 km neuer
`highway=cycleway`). Außerdem verließen 135 km eigenständiger Wege die Stufen A und B, als
`highway=path` + `bicycle=designated` zu `highway=footway` + `bicycle=yes` (89 km) oder zu
`highway=path` + `bicycle=yes` (22 km) wurde, was der Klassifikator zu Recht nicht zählt. Von
diesen 135 km waren 84 km `B_shared` (etwa Weg 354012617, Weg 699975735). Weitere 46 km waren
getrennte Geh- und Radwege, die v4 als `A_segregated` einstuft (etwa Weg 887604839) und v3 als B
zählte; unter v4 verteilt sich der Verlust also auf beide Stufen: A −125,4 km, B −57,4 km. Die
50.701 Bearbeitungen des Jahres (das 2,2-Fache von 2021) werden angeführt vom Anlegen von
`highway=footway`, von `cycleway:both=no` und von `cycleway:right=track -> separate`; eine
einzelne Person nahm 51 % davon vor (`single_mapper`).

### berlin/lau/2026

<!-- src: 9b8da8553d68 -->

Ursache: **Umtaggung** (Bereinigung alter Tags). `legacy_km` von 19,3 auf 3,9: `cycleway=opposite`
verschwand im Lauf des Jahres 2025 von eingestuften Seiten (9,0 -> 0,0 km, etwa Weg 4787341
auf einer `bicycle_road`), und `sidewalk:*:bicycle=yes` fiel von 9,9 auf 3,1 km (Weg 111283473 ->
`cycleway:both=no`). Der neue Wert `cycleway:*=crossing` auf Straßenseiten (etwa Weg 1133761372,
`cycleway:right=lane` -> `crossing`) wird seit v2 erkannt (ausgeschlossen, Untertyp `crossing`)
und erscheint daher nicht mehr als unerkannt. Die km der Hauptkennzahl stiegen normal (A+B 1.500
-> 1.532).

### berlin/fua/2022

<!-- src: f5a17bd3a341 -->

Ursache: **Kampagne**, dieselbe Neukartierung straßenbegleitender Radwege wie bei
berlin/lau/2022, ausgedehnt nach Brandenburg. `legacy_km` von 48,1 auf 73,0, weil
`sidewalk:both:bicycle=yes` auf ländlichen Hauptstraßen von 41,1 auf 67,6 km wuchs;
Straßenseiten wechselten von `cycleway=right`/`use_sidepath` zu `cycleway:right=separate` (Weg
206903446 mit 3,8 km; Weg 449341004); `unrecognised_km` fiel von 16,9 auf 9,1 (Klassifikator ab
v2). A+B fiel von 3.808,5 auf 3.460,0 km (−9,2 %, unter der Sprungschwelle von 10 %), bei 77.158
Bearbeitungen und einem Anteil des aktivsten Mappers von 0,50.

### bordeaux/fua/2019

<!-- src: b2b7e03f506a -->

Ursache: **Kartieraktivität**, angeführt von einer einzelnen Person (`single_mapper`), meist
Radwege, die neben Straßen gezeichnet wurden. A+B stieg von 850,1 auf 959,5 km (+109,3 km;
Schwelle 85,0). Bei einem Geometrieabgleich innerhalb von 10 m sind 140,4 km eingestufter
Geometrie neu und 30,7 km weggefallen. Von den neuen liegen 109,2 km neben bereits kartierten
Straßen, deren Seiten meist kein Radweg-Tag trugen (etwa Weg 651236625 mit 2,3 km entlang einer
Straße der Kategorie secondary), und 17,2 km dort, wo vorher kein Weg kartiert war (etwa Weg
517088624, eine `Voie verte`). Der größte einzelne Verlust ist Weg 194343158, die Piste Roger
Lapébie (14,2 km), umgetaggt von `highway=cycleway` zu `highway=path` + `bicycle=yes`, was keine
Stufe zählt; zum 1. Januar 2020 war sie wieder ein Radweg. Die 7.874 Bearbeitungen des Jahres
2018 bleiben unter dem Spitzen-Grenzwert (13.176), verteilt auf 1.397 Changesets (größtes
Changeset 1,8 %), doch eine einzelne Person nahm 50 % davon vor, darunter 632 der 964 neuen
`highway=cycleway`-Wege, und legte 44 % der 175,0 km an A/B-Wegen mit IDs an, die 2018 neu waren
(zu den neuen IDs gehören auch die Teilstücke geteilter Wege).

### bratislava/lau/current

<!-- src: 7f8fdba89ce6 -->

Ursache: **Kampagne** (Fußwegenetz), der städtische Teil von `bratislava/fua/current`. 7.114
gezählte Bearbeitungen zwischen dem 1. Januar und dem 3. Oktober 2026, bei einem Grenzwert von
6.198,6 (2 × Median 4.101 × 0,756). 5.362 davon geben einem Weg `highway=footway` (5.290 neue
Wege; 1.387 Bürgersteige, 768 Querungen), und 399 legen `highway=path` an. Die Bearbeitungen
verteilen sich auf 1.173 Changesets (größtes Changeset 2,5 %) und 85 Kartierende (Anteil des
aktivsten Mappers 0,29), mit 578 bis 1.079 Bearbeitungen in jedem Monat. A+B stieg normal
(164,8 -> 172,1 km).

### bratislava/fua/2022

<!-- src: 141cc0c32a28 -->

Ursache: **Kartieraktivität** (neue Radwege). A+B stieg von 282,2 auf 315,0 km (+32,7, Schwelle
28,2). Wege, die im Stand von 2021 fehlen, brachten 31,6 km (146 Wege, fast alle
`highway=cycleway`, etwa Weg 962211589 mit 2,9 km; Weg 908367212 mit 2,5 km). Bisher nicht
eingestufte Wege, die nach A/B umgetaggt wurden, brachten 12,8 km. Verkürzte Wege und Teilungen
(−5,8 km) sowie gelöschte Wege (−5,4 km) glichen einen Teil davon aus. Unter v4 verteilt sich der
Schritt gleichmäßig auf die Stufen: A 168,3 -> 184,8 km, B 113,9 -> 130,2 km. Die neuen Wege
bringen A 18,3 km und B 13,3 km, die Umtaggungen 6,7 und 6,8 km. Im Lauf des Jahres 2021 wurden
31,9 km `highway=cycleway` + `foot=yes` zu `foot=designated` + `bicycle=designated` umgetaggt
(etwa Weg 230140923 mit 6,5 km; Weg 181363641 mit 3,0 km): 83 Wege in 32 Changesets von 9
Kartierenden, Anteil des aktivsten Mappers 0,66; 40 davon im Oktober 2021. Klassifikator v3
verschob diese km von A nach B. v4 stuft beide Tag-Kombinationen als `B_shared` ein (Fußgänger
erlaubt), die Umtaggung verschiebt also keine km mehr zwischen den Stufen. Der Anteil der Stadt
am Sprung beträgt +15,5 km (LAU 115,2 -> 130,7, unter ihrer Schwelle).

### bratislava/fua/current

<!-- src: b12f9de63748 -->

Ursache: **Kampagne** (Fußwegenetz), kein Radverkehr. 15.720 gezählte Bearbeitungen zwischen dem
1. Januar und dem 3. Oktober 2026, bei einem Grenzwert von 10.787,5 (2 × Median 7.137 × 0,756 des
Jahres). 12.922 davon geben einem Weg `highway=footway` (12.831 neue Wege: 5.156 getaggt als
`footway=sidewalk` und 2.144 als `footway=crossing`), und 708 legen `highway=path` an. Die
Bearbeitungen verteilen sich auf 1.909 Changesets (größtes Changeset 2,0 %) und 148 Kartierende
(Anteil des aktivsten Mappers 0,42). Die stärksten Monate waren Januar (2.601) und März (2.580).
Das setzt 2025 fort (13.206 Bearbeitungen, davon 9.256 angelegte Gehwege, knapp unter dem
damaligen Grenzwert von 14.274). Gehwege zählen in `config/activity.yaml` als radrelevante
Bearbeitungen, gehören aber keiner Stufe an; A+B bewegte sich also normal (426,1 -> 443,3 km).

### krakow/lau/2022

<!-- src: dcbffa9f4276 -->

Ursache: **Umtaggung** (Radfahren gegen die Einbahnrichtung neu getaggt). `legacy_km` fiel von
10,0 auf 3,3, als `cycleway=opposite_lane` von 106 auf 31 Wege zurückging (9,95 -> 3,30 km). 81
Bearbeitungen im Jahr 2021 entfernten es, verteilt auf 18 Changesets, 55 davon im Dezember. 66
dieser Bearbeitungen verlegten den Wert nach `cycleway:left=opposite_lane` (etwa Weg 26303566
Jana Zamoyskiego, Weg 195780180 Nadwiślańska, Weg 338492810 Świętej Anny). Der Diagnosewert für veraltete Tags
prüft nur den Schlüssel `cycleway` (`config/activity.yaml`); diese Seiten fallen also heraus,
während 5,94 der 6,65 km Radfahrstreifen der Stufe D bleiben. A+B stieg normal (199,9 ->
213,2 km).

### krakow/lau/2024

<!-- src: 7470f5bc8fd6 -->

Ursache: **Kartieraktivität**, etwa zur Hälfte neue Wege und zur Hälfte Umtaggung bestehender.
A+B stieg von 228,2 auf 261,5 km (+33,3; es gilt die Untergrenze von 25 km, 10 % wären 22,8).
- Neue Wege bringen 20,0 km: 232 getrennte Geh- und Radwege (+10,5 km) und 82 Radwege
  (+7,2 km), angeführt von Weg 1144928679, einem asphaltierten Radweg von 3,6 km auf einem Deich.
- Umtaggungen bestehender Wege bringen 17,8 km: 115 Wege von footway zu path mit
  `bicycle=designated` (+8,8 km, etwa Weg 180015552) und von path/track zu cycleway (+4,5 km,
  etwa Weg 725715216).

Unter v4 gehören die getrennten Geh- und Radwege zu Stufe A (`A_segregated`, v3 stufte sie als B
ein), und Weg 1144928679 trägt `foot=yes`, daher stuft v4 ihn als B ein (`B_shared`). A stieg
von 152,1 auf 169,6 km und B von 76,0 auf 91,9 km. 2023 gab es 17.860 Bearbeitungen (Grenzwert
20.852), bei einem Anteil des aktivsten Mappers von 0,27. Von den Bearbeitungen fügen 1.425
`bicycle=yes` hinzu, was keine Stufe verändert.

### krakow/fua/2019

<!-- src: aac2b952628e -->

Ursache: **Kartieraktivität** (die Wiślana Trasa Rowerowa). A+B stieg von 201,6 auf 237,8 km
(+36,2; es gilt die Untergrenze von 25 km). Niepołomice gewann 19,9 km: neue Radwege mit dem
Namen Wiślana Trasa Rowerowa (Weg 587335464 mit 4,3 km; Weg 592717702 mit 3,6 km; Weg 657293994 mit
1,6 km) und die Verlängerung von Weg 396571694 (+8,6 km). Die Wege 587335464 und 396571694 sind
asphaltiert und tragen `embankment=yes`. Krakau gewann 10,6 km; v4 lässt dort 1,5 km als
MTB-Strecke getaggter Wege weg (`X_mtb_trail`), die v3 mitzählte. Die Aktivität war normal:
7.274 Bearbeitungen im Jahr 2018 (Median 13.386), bei einem Anteil des aktivsten Mappers von
0,25.

### krakow/fua/2020

<!-- src: 86c5ead208ed -->

Ursache: **Kartieraktivität** (die Route Velo Raba östlich von Krakau). A+B stieg von 237,8 auf
280,7 km (+43,0; es gilt die Untergrenze von 25 km). Drwinia gewann 15,2 km: Radwege mit dem
Namen Velo Raba (Weg 723989965 mit 4,6 km Schotter auf einem Damm; Weg 723993777 mit 2,4 km; Weg
723993781 mit 1,8 km) und ein asphaltierter ausgewiesener Weg von 4,0 km (Weg 758100703). Krakau
gewann 12,7 km, Skawina 4,9 km und Zabierzów 3,3 km. 2019 gab es 8.358 Bearbeitungen (Median
13.386), bei einem Anteil des aktivsten Mappers von 0,30.

### krakow/fua/2021

<!-- src: 28a207494342 -->

Ursache: **Kartieraktivität**, einschließlich Wegen, die von `highway=construction` umgetaggt
wurden. A+B stieg von 280,7 auf 325,1 kartierte km (+44,4, Schwelle 28,1):
- 88 neue Radwege bringen 16,0 km und 61 neue ausgewiesene Wege 7,0 km;
- Gehwege, die zu ausgewiesenen Geh- und Radwegen wurden, bringen 12,8 km (155 Wege);
- 10 Umtaggungen `construction` -> `cycleway` bringen 6,0 km.

Krakau gewann 16,5 km, Miechów 6,6 km (Weg 298772347, ein asphaltierter Radweg von 2,6 km mit
`railway=abandoned`, vorher `highway=construction`), Drwinia 6,5 km und Niepołomice 5,1 km. 2020
gab es 8.387 Bearbeitungen (Median 13.386), bei einem Anteil des aktivsten Mappers von 0,24; das
größte Changeset hält 2,4 %.

### krakow/fua/2022

<!-- src: 2ad92803196c -->

Ursache: **Umtaggung**, dieselbe Umtaggung des Radfahrens gegen die Einbahnrichtung wie bei
`krakow/lau/2022`. Alle km mit veralteten Tags der FUA liegen in der Stadt: 9,96 -> 3,30 km, identisch mit der
LAU-Reihe. A+B stieg von 325,1 auf 350,4 km, unter der Sprungschwelle.

### krakow/fua/2023

<!-- src: 58670b3f9db4 -->

Ursache: **Kartieraktivität**, mit Neuzeichnungen. A+B stieg von 350,4 auf 398,9 km (+48,5,
Schwelle 35,0):
- neue Radwege bringen 28,0 km, denen 12,1 km gelöschte gegenüberstehen;
- 10 Umtaggungen `construction` -> `cycleway` bringen 8,0 km;
- neue ausgewiesene Wege bringen 15,6 km.

Zwei weitere Umtaggungen `construction` -> `cycleway` in Krakau (1,2 km) tragen `mtb:scale=0`,
daher schließt v4 sie aus (`X_mtb_trail`). Zu den gelöschten Radwegen gehören die Velo-Raba-Wege
von `krakow/fua/2020`, die jetzt durch Weg 1082048422 (9,2 km) ersetzt sind; Drwinia gewinnt
daher netto nur 1,5 km. Krakau gewann 14,4 km, Skawina 8,8 km, Gołcza 8,5 km (Weg 1027429591 mit
3,0 km) und Siepraw 5,7 km. 2022 gab es 13.950 Bearbeitungen (Median 13.386), bei einem Anteil
des aktivsten Mappers von 0,29.

### krakow/fua/2024

<!-- src: 71a15bb54b32 -->

Ursache: **Kartieraktivität**, einschließlich eines Bahntrassenradwegs. A+B stieg von 398,9 auf
474,0 km (+75,1, Schwelle 39,9): 148 neue Radwege (+32,9 km), 348 neue ausgewiesene Wege
(+23,1 km) und Umtaggungen bestehender Wege (+24,3 km).
- Krakau gewann 33,8 km (der Schritt von `krakow/lau/2024`).
- Proszowice gewann 13,3 km, darunter ein asphaltierter Radweg und ein asphaltierter Weg, beide mit
  `railway=abandoned`, `gauge=750` (Weg 767489246 mit 4,5 km; Weg 806031541 mit 3,4 km).
- Kocmyrzów-Luborzyca gewann 10,0 km.

Weg 1143714546 „Rodzinny Flow“ in Myślenice (3,9 km), ein `highway=path` in einer Richtung mit
`bicycle=designated`, `foot=no` und `mtb:scale:imba=1`, zählt nicht mehr: v3 ordnete ihn Stufe A
zu (`A_path_cycle_only`), v4 schließt ihn als MTB-Strecke aus (`X_mtb_trail`). 2023 gab es
22.071 Bearbeitungen (Grenzwert 26.772), bei einem Anteil des aktivsten Mappers von 0,25.

### ljubljana/lau/2021

<!-- src: babf53e41497 -->

Ursache: **Kampagne** (straßenbegleitende Radwege als separate Wege neu kartiert), auf eine
einzelne Person konzentriert. A+B stieg von 138,4 auf 193,6 km (+55,2, Schwelle 25,0).
Straßenseitiges `cycleway=track` (`A_track_side`) fiel von 76,0 auf 3,0 km je Seite, weil 357
Straßenseiten das Tag verloren, als die Straßen auf `bicycle=no` + `foot=no` umgetaggt wurden
(etwa Weg 149769844 Zaloška cesta, Weg 369157584 Letališka cesta). An ihre Stelle traten separate
straßenbegleitende Radwege. 74,6 km neuer Seiten sind `highway=cycleway` + `foot=designated` +
`segregated=yes` (Regel `A_segregated`, etwa Weg 869836662 Celovška cesta, Weg 866720417
Dunajska cesta), und 17,6 km bestehender Gehwege und Wege (`footway`, `path`) wurden ebenso umgetaggt (Weg 530977027
Vilharjeva cesta, `highway=footway` -> `cycleway`). 26,6 km neuer Seiten sind `B_shared`, meist
`highway=cycleway` + `foot=designated` ohne Trennung (etwa Weg 866576235 Dunajska cesta,
`segregated=no`), und 13,3 km sind reine Radwege `highway=cycleway` (`A_cycle_only`, etwa Weg
849525190 Ižanska cesta, ohne `foot`-Tag). Stufe A stieg von 120,8 auf 151,3 km und Stufe B von
17,6 auf 42,2 km. 114,9 der 142,2 km neuer A+B-Seiten liegen auf Weg-IDs, die es am 1. Januar
2020 nicht gab. Der Datenpunkt zählt 6.205 Bearbeitungen im Jahr 2020 bei einem Median von 2.779
(Grenzwert 5.558). 4.669 davon fallen in die Monate Oktober bis Dezember 2020. Die größten Gruppen
sind 1.262 angelegte `highway=path`, 1.206 `highway=cycleway` und 864 `highway=footway`. Sie
verteilen sich auf 1.037 Changesets (größtes Changeset 2,3 %), und der Anteil des aktivsten
Mappers beträgt 0,52 (`single_mapper`).

### ljubljana/lau/2022

<!-- src: c2695825e095 -->

Ursache: **Kampagne** (ein Umtaggungsdurchgang über die getrennten straßenbegleitenden Radwege,
`highway=cycleway` -> `highway=path`). Unter v4 verschiebt er fast nichts zwischen den Stufen.
8.004 Bearbeitungen im Jahr 2021 (Grenzwert 5.558, Anteil des aktivsten Mappers 0,67). Darunter
sind 641 `highway`-Änderungen von cycleway zu path, 692 Bearbeitungen an `cycleway:surface`, 280
an `segregated` sowie 1.632 angelegte `highway=footway` und 1.529 angelegte `highway=path`. 41,1 km
Seiten (327) änderten nur ihren `highway`-Wert und bleiben `A_segregated`, weil v4 einen
getrennten Geh- und Radweg unabhängig vom `highway`-Wert als A einstuft (Weg 530977027 Vilharjeva
cesta, Weg 878942853 Litijska cesta: `highway=cycleway` -> `path`, wobei `bicycle=designated`,
`foot=designated` und `segregated=yes` bleiben). 7,9 km `B_shared`-Seiten erhielten
`segregated=yes`, meist im selben Umtaggungsdurchgang, und wechselten zu `A_segregated` (etwa Weg
868033233 Bratislavska cesta). Neue straßenbegleitende Radwege brachten 32,1 km `A_segregated`
(etwa Weg 986479122 Vodnikova cesta). Stufe A stieg von 151,3 auf 175,9 km, und Stufe B fiel von
42,2 auf 36,0 km. A+B stieg von 193,6 auf 211,9 km (+18,3), unter der Sprungschwelle (25,0).
Unter v3 verschob dieselbe Umtaggung 41,9 km von A nach B und begründete Ljubljanas B-lastige
Aufteilung; v4 kennt diese Aufteilung nicht (B macht im aktuellen Lauf 0,15 von A+B aus).

### ljubljana/lau/2023

<!-- src: 1a71fd26144f -->

Ursache: **Kampagne**, das Hauptjahr derselben Umtaggung `highway=cycleway` -> `highway=path`.
Der Datenpunkt zählt 7.934 Bearbeitungen im Jahr 2022 (Grenzwert 5.558), 875 davon
`highway`-Änderungen von cycleway zu path. Der Anteil des aktivsten Mappers beträgt 0,83, doch es
gibt keinen km-Sprung, daher greift `single_mapper` nicht. Unter v4 verschiebt die Umtaggung
nichts zwischen den Stufen. 57,4 km Seiten (607) bleiben `A_segregated` (etwa Weg 640258468
Letališka cesta, Weg 849525190 Ižanska cesta), und 8,5 km bleiben `B_shared` (`segregated=no`,
etwa Weg 875765266 Pot Roberta Blinca). Neue straßenbegleitende Radwege brachten 12,2 km
`A_segregated`. Der größte Verlust waren 6,4 km `B_shared` auf dem geschotterten Pot spominov in
tovarištva (PST), umgetaggt zu `highway=track` + `bicycle=yes` (Weg 863298376, Weg 858117391).
Stufe A stieg von 175,9 auf 189,6 km, und Stufe B fiel von 36,0 auf 31,1 km. A+B bewegte sich von
211,9 auf 220,7 km (+8,8), unter der Sprungschwelle.

### ljubljana/lau/2024

<!-- src: 5746cba093ff -->

Ursache: **Kartieraktivität** (weitere straßenbegleitende Radwege als separate
`highway=path`-Wege gezeichnet), die Ausläufer der Kampagne von 2021 bis 2022. Der Datenpunkt
zählt 7.922 Bearbeitungen im Jahr 2023 (Grenzwert 5.558), 2.154 davon im März, bei einem Anteil
des aktivsten Mappers von 0,64. Angeführt werden die Bearbeitungen von 1.798 angelegten
`highway=footway` und 1.094 angelegten `highway=path` sowie 793 Bearbeitungen an
`cycleway:surface`. Hinzu kamen 20,6 km neuer `A_segregated`-Seiten (etwa Weg 1172474051 Cesta
dveh cesarjev) und 5,2 km neuer `B_shared`-Seiten (Weg 1194995566 Cesta 27. aprila,
`segregated=no`). 29,4 der 33,6 km neuer A+B-Seiten liegen auf Weg-IDs, die es am 1. Januar 2023
nicht gab, während 18,4 km A+B-Seiten verschwanden. A+B stieg von 220,7 auf 224,6 km (+3,9),
unter der Sprungschwelle.

### ljubljana/fua/2021

<!-- src: 4db794ce1279 -->

Ursache: **Kampagne**, vor allem die Neukartierung straßenbegleitender Radwege in der Stadt
(siehe `ljubljana/lau/2021`). A+B stieg von 229,8 auf 303,4 km (+73,6, Schwelle 25,0). Von diesem
Anstieg liegen +55,2 km in der LAU und +18,4 km im übrigen FUA-Gebiet (A+B der FUA ohne die LAU:
91,4 -> 109,8 km). Außerhalb der Stadt sind die größten Zugänge 12,4 km straßenseitiges
`cycleway=track` (7,6 km auf bestehenden Straßen getaggt, etwa Weg 720165109 Drenov Grič; 4,8 km
auf neuen Wegen, etwa Weg 809933528) und 10,0 km `B_shared`. Das meiste davon sind neue
`highway=path` + `bicycle=designated` ohne `foot`-Tag, die v4 als `B_shared` einstuft, weil
Fußgänger einen path standardmäßig benutzen dürfen (Entscheidung 9; etwa Weg 888232569). Der
Datenpunkt zählt 10.736 Bearbeitungen im Jahr 2020, davon 5.731 in den Monaten Oktober bis
Dezember. Der Median der FUA liegt bei 9.703, es gibt also keine Aktivitätsspitze. Der Anteil des
aktivsten Mappers beträgt 0,30.

### ljubljana/fua/2022

<!-- src: c4f83e9d33ec -->

Ursache: **Kartieraktivität** außerhalb der Stadt. A+B stieg von 303,4 auf 345,0 km (+41,6,
Schwelle 30,3). Der Anteil der LAU daran betrug +18,3 km, das übrige FUA-Gebiet brachte +23,3 km
(109,8 -> 133,1). Zu den neuen Seiten außerhalb der LAU gehören 14,0 km `B_shared` und 11,9 km
`A_cycle_only` (`highway=cycleway` ohne `foot`-Tag, etwa Weg 891270259). Die Hälfte der
`B_shared`-km sind Wege mit `bicycle=designated` ohne `foot`-Tag (etwa Weg 906631574, ein
benannter Weg von 4,8 km ohne MTB-Tags, sodass `X_mtb_trail` nicht greift); der Rest sind meist
kombinierte Wege mit `foot=designated` + `segregated=no` (etwa Weg 981127313). 68,1 der 71,9 km
neuer A+B-Seiten liegen auf Weg-IDs, die es ein Jahr zuvor nicht gab. Die FUA enthält auch die
städtische Umtaggung `highway=cycleway` -> `highway=path` (siehe `ljubljana/lau/2022`), die diese
Seiten unter v4 in `A_segregated` belässt. 12.751 Bearbeitungen im Jahr 2021, Anteil des
aktivsten Mappers 0,42, keine Aktivitätsspitze.

### ljubljana/fua/2023

<!-- src: 197f59ff4aa6 -->

Ursache: **Kartieraktivität** außerhalb der Stadt. A+B stieg von 345,0 auf 389,7 km (+44,7,
Schwelle 34,5). Die LAU brachte +8,8 km, das übrige FUA-Gebiet +35,9 km (133,1 -> 169,0). Von den
37,0 km neuer A+B-Seiten außerhalb der LAU sind 16,6 km `highway=cycleway` ohne `foot`-Tag
(`A_cycle_only`, etwa Weg 1086139162 mit 3,1 km) und 8,3 km neue `B_shared`. Die Umtaggung
`highway=cycleway` -> `highway=path` der LAU (siehe `ljubljana/lau/2023`) liegt ebenfalls in der
FUA und ändert unter v4 weder A+B noch die Aufteilung. 11.261 Bearbeitungen im Jahr 2022 (keine
Aktivitätsspitze), verteilt auf 2.874 Changesets (größtes Changeset 0,8 %). Der Anteil des
aktivsten Mappers von 0,60 löst `single_mapper` aus. Der Anteil in der Stadt liegt im selben Jahr
bei 0,83, und ihre wichtigste Veränderung in diesem Jahr ist die Umtaggung, die A+B nicht ändert.
Der Sprung selbst kommt von außerhalb der Stadt.

### ljubljana/fua/2024

<!-- src: 4401dd1f707b -->

Ursache: **Kartieraktivität** außerhalb der Stadt. A+B stieg von 389,7 auf 437,6 km (+47,9,
Schwelle 39,0). Die LAU brachte +3,9 km, das übrige FUA-Gebiet +44,0 km (169,0 -> 213,0).
Außerhalb der LAU sind die neuen Seiten 16,6 km `B_shared` (meist Wege mit `bicycle=designated` +
`foot=designated`, etwa Weg 1217282229), 16,0 km straßenseitiges `cycleway=track` (etwa Weg
150354472 Loška cesta, `cycleway:left=track`; 4,6 km straßenseitiger Radwege außerhalb der LAU
verloren das Tag) und 10,1 km `highway=cycleway` ohne `foot`-Tag (`A_cycle_only`, etwa Weg
1182208725 mit 3,1 km). 12.619 Bearbeitungen im Jahr 2023, Anteil des aktivsten Mappers 0,41, keine
Aktivitätsspitze.

### ljubljana/fua/2025

<!-- src: e7327f92e03f -->

Ursache: **Kartieraktivität** außerhalb der Stadt. A+B stieg von 437,6 auf 524,8 kartierte km
(+87,2, Schwelle 43,8). +84,3 km davon liegen außerhalb der LAU (213,0 -> 297,3) und +2,9 km
innerhalb. Von 105,0 km neuer A+B-Seiten liegen 53,2 km auf Wegen, die es 2024 schon gab und die
neu in A oder B eingestuft wurden. Die größten Gruppen sind Straßen der Kategorie secondary ohne
Radweg-Tag (12,0 km), Wege (9,9 km) und Straßen der Kategorie primary ohne Radweg-Tag (9,2 km),
etwa Weg 28675982 (Straße 102), die außerhalb der Stadt auf beiden Seiten `cycleway=track`
erhielt. Ein Teil der neuen km ist wahrscheinlich neue Infrastruktur; das ist aus den Tags
zweier Wege geschlossen. Weg 442354000 außerhalb der Stadt wechselte von `highway=track` zu
`highway=cycleway`, mit einem fixme-Hinweis, die Oberfläche nach der Fertigstellung 2024 zu
ändern. In der Stadt wechselte Weg 1198338337, die Pionirska proga, von `railway=abandoned` zu
`highway=cycleway`. Die übrigen 51,8 km liegen auf Weg-IDs, die es ein Jahr zuvor nicht gab (neue
oder geteilte Wege), und 12,8 km A+B-Seiten gingen verloren. 9.703 Bearbeitungen im Jahr 2024,
verteilt auf 2.785 Changesets, Anteil des aktivsten Mappers 0,19, keine Aktivitätsspitze.

### lyon/lau/2025

<!-- src: 1f6d98124f59 -->

Ursache: **Kampagne** (Fußwegenetz, kein Radverkehr). 26.893 gezählte Bearbeitungen im Jahr 2024
bei einem Grenzwert von 6.700 (das Doppelte des Medians von 3.350): 23.570 davon legen
`highway=footway`-Wege an, 18.046 allein im Juli 2024. Die 18.039 Gehwege, die in jenem Juli
erstmals gezeichnet wurden, sind Bürgersteige (`footway=sidewalk`, 11.252), Querungen (6.041) und
Verkehrsinseln (592), etwa Weg 1298053632; drei Kartierende legten 99 % davon an, in 558
Changesets. Über das Jahr beträgt der Anteil des aktivsten Mappers 0,37, das größte Changeset
hält 2,0 %. Gehwege zählen in `config/activity.yaml` als radrelevante Bearbeitungen, gehören aber
keiner Stufe an; A+B bewegte sich also normal (83,4 -> 94,7 km, +11,3 km bei einer Sprungschwelle
von 25 km), vor allem durch Radwege, die neben Straßen gezeichnet wurden (etwa Weg 1311767651 mit
1,9 km entlang einer Straße der Kategorie secondary, deren Seite einen markierten Radfahrstreifen
hatte).

### lyon/fua/2021

<!-- src: 95cdfd58609f -->

Ursache: **Kartieraktivität** (Tags für Radwege an bestehenden Straßen ergänzt, dazu neue Wege),
an zweiter Stelle der **Klassifikator**: Der Prüfhinweis greift nur unter v4. A+B stieg von 577,5
auf 637,1 kartierte km (+59,6 km; die Schwelle liegt bei 57,8). A stieg von 268,3 auf 306,6 km
und B von 309,2 auf 330,6 km. Im Lauf des Jahres 2020 wurden 36,6 km Straßenseiten an
bestehenden Straßen zu straßenbegleitenden Radwegen der Stufe A (`A_track_side`):
`cycleway=track` kam auf 13,7 km hinzu und `cycleway:right=track` auf 12,7 km, 4,2 km davon
vorher markierte Radfahrstreifen. Die längsten liegen an der Route de Paris (5,7 km, etwa Weg
258511906) und der Route de Grenoble (5,1 km, etwa Weg 5078322). 7,1 km davon liegen in der
Gemeinde Lyon. Wege, die 2020 erstmals gezeichnet wurden, bringen 49,7 km, das meiste gemeinsame
Geh- und Radwege (`B_shared` 29,1 km, etwa Weg 780336508, ein `highway=cycleway` mit `foot=yes`)
und Radwege (`A_cycle_only` 11,9 km, `A_segregated` 4,5 km). Bestehende Gehwege und Wege (`footway`, `path`), die mit
`bicycle=designated` umgetaggt wurden, bringen 6,4 km in B. Verluste gleichen einen Teil des
Zuwachses aus. 15,1 km gemeinsamer Geh- und Radwege verließen Stufe B, vor allem Weg 129002330
(Chemin du Bac à Traille, 4,8 km), der von `highway=cycleway` + `bicycle=designated` zu
`highway=track` + `bicycle=yes` wechselte, und 10,2 km Radwege wurden gelöscht. Der Anteil des
Klassifikators: `X_mtb_trail` von v4 lässt am 1. Januar 2020 insgesamt 8,6 km ausdrücklich als MTB-Strecke
getaggter Wege weg, ein Jahr später aber nur noch 5,7 km. Die Voie Verte de la Bourbre (Weg
374341061, Weg 374341073; 3,9 km) verlor im Lauf des Jahres 2020 ihre `mtb:scale=0`-Tags und kam
in `B_shared`. Unter v3 stieg dasselbe Jahr von 586,1 auf 642,8 km (+56,7 bei einer Schwelle von
58,6) und war nicht markiert. Die Aktivität war gewöhnlich: 10.596 Bearbeitungen, 316
Kartierende, Anteil des aktivsten Mappers 0,08. Stufe E stieg im selben Jahr von 56,8 auf
91,2 km, vor allem durch Busspuren, die neu auf Straßen getaggt wurden (etwa Weg 3237103, Avenue
Jean Jaurès).

### lyon/fua/2025

<!-- src: 19f0762e8635 -->

Ursache: **Kampagne**, die Kartierung von Bürgersteigen und Querungen im Juli 2024 aus
lyon/lau/2025, ausgedehnt auf die FUA. 49.952 gezählte Bearbeitungen im Jahr 2024 bei einem
Grenzwert von 26.492 (Median 13.246): 38.997 legen `highway=footway` an, 27.361 davon im Juli 2024.
Die 27.348 Gehwege, die in jenem Juli erstmals gezeichnet wurden, sind 17.139 Bürgersteige, 9.146
Querungen und 750 Verkehrsinseln; drei Kartierende legten 99 % davon in 765 Changesets an. Über
das Jahr beträgt der Anteil des aktivsten Mappers 0,30, das größte Changeset hält 1,5 %. A+B
stieg von 735,4 auf 769,1 km (+33,7 km, unter der Sprungschwelle von 76,9 km).

### lyon/fua/2026

<!-- src: c9db622ccb79 -->

Ursache: **Kartieraktivität**, verteilt auf viele Kartierende, keine Kampagne und kein Import.
A+B stieg von 769,1 auf 847,6 km (+78,5 km; Schwelle 76,9). Bei einem Geometrieabgleich innerhalb
von 10 m zwischen den beiden Ständen sind 89,0 km (je Seite) eingestufter Geometrie neu und
14,4 km weggefallen. Von den neuen sind 44,2 km Radwege und Wege, die neben bereits kartierten
Straßen gezeichnet wurden; 19,2 km sind kartierte Gehwege, die zu ausgewiesenen Wegen umgetaggt
wurden (etwa Weg 26420781, Promenade de la Vorla, `highway=footway` + `bicycle=yes` ->
`highway=path` + `bicycle=designated`); 11,2 km sind Feldwege, die ebenso umgetaggt wurden (Weg
171670318, der Treidelpfad der ViaRhôna, 3,2 km); und 6,2 km waren am 1. Januar 2025
`highway=construction` und sind jetzt Radwege (etwa Weg 1417218765 mit dem Namen `VL7`). Das
meiste landet in Stufe B (`B_shared`): `highway=path` + `bicycle=designated` + `segregated=no`
wuchs von 201,6 auf 262,2 km. Die Bearbeitungen des Jahres 2025 waren normal (20.435 bei einem
Grenzwert von 26.492; 415 Kartierende, Anteil des aktivsten Mappers 0,19), und die A/B-Wege mit
neuen IDs (61,1 km) legten 84 Kartierende an, keine Person mit mehr als 18 % der km.

### madrid/lau/2025

<!-- src: 6fe2049caf6d -->

Ursache: **Kampagne** (Fußwegenetz, kein Radverkehr). 27.859 gezählte Bearbeitungen im Jahr 2024
bei einem Grenzwert von 15.538 (das Doppelte des Medians von 7.769). 20.601 davon legen
`highway=footway`-Wege an: Von den 21.110 Wegen, die 2024 zu Gehwegen wurden, sind 8.666
`footway=crossing`, 7.267 `footway=sidewalk` und 5.095 ohne Typ (etwa Weg 4330856, Weg 7732915).
Die Bearbeitungen verteilen sich auf 2.675 Changesets (größtes Changeset 1,4 %), bei einem Anteil
des aktivsten Mappers von 0,33. Die Bearbeitungen dieser Person (9.212 davon angelegte Gehwege)
fallen in die Monate März bis Mai und August bis September, 6.099 davon in den März. Gehwege
gehören keiner Stufe an, A+B bewegte sich also normal: von 321,0 auf 329,5 kartierte km (+8,5;
die Sprungschwelle liegt bei 32,1). Die Querungen teilen die Radwege dort, wo Fußwege sie kreuzen:
Die eingestuften Wege stiegen von 1.068 auf 2.057, mit 61,0 km auf 972 neuen
`highway=cycleway`-Wegen (etwa Weg 1320432687, Anillo Verde Ciclista) und 51,2 km Verlust an 313
bestehenden Wegen, die verkürzt wurden (etwa Weg 27885470). Deshalb wuchs A+B nur um 8,5 km.
Stufe A fiel von 254,7 auf 252,6 km, und B stieg von 66,3 auf 76,9 km, weil 8,7 km bestehender
Radwege `foot=yes` oder `foot=designated` erhielten und von `A_cycle_only` zu `B_shared`
wechselten (etwa Weg 27874960).

### madrid/lau/current

<!-- src: 9e318379a8d9 -->

Ursache: **Kampagne**, dieselbe Gehwegkartierung, fortgesetzt im Jahr 2026. Gezählt wurden 11.959
Bearbeitungen vom 1. Januar bis zum Stand vom 3. Oktober 2026, bei einem Grenzwert von 11.742,8
(15.538, hochgerechnet auf den verstrichenen Jahresanteil von 0,756). 9.102 Bearbeitungen legen
`highway=footway`-Wege an (von den 9.238 neuen Gehwegen: 3.984 Bürgersteige, 2.227 Querungen,
2.835 ohne Typ; etwa Weg 6126321); der Anteil des aktivsten Mappers beträgt 0,32 (3.759 angelegte
Gehwege), und die Bearbeitungen dieser Person fallen fast alle in die Monate Mai bis September.
1.631 Changesets, das größte Changeset hält 1,4 %. Der Datenpunkt 2026 (15.500 Bearbeitungen im
Jahr 2025) liegt knapp unter seinem Grenzwert von 15.538; das ist also das dritte Jahr derselben
Fußwegkartierung, kein neues Ereignis. A+B stieg von 346,4 auf 353,0 kartierte km (+6,7; die
Sprungschwelle liegt bei 34,6).

### madrid/fua/2025

<!-- src: 69f03a1b9840 -->

Ursache: **Kampagne**: die Gehwegkartierung von madrid/lau/2025, aus Sicht der FUA. 39.353
gezählte Bearbeitungen im Jahr 2024 bei einem Grenzwert von 34.450 (Median 17.225). 27.859 davon
liegen im Municipio. Die 11.494 Bearbeitungen außerhalb liegen nahe an den 9.392 von 2023 (17.225
in der FUA abzüglich 7.833 in der LAU); der Überschuss kommt also aus der Stadt. 26.468
Bearbeitungen legen `highway=footway` an. Die aktivste kartierende Person (Anteil 0,24; 9.235
angelegte Gehwege) zeigt dasselbe Monatsmuster wie die aktivste Person in der LAU (März 6.122,
April 1.694, Mai 1.098). 4.975 Changesets, das größte Changeset hält 1,0 %. A+B stieg von 1.122,0
auf 1.172,4 kartierte km (+4,5 %, unter der Sprungschwelle von 10 %).

### oslo/lau/2021

<!-- src: aacb9742ad1d -->

Ursache: **Umtaggung** (gang- og sykkelvei neu getaggt), an zweiter Stelle **Kartieraktivität**.
A+B stieg von 263,9 auf 298,1 km (+34,2 km, +13,0 %; die Regel verlangt 26,4), vor allem in Stufe
B (222,0 -> 248,5), A von 41,9 auf 49,6. Im Lauf des Jahres 2020 wurden 270 Seiten bestehender
Gehwege (und einiger Wege) als kombinierte Geh- und Radwege umgetaggt, `highway=footway` ->
`highway=cycleway` + `foot=designated` (Regel `B_shared`, +26,6 km; etwa Weg 3692715 mit 1,0 km; Weg
98638646). So wird die übliche norwegische Anlage kartiert (siehe `oslo/b_share_of_ab` in
`docs/review/trust/NO.md`). Neu gezeichnete Wege brachten 7,2 km `B_shared`, 6,9 km
`highway=cycleway` ohne `foot`-Tag (`A_cycle_only`) und 1,4 km straßenbegleitende Radwege.
Umtaggungen aus A/B heraus und Löschungen nahmen 8,9 km weg. Die Aktivität war gewöhnlich: 7.193
gezählte Bearbeitungen (im Vorjahr 6.158), 111 Kartierende, Anteil des aktivsten Mappers 0,36.

### oslo/fua/2021

<!-- src: 10bbd47754a5 -->

Ursache: **Kartieraktivität** (kombinierte Geh- und Radwege als separate Wege gezeichnet), an
zweiter Stelle **Umtaggung**. A+B stieg von 1.640,9 auf 1.836,9 km (+196,0 km, +11,9 %; die Regel
verlangt 164,1): B +229,1 km, A −33,2 km. Drei Veränderungen im Lauf des Jahres 2020 machen das
aus. Erstens 1.348 neue Wege `highway=cycleway` + `foot=designated` (+177,4 km `B_shared`, etwa
Weg 815611705 mit 3,5 km), von denen nur 6,5 km in Oslo kommune liegen; der Zuwachs liegt also in den
umliegenden Gemeinden. Zweitens wurden bestehende Gehwege, Wege und Feldwege nach demselben Schema
umgetaggt (+99,9 km, 677 Seiten; etwa Weg 23330061 mit 4,8 km, `highway=footway` -> `cycleway`).
Drittens erhielten 161 Seiten (35,5 km) `highway=cycleway` ohne `foot`-Tag ein `foot=designated`
(oder `foot=yes`), was sie von `A_cycle_only` zu `B_shared` verschiebt (etwa Weg 620971715). Das
erklärt den Rückgang in Stufe A und bleibt innerhalb von A+B. Unter v3 betrug diese Verschiebung
116,3 km, weil v3 auch Radwege von `foot=yes` zu `foot=designated` verschob; v4 stuft `foot=yes`
bereits als `B_shared` ein. Gelöschte A/B-Wege nahmen 35,0 km weg. Die Bearbeitungen stiegen von
14.646 auf 20.201 (281 Kartierende, Anteil des aktivsten Mappers 0,20), keine Aktivitätsspitze.

### paris/lau/2020

<!-- src: e118d7afe2e3 -->

Ursache: **Kartieraktivität**, mit **Umtaggung** im Diagnosewert für veraltete Tags. A+B stieg von 223,9 auf
257,3 kartierte km, fast ganz durch 357 neue `highway=cycleway`-Wege (+40,8 km, etwa Weg
744744226, Weg 701119869) und 53 neue Straßen mit `cycleway=track` (+5,6 km), die im Lauf des
Jahres 2019 gezeichnet wurden, während der Plan Vélo der Stadt lief. Eine amtliche Zahl zum Ausbau
in jenem Jahr ist hier nicht zitiert; es sind also nur kartierte km. Die Aktivität
war normal (8.422 Bearbeitungen, Anteil des aktivsten Mappers 0,22). `legacy_km` von 49,5 auf 8,2
ist die Umtaggung des Radfahrens gegen die Einbahnrichtung: `cycleway=opposite_lane` von 44,3
auf 6,4 km (Weg 25599714 -> `cycleway:left=opposite`).

### paris/lau/2021

<!-- src: d4e4e12540b9 -->

Ursache: **Kartieraktivität**: die vorläufigen „coronapistes“ von 2020, wie sie kartiert sind
(eine amtliche Zahl zum Bau ist hier nicht zitiert). A+B stieg von 257,3 auf 305,6 kartierte km:
+29,3 km neuer `highway=cycleway`-Wege (Weg 840939982) und Straßen, die `cycleway=track` mit
`cycleway:temporary=yes` erhielten (Weg 31823633, Weg 41872851 `share_busway` -> `track`, Weg
31956307 `lane` -> `track`). `legacy_km` von 8,2 auf 3,4 ist das Ende der Umtaggung von
`opposite_lane` (Weg 24709554).

### paris/lau/2024

<!-- src: 9238b3300bef -->

Ursache: **Kampagne** (Fußwegenetz, kein Radverkehr). 70.335 gezählte Bearbeitungen im Jahr 2023
bei einem Median von 9.206: 60.239 davon legen `highway=footway`-Wege an (etwa Weg 4527565),
34.099 allein im Juli 2023, verteilt auf 3.910 Changesets (größtes Changeset 1,2 %), Anteil des
aktivsten Mappers 0,39. Gehwege zählen in `config/activity.yaml` als radrelevante Bearbeitungen,
gehören aber keiner Stufe an; A+B bewegte sich also normal (+14,4 km).

### paris/lau/2025

<!-- src: 192f0b69bd55 -->

Ursache: **Kampagne**, die Ausläufer der Gehwegkartierung von 2023. Im Jahr 2024 gab es 20.590
Bearbeitungen (Grenzwert 18.412): 8.307 angelegte `highway=footway`, dazu 2.675 neue `highway=cycleway`-Wege
(etwa Weg 4039351) und 1.504 ergänzte `cycleway:both=no`; Anteil des aktivsten Mappers 0,15, also
kein Effekt einer einzelnen Person. A+B stieg von 318,6 auf 345,7 kartierte km (+8,5 %, unter
der Sprungschwelle), im normalen jährlichen Rahmen.

### paris/fua/2019

<!-- src: beeb3e884ddc -->

Ursache: **Kartieraktivität**, gewöhnliche nachgeholte Kartierung, keine Kampagne und kein Import.
A+B stieg von 2.325,7 auf 2.571,5 kartierte km (+10,6 %): 1.336 neue `highway=cycleway`-Wege
(+236 km, etwa Weg 597170301), +71 km neuer `highway=path` + `bicycle=designated` und 51 km Stufe
B durch `bicycle=yes` -> `designated` (Weg 107496601); teilweise ausgeglichen durch 65 km
`cycleway=track`, das an Straßen gelöscht wurde (Weg 188144495), und 59 km gelöschter Radwege.
Die 38.570 Bearbeitungen verteilen sich auf 10.445 Changesets (größtes Changeset 1,4 %, Anteil
des aktivsten Mappers 0,10) und sind keine Spitze.

### prague/lau/2020

<!-- src: 4c08729c4154 -->

Ursache: **Umtaggung** (Gehwege in Parks und am Flussufer zu Radwegen umgetaggt), dazu einige
neue Radwege. A+B stieg von 200,3 auf 231,5 km (+31,1, Schwelle 25,0). 26,7 km je Seite kamen von
Wegen, die vorher keiner Stufe angehörten: 20,5 km `highway=footway` + `bicycle=yes` wurden zu
`highway=cycleway` + `foot=yes` (etwa Weg 26427950 mit dem Namen Letenské sady; Weg 25401468),
dazu 2,4 km anderer Gehwege und 1,1 km Feldwege, die ebenso umgetaggt wurden. `foot=yes` erlaubt
Fußgänger, daher stuft v4 diese Wege als Stufe B ein (`B_shared`); v3 hatte sie in A eingeordnet
(`A_cycleway`). 205 der 230 umgetaggten Wege wurden von Februar bis April 2019 bearbeitet, in 32
Changesets von 11 Kartierenden (Anteil des aktivsten Mappers 0,37). Weitere 11,4 km sind 64 Wege,
die im Stand von 2019 fehlen, alle `highway=cycleway` (etwa Weg 757691856, Weg 694511682); v4
stuft 7,0 km davon als B und 4,4 km als A ein. Verkürzte Wege (−2,8 km), aus A/B heraus
umgetaggte Wege (−3,1 km) und gelöschte Wege (−1,7 km) glichen einen Teil aus. Unter v4 ist der
Schritt ein Schritt in Stufe B (B 157,0 -> 184,9 km, A 43,4 -> 46,6 km). Die Aktivität des Jahres
war normal (6.861 Bearbeitungen, Anteil des aktivsten Mappers 0,27).

### prague/fua/2020

<!-- src: b402e42870ca -->

Ursache: **Umtaggung**, dieselbe Umtaggung von Gehwegen wie bei prague/lau/2020, dazu
**Kartieraktivität** in den Vororten. A+B stieg von 347,2 auf 387,3 km (+40,1, Schwelle 34,7),
31,1 km davon in der Stadt. Über die ganze FUA kamen 31,5 km je Seite von vorher nicht
eingestuften Wegen (251 Wege; 20,7 km sind `highway=footway` + `bicycle=yes` ->
`highway=cycleway` + `foot=yes`, was v4 als `B_shared` einstuft) und 19,7 km von 95 Wegen, die im
Stand von 2019 fehlen (17,4 km `highway=cycleway`, etwa Weg 672969814 „Cyklostezka
Vestec-Kunratice“, Weg 751574330). v4 lässt 1,6 km als MTB-Strecke getaggter Pfade weg, die 2019
zu Radwegen umgetaggt wurden, meist in Dolní Břežany (`X_mtb_trail`). Weitere 4,2 km wechselten
von A nach B, als 18 `highway=cycleway`-Wege ohne `foot`-Tag `foot=designated` erhielten, was A+B
unverändert lässt. Radwege, die von `foot=yes` zu `foot=designated` umgetaggt wurden (2,4 km),
bleiben unter v4 `B_shared`. Die Aktivität war normal (9.692 Bearbeitungen, Anteil des aktivsten
Mappers 0,22).

### strasbourg/lau/2023

<!-- src: 6546bf71c078 -->

Ursache: **Kampagne** (Fußwege). 3.216 gezählte Bearbeitungen im Jahr 2022 bei einem Grenzwert
von 3.086 (Median 1.543): 1.298 legen `highway=footway` an, 492 davon im Oktober 2022 (von den 485
Gehwegen, die in jenem Monat erstmals gezeichnet wurden, zeichnete eine einzelne Person 90 %;
insgesamt 31 Changesets), 307 legen `highway=cycleway` an, und 741 ändern Tags, angeführt von
`highway=path -> footway` (168). Über das Jahr beträgt der Anteil des aktivsten Mappers 0,19,
verteilt auf 617 Changesets. A+B bewegte sich normal, von 205,9 auf 212,0 km (+6,0 km;
Sprungschwelle 25 km).

### strasbourg/lau/2025

<!-- src: d9e8a52e4e8b -->

Ursache: **Kampagne** (ein Umtaggungsdurchgang über Rad- und gemeinsame Geh- und Radwege, dazu
die Kartierung von Bürgersteigen und Querungen). 3.615 gezählte Bearbeitungen im Jahr 2024 bei
einem Grenzwert von 3.086. Davon sind 1.282 Tag-Änderungen, 865 davon in den Monaten März und
April 2024, angeführt von ergänztem `segregated` (`yes` 202, `no` 178), ergänztem
`bicycle=designated` (162) und `highway=cycleway -> path` (109). Weitere 1.213 sind angelegte
`highway=footway` (von den 1.206 Gehwegen, die 2024 erstmals gezeichnet wurden, sind 560
Bürgersteige und 421 Querungen, 57 % von einer einzelnen Person). Der Durchgang verschiebt km in
beide Richtungen zwischen A und B. 8,8 km auf 77 bestehenden Wegen wechselten von A nach B, wo
Radwege zu gemeinsamen Geh- und Radwegen wurden (`A_cycle_only` -> `B_shared`; etwa Weg 20336855,
Piste Antonin Magne, `highway=cycleway` -> `path` + `bicycle=designated` + `foot=designated` +
`segregated=no`). 4,7 km auf 48 Wegen wechselten von B nach A, wo `segregated=yes` ergänzt wurde
(`B_shared` -> `A_segregated`; etwa Weg 43456568, Piste de Traenheim). Weitere 23,6 km Radwege
erhielten `segregated=yes` und bleiben in Stufe A (`A_cycle_only` -> `A_segregated`), und 8,1 km
Gehwege erhielten `bicycle=designated` und kamen in B (etwa Weg 105927052). A fiel von 165,6 auf
158,2 km, während B von 52,6 auf 67,8 km stieg. A+B stieg von 218,2 auf 226,0 km, ein normales
Jahr. Über das Jahr beträgt der Anteil des aktivsten Mappers 0,19, verteilt auf 750 Changesets.

### utrecht/fua/2020

<!-- src: aa341e16430f -->

Ursache: **Umtaggung** (Fahrradstraßen auf den üblichen Schlüssel umgestellt). `unrecognised_km`
fiel von 39,6 auf 4,2, weil das nicht übliche `cycleway=cyclestreet`, das der Klassifikator auf
beiden Straßenseiten als unbekannten Wert liest (36,22 km je Seite im Jahr 2019, auf 133 Wegen),
im Lauf des Jahres 2019 durch `cyclestreet=yes` ersetzt wurde (etwa Weg 141862135
Westkanaaldijk, Weg 7068064 Tuinbouwweg, Weg 107229247 Engweg, alle am 2. Dezember 2019
bearbeitet). 2020 tragen 109 dieser Wege `cyclestreet=yes` und sind als Stufe E eingestuft
(`E_cycle_street`, 17,79 km); 7 tragen noch `cycleway=cyclestreet` (0,82 km je Seite). Die 119
verbliebenen Wege wurden zuletzt in 28 Changesets von 9 Kartierenden bearbeitet, 61 davon im
Dezember 2019; das Jahr hatte 5.009 Bearbeitungen bei einem Anteil des aktivsten Mappers von 0,10.
Die Umtaggung verschiebt km in Stufe E (23,1 -> 47,3 km), die nicht zur Hauptkennzahl gehört. A+B
bewegte sich normal, von 1.224,8 auf 1.230,6 km (+0,5 %). Im selben Jahr gibt es eine zweite,
kleinere Umtaggung innerhalb von A+B: 18,4 km Radwege erhielten `foot=yes` (etwa Weg 145564855 und
Weg 61116865, Oude Spoorbaan), was v4 als `B_shared` einstuft; B stieg also von 68,5 auf 85,9 km,
und A fiel von 1.156,2 auf 1.144,7 km. Weitere 26,2 km Wege wurden im Lauf des Jahres 2019 neu mit
`bicycle=designated` getaggt, tragen aber ausdrückliche MTB-Tags (etwa Weg 384215298,
`mtb:scale=1`, 3,8 km). v4 schließt sie als `X_mtb_trail` aus (32,6 -> 56,1 km), sie zählen also
nicht.

### vienna/lau/2025

<!-- src: ad5fe7ddd0c3 -->

Ursache: **Umtaggung**. `legacy_km` von 23,1 auf 10,3, als `cycleway=opposite_lane` von 21,8 auf
9,4 km fiel (Weg 206839268 -> `oneway:bicycle=no`; Weg 8043778 -> `cycleway:left=opposite`). Die
Umtaggung betrifft nur Stufe D; A+B stieg von 596 auf 620 km.

### warsaw/fua/2019

<!-- src: 1ed5cc742b5d -->

Ursache: **Kartieraktivität** in den Vororten, einschließlich Wegen, die von
`highway=construction` umgetaggt wurden; keine Kampagne und kein Import. A+B stieg von 833,1 auf
980,8 kartierte km (+147,8, Schwelle 83,3). 418 neue `highway=cycleway`-Wege bringen 113,7 km
(12,3 km Radwege wurden gelöscht). 85 Wege wechselten von `highway=construction` zu `cycleway`
(+19,6 km, etwa Weg 496608963 mit 3,4 km in Warschau), und neue ausgewiesene Geh- und Radwege bringen
25,3 km. Warschau selbst gewann 48,7 km (der Schritt von `warsaw/lau`, 528,2 -> 576,9). Die übrigen
99 km verteilen sich auf die Vorortgemeinden: Otwock 13,9 km, Nadarzyn 13,2 km (Weg 589686898 mit
3,6 km), Józefów 11,0 km (Weg 655210340 mit 3,6 km), Pilawa 9,8 km und Pruszków 7,8 km. Die 17.074
Bearbeitungen des Jahres 2018 liegen unter dem Median (41.531). Der Anteil des aktivsten Mappers
beträgt 0,16, und das größte Changeset hält 0,9 % der Bearbeitungen.

### warsaw/fua/2020

<!-- src: b61cef7e4c8d -->

Ursache: **Kartieraktivität** in den Vororten; Aktivität normal. A+B stieg von 980,8 auf
1.173,2 km (+192,4, Schwelle 98,1):
- 594 neue `highway=cycleway`-Wege bringen 130,4 km (12,2 km gelöscht);
- 136 neue ausgewiesene Geh- und Radwege bringen 43,4 km;
- 91 neue Wege `cycleway` + `foot=designated` bringen 18,9 km;
- 44 Umtaggungen `construction` -> `cycleway` bringen 14,1 km (etwa Weg 495949799 mit 3,6 km in
  Warschau).

Acht weitere neue Radwege (0,9 km, in Warschau) sind als MTB-Strecke getaggt, daher schließt v4
sie aus (`X_mtb_trail`). Warschau gewann 46,7 km und die Vororte 145,7 km: Ożarów Mazowiecki 11,5,
Piaseczno 10,1, Pruszków 9,9, Nieporęt 9,0 (Weg 700813876 mit 4,6 km), Radzymin 8,3 (Weg 700814676 mit
4,6 km) und Jabłonna 6,6 (Weg 732168390 mit 6,1 km). 2019 gab es 16.828 Bearbeitungen (Median
41.531), bei einem Anteil des aktivsten Mappers von 0,07.

### warsaw/fua/2021

<!-- src: 8093e09f7865 -->

Ursache: **Kartieraktivität**; die Aktivität war erhöht, aber unter dem Spitzen-Grenzwert. A+B
stieg von 1.173,2 auf 1.421,8 km (+248,6, Schwelle 117,3):
- 1.302 neue `highway=cycleway`-Wege bringen 156,4 km, denen 134 gelöschte gegenüberstehen
  (−33,7 km, meist neu gezeichnet);
- neue ausgewiesene Geh- und Radwege bringen 98,3 km (432 Wege);
- 85 Umtaggungen `construction` -> `cycleway` bringen 22,4 km;
- 138 bestehende Straßenwege der Kategorie secondary erhielten straßenbegleitende Radwege
  (+9,6 km).

Warschau gewann 50,6 km und die Vororte 198,0 km: Błonie 20,2 (Weg 820164997, ein Geh- und
Radweg von 4,0 km), Halinów 13,8, Nieporęt 11,0 und Nadarzyn 10,4. Die 31.963 Bearbeitungen des
Jahres 2020 (Median 41.531) erreichen im November und Dezember ihren Höhepunkt (10.166). Die
meisten sind angelegte `highway=footway` (17.667). Der Anteil des aktivsten Mappers beträgt 0,14,
und das größte Changeset hält 0,7 %.

### wroclaw/lau/2018

<!-- src: cef7634ae339 -->

Ursache: **Kampagne** einer einzelnen Person (Fußwegenetz). 22.113 gezählte Bearbeitungen im Jahr
2017 bei einem Median von 8.419: 14.617 legen `highway=footway` an (etwa Weg 24964920), und 15.708
aller gezählten Bearbeitungen fallen in die Monate Juni bis August 2017, bei einem Anteil des
aktivsten Mappers von 0,89, verteilt auf 2.783 Changesets. 2018 ist der erste Datenpunkt, daher
lässt sich keine km-Veränderung zuordnen; A+B wuchs danach stetig (261,5 -> 272,7 km).

### wroclaw/fua/2018

<!-- src: e1de57dc775b -->

Ursache: **Kampagne** einer einzelnen Person (Fußwegenetz), dieselbe Kampagne wie bei
`wroclaw/lau/2018`. 23.299 gezählte Bearbeitungen im Jahr 2017 bei einem Median von 10.439
(Grenzwert 20.878): 15.165 ergänzen `highway=footway`, 16.119 fallen in die Monate Juni bis
August, und der Anteil des aktivsten Mappers beträgt 0,87, verteilt auf 3.147 Changesets
(größtes Changeset 0,5 % der Bearbeitungen). Die Reihe der Stadt zählt 22.113 davon. 2018 ist der
erste Datenpunkt, daher lässt sich keine km-Veränderung zuordnen; A+B wuchs im Lauf des Jahres
2018 von 332,0 auf 362,8 km.

### wroclaw/fua/2020

<!-- src: ddc6b9b23542 -->

Ursache: **Kartieraktivität** (neue Radwege in den nördlichen Gemeinden und in der Stadt). Der
`single_mapper`-Anteil trägt die km nicht. A+B stieg von 362,8 auf 413,7 km (+50,9, Schwelle
36,3): 158 neue `highway=cycleway`-Wege (+29,9 km), sechs Umtaggungen `highway=track` ->
`cycleway` (+9,6 km, etwa Weg 188218945 mit 4,9 km) und 138 neue `highway=path`-Wege mit
`bicycle=designated` (+11,0 km). Nach Wegmittelpunkt gewann Żmigród 21,4 km (Weg 691709709, ein
Betonradweg von 7,9 km; Weg 723787159 mit 2,2 km), Wrocław 15,6 km, Trzebnica 6,0 km und Oborniki
Śląskie 3,9 km. Die 6.409 Bearbeitungen des Jahres 2019 liegen unter dem Median (10.439). Eine
einzelne Person nahm 55 % davon vor, meist angelegte `highway=footway` und `highway=path` (1.251
und 1.088 Bearbeitungen). Die Wege, die diese Person 2019 bearbeitete, tragen 19,7 der 62,6 km
Brutto-Zuwachs in A+B (0,31).

### wroclaw/fua/2022

<!-- src: 7ffa22438f8a -->

Ursache: **Kartieraktivität**, bei normaler Aktivität (11.351 Bearbeitungen im Jahr 2021, Median
10.439; Anteil des aktivsten Mappers 0,37). A+B stieg von 439,4 auf 496,3 km (+56,9, Schwelle
43,9). 222 neue `highway=cycleway`-Wege bringen 37,1 km, denen 9,6 km gelöschte gegenüberstehen
(251 Wege, meist neu gezeichnet). 310 neue `highway=path`-Wege mit `bicycle=designated` bringen
19,4 km. Zwei Deichwege in Wrocław wechselten von `highway=service` zu `path` („Grobla
Szczytnicko-Bartoszowicka“, Weg 164857942 und Weg 616369204, zusammen 3,9 km). Die Hälfte des Zuwachses
liegt in der Stadt (+27,6 km, der Schritt von `wroclaw/lau`, 306,0 -> 333,6). Außerhalb gewann
Trzebnica 9,0 km (Weg 916262472, ein Radweg aus Betonplatten von 5,8 km; Weg 960207140 mit 3,1 km)
und Prusice 3,1 km (Weg 995926320).

### wroclaw/fua/2023

<!-- src: 3e3c1cffc66a -->

Ursache: **Kartieraktivität** (Wege in den Vorortgemeinden gezeichnet). Eine einzelne Person nahm
einen großen Teil der Bearbeitungen vor, trägt aber nur einen kleineren Teil der km. A+B stieg von
496,3 auf 554,5 km (+58,2, Schwelle 49,6):
- neue `highway=path`-Wege mit `bicycle=designated` bringen 47,0 km (693 Wege);
- neue Radwege bringen 17,3 km, denen 12,3 km gelöschte gegenüberstehen (Neuzeichnung);
- Umtaggungen von footway zu path bringen 8,6 km;
- Wege, die von `highway=construction` zu `cycleway`/`path` umgetaggt wurden, bringen 6,5 km
  (kartierte km; die Umtaggung markiert die Kartierung, keine geprüfte Eröffnung).

Nach Wegmittelpunkt gewann Długołęka 16,3 km (etwa Weg 1002612806, `track` -> `path`; Weg
1001464229, `construction` -> `cycleway`), Wrocław 14,8 km, Sobótka 5,3 km und Siechnice
5,0 km. Die 17.938 Bearbeitungen des Jahres 2022 liegen unter dem Spitzen-Grenzwert (20.878).
Eine einzelne Person nahm 53 % davon vor (`single_mapper`): 6.265 waren angelegte
`highway=footway`, und 5.720 fielen in die Monate April und Mai. Die Wege, die diese Person 2022
bearbeitete, tragen 22,9 der 95,0 km Brutto-Zuwachs in A+B (0,24).
