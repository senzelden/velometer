# velometer M7 Implementation Plan: the reader app, narratives and external sources

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the private app as the hybrid chosen in the M7 spike (navigation, city tabs,
Compare with Lines/Small multiples/Rank/Table and a slide-over, a scrolling Stories page), backed
by validated narratives whose quotes come only from external sources, plus a "Why the figures
differ" view and explanations for eight unexplained shifts.

**Architecture:** Narratives and sources are YAML content under `content/`, validated by Pydantic
models in a new `velometer.content` package; numbers in prose are declared facts recomputed from
the report data by `velometer content --check`. The FastAPI/Jinja app stays server-rendered and
read-only; a small vanilla-JS SVG chart module (tested with `node --test`) enhances pages from one
cached JSON endpoint.

**Tech Stack:** Python 3 / uv, FastAPI, Jinja2, Pydantic v2, typer, SQLite (read-only), vanilla
ES modules + SVG, Node's built-in test runner (no npm packages).

**Spec:** `docs/superpowers/specs/2026-10-06-velometer-m7-design.md` (read it first; section
numbers below refer to it). Reference screenshots: `docs/superpowers/specs/m7-reference/`.
Prototype code (behaviour/layout reference only, git-ignored): `.superpowers/m7-prototypes/`
(`option-a-atlas/`, `option-b-workbench/`, `option-c-story/`, `data.json`, `narratives/`).

## Global Constraints

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest` — from Task 9 on
  also `node --test src/velometer/app/static/js/tests/`. Network tests are `@pytest.mark.slow`.
- OSM lengths are **mapped km** (ADR 0006). Outside quotes, no construction verb for OSM figures:
  `built`, `constructed`, `opened`, `removed` (spec §2.14).
- Quotes come only from external sources in the registry; project documents are cited as data,
  never quoted (spec §2.2). Excerpts ≤ 60 words, verbatim, original language, with `gloss_en`
  when not English (spec §2.16). Full page texts are never committed.
- Never type OSM ids from memory; query them. No mapper uid/username anywhere. Never print, log or
  write credentials.
- No new runs: M7 never starts `velometer run` and never writes `velometer.sqlite`.
- The app stays on 127.0.0.1, read-only; no third-party scripts, styles or fonts; the only
  external host a page loads from is `tile.openstreetmap.org`.
- No npm packages, no `package.json`, no build step. JS is plain ES modules under
  `src/velometer/app/static/js/`.
- English only for narratives and new pages.
- Commits: explicit paths, one trailer line `Assisted-by: Claude:claude-opus-5-5`.

**Plan ruling (deviation from spec wording, recorded):** the registry is a directory
`content/sources/*.yaml` (one file per region) instead of one `content/sources.yaml`, so the four
research groups never edit the same file. The loader merges the files; ids are unique across them.

## Review Focus

1. A narrative cites a source or excerpt id that a later edit renamed → `content --check` names
   the narrative, the id and the file; the app never 500s on it (Task 3 test, Task 11 test).
2. A city with no narrative file, or Paris-like cities with no current run in the fixture → the
   Story tab shows "no narrative yet" / "no run" notes, never a 500 (Task 11 test).
3. A Compare URL edited by hand with unknown cities, an unknown metric, `mode=index` on a metric
   whose 2018 value is 0 or missing → unknown values are dropped to defaults, the index line is
   omitted with a note (Task 9 `parseState` test, Task 12 test).
4. JavaScript disabled → every page still shows its table, narrative text and sources (Task 10,
   11, 12, 13 no-JS tests).
5. A 390 px phone → no horizontal page scroll on any route; the filter UI becomes a sheet
   (Task 14 render check, Task 12 CSS assertion on the sheet class).

---

### Task 1: Content models and loaders

**Files:**
- Create: `src/velometer/content/__init__.py`, `src/velometer/content/models.py`,
  `src/velometer/content/loader.py`
- Create: `content/sources/README.md` (format, one paragraph), `content/narratives/.gitkeep`
- Test: `tests/test_content_models.py`

**Interfaces:**
- Produces:
  - `class ContentError(Exception)` (message names the file).
  - Models (all `extra="forbid", frozen=True`): `Excerpt(id, text, gloss_en: str|None, locator)`,
    `Source(id, publisher, title, url, published: date|None, accessed: date, language,
    kind: Literal["official","parliament","ngo","index","press"], archive_url: str|None,
    excerpts: list[Excerpt])`, `Quote(excerpt: str  # "<source_id>/<excerpt_id>", after: int)`,
    `Fact(id, expr, printed)`, `DataRef(id, label, file: str|None, locator: str|None,
    route: str|None)`, `Section(heading: str|None, step: str|None,
    role: Literal["story","figures"]="story", paragraphs: list[str])`,
    `Narrative(city_id, title, dek, sections: list[Section], quotes: list[Quote]=[],
    facts: list[Fact]=[], data_refs: list[DataRef]=[], literals: list[str]=[])` with property
    `paragraphs -> list[str]` (all sections, in order; `Quote.after` indexes this list),
    `Explainer(title, intro: list[str], sections: list[ExplainerSection], quotes, facts,
    data_refs, literals)`, `ExplainerSection(dimension, heading, paragraphs)`.
  - `load_sources(dir: Path) -> dict[str, Source]`, `load_narratives(dir: Path) ->
    dict[str, Narrative]` (file stem must equal `city_id`; `combined.yaml` has
    `city_id: combined`), `load_explainer(path: Path) -> Explainer | None` (None if absent).
  - `STORY_STEPS = ("all", "leaders", "tail", "growth", "jumps", "bezirke")` in `models.py`.

- [ ] **Step 1: Write the failing tests** in `tests/test_content_models.py`:

```python
from datetime import date
from pathlib import Path

import pytest
import yaml

from velometer.content.loader import load_explainer, load_narratives, load_sources
from velometer.content.models import ContentError, Narrative, Source

SRC = {
    "id": "berlin-drs-19-25987",
    "publisher": "Abgeordnetenhaus Berlin",
    "title": "Schriftliche Anfrage 19/25987",
    "url": "https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/SchrAnfr/S19-25987.pdf",
    "published": "2026-05-20",
    "accessed": "2026-10-06",
    "language": "de",
    "kind": "parliament",
    "excerpts": [{"id": "vorrangnetz-total", "text": "Insgesamt sind 78,2 km des "
                  "Radvorrangnetzes umgesetzt worden.", "gloss_en": "In total, 78.2 km of the "
                  "priority network have been implemented.", "locator": "Antwort zu 18"}],
}


def _write(d: Path, name: str, doc: dict) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(yaml.safe_dump(doc, allow_unicode=True))


def test_sources_load_and_merge_across_files(tmp_path):
    _write(tmp_path / "s", "de.yaml", {"sources": [SRC]})
    other = {**SRC, "id": "other", "excerpts": []}
    _write(tmp_path / "s", "fr.yaml", {"sources": [other]})
    got = load_sources(tmp_path / "s")
    assert set(got) == {"berlin-drs-19-25987", "other"}
    assert got["berlin-drs-19-25987"].published == date(2026, 5, 20)


def test_duplicate_source_id_across_files_is_an_error(tmp_path):
    _write(tmp_path / "s", "a.yaml", {"sources": [SRC]})
    _write(tmp_path / "s", "b.yaml", {"sources": [SRC]})
    with pytest.raises(ContentError, match="b.yaml.*berlin-drs-19-25987"):
        load_sources(tmp_path / "s")


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:8000/city/berlin", "file:///home/x/docs/reconciliation.md",
     "docs/reconciliation.md", "https://localhost/methodology"],
)
def test_internal_or_non_http_source_url_is_refused(url):
    with pytest.raises(ValueError, match="external"):
        Source.model_validate({**SRC, "url": url})


def test_excerpt_over_60_words_is_refused():
    long = " ".join(["Wort"] * 61)
    bad = {**SRC, "excerpts": [{"id": "x", "text": long, "locator": "p. 1"}]}
    with pytest.raises(ValueError, match="60 words"):
        Source.model_validate(bad)


def test_non_english_excerpt_needs_a_gloss():
    bad = {**SRC, "excerpts": [{"id": "x", "text": "Kurz.", "locator": "p. 1"}]}
    with pytest.raises(ValueError, match="gloss_en"):
        Source.model_validate(bad)


NARR = {
    "city_id": "berlin", "title": "Berlin", "dek": "One line.",
    "sections": [
        {"paragraphs": ["First 109.1 [#series]."]},
        {"role": "figures", "heading": "Figures", "paragraphs": ["Second [@berlin-drs-19-25987]."]},
    ],
    "quotes": [{"excerpt": "berlin-drs-19-25987/vorrangnetz-total", "after": 1}],
    "facts": [{"id": "h", "expr": "series.berlin.lau.current.headline", "printed": "109.1"}],
    "data_refs": [{"id": "series", "label": "velometer v4 run set", "route": "/city/berlin/time"}],
}


def test_narratives_load_by_file_stem(tmp_path):
    _write(tmp_path / "n", "berlin.yaml", NARR)
    got = load_narratives(tmp_path / "n")
    assert list(got) == ["berlin"] and got["berlin"].paragraphs[1].startswith("Second")


def test_narrative_file_stem_must_match_city_id(tmp_path):
    _write(tmp_path / "n", "paris.yaml", NARR)
    with pytest.raises(ContentError, match="paris.yaml.*berlin"):
        load_narratives(tmp_path / "n")


def test_quote_after_must_index_a_paragraph():
    with pytest.raises(ValueError, match="after"):
        Narrative.model_validate({**NARR, "quotes": [{"excerpt": "a/b", "after": 2}]})


def test_unknown_step_is_refused():
    bad = {**NARR, "sections": [{"step": "nope", "paragraphs": ["x"]}]}
    with pytest.raises(ValueError, match="step"):
        Narrative.model_validate(bad)


def test_missing_explainer_is_none(tmp_path):
    assert load_explainer(tmp_path / "explainer.yaml") is None
```

- [ ] **Step 2: Run** `uv run pytest tests/test_content_models.py -q` — expect ImportError.

- [ ] **Step 3: Implement** `models.py` and `loader.py`. Key rules:

```python
# models.py (core of the validators)
INTERNAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}
MAX_EXCERPT_WORDS = 60

class Source(_Strict):
    ...
    @field_validator("url", "archive_url")
    @classmethod
    def _external(cls, v):
        if v is None:
            return v
        u = urlparse(v)
        if u.scheme not in ("http", "https") or not u.hostname or u.hostname in INTERNAL_HOSTS:
            raise ValueError(f"source url must be an external http(s) URL, not {v!r}")
        return v

    @model_validator(mode="after")
    def _excerpts(self):
        ids = [e.id for e in self.excerpts]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate excerpt id in {self.id}")
        for e in self.excerpts:
            if len(e.text.split()) > MAX_EXCERPT_WORDS:
                raise ValueError(f"excerpt {self.id}/{e.id} has more than 60 words")
            if self.language != "en" and not e.gloss_en:
                raise ValueError(f"excerpt {self.id}/{e.id} needs gloss_en (language {self.language})")
        return self
```

`Narrative` validator: `0 <= q.after < len(self.paragraphs)` for each quote; each `Section.step`
is None or in `STORY_STEPS`; fact and data-ref ids unique. Loaders read YAML with
`yaml.safe_load`, wrap `OSError`, `yaml.YAMLError`, `ValidationError` into
`ContentError(f"{path}: {e}")`; `load_sources` iterates `sorted(dir.glob("*.yaml"))` and
reports a duplicate id with the second file's path and the id.

- [ ] **Step 4: Run** the tests — expect PASS. Then the gate.
- [ ] **Step 5: Commit** `feat(content): narrative and source models with loaders`.

---

### Task 2: The fact expression language

**Files:**
- Create: `src/velometer/content/facts.py`
- Test: `tests/test_content_facts.py` (uses the shared report fixture: `fixture_db` from
  `tests/conftest.py`, which yields `(db_path, cfg, conn, data)`; berlin has LAU and FUA history
  2024–2026 plus current, subareas only via `build_report_fixture_subareas`)

**Interfaces:**
- Consumes: `ReportData` (`series(city, kind) -> CitySeries|None` with `points: list[YearPoint]`
  (`label, headline, ab_km, tiers_km`), `subarea_series(city) -> dict[str, list[SubareaPoint]]`,
  `reconcile(city) -> CityReport|None` (`gaps: list[Gap]` with `comparison, ours, theirs,
  gap_pct`), `reported_figures(city) -> list[ExternalFigure]`, `cities()`), and
  `velometer.report.change.bezirk_table(text) -> str|None` for change pages.
- Produces:
  - `class FactError(Exception)`.
  - `evaluate(expr: str, data: ReportData, docs_dir: Path) -> float`.
  - `printed_matches(value: float, printed: str) -> bool`.
  - `parse_printed(printed: str) -> tuple[float, int]` (value, decimals).
  - `FAMILIES: tuple[str, ...]` (for error messages).

Grammar (dot-separated; `<kind>` is `lau|fua`; `<label>` is a year or `current`; `<field>` is
`headline | ab_km | A | B | C | D | E`):

| expr | value |
|---|---|
| `series.<city>.<kind>.<label>.<field>` | the YearPoint field (tiers from `tiers_km`) |
| `index.<city>.<kind>.<label>.<field>` | value ÷ value at the series' first year × 100 (FactError if the base is 0/missing) |
| `delta.<city>.<kind>.<from>.<to>.<field>` | value(to) − value(from) |
| `pct.<city>.<kind>.<from>.<to>.<field>` | (value(to) ÷ value(from) − 1) × 100 |
| `denominator.<city>.<kind>.<label>` | ab_km ÷ headline × 100 (main-road km) |
| `rank.<city>.<kind>.<label>.headline` | 1 = highest headline among all trusted cities with that label |
| `total.<kind>.<label>.ab_km` | sum of ab_km over trusted cities with that label |
| `bezirk.<city>.<subarea_id>.<label>.<field>` | SubareaPoint headline or tier km |
| `gap.<city>.<comparison>.<ours\|theirs\|gap_pct>` | from `reconcile(city).gaps` (gap_pct × 100, as the app prints it) |
| `figure.<city>.<source>.<metric_name>.<network_scope>` | ExternalFigure value |
| `population.<city>` | `City.population.value` |
| `change.<city>.<gained\|lost\|retiered\|redrawn\|geometry>` | the city row of the default-window change page's Bezirk table (`docs/review/<city>_change_<from>_<to>.md`, window from `data.report_config.change_window`) |

`printed_matches`: strip a leading `+`, map `−` (U+2212) to `-`, drop `,` thousands separators
and a trailing `%`; decimals = digits after `.`; match when `round(value, decimals) ==
parsed` (compare with `math.isclose(..., abs_tol=10**-(decimals+3))`).

- [ ] **Step 1: Failing tests** in `tests/test_content_facts.py`:

```python
import math
import pytest

from velometer.content.facts import FactError, evaluate, parse_printed, printed_matches


@pytest.mark.parametrize(
    "printed,value,ok",
    [("109.1", 109.1449, True), ("109.1", 109.16, False), ("1,551", 1550.7, True),
     ("+16%", 16.3, True), ("−4.6", -4.62, True), ("-4.6", -4.62, True), ("95", 95.4, True)],
)
def test_printed_matches(printed, value, ok):
    assert printed_matches(value, printed) is ok


def test_parse_printed_decimals():
    assert parse_printed("1,234.56") == (1234.56, 2)


def test_series_and_derived_families(fixture_db, tmp_path):
    _db, _cfg, _conn, data = fixture_db
    pts = {p.label: p for p in data.series("berlin", "lau").points}
    first = min(pts, key=lambda l: (l == "current", l))
    cur = pts["current"]
    assert evaluate("series.berlin.lau.current.ab_km", data, tmp_path) == cur.ab_km
    assert evaluate("series.berlin.lau.current.A", data, tmp_path) == cur.tiers_km["A"]
    assert math.isclose(
        evaluate("index.berlin.lau.current.ab_km", data, tmp_path),
        cur.ab_km / pts[first].ab_km * 100,
    )
    assert math.isclose(
        evaluate("denominator.berlin.lau.current", data, tmp_path),
        cur.ab_km / cur.headline * 100,
    )
    assert evaluate("rank.berlin.lau.2025.headline", data, tmp_path) in (1, 2)


@pytest.mark.parametrize(
    "expr",
    ["series.berlin.lau.1999.headline", "series.nowhere.lau.current.headline",
     "series.berlin.lau.current.F", "bogus.berlin", "series.berlin"],
)
def test_unknown_paths_raise(fixture_db, tmp_path, expr):
    _db, _cfg, _conn, data = fixture_db
    with pytest.raises(FactError, match=expr.split(".")[0]):
        evaluate(expr, data, tmp_path)
```

Add one test per remaining family against the fixture (`figure`, `gap`, `population`,
`total`, `delta`, `pct`; `bezirk` with `build_report_fixture_subareas`; `change` with a
change page written to `tmp_path/review/` in the format `tests/test_app.py::_change_markdown`
uses).

- [ ] **Step 2: Run** — expect ImportError.
- [ ] **Step 3: Implement** `facts.py` as a dispatch table `{family: handler}`; each handler
  validates its arity and raises `FactError(f"{expr}: <reason>")`.
- [ ] **Step 4: Run** tests + gate. **Step 5: Commit** `feat(content): fact expressions over the report data`.

---

### Task 3: `velometer content --check`

**Files:**
- Create: `src/velometer/content/check.py`
- Modify: `src/velometer/cli.py` (new top-level command `content`)
- Test: `tests/test_content_check.py`

**Interfaces:**
- Consumes: Task 1 loaders/models, Task 2 `evaluate`, `printed_matches`.
- Produces:
  - `check_content(content_dir: Path, data: ReportData, docs_dir: Path) -> list[str]` —
    problems, each `"<file>: <message>"`.
  - `undeclared_numbers(paragraph: str, allowed: set[str]) -> list[str]`.
  - `construction_verbs(paragraph: str) -> list[str]`.
  - `check_online(sources: dict[str, Source], fetch=...) -> list[str]` (fetch injectable).
  - CLI: `velometer content [--check] [--online] [--content content] [--db] [--config-dir]
    [--docs docs]`; without `--check` it prints `N narratives, M sources, K excerpts`.

Rules (spec §4.4), each a separate problem string:
1. Load errors (ContentError) → one problem, stop.
2. A quote's `excerpt` id not `<source>/<excerpt>` in the registry → `unknown excerpt`.
3. `[@id]` in a paragraph with no such source → `unknown source`; `[#id]` with no data_ref →
   `unknown data ref`.
4. A fact whose `evaluate` raises → `fact <id>: <error>`; whose value does not match `printed`
   → `fact <id>: <expr> is <value>, printed <printed>`.
5. Undeclared numbers: tokens `[+−-]?\d[\d,]*(?:\.\d+)?%?` after removing `[@…]`, `[#…]`,
   inline code and link targets; allowed = facts' `printed` (normalised as in
   `printed_matches`' parsing, compared as strings after normalisation) ∪ `literals` ∪ integers
   2000–2099 ∪ ordinals (`\d+(st|nd|rd|th)`).
6. Construction verbs outside quotes: `\b(built|constructed|opened|removed)\b`, case-insensitive.
7. Every trusted city (`data.cities()`) has `content/narratives/<id>.yaml`; `combined.yaml`
   exists; each city narrative has ≥ 1 section with `role: figures`; every `step` used in
   `combined.yaml` sections covers each of `STORY_STEPS` exactly once.
8. `content/explainer.yaml`: same rules 2–6, and one section per dimension id of
   `config/differences.yaml` (Task 4) — skip this rule if the file does not exist yet, but
   rule 7 requires it from Task 7 on: the check reports `missing explainer` once
   `content/narratives/combined.yaml` exists.

- [ ] **Step 1: Failing tests**: build a tmp `content/` with one valid source and one berlin
  narrative against the fixture DB (facts must match fixture values — compute them in the test
  via `evaluate` and write `printed` with `f"{v:.1f}"`), assert `check_content` returns `[]`
  for paris missing → exactly one `missing narrative: paris` problem. Then one red test per rule:

```python
@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda n: n["quotes"].__setitem__(0, {"excerpt": "src/nope", "after": 0}), "unknown excerpt"),
        (lambda n: n["sections"][0]["paragraphs"].__setitem__(0, "See [@ghost]."), "unknown source"),
        (lambda n: n["sections"][0]["paragraphs"].__setitem__(0, "It was 77.7 km."), "undeclared number 77.7"),
        (lambda n: n["sections"][0]["paragraphs"].__setitem__(0, "Berlin built paths."), "construction verb 'built'"),
        (lambda n: n["facts"][0].__setitem__("printed", "1.0"), "printed 1.0"),
        (lambda n: n["sections"].__setitem__(1, {"paragraphs": ["no figures role"]}), "no figures section"),
    ],
)
def test_each_rule_reports(...): ...
```

  Plus: a quote text present in a paragraph does not count as undeclared (quotes are not in
  paragraphs, so assert a German excerpt with "78,2" in the registry raises nothing); years and
  `literals` pass; `check_online` with a fake `fetch` returning page text without the excerpt
  reports `excerpt not found online`, and with the excerpt reports nothing (whitespace
  normalised). CLI test with `CliRunner`: exit 1 and problems on stderr; exit 0 prints `ok`.

- [ ] **Step 2–4:** run red, implement, run green, gate.
- [ ] **Step 5: Commit** `feat(content): content --check for quotes, facts, numbers and wording`.

---

### Task 4: Why the figures differ: config and rows

**Files:**
- Create: `config/differences.yaml`, `src/velometer/report/differences.py`
- Modify: `src/velometer/config.py` (`DifferencesConfig`, `load_differences(path)`)
- Test: `tests/test_differences.py`

**Interfaces:**
- Produces:
  - `DifferencesConfig(dimensions: list[Dimension(id, label)], metric_kinds: dict[str, str],
    source_methods: dict[str, str], length_bases: dict[str, str], labels: dict[str, str],
    areas: dict[str, str])`; dimension ids exactly
    `("scope", "kind", "length", "date", "area", "method")`.
  - `@dataclass(frozen=True) Driver(dimension: str, ours: str, theirs: str)`.
  - `@dataclass(frozen=True) DifferenceRow(source: str, metric: str, theirs: float, unit: str,
    ours: float | None, ours_label: str | None, gap_pct: float | None, reference_date:
    date | None, url: str | None, drivers: list[Driver])`.
  - `difference_rows(data: ReportData, city_id: str, cfg: DifferencesConfig) ->
    list[DifferenceRow]` — reconcile gaps first (ours/theirs/gap from `Gap`), then reported
    figures (`ours=None`), each with drivers where ours ≠ theirs on a dimension.

`config/differences.yaml` (complete, all metric names currently in `config/external/figures.csv`
and `config/reconcile.yaml` must be covered — the test asserts it):

```yaml
dimensions:
  - {id: scope, label: What is counted}
  - {id: kind, label: What kind of km}
  - {id: length, label: How length is measured}
  - {id: date, label: When}
  - {id: area, label: Where}
  - {id: method, label: Who measured}
ours:  # our side of each dimension
  scope: all mapped cycling infrastructure, tiers A–E (headline A+B)
  kind: mapped in OpenStreetMap at the snapshot date
  length: per road side
  area: city proper (LAU)
  method: OpenStreetMap, velometer classifier
metric_kinds:
  new_cycle_infra_km: completed in the year
  vorrangnetz_implemented_km: completed to date
  vorrangnetz_target_km: planned network
  radverkehrsnetz_completed_km: completed to date
  radverkehrsnetz_target_km: planned network
  radverkehrsnetz_completed_share_pct: share of the planned network completed
source_methods:
  clean_cities_2025: figures submitted by the city, OSM as fallback
  qecio_v2_10: OpenStreetMap, QECIO method
  bikenetkit_v1: OpenStreetMap, BikeNetKit method
  official: the administration's own records
  changing_cities: an NGO's count of completed projects
  mobilitaetsagentur_wien: the city's mobility agency
length_bases:
  streckenlaenge: route length (Streckenlänge)
  reallaenge: real length
  unknown: basis not stated by the source
areas:
  qecio_v2_10: NUTS3 region
  default: the city as the source defines it
```

(Implementer: list every `metric_name` and `source` that appears in `figures.csv` and the
reconcile comparisons; add any missing key with a plain-English value; never invent a definition
a source does not state — use "not stated by the source".)

- [ ] **Step 1: Failing tests**: config loads; every figures.csv metric/source and every
  reconcile comparison source has an entry (red-proof by deleting one key); on the fixture,
  `difference_rows(data, "berlin", cfg)` returns one row per gap plus one per reported figure;
  a reported figure with `length_basis="streckenlaenge"` gets a `length` driver
  `Driver("length", "per road side", "route length (Streckenlänge)")`; a QECIO gap gets an
  `area` driver; a row whose dimension equals ours has no driver for it.
- [ ] **Step 2–4**, gate. **Step 5: Commit** `feat(report): figure differences by dimension`.

---

### Task 5: External source research (four regions)

This task is research, not code. The controller dispatches **four researchers in parallel**, one
per region file (no shared file):

| file | cities |
|---|---|
| `content/sources/central.yaml` | berlin, vienna, prague, bratislava, budapest, ljubljana, wroclaw, warsaw, krakow |
| `content/sources/west.yaml` | paris, lyon, strasbourg, bordeaux, madrid, barcelona |
| `content/sources/north.yaml` | copenhagen, stockholm, oslo, helsinki, amsterdam, utrecht |
| `content/sources/cross.yaml` | Clean Cities 2025 report, QECIO v2.10/2.1 methodology (definitions), EU/ECF-level sources |

**Per researcher (brief):**
- For each city, look for: the city's cycling strategy/plan and its progress reports, the
  latest official network length figures and their definitions, parliamentary/council answers,
  and quality press on cycling infrastructure 2018–2026. Target 2–5 excerpts per city, at least
  one stating a definition or basis of a reported figure where one exists.
- Every excerpt is copied from the page you fetched (WebFetch), verbatim, ≤ 60 words, with
  `locator`, `accessed: 2026-10-06` (or the actual date), `published` if shown, `gloss_en` for
  non-English. Try `https://web.archive.org/save/` is NOT to be called (that publishes); instead
  look up an existing snapshot via `https://archive.org/wayback/available?url=<url>` and record
  it as `archive_url` when one exists.
- Never quote from memory, from a search-result snippet, or from a secondary paraphrase of a
  primary document you did not reach; if the primary is unreachable, quote the secondary and say
  so in `title` (e.g. "… (as reported by dpa)").
- Migrate the verbatim official quotes already in `config/external/figures.csv` `note` column
  (Berlin, Copenhagen, Vienna) into the registry (central/north files) as excerpts of their
  `source_url`, after re-fetching to confirm them; if a page is unreachable, keep the excerpt
  with `title` "… (not re-reached 2026-10-06)" and list it.
- Write `content/sources/<file>.yaml` (`sources: [...]`) and a research log
  `docs/review/m7-sources-<file>.md`: per city, sources searched, found, not reached (with
  reason). No mapper names. No credentials.
- Validate with `uv run python -c "from velometer.content.loader import load_sources;
  print(len(load_sources(__import__('pathlib').Path('content/sources'))))"`.

- [ ] **Step 1:** controller dispatches the four researchers (each writes only its two files).
- [ ] **Step 2:** controller runs `load_sources` (no ContentError) and the gate.
- [ ] **Step 3: Commit** per region: `content(m7): external sources, <region>`.

---

### Task 6: The eight shifts

**Files:**
- Create: `docs/review/shifts.md`
- Scratch only (never committed): `$TMPDIR/shift_*.py`

The eight shifts are listed in spec §6. For each, investigate from the cached snapshots under
`data/snapshots/` using `velometer.pipeline.classify.classify_ways` with
`load_classifier(config/classifier/v4.yaml)` and the run ids in `velometer.sqlite` (read-only:
`sqlite3.connect("file:velometer.sqlite?mode=ro", uri=True)`), the way `docs/review/m3_timeseries.md`
explanations were made: which ways/tags moved between the two snapshots, how many km, top tag
signatures, example way ids **taken from the data**. For the two denominator shifts (Warsaw,
Helsinki 2025) compare the main-road (`main_excl_motorway`) km of the two runs and the road
classes/ways behind the change.

`docs/review/shifts.md` format:

```markdown
# Unflagged shifts (M7)

Shifts in the v4 run set that no flag rule fires on, investigated for the narratives. Km are
mapped km per side (ADR 0006). Not read by `timeseries --check`.

### bratislava/lau/2020

Cause: **<campaign | tag drift | mapping activity | boundary | classifier | denominator | no cause found>**. <explanation with numbers, way examples, tag signatures>.
```

Headings: `bratislava/lau/2020`, `stockholm/lau/2018-current`, `budapest/lau/2024`,
`ljubljana/lau/current`, `amsterdam/lau/2025`, `copenhagen/lau/2025`, `warsaw/lau/2025`,
`helsinki/lau/2025`. The cause vocabulary is the M5 one (rulings R24–R26) plus `denominator`.

- [ ] **Step 1:** investigate each shift (scratch scripts); record numbers.
- [ ] **Step 2:** write `docs/review/shifts.md`; every number traceable to a query you ran.
- [ ] **Step 3: Commit** `docs(m7): explanations of eight unflagged shifts`.

---

### Task 7: Narratives and the explainer

**Files:**
- Create: `content/narratives/<city_id>.yaml` × 21, `content/narratives/combined.yaml`,
  `content/explainer.yaml`

**Brief (controller dispatches four drafters by the Task 5 regions, then one for combined +
explainer):**
- Start from the spike drafts in `.superpowers/m7-prototypes/narratives/<city>.json` for
  structure and findings, but rewrite into the Task 1 schema. **Remove every quote from project
  documents**; quotes now reference registry excerpts only. Internal material (explanations,
  shifts.md, reconciliation rows, the run set) is cited with `[#data_ref]`.
- Each city: `title`, `dek`, 130–220 words of story paragraphs on 2018 → current (LAU first,
  FUA where it differs), causes only where an explanation (`m3_timeseries.md`, `shifts.md`) or an
  external source supports them, and one `role: figures` section (60–120 words) on how the
  city's external figures relate to ours along the Task 4 dimensions, quoting the source's own
  definition where the registry has one. 0–3 quotes. Every number a declared fact (Task 2
  grammar) or a `literal` (counts like `12` Bezirke, `21` cities).
- `combined.yaml`: 600–900 words; sections each with a `step` covering all six `STORY_STEPS`
  (all, leaders, tail, growth, jumps, bezirke), plus a final figures section (`role: figures`);
  4–7 external quotes.
- `explainer.yaml`: one section per dimension of `config/differences.yaml`, each with a worked
  example from the 21 cities and, where available, the external source's own definition quoted.
- Run `uv run velometer content --check` until it exits 0.

- [ ] **Step 1:** four city drafters in parallel (one file set each), then combined + explainer.
- [ ] **Step 2:** `uv run velometer content --check` → exit 0; gate.
- [ ] **Step 3: Commit** `content(m7): city narratives, combined story and differences explainer`.

---

### Task 8: Review stop (user)

- [ ] **Step 1:** write `docs/review/m7-content-review.md`: per city the narrative (rendered as
  text with its quotes and sources), the source list with links, the shift findings, and the
  research logs' "not reached" lists; plus a short list of judgement calls.
- [ ] **Step 2:** commit it, then **stop and ask the user** for one verdict per item class
  (sources, shifts, narratives, explainer) with an AskUserQuestion batch. Apply requested
  changes (re-run `content --check`), commit, record the decision in
  `docs/superpowers/rulings-m7.md`.

---

### Task 9: The chart module and its tests

**Files:**
- Create: `src/velometer/app/static/js/chart-core.js` (pure functions),
  `src/velometer/app/static/js/chart.js` (DOM/SVG rendering),
  `src/velometer/app/static/js/state.js` (URL state),
  `src/velometer/app/static/js/tests/chart-core.test.mjs`,
  `src/velometer/app/static/js/tests/state.test.mjs`
- Modify: `CLAUDE.md` (gate line adds `&& node --test src/velometer/app/static/js/tests/`)

**Interfaces (ES module exports):**
- `chart-core.js`: `scaleLinear([d0,d1],[r0,r1]) -> (v)=>number`; `niceTicks(min, max, count=5)
  -> number[]`; `indexSeries(points: {label, value}[], baseLabel) -> {label, value|null}[]`
  (null everywhere if the base is missing or 0); `ranks(valuesByCity: Record<string, number|null>)
  -> Record<string, number|null>` (competition ranking, 1 = highest, ties share, nulls unranked);
  `placeLabels(items: {id, y}[], minGap, top, bottom) -> Record<id, y>` (order kept, no two
  closer than minGap, clamped to [top,bottom]); `assignColours(prev: Record<id,string>,
  highlighted: string[], palette: string[]) -> Record<id,string>` (kept colours stay, freed
  colours reused, max palette.length coloured); `xLabels(labels) -> string[]` (`current` →
  `Oct 2026` from a passed date).
- `state.js`: `DEFAULTS = {c: PILOT5, m: "headline", b: "lau", mode: "abs", view: "lines",
  hl: []}`; `parseState(search: string, known: {cities: string[], metrics: string[]}) -> state`
  (unknown cities/metrics/values dropped to defaults; `hl` ⊆ `c`, max 8); `serializeState(state)
  -> string` (omits defaults; stable key order).

- [ ] **Step 1: Failing tests** (`node:test` + `node:assert/strict`), e.g.:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { indexSeries, ranks, placeLabels, assignColours, niceTicks } from "../chart-core.js";

test("indexSeries: base 2018 = 100, missing base gives nulls", () => {
  assert.deepEqual(indexSeries([{label:"2018",value:50},{label:"2019",value:75}], "2018"),
    [{label:"2018",value:100},{label:"2019",value:150}]);
  assert.deepEqual(indexSeries([{label:"2018",value:0},{label:"2019",value:5}], "2018"),
    [{label:"2018",value:null},{label:"2019",value:null}]);
});
test("ranks: ties share, nulls unranked", () => {
  assert.deepEqual(ranks({a:3,b:5,c:5,d:null}), {b:1,c:1,a:3,d:null});
});
test("placeLabels keeps order and spacing within bounds", () => {
  const y = placeLabels([{id:"a",y:10},{id:"b",y:11},{id:"c",y:12}], 10, 0, 100);
  assert.ok(y.b - y.a >= 10 && y.c - y.b >= 10 && y.a >= 0 && y.c <= 100);
});
test("assignColours keeps existing colours when one city leaves", () => {
  const p = ["#1","#2","#3"];
  const a = assignColours({}, ["x","y","z"], p);
  const b = assignColours(a, ["x","z","w"], p);
  assert.equal(b.x, a.x); assert.equal(b.z, a.z); assert.equal(b.w, a.y);
});
test("niceTicks covers the range", () => {
  const t = niceTicks(3, 97, 5); assert.ok(t[0] <= 3 && t.at(-1) >= 97);
});
```

  and in `state.test.mjs`: round trip `serializeState(parseState(s)) === s` for a non-default
  state; unknown city `c=berlin,atlantis` → `["berlin"]`; `m=nope` → default; `hl` not in `c`
  dropped; more than 8 `hl` truncated; `mode=index` kept.
- [ ] **Step 2:** `node --test src/velometer/app/static/js/tests/` → fails (missing modules).
- [ ] **Step 3:** implement (port logic from the prototypes' `chart.js`/`charts.js`, rewritten
  as pure functions). `chart.js` exports `renderLines(el, model, opts)`,
  `renderSmallMultiples(el, model, opts)`, `renderRank(el, model, opts)`,
  `renderSparkline(el, points)`, `renderTiers(el, model)`; all build SVG with
  `document.createElementNS`, no innerHTML from data.
- [ ] **Step 4:** tests green; gate (with the new node step). **Step 5: Commit**
  `feat(app): SVG chart core with node:test suite`.

---

### Task 10: App foundation: layout, navigation, CSP, JSON endpoint, Overview, Cities

**Files:**
- Modify: `src/velometer/app/main.py`, `src/velometer/app/cache.py`, `src/velometer/cli.py`
  (`serve --content content`), `templates/base.html`, `templates/index.html`,
  `static/app.css`
- Create: `templates/cities.html`, `templates/_nav.html`, `static/js/nav.js`,
  `src/velometer/app/series.py` (`series_payload(data) -> dict`)
- Delete: `static/vendor/vega*.js`, `vega*.LICENSE` (update `static/vendor/VERSIONS`),
  the `vega` macro in `templates/macros.html`
- Test: `tests/test_app.py` (update), `tests/test_app_m7.py` (new)

**Interfaces:**
- `create_app(db_path, config_dir, maps_dir, docs_dir, content_dir: Path = Path("content"))`;
  `fingerprint(..., content_dir)` adds `("content", *_tree(content_dir))`.
- `series_payload(data) -> dict` with the spike `data.json` keys: `cities`, `series`
  (`"<id>/<kind>"` → list of `{label, run_id, osm, A..E, ab_km, headline, ecf_qecio,
  clean_cities, flags}`), `bezirke`, `presets`, `explanations.timeseries` (key → text from
  `ts.explanation`). Route `/data/series.json`, cached under `"series"`.
- CSP middleware: every response gets
  `Content-Security-Policy: default-src 'self'; img-src 'self' data: https://tile.openstreetmap.org; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`.
- Nav partial: `Overview · Compare · Cities ▾ · Stories · Methodology`, `aria-current="page"` on
  the active item; breadcrumbs block in `base.html`.

- [ ] **Step 1: Failing tests** (new file `tests/test_app_m7.py`, reuse `setup`/`_client` by
  importing from `tests.test_app`):
  - every route in `ROUTES + ["/cities", "/data/series.json"]` returns 200 and carries the CSP
    header exactly as above;
  - no template contains an inline `<script>` with a body (regex over rendered HTML of every
    route: `<script(?![^>]*\bsrc=)[^>]*>\s*\S`);
  - `/data/series.json` has keys `cities, series, bezirke, presets, explanations` and
    `series["berlin/lau"]` labels end with `current`;
  - `/` and `/cities` contain a link to every trusted city and the nav with
    `aria-current="page"` on the right item; `/cities` groups by country name;
  - no response references `/static/vendor/vega`;
  - the fingerprint changes when a file under `content/` changes.
- [ ] **Step 2:** red. **Step 3:** implement. Move existing inline scripts (tier map, change
  map, vega embeds) to static files reading their config from `data-*` attributes or a
  `<script type="application/json" id="...">` block (JSON blocks are not executed and are allowed
  under the CSP; the inline-script test ignores `type="application/json"`). Replace Vega charts on
  `/` with the new module (`static/js/overview.js` fetching `/data/series.json`) plus a server-side
  table fallback.
- [ ] **Step 4:** green + gate. **Step 5: Commit** `feat(app): navigation, CSP, series endpoint, overview and cities`.

---

### Task 11: City tabs, narrative rendering, Figures and the explainer

**Files:**
- Modify: `src/velometer/app/main.py`, `templates/city.html` → split into
  `templates/city/_header.html`, `story.html`, `time.html`, `tiers.html`, `figures.html`,
  `bezirke.html`; create `templates/differences.html`, `src/velometer/app/narrative.py`
  (`render_narrative(n, sources, data_refs_base) -> RenderedNarrative`)
- Create: `static/js/city.js`
- Test: `tests/test_app_m7.py`

**Interfaces:**
- Routes: `/city/<id>` (Story), `/city/<id>/time`, `/city/<id>/tiers`, `/city/<id>/figures`,
  `/city/<id>/bezirke` (404 when the city has no subareas), `/differences`; unknown tab → 404.
- `render_narrative` returns paragraphs as `Markup` with `[@id]` → `<sup><a href="#src-n">n</a></sup>`
  (numbered in first-use order), `[#id]` → `<sup><a href="#ref-n">n</a></sup>` in a separate
  "velometer data" list, quotes as `<figure class="pullquote"><blockquote lang="xx">text</blockquote>
  <figcaption>publisher, title, date · <a href=url>link</a> · gloss</figcaption></figure>` after
  their paragraph. All text escaped before markers are substituted (no raw HTML from content).
- Figures tab: the `difference_rows` table (Task 4) with drivers as a definition list per row,
  the narrative's `role: figures` section, the existing reconciliation and reported-figures
  tables, and the source list.

- [ ] **Step 1: Failing tests** with a tmp `content/` (one berlin narrative + one source):
  - `/city/berlin` shows the title, the quote inside `<blockquote lang="de">`, a citation link
    to `#src-1`, and the source's publisher and URL;
  - a paragraph containing `<script>` in content renders escaped;
  - `/city/paris` without a narrative shows `no narrative yet`;
  - a narrative citing an unknown excerpt renders without 500 and shows `source missing`;
  - `/city/berlin/bezirke` 200 on the subarea fixture, `/city/paris/bezirke` 404,
    `/city/berlin/nope` 404; tab nav marks the current tab;
  - `/city/berlin/figures` lists a `length` driver row for a `streckenlaenge` figure;
  - `/differences` renders one section per dimension when `content/explainer.yaml` exists, and a
    note otherwise;
  - no-JS: the Over time tab includes the yearly table and flagged-year explanations in HTML.
  - every tab has a "Compare this city with…" form (`<form action="/compare">` with a hidden
    `c=<id>` and a city `<select name="c">`, multiple) that works without JS;
  - the city header's key numbers sit in one `.keynums` row (CSS: horizontal scroll inside the
    row at ≤ 480 px, never the page).
- [ ] **Step 2–4.** **Step 5: Commit** `feat(app): city tabs, narratives, figures and the differences explainer`.

---

### Task 12: Compare and the slide-over

**Files:**
- Create: `templates/compare.html`, `templates/city/panel.html`, `static/js/compare.js`,
  `static/js/panel.js`
- Modify: `src/velometer/app/main.py`, `static/app.css`
- Test: `tests/test_app_m7.py`

**Interfaces:**
- `/compare?c=&m=&b=&mode=&view=&hl=` server-renders the filter form (a real `<form method=get>`
  that works without JS) and the Table view for the requested state, using the same defaults and
  validation as `state.js` (`src/velometer/app/compare.py: parse_compare(query, cities,
  metrics) -> CompareState`, mirrored by tests on both sides with the same cases).
- `/city/<id>/panel` returns a fragment (no `<html>`/nav) with key numbers, a tiers table, flagged
  years with explanations and a link to `/city/<id>`.
- Metrics: `headline, ab_km, A, B, C, D, E, ecf_qecio, clean_cities, ab_per_100k` (the last LAU
  only; with `b=fua` it is dropped to `headline` with a visible note).

- [ ] **Step 1: Failing tests:** default `/compare` lists the pilot 5 in the table; `?c=berlin,atlantis`
  shows only berlin; `?m=nope` falls back to headline; `?mode=index` with a city whose first-year
  value is 0 shows the note `no index: first year is 0 or missing`; `?b=fua&m=ab_per_100k`
  shows the fallback note; the filter sheet wrapper has class `filters-sheet`; `/city/berlin/panel`
  has no `<nav` and contains `/city/berlin`; the Python `parse_compare` and JS `parseState`
  share a cases table (`tests/compare_cases.json`, read by both suites).
- Quick sets (server and JS share `config/report.yaml`-independent constants in
  `src/velometer/app/compare.py: QUICK_SETS` and `static/js/state.js: QUICK_SETS`, asserted equal
  by a test reading both): `all`, `pilot5` = berlin, paris, vienna, copenhagen, wroclaw;
  `nordic` = copenhagen, stockholm, oslo, helsinki; `dach` = berlin, vienna; `west` = paris, lyon,
  strasbourg, bordeaux, madrid, barcelona, amsterdam, utrecht; `central` = wroclaw, warsaw,
  krakow, prague, bratislava, budapest, ljubljana.
- [ ] **Step 2–4.** JS: views Lines/Small multiples/Rank/Table switch without reload and update the
  URL (`history.replaceState`); clicking a line opens the panel (fetch the fragment), Escape and
  Back close it; colours via `assignColours`; flag markers open the explanation from
  `series.json`. **Step 5: Commit** `feat(app): compare views, filters and the city slide-over`.

---

### Task 13: Stories

**Files:**
- Create: `templates/stories.html`, `static/js/story.js`
- Modify: `src/velometer/app/main.py`, `static/app.css`
- Test: `tests/test_app_m7.py`

**Interfaces:** `/stories` renders `combined.yaml` sections in order, each `<section
data-step="…">` with its paragraphs, quotes and an "Explore this chart" link to `/compare?...`
for that step (a fixed map `STEP_COMPARE` in `main.py`: all → all cities headline; leaders → top 5
current; tail → bottom 5; growth → all, `mode=index`, `m=ab_km`; jumps → cities with flagged years;
bezirke → `/city/berlin/bezirke`). `story.js` uses IntersectionObserver to switch the sticky
chart; `prefers-reduced-motion` disables transitions.

- [ ] **Step 1: Failing tests:** one `data-step` per `STORY_STEPS`, in order; each section has an
  Explore link with the expected query; without `combined.yaml` the page shows `story not written
  yet`; the growth step's chart and text use the same metric (`ab_km`, indexed) — assert the
  Explore link has `m=ab_km&mode=index` (the spike's mismatch).
- [ ] **Step 2–4.** **Step 5: Commit** `feat(app): stories page with step-driven chart`.

---

### Task 14: Render check, docs, final

- [ ] **Step 1:** `uv run velometer serve --port 8791` (port 8000/8765 may be taken); screenshot
  every route for 4 cities (berlin, paris, ljubljana, stockholm) plus `/`, `/compare` (lines,
  small, rank, table; hover; panel open), `/cities`, `/stories`, `/differences` at 1280 and 390 px
  with a headless-Chrome CDP script in `$TMPDIR`; check: no horizontal scroll at 390 px, no
  console errors, network hosts only 127.0.0.1 and tile.openstreetmap.org. Look at every
  screenshot; fix defects in the owning code with a test.
- [ ] **Step 2:** docs: HANDOVER §9 M7 entry; `CLAUDE.md` latest-delivered line (M7, spec and
  `docs/superpowers/rulings-m7.md`) and gate; ADR 0008 M7 note (short quotations with attribution;
  no full texts); `docs/superpowers/rulings-m7.md` (rulings by task, follow-ups incl. the
  denominator flag idea and the M6 `foot` gap).
- [ ] **Step 3:** final gate and all checks: `timeseries --check`, `reconcile --check`,
  `trust check`, `report methodology --check`, `content --check`.
- [ ] **Step 4: Commit** `docs(m7): handover, rulings, ADR 0008 note`.
