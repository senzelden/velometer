"""Normalised counter records and `config/counters.yaml` (M8 spec §5).

Adapters turn each portal's files into `Site` plus `HourCount` (hourly portals), `DayCount`
(daily portals) or `MonthValue` (monthly portals: Barcelona). `HourCount.local_hour` is the
naive local wall-clock hour in the entry's timezone; the second occurrence of the repeated hour
on a fall-back day carries `fold=1` (PEP 495), the first and every other hour `fold=0`.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from velometer.config import ConfigError, require_de
from velometer.content.models import bracket_lang, name_lang
from velometer.i18n import Lang

COUNTERS_FILE = "counters.yaml"
DEFAULT_BASE_YEAR = 2019  # the index base year (= 100) unless an entry names another (§2.13)
COVID_YEAR = 2020  # marked on every counter chart (spec decision 12)
MIN_LINE_YEARS = 2  # years with a value an index needs to be drawn as a line (user ruling, Task 8)


def has_line(values) -> bool:
    """Whether an index with these yearly values (None: no value) is drawn as a line: at least
    `MIN_LINE_YEARS` years with a value. The Counts tab, Compare and the methodology."""
    return sum(v is not None for v in values) >= MIN_LINE_YEARS


GAP_DAYS = 31  # a run of days without any count longer than this is a gap in the data
# the counter index rule readers show (M13 spec §4.2): v2 pools counts per complete day; the
# stored v1 rows (M8-M12: summed counts) feed only the methodology's v1->v2 table
INDEX_METHOD = "v2"
INDEX_METHODS = ("v1", "v2")

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
    counters: int = 1  # counters that reported the hour (a summed site-hour: how many were summed)


@dataclass(frozen=True, slots=True)
class DayCount:
    site_id: str
    day: date
    count: int
    complete: bool


@dataclass(frozen=True, slots=True)
class MonthValue:
    site_id: str
    month: str  # YYYY-MM
    day_type: str  # e.g. working_day; the portal's day types, normalised
    avg_daily: float  # the portal's average daily value for that month and day type


def data_gaps(days: list[DayCount]) -> list[tuple[str, str]]:
    """Runs of more than GAP_DAYS days without a count at any site, inside the data's span, as
    (first, last) ISO days of each run."""
    seen = sorted({d.day for d in days})
    out = []
    for a, b in zip(seen, seen[1:], strict=False):
        if (b - a).days - 1 > GAP_DAYS:
            out.append(((a + timedelta(days=1)).isoformat(), (b - timedelta(days=1)).isoformat()))
    return out


class CounterFormatError(Exception):
    """A portal file lacks a sheet or column the adapter needs, or holds a value it cannot
    read; the message names the file and what is missing."""

    def __init__(self, path: Path | str, detail: str):
        self.path = Path(path)
        self.detail = detail
        super().__init__(f"{path}: {detail}")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StepDown(_Strict):
    """A site whose counts step down while it keeps counting, from `since` (YYYY-MM): our
    reading of the daily data, not a sourced claim. Used only for the Counts tab's note, which
    gives the index without the site from that year on; the stored index keeps it (spec §2.13,
    user ruling 2026-10-07)."""

    site: str
    since: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class CounterEntry(_Strict):
    """One city's counter portal."""

    city: str
    adapter: str
    source: str  # the publishing body, as shown in the attribution line
    # the German attribution, only where `source` holds our English words beside the name
    # (Oslo's "(state counters)"); a publisher's own name is not translated (M12)
    source_de: str | None = None
    # the language of `source` (BCP 47) where it is the body's own name (an original-language
    # form in brackets beside it shares it), written as its `lang` (M12-1); not used for source_de
    source_lang: str | None = None
    # the language of the bracketed form ending `source` where it is not `source_lang`
    # (Helsinki's Finnish name beside the English one; review 10, I1); not used for source_de
    source_bracket_lang: str | None = None
    licence: str
    licence_url: str
    page: str  # the dataset's portal page
    urls: list[str] = Field(min_length=1)  # the files `counters fetch` downloads, in load order
    timezone: str
    grain: Grain
    base_year: int = DEFAULT_BASE_YEAR  # spec §2.13
    # a portal id -> the canonical site id (Berlin: a site renumbered between yearly sheets;
    # Helsinki: the two sides of a bridge, summed, whose counts move between columns)
    site_aliases: dict[str, str] = {}
    # columns that aggregate other columns of the same file (counted twice if kept)
    exclude_columns: list[str] = []
    # sites outside the city's stored boundary of this kind (data/boundaries/<city>_<kind>.geojson)
    # are dropped, with their counts (Oslo: state counters, county-wide query)
    boundary: Literal["lau"] | None = None
    step_downs: list[StepDown] = []
    # a clause the methodology adds after the gaps of a city drawn without an index line, in
    # the portal's words as we read them (Madrid: "while the detectors were changed"); the German
    # clause is required beside it (M12)
    note: str | None = None
    note_de: str | None = None

    @model_validator(mode="after")
    def _german_note(self) -> "CounterEntry":
        require_de(self, f"city {self.city!r}", "note")
        return self

    @model_validator(mode="after")
    def _source_bracket_lang(self) -> "CounterEntry":
        bracket_lang(self.source_bracket_lang, self.source, "source_bracket_lang")
        return self

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"unknown timezone {v!r}") from e
        return v

    def source_in(self, lang: Lang) -> str:
        return (self.source_de or self.source) if lang == "de" else self.source

    def source_lang_in(self, lang: Lang) -> str | None:
        """The `lang` of what `source_in(lang)` shows: none for our German `source_de`."""
        return None if lang == "de" and self.source_de else self.source_lang

    def source_bracket_lang_in(self, lang: Lang) -> str | None:
        """The language of the bracket in what `source_in(lang)` shows: none for `source_de`."""
        return None if lang == "de" and self.source_de else self.source_bracket_lang

    @field_validator("source_lang")
    @classmethod
    def _source_lang(cls, v: str | None) -> str | None:
        return name_lang(v, "source_lang")


class NoCounterData(_Strict):
    """A city without an open, licensed counter dataset, and the portals checked."""

    city: str
    checked: list[str] = Field(min_length=1)
    # the portals in German, only where `checked` holds our English words (M12)
    checked_de: list[str] | None = None
    note: str | None = None
    note_de: str | None = None  # the German note, required beside `note` (M12)

    @model_validator(mode="after")
    def _german_note(self) -> "NoCounterData":
        require_de(self, f"none {self.city!r}", "note")
        if self.checked_de is not None and len(self.checked_de) != len(self.checked):
            raise ValueError(f"none {self.city!r}: checked_de must list each portal of checked")
        return self

    def note_in(self, lang: Lang) -> str | None:
        return (self.note_de or self.note) if lang == "de" else self.note

    def checked_in(self, lang: Lang) -> list[str]:
        return (self.checked_de or self.checked) if lang == "de" else self.checked


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
