# velometer M0 + M1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the project skeleton (uv package, config, SQLite schema, `velometer init`) and a data-driven way-side classifier. The classifier turns OSM ways into tiered lengths (A–E), main-road denominators and preset metrics, and is pinned by golden fixture tests.

**Architecture:** Pure-function pipeline: `read` (pyosmium) → `explode` (way → way-sides) → `classify` (ordered YAML rules) → `dedupe` (shapely flags) → `measure` (projected lengths, aggregates, presets). Config is YAML, validated by Pydantic. Only `read.py` touches pyosmium and only `db.py` touches SQLite.

**Tech Stack:** Python ≥3.12 (developed on 3.14), uv, hatchling, Typer, Pydantic v2, PyYAML, pyosmium (`osmium`), pyproj, shapely 2, pytest, ruff. Dev-only: httpx and matplotlib (golden scripts).

**Spec:** `docs/superpowers/specs/2026-10-01-velometer-m0-m1-design.md`. Also read `docs/adr/0002-*.md` and `docs/adr/0003-*.md`, which define tiers, length bases, road classes and presets.

## Global Constraints

- `requires-python = ">=3.12"`. Use the system Python 3.14 via `.python-version` = `3.14`.
- uv only (never pip/poetry), `src/` layout, hatchling, `[project.scripts] velometer = "velometer.cli:app"`.
- ruff `line-length = 100`. The gate is `uv run ruff format --check . && uv run ruff check . && uv run pytest`.
- pytest: `addopts = "-m 'not slow'"`, with the `slow` marker registered. **No network in the default test pass.**
- Lengths are always computed in the projected CRS `EPSG:<city epsg>`, never in degrees.
- Classifier rules live in `config/classifier/v1.yaml`, not in code. Code only implements the rule *engine*.
- Commits: stage explicit paths (never `git add -A`). End each message with exactly one trailer line `Assisted-by: Claude:claude-opus-5-5`. No `Co-Authored-By`.
- Never write OSM IDs (relations, ways) from memory. Query them.
- Tag-value semantics everywhere: a tag value is split on `;` and stripped, and a condition holds if **any** part matches.

## Review Focus

1. **Ways with unresolvable nodes** (clipped extracts reference nodes outside the file). They must be skipped and counted, not crash the run. Pinned in Task 3.
2. **Multi-valued tags** (`cycleway:right:separation=kerb;parking_lane`, ` track` with whitespace). They must match by any part. Pinned in Task 5.
3. **Unknown cycleway values** (`cycleway:right=crossing`). The result is tier `None` with `attrs["unknown_value"]`, counted, never a crash and never silently tiered. Pinned in Task 5.
4. **Degenerate geometry** (a way with two identical nodes, length 0). No ZeroDivisionError in dedupe share computations. Pinned in Task 6.
5. **Empty denominator** (an area with no main roads). The metric value is `None`, not a ZeroDivisionError or inf. Pinned in Task 7.
6. **YAML 1.1 booleans:** `segregated: yes` in rule YAML parses as Python `True` and must still match the OSM tag value `"yes"`. Pinned in Task 5.

---

## File map

| File | Responsibility |
|---|---|
| `pyproject.toml`, `.python-version`, `CLAUDE.md`, `LICENSE` | project setup |
| `config/cities.yaml` | 5 pilot cities |
| `config/classifier/v1.yaml` | road classes, value lists, ordered rules |
| `config/presets.yaml` | ours_headline, ecf_qecio, clean_cities_2025 |
| `src/velometer/config.py` | YAML → Pydantic config models, `ConfigError` |
| `src/velometer/models.py` | persisted Pydantic models (handover §7 + ADR additions) |
| `src/velometer/db.py` | SQLite schema and repository functions |
| `src/velometer/cli.py` | Typer app: `init`, `classify` |
| `src/velometer/pipeline/types.py` | frozen dataclasses: WayRecord, WaySide, Classified, DuplicateFlag, DualPair |
| `src/velometer/pipeline/match.py` | rule match-expression evaluator and validator |
| `src/velometer/pipeline/read.py` | pyosmium reader |
| `src/velometer/pipeline/explode.py` | way → way-sides |
| `src/velometer/pipeline/classify.py` | rule engine |
| `src/velometer/pipeline/geometry.py` | projector and length helpers |
| `src/velometer/pipeline/dedupe.py` | parallel-duplicate and dual-carriageway detection |
| `src/velometer/pipeline/measure.py` | aggregation, road lengths, preset metrics |
| `tests/fixtures/cases/*.osm`, `tests/fixtures/expected.yaml` | golden classifier cases |
| `scripts/fetch_berlin_golden.py`, `scripts/render_golden_review.py` | one-off Berlin golden set and review sheet |

---

### Task 1: Project scaffold and config loading

**Files:**
- Create: `pyproject.toml`, `.python-version`, `CLAUDE.md`, `LICENSE`, `src/velometer/__init__.py`, `src/velometer/config.py`, `src/velometer/pipeline/__init__.py`, `src/velometer/pipeline/match.py`, `config/cities.yaml`, `config/presets.yaml`, `config/classifier/v1.yaml` (skeleton: road classes and value lists, `rules: []`)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `velometer.config.ConfigError(Exception)`
  - `CityConfig`, `RoadClasses`, `Rule`, `ClassifierConfig`, `Preset`
  - `default_config_dir() -> Path`
  - `load_cities(path: Path) -> list[CityConfig]`
  - `load_classifier(path: Path) -> ClassifierConfig`
  - `load_presets(path: Path) -> list[Preset]`
  - `velometer.pipeline.match.matches(expr: dict, tags: Mapping[str, str], lists: Mapping[str, list[str]]) -> bool`
  - `validate_expr(expr: dict, lists: Mapping[str, list[str]]) -> None` (raises `ValueError`)

- [ ] **Step 1: Write `pyproject.toml`, `.python-version`, `LICENSE`, `CLAUDE.md`**

```toml
[project]
name = "velometer"
version = "0.1.0"
description = "Reproducible OSM measurement of protected cycling infrastructure in European cities"
readme = "HANDOVER.md"
license = "MIT"
requires-python = ">=3.12"
dependencies = [
  "osmium>=4.0",
  "pydantic>=2.7",
  "typer>=0.12",
  "pyyaml>=6.0",
  "pyproj>=3.6",
  "shapely>=2.0",
]

[project.scripts]
velometer = "velometer.cli:app"

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "httpx>=0.27", "matplotlib>=3.9"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/velometer"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-m 'not slow'"
markers = ["slow: needs network or large data; deselected by default"]
```

`.python-version` contains `3.14`. `LICENSE` is the standard MIT text, `Copyright (c) 2026 DS`, followed by a paragraph: "Data derived from OpenStreetMap is © OpenStreetMap contributors and licensed under ODbL 1.0 (see docs/adr/0008-licences.md)."

`CLAUDE.md`:

```markdown
# velometer

Read `HANDOVER.md` (project brief) and `docs/adr/` (locked decisions) before changing behaviour.
Current scope: `docs/superpowers/specs/2026-10-01-velometer-m0-m1-design.md`.

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest`
- Network tests are `@pytest.mark.slow` and deselected by default.
- Classifier rules are data in `config/classifier/vN.yaml`; a rule change is a new version.
- Lengths only in the city's projected EPSG. OSM km are "mapped km" (ADR 0006).
- Never type OSM ids from memory; query them.
```

Run: `uv sync`
Expected: creates `.venv`, installs deps, exit 0.

- [ ] **Step 2: Look up the OSM relation IDs (network, once)**

For each pilot city, run (the host is `nominatim.openstreetmap.org`; send a User-Agent):

```bash
curl -s -A "velometer/0.1 (research)" "https://nominatim.openstreetmap.org/search?city=Berlin&country=Germany&format=jsonv2&limit=3" | python3 -m json.tool | grep -E '"(osm_type|osm_id|display_name|addresstype)"'
```

Repeat for `city=Paris&country=France`, `city=Wien&country=Austria`, `city=København&country=Denmark` and `city=Wrocław&country=Poland`. Take the `osm_type: relation` result whose `addresstype` is city or state (Berlin). Record each ID together with the query in a YAML comment.

- [ ] **Step 3: Write `config/cities.yaml` and `config/presets.yaml`**

```yaml
# Pilot cities (handover §9). osm_relation_id values were looked up via Nominatim on 2026-10-01;
# query: https://nominatim.openstreetmap.org/search?city=<name>&country=<country>&format=jsonv2
# lau_code / fua_code are filled in M2 (GISCO). EPSG = ETRS89 / UTM zone of the city.
cities:
  - id: berlin
    name: Berlin
    country_iso2: DE
    epsg: 25833
    geofabrik_region: europe/germany/berlin
    osm_relation_id: <value from step 2>
  - id: paris
    name: Paris
    country_iso2: FR
    epsg: 25831
    geofabrik_region: europe/france/ile-de-france
    osm_relation_id: <value from step 2>
  - id: vienna
    name: Wien
    country_iso2: AT
    epsg: 25833
    geofabrik_region: europe/austria
    osm_relation_id: <value from step 2>
  - id: copenhagen
    name: København
    country_iso2: DK
    epsg: 25832
    geofabrik_region: europe/denmark
    osm_relation_id: <value from step 2>
  - id: wroclaw
    name: Wrocław
    country_iso2: PL
    epsg: 25833
    geofabrik_region: europe/poland/dolnoslaskie
    osm_relation_id: <value from step 2>
```

(Replace each `<value from step 2>` with the integer you looked up. Don't commit with the marker still in place; the config test rejects non-integers.)

```yaml
# Presets (ADR 0003). tiers: "X" = all subtypes of tier X; "X/sub" = only that subtype.
presets:
  - id: ours_headline
    tiers: [A, B]
    basis: per_side
    denominator: main_excl_motorway
  - id: ecf_qecio
    tiers: [A, B, C, D]
    basis: qecio_weighted
    denominator: main_incl_motorway_raw
  - id: clean_cities_2025
    tiers: [A, B]
    basis: per_side
    denominator: all_public
```

- [ ] **Step 4: Write the skeleton `config/classifier/v1.yaml`** (Task 5 fills in `rules`)

```yaml
version: v1
road_classes:
  # highways whose cycleway side tags are exploded into left/right sides
  carriageway: [motorway, motorway_link, trunk, trunk_link, primary, primary_link, secondary,
                secondary_link, tertiary, tertiary_link, unclassified, residential, living_street,
                service, road, busway]
  # denominators (ADR 0003)
  main: [trunk, trunk_link, primary, primary_link, secondary, secondary_link, tertiary,
         tertiary_link]
  motorway: [motorway, motorway_link]
  local: [unclassified, residential, living_street, pedestrian]
value_lists:
  physical_separation: [kerb, separation_kerb, bollard, flex_post, vertical_panel, planter,
                        parking_lane, fence, guard_rail, jersey_barrier, grass_verge, tree_row,
                        bump, studs, barrier, hedge, ditch, wall, railing]
  paint_separation: [solid_line, dashed_line, double_solid_line, no, none]
  bicycle_allowed: [yes, designated, permissive]
rules: []
```

- [ ] **Step 5: Write the failing tests `tests/test_config.py`**

```python
from pathlib import Path

import pytest
import yaml

from velometer.config import (
    ConfigError,
    default_config_dir,
    load_cities,
    load_classifier,
    load_presets,
)
from velometer.pipeline.match import matches, validate_expr

CFG = default_config_dir()


def test_pilot_cities_load_with_projected_epsg_and_integer_relations():
    cities = load_cities(CFG / "cities.yaml")
    assert {c.id for c in cities} == {"berlin", "paris", "vienna", "copenhagen", "wroclaw"}
    assert all(isinstance(c.osm_relation_id, int) and c.osm_relation_id > 0 for c in cities)


def test_geographic_epsg_is_rejected(tmp_path: Path):
    bad = tmp_path / "cities.yaml"
    bad.write_text(
        "cities:\n  - {id: x, name: X, country_iso2: DE, epsg: 4326,"
        " geofabrik_region: europe/x, osm_relation_id: 1}\n"
    )
    with pytest.raises(ConfigError, match="cities.yaml"):
        load_cities(bad)


def test_presets_reference_known_denominators():
    presets = load_presets(CFG / "presets.yaml")
    assert {p.id for p in presets} == {"ours_headline", "ecf_qecio", "clean_cities_2025"}


def _classifier_with_rules(tmp_path: Path, rules: list[dict]) -> Path:
    data = yaml.safe_load((CFG / "classifier" / "v1.yaml").read_text())
    data["rules"] = rules
    p = tmp_path / "v1.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_shipped_classifier_loads():
    assert load_classifier(CFG / "classifier" / "v1.yaml").version == "v1"


def test_duplicate_rule_ids_rejected(tmp_path: Path):
    rule = {"id": "r", "applies_to": "standalone", "tier": "A", "match": {"highway": "cycleway"}}
    with pytest.raises(ConfigError, match="duplicate rule id"):
        load_classifier(_classifier_with_rules(tmp_path, [rule, rule]))


def test_unknown_value_list_rejected(tmp_path: Path):
    rule = {"id": "r", "applies_to": "road_side", "tier": "C",
            "match": {"cycleway:separation": {"in_list": "nope"}}}
    with pytest.raises(ConfigError, match="nope"):
        load_classifier(_classifier_with_rules(tmp_path, [rule]))


LISTS = {"phys": ["kerb", "bollard"]}


@pytest.mark.parametrize(
    ("expr", "tags", "expected"),
    [
        ({"highway": "cycleway"}, {"highway": "cycleway"}, True),
        ({"highway": ["path", "footway"]}, {"highway": "cycleway"}, False),
        ({"foot": {"absent": True}}, {}, True),
        ({"foot": {"absent": True}}, {"foot": "yes"}, False),
        ({"foot": {"not_in": ["designated"]}}, {}, True),
        ({"foot": {"not_in": ["designated"]}}, {"foot": "designated"}, False),
        ({"sep": {"in_list": "phys"}}, {"sep": "solid_line;kerb"}, True),
        ({"sep": {"in_list": "phys"}}, {"sep": " kerb "}, True),
        ({"sep": {"in_list": "phys"}}, {"sep": "solid_line"}, False),
        ({"segregated": True}, {"segregated": "yes"}, True),  # YAML 1.1 `yes` -> True
        ({"segregated": False}, {"segregated": "no"}, True),
        ({"any": [{"a": "1"}, {"b": "1"}]}, {"b": "1"}, True),
        ({"all": [{"a": "1"}, {"b": "1"}]}, {"b": "1"}, False),
        ({"not": {"a": "1"}}, {"a": "2"}, True),
        ({"highway": "cycleway", "foot": "designated"}, {"highway": "cycleway"}, False),
    ],
)
def test_match_semantics(expr, tags, expected):
    assert matches(expr, tags, LISTS) is expected


def test_validate_expr_rejects_unknown_operator():
    with pytest.raises(ValueError, match="unknown condition"):
        validate_expr({"a": {"regex": "x"}}, LISTS)
```

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'velometer.config'`.

- [ ] **Step 6: Implement `src/velometer/pipeline/match.py`**

```python
"""Evaluator for classifier rule match expressions (spec §4, classify.py grammar)."""

from collections.abc import Mapping
from typing import Any

_BOOL = {True: "yes", False: "no"}
_OPERATORS = {"all", "any", "not"}


def _norm(value: Any) -> str:
    # PyYAML (YAML 1.1) turns `yes`/`no` into booleans; OSM values are strings.
    if isinstance(value, bool):
        return _BOOL[value]
    return str(value)


def _parts(tags: Mapping[str, str], key: str) -> set[str]:
    raw = tags.get(key)
    if raw is None:
        return set()
    return {p.strip() for p in raw.split(";") if p.strip()}


def _check(parts: set[str], cond: Any, lists: Mapping[str, list[str]]) -> bool:
    if isinstance(cond, dict):
        if "absent" in cond:
            return not parts if cond["absent"] else bool(parts)
        if "not_in" in cond:
            return not parts & {_norm(v) for v in cond["not_in"]}
        if "in_list" in cond:
            return bool(parts & {_norm(v) for v in lists[cond["in_list"]]})
        raise ValueError(f"unknown condition {cond!r}")
    allowed = {_norm(v) for v in cond} if isinstance(cond, list) else {_norm(cond)}
    return bool(parts & allowed)


def matches(expr: dict, tags: Mapping[str, str], lists: Mapping[str, list[str]]) -> bool:
    """True if every entry of `expr` holds. Keys are `all`/`any`/`not` or tag keys."""
    for key, cond in expr.items():
        if key == "all":
            ok = all(matches(e, tags, lists) for e in cond)
        elif key == "any":
            ok = any(matches(e, tags, lists) for e in cond)
        elif key == "not":
            ok = not matches(cond, tags, lists)
        else:
            ok = _check(_parts(tags, key), cond, lists)
        if not ok:
            return False
    return True


def validate_expr(expr: dict, lists: Mapping[str, list[str]]) -> None:
    """Raise ValueError if `expr` uses an unknown operator, condition or value list."""
    if not isinstance(expr, dict) or not expr:
        raise ValueError(f"match expression must be a non-empty mapping, got {expr!r}")
    for key, cond in expr.items():
        if key in ("all", "any"):
            if not isinstance(cond, list) or not cond:
                raise ValueError(f"{key} needs a non-empty list")
            for e in cond:
                validate_expr(e, lists)
        elif key == "not":
            validate_expr(cond, lists)
        elif isinstance(cond, dict):
            if set(cond) not in ({"absent"}, {"not_in"}, {"in_list"}):
                raise ValueError(f"unknown condition {cond!r} for key {key!r}")
            if "in_list" in cond and cond["in_list"] not in lists:
                raise ValueError(f"unknown value list {cond['in_list']!r}")
        elif not isinstance(cond, (str, bool, int, float, list)):
            raise ValueError(f"unsupported condition {cond!r} for key {key!r}")
```

- [ ] **Step 7: Implement `src/velometer/config.py`**

```python
"""Load and validate YAML configuration (cities, classifier, presets)."""

import os
from pathlib import Path
from typing import Any, Literal

import pyproj
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from velometer.pipeline.match import validate_expr

Tier = Literal["A", "B", "C", "D", "E", "excluded"]
Basis = Literal["per_side", "qecio_weighted"]
RoadClass = Literal["main_excl_motorway", "main_incl_motorway", "main_incl_motorway_raw", "all_public"]


class ConfigError(Exception):
    """A configuration file is missing or invalid; the message names the file."""


def default_config_dir() -> Path:
    env = os.environ.get("VELOMETER_CONFIG_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "config"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CityConfig(_Strict):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    country_iso2: str = Field(pattern=r"^[A-Z]{2}$")
    epsg: int
    geofabrik_region: str
    osm_relation_id: int = Field(gt=0)
    lau_code: str | None = None
    fua_code: str | None = None

    @field_validator("epsg")
    @classmethod
    def _projected(cls, v: int) -> int:
        if not pyproj.CRS.from_epsg(v).is_projected:
            raise ValueError(f"EPSG:{v} is not a projected CRS")
        return v


class RoadClasses(_Strict):
    carriageway: list[str]
    main: list[str]
    motorway: list[str]
    local: list[str]


class Rule(_Strict):
    id: str
    applies_to: Literal["road_side", "standalone", "any"]
    tier: Tier
    subtype: str | None = None
    match: dict[str, Any]
    attrs: dict[str, bool | str] = {}


class ClassifierConfig(_Strict):
    version: str
    road_classes: RoadClasses
    value_lists: dict[str, list[str]]
    rules: list[Rule]

    @model_validator(mode="after")
    def _check_rules(self) -> "ClassifierConfig":
        seen: set[str] = set()
        for rule in self.rules:
            if rule.id in seen:
                raise ValueError(f"duplicate rule id {rule.id!r}")
            seen.add(rule.id)
            try:
                validate_expr(rule.match, self.value_lists)
            except ValueError as e:
                raise ValueError(f"rule {rule.id!r}: {e}") from e
        return self


class Preset(_Strict):
    id: str
    tiers: list[str]
    basis: Basis
    denominator: RoadClass


def _read(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError(f"{path}: {e}") from e


def _parse(path: Path, fn):
    try:
        return fn(_read(path))
    except (ValidationError, ValueError, KeyError, TypeError) as e:
        raise ConfigError(f"{path}: {e}") from e


def load_cities(path: Path) -> list[CityConfig]:
    return _parse(path, lambda d: [CityConfig.model_validate(c) for c in d["cities"]])


def load_classifier(path: Path) -> ClassifierConfig:
    return _parse(path, ClassifierConfig.model_validate)


def load_presets(path: Path) -> list[Preset]:
    return _parse(path, lambda d: [Preset.model_validate(p) for p in d["presets"]])
```

Create `src/velometer/__init__.py` containing only `"""velometer: protected cycling infrastructure from OSM."""`, and `src/velometer/pipeline/__init__.py` containing only `"""Pure-function OSM classification pipeline."""`.

- [ ] **Step 8: Run the tests and the gate**

Run: `uv run pytest tests/test_config.py -v && uv run ruff format . && uv run ruff check .`
Expected: all PASS, ruff clean.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock .python-version LICENSE CLAUDE.md config src tests/test_config.py
git commit -m "feat: project scaffold, YAML config loading and rule matcher

Assisted-by: Claude:claude-opus-5-5"
```

---

### Task 2: Persisted models, SQLite schema, `velometer init`

**Files:**
- Create: `src/velometer/models.py`, `src/velometer/db.py`, `src/velometer/cli.py`
- Test: `tests/test_db.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_cities`, `default_config_dir`, `CityConfig` (Task 1).
- Produces:
  - `velometer.models`: `City`, `Boundary`, `Run`, `TierLength`, `RoadLength`, `Metric`, `Completeness`, `ExternalFigure`, `Duplicate` (Pydantic).
  - `velometer.db`: `connect(path: Path) -> sqlite3.Connection`, `create_schema(conn) -> None`, `upsert_cities(conn, cities: list[CityConfig]) -> int`, `fetch_cities(conn) -> list[City]`, `SCHEMA_VERSION: int`.
  - `velometer.cli.app` (a Typer app with an `init` command; Task 7 adds `classify`).

- [ ] **Step 1: Write the failing tests**

`tests/test_db.py`:

```python
import sqlite3

import pytest

from velometer.config import default_config_dir, load_cities
from velometer.db import SCHEMA_VERSION, connect, create_schema, fetch_cities, upsert_cities

TABLES = {
    "cities", "boundaries", "runs", "tier_lengths", "road_lengths", "metrics",
    "completeness", "external_figures", "duplicates",
}


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def test_schema_has_all_tables_and_version(tmp_path):
    conn = connect(tmp_path / "v.sqlite")
    create_schema(conn)
    assert TABLES <= _tables(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_create_schema_and_upsert_are_idempotent(tmp_path):
    conn = connect(tmp_path / "v.sqlite")
    cities = load_cities(default_config_dir() / "cities.yaml")
    for _ in range(2):
        create_schema(conn)
        upsert_cities(conn, cities)
    assert sorted(c.id for c in fetch_cities(conn)) == sorted(c.id for c in cities)


def test_upsert_updates_changed_fields(tmp_path):
    conn = connect(tmp_path / "v.sqlite")
    create_schema(conn)
    cities = load_cities(default_config_dir() / "cities.yaml")
    upsert_cities(conn, cities)
    changed = [cities[0].model_copy(update={"lau_code": "DE_11000000"})]
    upsert_cities(conn, changed)
    berlin = next(c for c in fetch_cities(conn) if c.id == cities[0].id)
    assert berlin.lau_code == "DE_11000000"


def test_tier_lengths_reject_unknown_basis(tmp_path):
    conn = connect(tmp_path / "v.sqlite")
    create_schema(conn)
    conn.execute("INSERT INTO runs (id, started_at, classifier_version, git_commit,"
                 " osm_timestamp, boundary_kind, status) VALUES (1, 't', 'v1', 'c', 't',"
                 " 'lau', 'done')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO tier_lengths (run_id, city_id, tier, subtype, length_basis,"
                     " length_km, n_ways) VALUES (1, 'berlin', 'A', NULL, 'lane', 1.0, 1)")
```

`tests/test_cli.py`:

```python
from typer.testing import CliRunner

from velometer.cli import app
from velometer.db import connect, fetch_cities


def test_init_creates_db_with_cities_and_is_idempotent(tmp_path):
    db = tmp_path / "v.sqlite"
    runner = CliRunner()
    for _ in range(2):
        result = runner.invoke(app, ["init", "--db", str(db)])
        assert result.exit_code == 0, result.output
    assert len(fetch_cities(connect(db))) == 5
    assert "5 cities" in result.output
```

Run: `uv run pytest tests/test_db.py tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'velometer.db'`.

- [ ] **Step 2: Implement `src/velometer/models.py`**

```python
"""Persisted records (handover §7, with ADR 0002/0003 additions). Mirrored in db.py."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from velometer.config import Basis, RoadClass


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Population(_Model):
    value: int
    year: int
    source: str


class City(_Model):
    id: str
    name: str
    country_iso2: str
    lau_code: str | None = None
    fua_code: str | None = None
    osm_relation_id: int
    epsg: int
    geofabrik_region: str
    population: Population | None = None


class Boundary(_Model):
    city_id: str
    kind: Literal["lau", "fua", "osm_admin"]
    source: str
    source_version: str
    area_km2: float
    path: str
    sha256: str


class Run(_Model):
    id: int | None = None
    started_at: datetime
    classifier_version: str
    git_commit: str
    osm_timestamp: str
    boundary_kind: Literal["lau", "fua", "osm_admin", "none"]
    status: Literal["running", "done", "failed"]


class TierLength(_Model):
    run_id: int | None = None
    city_id: str | None = None
    tier: Literal["A", "B", "C", "D", "E", "excluded"]
    subtype: str | None = None
    length_basis: Basis
    length_km: float
    n_ways: int


class RoadLength(_Model):
    run_id: int | None = None
    city_id: str | None = None
    road_class: RoadClass
    length_km: float


class Metric(_Model):
    run_id: int | None = None
    city_id: str | None = None
    preset: str
    length_basis: Basis
    value: float | None
    numerator_km: float
    denominator_km: float


class Completeness(_Model):
    run_id: int
    city_id: str
    tier: str
    share_with_width: float
    share_with_surface: float
    share_with_segregated: float


class ExternalFigure(_Model):
    city_id: str
    source: str
    metric_name: str
    value: float
    unit: str
    reference_date: date | None
    network_scope: str
    length_basis: Literal["streckenlaenge", "reallaenge", "unknown"]
    source_url: str
    retrieved_at: date
    note: str = ""


class Duplicate(_Model):
    run_id: int | None = None
    kind: Literal["parallel", "dual_carriageway"]
    way_id_separate: int
    way_id_road: int
    side: str | None
    overlap_share: float
    distance_m: float
    resolved: bool = False
```

- [ ] **Step 3: Implement `src/velometer/db.py`**

```python
"""SQLite schema and repository functions (ADR 0007: SQLite is canonical)."""

import sqlite3
from pathlib import Path

from velometer.config import CityConfig
from velometer.models import City, Population

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cities (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, country_iso2 TEXT NOT NULL,
  lau_code TEXT, fua_code TEXT, osm_relation_id INTEGER NOT NULL, epsg INTEGER NOT NULL,
  geofabrik_region TEXT NOT NULL,
  population_value INTEGER, population_year INTEGER, population_source TEXT
);
CREATE TABLE IF NOT EXISTS boundaries (
  city_id TEXT NOT NULL REFERENCES cities(id),
  kind TEXT NOT NULL CHECK (kind IN ('lau','fua','osm_admin')),
  source TEXT NOT NULL, source_version TEXT NOT NULL, area_km2 REAL NOT NULL,
  path TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY (city_id, kind)
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, classifier_version TEXT NOT NULL,
  git_commit TEXT NOT NULL, osm_timestamp TEXT NOT NULL,
  boundary_kind TEXT NOT NULL CHECK (boundary_kind IN ('lau','fua','osm_admin','none')),
  status TEXT NOT NULL CHECK (status IN ('running','done','failed'))
);
CREATE TABLE IF NOT EXISTS tier_lengths (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL,
  tier TEXT NOT NULL CHECK (tier IN ('A','B','C','D','E','excluded')), subtype TEXT,
  length_basis TEXT NOT NULL CHECK (length_basis IN ('per_side','qecio_weighted')),
  length_km REAL NOT NULL, n_ways INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS road_lengths (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL,
  road_class TEXT NOT NULL CHECK (road_class IN
    ('main_excl_motorway','main_incl_motorway','main_incl_motorway_raw','all_public')),
  length_km REAL NOT NULL, PRIMARY KEY (run_id, city_id, road_class)
);
CREATE TABLE IF NOT EXISTS metrics (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL, preset TEXT NOT NULL,
  length_basis TEXT NOT NULL CHECK (length_basis IN ('per_side','qecio_weighted')),
  value REAL, numerator_km REAL NOT NULL, denominator_km REAL NOT NULL,
  PRIMARY KEY (run_id, city_id, preset)
);
CREATE TABLE IF NOT EXISTS completeness (
  run_id INTEGER NOT NULL REFERENCES runs(id), city_id TEXT NOT NULL, tier TEXT NOT NULL,
  share_with_width REAL NOT NULL, share_with_surface REAL NOT NULL,
  share_with_segregated REAL NOT NULL, PRIMARY KEY (run_id, city_id, tier)
);
CREATE TABLE IF NOT EXISTS external_figures (
  id INTEGER PRIMARY KEY, city_id TEXT NOT NULL, source TEXT NOT NULL,
  metric_name TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, reference_date TEXT,
  network_scope TEXT NOT NULL,
  length_basis TEXT NOT NULL CHECK (length_basis IN ('streckenlaenge','reallaenge','unknown')),
  source_url TEXT NOT NULL, retrieved_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS duplicates (
  run_id INTEGER REFERENCES runs(id),
  kind TEXT NOT NULL CHECK (kind IN ('parallel','dual_carriageway')),
  way_id_separate INTEGER NOT NULL, way_id_road INTEGER NOT NULL, side TEXT,
  overlap_share REAL NOT NULL, distance_m REAL NOT NULL, resolved INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def upsert_cities(conn: sqlite3.Connection, cities: list[CityConfig]) -> int:
    conn.executemany(
        """
        INSERT INTO cities (id, name, country_iso2, lau_code, fua_code, osm_relation_id, epsg,
                            geofabrik_region)
        VALUES (:id, :name, :country_iso2, :lau_code, :fua_code, :osm_relation_id, :epsg,
                :geofabrik_region)
        ON CONFLICT(id) DO UPDATE SET
          name=excluded.name, country_iso2=excluded.country_iso2, lau_code=excluded.lau_code,
          fua_code=excluded.fua_code, osm_relation_id=excluded.osm_relation_id,
          epsg=excluded.epsg, geofabrik_region=excluded.geofabrik_region
        """,
        [c.model_dump() for c in cities],
    )
    conn.commit()
    return len(cities)


def fetch_cities(conn: sqlite3.Connection) -> list[City]:
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM cities ORDER BY id").fetchall()
    finally:
        conn.row_factory = None
    out = []
    for r in rows:
        d = dict(r)
        pop = None
        if d["population_value"] is not None:
            pop = Population(
                value=d["population_value"], year=d["population_year"],
                source=d["population_source"],
            )
        for k in ("population_value", "population_year", "population_source"):
            d.pop(k)
        out.append(City(**d, population=pop))
    return out
```

- [ ] **Step 4: Implement `src/velometer/cli.py` (init only)**

```python
"""velometer command-line interface."""

from pathlib import Path

import typer

from velometer.config import ConfigError, default_config_dir, load_cities
from velometer.db import connect, create_schema, upsert_cities

app = typer.Typer(no_args_is_help=True, help="Protected cycling infrastructure from OSM.")


@app.callback()
def main() -> None:
    """velometer: reproducible OSM cycling-infrastructure measurement."""


@app.command()
def init(
    db: Path = typer.Option(Path("velometer.sqlite"), help="SQLite database path."),
    config_dir: Path = typer.Option(default_config_dir(), help="Config directory."),
) -> None:
    """Create the SQLite schema and load config/cities.yaml (idempotent)."""
    try:
        cities = load_cities(config_dir / "cities.yaml")
    except ConfigError as e:
        typer.echo(f"config error: {e}", err=True)
        raise typer.Exit(1) from e
    conn = connect(db)
    create_schema(conn)
    n = upsert_cities(conn, cities)
    typer.echo(f"{db}: schema ready, {n} cities loaded")
```

- [ ] **Step 5: Run the tests and the gate**

Run: `uv run pytest -v && uv run ruff format . && uv run ruff check . && uv run velometer init --db "$TMPDIR/v.sqlite"`
Expected: all PASS. The CLI prints `…: schema ready, 5 cities loaded`.

- [ ] **Step 6: Commit**

```bash
git add src/velometer/models.py src/velometer/db.py src/velometer/cli.py tests/test_db.py tests/test_cli.py
git commit -m "feat: persisted models, SQLite schema and velometer init

Assisted-by: Claude:claude-opus-5-5"
```

---

### Task 3: Pipeline types and OSM reader

**Files:**
- Create: `src/velometer/pipeline/types.py`, `src/velometer/pipeline/read.py`, `tests/fixtures/cases/` (directory), `tests/fixtures/read_missing_node.osm`
- Test: `tests/test_read.py`

**Interfaces:**
- Produces:

```python
# velometer.pipeline.types
@dataclass(frozen=True)
class WayRecord:
    id: int
    tags: Mapping[str, str]
    coords: tuple[tuple[float, float], ...]   # (lon, lat)

Side = Literal["left", "right", "self"]
Kind = Literal["road_side", "standalone"]

@dataclass(frozen=True)
class WaySide:
    way_id: int
    side: Side
    kind: Kind
    tags: Mapping[str, str]
    coords: tuple[tuple[float, float], ...]
    contraflow: bool = False

@dataclass(frozen=True)
class Classified:
    side: WaySide
    tier: str | None          # "A".."E", "excluded", or None (no rule matched)
    subtype: str | None
    rule_id: str | None
    attrs: Mapping[str, bool | str]

@dataclass(frozen=True)
class DuplicateFlag:
    standalone_way_id: int
    road_way_id: int
    road_side: str
    overlap_share: float
    distance_m: float

@dataclass(frozen=True)
class DualPair:
    way_id: int
    partner_ids: tuple[int, ...]
    overlap_share: float

@dataclass(frozen=True)
class ReadResult:
    ways: list[WayRecord]
    skipped: list[int]        # way ids with <2 resolvable nodes
```

- `velometer.pipeline.read.read_ways(path: Path) -> ReadResult`

- [ ] **Step 1: Write `types.py`** with exactly the dataclasses above (`from collections.abc import Mapping`, `from dataclasses import dataclass`, `from typing import Literal`). It contains no logic.

- [ ] **Step 2: Write the fixture `tests/fixtures/read_missing_node.osm`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="hand">
  <node id="1" lat="52.5000" lon="13.4000"/>
  <node id="2" lat="52.5000" lon="13.4100"/>
  <node id="3" lat="52.5000" lon="13.4200"/>
  <way id="100"><nd ref="1"/><nd ref="2"/><nd ref="3"/><tag k="highway" v="cycleway"/></way>
  <way id="101"><nd ref="1"/><nd ref="999"/><tag k="highway" v="path"/></way>
  <way id="102"><nd ref="2"/><nd ref="999"/><nd ref="3"/><tag k="highway" v="footway"/></way>
  <way id="103"><nd ref="1"/><nd ref="2"/></way>
</osm>
```

- [ ] **Step 3: Write the failing test `tests/test_read.py`**

```python
from pathlib import Path

from velometer.pipeline.read import read_ways

FIX = Path(__file__).parent / "fixtures"


def test_reads_tags_and_lonlat_coords():
    res = read_ways(FIX / "read_missing_node.osm")
    way = next(w for w in res.ways if w.id == 100)
    assert dict(way.tags) == {"highway": "cycleway"}
    assert way.coords == ((13.4, 52.5), (13.41, 52.5), (13.42, 52.5))


def test_unresolvable_ways_are_skipped_and_reported_not_raised():
    res = read_ways(FIX / "read_missing_node.osm")
    assert res.skipped == [101]
    # 102 keeps its 2 resolvable nodes; partial ways are kept, dropped nodes don't crash
    assert [w.coords for w in res.ways if w.id == 102] == [((13.41, 52.5), (13.42, 52.5))]


def test_untagged_ways_are_ignored():
    res = read_ways(FIX / "read_missing_node.osm")
    assert 103 not in {w.id for w in res.ways}
```

Run: `uv run pytest tests/test_read.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement `read.py`**

```python
"""Read OSM ways (with node locations) from .osm / .osm.pbf via pyosmium."""

from pathlib import Path

import osmium

from velometer.pipeline.types import ReadResult, WayRecord


def read_ways(path: Path) -> ReadResult:
    """Return tagged ways with lon/lat coords. Ways with <2 resolvable nodes go to `skipped`."""
    ways: list[WayRecord] = []
    skipped: list[int] = []
    fp = osmium.FileProcessor(str(path), osmium.osm.WAY).with_locations()
    for obj in fp:
        if not obj.is_way() or len(obj.tags) == 0:
            continue
        coords = tuple(
            (n.location.lon, n.location.lat) for n in obj.nodes if n.location.valid()
        )
        if len(coords) < 2:
            skipped.append(obj.id)
            continue
        ways.append(WayRecord(id=obj.id, tags={t.k: t.v for t in obj.tags}, coords=coords))
    return ReadResult(ways=ways, skipped=skipped)
```

Note: `with_locations()` needs node objects to pass through the processor even though only ways are returned. If filtering on `osmium.osm.WAY` stops node locations from resolving (the test will show this), drop the entity filter and keep the `obj.is_way()` check.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_read.py -v && uv run ruff format . && uv run ruff check .`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/velometer/pipeline/types.py src/velometer/pipeline/read.py tests/test_read.py tests/fixtures/read_missing_node.osm
git commit -m "feat: pipeline types and pyosmium way reader with skip reporting

Assisted-by: Claude:claude-opus-5-5"
```

---

### Task 4: Explode ways into way-sides

**Files:**
- Create: `src/velometer/pipeline/explode.py`
- Test: `tests/test_explode.py`

**Interfaces:**
- Consumes: `WayRecord`, `WaySide` (Task 3), `RoadClasses` (Task 1).
- Produces: `explode(way: WayRecord, road_classes: RoadClasses) -> list[WaySide]`, `ONEWAY_YES: frozenset[str]`.

**Normalised road-side tag keys:**
- `cycleway`;
- `cycleway:<sub>` for sub ∈ `lane, oneway, separation, buffer, segregated, surface, width`;
- `sidewalk_bicycle`;
- `road:<k>` for k ∈ `highway, access, bicycle, area, oneway, name, ref, dual_carriageway`.

**Rules (spec §4 explode):**
- Precedence is `cycleway:<side>` > `cycleway:both` > `cycleway`, and sub-keys follow the same precedence. Each sub-key is collected at the first level that has any key equal to `<prefix>:<sub>` or starting with `<prefix>:<sub>:`, and the values are joined as a sorted, de-duplicated `;` list.
- Plain `cycleway=<v>` applies to both sides, except:
  - on a `oneway=yes|1|true` road it applies to the right side only;
  - `opposite` yields nothing;
  - `opposite_<x>` applies to the left side only, as `<x>` with `contraflow=True`.
- `opposite_<x>` given at the side or both level is normalised the same way.
- `sidewalk:<side>:bicycle`, falling back to `sidewalk:both:bicycle`, is always carried as `sidewalk_bicycle` when present.
- A road side is emitted only if it has `cycleway` or `sidewalk_bicycle`.
- A road way with `bicycle_road|cyclestreet|cycle_street=yes` additionally yields one `self` side of kind `standalone` carrying all the way's tags.
- Non-carriageway highways yield exactly one `self` standalone side with the way's tags.
- Ways without `highway` yield nothing.

- [ ] **Step 1: Write the failing tests `tests/test_explode.py`**

```python
import pytest

from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.explode import explode
from velometer.pipeline.types import WayRecord

RC = load_classifier(default_config_dir() / "classifier" / "v1.yaml").road_classes
LINE = ((13.40, 52.5), (13.41, 52.5))


def sides(tags: dict) -> dict:
    return {(s.side, s.kind): s for s in explode(WayRecord(1, tags, LINE), RC)}


def test_standalone_way_yields_self():
    out = sides({"highway": "cycleway", "foot": "designated"})
    assert list(out) == [("self", "standalone")]
    assert out[("self", "standalone")].tags["foot"] == "designated"


def test_no_highway_yields_nothing():
    assert sides({"building": "yes"}) == {}


def test_road_without_cycling_tags_yields_nothing():
    assert sides({"highway": "primary"}) == {}


def test_both_applies_to_each_side_and_carries_road_tags():
    out = sides({"highway": "primary", "cycleway:both": "lane", "name": "X", "access": "yes"})
    assert set(out) == {("left", "road_side"), ("right", "road_side")}
    right = out[("right", "road_side")].tags
    assert right["cycleway"] == "lane"
    assert right["road:highway"] == "primary" and right["road:name"] == "X"


def test_side_beats_both_beats_plain():
    out = sides({"highway": "secondary", "cycleway": "lane", "cycleway:both": "track",
                 "cycleway:left": "no"})
    assert out[("left", "road_side")].tags["cycleway"] == "no"
    assert out[("right", "road_side")].tags["cycleway"] == "track"


def test_subkeys_resolve_per_level_and_join_values():
    out = sides({
        "highway": "primary", "cycleway:right": "lane",
        "cycleway:right:separation:left": "kerb", "cycleway:right:separation:right": "bollard",
        "cycleway:both:lane": "exclusive", "cycleway:right:lane": "advisory",
    })
    tags = out[("right", "road_side")].tags
    assert tags["cycleway:separation"] == "bollard;kerb"
    assert tags["cycleway:lane"] == "advisory"


def test_plain_cycleway_on_oneway_road_is_right_only():
    out = sides({"highway": "tertiary", "oneway": "yes", "cycleway": "lane"})
    assert set(out) == {("right", "road_side")}


@pytest.mark.parametrize("value", ["opposite_track", "opposite_lane"])
def test_legacy_opposite_goes_left_with_contraflow(value):
    out = sides({"highway": "residential", "oneway": "yes", "cycleway": value})
    assert set(out) == {("left", "road_side")}
    left = out[("left", "road_side")]
    assert left.contraflow is True
    assert left.tags["cycleway"] == value.removeprefix("opposite_")


def test_plain_opposite_yields_nothing():
    assert sides({"highway": "residential", "oneway": "yes", "cycleway": "opposite"}) == {}


def test_sidewalk_bicycle_legacy_side():
    out = sides({"highway": "primary", "sidewalk:right:bicycle": "designated"})
    assert set(out) == {("right", "road_side")}
    assert out[("right", "road_side")].tags["sidewalk_bicycle"] == "designated"


def test_bicycle_road_adds_self_side_plus_side_tags():
    out = sides({"highway": "residential", "bicycle_road": "yes", "cycleway:right": "lane"})
    assert set(out) == {("self", "standalone"), ("right", "road_side")}
```

Run: `uv run pytest tests/test_explode.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 2: Implement `explode.py`**

```python
"""Explode OSM ways into way-sides (ADR 0002: classification is per way-side)."""

from velometer.config import RoadClasses
from velometer.pipeline.types import WayRecord, WaySide

ONEWAY_YES = frozenset({"yes", "1", "true", "-1"})
SUBKEYS = ("lane", "oneway", "separation", "buffer", "segregated", "surface", "width")
ROAD_CARRY = ("highway", "access", "bicycle", "area", "oneway", "name", "ref", "dual_carriageway")
CYCLE_STREET_KEYS = ("bicycle_road", "cyclestreet", "cycle_street")


def _side_value(tags, side: str, oneway: bool) -> str | None:
    for key in (f"cycleway:{side}", "cycleway:both"):
        if key in tags:
            return tags[key]
    plain = tags.get("cycleway")
    if plain is None:
        return None
    if plain.startswith("opposite"):
        return plain if side == "left" else None
    if oneway and side == "left":
        return None
    return plain


def _collect_sub(tags, side: str, sub: str) -> str | None:
    for prefix in (f"cycleway:{side}", "cycleway:both", "cycleway"):
        base = f"{prefix}:{sub}"
        vals = [v for k, v in tags.items() if k == base or k.startswith(base + ":")]
        if vals:
            parts = {p.strip() for v in vals for p in v.split(";") if p.strip()}
            return ";".join(sorted(parts))
    return None


def _resolve_side(tags, side: str) -> tuple[dict[str, str], bool] | None:
    oneway = tags.get("oneway") in ONEWAY_YES - {"-1"}
    value = _side_value(tags, side, oneway)
    contraflow = False
    if value == "opposite":
        value = None
    elif value is not None and value.startswith("opposite_"):
        value, contraflow = value.removeprefix("opposite_"), True
    out: dict[str, str] = {}
    if value is not None:
        out["cycleway"] = value
        for sub in SUBKEYS:
            joined = _collect_sub(tags, side, sub)
            if joined is not None:
                out[f"cycleway:{sub}"] = joined
    sidewalk = tags.get(f"sidewalk:{side}:bicycle", tags.get("sidewalk:both:bicycle"))
    if sidewalk is not None:
        out["sidewalk_bicycle"] = sidewalk
    return (out, contraflow) if out else None


def explode(way: WayRecord, road_classes: RoadClasses) -> list[WaySide]:
    highway = way.tags.get("highway")
    if highway is None:
        return []
    if highway not in road_classes.carriageway:
        return [WaySide(way.id, "self", "standalone", dict(way.tags), way.coords)]
    result: list[WaySide] = []
    if any(way.tags.get(k) == "yes" for k in CYCLE_STREET_KEYS):
        result.append(WaySide(way.id, "self", "standalone", dict(way.tags), way.coords))
    carried = {f"road:{k}": way.tags[k] for k in ROAD_CARRY if k in way.tags}
    for side in ("left", "right"):
        resolved = _resolve_side(way.tags, side)
        if resolved is None:
            continue
        tags, contraflow = resolved
        result.append(
            WaySide(way.id, side, "road_side", {**tags, **carried}, way.coords, contraflow)
        )
    return result
```

- [ ] **Step 3: Run the tests**

Run: `uv run pytest tests/test_explode.py -v && uv run ruff format . && uv run ruff check .`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/velometer/pipeline/explode.py tests/test_explode.py
git commit -m "feat: explode road ways into normalised way-sides

Assisted-by: Claude:claude-opus-5-5"
```

---

### Task 5: Classifier rules v1, rule engine, golden cases, mutation tests

**Files:**
- Create: `src/velometer/pipeline/classify.py`, `tests/fixtures/cases/*.osm` (one per case below), `tests/fixtures/expected.yaml`
- Modify: `config/classifier/v1.yaml` (replace `rules: []`)
- Test: `tests/test_classify.py`

**Interfaces:**
- Consumes: `explode` (Task 4), `matches` (Task 1), `read_ways` (Task 3), `ClassifierConfig`.
- Produces:
  - `classify(side: WaySide, cfg: ClassifierConfig) -> Classified`
  - `classify_ways(ways: Iterable[WayRecord], cfg: ClassifierConfig) -> list[Classified]` (explode + classify, in input order)
  - `is_bidirectional(side: WaySide) -> bool`
- `Classified.attrs` always has `bidirectional: bool` and `contraflow: bool`. It has `segregated: str` when the side's tags have `segregated` (standalone) or `cycleway:segregated` (road side). It has `unknown_value: str` when a road side with a `cycleway` value matched no rule. Rule `attrs` are merged on top.

- [ ] **Step 1: Write the rules in `config/classifier/v1.yaml`** (replace `rules: []`; first match wins, so order matters)

```yaml
# Ordered; first match wins. Invalidating exclusions first, then tiers, then
# "no infrastructure" exclusions. Tier semantics: docs/adr/0002-tiered-classifier-from-qecio.md
rules:
  # --- invalidating exclusions ---
  - id: X_lifecycle
    applies_to: standalone
    tier: excluded
    subtype: lifecycle
    match: {highway: [construction, proposed]}
  - id: X_area
    applies_to: standalone
    tier: excluded
    subtype: area
    match: {area: "yes"}
  - id: X_road_area
    applies_to: road_side
    tier: excluded
    subtype: area
    match: {"road:area": "yes"}
  - id: X_private
    applies_to: standalone
    tier: excluded
    subtype: private
    match: {access: private, bicycle: {not_in: [yes, designated, permissive]}}
  - id: X_road_private
    applies_to: road_side
    tier: excluded
    subtype: private
    match: {"road:access": private, "road:bicycle": {not_in: [yes, designated, permissive]}}
  - id: X_bicycle_no
    applies_to: standalone
    tier: excluded
    subtype: bicycle_no
    match: {bicycle: ["no", dismount]}
  - id: X_separate
    applies_to: road_side
    tier: excluded
    subtype: separate
    match: {cycleway: separate}
  # --- tier A: separated cycle track ---
  - id: A_cycleway
    applies_to: standalone
    tier: A
    match:
      highway: cycleway
      any: [{foot: {not_in: [designated]}}, {segregated: "yes"}]
  - id: A_track_side
    applies_to: road_side
    tier: A
    match: {cycleway: track}
  # --- tier B: shared foot/cycle path ---
  - id: B_cycleway_foot
    applies_to: standalone
    tier: B
    match: {highway: cycleway, foot: designated}
  - id: B_path_segregated
    applies_to: standalone
    tier: B
    subtype: segregated
    match: {highway: [path, footway, pedestrian], bicycle: designated, segregated: "yes"}
  - id: B_path
    applies_to: standalone
    tier: B
    match: {highway: [path, footway, pedestrian], bicycle: designated}
  - id: B_sidewalk_designated
    applies_to: road_side
    tier: B
    subtype: sidewalk
    match: {sidewalk_bicycle: designated, cycleway: {not_in: [lane, share_busway]}}
  - id: B_share_sidewalk
    applies_to: road_side
    tier: B
    subtype: sidewalk
    match: {cycleway: share_sidewalk}
  # --- tier C/D: lanes ---
  - id: C_lane_physical
    applies_to: road_side
    tier: C
    match: {cycleway: lane, "cycleway:separation": {in_list: physical_separation}}
  - id: D_lane_advisory
    applies_to: road_side
    tier: D
    subtype: advisory
    attrs: {advisory: true}
    match: {cycleway: lane, "cycleway:lane": [advisory, pictogram]}
  - id: D_lane
    applies_to: road_side
    tier: D
    match: {cycleway: lane}
  # --- tier E: cycle streets, bus lanes ---
  - id: E_cycle_street
    applies_to: standalone
    tier: E
    subtype: cycle_street
    match: {any: [{bicycle_road: "yes"}, {cyclestreet: "yes"}, {cycle_street: "yes"}]}
  - id: E_bus
    applies_to: road_side
    tier: E
    subtype: bus
    attrs: {bus: true}
    match: {cycleway: share_busway}
  # --- no infrastructure (diagnostic only) ---
  - id: X_no
    applies_to: road_side
    tier: excluded
    subtype: "no"
    match: {cycleway: ["no", none]}
  - id: X_shared_lane
    applies_to: road_side
    tier: excluded
    subtype: shared_lane
    attrs: {shared_lane: true}
    match: {cycleway: [shared_lane, shared]}
  - id: X_sidewalk_bicycle_permitted
    applies_to: road_side
    tier: excluded
    subtype: sidewalk_permitted
    match: {sidewalk_bicycle: ["yes", permissive]}
```

Notes for the implementer:
- `"no"` and `"yes"` must be quoted in YAML (or rely on the matcher's bool normalisation, which Task 1 tests).
- The quoting of `"road:area"` etc. is required because of the colon.
- `X_bicycle_no` treats `dismount` as no-cycling (ruling).
- A standalone `highway=footway` without `bicycle=designated` matches nothing (tier `None`). This is intended: QECIO's "pedestrian track with cycling allowed" is not counted.

- [ ] **Step 2: Write the golden case fixtures**

Each case is a file `tests/fixtures/cases/<case>.osm`. Geometry convention: nodes lie on latitude 52.5, starting at lon 13.40, spaced 0.0147° (≈1 km) apart. Use node ids 1–4 and way ids starting at 10. Template, for case `A_cycleway_basic`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="hand">
  <node id="1" lat="52.5" lon="13.4000"/>
  <node id="2" lat="52.5" lon="13.4147"/>
  <way id="10"><nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="cycleway"/>
  </way>
</osm>
```

Write one file per row below, with way 10 carrying the listed tags. Then add an entry to `tests/fixtures/expected.yaml`. The expected `sides` list must be **complete**: every side whose tier is not `None` is listed, and the test fails on extras. A `tier: null` row asserts that the side exists but matches no rule.

| case | way 10 tags | expected sides `(side, tier, rule)` + attrs |
|---|---|---|
| A_cycleway_basic | highway=cycleway | (self, A, A_cycleway), bidirectional: true |
| A_cycleway_oneway | highway=cycleway, oneway=yes | (self, A, A_cycleway), bidirectional: false |
| A_cycleway_foot_segregated | highway=cycleway, foot=designated, segregated=yes | (self, A, A_cycleway), segregated: "yes" |
| B_cycleway_foot_shared | highway=cycleway, foot=designated, segregated=no | (self, B, B_cycleway_foot), segregated: "no" |
| B_cycleway_foot_untagged | highway=cycleway, foot=designated | (self, B, B_cycleway_foot) |
| B_footway_segregated | highway=footway, bicycle=designated, segregated=yes | (self, B, B_path_segregated) |
| B_path_shared | highway=path, bicycle=designated, foot=designated, segregated=no | (self, B, B_path) |
| B_pedestrian_designated | highway=pedestrian, bicycle=designated | (self, B, B_path) |
| footway_bicycle_yes | highway=footway, bicycle=yes | (self, null, null) |
| A_track_both | highway=primary, cycleway:both=track | (left, A, A_track_side), (right, A, A_track_side), bidirectional: false |
| A_track_right_twoway | highway=primary, cycleway:right=track, cycleway:right:oneway=no | (right, A, A_track_side), bidirectional: true |
| side_precedence | highway=secondary, cycleway:both=lane, cycleway:left=no | (left, excluded, X_no), (right, D, D_lane) |
| C_lane_kerb | highway=primary, cycleway:right=lane, cycleway:right:separation:left=kerb | (right, C, C_lane_physical) |
| C_lane_multi_value | highway=primary, cycleway:right=lane, cycleway:right:separation=solid_line;bollard | (right, C, C_lane_physical) |
| C_lane_parking | highway=primary, cycleway:both=lane, cycleway:both:separation=parking_lane | (left, C, C_lane_physical), (right, C, C_lane_physical) |
| D_lane_paint | highway=primary, cycleway:right=lane, cycleway:right:separation=solid_line | (right, D, D_lane) |
| D_lane_advisory | highway=residential, cycleway:both=lane, cycleway:both:lane=advisory | (left, D, D_lane_advisory), (right, D, D_lane_advisory), advisory: true |
| E_bus | highway=primary, cycleway:right=share_busway | (right, E, E_bus), bus: true |
| E_bicycle_road | highway=residential, bicycle_road=yes | (self, E, E_cycle_street) |
| E_cyclestreet | highway=residential, cyclestreet=yes | (self, E, E_cycle_street) |
| X_separate | highway=primary, cycleway:both=separate | (left, excluded, X_separate), (right, excluded, X_separate) |
| X_shared_lane | highway=residential, cycleway=shared_lane | (left, excluded, X_shared_lane), (right, excluded, X_shared_lane), shared_lane: true |
| X_private_cycleway | highway=cycleway, access=private | (self, excluded, X_private) |
| private_but_bicycle_yes | highway=cycleway, access=private, bicycle=yes | (self, A, A_cycleway) |
| X_bicycle_no | highway=path, bicycle=no | (self, excluded, X_bicycle_no) |
| X_area | highway=pedestrian, bicycle=designated, area=yes | (self, excluded, X_area) |
| X_construction | highway=construction, construction=cycleway | (self, excluded, X_lifecycle) |
| legacy_opposite_track | highway=residential, oneway=yes, cycleway=opposite_track | (left, A, A_track_side), contraflow: true |
| legacy_opposite_lane | highway=residential, oneway=yes, cycleway=opposite_lane | (left, D, D_lane), contraflow: true |
| legacy_sidewalk_designated | highway=primary, sidewalk:right:bicycle=designated | (right, B, B_sidewalk_designated) |
| legacy_sidewalk_yes | highway=primary, sidewalk:both:bicycle=yes | (left, excluded, X_sidewalk_bicycle_permitted), (right, excluded, X_sidewalk_bicycle_permitted) |
| oneway_plain_lane | highway=tertiary, oneway=yes, cycleway=lane | (right, D, D_lane) |
| unknown_value | highway=primary, cycleway:right=crossing | (right, null, null), unknown_value: "crossing" |
| road_private | highway=service, access=private, cycleway:right=track | (right, excluded, X_road_private) |

`expected.yaml` format:

```yaml
cases:
  A_cycleway_basic:
    sides:
      - {way: 10, side: self, tier: A, rule: A_cycleway, attrs: {bidirectional: true}}
  unknown_value:
    sides:
      - {way: 10, side: right, tier: null, rule: null, attrs: {unknown_value: crossing}}
```

- [ ] **Step 3: Write the failing tests `tests/test_classify.py`**

```python
from pathlib import Path

import pytest
import yaml

from velometer.config import ClassifierConfig, default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.read import read_ways

FIX = Path(__file__).parent / "fixtures"
CFG = load_classifier(default_config_dir() / "classifier" / "v1.yaml")
EXPECTED = yaml.safe_load((FIX / "expected.yaml").read_text())["cases"]


def run_case(case: str, cfg: ClassifierConfig = CFG) -> list:
    return classify_ways(read_ways(FIX / "cases" / f"{case}.osm").ways, cfg)


def observed(case: str, cfg: ClassifierConfig = CFG) -> set[tuple]:
    return {(c.side.way_id, c.side.side, c.tier, c.rule_id) for c in run_case(case, cfg)}


def test_every_case_file_has_an_expectation_and_vice_versa():
    files = {p.stem for p in (FIX / "cases").glob("*.osm")}
    assert files == set(EXPECTED)
    assert len(files) >= 25


@pytest.mark.parametrize("case", sorted(EXPECTED))
def test_case_sides_tiers_and_rules(case):
    want = {(s["way"], s["side"], s["tier"], s["rule"]) for s in EXPECTED[case]["sides"]}
    got = observed(case)
    # sides with tier None are only compared when the expectation lists them
    got = {g for g in got if g[2] is not None or g in want}
    assert got == want


@pytest.mark.parametrize("case", sorted(EXPECTED))
def test_case_attrs(case):
    by_key = {(c.side.way_id, c.side.side): c for c in run_case(case)}
    for s in EXPECTED[case]["sides"]:
        attrs = by_key[(s["way"], s["side"])].attrs
        for k, v in s.get("attrs", {}).items():
            assert attrs.get(k) == v, (case, s["side"], k)


def _without(rule_id: str) -> ClassifierConfig:
    rules = [r for r in CFG.rules if r.id != rule_id]
    assert len(rules) == len(CFG.rules) - 1, rule_id
    return CFG.model_copy(update={"rules": rules})


# Red-proofing: each core rule is load-bearing for at least the named fixture.
@pytest.mark.parametrize(
    ("rule_id", "case"),
    [
        ("A_cycleway", "A_cycleway_basic"),
        ("A_track_side", "A_track_both"),
        ("B_path_segregated", "B_footway_segregated"),
        ("B_cycleway_foot", "B_cycleway_foot_shared"),
        ("C_lane_physical", "C_lane_kerb"),
        ("D_lane_advisory", "D_lane_advisory"),
        ("E_bus", "E_bus"),
        ("E_cycle_street", "E_bicycle_road"),
        ("X_separate", "X_separate"),
        ("X_private", "X_private_cycleway"),
        ("X_road_private", "road_private"),
        ("B_sidewalk_designated", "legacy_sidewalk_designated"),
    ],
)
def test_rule_is_load_bearing(rule_id, case):
    assert observed(case, _without(rule_id)) != observed(case)


def test_rule_order_matters_track_before_sidewalk():
    # a road side with both a track and a designated sidewalk is a track (tier A)
    from velometer.pipeline.types import WayRecord

    way = WayRecord(10, {"highway": "primary", "cycleway:right": "track",
                         "sidewalk:right:bicycle": "designated"}, ((13.4, 52.5), (13.41, 52.5)))
    (c,) = classify_ways([way], CFG)
    assert (c.tier, c.rule_id) == ("A", "A_track_side")
```

Run: `uv run pytest tests/test_classify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'velometer.pipeline.classify'`.

- [ ] **Step 4: Implement `classify.py`**

```python
"""Ordered, data-driven rule engine over way-sides (rules: config/classifier/vN.yaml)."""

from collections.abc import Iterable

from velometer.config import ClassifierConfig
from velometer.pipeline.explode import ONEWAY_YES, explode
from velometer.pipeline.match import matches
from velometer.pipeline.types import Classified, WayRecord, WaySide


def is_bidirectional(side: WaySide) -> bool:
    """QECIO Methodology Table 3 directionality."""
    if side.kind == "standalone":
        return (
            side.tags.get("oneway", "no") not in ONEWAY_YES
            and side.tags.get("oneway:bicycle") != "yes"
        )
    return side.tags.get("cycleway:oneway") == "no"


def _generic_attrs(side: WaySide) -> dict[str, bool | str]:
    attrs: dict[str, bool | str] = {
        "bidirectional": is_bidirectional(side),
        "contraflow": side.contraflow,
    }
    seg = side.tags.get("segregated" if side.kind == "standalone" else "cycleway:segregated")
    if seg is not None:
        attrs["segregated"] = seg
    return attrs


def classify(side: WaySide, cfg: ClassifierConfig) -> Classified:
    attrs = _generic_attrs(side)
    for rule in cfg.rules:
        if rule.applies_to not in ("any", side.kind):
            continue
        if matches(rule.match, side.tags, cfg.value_lists):
            return Classified(side, rule.tier, rule.subtype, rule.id, {**attrs, **rule.attrs})
    if side.kind == "road_side" and "cycleway" in side.tags:
        attrs["unknown_value"] = side.tags["cycleway"]
    return Classified(side, None, None, None, attrs)


def classify_ways(ways: Iterable[WayRecord], cfg: ClassifierConfig) -> list[Classified]:
    return [classify(s, cfg) for w in ways for s in explode(w, cfg.road_classes)]
```

- [ ] **Step 5: Run the tests and iterate on the fixtures and YAML (never by special-casing in code)**

Run: `uv run pytest tests/test_classify.py -v`
Expected: all PASS. If a case fails, check the fixture against the table first. Only change `v1.yaml` if the table and the ADR agree that the rule is wrong, and report any such change in your task summary.

- [ ] **Step 6: Verify red-proofing manually once**

In `v1.yaml`, temporarily change `C_lane_physical`'s `in_list: physical_separation` to `in_list: paint_separation`. Run `uv run pytest tests/test_classify.py -q`. Expected: `C_lane_kerb`, `C_lane_multi_value` and `C_lane_parking` FAIL. Revert with `git checkout config/classifier/v1.yaml`, or undo the edit if it isn't committed yet.

- [ ] **Step 7: Commit**

```bash
git add config/classifier/v1.yaml src/velometer/pipeline/classify.py tests/test_classify.py tests/fixtures/cases tests/fixtures/expected.yaml
git commit -m "feat: v1 classifier rules, rule engine and golden case fixtures

Assisted-by: Claude:claude-opus-5-5"
```

---

### Task 6: Geometry helpers and dedupe (parallel duplicates, dual carriageways)

**Files:**
- Create: `src/velometer/pipeline/geometry.py`, `src/velometer/pipeline/dedupe.py`, `tests/fixtures/dedupe/parallel.osm`, `tests/fixtures/dedupe/dual.osm`
- Test: `tests/test_dedupe.py`, `tests/test_geometry.py`

**Interfaces:**
- Consumes: `Classified`, `WayRecord`, `DuplicateFlag`, `DualPair` (Task 3); `classify_ways` (Task 5).
- Produces:
  - `geometry.Projector`: a class with `__init__(self, epsg: int)` and `line(self, coords) -> shapely.LineString`, results cached by coords tuple.
  - `geometry.length_km(line) -> float`.
  - `dedupe.flag_parallel_duplicates(classified: list[Classified], proj: Projector, max_dist_m: float = 15.0, min_share: float = 0.8) -> list[DuplicateFlag]`.
  - `dedupe.pair_dual_carriageways(roads: list[WayRecord], pairable_highways: set[str], proj: Projector, max_dist_m: float = 50.0, min_share: float = 0.7, min_angle_deg: float = 150.0) -> tuple[dict[int, float], list[DualPair]]`. Factors are 0.5 or 1.0 for every road in `roads`.

- [ ] **Step 1: Write the failing tests**

`tests/test_geometry.py`:

```python
from pyproj import Geod

from velometer.pipeline.geometry import Projector, length_km


def test_one_km_geodesic_segment_measures_one_km_in_utm():
    lon2, lat2, _ = Geod(ellps="WGS84").fwd(13.4, 52.5, 90, 1000.0)
    line = Projector(25833).line(((13.4, 52.5), (lon2, lat2)))
    assert abs(length_km(line) - 1.0) < 0.005


def test_lengths_are_not_degrees():
    line = Projector(25833).line(((13.4, 52.5), (13.5, 52.5)))
    assert 6.0 < length_km(line) < 7.5  # 0.1° lon at 52.5°N ≈ 6.8 km, not 0.1
```

`tests/fixtures/dedupe/parallel.osm`:
- Way 10: highway=primary, cycleway:right=track, from (13.4000, 52.5000) to (13.4147, 52.5000).
- Way 11: highway=cycleway, oneway=yes, from (13.4000, 52.49992) to (13.4147, 52.49992), about 9 m south.
- Way 12: highway=cycleway, from (13.4000, 52.5010) to (13.4147, 52.5010), about 110 m north, so it is not a duplicate.
- Way 13: highway=cycleway, two identical nodes at (13.42, 52.5) (degenerate).

`tests/fixtures/dedupe/dual.osm`:
- Way 20: highway=primary, oneway=yes, name=Karl-Marx-Allee, west→east along lat 52.5000, lon 13.40→13.4147.
- Way 21: same name, oneway=yes, east→west along lat 52.50025 (≈28 m north).
- Way 22: highway=primary, oneway=yes, name=Einbahnstraße, west→east along lat 52.51, with no partner.
- Way 23: highway=secondary, dual_carriageway=yes, along lat 52.52.
- Way 24: highway=primary, oneway=yes, name=Karl-Marx-Allee, west→east along lat 52.5003. It has the same direction as way 20, so it must **not** pair with 20. It can pair with 21.

`tests/test_dedupe.py`:

```python
from pathlib import Path

from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.dedupe import flag_parallel_duplicates, pair_dual_carriageways
from velometer.pipeline.geometry import Projector
from velometer.pipeline.read import read_ways

FIX = Path(__file__).parent / "fixtures" / "dedupe"
CFG = load_classifier(default_config_dir() / "classifier" / "v1.yaml")
PROJ = Projector(25833)
MAIN = set(CFG.road_classes.main) | set(CFG.road_classes.motorway)


def test_parallel_cycleway_next_to_tagged_track_is_flagged_not_removed():
    classified = classify_ways(read_ways(FIX / "parallel.osm").ways, CFG)
    flags = flag_parallel_duplicates(classified, PROJ)
    assert [(f.standalone_way_id, f.road_way_id, f.road_side) for f in flags] == [
        (11, 10, "right")
    ]
    assert flags[0].overlap_share >= 0.8 and flags[0].distance_m < 15
    assert {c.side.way_id for c in classified} >= {10, 11, 12}  # nothing removed


def test_degenerate_geometry_does_not_crash():
    classified = classify_ways(read_ways(FIX / "parallel.osm").ways, CFG)
    flag_parallel_duplicates(classified, PROJ)  # way 13 has zero length


def test_dual_carriageway_by_pairing_and_by_tag():
    roads = read_ways(FIX / "dual.osm").ways
    factors, pairs = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors[20] == 0.5 and factors[21] == 0.5 and factors[24] == 0.5
    assert factors[22] == 1.0
    assert factors[23] == 0.5  # dual_carriageway=yes
    by_way = {p.way_id: set(p.partner_ids) for p in pairs}
    assert 24 not in by_way[20]  # same direction never pairs
    assert by_way[20] == {21}


def test_pairing_ignores_non_main_highways():
    roads = [
        w if w.id != 21 else type(w)(w.id, {**w.tags, "highway": "residential"}, w.coords)
        for w in read_ways(FIX / "dual.osm").ways
    ]
    factors, _ = pair_dual_carriageways(roads, MAIN, PROJ)
    assert factors[21] == 1.0
```

Run: `uv run pytest tests/test_geometry.py tests/test_dedupe.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 2: Implement `geometry.py`**

```python
"""Projection to a city's metric CRS and length helpers (never measure in degrees)."""

from shapely import LineString
from shapely.ops import transform
from pyproj import Transformer


class Projector:
    def __init__(self, epsg: int) -> None:
        self.epsg = epsg
        self._tf = Transformer.from_crs(4326, epsg, always_xy=True)
        self._cache: dict[tuple, LineString] = {}

    def line(self, coords: tuple[tuple[float, float], ...]) -> LineString:
        hit = self._cache.get(coords)
        if hit is None:
            hit = transform(self._tf.transform, LineString(coords))
            self._cache[coords] = hit
        return hit


def length_km(line: LineString) -> float:
    return line.length / 1000.0
```

- [ ] **Step 3: Implement `dedupe.py`**

```python
"""Flag (never delete) double-mapped infrastructure; detect dual carriageways (ADR 0003)."""

import math
from collections import defaultdict

from shapely import STRtree, unary_union

from velometer.pipeline.explode import ONEWAY_YES
from velometer.pipeline.geometry import Projector
from velometer.pipeline.types import Classified, DualPair, DuplicateFlag, WayRecord

ROAD_TIERS = {"A", "B", "C", "D"}
STANDALONE_TIERS = {"A", "B"}


def _share_within(line, other, dist_m: float) -> float:
    if line.length == 0:
        return 0.0
    return line.intersection(other.buffer(dist_m)).length / line.length


def flag_parallel_duplicates(
    classified: list[Classified], proj: Projector, max_dist_m: float = 15.0,
    min_share: float = 0.8,
) -> list[DuplicateFlag]:
    roads = [c for c in classified if c.side.kind == "road_side" and c.tier in ROAD_TIERS]
    stands = [c for c in classified if c.side.kind == "standalone" and c.tier in STANDALONE_TIERS]
    if not roads or not stands:
        return []
    road_geoms = [proj.line(r.side.coords) for r in roads]
    tree = STRtree(road_geoms)
    flags: list[DuplicateFlag] = []
    for s in stands:
        geom = proj.line(s.side.coords)
        if geom.length == 0:
            continue
        for idx in tree.query(geom.buffer(max_dist_m)):
            share = _share_within(geom, road_geoms[idx], max_dist_m)
            if share >= min_share:
                r = roads[idx]
                mid = geom.interpolate(0.5, normalized=True)
                flags.append(DuplicateFlag(
                    s.side.way_id, r.side.way_id, r.side.side, round(share, 4),
                    round(road_geoms[idx].distance(mid), 2),
                ))
    return sorted(flags, key=lambda f: (f.standalone_way_id, f.road_way_id, f.road_side))


def _bearing(line, reverse: bool) -> float:
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    if reverse:
        x0, y0, x1, y1 = x1, y1, x0, y0
    return math.degrees(math.atan2(y1 - y0, x1 - x0))


def _angle(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def pair_dual_carriageways(
    roads: list[WayRecord], pairable_highways: set[str], proj: Projector,
    max_dist_m: float = 50.0, min_share: float = 0.7, min_angle_deg: float = 150.0,
) -> tuple[dict[int, float], list[DualPair]]:
    factors = {w.id: 1.0 for w in roads}
    for w in roads:
        if w.tags.get("dual_carriageway") == "yes":
            factors[w.id] = 0.5
    groups: dict[tuple[str, str], list[WayRecord]] = defaultdict(list)
    for w in roads:
        if w.tags.get("highway") not in pairable_highways:
            continue
        if w.tags.get("oneway") not in ONEWAY_YES:
            continue
        for key in ("name", "ref"):
            if w.tags.get(key):
                groups[(key, w.tags[key].strip().casefold())].append(w)
    pairable_ids = {x.id for g in groups.values() for x in g}
    pairs: list[DualPair] = []
    for w in roads:
        if w.id not in pairable_ids:  # never halve two-way or non-main roads by pairing
            continue
        partners: dict[int, WayRecord] = {}
        geom = proj.line(w.coords)
        if geom.length == 0:
            continue
        bw = _bearing(geom, w.tags.get("oneway") == "-1")
        for key in ("name", "ref"):
            value = w.tags.get(key)
            if not value:
                continue
            for o in groups.get((key, value.strip().casefold()), []):
                if o.id == w.id or o.id in partners:
                    continue
                og = proj.line(o.coords)
                if og.length == 0:
                    continue
                if _angle(bw, _bearing(og, o.tags.get("oneway") == "-1")) >= min_angle_deg:
                    partners[o.id] = o
        if not partners:
            continue
        union = unary_union([proj.line(o.coords) for o in partners.values()])
        share = _share_within(geom, union, max_dist_m)
        if share >= min_share:
            factors[w.id] = 0.5
            pairs.append(DualPair(w.id, tuple(sorted(partners)), round(share, 4)))
    return factors, pairs
```

Note: `DualPair.partner_ids` lists all opposite-direction same-name candidates whose union gives the share. The test expects `{21}` for way 20, because way 24 has the same direction.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_geometry.py tests/test_dedupe.py -v && uv run ruff format . && uv run ruff check .`
Expected: PASS.

- [ ] **Step 5: Red-proof once.** Temporarily change `min_angle_deg` default to `0.0`. Run `tests/test_dedupe.py::test_dual_carriageway_by_pairing_and_by_tag`. Expected: FAIL (24 pairs with 20). Revert.

- [ ] **Step 6: Commit**

```bash
git add src/velometer/pipeline/geometry.py src/velometer/pipeline/dedupe.py tests/test_geometry.py tests/test_dedupe.py tests/fixtures/dedupe
git commit -m "feat: projected geometry, parallel-duplicate flags and dual-carriageway pairing

Assisted-by: Claude:claude-opus-5-5"
```

---

### Task 7: Measure, presets, `velometer classify`

**Files:**
- Create: `src/velometer/pipeline/measure.py`, `tests/fixtures/measure/mini_city.osm`
- Modify: `src/velometer/cli.py` (add the `classify` command)
- Test: `tests/test_measure.py`, `tests/test_cli.py` (add a test)

**Interfaces:**
- Consumes: everything above; `TierLength`, `RoadLength`, `Metric` (Task 2); `Preset`, `load_presets` (Task 1).
- Produces:

```python
@dataclass(frozen=True)
class MeasureResult:
    tier_lengths: list[TierLength]
    road_lengths: list[RoadLength]
    duplicates: list[DuplicateFlag]
    dual_pairs: list[DualPair]
    classified: list[Classified]
    unknown_values: dict[str, int]   # cycleway value -> count of unmatched road sides

def measure(ways: list[WayRecord], cfg: ClassifierConfig, epsg: int) -> MeasureResult
def compute_metrics(result: MeasureResult, presets: list[Preset]) -> list[Metric]
def road_length(result: MeasureResult, road_class: str) -> float
```

**Aggregation rules:**
- Each classified side with a tier (including `excluded`) contributes its way length to `(tier, subtype, "per_side")`. The same length × (1.0 if `attrs["bidirectional"]` else 0.5) goes to `(tier, subtype, "qecio_weighted")`.
- `n_ways` = the number of distinct way ids in that key.
- Road lengths come from ways whose `highway` is in main ∪ motorway ∪ local, excluding `access=private` and `area=yes`:
  - `main_excl_motorway` = Σ L·f over main;
  - `main_incl_motorway` = Σ L·f over main ∪ motorway;
  - `main_incl_motorway_raw` = Σ L over main ∪ motorway;
  - `all_public` = Σ L·f over all three.
- f comes from `pair_dual_carriageways(public_roads, main ∪ motorway, proj)`.
- A preset tier entry `"X"` selects tier X with any subtype; `"X/s"` selects only subtype s. `excluded` is never selected.
- Metric `value = 100 * num / den`, or `None` when `den == 0`.

`tests/fixtures/measure/mini_city.osm` (lat 52.5; each segment about 1 km = 0.0147° lon; distinct latitudes so that nothing pairs unless intended):
- Way 1: primary, cycleway:both=track (1 km) → A per_side 2 km, qecio 1 km.
- Way 2: highway=cycleway, oneway=yes (1 km), at lat 52.51 → A per_side 1, qecio 0.5.
- Way 3: highway=footway, bicycle=designated (1 km), at lat 52.52 → B per_side 1, qecio 1.
- Way 4: secondary, cycleway:right=lane (1 km), at lat 52.53 → D per_side 1, qecio 0.5.
- Way 5: motorway (1 km), at lat 52.54.
- Way 6: residential (1 km), at lat 52.55.
- Way 7: service, access=private (1 km), at lat 52.56 → ignored.

Expected (±1%):
- A per_side 3, A qecio 1.5, B per_side 1, D per_side 1.
- main_excl 2, main_incl 3, main_incl_raw 3, all_public 4.
- ours_headline = 100·(3+1)/2 = 200.
- ecf_qecio = 100·(1.5+1+0.5)/3 = 100.
- clean_cities_2025 = 100·4/4 = 100.

Compute lengths in the test from the fixture via `Projector`, not from these rounded numbers. Assert the *ratios*, which are exact by construction.

- [ ] **Step 1: Write the failing tests `tests/test_measure.py`**

```python
from pathlib import Path

import pytest

from velometer.config import default_config_dir, load_classifier, load_presets
from velometer.pipeline.measure import compute_metrics, measure, road_length
from velometer.pipeline.read import read_ways
from velometer.pipeline.types import WayRecord

FIX = Path(__file__).parent / "fixtures" / "measure"
CFG = load_classifier(default_config_dir() / "classifier" / "v1.yaml")
PRESETS = load_presets(default_config_dir() / "presets.yaml")


@pytest.fixture(scope="module")
def result():
    return measure(read_ways(FIX / "mini_city.osm").ways, CFG, 25833)


def km(result, tier, basis, subtype=None):
    return sum(t.length_km for t in result.tier_lengths
               if t.tier == tier and t.length_basis == basis
               and (subtype is None or t.subtype == subtype))


def test_per_side_counts_each_side_qecio_halves_unidirectional(result):
    unit = road_length(result, "main_excl_motorway") / 2  # 1 segment
    assert km(result, "A", "per_side") == pytest.approx(3 * unit, rel=0.01)
    assert km(result, "A", "qecio_weighted") == pytest.approx(1.5 * unit, rel=0.01)
    assert km(result, "B", "qecio_weighted") == pytest.approx(1 * unit, rel=0.01)


def test_road_classes_exclude_private_and_split_motorways(result):
    main = road_length(result, "main_excl_motorway")
    assert road_length(result, "main_incl_motorway") == pytest.approx(1.5 * main, rel=0.01)
    assert road_length(result, "main_incl_motorway_raw") == pytest.approx(1.5 * main, rel=0.01)
    assert road_length(result, "all_public") == pytest.approx(2 * main, rel=0.01)


def test_preset_metrics(result):
    m = {x.preset: x.value for x in compute_metrics(result, PRESETS)}
    assert m["ours_headline"] == pytest.approx(200, rel=0.01)
    assert m["ecf_qecio"] == pytest.approx(100, rel=0.01)
    assert m["clean_cities_2025"] == pytest.approx(100, rel=0.01)


def test_empty_denominator_gives_none_not_error():
    ways = [WayRecord(1, {"highway": "cycleway"}, ((13.4, 52.5), (13.41, 52.5)))]
    m = compute_metrics(measure(ways, CFG, 25833), PRESETS)
    assert all(x.value is None and x.denominator_km == 0 for x in m)


def test_unknown_values_are_counted():
    ways = [WayRecord(1, {"highway": "primary", "cycleway:both": "crossing"},
                      ((13.4, 52.5), (13.41, 52.5)))]
    assert measure(ways, CFG, 25833).unknown_values == {"crossing": 2}


def test_dual_carriageway_halves_denominator_but_not_raw():
    a = WayRecord(1, {"highway": "primary", "oneway": "yes", "name": "X"},
                  ((13.40, 52.5), (13.4147, 52.5)))
    b = WayRecord(2, {"highway": "primary", "oneway": "yes", "name": "X"},
                  ((13.4147, 52.50025), (13.40, 52.50025)))
    r = measure([a, b], CFG, 25833)
    raw = road_length(r, "main_incl_motorway_raw")
    assert road_length(r, "main_excl_motorway") == pytest.approx(raw / 2, rel=0.01)
    assert len(r.dual_pairs) == 2
```

Add to `tests/test_cli.py`:

```python
from pathlib import Path


def test_classify_prints_tiers_roads_and_presets():
    fixture = Path(__file__).parent / "fixtures" / "measure" / "mini_city.osm"
    result = CliRunner().invoke(app, ["classify", "--file", str(fixture), "--epsg", "25833"])
    assert result.exit_code == 0, result.output
    for needle in ("A", "main_excl_motorway", "ours_headline", "skipped ways: 0"):
        assert needle in result.output
```

Run: `uv run pytest tests/test_measure.py tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError` / no such command.

- [ ] **Step 2: Implement `measure.py`**

```python
"""Aggregate classified way-sides into tier lengths, road lengths and preset metrics."""

from collections import Counter, defaultdict
from dataclasses import dataclass

from velometer.config import ClassifierConfig, Preset
from velometer.models import Metric, RoadLength, TierLength
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.dedupe import flag_parallel_duplicates, pair_dual_carriageways
from velometer.pipeline.geometry import Projector, length_km
from velometer.pipeline.types import Classified, DualPair, DuplicateFlag, WayRecord


@dataclass(frozen=True)
class MeasureResult:
    tier_lengths: list[TierLength]
    road_lengths: list[RoadLength]
    duplicates: list[DuplicateFlag]
    dual_pairs: list[DualPair]
    classified: list[Classified]
    unknown_values: dict[str, int]


def _public_roads(ways: list[WayRecord], cfg: ClassifierConfig) -> list[WayRecord]:
    rc = cfg.road_classes
    classes = set(rc.main) | set(rc.motorway) | set(rc.local)
    return [
        w for w in ways
        if w.tags.get("highway") in classes
        and w.tags.get("access") != "private"
        and w.tags.get("area") != "yes"
    ]


def measure(ways: list[WayRecord], cfg: ClassifierConfig, epsg: int) -> MeasureResult:
    proj = Projector(epsg)
    lengths = {w.id: length_km(proj.line(w.coords)) for w in ways}
    classified = classify_ways(ways, cfg)

    km: dict[tuple, float] = defaultdict(float)
    way_ids: dict[tuple, set[int]] = defaultdict(set)
    unknown: Counter[str] = Counter()
    for c in classified:
        if c.tier is None:
            if "unknown_value" in c.attrs:
                unknown[str(c.attrs["unknown_value"])] += 1
            continue
        length = lengths[c.side.way_id]
        weight = 1.0 if c.attrs["bidirectional"] else 0.5
        for basis, value in (("per_side", length), ("qecio_weighted", length * weight)):
            key = (c.tier, c.subtype, basis)
            km[key] += value
            way_ids[key].add(c.side.way_id)
    tier_lengths = [
        TierLength(tier=t, subtype=s, length_basis=b, length_km=v, n_ways=len(way_ids[(t, s, b)]))
        for (t, s, b), v in sorted(km.items(), key=lambda kv: (kv[0][0], kv[0][1] or "", kv[0][2]))
    ]

    rc = cfg.road_classes
    main, motorway = set(rc.main), set(rc.motorway)
    public = _public_roads(ways, cfg)
    factors, pairs = pair_dual_carriageways(public, main | motorway, proj)

    def total(highways: set[str], dedupe: bool) -> float:
        return sum(
            lengths[w.id] * (factors[w.id] if dedupe else 1.0)
            for w in public if w.tags["highway"] in highways
        )

    everything = main | motorway | set(rc.local)
    road_lengths = [
        RoadLength(road_class="main_excl_motorway", length_km=total(main, True)),
        RoadLength(road_class="main_incl_motorway", length_km=total(main | motorway, True)),
        RoadLength(road_class="main_incl_motorway_raw", length_km=total(main | motorway, False)),
        RoadLength(road_class="all_public", length_km=total(everything, True)),
    ]
    return MeasureResult(
        tier_lengths=tier_lengths,
        road_lengths=road_lengths,
        duplicates=flag_parallel_duplicates(classified, proj),
        dual_pairs=pairs,
        classified=classified,
        unknown_values=dict(unknown),
    )


def road_length(result: MeasureResult, road_class: str) -> float:
    return next(r.length_km for r in result.road_lengths if r.road_class == road_class)


def _selected(t: TierLength, entries: list[str]) -> bool:
    if t.tier == "excluded":
        return False
    for e in entries:
        tier, _, sub = e.partition("/")
        if t.tier == tier and (not sub or t.subtype == sub):
            return True
    return False


def compute_metrics(result: MeasureResult, presets: list[Preset]) -> list[Metric]:
    out = []
    for p in presets:
        num = sum(
            t.length_km for t in result.tier_lengths
            if t.length_basis == p.basis and _selected(t, p.tiers)
        )
        den = road_length(result, p.denominator)
        out.append(Metric(
            preset=p.id, length_basis=p.basis, value=(100 * num / den) if den else None,
            numerator_km=num, denominator_km=den,
        ))
    return out
```

- [ ] **Step 3: Add the `classify` command to `cli.py`**

```python
@app.command()
def classify(
    file: Path = typer.Option(..., exists=True, dir_okay=False, help=".osm or .osm.pbf"),
    epsg: int = typer.Option(..., help="Projected CRS for lengths (city EPSG)."),
    classifier: str = typer.Option("v1", help="Classifier version (config/classifier/<v>.yaml)."),
    config_dir: Path = typer.Option(default_config_dir(), help="Config directory."),
) -> None:
    """Classify one OSM file and print tier lengths, road lengths and preset metrics."""
    from velometer.config import load_classifier, load_presets
    from velometer.pipeline.measure import compute_metrics, measure
    from velometer.pipeline.read import read_ways

    try:
        cfg = load_classifier(config_dir / "classifier" / f"{classifier}.yaml")
        presets = load_presets(config_dir / "presets.yaml")
    except ConfigError as e:
        typer.echo(f"config error: {e}", err=True)
        raise typer.Exit(1) from e
    read = read_ways(file)
    result = measure(read.ways, cfg, epsg)
    typer.echo(f"classifier {cfg.version}  ways: {len(read.ways)}  skipped ways: {len(read.skipped)}")
    typer.echo("\ntier  subtype            basis            km       ways")
    for t in result.tier_lengths:
        typer.echo(f"{t.tier:<5} {t.subtype or '-':<18} {t.length_basis:<16} "
                   f"{t.length_km:>8.3f} {t.n_ways:>6}")
    typer.echo("\nroad class               km")
    for r in result.road_lengths:
        typer.echo(f"{r.road_class:<24} {r.length_km:>8.3f}")
    typer.echo("\npreset               value     num km   den km")
    for m in compute_metrics(result, presets):
        value = "n/a" if m.value is None else f"{m.value:.1f}"
        typer.echo(f"{m.preset:<20} {value:>7} {m.numerator_km:>9.3f} {m.denominator_km:>8.3f}")
    typer.echo(f"\nparallel duplicates flagged: {len(result.duplicates)}  "
               f"dual-carriageway ways: {len(result.dual_pairs)}")
    if result.unknown_values:
        typer.echo(f"unknown cycleway values: {result.unknown_values}")
```

- [ ] **Step 4: Run the full gate**

Run: `uv run ruff format . && uv run ruff check . && uv run pytest -v && uv run velometer classify --file tests/fixtures/measure/mini_city.osm --epsg 25833`
Expected: all PASS, and the CLI prints `ours_headline` ≈ 200.0.

- [ ] **Step 5: Commit**

```bash
git add src/velometer/pipeline/measure.py src/velometer/cli.py tests/test_measure.py tests/test_cli.py tests/fixtures/measure
git commit -m "feat: tier/road aggregation, preset metrics and velometer classify

Assisted-by: Claude:claude-opus-5-5"
```

---

### Task 8: Berlin golden set (fetch once), golden test, review sheet

**Files:**
- Create: `scripts/fetch_berlin_golden.py`, `scripts/render_golden_review.py`, `tests/fixtures/berlin_golden.osm` (generated), `tests/fixtures/berlin_golden.yaml` (generated), `tests/test_golden.py`, `docs/review/berlin_golden.md` (generated), `docs/review/berlin_golden.png` (generated)

**Interfaces:**
- Consumes: `read_ways`, `classify_ways`, `load_classifier`, `Projector`.
- Produces the `berlin_golden.yaml` schema:

```yaml
source: "Overpass API, fetched <ISO timestamp>; © OpenStreetMap contributors, ODbL 1.0"
classifier_version: v1
ways:
  - way_id: 123
    group: kantstrasse
    name: Kantstraße
    highway: primary
    proposed: [{side: right, tier: C, rule: C_lane_physical}]
    confirmed: false
    note: ""
```

- [ ] **Step 1: Write `scripts/fetch_berlin_golden.py`.** It uses httpx against `https://overpass-api.de/api/interpreter` with a User-Agent, in two phases.
  - **Phase 1** runs one id-only query per group inside `area["name"="Berlin"]["admin_level"="4"]->.b;`. Groups and caps:
    - `kantstrasse`: `way["name"="Kantstraße"]["highway"]`, cap 8;
    - `ollenhauerstrasse`: `way["name"="Ollenhauerstraße"]["highway"]`, cap 6;
    - `unter_den_eichen`: `way["name"="Unter den Eichen"]["highway"]`, cap 6;
    - `karl_marx_allee`: `way["name"="Karl-Marx-Allee"]["highway"]`, cap 6;
    - `fahrradstrasse`: `way["bicycle_road"="yes"]`, cap 4;
    - `hochbord_shared`: `way["highway"="footway"]["footway"="sidewalk"]["bicycle"="designated"]`, cap 4;
    - `sidewalk_cycleway`: `way["highway"="cycleway"]["cycleway"="sidewalk"]`, cap 4;
    - `protected_lane`: `way["cycleway:right:separation"]`, cap 4;
    - `busway`: `way[~"^cycleway(:both|:right|:left)?$"~"share_busway"]`, cap 4;
    - `separate`: `way["cycleway:both"="separate"]`, cap 4.
  - Each query ends `out ids;`. Take the ids sorted ascending and keep the first *cap*. The selection is deterministic for a given OSM state.
  - **Phase 2** runs one query `way(id:<all ids>); (._;>;); out meta;` and writes the XML response to `tests/fixtures/berlin_golden.osm`. Insert an XML comment with the attribution and the fetch timestamp after the `<?xml …?>` line.
  - It then runs `read_ways` + `classify_ways` with v1 and writes `berlin_golden.yaml`, listing only sides with a non-None tier in `proposed`. `confirmed` is false everywhere. The script prints counts per group and exits non-zero if the total is below 40.
  - The script never runs in pytest.

- [ ] **Step 2: Write `tests/test_golden.py`**

```python
from collections import defaultdict
from pathlib import Path

import pytest
import yaml

from velometer.config import default_config_dir, load_classifier
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.read import read_ways

FIX = Path(__file__).parent / "fixtures"
GOLDEN = yaml.safe_load((FIX / "berlin_golden.yaml").read_text())
CFG = load_classifier(default_config_dir() / "classifier" / "v1.yaml")


def _observed() -> dict[int, set[tuple]]:
    out: dict[int, set[tuple]] = defaultdict(set)
    for c in classify_ways(read_ways(FIX / "berlin_golden.osm").ways, CFG):
        if c.tier is not None:
            out[c.side.way_id].add((c.side.side, c.tier, c.rule_id))
    return out


def test_golden_set_is_large_enough_and_covers_named_streets():
    groups = {w["group"] for w in GOLDEN["ways"]}
    assert len(GOLDEN["ways"]) >= 40
    assert {"kantstrasse", "ollenhauerstrasse", "unter_den_eichen", "karl_marx_allee",
            "fahrradstrasse", "hochbord_shared"} <= groups


def test_every_golden_way_is_in_the_osm_fixture():
    ids = {w.id for w in read_ways(FIX / "berlin_golden.osm").ways}
    assert {w["way_id"] for w in GOLDEN["ways"]} <= ids


def test_confirmed_ways_match_classifier():
    confirmed = [w for w in GOLDEN["ways"] if w["confirmed"]]
    if not confirmed:
        pytest.skip(f"0/{len(GOLDEN['ways'])} golden ways confirmed yet (awaiting review)")
    obs = _observed()
    for w in confirmed:
        want = {(p["side"], p["tier"], p["rule"]) for p in w["proposed"]}
        assert obs[w["way_id"]] == want, (w["way_id"], w["name"])
```

- [ ] **Step 3: Write `scripts/render_golden_review.py`.** It reads both fixtures and writes two files.
  - **`docs/review/berlin_golden.md`:**
    - a header with the source and attribution, plus instructions: "set `confirmed: true` (and fix `proposed`) per way in `tests/fixtures/berlin_golden.yaml`";
    - a table per group with these columns: way (link `https://www.openstreetmap.org/way/<id>`), name, highway, key cycling tags (every tag starting with `cycleway`, `bicycle`, `foot`, `segregated`, `sidewalk`, `oneway`), and proposed sides as `side:tier (rule)`.
  - **`docs/review/berlin_golden.png`:** a matplotlib figure with each golden way projected to EPSG:25833 and coloured by its best tier (A dark green, B light green, C blue, D orange, E purple, excluded/None grey), with a legend, one subplot per group (a 3×4 grid) and titles. Use the default `Agg` backend.

- [ ] **Step 4: Run the fetch once (network; allowed host `overpass-api.de`), render, run the gate**

Run: `uv run python scripts/fetch_berlin_golden.py && uv run python scripts/render_golden_review.py && uv run ruff format . && uv run ruff check . && uv run pytest -v`
Expected: the fetch prints the group counts with a total ≥ 40. All tests pass; `test_confirmed_ways_match_classifier` SKIPS with "0/N golden ways confirmed yet".

- [ ] **Step 5: Look at the PNG and the markdown table.** Check that every group has ways, that the geometry looks like streets, and that tiers are plausible: Kantstraße shows C or E (pop-up lane or bus lane) and the Fahrradstraße shows E. List any surprising proposals in the task summary instead of changing rules.

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch_berlin_golden.py scripts/render_golden_review.py tests/test_golden.py tests/fixtures/berlin_golden.osm tests/fixtures/berlin_golden.yaml docs/review
git commit -m "feat: Berlin golden way set, golden test and review sheet (awaiting sign-off)

Assisted-by: Claude:claude-opus-5-5"
```

**STOP after Task 8 and the final review.** Dennis reviews `docs/review/berlin_golden.md` and confirms the tiers (handover M1 acceptance).
