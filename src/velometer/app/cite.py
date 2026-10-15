"""Citation fields and the readable citation text (M11 spec decision 3).

The formatting rule lives twice: here (the text, for server-rendered pages) and in
`static/js/cite.js` (text, BibTeX and CSL-JSON, with the accessed date and URL of the moment).
Both are tested against `tests/cite_cases.json`, which has cases per language (M12): the words
come from the UI catalogue (`cite.*` here, `js.cite.*` in the browser).
"""

import re
from dataclasses import asdict, dataclass
from functools import cache

from velometer.i18n import Lang, t
from velometer.reconcile import short_commit
from velometer.run import git_commit

ATTRIBUTION = t("en", "cite.attribution")
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
    attribution: str = ATTRIBUTION  # the page's language: `fields_for_*` set it


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

    def runs(self, city_ids: list[str], kind: str = "lau") -> dict[str, dict[str, str]]:
        """{city: {osm_timestamp, classifier}} of each city's run of a boundary kind: what a
        browser needs to rebuild a multi-city citation when Compare changes its cities or its
        boundary without a reload."""
        out = {}
        for c in city_ids:
            row = _current_row_of_kind(self, c, kind)
            if row is not None:
                out[c] = {
                    "osm_timestamp": row["osm_timestamp"],
                    "classifier": row["classifier_version"],
                }
        return out


def fields_for_city(
    data, city_id: str, title: str, path: str, kind: str = "lau", lang: Lang = "en"
) -> CiteFields | None:
    """The citation fields of a city's run, or None when it has none for `kind`; the
    attribution in `lang`."""
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
        attribution=t(lang, "cite.attribution"),
    )


def fields_for_city_runs(
    data,
    city_id: str,
    title: str,
    path: str,
    kinds: tuple[str, str] = ("lau", "fua"),
    lang: Lang = "en",
) -> CiteFields | None:
    """The citation fields of a figure drawn from two runs of one city (the headline chart's LAU
    and FUA lines): the snapshot note names each boundary's run and OSM snapshot, in `kinds`
    order; there is no single run id or timestamp. None unless the city has a run of both."""
    rows = [_current_row_of_kind(data, city_id, k) for k in kinds]
    if any(r is None for r in rows):
        return None
    (a, row_a), (b, row_b) = zip(kinds, rows, strict=True)
    note = t(lang, "cite.snapshot_two", kind_a=a.upper(), run_a=row_a["run_id"],
             ts_a=row_a["osm_timestamp"], kind_b=b.upper(), run_b=row_b["run_id"],
             ts_b=row_b["osm_timestamp"])  # fmt: skip
    return CiteFields(
        title=title,
        path=path,
        osm_timestamp=None,
        snapshot_note=note,
        classifier="/".join(
            sorted({r["classifier_version"] for r in (row_a, row_b)}, key=_natural)
        ),
        run_id=None,
        commit=_commit(),
        attribution=t(lang, "cite.attribution"),
    )


def fields_for_cities(
    data, city_ids: list[str], title: str, path: str, kind: str = "lau", lang: Lang = "en"
) -> CiteFields | None:
    """Fields for several cities' runs of a boundary kind; runless cities are skipped, None when
    none has a run. The snapshot note and the attribution are in `lang`."""
    rows = [r for c in city_ids if (r := _current_row_of_kind(data, c, kind)) is not None]
    if not rows:
        return None
    days = sorted(r["osm_timestamp"][:10] for r in rows)
    first, last = days[0], days[-1]
    if first == last:
        note = t(lang, "cite.snapshot_one", day=first)
    else:
        note = t(lang, "cite.snapshot_range", first=first, last=last)
    return CiteFields(
        title=title,
        path=path,
        osm_timestamp=None,
        snapshot_note=note,
        classifier="/".join(sorted({r["classifier_version"] for r in rows}, key=_natural)),
        run_id=None,
        commit=_commit(),
        attribution=t(lang, "cite.attribution"),
    )


def _year(f: CiteFields) -> str:
    if f.osm_timestamp:
        return f.osm_timestamp[:4]
    dates = _DATE.findall(f.snapshot_note or "")
    return dates[-1][:4] if dates else ""


def _provenance(f: CiteFields, lang: Lang) -> str:
    """`<snapshot>; classifier <v>; run <id>; commit <c>` (the run part only with a run)."""
    snapshot = f.snapshot_note or t(lang, "cite.snapshot", timestamp=f.osm_timestamp)
    parts = [snapshot, t(lang, "cite.classifier", version=f.classifier)]
    if f.run_id is not None:
        parts.append(t(lang, "cite.run", run=f.run_id))
    parts.append(t(lang, "cite.commit", commit=f.commit))
    return "; ".join(parts)


def cite_text(
    f: CiteFields, accessed: str | None = None, url: str | None = None, lang: Lang = "en"
) -> str:
    """The readable citation in `lang`, ending with the page's address (and the accessed date)
    when there is one."""
    text = t(lang, "cite.text", year=_year(f), title=f.title, provenance=_provenance(f, lang),
             attribution=f.attribution)  # fmt: skip
    if url:
        text += " " + (
            t(lang, "cite.accessed", url=url, accessed=accessed) if accessed else f"{url}."
        )
    return text
