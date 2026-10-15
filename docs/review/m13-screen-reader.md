# M13 screen-reader pass (Orca)

**Method: a real screen reader ran.** Orca 50.2 (AT-SPI2 2.60.4) read the exported static edition
in Google Chrome. Every utterance below comes from Orca's speech output, captured in its debug log.
This is not the accessibility-tree fallback of spec §4.7. A CDP `Accessibility.getFullAXTree`
check was run only as a cross-check of two findings (marked "AX tree").

- Export: `uv run velometer app export --out data/scratch-m13/t11/export --base /velometer/ --clean`
  at `cce1798` (before), and again with the fixes (after).
- Driver: `tools/orca_pass.py` (committed; see `tools/README.md`).
- Raw output: `transcript.md`, `steps.json` and `orca-debug.log` under `data/scratch-m13/t11/run4`
  (before the fixes) and `.../run9` (after). The output is git-ignored scratch.
- Final run: 28 steps, 230 actions, 5,307 utterances, no driver error.

## How it ran, and how that differs from a desktop session

The pass ran next to a live Wayland desktop without touching it. Everything ran inside
`dbus-run-session`, which gives a private session bus and so a private AT-SPI bus.

- **No display.** `DISPLAY` was unset, and `WAYLAND_DISPLAY` pointed at a socket that does not
  exist. Chrome ran headless (`--ozone-platform=headless --headless=new --app=URL
  --force-renderer-accessibility`). It still registered with the private AT-SPI bus, and Orca
  read it.
- **No audio.**
  - A stub blocked Orca's `speechd` import.
  - Orca's speech server was a stub that only writes.
  - Each utterance went to the debug log as `SPEECH OUTPUT: '<text>' <voice>`, with the voice's
    language (`lang`), which is how the language checks below were made.
  - `PULSE_SERVER` and `PIPEWIRE_REMOTE` pointed at nothing.
- **Orca's settings stayed out of the user's.** Orca used a private `HOME`, `XDG_*` and
  `GSETTINGS_BACKEND=memory`. Orca's say-all-on-load was switched off over D-Bus, so a page load
  speaks its first line.
- **Keys.**
  - Tab, Shift+Tab, Enter, Escape, the arrows and typed letters were real key events, sent to the
    page through CDP `Input.dispatchKeyEvent`. Orca heard the focus and caret changes they caused.
  - Orca's own browse-mode keys cannot reach Orca without a display. These are H (next heading),
    T (next table), Alt+Shift+arrows (table navigation), KP_Add (say all) and Orca+A (browse or
    focus mode). The pass sent them as the same Orca commands over Orca's D-Bus remote control,
    for example `StructuralNavigator.NextHeading`. The log names each one.
- **Harness workarounds.** Each is an artefact of driving Orca without a keyboard, not a property
  of the site:
  - Each page loads in a fresh Chrome. Navigating one tab left Orca's caret context on the
    previous page's objects.
  - A real key marks a file that the Orca shim reads. Without that mark, Orca's "last input event"
    stays the last D-Bus command, and Orca ignores every later focus change ("Event ignored: Last
    command was table nav").
  - Chrome's "Translate this page?" bubble is off. On German pages, Tab otherwise went into it.
  - When Orca settled a page in focus mode, the pass toggled browse mode (Orca+A), as a reader
    would on hearing "Focus mode".
- **Role words after H.** After a D-Bus H, Orca speaks the heading text without "heading level
  n". Orca sets its locus to the heading before it generates speech, so it treats the heading as
  the prior object. The role is in Orca's locus (`heading: '…'`) and is spoken in say all
  ("heading 1", "heading 2").

## The sample, both editions

The en and de columns show what Orca said. A slash (/) separates successive utterances. "OK" means
Orca said what a sighted reader gets.

| Step | Keys | en (Orca said) | de (Orca said) | Matches? |
|---|---|---|---|---|
| Home | load | "Finished loading velometer · overview." / "Page has 13 landmarks, 6 headings, 3 tables …" / "Skip to content link." | "… velometer · Überblick." / "Zum Inhalt springen link." [de] | OK |
| | Tab ×3, Shift+Tab | "Skip to content link." / "banner velometer link." / "navigation Main List with 10 items Overview link. (Current page)" / "velometer link." | "Zum Inhalt springen" / "banner velometer" / "navigation Hauptnavigation … Überblick link. (Current page)" | OK, except "Hauptnavigation" in the English voice (R1) |
| | H ×4 | "Protected cycling infrastructure in 21 European cities, as mapped" / "Headline ranking, city proper (LAU)" / "Over time" / "Explore" | "Geschützte Radinfrastruktur …" / "Rangfolge der Hauptkennzahl …" / "Zeitverlauf" / "Weiterlesen" [de] | OK |
| Compare, table | H ×2 | "Compare cities" / "Headline · City proper (LAU)" | "Städte vergleichen" / "Hauptkennzahl · Kernstadt (LAU)" | OK |
| | Tab to Table view, Enter, T | "Table link." / "City button." | "Tabelle link." / "Stadt button." | OK |
| | Alt+Shift+Down, Right ×2, Down | "row header. Berlin link. Row 2, column 1." / "Berlin. 113.7. … Row 2, column 2." / "2019 column header 112.5. ⚑ … (flagged) … Row 2, column 3." / "Paris. 34.8. 37.5. …" | the same in German number format ("113,7") | headers and the flag are announced (R5) |
| | Tab to the 2018 sort button, Enter ×2 | "City button. column header. column 2 2018 button." / "column header sorted descending. … 2018 ↓ button." / "… sorted ascending. … 2018 ↑ button." | the same | OK; focus stays on the button |
| Compare, panel | Tab to Berlin, Enter | "row header. row 2. column 1 Berlin link." / "Loading… Close panel button." / "Loading Berlin…" / "Berlin" (#live) | "Wird geladen … Fenster schließen button." / "Berlin wird geladen …" / "Berlin" | focus moves into the panel, the load is announced (R3) |
| | Tab ×2 | before: **"banner Open full page → link."** after: "Open full page → link." / "Cite Berlin: key numbers, city proper (LAU) toggle button collapsed." | before: **"banner Ganze Seite öffnen →"** after: "Ganze Seite öffnen → link." / "Zitieren Berlin: …" | **defect D1, fixed** |
| | Escape | "… main content Headline per city and snapshot. table with 6 rows 11 columns row header. row 2. column 1 Berlin link." | the same in German, with the table name in the English voice (R1) | OK; focus back on the opener |
| Compare, chart | Tab to Lines, Enter, Tab ×3, H ×2 | "navigation Views List with 4 items Lines link. (Current page)" / "Small multiples link." / "Rank link." / "Table visited link." / "Headline · City proper (LAU)" / "Wrapping to top. Compare cities" | "Ansichten" (English voice, R1) / "Linien" / "Kleine Diagramme" / "Rang" / "Tabelle" | OK |
| City page, tabs | Tab to the tabs, Tab ×5 | "City sections List with 6 items Story link. (Current page)" / "Over time link." / "Tiers" / "Figures" / "Counts" / "Bezirke" | "Abschnitte der Stadtseite" (English voice, R1) / "Geschichte" … | OK |
| | each tab loaded, H ×2 | "Berlin" / "Berlin: one re-mapping campaign, then a slow climb"; "Tier composition"; "Over time"; "Counter index"; "Bezirke"; "Why the figures differ" | the German headings [de] | OK |
| Figures (Copenhagen) | H ×2, T | "København" / "Why the figures differ" / "table with 13 rows 6 columns Source column header." | "Kopenhagen" / … | OK (R2) |
| | Alt+Shift+Down, Right | "Clean Cities Campaign, Cycling Ranking 2025 link. …" / before: **"protected cycling infrastructure as a ratio to the road network. protected_share_pct. 43.0 % …"** after: "protected cycling infrastructure as a ratio to the road network. 43.0 % +36.2% …" | before: the same id spoken; after: none | **defect D2, fixed** |
| | say all | "… The city counts 401 km of" / "cykelsti" **[da]** / "(kerbed cycle track) …"; the Danish quotes [da] | the same, plus the Danish source names [da] | the language switches |
| Methodology | H ×4, T, Alt+Shift+Down | "Methodology" / "What is measured" / "Classification rules" / "Headline and presets" / "Headline and presets. table with 4 rows 4 columns Preset column header." / "ours_headline Row 2, column 1." | "Methodik" / … / "Hauptkennzahl und Kennzahlvarianten." (English voice, R1) | OK (the preset ids are the visible cell text) |
| Sources | (Orca+A), H ×3, Tab ×3 | "Sources and how they measure" / "What the cells cite" / "Sources" / "List with 15 items source link." / "source link." / "source link." | the same in German | R4 |
| | say all | "Changing Cities e.V." [de], "Berliner Radnetz" [de], "Senatsverwaltung für Mobilität …" [de], "Københavns Kommune (" [da] "City of Copenhagen" [en] …, "cykelsti" [da], "Hauptradverkehrsnetz" [de] | the English publishers and titles [en] in the German page | the language switches |
| Differences, Organisations (language markup of Tasks 7 and 10) | say all | "cykelsti" [da], "cykelbaner" [da], "Radvorrangnetz" [de], "Stockholms län" [sv], the Vienna quote [de], the Paris quote [fr], the Abgeordnetenhaus quotes [de], "Nebennetz", "Hauptverkehrsstraßen" [de] | the English quotes and titles [en] in the German page, "Ville de Paris" [fr], "Linéaire cyclable (en km)" [fr] | the language switches on every marked span heard |
| Search | Tab to the box | "Search cities and pages editable combo box. opens listbox Focus mode" | "Städte und Seiten suchen editable combo box." | OK |
| | type "ber", Down, Enter | "b" / "8 results" / "6 results" / "3 results" / "Berlin (Germany)" / "… Finished loading velometer · Berlin." | "8 Treffer" / "7 Treffer" / "5 Treffer" / "Berlin (Deutschland)" / … | OK; the counts are announced and Enter lands |
| | type "zzz", Escape | "5 results" / "No match" / "No match" | "4 Treffer" / "Kein Treffer" / "Kein Treffer" | OK (R6) |
| Cite (Berlin, Over time) | Tab to Cite, Enter, Tab ×2, Enter on Copy | "Cite Berlin: key numbers, city proper (LAU) toggle button collapsed." / "expanded" / "Copy Text, Berlin: … button." / "Copy BibTeX, … button." / "Copied" (#live) | "Zitieren Berlin: Kennzahlen, Kernstadt (LAU)" / "Text kopieren, …" / "BibTeX kopieren, …" / "Kopiert" | OK |
| Download (Berlin, Tiers) | Tab to Download, Enter, Tab ×3, Escape | "Download Tier composition over time, Berlin LAU toggle button collapsed." / "expanded" / "Download SVG, …" / "Download PNG, …" / "Download CSV, … button." / (Escape: nothing, focus stays) | "Herunterladen Stufen im Zeitverlauf, Berlin LAU" / "SVG herunterladen, …" … | OK (R7) |
| 404 (one bilingual page) | H ×2, say all | "Page not found" / "Wrapping to top. Page not found" / "There is no page at this address." / "Go to the overview link" / "Seite nicht gefunden." **[de]** / "Unter dieser Adresse gibt es keine Seite." [de] / "Zur Übersicht" [de] | — | the language switches |

## Defects (fixed, each with a test)

### D1: a second banner landmark inside the city panel

On entering the open city panel, Orca said "banner" before "Open full page →".

- **Cause:** the panel fragment's `<header class="panel-head">` (`city/panel.html`). Compare puts
  the fragment in `<aside role="dialog">`. Because the explicit role replaces the aside's
  semantics, the `<header>` is not scoped by sectioning content and maps to `banner`.
- **AX tree before:** `banner`, `dialog 'City panel'`, `button 'Close panel'`, `banner`.
- **AX tree after:** one `banner`.
- **Fix:** `<div class="panel-head">`. The CSS selects on the class, so the panel looks the same.
- **Test:** `tests/test_a11y.py::test_every_page_is_one_banner_and_a_panel_adds_none`. Every
  page has exactly one `<header>`, and a panel fragment has none. It was red on
  `/city/berlin/panel` before the fix.
- **Before:** run4, "banner" spoken 2 times (en and de).
- **After:** run9, 0 times.

### D2: the Figures metric cells read out a raw id

On the Figures tab, Orca read each metric cell as "… road network. protected_share_pct".

- **Cause:** the cell carried `title="{{ r.metric }}"`. A title is the accessible description,
  and Orca speaks descriptions. A sighted reader sees the id only on hover.
- **Fix:** no `title` on the cell.
- **Tests:**
  - `tests/test_a11y.py::test_no_title_attribute_carries_a_raw_id`: no `title` on any page is a
    raw snake_case id. It was red on `protected_share_pct` before the fix.
  - `tests/test_app_m7.py::test_figures_rows_show_the_metric_label_not_its_id` now asserts the id
    is not in the cell. It used to assert that the id stays on hover.
  - Three M7 tests found their rows by the id and now find them by the label.
- **Before:** run4, the id spoken in the Figures step.
- **After:** run9, never.
- This reverses the M7 render-check choice "id in title" (commit `7be82d3`). See the report's
  concerns.

## Recorded, not defects

- **R1: accessible names are spoken in the browser's locale.** On German pages, Orca used the
  English voice for landmark labels and table names: "Hauptnavigation", "Ansichten",
  "Abschnitte der Stadtseite", "Die sechs Dimensionen", "Organisationen" (the nav label), and the
  table names "Hauptkennzahl je Stadt und Stand.", "Hauptkennzahl und Kennzahlvarianten.".
  - Text content, link and button names switch correctly ("Städte und Seiten suchen" [de],
    "Zitieren Berlin: …" [de]).
  - Orca takes the language of an object without text from AT-SPI's object locale. Chrome reports
    that as `en_US` for every object (Orca's log: "Reported locale of [landmark] is en_US";
    "[column header: 'Stadt'] is en_US"), whatever the `lang` in the page.
  - The markup is right: `<html lang="de">`, and the labels are German text. This is a
    Chrome/Orca limitation, not something markup can change. A German reader runs a German Orca
    voice by default, so these labels would sound right there.
- **R2: city endonyms in the English edition carry no `lang`.** For example, "København" is spoken
  with the English voice. These are proper names. WCAG 3.1.2 exempts proper names, and organisation
  names got `lang` by an explicit M13 decision (Task 10). City names were not in that decision.
- **R3: the panel is announced by its content, not its name.** On opening, Orca said "Loading…"
  (the dialog's placeholder text, as its "new ancestor") and not "City panel dialog".
  - AX tree: `dialog 'City panel'`, `modal: false`.
  - The markup is standard (`role="dialog"`, `aria-label`). This is how Orca 50 presents a
    non-modal dialog entered by focus. "Loading Berlin…" and "Berlin" then come through `#live`.
- **R4: Sources' "source" links have a generic name.** Tab on Sources gives "source link." three
  times. The purpose is clear from the list item they end ("3. BikeNetKit (GitHub, …) · source"),
  so WCAG 2.4.4 (in context) is met, but Orca's links list would show 15 "source" entries. This
  is a candidate for a later wording pass ("source: <title>").
- **R5: table navigation and headers.**
  - Row and column headers are exposed: compare has 16 header cells, Figures 20, methodology 40
    (AX tree).
  - Orca announces "row header", "2019 column header", "column header sorted descending" and the
    table name and size.
  - In its full-row reading, Orca did not repeat the column header on the first move into a row.
    That is Orca's presentation; the header is there.
  - Some data tables have no name (home 3, Figures 3, Over time 2), and Orca says only "table with
    N rows M columns". The tables are not announced without headers, so this is not a defect by
    the brief's rule.
- **R6: "No match" is said twice.** This is by design (Task 9): the status (`role=status`) and
  `#live` both carry it, because a live region is not always heard the first time. The result
  counts ("8 results", "6 results", "3 results") are announced as letters are typed.
- **R7: Escape does not close the Download disclosure.** Focus stays on the last button and is not
  lost. Download and Cite are `<details>` disclosures, which the pattern does not require to close
  on Escape. The Cities menu closes on Escape because it is a nav menu.
- **"Bezirke"** (a Berlin tab, English edition) is spoken in the English voice. It is used as the
  name of the tab, and Task 7's term inventory covers it.
- **No unnamed control** on any sample page in either edition (AX tree: no button, link, checkbox,
  combobox, option or dialog without a name).

## Reproduce

```bash
uv run velometer app export --out data/scratch-m13/t11/export --base /velometer/ --clean
uv run --group dev python tools/orca_pass.py --site data/scratch-m13/t11/export \
    --base /velometer/ --out data/scratch-m13/t11/run --editions en,de
```

The run takes about 7 minutes. It starts Orca, Chrome and a local server inside
`dbus-run-session` and stops each one by its own handle.
