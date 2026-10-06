# M7 external sources, west region: research log

Region file: `content/sources/west.yaml` (30 sources, 64 excerpts). Accessed 2026-10-06.

## Method

- Searched with WebSearch. Every quoted page was then fetched in full with a plain HTTP GET, and the text was extracted locally (an HTML-to-text pass, or `pdftotext` for PDFs). Excerpts were copied from that text. No excerpt comes from a search snippet or from memory.
- Every excerpt was checked by machine against the fetched text after whitespace was normalised. Checks that needed care:
  - Paris press kit p. 8 sidebar: the text layer overlaps a graphic. The two sentences were confirmed with `pdftotext -raw`, which keeps the reading order.
  - Lyon Plan vélo p. 10: the facility breakdown is a chart. The excerpt joins the chart's labels in text-layer order, and the locator says so.
  - Bordeaux Plan vélo p. 8: bullet characters were removed from the list.
- Dataset descriptions on Paris Data and data.strasbourg.eu render client-side. Their text was read from the portals' catalogue API (Opendatasoft v2.1), and the source `url` is the human-readable dataset page. The Madrid (CKAN) and Barcelona (CKAN) dataset pages serve the same text in their HTML, and that HTML was checked.
- WebFetch was used once, on a madrid.es news page that blocks plain GETs. Nothing from it is quoted, because WebFetch returns text processed by a model, not the raw page.
- Archive snapshots were looked up only through `https://archive.org/wayback/available?url=…`. No save requests were made. Sources with no `archive_url` had no snapshot.

## Paris

Searched for: Plan Vélo 2015–2020 and 2021–2026, coronapistes, official network length and its definition, the Paris Data datasets, and progress tracking.

Found and used:
- `paris-plan-velo-2021-2026`: Ville de Paris press kit (PDF). Gives 1,094 km recorded in 2021 and says what it counts (tracks, reserved lanes, contraflow). The same page gives 1,404 km for 2020 from the Agence de la Mobilité observatory, so two official figures differ on one page. Also has the targets: 180 km of tracks, 52 km of coronapistes made permanent, and 390 km of contraflow.
- `paris-opendata-lineaire-km`: the official yearly series (935 km in 2015 to 1,607 km in January 2026). The definition takes in bus lanes, pedestrian streets and contraflow. **The data are an extract of OSM.**
- `paris-opendata-amenagements` and `paris-notice-amenagements`: the dataset definition and its notice (June 2023). The cycling unit validates OSM edits with LeBonTag. Facilities on both sides of a road are "superposés", and motor-free paths are left out of the review figure.
- `paris-lessentiel-1565km`: press report of the 1 January 2025 figure (1,565 km).
- `paris-parisenselle-observatoire`: the NGO tracker. It found that the 2015–2020 plan reached 55 % of the length promised.

Not used:
- `cdn.paris.fr/paris/2021/12/08/2fc9cb8ad6db58b6bfde3e6ccfc4c48c.pdf`: reached, but it is a 13th-arrondissement plan bundled with vendor material, so it is off-topic.
- The 2026 figure (1,607 km) appears only as a data row, not as quotable prose, so it is not quoted.

## Lyon

Searched for: the Métropole Plan vélo, Voies Lyonnaises targets and progress, the total network length, and NGO and press reviews.

Found and used:
- `lyon-plan-velo-2024`: Métropole de Lyon Plan vélo (Aug 2024, PDF). Gives 1,013 km at the end of 2020 and 1,208 km in 2023, broken down by type (accotement revêtu, bande, piste, couloir bus/vélo, double sens, voie verte). The target is 2,000 km, and the Voies Lyonnaises target is 355 km by 2030.
- `lyon-grandlyon-circuler-a-velo`: the current service page. It says "près de 1250 km d'aménagements cyclables" and also "plus de 1 100 km de pistes cyclables". The two wordings on one page do not agree.
- `lyon-lavilleavelo-bilan-vl`: the NGO's end-of-term review. Of the 250 km promised, 170 km will be delivered, including 60 km that already existed, and about 110 km are new.
- `lyon-lyoncapitale-vl-2025`: press. The term target was cut from 250 to 200 and then to 180 km.

Not used: Cyclopolis (cyclopolis.fr) was not fetched. It is an NGO dashboard, and La Ville à Vélo already cites it.

## Strasbourg

Searched for: the Plan vélo 2021–2026, Vélostras, the official network length, the open-data basis, and press.

Found and used:
- `strasbourg-premiere-agglomeration` and `strasbourg-a-velo`: official, "600 km" / "plus de 600 km d'itinéraires cyclables".
- `strasbourg-plan-velo-2024`: official progress note (30 Oct 2024). About 100 operations covering about 100 km by 2026, with 52 done by the end of 2024.
- `strasbourg-velostras`: the Vélostras express network will total more than 130 km.
- `strasbourg-opendata-bnac`: official cycle data come from the Eurométropole's own road centreline network in the national BNAC schema. Unlike Paris, they are not derived from OSM.
- `strasbourg-rue89-plan-velo-2021`: press on the 2021 plan vote (120 km, about 50 junctions).
- `strasbourg-cityra-mi-chemin`: press. It says "750 kilomètres de pistes déjà existants", which does not match the official 600 km. Cityra gives no source.

## Bordeaux

Searched for: the 3rd Plan vélo 2021–2026, ReVE, the city and metropolitan network lengths, and the regional audit chamber.

Found and used:
- `bordeaux-plan-velo-2021-2026`: Bordeaux Métropole plan (PDF). Gives 1,506 km in June 2021, of which 624 km are traffic-calmed streets and 167 km are pedestrian streets. This is a key reason the official figure exceeds mapped km.
- `bordeaux-crc-plan-velo-2025`: Chambre régionale des comptes, final report (deliberated 5 Aug 2025). Gives 1,700 km at the end of 2024, "tous types confondus (bandes, pistes, zones apaisées, couloirs bus&vélo)". ReVE stood at 36 of 270 km.
- `bordeaux-metropole-reve`: ReVE is 14 routes and 272 km. The page also says "plus de 1000 kms d'aménagements cyclables", which does not match the CRC's 1,700 km and points to a different basis.
- `bordeaux-ville-circuler-a-velo`: the Ville de Bordeaux page. 378 km including bus lanes.

Not reached or not used:
- `https://www.bordeaux.fr/velo-et-marche-des-modes-de-deplacement-doux-dans-une-ville-apaisee`: HTTP 403.
- The CRC report as hosted by ccomptes.fr was not found. `ccomptes.fr/…/NAR2025-062.pdf` is a different report, so the copy republished by the Ville de Mérignac is quoted instead, and the title says so.
- Rue89 Bordeaux on the CRC report: reached, but no quotable figures in the accessible text.

## Madrid

Searched for: Ayuntamiento figures and definitions, the Plan Director de Movilidad Ciclista (2008, revised 2018), ciclocarriles, NGO critiques, and press.

Found and used:
- `madrid-opendata-infraestructura-ciclista`: Ayuntamiento open data. Gives the typology and definitions. The figures cover exclusive, preferential and shared-use ways. A "senda ciclable" runs through parks, and a "ciclocarril" is shared with motor traffic at 30 km/h.
- `madrid-ultimahora-1167km`: press, citing the city's Área de Urbanismo, Medio Ambiente y Movilidad. Gives 1,167 km: 764.7 km of "carril bici segregado" and 402.4 km of ciclocarriles, against 1,047.7 / 699 / 347 km in 2019.
- `madrid-enbici-300km-segregadas` (2020) and `madrid-enbici-red-continua-247km` (2022): NGO. Gives 347 km segregated plus 345 km of ciclocarriles from the official maps. It explains that much reporting counted only the "carril-bici" category, and that 247 km of the 360 km form a connected network.
- `madrid-eldiario-carriles-2019`: press on the ciclocarril model.

Not reached or not used:
- madrid.es returns HTTP 403 (Akamai) to plain GETs. Affected: the Plan Director 2008 revision PDF (`…/PDMC2008_Revision_y_actualizacion_1.pdf`), the plan's landing page, and the 2007 news item on the 274 km network. The official press release behind the 1,167 km figure was not found, so a secondary source is quoted and the title says so.
- madridpress.com: HTTP 403.
- madridactual.es: reached, but it covers the regional (Comunidad de Madrid) network, not the city.

## Barcelona

Searched for: the Ajuntament's bike-lane network length, open-data definitions, the mandate plans, and press.

Found and used:
- `barcelona-premsa-42km-2025`: Ajuntament press release (11 Feb 2025). "Actualment, la xarxa de carrils bici de Barcelona és de 268 km."
- `barcelona-opendata-vies-ciclables`: open data. "Vies ciclables" are 30/20/10 streets or bike paths outside zones 30, a category separate from "carril bici".
- `barcelona-naciodigital-frena`: press (May 2026). Gives 271.1 km of bike lanes, plus 801 km of 30 streets and 147 km of reversed priority (2024), with km per mayor.
- `barcelona-ara-32km-2021`: press. About 1,150 km of "itineraris ciclistes" once 30/20/10 streets are counted, against about 270 km of bike lanes.

Not reached:
- `https://ce.atm.cat/ca/web/observatori/w/quilometres-xarxa-ciclable-ciutat-barcelona` (ATM mobility observatory, km by type): TLS certificate verification failed, and the page was not fetched without verification. Not quoted.
- barcelona.cat/mobilitat news (11 Feb 2025): reached. It repeats the 268 km, so the Servei de Premsa release is used instead.
