"""Plain data types passed between pipeline stages. No logic lives here."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class WayRecord:
    id: int
    tags: Mapping[str, str]
    coords: tuple[tuple[float, float], ...]  # (lon, lat)


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
    tier: str | None  # "A".."E", "excluded", or None (no rule matched)
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
    partner_ids: tuple[int, ...]  # opposite oneways within max_dist_m, sorted
    overlap_share: float  # share of the way within max_dist_m of all partners together
    partner_shares: tuple[float, ...]  # per partner (same order): share of the way near it
    partner_distances_m: tuple[float, ...]  # per partner: minimum distance to the way


@dataclass(frozen=True)
class ReadResult:
    ways: list[WayRecord]
    skipped: list[int]  # way ids with <2 resolvable nodes
