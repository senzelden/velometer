"""Plan targets (`config/plans/plans.yaml`) and the figures printed in progress documents
(`config/plans/reports.csv`), stored as printed (M8 spec §2.8, §4.1).

Two documents that disagree for the same plan item, year and quantity are both kept: the one
with the later `doc_date` is current, the others are revisions (`current_and_revisions`).
"""

import csv
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from velometer.config import ConfigError, require_de
from velometer.i18n import Lang

PLANS_FILE = "plans.yaml"
# The day "mapped on the network" is counted from: the comparable quantity is the change since
# 1 January 2022, not the level (M8 spec decision 9, §4.4)
MAPPED_BASELINE = date(2022, 1, 1)
REPORTS_FILE = "reports.csv"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PlanItem(_Strict):
    id: str
    label: str
    label_de: str | None = None  # required beside `label` (M12)
    target_kind: Literal["km_per_year", "km_cumulative", "km_total", "share", "none"]
    targets: dict[int, float] = {}
    unit: str = "km"
    unit_de: str | None = None  # a German unit only where `unit` is an English word

    @model_validator(mode="after")
    def _german_label(self) -> "PlanItem":
        require_de(self, f"item {self.id!r}", "label")
        return self


class Plan(_Strict):
    id: str
    city: str
    title: str
    # a German title only where the title holds English words; a document's own title stays
    title_de: str | None = None
    adopted: date | None
    url: str
    status: Literal["current", "expired", "replaced"]
    successor: str | None = None
    successor_de: str | None = None  # as title_de: only where the successor has English words
    publisher: str
    items: list[PlanItem]
    note: str | None = None
    note_de: str | None = None  # required beside `note` (M12)

    @model_validator(mode="after")
    def _unique_items(self) -> "Plan":
        ids = [i.id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate item id in plan {self.id}")
        return self

    @model_validator(mode="after")
    def _german_note(self) -> "Plan":
        require_de(self, f"plan {self.id!r}", "note")
        return self

    def localised(self, lang: Lang) -> "Plan":
        """This plan with the `lang` text in the English fields (itself for English)."""
        if lang == "en":
            return self
        return self.model_copy(
            update={
                "title": self.title_de or self.title,
                "successor": self.successor_de or self.successor,
                "note": self.note_de or self.note,
                "items": [
                    i.model_copy(
                        update={"label": i.label_de or i.label, "unit": i.unit_de or i.unit}
                    )
                    for i in self.items
                ],
            }
        )


class ReportRow(_Strict):
    plan_id: str
    item_id: str
    year: int
    value: float
    unit: str
    quantity: Literal[
        "implemented_in_year", "implemented_cumulative", "under_construction", "in_planning"
    ]
    doc_type: Literal["drucksache", "rote_nummer", "report", "web"]
    doc_id: str
    doc_date: date
    url: str
    locator: str
    retrieved_at: date
    note: str | None = None
    publisher: str
    suspect: bool = False
    cumulative_from: int | None = None


REPORT_COLUMNS = tuple(ReportRow.model_fields)
OPTIONAL_COLUMNS = ("suspect", "cumulative_from")  # a file may omit these trailing columns
DOC_TYPE_RANK = {"drucksache": 0, "rote_nummer": 0, "report": 1, "web": 2}

RowKey = tuple[str, str, int, str, int | None]  # plan, item, year, quantity, cumulative_from


def _load_plan_list(path: Path) -> list[Plan]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError(f"{path}: {e}") from e
    if not isinstance(raw, list):
        raise ConfigError(f"{path}: expected a list of plans")
    plans: list[Plan] = []
    for entry in raw:
        try:
            plans.append(Plan.model_validate(entry))
        except ValidationError as e:
            raise ConfigError(f"{path}: {e}") from e
    ids = [p.id for p in plans]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ConfigError(f"{path}: duplicate plan id {', '.join(dupes)}")
    return plans


def _load_reports(path: Path) -> list[ReportRow]:
    try:
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            header = tuple(reader.fieldnames or ())
            if header not in (REPORT_COLUMNS, REPORT_COLUMNS[: -len(OPTIONAL_COLUMNS)]):
                raise ConfigError(
                    f"{path}: header must be {','.join(REPORT_COLUMNS)}, got {','.join(header)}"
                )
            rows: list[ReportRow] = []
            for line, rec in enumerate(reader, start=2):
                values = {k: (v if v != "" else None) for k, v in rec.items()}
                for name in ("note", "suspect"):
                    if name in values and values[name] is None:
                        del values[name]
                try:
                    rows.append(ReportRow.model_validate(values))
                except ValidationError as e:
                    raise ConfigError(f"{path}:{line}: {e}") from e
    except OSError as e:
        raise ConfigError(f"{path}: {e}") from e
    return rows


def load_plans(dir: Path) -> tuple[list[Plan], list[ReportRow]]:
    """The plans and report rows of `dir` (`plans.yaml`, `reports.csv`); ConfigError naming the
    file on any problem."""
    dir = Path(dir)
    return _load_plan_list(dir / PLANS_FILE), _load_reports(dir / REPORTS_FILE)


def current_and_revisions(
    rows: list[ReportRow],
) -> dict[RowKey, tuple[ReportRow, list[ReportRow]]]:
    """Per (plan, item, year, quantity, cumulative_from), so cumulative figures counted from
    different start years are separate series, not revisions: the current row and the other rows
    as revisions, best first. Preference: a non-suspect row over a suspect one, then the latest
    `doc_date`, then on equal dates drucksache = rote_nummer over report over web, then the later
    row in file order."""
    groups: dict[RowKey, list[ReportRow]] = {}
    for r in rows:
        groups.setdefault((r.plan_id, r.item_id, r.year, r.quantity, r.cumulative_from), []).append(
            r
        )

    def preference(ir: tuple[int, ReportRow]) -> tuple:
        i, r = ir
        return (not r.suspect, r.doc_date, -DOC_TYPE_RANK[r.doc_type], i)

    out: dict[RowKey, tuple[ReportRow, list[ReportRow]]] = {}
    for key, group in groups.items():
        ordered = sorted(enumerate(group), key=preference, reverse=True)
        out[key] = (ordered[0][1], [r for _, r in ordered[1:]])
    return out
