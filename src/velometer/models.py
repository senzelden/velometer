"""Persisted records (handover §7, with ADR 0002/0003 additions). Mirrored in db.py."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from velometer.config import Basis, RoadClass


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Population(_Model):
    value: int = Field(gt=0)
    year: int
    source: str


class City(_Model):
    id: str
    name: str
    country_iso2: str
    lau_code: str | None = None
    fua_code: str | None = None
    nuts3_code: str | None = None  # NUTS3 unit used for QECIO matching
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
    city_id: str
    started_at: datetime
    finished_at: datetime | None = None
    classifier_version: str
    classifier_parameters: str  # canonical JSON (sorted keys)
    git_commit: str
    osm_timestamp: str
    region_md5: str
    boundary_kind: Literal["lau", "fua", "osm_admin", "none"]
    boundary_sha256: str
    status: Literal["running", "done", "failed"]
    error: str | None = None


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
    per_100k: float | None = None  # preset numerator km per 100k residents


class Completeness(_Model):
    run_id: int | None = None
    city_id: str | None = None
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


class ActivityYear(_Model):
    """One year of OSM editing activity inside a city boundary. Aggregates only: no mapper ids."""

    city_id: str
    boundary_kind: str
    year: int
    history_set_md5: str
    n_edits: int
    n_changesets: int
    n_mappers: int
    top_mapper_share: float
    n_ways_created_cycling: int
    n_ways_deleted_cycling: int
