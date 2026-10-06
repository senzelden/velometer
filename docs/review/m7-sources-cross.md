# M7 source research: cross-city (definitions and methods)

Registry file: `content/sources/cross.yaml` (15 sources, 48 excerpts). Accessed 2026-10-06.

## How the excerpts were checked

Each document was downloaded (curl) and turned into text (`pdftotext`, or HTML with the tags stripped). Every excerpt was then checked by script as a whitespace-normalised substring of that text, so 45 of 48 matched exactly. The three Zenodo excerpts could not be checked this way. curl got HTTP 403 from zenodo.org, so they were read through WebFetch twice, once from the rendered record and once from the raw `metadata.description` of `/api/records/22271229`. Both readings gave identical wording. Nothing was quoted from a search snippet or from memory. Wayback snapshots were looked up only through `archive.org/wayback/available`; nothing was saved to the archive.

## Clean Cities Campaign, City Ranking 2025 ("Streets for Kids, Cities for All")

- **Found:** the report PDF (`cc2025-report`, 8 excerpts), the annexes PDF (`cc2025-annexes`, 8), and the protected-cycling table page (`cc2025-cycling-table`, 3; datePublished 2025-05-14, modified 2025-07-17). The report PDF is laid out as 2-up spreads, so locators give both the PDF page and the printed page.
- **What counts:** physically segregated infrastructure (barrier, height difference or distance). Shared foot/bike paths, pedestrian streets and greenways count. Painted lanes, cycle streets, living streets, shared spaces and bus lanes do not (Annex p.4).
- **Who measured:** the cities themselves (34 of 36 supplied at least partial data). Where data was missing, public sources, ECF and OSM were used, and the OSM fallback followed ECF's tracker tag list (Annex p.4). **The report does not say which source was used for any given city.** The data PDF (`CCC-city-ranking-2025-data.pdf`) is image-only, with no extractable text, and was not used.
- **Date:** data collected December 2024 to 7 February 2025; updates accepted until 4 April 2025 (report p.20).
- **Area:** the municipality of the same name, unless stated otherwise (report p.19).
- **How length is measured:** for the *road network*, lanes and directions do not change the length, so a centreline basis (Annex p.3). **No rule is given for the cycling numerator** (one km per side or per centreline). City-submitted figures can use either basis.
- **Inconsistency worth noting:** the web table describes protected infrastructure as "dedicated bike lanes that are physically separated", but the annex also counts shared foot/bike paths, pedestrian streets and greenways. The report itself says Helsinki's 48% "includes a large proportion of shared foot and bike paths".
- **Definition sensitivity:** the July 2025 update moved Vienna from 384.1 km to 625.1 km, after "traffic-calmed areas" with restricted motor access were added.
- Wayback snapshots exist for all three URLs and are recorded.

## ECF QECIO 2.1 (methodology v2.10)

- **Found:** `qecio-methodology` (10 excerpts) and `qecio-metadata` (2), both on ECF's own tracker site, `european-cyclists-federation.github.io` (author contacts are @ecf.com addresses; the ecf.com QECIO page links to this site). The downloaded Methodology.pdf has the same SHA-256 as the repo copy `docs/research/ecf-qecio-2.1-methodology.pdf` (11f69d40…).
- **Not reached:** `https://ecf.com/quantifying-europe-cycling-infrastructure-using-openstreetmap-qecio-2` returned a Cloudflare 403 page to curl and an empty page to WebFetch. No Wayback snapshot exists for Methodology.pdf; one exists for Metadata.pdf (2023-12-12, which predates v2.10).
- **What counts:** Table 2 (p.15) defines cycle tracks (physically separated), cycle lanes (paint only) and cycle and pedestrian tracks (signed shared). The "segregated" ratio adds painted cycle lanes to tracks and shared paths (p.5), so ECF's "segregated" is **not** Clean Cities' "protected".
- **How length is measured:** side-tagged ways become two features, and one-way infrastructure is counted at half length (p.5). A ratio of 100 means "bidirectional" infrastructure on all main roads.
- **Area:** NUTS 3 regions, with highways clipped to NUTS-3 boundaries (pp.2, 4).
- **Date:** PBF files downloaded 10–11 January 2024 from Geofabrik (Metadata p.1). There has been no release since.
- **Kind of km:** mapped km only. The Disclaimer (p.8) says the data "only represents OSM contributions".

## BikeNetKit (Zenodo 22271229)

- **Found:** the Zenodo record (`bikenetkit-zenodo`, 3 excerpts; published 2026-09-03; Szell, Pessoa), read via WebFetch as described above. The Zenodo description sends readers to GitHub "for details", so the method was taken from the code at pinned commits: `bikenetkit-export-notebook` (dataexport e2a5bcf: country PBFs, cropped to city boundaries of cities above 100k population) and `bikenetkit-pbi-filter` (growbikenet 8820875: `PBI_CUSTOM_FILTER`, "protected bicycle infrastructure").
- **What counts:** the bike network filter includes `highway=living_street` and footway/path/pedestrian ways with `bicycle=yes|permissive|designated`. That is broader than the Clean Cities "protected" definition and includes living streets, which Clean Cities excludes.
- **How length is measured:** the notebook builds the graph with `force_bidirectional=True` and simplifies it. No km basis is stated in prose. **No quotable definition of length**.
- **Date:** only "over the summer of 2026". The PBF snapshot date is not stated.
- **Not reached:** zenodo.org gave HTTP 403 to curl (rate limit). No Wayback snapshot exists for the record or the GitHub files.

## EU Urban Mobility Indicators, C(2026) 4676

- **Found:** the act PDF (`eu-c2026-4676-act`, 2 excerpts), the Annex PDF (`eu-c2026-4676-annex`, 2) and the DG MOVE news item (`eu-umi-news`, 1; Wayback snapshot recorded). No Wayback snapshot exists for the two PDFs.
- **Cycling:** the only indicator that mentions cycling is SU.1, trips per day by mode, collected by survey, mobile phone data, model or big data (Annex p.2). **There is no cycling-infrastructure-length indicator.** First data is due 31 December 2027 (Article 5(1)), and SU.1 may be reported every fifth year (Article 5(3), not excerpted).
- **Area:** each urban node is a set of LAUs (Article 6(1), pp.5–6).

## OSM wiki (definitions of the tags behind mapped km)

- **Found:** Key:cycleway (2 excerpts), Tag:cycleway=lane (2), Tag:cycleway=track (1) and Tag:highway=cycleway (1). These were fetched with `action=render`, and the URLs recorded are the canonical `/wiki/` pages. Wayback snapshots exist for the three Tag pages but not for Key:cycleway.
- **Why they are useful:** they explain the per-side issue in mapped km. A lane or track on the road is an attribute of the road way, and plain `cycleway=lane` can mean lanes on both sides, while `highway=cycleway` is a separate way. The wiki is community documentation and is edited continuously.

## Coverage of the six dimensions

| dimension | quotable definition |
|---|---|
| what is counted | yes: CC annex, QECIO Table 2, BikeNetKit filter, OSM wiki |
| kind of km (built/planned/mapped) | yes for QECIO (mapped, Disclaimer). CC: city figures vs OSM fallback, but per city unknown |
| how length is measured | QECIO yes (half-length for one-way, two features per side). CC only for the road network (centreline). BikeNetKit no. OSM wiki on sides |
| date | CC yes (Dec 2024 to 7 Feb 2025; cutoff 4 Apr 2025). QECIO yes (PBF 10–11 Jan 2024). BikeNetKit only "summer of 2026". EU deadline 2027 |
| area | CC yes (municipality). QECIO yes (NUTS 3). EU yes (LAU sets). BikeNetKit only "city boundary", from code |
| who measured | CC yes (cities, with public/ECF/OSM fallback). QECIO yes (ECF from OSM). BikeNetKit yes (ITU from OSM) |

## Notes for narrative authors

- The `kind` values for QECIO and BikeNetKit (`index`) and for the OSM wiki (`ngo`) are a judgement call, because the schema has no "dataset" or "community documentation" kind.
- The `published` date is left empty for the CC report and annex PDFs because neither shows a date. The launch date, 2025-05-14, is on the table page.
