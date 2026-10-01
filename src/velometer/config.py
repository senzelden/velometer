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
BASES: tuple[Basis, ...] = ("per_side", "qecio_weighted")
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
    nuts3_code: str | None = None  # NUTS3 unit for QECIO matching (may be larger than the city)
    # NUTS3 unit identical to the commune: the population fallback when LAU has none
    population_nuts3: str | None = None

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


class BasisRef(_Strict):
    """`{parameter: <name>}`: the length basis is read from the presets `parameters` block."""

    parameter: str


class PresetParameters(_Strict):
    """Report-time interpretation choices of the presets; every basis is computed and stored."""

    # Which length basis the Clean Cities figures are reported on. `per_side` counts each side
    # of a road once (ADR 0003, the recorded reading of Clean Cities' method). `qecio_weighted`
    # counts a road with infrastructure on both sides once (centreline-like), which is what
    # Clean Cities' published km match (docs/reconciliation.md, berlin/cc_km).
    clean_cities_basis: Basis = "per_side"

    def resolve(self, basis: "Basis | BasisRef") -> Basis:
        """The literal basis, or the value of the parameter it names."""
        if isinstance(basis, BasisRef):
            return getattr(self, basis.parameter)
        return basis

    def with_values(self, **overrides: str) -> "PresetParameters":
        return PresetParameters.model_validate({**self.model_dump(), **overrides})


def check_parameter_ref(basis: "Basis | BasisRef") -> None:
    """Raise ValueError when `{parameter: x}` names a parameter that does not exist."""
    if isinstance(basis, BasisRef) and basis.parameter not in PresetParameters.model_fields:
        known = ", ".join(PresetParameters.model_fields)
        raise ValueError(f"unknown parameter {basis.parameter!r} (known: {known})")


class Preset(_Strict):
    """`tiers` entries: "X" = every subtype of tier X; "X/sub" = only that subtype (X in A-E).

    A `basis` of `{parameter: name}` is computed on every basis and chosen at report time.
    """

    id: str
    tiers: list[str] = Field(min_length=1)
    basis: Basis | BasisRef
    denominator: RoadClass

    @field_validator("tiers")
    @classmethod
    def _grammar(cls, v: list[str]) -> list[str]:
        for entry in v:
            tier, slash, sub = entry.partition("/")
            if tier not in PRESET_TIERS or (slash and not sub):
                raise ValueError(f"tier entry {entry!r} must be one of A-E or '<tier>/<subtype>'")
        return v

    @field_validator("basis")
    @classmethod
    def _known_parameter(cls, v: "Basis | BasisRef") -> "Basis | BasisRef":
        check_parameter_ref(v)
        return v

    @property
    def parameterised(self) -> bool:
        return isinstance(self.basis, BasisRef)


class PresetsConfig(_Strict):
    parameters: PresetParameters = PresetParameters()
    presets: list[Preset]

    def with_parameters(self, **overrides: str) -> "PresetsConfig":
        return self.model_copy(update={"parameters": self.parameters.with_values(**overrides)})

    def preset(self, preset_id: str) -> Preset:
        for p in self.presets:
            if p.id == preset_id:
                return p
        raise KeyError(f"no preset {preset_id!r}")


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


def load_presets(path: Path, classifier: ClassifierConfig) -> PresetsConfig:
    """Load presets and their parameters; every "X/sub" entry must name a produced subtype."""
    config = _parse(path, PresetsConfig.model_validate)
    produced = {(r.tier, r.subtype) for r in classifier.rules if r.subtype is not None}
    for p in config.presets:
        for entry in p.tiers:
            tier, _, sub = entry.partition("/")
            if sub and (tier, sub) not in produced:
                raise ConfigError(
                    f"{path}: preset {p.id!r}: no rule in classifier {classifier.version} "
                    f"produces tier {tier} subtype {sub!r} (entry {entry!r})"
                )
    return config


class CyclingKeys(_Strict):
    exact: list[str]
    prefixes: list[str]
    highway_values: list[str]


class LegacyConfig(_Strict):
    rules: list[str]
    value_prefixes: dict[str, str]


class FlagThresholds(_Strict):
    km_jump_pct: float
    km_jump_min_km: float
    activity_spike_factor: float
    single_mapper_share: float
    tag_drift_pct: float


class ActivityConfig(_Strict):
    cycling_keys: CyclingKeys
    legacy: LegacyConfig
    flags: FlagThresholds


def load_activity(path: Path) -> ActivityConfig:
    return _parse(path, ActivityConfig.model_validate)


class HistoryConfig(_Strict):
    """Which yearly history series exist and which boundary kinds each city must have."""

    years: str = Field(pattern=r"^\d{4}-\d{4}$")
    required_kinds: dict[str, list[str]]

    @model_validator(mode="after")
    def _has_default(self):
        if "default" not in self.required_kinds:
            raise ValueError("required_kinds needs a 'default' entry")
        return self

    def required(self, city_id: str) -> list[str]:
        return self.required_kinds.get(city_id, self.required_kinds["default"])


def load_history(path: Path) -> HistoryConfig:
    return _parse(path, HistoryConfig.model_validate)
