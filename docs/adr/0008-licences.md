# 0008 — Licences

- Status: accepted
- Date: 2026-10-01

## Decision

- **Code:** MIT (`LICENSE`).
- **Derived data:** ODbL 1.0, with the attribution "© OpenStreetMap contributors". This covers our tier lengths, metrics, exports and the app's CSV. BikeNetKit (Zenodo 22271229) is also ODbL, so its obligations are the same.
- **External comparison numbers** are stored with source URL and retrieval date. Examples: Clean Cities, Copenhagenize, QECIO (no licence stated) and official city figures. They are cited, not redistributed beyond what citation allows.
- **Test fixtures** containing real OSM data (the Berlin golden set) are ODbL. Each carries an attribution note.
- **M7 narratives and quotations:** narratives quote external sources only, as short excerpts (at most 60 words) with attribution, publisher, title, date and link. Full texts are never stored. Excerpts and their English glosses live in `content/sources/*.yaml`; project documents are cited as data, not quoted.
- **M8 open data (counters, the Berlin plan network):** each downloaded dataset records its URL, licence and retrieval time beside the raw file under `data/` (git-ignored, never committed), and every page that shows it carries an attribution line. Licences in use: **dl-de-zero-2.0** (Berlin counter file; the Senate's WFS layers `radverkehrsnetz` and `radverkehrsmassnahmen`, read for the plan overlay and the infraVelo completed projects), **ODbL** (Paris counters, with the same share-alike obligations as our derived data), **CC BY 4.0** (Vienna, Helsinki, Madrid and Barcelona counters; attribution to the publisher on each Counts tab) and **NLOD** (Norwegian Licence for Open Government Data: Oslo's state counters from Statens vegvesen; attribution required). The **Licence Ouverte** (Etalab) of the French portals checked for Lyon, Bordeaux and Strasbourg is not used: none of their counter series was loaded. The stored index values and daily totals are derived from these datasets and keep their attribution. Plan documents (Verordnungen, Drucksachen, Hauptausschuss reports, other cities' plans) state no licence; they are stored as printed figures with a citation, never redistributed as files.
