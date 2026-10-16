# M14 screen-reader pass: Orca under a German locale

**Verdict: in one run per condition, the German labels were spoken in a German voice under a German
process locale and in an English voice without it.** All seven labels M13 R1 named got `lang: de`
in `run-de`; in the control (no locale) six of them got `lang: en`, and the seventh, "Organisationen",
got `en` for the nav label only (see below). That is consistent with the cause M13 R1 gave, the
run's process locale and not the markup. The site did not change in this task.

Limits of this claim:

- One run per condition. Nothing was repeated.
- Only the voice language of the labels is claimed. Orca's own role words were English in both
  runs (see below), and the speech around the labels is outside the claim.
- A reader with an English system locale reading the German edition was not tested.

## Method

Same pass as M13 (`tools/orca_pass.py`, Orca 50.x, `docs/review/m13-screen-reader.md`), German
edition only (`--editions de`: 14 steps, 113 actions, no driver error), on a fresh export at
`4000b3f`. Two runs on one export:

- `run-de`: `--locale de_DE.UTF-8 --locpath data/scratch-m14/locale`.
- `run-de-en`: the control. No locale, so the run inherits `LANG=en_US.UTF-8`, as in M13.

How it differs from M13: the new `--locale` and `--locpath` options. With them, the private session
gets `LANG` and `LC_ALL` set to the locale (the caller's `LANGUAGE` is dropped), `LOCPATH` set to
the directory, and Chrome gets `--lang=de`. The locale was built without root:
`localedef -i de_DE -f UTF-8 data/scratch-m14/locale/de_DE.UTF-8` (exit 0).

Isolation is unchanged: a private session bus, headless Chrome with no display, the speech stub
(no audio), and a private `HOME`, `XDG_*` and `GSETTINGS_BACKEND=memory`. No process was left
behind.

## Comparison

Voice language Orca reported (`lang` in `SPEECH OUTPUT`) for each label, from `steps.json`. The
counts are how many times the label was spoken in that voice.

| Label (M13 R1) | Control, no locale (`run-de-en`) | German locale (`run-de`) |
|---|---|---|
| Hauptnavigation | en (3) | de (3) |
| Ansichten | en (1) | de (1) |
| Abschnitte der Stadtseite | en (1) | de (1) |
| Die sechs Dimensionen | en (1) | de (1) |
| Organisationen (nav label, say all on /de/organisations) | en (1) | de (1) |
| Organisationen (other mentions: page title, heading and link text) | de (5) | de (5) |
| Hauptkennzahl je Stadt und Stand. | en (2) | de (3) |
| Hauptkennzahl und Kennzahlvarianten. | en (1) | de (1) |

The control already spoke the other "Organisationen" mentions in German because they are text
content (page title, heading, link text), which takes its language from the DOM `lang`. Only the
nav's `aria-label` has no text of its own, so it takes AT-SPI's object locale (M13 R1). The load
announcement "Finished loading velometer · Organisationen." carries no voice language in either
run. The table-name count differs by one between runs because the two runs do not speak the same
number of announcements.

Orca's own role words were English in both runs. In `run-de` and `run-de-en` the counts of
utterances containing them are the same: "heading" 81 / 81, "link" 530 / 530, "button" 43 / 43,
"landmark" 21 / 21, "navigation" 15 / 15, "list with" 21 / 21, "table" 32 / 30, "rows" 34 / 33,
"columns" 7 / 6. No German role word ("Überschrift", "Schaltfläche", "Liste mit") was spoken in
either (the "Tabelle" and "Zeile" hits are page text, 2 each in both). The German locale changed the
voice of the labels but not Orca's role vocabulary. Why was not investigated.

Debug-log "Reported locale" lines, by the locale AT-SPI gave Orca:

| Run | de_DE | en_US | empty (names no object) | total |
|---|---|---|---|---|
| `run-de` | 426 | 0 | 1 | 427 |
| `run-de-en` | 0 | 428 | 1 | 429 |

Voice languages over all utterances: `run-de` de 1466, en 152, da 58, fr 15, sv 4, none 1076;
`run-de-en` de 1448, en 172, da 58, fr 15, sv 4, none 1076. The 20 fewer English utterances in
`run-de` come from two sources, found by aligning the two logs:

- 14 identical utterances that changed from `en` to `de`: 10 of the labels above (Hauptnavigation
  x3, Hauptkennzahl je Stadt und Stand. x2, Ansichten, Abschnitte der Stadtseite, Hauptkennzahl und
  Kennzahlvarianten., Die sechs Dimensionen, Organisationen) and 4 other German strings that also have
  no text of their own: "velometer · Berlin", "Warum die Zahlen abweichen.", "Vergleich mit
  veröffentlichten Zahlen", "Amtliche und gemeldete Zahlen".
- Spoken `127.0.0.1:<port>/velometer/de/...` addresses, which differ between the runs because the
  server port differs: 6 `en` in the control against 3 `de` in `run-de`.

All 152 remaining English utterances in `run-de` are say-all text (organisations 73, differences 57,
sources 18, figures 4): English source titles, publishers and quotes on the German pages, as in M13
(Tasks 7 and 10).

## Cause

Orca takes the language of an object that has no text from AT-SPI's object locale. That locale
follows the process locale of the browser, not the page's `lang`. A German process locale makes it
`de_DE` for every object, and the German labels then get a German voice. M13's English voice was a
property of the run, and a reader whose system locale is German does not meet it. A reader whose
system is English and who reads the German edition may still hear these labels in an English voice;
that was not tested here and is not fixable from the page.

## Reproduce

```bash
localedef -i de_DE -f UTF-8 data/scratch-m14/locale/de_DE.UTF-8
uv run velometer app export --out data/scratch-m14/orca/export --base /velometer/ --clean
uv run --group dev python tools/orca_pass.py --site data/scratch-m14/orca/export \
    --base /velometer/ --editions de --locale de_DE.UTF-8 --locpath data/scratch-m14/locale \
    --out data/scratch-m14/orca/run-de
uv run --group dev python tools/orca_pass.py --site data/scratch-m14/orca/export \
    --base /velometer/ --editions de --out data/scratch-m14/orca/run-de-en
grep -o 'Reported locale.*' RUN/orca-debug.log | grep -o 'is [A-Za-z_]*$' | sort | uniq -c
```

Each run takes a few minutes. Raw output (`transcript.md`, `steps.json`, `orca-debug.log`) is
git-ignored scratch.
