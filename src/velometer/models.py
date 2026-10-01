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
