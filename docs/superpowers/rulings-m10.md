# M10 rulings

Polish and accessibility (spec `docs/superpowers/specs/2026-10-09-velometer-m10-design.md`, plan
`docs/superpowers/plans/2026-10-10-velometer-m10.md`). These are the controller rulings from the SDD
ledger (`.superpowers/sdd/2026-10-10-velometer-m10/progress.md`), in readable form, by task. Each
gives the decision, the reason, and what it costs.

## Pre-flight

- **Missing-token fallback in the JS is a neutral grey plus one `console.error`, not "the light
  value" (spec §5).** A light-value fallback would copy every token into JS, against decision 2's
  single source. The render pass fails on the console error either way. Cost: a one-line change if
  the user prefers the spec wording (the user was told).
- **The series palette changes too.** Three of the eight old series colours were under 3:1 on white
  and decision 7 requires chart lines at 3:1. The series rule is normal-vision colour difference
  (ΔE at least 20) only. Cost: city colours change on charts.
- **Quote language comes from `Source.language`.** Every source already has one, so decision 6
  needs no new markup in the content. Cost: none.

## Task 1 (render pass)

- **Fix round 1 took the review's Important finding and M1 to M7.** The tool is every later task's
  proof, so it must not pass silently: overflow exclusions no longer hide leaf text spill or
  clipped content, errors and statuses are findings, an empty run fails, results are saved after
  every visit, `--chrome` / `VELOMETER_CHROME`, and `--interact` opens the compare panel and runs
  axe on it in both themes (this replaced a manual-only plan). Cost: one larger round.

## Task 3 (tokens and contrast)

- **Input, select and chip borders must reach 3:1.** Decision 7 names "borders of inputs"; the
  plan's test exempted `--grid-2` as decoration, which was a plan defect. Cost: a border token.
- **Fix round 1 hardened the contrast tests** (SVG fill text held to 4.5:1 and six smaller items),
  because they are the theme's only gate. Cost: one round.

## Task 4 (JS reads the tokens)

- **The light change colours stay under 3:1 on white.** Decision 3 fixes them at their M9 values
  so the change PNGs are not regenerated. They draw over greyed tiles, not white, and the key
  swatch carries a text label. Cost: a known 1.4.11 gap on the change map in the light theme; it is
  stated in the HANDOVER accessibility statement and listed in the Follow-ups.

## Task 5 (maps and PNGs)

- **No PNG is embedded in any page**, so the light plate (`figure.map-png`) guards future use only.
  Decision 4 assumed embeds; the PNGs are linked and open on the browser's own background. Cost: a
  dark-theme reader opening a PNG link sees it on the browser default; accepted.
- **The `report maps` `.run` marker ignores the palette.** A palette change re-renders nothing
  unless the markers are deleted; documented in HANDOVER §8. Cost: a manual step.

## Task 6 (phone tables)

- **Task 6 also owns the non-table overflow the baseline found at 390 and 320 px** (`.keynums`,
  the tab and crumb lists, `:root` on seven city pages, the panel's tiers table), because decisions
  5 and 6 require reflow at 320 px. Cost: a larger task.
- **The Bezirke "Mapped change" table stacks.** Only methodology and explainer prose tables scroll
  (decision 5), so the first fix that put it under `.prose` was reversed. Cost: a template and
  markdown post-process.
- **The compare table keeps a visible sort bar below 600 px** (its header shown as a wrapped row
  of sort buttons). The brief's visually hidden header assumed no controls in it; 2.4.7 and
  working sort outrank it. Cost: a CSS exception for `.compare-table`.

- **Fix round 1 also takes M1 to M3 and a re-shoot.** A test that `compare.js` builds the `.stack`
  table and calls `labelCells` after each render and re-sort (M1); `.kn` pinned to
  `min-width: 0` (M2, the 320 px fix); the Figures "Ours" cell right-aligned like Theirs and Gap;
  and a 320 px re-shoot of the breadcrumbs. All cheap. Cost: none.

## Task 7 (focus, regions, live region)

- **Keep the post-process layer (`regions.py`) for scroll regions** and narrow it: class token
  match, a wrapper's name only from a caption or heading inside or labelling it, no double tab stop
  on a table inside a `.scroll`, groups tied to their labels with `aria-labelledby`, and a test
  that `panel.js` releases its charts. It covers live, export, panel and 404 in one place.
  Cost: one round.
- **`main`'s focus ring after the skip link is accepted.** Removing it would break the
  no-outline-removal guard.

## Task 8 (data tables, flags, language)

- **Task 8 also carries decision 6 items missing from the plan text:** tier-line charts have a
  key, tier-map side popups name their tier, the markdown renderer keeps `lang` on quotes, and
  `content --check` fails on a `lang` that is not BCP 47. The spec outranks the plan. Cost: a
  larger task.
- **The Story aside table fits its box** (compacted; stacked if compaction fails) and a stale
  `aria-describedby` is removed when a step has no table. Cost: one small round.

## Task 9 (full render pass, fix wave, keyboard pass, docs)

- **Column heads wrap.** The overflow entries at 1280 px that earlier tasks called "intentional"
  were not prose tables: the overview rank-comparison table (1310 px in a 1120 px box), the
  city Time tab's presets table (575 in 544), and the stories step-values tables (633 and 463
  in 432) were all held open by `white-space: nowrap` on long column heads. A rule
  (`thead th { white-space: normal }`) fixes all four at once; data cells stay on one line. The
  tool needed no change: none of them was a prose table. Cost: taller headers on narrow columns.
- **Sorting the compare table keeps keyboard focus.** The keyboard pass found that the sort
  re-render dropped focus to `<body>`; the click handler now refocuses the rebuilt header button.
  Cost: a `data-key` attribute on the sort buttons.
- **The keyboard pass lives in the tool (`--keyboard`)**, so it is repeatable and its steps are
  recorded in `results.json`, instead of a manual script. Cost: about 250 lines in the tool.
- **Parked minors folded in:** `_stack_table` no longer double-escapes `data-label` (`A & B`),
  the dark-tile negative guard also forbids rules on the marker pane and icons, the tautological
  `TIERS` loop in the swatch test is gone, the `compare.js` source guard strips comments first, the
  `.kn` selector is matched exactly, and the compare phone sort bar has a visible "Sort by"
  caption tied to the table with `aria-describedby`. Cost: none.
- **200% zoom and text spacing: the Figures tables scroll in their region** at 640 CSS px and
  under WCAG 1.4.12 spacing. Nothing is clipped and the page does not scroll sideways, which
  passes 1.4.10 and 1.4.12, but it departs from "only prose tables scroll". Raising the stack
  breakpoint above 600 px would not be robust (zoom on other screens gives other widths). Cost: a
  known limit, in the HANDOVER statement and below.

## Final review and the final fix wave

The whole-branch review (`.superpowers/sdd/2026-10-10-velometer-m10/final-review.md`) found no
Critical issue, three Important and seven Minor. One round took:

- **The compare chart keeps its description (Important 1).** `drawTable` rebuilt the table
  caption without the id the chart's `aria-describedby` points at, so after table view and back the
  chart's description dangled. The JS caption now carries `id="compare-caption"`. The keyboard pass
  gained a step that returns to the chart view and fails on any `aria-describedby`,
  `aria-labelledby` or `aria-controls` that names no element, and runs axe there (axe did not flag
  this case; the id check did). Cost: one more step in the keyboard pass.
- **Node tests own spec decision 7 (Important 2).** The chart tests stub `getComputedStyle` with a
  token map: a line draws in its slot's `--series-N`, a tier in its `--tier-x`, and no chart draws
  from the missing-token fallback. A theme change redraws a connected chart, and a disconnected one
  lets go instead. Cost: none.
- **Honest claims (Important 3).** The HANDOVER Accept line and accessibility statement say what
  is audited: every exported page as loaded, plus Compare with a panel open and the keyboard
  pass; the full `--pages all` pass is cited as run on the M10 head. The light change-map gap is
  named as a WCAG 1.4.11 gap. Cost: wording.
- **The "Sort by" description applies only where the caption is visible (Minor 4).** The table is
  described by it under the phone query and the attribute follows the window across the breakpoint.
- **An empty card cell keeps its label and says so (Minor 5).** On a phone it shows a dash with the
  spoken alternative "no value" instead of vanishing; no displayed number changed.
- **A plan item without yearly rows gets no chart (Minor 8).** It shows a note instead, so a chart
  never ships without its data table.

Parked to M11: the chart SVG keeps axis and label colours on CSS classes, so a saved SVG would
differ from the screen (matters for downloads); `regions.py` tag counting inside `<script>` and
comments (latent); source-grep tests that could become behaviour tests; `.sr-only` and
`.visually-hidden` are one rule twice.

## Follow-ups

- **Light change-map colours under 3:1 on white** (decision 3 fixed them). A fix needs the change
  PNGs regenerated.
- **Dark PNG maps were not made** (out of scope); PNGs are linked, not embedded, on the browser's
  own background. If a page ever embeds one, add a synthetic self-check to the plate test (its page
  scan is vacuous today).
- **Series palette: normal-vision ΔE only.** Tiers B and E are only ΔE 20.5 apart under
  deuteranopia. Charts label series directly and have tables, but a colour-blind-safe series
  palette is open.
- **`report maps` `.run` marker ignores palette changes.** Make the marker include the palette.
- **Figures tables scroll at 200% zoom on a 1280 px screen** (640 CSS px) and under text spacing;
  consider stacking below 700 px.
- **Missing-token fallback wording** (spec §5 versus the ruling): one line to change.
- **Screen-reader testing** with real assistive technology was not done.
- **Deferred minors:** the `importlib` loader is duplicated in three tests; `lab()` white point is
  off by about 0.01 and `ciede2000` is unannotated with an unused 3-digit hex branch;
  `CITY_COLOURS[:7]` leaves series 8 unused in Altair; the text-colour scanner in the chart tests
  sees only inline `svgEl` attributes and `.style.color`/`.fill` (and its hex regex could hit an id
  like `#add`); chart redraw resets hover state; `regions.py` matches the wrapper with a double
  quote only and a nested `.scroll` gets its own stop; `panel.js` draw/load test seams;
  `QUOTE_MARK` before `CODE_MARK` can misnest; the tier key and popup tests grep source; the
  "suspect" alt text in plans rows is unproven; the interact test asserts `axe` is a list only.
- **Render-pass cost:** `--pages all` with `--interact` is 600+ visits and takes about an hour.
