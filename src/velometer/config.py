"""Load and validate YAML configuration (cities, classifier, presets)."""

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from velometer.pipeline.geometry import require_projected
from velometer.pipeline.match import validate_expr

Tier = Literal["A", "B", "C", "D", "E", "excluded"]
Basis = Literal["per_side", "qecio_weighted"]
RoadClass = Literal[
    "main_excl_motorway", "main_incl_motorway", "main_incl_motorway_raw", "all_public"
]


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
        return require_projected(v)


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


PLAIN_ONEWAY_MODES = ("traffic_side", "both_sides")


class ClassifierParameters(_Strict):
    """Tunable interpretation choices; every run reports the values it used."""

    # plain `cycleway=<v>` on a oneway road: the side where traffic flows (traffic_side,
    # usual OSM reading) or both sides (both_sides, literal "cycleway=* = both sides")
    plain_cycleway_on_oneway: Literal["traffic_side", "both_sides"] = "traffic_side"


class ClassifierConfig(_Strict):
    version: str
    parameters: ClassifierParameters = ClassifierParameters()
    road_classes: RoadClasses
    value_lists: dict[str, list[str]]
    rules: list[Rule]

    def with_parameters(self, **overrides: str) -> "ClassifierConfig":
        params = ClassifierParameters.model_validate({**self.parameters.model_dump(), **overrides})
        return self.model_copy(update={"parameters": params})

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


PRESET_TIERS = ("A", "B", "C", "D", "E")


class Preset(_Strict):
    """`tiers` entries: "X" = every subtype of tier X; "X/sub" = only that subtype (X in A-E)."""

    id: str
    tiers: list[str] = Field(min_length=1)
    basis: Basis
    denominator: RoadClass

    @field_validator("tiers")
    @classmethod
    def _grammar(cls, v: list[str]) -> list[str]:
        for entry in v:
            tier, slash, sub = entry.partition("/")
            if tier not in PRESET_TIERS or (slash and not sub):
                raise ValueError(f"tier entry {entry!r} must be one of A-E or '<tier>/<subtype>'")
        return v


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


def load_presets(path: Path, classifier: ClassifierConfig) -> list[Preset]:
    """Load presets; every "X/sub" entry must name a subtype that a tier-X rule produces."""
    presets = _parse(path, lambda d: [Preset.model_validate(p) for p in d["presets"]])
    produced = {(r.tier, r.subtype) for r in classifier.rules if r.subtype is not None}
    for p in presets:
        for entry in p.tiers:
            tier, _, sub = entry.partition("/")
            if sub and (tier, sub) not in produced:
                raise ConfigError(
                    f"{path}: preset {p.id!r}: no rule in classifier {classifier.version} "
                    f"produces tier {tier} subtype {sub!r} (entry {entry!r})"
                )
    return presets
