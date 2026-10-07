# M8 rulings

## Task 8: user review stop (2026-10-07)

The user reviewed `docs/review/m8-content-review.md` (commit 1e96c54) and the overlay_v3 sanity map,
and gave one verdict per item class:

- Profiles (9 organisations): approved, with one fix: the Abgeordnetenhaus profile gives the German
  title "Acht Jahre Mobilitätsgesetz – …" instead of a translated title in quotation marks.
- Plans (21 plans, 118 Berlin rows, the Berlin plan page): approved, with fixes:
  - the Berlin plan page's quotes are placed after the paragraph they belong to (the `after`
    indices were counted with the intro);
  - Copenhagen 37 and Strasbourg 52 are marked suspect, because their sources count funded or
    under-construction work, or a forecast, as implemented; the page flags them;
  - the unstored Radverkehrsnetz + Hauptverkehrsstraßen rows (1733 C 22.7 / 69.9, 1733 E 20.1 /
    156.9) are listed in the research log's "Not stored" list;
  - each downloaded plan document records "licence: not stated" instead of the general § 5 UrhG
    sentence;
  - Drs 19/27049 Ergänzungsnetz 2023 55.1 stays suspect; the five expired plans without a
    successor show "no successor found" (Task 9).
- Overlay: overlay_v3 ships as the latest method, with the caveat that the series measures what is
  mapped, depends on how OSM draws ways, and moves when ways are redrawn. Before shipping, the
  v3-only pieces are checked on a zoomed map for crossing-street false positives.
- Counters: the index rule of spec §2.13 stays as recorded. Helsinki 2025 stays 84.2; the Counts
  tab notes the two sites whose counts step down during works (Kaivokatu from April 2024,
  Pitkäsilta west from May 2025) and the index without them (99.9) (Task 10). The other counter
  rulings are approved: Oslo completeness from byHour, a zero-total day is an outage, the Paris
  in-service rule, and Madrid without an index line.

The other judgement calls listed in the review document stand as written there.

## Rulings made by the controller (Tasks 1–7)

The SDD ledger's rulings, in order, are listed in the review document's "Judgement calls" section
(19 items). They stand as approved above.
