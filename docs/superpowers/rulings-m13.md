# M13 rulings

M13 is a batch of open follow-ups. It covers everything except hosting and deployment.
- Spec: `docs/superpowers/specs/2026-10-14-velometer-m13-design.md`.
- Plan: `docs/superpowers/plans/2026-10-15-velometer-m13.md`.
- SDD ledger, briefs, reports and reviews: `.superpowers/sdd/2026-10-15-velometer-m13/` (git-ignored scratch).

The committed evidence is in `docs/review/`:
- `m13-counters.md` and `m13-terms.md`;
- `m13-minors.md`, which has every deferred minor from M8 to M12 with its fix, close or keep;
- `m13-screen-reader.md`;
- the M13 section of `m8-overlay.md`.

Each ruling reads: Ruling — why — cost.

## User rulings

Before the spec (2026-10-14):
- Index v2 is versioned. `counter_index` gains a `method` column, and the site switches to v2.
- Overlay v5: measure first, then decide.
- Paris: fix the in-service granularity and reload.
- Extras in scope: an Orca screen-reader pass, and the deferred review minors from M8 to M12.
- Out of scope: the Straßburg exonym and the GeoJSON shrink.
- "No rm rf commands." No recursive force delete was run, and the SDD workspace stays in place.

## Review notes

The user marked the review page (artifact `1R7w8Z6FP8z11dMRnTgQqS`) on 2026-10-15:
- **Sentences:** all 107 changed sentence rows and the 5 methodology rows are OK: "All still open text changes are: OK". No German paragraph needed re-stamping for a note.
- **Palette:** keep the new colour-blind-safe series palette. It is darker in light, and series 1 goes from #2a78d6 to #7095bf.
- **Plan chart:** build a second panel. The mapped-km line moves out of the per-year chart onto its own panel, on the same years (Task 13a, `f317a19`). This replaces Task 8's right axis.
- **Overlay v5:** accept "not needed". See Measured effects.
- **Index wording:** use "complete day" throughout, in German "vollständiger Tag" (Task 13b, `5743a5a`).
- **German tier E:** accept "Fahrradstraßen o. Ä."
- **Berlin network term:** accept *Radvorrangnetz* or *Vorrangnetz*, whichever form its citation prints.
- **Small points:** "Handle all now". Task 13b did all of them:
  - the Bezirke remainder label is glossed (G1);
  - methodology headings have shared ids, and the Berlin main-roads pointer (G7) lands on its paragraph;
  - `content --check --online` reads PDFs and retries a timeout;
  - chart downloads carry the plan and Counts keys (Task 13a).

## Measured effects

- **Paris and Helsinki in service by hour (§4.1).**
  - The hour rule moved almost nothing. The M8 defect occurs only once in the real data (1 Paris site-hour), and Helsinki was unchanged.
  - The rule for overlapping files fixed a separate defect that predated M13. On 119 Paris site-days (2025-09-06 to 12-31, 8 sites), the rolling export's partial sums had overwritten the archive. Fixing it restored 31,520 counts.
  - Paris 2025 v1 index: 205.156574 → 205.244892.
- **Counter index v2 (§4.2).**
  - 37 of 49 links move by less than 0.5 %.
  - The largest moves are Paris 2019→2020 (−2.09 %) and Helsinki 2024→2025 (+2.06 %). Barcelona is unchanged.
  - Berlin 2020 goes from 114.6 to 114.2.
  - v2 does not remove the coverage effect entirely. A difference in coverage still moves the ratio through the weight a site's days carry in the pool, and the methodology says so.
- **Overlay v5 (§4.3), not built.**
  - Read literally, the plan's "real loss" is above 2 km: 3.49, 4.55, 6.46 and 6.50 km on runs 735, 739, 743 and 713.
  - That figure counts outer-corner pieces. Of 32 rendered samples, at most 2 follow the network; the rest are streets that continue past the turn.
  - The km a turn would actually recover are 0.36, 0.37, 0.59 and 0.59, all under 2 km. The 2-in-32 rate from run 743 is applied to the other runs.
  - The user accepted this.

## Ledger rulings

- **Minors ledger location.** It lives at `docs/review/m13-minors.md`, committed, not in the git-ignored workspace the spec named. The record must survive. Costs nothing.
- **SDD workspace.** It is not deleted at the end (the user's no-rm-rf rule). Costs a few KB of scratch.
- **Helsinki and the hour rule.** `sum_counters`' hour rule applies to Helsinki too, because the function is shared (the spec was amended in 4d98ce2). Costs a Helsinki change the user did not name; there was none.
- **Reload source.** Paris and Helsinki reload from the existing raw files, with no new download. This isolates the method's effect. Costs the newest months of the rolling export.
- **Overlapping counter files.** A site-hour keeps the reading with more reporting counters; on a tie, the later file wins. Otherwise the hour rule lets a partial reading at the edge of the rolling export overwrite the archive's full one. Costs a small loader change.
- **Shared test cases.** Spec §4.2's "py-js parity for `tests/counter_cases.json`" is moot: JS has no chain function. The shared cases stay py-only. Costs nothing unless JS ever computes links.
- **Coverage wording.** Spec §4.2's sentence "a coverage difference no longer moves the ratio" is wrong under its own formula. The methodology states the accurate version, and the user accepted it.
- **Palette search range.** The light palette search was widened to OKLCH L 0.30–0.66, because the brief's 0.45–0.62 holds at most 6 colours that pass. The rule is ΔE ≥ 20 under normal, deuteranopia and protanopia vision, in both themes. The closest pairs sit at 20.06 in light and 20.05 in dark, against a floor of 20. The user accepted it.
- **Online check before M13.** `content --check --online` was already red at baseline: 143 lines, mostly PDFs read as text, plus the grandlyon.com timeout. Task 6 was judged on its new excerpts. Task 13b then fixed the checker (see Follow-ups for what remains).
- **/tmp quota.** /tmp reached its user quota (EDQUOT). The M13 scratch was moved with `mv` into the git-ignored `data/scratch-m13/`; nothing was deleted, and other sessions' directories were left alone. Costs nothing.
- **Strict term forms.** Original terms use the exact form of the cited source. *Radvorrangnetz* is used wherever only the Drucksache or the amendment is cited. The user accepted it.
- **Tier E in German.** The German tier E reads "Fahrradstraßen o. Ä." in labels and prose. The methodology reads "Fahrradstraßen und vergleichbare Straßen sowie für den Radverkehr freigegebene Busspuren". The legal category is narrower than tier E. The user accepted it.
- **Methodology check pytest.** No pytest runs `report methodology --check`, because it needs the git-ignored database; data bullets sit outside the generated markers. The check runs in the six-check set instead. Costs a manual step.
- **Isolated Orca run.** Orca ran only inside an isolated `dbus-run-session`, with headless Chrome and speech going to its debug log. It never touched the user's Wayland desktop, session bus or speakers. Orca really ran; the fallback was not used.
- **Metric-id tooltip (D2).** The Figures metric-id `title=` from M7 (`7be82d3`) is removed (`5efdef7`), because Orca read the raw id as each row's description. The tooltip was a render-check convenience, not an M7 ruling. Costs the id on mouse hover; an `aria-hidden` child could restore it.
- **Bezirke label precedence.** The G1 gloss of the Bezirke remainder label supersedes the label as quoted in ADR 0004 (line 128) and `rulings-m6.md` (line 47). The locked ADR is not edited; this line records the change.
- **v1 index rows recomputed.** Stored v1 index rows are recomputed on each `counters load` instead of being kept frozen as the spec described. Both methods come from the same `counter_daily`, so a reload keeps them comparable. The v1→v2 table in the methodology is built from those rows. The cost: v1 values follow any later data fix instead of staying as they were at M12.
- **Schema v10 migration.** `velometer migrate` takes an M12 database to schema v10, but it writes only v1 index rows. No counter line shows until `velometer counters load` has run for all seven cities. Since the final fix round, `migrate` prints that hint. HANDOVER §9 records the step.
- **Plan chart scale.** The per-year panel's off-scale cap still counts the mapped values, so Vorrangnetz's 60 and 100 km targets stay on scale. No behaviour change came with the panel split.

- **Sources overflow at 1280.** The final render pass found the English Sources table 49 px wider than its column at 1280 (1169 > 1120). The cause is *Hauptradverkehrsnetz*, which Task 7 brought in as an original term: one unbroken word that no German hyphenation rule reached on an English page. The original-term marks in the table now take `hyphens: auto; overflow-wrap: anywhere` (`0f4b41e`). Where the browser has no German dictionary, as in headless Chrome, the word breaks without a hyphen. That costs one unhyphenated break in that cell.

## Follow-ups

- **Online check.** 14 excerpts are still not found after Task 13b (143 lines at main → 14):
  - 7 scanned PDF pages, which would need OCR;
  - 3 PDF table columns;
  - one each of a running header, a soft hyphen, interleaved text boxes and bullets.
  None is a wrong excerpt. The list is in `docs/review/m13-minors.md` (M13-l). The Bordeaux excerpt `epci-28-communes` was corrected to "(EPCI)" as the page prints it; it had been typed with the old checker's space artefact.
- **Sources links.** Sources has 15 links all named "source". That passes WCAG 2.4.4 but fails 2.4.9 (AAA). A wording pass could add visually hidden context.
- **Accessibility markup.** Some data tables have no `<caption>`, and city endonyms carry no `lang` (proper names are exempt).
- **Missing `lang`.** The mixed-language plan titles (Vienna, Lyon) and Oslo's source carry no `lang`. The new `bracket_lang` field can tag them.
- **UI labels.** Original terms in UI labels, such as the `figure.scope` and `figure.basis` labels in `content/ui/*.yaml`, carry no `lang`, because UI strings can't hold the `<i lang>` mark. A UI-string mark or a per-key language field would close this.
- **Download wrap.** Downloaded-chart titles wrap by the average glyph width. A line of wide glyphs can overrun by a few px, which the 16 px margin has absorbed so far. Measuring each line would be exact.
- **Bisectability.** The G1 commits are not bisect-clean: `e64a0eb` fails about 6 tests until `e7cb62f`. This is cosmetic.
- **Test warnings.** ResourceWarnings remain in some test files; they predate M13.
- **Hover id.** If wanted, restore the Figures metric id on hover through an `aria-hidden` child.
- **Language switching under Orca.** German UI labels are spoken in the English voice, because of the run's process locale (`LANG=en_US.UTF-8`). Re-run with a German locale to confirm language switching.
- **Rejected for now: full-text search.** Search over narrative text and quotes (M11-9) is a new feature, kept as an open idea.

## Acceptance (head `0f4b41e`)

- **Gate:** green, with 2900 passed and the node tests at 0 failures.
- **Six checks:** all exit 0 (`counters --check`, `content --check`, `report methodology --check`, `timeseries --check`, `reconcile --check`, `trust check`).
- **Full render pass:** `--pages all`, both themes, 1280/390/320, both editions. 1230 visits, 0 with findings.
- **Type render pass:** `--pages types --interact --keyboard --flip`. 173 visits, 0 with findings.
- **Sources page:** the screenshot at 1280 was checked after the overflow fix.
