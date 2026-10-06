# M7 external sources: north (research log)

Region file: `content/sources/north.yaml`. Cities: copenhagen, stockholm, oslo, helsinki,
amsterdam, utrecht. All pages and PDFs were fetched on 2026-10-06. Each excerpt was copied
from the fetched page text (PDFs through `pdftotext`) and then machine-checked against that
text. There are two intentional exceptions:

- `oslo-ey-evaluering-2024/built-107-upgraded-48`: in the PDF text layer, chart axis labels
  sit between the words of this sentence. The sentence was confirmed in layout mode, and the
  axis labels were left out.
- `amsterdam-meerjarenplan-fiets-2017/width-target`: footnote markers "2" and "3" were left
  out, and the locator says so. Soft hyphens were removed from PDF text throughout.

Wayback snapshots were looked up only through `archive.org/wayback/available`. Nothing was
submitted for archiving. Sources with no snapshot have no `archive_url`.

Totals: 23 sources, 53 excerpts.

## copenhagen (4 sources, 11 excerpts)

Found:
- **Mobilitetsredegørelse 2026** (Københavns Kommune, PDF). p. 15 has "I 2025 var der 401 km
  cykelsti i København". This **confirms the verbatim quote in `config/external/figures.csv`**
  (`copenhagen,official,cycle_track_km,401`, `source_url` re-fetched 2026-10-06). The quote is
  migrated as `copenhagen-mobilitetsredegorelse-2026/cykelsti-2025`.
  - Tabel 5 on p. 15 reports *Cykelstier i alt* (388→401 km, 2021–2025) and *Cykelbaner i alt*
    (33 km every year) as separate rows. The official 401 km therefore excludes painted
    cycle lanes.
  - p. 29 covers the strategy documents. p. 33 gives the status of the
    Cykelstiprioriteringsplan: 37 of 151 initiatives fully implemented.
- **Verdens bedste cykelby** (byudvikling.kk.dk) gives the basis for the switch in reports:
  "Fra 2021 og frem bliver Cykelredegørelserne afløst af Mobilitetsredegørelsen". The
  biennial *cykelregnskab* continues. The page says the cykelregnskab has appeared since 1995.
- **The Bicycle Account 2022** (English PDF, p. 7, spread pp. 12–13): 388 km cycle tracks and
  33 km cycle lanes. These are the same categories as Tabel 5.
- **Cykelfokus 2024** (Copenhagen design guidelines, council agenda annex) defines both terms:
  - *cykelsti*: kerb-separated from the carriageway and the pavement
  - *cykelbane*: a marked area level with the carriageway
  This fills the gap in the figures.csv note ("municipal definition of cykelsti not read").
  The guideline does not itself say that the 401 km count uses this definition, but the
  table keeps the two categories apart.

Not reached:
- The Bicycle Account 2022 at `kk.sites.itera.dk/apps/kk_pub2/pdf/2420_d4db2492337f.pdf`. The
  server returned an SQL error page. The same document was reached at
  urbandevelopmentcph.kk.dk instead.
- English *Mobility Report 2026* (`byudvikling.kk.dk/.../Mobility%20Report%202026.pdf`). It
  was fetched and matches the Danish text ("In 2025, there were 401 km of cycle paths"). It
  was not added, to avoid a duplicate. Note that it translates *cykelsti* as "cycle paths".
- No snapshot exists for the Bicycle Account 2022 URL.

## stockholm (3 sources, 8 excerpts)

Found:
- **cykla.stockholm/cykelvagar**: "ungefär 117 mil cykelvägar". 1 Swedish mil = 10 km, so
  about 1,170 km. The definition is stated: separate cycle tracks, combined walking and
  cycling paths, and painted cycle lanes (cykelfält). Primary routes are about 36 mil. The
  local network includes 30 km/h mixed-traffic streets.
- **Cykelplan för Stockholms stad (Cykelstaden, 2022)**: the same 117 mil with the same three
  categories. Also about 10 km of new or widened cycle tracks per year, and SEK 1 bn spent
  2012–2018. The copy comes from insynsverige.se, a mirror of municipal documents, and the
  title says so. An original on stockholm.se was not found.
- **KS utlåtande Dnr KS 2022/535** (council decision paper, 18 May 2022): the 2040 outlook and
  the goal that "var fjärde resa" (every fourth trip) is made by bike by 2040.

Searched, not used:
- The regional cycling plan (Region Stockholm), as it is out of city scope.
- The Cykelfrämjandet consultation response, because better primaries were available.
- Quality press (DN/SvD), which is paywalled and was not fetched.

Gap: there is no official breakdown of the 117 mil into its three categories, and no recent
(2024–2026) progress report was found.

## oslo (4 sources, 10 excerpts)

Found:
- **oslo.kommune.no Sykkelkart** (map updated summer 2024):
  - network "mer enn 290 km"
  - target 530 km
  - the map's provision covers gang- og sykkelveier, sykkelfelt and sykkelveier, which is the
    definition basis
- **Oslo kommune press release, 11 Nov 2024**: 155 km built and upgraded since 2015. It also
  reports EY's finding that chasing kilometres came at the expense of other parts of the
  strategy, and that the 25% share goal was missed.
- **EY final evaluation of the Sykkelstrategi 2015–2025** (2024, commissioned by Oslo
  kommune):
  - p. 23: the network is mainly marked cycle lanes, not physically separated infrastructure
  - p. 35: about 107 km built and about 48 km upgraded
  - p. 46: junctions "teller lite i strekningsbaserte måling" (count for little in
    length-based measurement)

  The `kind` is `official`, but the publisher is a consultant, and the title and publisher
  fields say so.
- **Oslo kommune Byplan magazine (2019)**: the 2018 council plan of more than 10 km a year. A
  city planner says cycle lanes are the most common solution.

Not reached / not used:
- Aftenposten and Nettavisen articles (paywall or not fetched).
- The *Plan for sykkelveinettet* PDF itself, as it was not needed.

## helsinki (4 sources, 10 excerpts)

Found:
- **Pyöräväylien priorisointi- ja toteuttamisohjelma (2021:21)**:
  - "yli 1200 kilometriä erillisiä pyöräväyliä" (separate cycleways), with cycling on the
    carriageway elsewhere
  - mostly two-way, with fewer than 40 km of one-way cycleways (2020)
  - baana quality target: 9.5 km by 2021
- **Urban Environment Committee, 25 Oct 2022 (HEL 2022-010017)**, monitoring of the
  programme 2020–2025:
  - inner-city target network about 140 km, of which 44.7 km built
  - baana target network about 140 km, of which 16.9 km built to the design guideline
  - the "built cycleway km" indicator
  - 2021 mode share of 9%
- **Pyöräilykatsaus 2021**: about 8 km of baana by the end of 2020, network planned at 130 km.
  This figure differs from the later about 140 km target.
- **Yle, 25 Aug 2026**:
  - about 33 km of baana
  - about 71 km of the inner-city target network
  - €218 m since 2013, with mode share flat at about 10%

Gaps:
- No 2024–2026 official monitoring report was reached. The Yle figures are the latest and come
  from the press.
- The paatokset.hel.fi case page has no Wayback snapshot.

## amsterdam (4 sources, 9 excerpts)

Found:
- **maps.amsterdam.nl/fietsnetten** (Gemeente Amsterdam) gives the clearest definitions in
  the region:
  - *fietspaden* (mandatory, non-mandatory, cycle/moped) are physically separated from the
    carriageway
  - *fietsstroken* are part of the carriageway
  - *fietssuggestiestroken* (advisory lanes) are not official lanes and are counted under
    "Fiets op de rijbaan"

  The map computes km interactively. **No total km figure appears in the page text**, so no
  official Amsterdam network length is quoted. Contact names on the page were not copied.
- **Meerjarenplan Fiets 2017–2022** (p. 13): 2.5 m standard, with the target that by 2025 half
  of the Plusnet Fiets inside the A10 is at least 2.50 m wide (34% in early 2017).
- **Rekenkamer Metropool Amsterdam, Amsterdam Fietsstad (13 Nov 2019)**: €200–800 m needed to
  bring the whole Plusnet Fiets to width. Cycle path width was the lowest-rated item in the
  2017 survey (5.9).
- **Uitvoeringsplan 2024** (Verkeersveiligheid, 30 km/u, Voetganger en Fiets): busy, often
  narrow paths, and the 2016/2017 multi-year plans are expiring.

Searched, not used:
- A Gemeente Amsterdam tweet asking how many km are on the hoofdnet. It is on X, not
  fetchable, and gave no answer text.
- A Fietsersbond 2013 article on 60 km of 30-zone paths. It is older than the 2018–2026
  window.
- Wikipedia and versus.com figures, which are not acceptable sources.

Gap: there is no official total km of fietspad for Amsterdam. Recommend citing the maps.amsterdam
dataset as data rather than quoting a length.

## utrecht (4 sources, 5 excerpts)

Found:
- **Actieplan Utrecht fietst! 2015–2020** (p. 15): the city grits about 400 km of
  *hoofdfietspaden* and important bridges. This is a maintenance network, not a total.
- **Raadsvoorstel Mobiliteitsplan 2040** (2021): the Fietsnetwerk map on p. 71 of the plan,
  and the principle of 30 km/h on all roads unless otherwise decided, with 50 km/h on
  connector roads.
- **Oud-Utrecht** (historical society, reprint of a 2015 article): "In 2012 telde Utrecht
  hierdoor 245 kilometer fietspad en 90 kilometer fietsstrook". This splits fietspad from
  fietsstrook, but it is a secondary source and dated 2012. Kind is `ngo`.
- **RTV Utrecht, 3 Jun 2025**, reporting a Fietsersbond/Bouwend Nederland study: 242 km of
  cycle paths in the province are too narrow, and the municipality of Utrecht has the most.

Not reached:
- **Utrecht open data, Indicatoren Fiets** (`open.utrecht.nl/dataset/indicatoren-fiets-mobiliteit/...`)
  returned a 404.
- data.utrecht.nl was not tried after the 404.
- Staat van Utrecht (provincial) has only total road km (gemeente Utrecht 1,185 km of road,
  2024) and no cycle path km, so it was not used.
- The Mobiliteitsplan 2040 itself was found only as a third-party copy (bollunetten.nl) and
  was not used.

Gap: there is no current official Utrecht figure for cycle path km.

## Concerns for the controller

- The Copenhagen 401 km is *cykelsti* only. The official table lists 33 km of *cykelbaner*
  separately (unchanged 2021–2025). Any comparison with mapped km should say which category is
  meant.
- Stockholm (about 1,170 km) and Helsinki (more than 1,200 km) **include shared walking and
  cycling paths**. Oslo's 290 km includes gang- og sykkelveier and painted lanes. These are not
  like-for-like with Copenhagen's kerbed-track figure.
- Amsterdam and Utrecht have no current official total km in the sources reached.
- The Stockholm Cykelplan PDF is a mirror copy (insynsverige.se), not a city domain.
- The Oslo EY report is consultant-authored. It is tagged `official` because the city
  commissioned it, which may need a ruling.
