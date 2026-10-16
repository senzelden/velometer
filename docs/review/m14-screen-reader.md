# M14 screen-reader pass: Orca under a German locale

**Verdict: confirmed. With a German process locale, the German accessible names are spoken in a
German voice.** All seven labels M13 R1 named got `lang: de`; in the control run (no locale) the
same run gave `lang: en` for six of them. The cause named in M13 R1 was right: the run's process
locale, not the markup. The site did not change in this task.

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
| Organisationen (nav label) | en (1, in say all); the 5 other mentions de | de (all 6) |
| Hauptkennzahl je Stadt und Stand. | en (2) | de (3) |
| Hauptkennzahl und Kennzahlvarianten. | en (1) | de (1) |

"Organisationen" also occurs in the load announcement "Finished loading velometer · Organisationen."
(no voice language in either run). The table-name count differs by one between runs because the
steps do not hit the same number of announcements each time.

Debug-log "Reported locale" lines, by the locale AT-SPI gave Orca:

| Run | de_DE | en_US | empty (names no object) | total |
|---|---|---|---|---|
| `run-de` | 426 | 0 | 1 | 427 |
| `run-de-en` | 0 | 428 | 1 | 429 |

Voice languages over all utterances: `run-de` de 1466, en 152, da 58, fr 15, sv 4, none 1076;
`run-de-en` de 1448, en 172, da 58, fr 15, sv 4, none 1076. The 20 fewer English utterances in
`run-de` are the labels above. The remaining English ones are the marked English quotes, titles and
publishers on the German pages (M13 Tasks 7 and 10).

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
