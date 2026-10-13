"""Load and validate YAML configuration (cities, classifier, presets)."""

import os
import re
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from velometer.i18n import Lang, t
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


class PopulationOverride(_Strict):
    """A cited national-statistics population, used only when GISCO LAU has none."""

    value: int = Field(gt=0)
    year: int = Field(ge=2000, le=2030)
    source: str  # e.g. "INSEE population légale 2022"
    source_url: str

    @field_validator("source")
    @classmethod
    def _source_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("population_override.source must name the statistic")
        return v

    @field_validator("source_url")
    @classmethod
    def _https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("population_override.source_url must start with https://")
        return v


# The derived "outside the subareas" row: city boundary minus the union of the subarea polygons
# (Berlin: the generalised LAU edge the 12 OSM Bezirke do not reach). Not a configured relation.
REMAINDER_ID = "remainder"
REMAINDER_NAME = "Outside the subareas (boundary edge)"
SUBAREA_SECTION = "Bezirke"  # the subarea section title of the app, CSV and change page


def remainder_label(n_subareas: int, section: str = SUBAREA_SECTION, lang: Lang = "en") -> str:
    """The remainder row's display name for a city with `n_subareas` configured relations, in
    `lang` (`subarea.remainder` of the UI catalogue for the Bezirk section)."""
    if section != SUBAREA_SECTION:
        return REMAINDER_NAME
    return t(lang, "subarea.remainder", n=n_subareas)


def subarea_display_name(names: dict[str, str], subarea_id: str, n_subareas: int) -> str:
    """A subarea's name from `names` (id -> name), the remainder's label, or the id itself."""
    if subarea_id == REMAINDER_ID:
        return remainder_label(n_subareas)
    return names.get(subarea_id, subarea_id)


class SubareaRelation(_Strict):
    id: int = Field(gt=0)
    name: str
    slug: str = Field(pattern=r"^[a-z0-9_]+$")  # unique within the city


class SubareasConfig(_Strict):
    """Sub-city areas (Berlin's Bezirke), assembled offline from OSM admin relations."""

    source: Literal["osm_admin"]
    admin_level: int
    relations: list[SubareaRelation] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> "SubareasConfig":
        for field in ("id", "slug"):
            values = [getattr(r, field) for r in self.relations]
            dup = sorted({v for v in values if values.count(v) > 1}, key=str)
            if dup:
                raise ValueError(f"subareas.relations: duplicate {field} {dup}")
        if any(r.slug == REMAINDER_ID for r in self.relations):
            raise ValueError(
                f"subareas.relations: slug {REMAINDER_ID!r} is reserved for the derived "
                "outside-the-subareas row"
            )
        return self


class CityConfig(_Strict):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    # The German exonym (Prag, Warschau): the name of the German edition; None: `name`. Display
    # data only, like the aliases
    name_de: str | None = None
    # Other names the search matches (the common English one): display data, not classifier input
    aliases: list[str] = []
    country_iso2: str = Field(pattern=r"^[A-Z]{2}$")
    epsg: int
    geofabrik_region: str
    osm_relation_id: int = Field(gt=0)
    lau_code: str | None = None
    # A city without one GISCO LAU polygon (Bratislava): the admin layer is the union of these
    # LAU polygons and its population the sum of their POP_2024. Exclusive with lau_code.
    lau_codes: list[str] | None = Field(default=None, min_length=2)
    fua_code: str | None = None
    nuts3_code: str | None = None  # NUTS3 unit for QECIO matching (may be larger than the city)
    # NUTS3 unit identical to the commune: the population fallback when LAU has none
    population_nuts3: str | None = None
    # "gisco": the LAU polygon; "osm_relation": the admin layer is built from osm_relation_id
    # (still stored as kind "lau"; population still comes from the GISCO LAU feature)
    admin_boundary: Literal["gisco", "osm_relation"] = "gisco"
    # Urban Audit city code (urb_cpop1): the population fallback when LAU has none and
    # population_nuts3 is unset
    population_urau: str | None = None
    # Cited national-statistics population (INSEE, INE); fills a gap in LAU, wins over NUTS3/URAU
    population_override: PopulationOverride | None = None
    # Reason for an EPSG that is not the UTM zone of the boundary centroid (only the adjacent
    # zone is accepted, see sources.boundaries.check_epsg)
    epsg_exception: str | None = None
    # BikeNetKit city id (file stem in bike_networks.zip); None = the city is not in BikeNetKit
    bikenetkit_id: str | None = None
    # Is the NUTS3 unit the city itself? None = not assessed. False adds a QECIO row caveat.
    nuts3_is_city: bool | None = None
    # Free-text caveat appended to the QECIO row notes of this city
    nuts3_note: str | None = None
    # Optional sub-city areas; None = the city has none
    subareas: SubareasConfig | None = None

    @field_validator("aliases")
    @classmethod
    def _aliases_not_blank(cls, v: list[str]) -> list[str]:
        if any(not a.strip() for a in v):
            raise ValueError("aliases: a blank alias")
        return v

    @field_validator("name_de")
    @classmethod
    def _name_de_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name_de must not be blank (omit it to use name)")
        return v

    @property
    def names(self) -> tuple[str, ...]:
        """Every form of the name a reader may search for: the name, the German one, the
        aliases (each once, in that order)."""
        names = [self.name, *([self.name_de] if self.name_de else []), *self.aliases]
        return tuple(dict.fromkeys(names))

    def display_name(self, lang: Lang) -> str:
        """The name a page in `lang` shows: the German exonym on German pages, else `name`."""
        return (self.name_de or self.name) if lang == "de" else self.name

    @model_validator(mode="after")
    def _one_lau_source(self) -> "CityConfig":
        if self.lau_code and self.lau_codes:
            raise ValueError("set lau_code or lau_codes, not both")
        if self.lau_codes and self.admin_boundary == "osm_relation":
            raise ValueError(
                "lau_codes (a union of LAU polygons) and admin_boundary: osm_relation are two "
                "admin layers; set one"
            )
        return self

    @field_validator("epsg_exception")
    @classmethod
    def _reason_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("epsg_exception must give a reason")
        return v

    @field_validator("epsg")
    @classmethod
    def _projected(cls, v: int) -> int:
        require_projected(v)
        if not 25828 <= v <= 25838:
            raise ValueError(f"EPSG:{v} is not ETRS89 / UTM 28N-38N (EPSG 25828-25838)")
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
    # separators between multiple values of one tag; v1 splits on `;` only (OSM convention),
    # v2 also on `,` (common mistagging such as `share_busway,track`)
    value_separators: list[str] = Field(default_factory=lambda: [";"], min_length=1)
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
    tag_drift_min_km: float


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

    @model_validator(mode="before")
    @classmethod
    def _report_classifier_moved(cls, data):
        if isinstance(data, dict) and "report_classifier" in data:
            raise ValueError(
                "report_classifier moved to config/report.yaml; remove it from history.yaml"
            )
        return data

    @model_validator(mode="after")
    def _has_default(self):
        if "default" not in self.required_kinds:
            raise ValueError("required_kinds needs a 'default' entry")
        return self

    @model_validator(mode="after")
    def _years_ordered(self):
        first, last = self.years.split("-")
        if int(last) < int(first):
            raise ValueError(f"years {self.years!r}: the last year is before the first")
        return self

    def required(self, city_id: str) -> list[str]:
        return self.required_kinds.get(city_id, self.required_kinds["default"])

    def year_range(self) -> range:
        """The series years, inclusive: "2018-2026" -> range(2018, 2027)."""
        first, last = self.years.split("-")
        return range(int(first), int(last) + 1)


def load_history(path: Path) -> HistoryConfig:
    return _parse(path, HistoryConfig.model_validate)


def require_de(obj: BaseModel, where: str, *fields: str) -> None:
    """Each English reader-prose `field` of `obj` that is set needs its German sibling
    `<field>_de` (M12): a ValueError naming the missing sibling and `where` it is missing."""
    for field in fields:
        if getattr(obj, field) is None:
            continue
        de = getattr(obj, f"{field}_de")
        if de is None or not str(de).strip():
            raise ValueError(f"{where}: {field}_de is required beside {field}")


def require_de_map(en: dict[str, str], de: dict[str, str], where: str) -> None:
    """A German map (`<field>_de`) mirrors its English map key for key."""
    missing, extra = sorted(set(en) - set(de)), sorted(set(de) - set(en))
    if missing or extra:
        raise ValueError(
            f"{where}_de must mirror {where} key for key (missing: {missing}, extra: {extra})"
        )
    blank = sorted(k for k, v in de.items() if not str(v).strip())
    if blank:
        raise ValueError(f"{where}_de: blank German text for {blank}")


class _RankingProse(_Strict):
    """The display text of a ranking row, in both languages."""

    id: str
    label: str
    label_de: str | None = None
    note: str | None = None
    note_de: str | None = None

    @model_validator(mode="after")
    def _german_siblings(self):
        require_de(self, f"ranking {self.id!r}", "label", "note")
        return self

    def label_in(self, lang: Lang) -> str:
        return (self.label_de or self.label) if lang == "de" else self.label

    def note_in(self, lang: Lang) -> str | None:
        return (self.note_de or self.note) if lang == "de" else self.note


class PresetRanking(_RankingProse):
    """A ranking row computed by us: a preset of config/presets.yaml."""

    kind: Literal["preset"]
    preset: str
    # the figure-source id this preset recomputes on our data (None: our own headline)
    recomputes: str | None = None


class ExternalRanking(_RankingProse):
    """A ranking row read from one stored external figure per city."""

    kind: Literal["external"]
    source: str
    metric: str
    scope: str


class ExternalRatioRanking(_RankingProse):
    """A ranking row that is a ratio of two stored external metrics of one source."""

    kind: Literal["external_ratio"]
    source: str
    numerator: list[str] = Field(min_length=1)
    denominator: str
    # format string over city config fields, e.g. "nuts3_{nuts3_code}"; a city whose field is
    # None has no value in this ranking
    scope: str


RankingSource = Annotated[
    PresetRanking | ExternalRanking | ExternalRatioRanking, Field(discriminator="kind")
]


class ChangeWindow(_Strict):
    """The default window of `report change`: two snapshot dates (1 January, where history runs
    sit), or `current` for the latest current run (decision 17)."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    from_: date = Field(alias="from")
    to: Literal["current"] | date = "current"

    @field_validator("from_", "to")
    @classmethod
    def _first_of_january(cls, v):
        if isinstance(v, date) and (v.month, v.day) != (1, 1):
            raise ValueError(
                f"{v} is not a 1 January snapshot date (history runs sit on 1 January)"
            )
        return v


DEFAULT_CHANGE_WINDOW = ChangeWindow(from_=date(2023, 1, 1), to="current")


class ReportConfig(_Strict):
    """Which classifier every report surface shows, and which ranking sources it lists."""

    report_classifier: str = Field(pattern=r"^v\d+$")
    rankings: list[RankingSource]
    # chart roles: a city in neither list is "other" (grey context lines)
    highlight: list[str] = ["berlin"]
    comparison_set: list[str] = []
    change_window: ChangeWindow = DEFAULT_CHANGE_WINDOW

    @model_validator(mode="after")
    def _roles_are_disjoint(self):
        both = sorted(set(self.highlight) & set(self.comparison_set))
        if both:
            raise ValueError(f"cities in both highlight and comparison_set: {both}")
        return self

    @model_validator(mode="after")
    def _roles_have_no_duplicates(self):
        for field in ("highlight", "comparison_set"):
            ids = getattr(self, field)
            dup = sorted({i for i in ids if ids.count(i) > 1})
            if dup:
                raise ValueError(f"duplicate ids in {field}: {dup}")
        return self

    @model_validator(mode="after")
    def _unique_ids(self):
        ids = [r.id for r in self.rankings]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"duplicate ranking ids: {dup}")
        return self


def _figure_source_ids(path: Path) -> set[str]:
    """The figure-source ids: the `source` of every config/organisations.yaml entry."""
    doc = _read(path)
    try:
        return {str(m["source"]) for m in doc}
    except (KeyError, TypeError) as e:
        raise ConfigError(f"{path}: expected a list of {{city, source, organisation}}: {e}") from e


def load_report(
    path: Path, presets_path: Path | None = None, cities_path: Path | None = None
) -> ReportConfig:
    """Load report.yaml; every preset ranking must name a preset of presets.yaml (default: the
    one beside it). With `cities_path`, every highlight / comparison_set id must be a city."""
    config = _parse(path, ReportConfig.model_validate)
    presets_path = presets_path or path.parent / "presets.yaml"
    known = {p.id for p in _parse(presets_path, PresetsConfig.model_validate).presets}
    for r in config.rankings:
        if isinstance(r, PresetRanking) and r.preset not in known:
            raise ConfigError(
                f"{path}: ranking {r.id!r}: preset {r.preset!r} is not in {presets_path.name} "
                f"(known: {sorted(known)})"
            )
    recomputing = [r for r in config.rankings if isinstance(r, PresetRanking) and r.recomputes]
    if recomputing:
        figure_sources = _figure_source_ids(path.parent / "organisations.yaml")
        for r in recomputing:
            if r.recomputes not in figure_sources:
                raise ConfigError(
                    f"{path}: ranking {r.id!r}: recomputes {r.recomputes!r} is not a figure "
                    f"source of organisations.yaml (known: {sorted(figure_sources)})"
                )
    if cities_path is not None:
        cities = {c.id for c in load_cities(cities_path)}
        for field in ("highlight", "comparison_set"):
            unknown = [i for i in getattr(config, field) if i not in cities]
            if unknown:
                raise ConfigError(
                    f"{path}: {field}: unknown city id {unknown[0]!r} (not in {cities_path.name})"
                )
    return config


class Limitation(BaseModel):
    """A known limitation; both languages are required and non-blank."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    en: str
    de: str

    @field_validator("en", "de")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()


class _LimitationsFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    limitations: list[Limitation] = Field(min_length=1)

    @field_validator("limitations")
    @classmethod
    def _unique(cls, v: list[Limitation]) -> list[Limitation]:
        ids = [x.id for x in v]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"duplicate limitation ids: {dup}")
        return v


def load_limitations(path: Path) -> list[Limitation]:
    """config/limitations.yaml; ConfigError (naming the file) when a language is missing."""
    return _parse(path, lambda d: _LimitationsFile.model_validate(d).limitations)


class TrustThresholds(_Strict):
    unrecognised_share_max: float = Field(gt=0, le=1)
    excluded_share_max: float = Field(gt=0, le=1)
    b_share_of_ab_max: float = Field(gt=0, le=1)
    boundary_diff_pct_max: float = Field(gt=0)


class CountryTrust(_Strict):
    status: Literal["pending", "trusted"]
    basis: str
    basis_de: str | None = None  # German wording of basis for methodology.de.md; None: basis
    pilot: str | None = None  # same-country pilot city for comparison
    golden: str | None = None  # "tests/fixtures/golden/<cc>" (no extension)
    # e.g. "v3"; required when golden is set and trusted; `trust check` holds every trusted
    # country to the report classifier (spec 3.3)
    classifier_reviewed: str | None = None
    signed_off: date | None = None  # required when golden is set and trusted

    @field_validator("basis_de")
    @classmethod
    def _basis_de_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("basis_de must not be blank (omit it to fall back to basis)")
        return v

    @model_validator(mode="after")
    def _golden_needs_signoff(self):
        if self.status == "trusted" and self.golden is not None:
            missing = [n for n in ("classifier_reviewed", "signed_off") if getattr(self, n) is None]
            if missing:
                raise ValueError(f"a trusted country with a golden set needs {', '.join(missing)}")
        return self


class TrustConfig(_Strict):
    thresholds: TrustThresholds
    countries: dict[str, CountryTrust]  # key: ISO2

    @field_validator("countries")
    @classmethod
    def _iso2_keys(cls, v):
        for key in v:
            if not re.fullmatch(r"[A-Z]{2}", key):
                raise ValueError(f"country key {key!r} is not an ISO 3166-1 alpha-2 code")
        return v


def load_trust(path: Path) -> TrustConfig:
    """config/trust.yaml; ConfigError when it is missing or invalid."""
    return _parse(path, TrustConfig.model_validate)


DIFFERENCE_DIMENSIONS = ("scope", "kind", "length", "date", "area", "method")


class Dimension(_Strict):
    id: str
    label: str
    label_de: str | None = None

    @model_validator(mode="after")
    def _german_label(self):
        require_de(self, f"dimensions {self.id!r}", "label")
        return self


class SourceLength(_Strict):
    theirs: str
    theirs_de: str | None = None
    matches: list[str]  # our bases (`bases` keys) that already are the source's

    @model_validator(mode="after")
    def _german_theirs(self):
        require_de(self, "source_length_bases", "theirs")
        return self


# the prose maps of differences.yaml; each has a German twin `<name>_de` with the same keys
DIFFERENCE_MAPS = (
    "ours", "metric_kinds", "source_methods", "length_bases", "bases", "labels", "areas",
    "source_names",
)  # fmt: skip


class DifferencesConfig(_Strict):
    """config/differences.yaml: why a published figure differs from our mapped km. Every prose
    value has a German sibling (`label_de`, `theirs_de`, the `<map>_de` maps); `localised("de")`
    is the same config with the German text in the English fields."""

    dimensions: list[Dimension]
    ours: dict[str, str]  # our side of each dimension (date: the run's snapshot, not listed)
    metric_kinds: dict[str, str]
    source_methods: dict[str, str]
    length_bases: dict[str, str]
    bases: dict[str, str]  # our basis id -> words
    source_length_bases: dict[str, SourceLength]  # "<source>/<metric>" -> the source's basis
    labels: dict[str, str]  # metric_name -> what it counts
    areas: dict[str, str]  # source id (or "default") -> the area it covers
    source_names: dict[str, str] = {}  # source id -> the name a reader knows it by
    ours_de: dict[str, str] = {}
    metric_kinds_de: dict[str, str] = {}
    source_methods_de: dict[str, str] = {}
    length_bases_de: dict[str, str] = {}
    bases_de: dict[str, str] = {}
    labels_de: dict[str, str] = {}
    areas_de: dict[str, str] = {}
    source_names_de: dict[str, str] = {}

    @model_validator(mode="after")
    def _dimensions(self):
        ids = tuple(d.id for d in self.dimensions)
        if ids != DIFFERENCE_DIMENSIONS:
            raise ValueError(f"dimension ids must be {DIFFERENCE_DIMENSIONS}, got {ids}")
        unknown = sorted(set(self.ours) - set(ids))
        if unknown:
            raise ValueError(f"ours names unknown dimensions: {unknown}")
        for key, sl in self.source_length_bases.items():
            bad = sorted(set(sl.matches) - set(self.bases))
            if bad:
                raise ValueError(f"source_length_bases {key!r} matches unknown bases: {bad}")
        return self

    @model_validator(mode="after")
    def _german_maps(self):
        for name in DIFFERENCE_MAPS:
            require_de_map(getattr(self, name), getattr(self, f"{name}_de"), name)
        return self

    def localised(self, lang: Lang) -> "DifferencesConfig":
        """This config with the `lang` text in the English fields (itself for English)."""
        if lang == "en":
            return self
        update: dict[str, Any] = {name: getattr(self, f"{name}_de") for name in DIFFERENCE_MAPS}
        update["dimensions"] = [
            d.model_copy(update={"label": d.label_de or d.label}) for d in self.dimensions
        ]
        update["source_length_bases"] = {
            k: sl.model_copy(update={"theirs": sl.theirs_de or sl.theirs})
            for k, sl in self.source_length_bases.items()
        }
        return self.model_copy(update=update)


def load_differences(path: Path) -> DifferencesConfig:
    """config/differences.yaml; ConfigError when it is missing or invalid."""
    return _parse(path, DifferencesConfig.model_validate)


def reader_prose(config_dir: Path) -> list[tuple[str, str, str]]:
    """`(where, en, de)` for every English reader-prose value of the config that has a German
    sibling: differences.yaml, the report.yaml rankings, plans.yaml, the counters.yaml `none`
    notes, the figures.csv notes and the cities.yaml German names. ConfigError when a file is
    invalid."""
    import csv

    from velometer.counters.model import COUNTERS_FILE, load_counters_config
    from velometer.plans.models import load_plans

    config_dir = Path(config_dir)
    out: list[tuple[str, str, str]] = []
    diffs = load_differences(config_dir / "differences.yaml")
    out += [
        (f"differences.yaml dimensions.{d.id}", d.label, d.label_de or "") for d in diffs.dimensions
    ]
    for name in DIFFERENCE_MAPS:
        de = getattr(diffs, f"{name}_de")
        out += [(f"differences.yaml {name}.{k}", v, de[k]) for k, v in getattr(diffs, name).items()]
    out += [
        (f"differences.yaml source_length_bases.{k}", sl.theirs, sl.theirs_de or "")
        for k, sl in diffs.source_length_bases.items()
    ]
    report = _parse(config_dir / "report.yaml", ReportConfig.model_validate)
    for r in report.rankings:
        out.append((f"report.yaml rankings.{r.id}.label", r.label, r.label_de or ""))
        if r.note is not None:
            out.append((f"report.yaml rankings.{r.id}.note", r.note, r.note_de or ""))
    plans, _rows = load_plans(config_dir / "plans")
    for p in plans:
        for field in ("title", "successor", "note"):
            en, de = getattr(p, field), getattr(p, f"{field}_de")
            if en is not None and de is not None:
                out.append((f"plans.yaml {p.id}.{field}", en, de))
        out += [(f"plans.yaml {p.id}.{i.id}.label", i.label, i.label_de or "") for i in p.items]
        out += [(f"plans.yaml {p.id}.{i.id}.unit", i.unit, i.unit_de) for i in p.items if i.unit_de]
    counters = load_counters_config(config_dir / COUNTERS_FILE)
    out += [
        (f"counters.yaml none.{n.city}.note", n.note, n.note_de or "")
        for n in counters.none
        if n.note is not None
    ]
    path = config_dir / "external" / "figures.csv"
    with path.open(newline="", encoding="utf-8") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            if row.get("note"):
                out.append((f"figures.csv row {line}", row["note"], row.get("note_de") or ""))
    out += [
        (f"cities.yaml {c.id}.name", c.name, c.name_de)
        for c in load_cities(config_dir / "cities.yaml")
        if c.name_de
    ]
    return out
