# velometer M13: Follow-up batch (design)

Status: draft for user review, 2026-10-14. There is no roadmap entry: the M9 roadmap ended at M12.
The user asked for "everything but hosting / deployment as one batch". This spec gathers every open
follow-up recorded in `rulings-m8.md` … `rulings-m12.md` and
`.superpowers/followups/original-terms-inventory.md`, minus the items excluded in §2.

## 1. Purpose

Close the open follow-up ledger in one milestone. Three items change stored numbers (the counter
index method, the Paris counter days, and, only if the measurement in §4.3 says so, the plan
overlay). One item changes reader-visible terms in both editions (original national terms). The
rest fix accessibility, colour, layout and code hygiene. Each changed number is disclosed in the
methodology, and the changed prose gets one user review stop.

## 2. User decisions (2026-10-14)

- **Scope:** everything except hosting and deployment. The user also excluded the Straßburg exonym
  and shrinking the tier-map GeoJSON, so both stay open.
- **Counter index v2:** switch to v2, versioned. Each link's ratio becomes the *pooled mean per
  complete day*; v2 becomes the headline; the methodology states the change and shows the v1→v2
  differences. This reverses the M8 ruling that kept the sum over complete days (spec §2.13/§5.3),
  at the user's request.
- **Overlay v5:** measure first. Build v5 only if v4 loses more than 2 km of real along-network
  km (or more than 1 % of the overlay km) on a measured run. Otherwise close the item with the
  measurement written down.
- **Paris in-service:** fix it and reload; the Paris index changes, and the change is disclosed.
- **Screen reader:** a real Orca pass, in scope.
- **Deferred review minors from M8–M12:** in scope.
- **Original national terms:** the decisions of 2026-10-14 recorded in the inventory stand:
  - the original term comes first with the translation in brackets, in both editions;
  - only the comparability hits are in scope;
  - a term with no source gets an official source added before it is used;
  - the user reviews the changed sentences.

## 3. Facts this design rests on (survey of 2026-10-14)

- `counters/index.py`:
  - `_chain` sums `values[year][site]` over the sites valid in both years. For daily series,
    `values` is the count summed over complete days.
  - The M8 final review measured a pooled-mean link against the stored one: 37 of 49 daily links
    move by less than 0.5 %. The largest moves are Paris 2019→2020 +2.1 %, Helsinki 2024→2025
    −2.0 %, Helsinki 2022→2023 −1.8 %, Paris 2023→2024 +1.6 % and Oslo 2018→2019 −1.3 %.
- `counter_index(city_id, year, idx, sites, base_year, series)` has no method column.
- Barcelona (`chain_index_monthly`) uses only sites with all twelve months in both years, and
  each site's value is a mean. Pooling therefore gives the same ratio as v1, so Barcelona does
  not move.
- Paris: `counters/days.py` `sum_counters` sets a counter's in-service span from its first to its
  last reported *day* in a file. On a counter's first and last day, the hours outside its
  reporting are counted as missing, so those site-days become incomplete. The rolling 13-month
  export is UTC, so its first local day starts mid-day. Raw files for 2016–2025 are under
  `data/counters/paris/`.
- Overlay:
  - `scripts/overlay_false_positives.py` classifies the pieces that one version keeps and another
    drops.
  - The M8 log puts the real along-network km that v4 loses at about 0.5–3 km on 2026-01-01
    (run 743), "not a strict bound".
  - The overlay versions are in `config/plans/overlay_v{1..4}.yaml`.
- Orca 50.2, speech-dispatcher and AT-SPI 2.60 are installed on this machine.
- The original-terms inventory lists 48 comparability hits in 13 countries:
  - nine have no source yet: S2–S4 *län*, NL5 *Groot-Amsterdam*, FR5/FR7
    *Métropole*/*département*, ES4, ES8, PL1 *gmina*, and G8 has no source term;
  - two "also check" items: the German tier-E label "Fahrradstraßen" against the legal
    *Fahrradstraße*, and the raw English `figure.scope`/`basis` ids in `ui/*.yaml`.

## 4. Design

### 4.1 Paris: in service by hour (stored numbers change)

- A counter is in service from its first to its last reported **hour** (local time, as now)
  within a file, not from day to day.
- A site-hour is kept when every counter in service *at that hour* reports it. Day completeness
  still means 24 site-hours present.
- This also fixes the partial first local day of the UTC rolling export.
- An outage inside the span still makes a day incomplete (unchanged, as documented).
- Reload Paris from the raw files already in `data/counters/paris/`. Re-download only a file that
  is missing.
- Ruling (2026-10-15, planning): `sum_counters` is shared with Helsinki (bridge sides), so the
  hour rule applies there too. Helsinki is reloaded the same way and its effect is reported.
- Report the change in complete days per year and the Paris index before and after, separately
  from the v2 effect (§4.2).
- The adapter docstring and the methodology sentence on Paris are updated.
- Tests:
  - a counter starting at 14:00 leaves its first day's earlier site-hours complete;
  - an outage hour inside the span still makes the day incomplete;
  - the rolling export's first UTC hours, converted to local time, are handled the same way.

### 4.2 Counter index v2 (stored numbers change)

- The link ratio for years t−1→t, over the sites S that qualify in both years, is:
  `(Σ_S count_t / Σ_S completedays_t) / (Σ_S count_{t−1} / Σ_S completedays_{t−1})`.
  This is the pooled mean per complete day.
- Qualification, `MIN_SITES`, `MIN_VALID`, chaining, base-year rules and chain breaks stay as
  §2.13.
- Monthly series: unchanged (see §3).
- Versioning:
  - `counter_index` gains `method TEXT NOT NULL` (`v1`/`v2`). It is part of the key, so rows are
    selected by method.
  - A migration tags the existing rows `v1`.
  - The recompute writes `v2` rows and keeps the `v1` rows, which feed the methodology's
    comparison table.
  - The current method is named once, in `counters/model.py` (`INDEX_METHOD = "v2"`).
  - Readers (Compare, the Counts tab, CSV, search, citations) read `INDEX_METHOD` rows only.
- The v1 function is kept, renamed `chain_index_v1`. Both functions are tested against one shared
  case file (`tests/counter_cases.json`, extended), and the py/js mirror stays in parity.
- The methodology (en/de) describes the method and why it changed: a coverage difference between
  the two years no longer moves the ratio. A generated table lists every link that moved by
  ≥ 0.5 %, from the stored v1 and v2 rows. Prose that states an index value draws it from facts;
  `content --check` catches drift.
- `counters --check` also asserts that every city with v1 rows has v2 rows, and that the v2 base
  year is 100.

### 4.3 Overlay v5 (measure, then decide)

- Extend `overlay_false_positives.py` (or add `--real-loss`) to measure, per run, the km that v4's
  directional free-end rule drops while a matching network line runs *along* the piece. These are
  the real turns clipped. Measure Berlin's LAU runs for 2018-01-01, 2022-01-01 and 2026-01-01,
  with the run ids queried from the DB.
- **Decision rule:** build v5 only if any measured run loses more than 2 km, or more than 1 % of
  that run's overlay km.
  - **Below the threshold:** record the measurement in `m8-overlay.md` (M13 section) and in
    rulings-m13, then close the item.
  - **Above it:** write `config/plans/overlay_v5.yaml` with a turn rule that keeps along-network
    pieces across a network turn. Check it on the same classes; v5 must not raise the
    false-positive classes above v4 by more than it recovers. Then rerun the overlay for
    Berlin's runs as `overlay_v5`, which becomes the latest version, and disclose it in the
    methodology. A reader-visible km change goes into the §5 review.

### 4.4 Colour

- **Series palette, colour-blind safe:** pick the series colours by rule. In both themes the
  pairwise CIEDE2000 difference must be ≥ the M10 normal-vision floor under normal vision and
  under simulated deuteranopia and protanopia (Machado 2009 matrices), with 3:1 against the
  ground. Tiers B and E (ΔE 20.5 under deuteranopia today) must pass. Extend
  `tests/test_colour.py`. Altair's `CITY_COLOURS` uses all eight.
- **Light change-map colours:** ≥ 3:1 on white; regenerate the change PNGs.
- **`report maps` `.run` marker:** it includes a hash of the palette, so a palette change
  re-renders without deleting markers by hand. HANDOVER's manual-delete note goes.
- The missing-token fallback wording follows the M10 ruling (one line).

### 4.5 Layout

- Figures tables stack into labelled cards below 700 CSS px, not 600 px. This covers 200 % zoom on
  a 1280 px screen and the 390 px Figures-tab scroll left from M7. Methodology and explainer prose
  tables keep their scroll.
- The phone-width CSS tests assert the resolved cascade in headless Chrome (computed style), not
  that a rule is present.

### 4.6 Original national terms (both editions)

- Apply the rule (original term first, translation in brackets) to every in-scope hit in the
  inventory, in English and German.
- For the nine hits without a source: find an official source (a statistics office, the law, or
  the authority's own page), add it to `content/sources/*.yaml` with a quoted excerpt and a gloss,
  then apply. A term is never written from memory. A hit with no official source found is
  reported and left as it is.
- G4 check: whether the Abgeordnetenhaus's "Nebennetz" is the Ergänzungsnetz. If the source does
  not say so, use "Nebennetz" with a translation.
- G7 (high): the Berlin legal *Hauptverkehrsstraßen* must not read as velometer's "main roads".
  Use the original term, plus a one-line pointer to the velometer definition where the two meet.
- SK1: the German edition stops using the StVO term "Schutzstreifen" for the Slovak *ochranné
  pruhy*.
- "Also check":
  - the German tier-E label gets a disambiguation if velometer's tier E is wider than the legal
    *Fahrradstraße*;
  - the raw `figure.scope`/`basis` ids get glossed labels in both editions.
- The German translation stamps are renewed for every touched paragraph after the user review.

### 4.7 Screen-reader pass (Orca)

- Run Orca with Chrome (`--force-renderer-accessibility`) against the exported site under
  `/velometer/`, on a fixed sample in both editions:
  - home;
  - Compare with the table view, the chart view and an open city panel;
  - a city page with its tabs;
  - Figures;
  - methodology;
  - Sources;
  - search (type, arrow, select);
  - an open Cite;
  - the Download menu;
  - the 404 page.
- Speech is captured to a log (speech-dispatcher's dummy output module or Orca's debug log),
  together with the key sequence. The log is committed under `docs/review/m13-screen-reader.md`
  with findings.
- If Orca cannot drive Chrome here (no session bus or display), fall back to the Chrome
  accessibility-tree audit (`read_page` / CDP `Accessibility.getFullAXTree`) of the same sample.
  The review log must label it as that fallback, not as a screen-reader check.
- Every finding that is a defect is fixed with a test. The rest are recorded.

### 4.8 Defects, hygiene and dependencies

- **Deferred minors:** every open, unmarked minor in the Follow-ups of rulings-m8 … m12 is
  triaged into one ledger, `.superpowers/sdd/<m13>/minors.md`, in one of three groups:
  - **fix:** a defect, a drift risk or a misleading test, fixed with a red-first test;
  - **close:** obsolete or already fixed, closed with the reason;
  - **keep:** a deliberate design trade-off, kept with the reason.
  These rulings close one item each:
  - the plan chart's cumulative line axis: the cumulative line gets its own labelled axis or
    panel, as M8 disclosed;
  - the unreachable km-only Counts chart branch: removed;
  - the Madrid detector clause: gets the `note:` field M8 proposed, so `--check` sees it;
  - the Copenhagen 37 / Strasbourg 52 suspect flags: a test asserts the suspect *rule* on a
    fixture, not the two values.
- **Starlette `httpx` deprecation warning:** remove it with the smallest change: adapt the
  TestClient use, or bump fastapi/starlette within the lock if that is the only way. The gate's
  pytest output must show no warning from this source.
- **`test_overlay_facts`:** run it 200 times in random orders and in isolation. Find and fix the
  cause, or record "no repro in N runs" with the commands and close it.

## 5. User review stop (single)

One private review page, in the M12 pattern, with English and German side by side, old and new,
grouped by page. It holds:
- every sentence changed by §4.6;
- every prose sentence whose wording changed because of §4.1–§4.3 (numbers that come from facts
  change without a wording change, and are listed only as a summary table);
- the new methodology paragraphs on index v2 and Paris.

The user marks lines and leaves notes. Claude applies them and re-stamps the German paragraphs.
Execution runs everything else in parallel with the wait for this review.

## 6. Out of scope

- Hosting and deployment (HANDOVER §12 Q4).
- Shrinking or simplifying the tier-map GeoJSON.
- The Straßburg exonym.
- Dark PNG maps.
- The English-word sniff heuristic.

## 7. Execution order

1. Paris by hour (§4.1), then index v2 (§4.2) on the reloaded data, each effect measured on its
   own.
2. Overlay v5 measurement (§4.3), and v5 only if the threshold is crossed.
3. Original terms (§4.6): the source lookups first, then the edits; the review page is published
   as soon as §4.1–§4.3 prose is drafted.
4. Colour (§4.4) and layout (§4.5).
5. Minors, the warning and the flaky test (§4.8).
6. Orca pass (§4.7) on the export of the near-final head, then fixes.
7. Review notes applied (§5); HANDOVER, rulings-m13 and CLAUDE.md updated; final whole-branch
   review.

## 8. Accept

- The gate is green, including the node tests, with no Starlette deprecation warning.
- The six checks exit 0.
- `velometer.sqlite` changes only in:
  - the `counter_index` method column and its v2 rows;
  - Paris and Helsinki `counter_sites`/`counter_daily`;
  - `plan_overlay` v5 rows, only if built.
  A `velometer results` diff shows no other change.
- The full render pass (`--pages all`, both themes, 1280/390/320, both editions) and
  `--pages types --interact --keyboard --flip`, run on the M13 head, exit 0.
- Screenshots were looked at in both themes:
  - Figures at 390 and at 200 % zoom;
  - Compare with the new series palette, under a deuteranopia simulation;
  - a regenerated change map;
  - the methodology v2 table;
  - a city page with original terms, in both editions.
- `docs/review/m13-screen-reader.md` exists, says which method ran, and lists its findings.
- Each of the §2 decisions is reflected in rulings-m13, with the measured v1→v2, Paris and overlay
  effects.
