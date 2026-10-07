"""Normalised counter records and `config/counters.yaml` (M8 spec §5).

Adapters turn each portal's files into `Site` plus either `HourCount` (hourly portals) or
`DayCount` (daily portals). `HourCount.local_hour` is the naive local wall-clock hour in the
entry's timezone; the second occurrence of the repeated hour on a fall-back day carries
`fold=1` (PEP 495), the first and every other hour `fold=0`.
"""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from velometer.config import ConfigError

COUNTERS_FILE = "counters.yaml"

Grain = Literal["hourly", "daily", "monthly"]


@dataclass(frozen=True, slots=True)
class Site:
    site_id: str
    name: str
    lat: float | None
    lon: float | None


@dataclass(frozen=True, slots=True)
class HourCount:
    site_id: str
    local_hour: datetime  # naive local wall clock; fold=1 on the repeated fall-back hour
    count: int


@dataclass(frozen=True, slots=True)
class DayCount:
    site_id: str
    day: date
    count: int
    complete: bool


class CounterFormatError(Exception):
    """A portal file lacks a sheet or column the adapter needs, or holds a value it cannot
    read; the message names the file and what is missing."""

    def __init__(self, path: Path | str, detail: str):
        self.path = Path(path)
        self.detail = detail
        super().__init__(f"{path}: {detail}")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CounterEntry(_Strict):
    """One city's counter portal."""

    city: str
    adapter: str
    source: str  # the publishing body, as shown in the attribution line
    licence: str
    licence_url: str
    page: str  # the dataset's portal page
    urls: list[str] = Field(min_length=1)  # the files `counters fetch` downloads, in load order
    timezone: str
    grain: Grain
    base_year: int = 2019  # spec §2.13
    # a portal id -> the canonical site id (a site renumbered between yearly sheets)
    site_aliases: dict[str, str] = {}
    # columns that aggregate other columns of the same file (counted twice if kept)
    exclude_columns: list[str] = []

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"unknown timezone {v!r}") from e
        return v


class NoCounterData(_Strict):
    """A city without an open, licensed counter dataset, and the portals checked."""

    city: str
    checked: list[str] = Field(min_length=1)
    note: str | None = None


class CountersConfig(_Strict):
    cities: list[CounterEntry]
    none: list[NoCounterData]

    @model_validator(mode="after")
    def _unique_cities(self) -> "CountersConfig":
        ids = [c.city for c in self.cities] + [n.city for n in self.none]
        dup = sorted({c for c in ids if ids.count(c) > 1})
        if dup:
            raise ValueError(f"city listed more than once: {', '.join(dup)}")
        return self

    def entry(self, city: str) -> CounterEntry:
        for c in self.cities:
            if c.city == city:
                return c
        raise ConfigError(f"{COUNTERS_FILE}: no counter portal for city {city!r}")


def load_counters_config(path: Path) -> CountersConfig:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError(f"{path}: {e}") from e
    try:
        return CountersConfig.model_validate(raw)
    except ValidationError as e:
        raise ConfigError(f"{path}: {e}") from e
