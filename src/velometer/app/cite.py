"""Citation fields and the readable citation text (M11 spec decision 3).

The formatting rule lives twice: here (the text, for server-rendered pages) and in
`static/js/cite.js` (text, BibTeX and CSL-JSON, with the accessed date and URL of the moment).
Both are tested against `tests/cite_cases.json`.
"""

import re
from dataclasses import asdict, dataclass
from functools import cache

from velometer.reconcile import short_commit
from velometer.run import git_commit

ATTRIBUTION = "Map data © OpenStreetMap contributors, ODbL 1.0"
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class CiteFields:
    title: str
    path: str  # the page path without base, e.g. "/city/berlin/time"
    osm_timestamp: str | None  # ISO, from the run; None for multi-city views
    snapshot_note: str | None  # multi-city: "OSM snapshots of 2026-10-03 to 2026-10-05"
    classifier: str
    run_id: str | None
    commit: str
    attribution: str = ATTRIBUTION


@cache
def _commit() -> str:
    """The short commit, resolved once per process (git is not shelled out to per figure)."""
    return short_commit(git_commit())


def _natural(s: str) -> list:
    """Sort key where digit runs compare as numbers: v9 before v10."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", s)]


def json_fields(f: CiteFields) -> dict:
    """The fields as the page's `.cite-data` JSON holds them. The path loses its leading slash
    (`absoluteUrl` adds the base path and the slash): a root-relative string in a page's JSON is
    a URL the static export must find under the base (M9), and this one is not."""
    return {**asdict(f), "path": f.path.lstrip("/")}


def _pick(rows: list[dict], kind: str):
    """The `current` row of a boundary kind among `rows` (else the last), None without one."""
    rows = [r for r in rows if r["boundary_kind"] == kind]
    if not rows:
        return None
    current = [r for r in rows if r["label"] == "current"]
    return (current or rows)[-1]


def _current_row_of_kind(data, city_id: str, kind: str):
    """The city's `current` row for a boundary kind (else its last), None without a run."""
    return _pick(data.csv_rows(city_id), kind)


class RunRows:
    """The one row per (city, boundary kind) the citation fields read. A page builds many
    citations from one of these (cached with the page), since `csv_rows` is not free. It quacks
    like the part of ReportData the `fields_for_*` functions use."""

    def __init__(self, rows: dict[str, list[dict]]):
        self._rows = rows

    @classmethod
    def of(cls, data) -> "RunRows":
        rows: dict[str, list[dict]] = {}
        for c in data.cities():
            all_rows = data.csv_rows(c.id)
            kinds = sorted({r["boundary_kind"] for r in all_rows})
            rows[c.id] = [r for k in kinds if (r := _pick(all_rows, k)) is not None]
        return cls(rows)

    def csv_rows(self, city_id: str) -> list[dict]:
        return self._rows.get(city_id, [])

    def city_ids(self) -> list[str]:
        return list(self._rows)

    def runs(self, city_ids: list[str]) -> dict[str, dict[str, str]]:
        """{city: {osm_timestamp, classifier}} of each city's LAU run: what a browser needs to
        rebuild a multi-city citation when Compare changes its cities without a reload."""
        out = {}
        for c in city_ids:
            row = _current_row_of_kind(self, c, "lau")
            if row is not None:
                out[c] = {
                    "osm_timestamp": row["osm_timestamp"],
                    "classifier": row["classifier_version"],
                }
        return out


def fields_for_city(
    data, city_id: str, title: str, path: str, kind: str = "lau"
) -> CiteFields | None:
    """The citation fields of a city's run, or None when it has none for `kind`."""
    row = _current_row_of_kind(data, city_id, kind)
    if row is None:
        return None
    return CiteFields(
        title=title,
        path=path,
        osm_timestamp=row["osm_timestamp"],
        snapshot_note=None,
        classifier=row["classifier_version"],
        run_id=str(row["run_id"]),
        commit=_commit(),
    )


def fields_for_cities(data, city_ids: list[str], title: str, path: str) -> CiteFields | None:
    """Fields for several cities; runless cities are skipped, None when none has a run."""
    rows = [r for c in city_ids if (r := _current_row_of_kind(data, c, "lau")) is not None]
    if not rows:
        return None
    days = sorted(r["osm_timestamp"][:10] for r in rows)
    first, last = days[0], days[-1]
    note = f"OSM snapshot of {first}" if first == last else f"OSM snapshots of {first} to {last}"
    return CiteFields(
        title=title,
        path=path,
        osm_timestamp=None,
        snapshot_note=note,
        classifier="/".join(sorted({r["classifier_version"] for r in rows}, key=_natural)),
        run_id=None,
        commit=_commit(),
    )


def _year(f: CiteFields) -> str:
    if f.osm_timestamp:
        return f.osm_timestamp[:4]
    dates = _DATE.findall(f.snapshot_note or "")
    return dates[-1][:4] if dates else ""


def _snapshot(f: CiteFields) -> str:
    return f.snapshot_note or f"OSM snapshot {f.osm_timestamp}"


def _provenance(f: CiteFields) -> str:
    """`<snapshot>; classifier <v>; run <id>; commit <c>` (the run part only with a run)."""
    parts = [_snapshot(f), f"classifier {f.classifier}"]
    if f.run_id is not None:
        parts.append(f"run {f.run_id}")
    parts.append(f"commit {f.commit}")
    return "; ".join(parts)


def cite_text(f: CiteFields, accessed: str | None = None, url: str | None = None) -> str:
    text = f"velometer ({_year(f)}). {f.title} [Data set]. {_provenance(f)}. {f.attribution}."
    if url:
        text += f" {url}" + (f" (accessed {accessed})." if accessed else ".")
    return text
