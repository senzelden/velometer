# M12 rulings

German edition (spec `docs/superpowers/specs/2026-10-12-velometer-m12-design.md`, plan
`docs/superpowers/plans/2026-10-12-velometer-m12.md`). The pre-flight review and the SDD ledger are
in `.superpowers/sdd/2026-10-12-velometer-m12/`. This file records the user's rulings and the
German review (Task 10). Each ruling reads: Ruling — why — cost.

## User rulings

- Ruling: data-reference captions stay English. Every data-ref label (`data_refs.<id>`, e.g.
  "velometer reconciliation, vienna/cc_km") shows the English label on German pages, inside
  `lang="en"`. This reverses pre-flight ruling 3.1 (data-ref labels translated) and restores spec
  §4.4 (data references come only from the English file, so they can never disagree). It is
  structural: `translate.walk` yields no data-ref path, so `merge`, `stamp`, the completeness
  check and `tools/review_rows.py` never see one; the translation models reject a `data_refs`
  key (the content check reports the file), so a stale German copy cannot linger; the 121 German
  labels were removed from the 24 translation files and the files re-stamped — the labels are
  identifiers of our own data, and one English form avoids two captions per reference — cost:
  German readers see 101 short English captions, marked `lang="en"`.
- Ruling: the English label on a German page sits in `<span lang="en">` without `data-fallback`
  — it is the design, not a missing translation, so the "no fallback on German pages" test keeps
  meaning "nothing is missing" — cost: none. The leak test gains a `data_refs` phrase source, so
  an English label outside `lang="en"` on a German page fails it.
- Ruling: the user accepted all other German rows as drafted.

## Review notes

One line per reviewed row: row id — mark / note — how handled.

- `content/de/explainer.yaml#sections.5.paragraphs.1` — fine — unchanged.
- `content/de/explainer.yaml#sections.0.paragraphs.1` — fine — unchanged.
- `content/de/explainer.yaml#intro.1` — fine — unchanged.
- `content/de/explainer.yaml#sections.2.paragraphs.0` — fine — unchanged.
- `content/de/explainer.yaml#sections.2.paragraphs.1` — fine — unchanged.
- `content/de/explainer.yaml#sections.1.paragraphs.0` — fine — unchanged.
- `content/de/explainer.yaml#sections.3.paragraphs.1` — fine — unchanged.
- `content/de/counters.yaml#sections.0.paragraphs.0` — change: "Not sure what a county represents
  in Finland. My first intuition would be 'regionalen Straßen'" — the sentence is about Oslo
  (Norway; fylkesvei = county road). "an Staats- und Provinzstraßen" became "an staatlichen und
  regionalen Straßen"; re-stamped. For consistency the Trafikkdata `gloss_de` in
  `content/sources/counters.yaml` now reads "dem regionalen Straßennetz der Fylker" (was "dem der
  Fylker (Provinzen)"), and `docs/glossary.de.md` gains "county road (fylkesvei) → regionale
  Straße". "Provinz" is kept where it means a province, län or NUTS region (Stockholm, Utrecht,
  Barcelona, the limitations).

No English text changed.
