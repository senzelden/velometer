"""The /sources page: one row per figure source, plus the row for our own figures.

A figure source is a source id of `config/organisations.yaml` (M11 spec decision 1, as ruled):
one row per (source, organisation) entry there, its six dimension cells from that
organisation's "How they measure" `dimensions`, rendered with one citation numbering over the
whole page so the page ends with a single list of the sources it cites. A `city: "*"` entry is a
cross-city ranking or dataset; any other entry is a city source.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path

from markupsafe import Markup

from velometer.app.narrative import _Numbering, _route
from velometer.app.organisations import org_of_sources
from velometer.config import load_differences
from velometer.content.loader import load_organisation_map, load_organisations, load_sources
from velometer.content.models import DataRef, Source
from velometer.i18n import Lang, t
from velometer.report.data import ReportData
from velometer.report.differences import difference_rows

GROUPS = ("ours", "ranking", "city")  # the table's row groups, in page order
CITE_PREFIX = "cite-"  # the page's citation anchors (`cite-src-<n>`), apart from `src-<id>` rows


def group_name(group: str, lang: Lang = "en") -> str:
    """A row group's heading."""
    if group == "ours":
        return t(lang, "sources.ours")
    if group == "ranking":
        return t(lang, "sources.rankings")
    return t(lang, "sources.city")


def _missing_cell(lang: Lang) -> Markup:
    return Markup('<span class="note">{}</span>').format(t(lang, "sources.missing_cell"))


def source_anchor(source_id: str | None) -> str:
    """The /sources fragment of a source row; `ours` is the row for our own figures."""
    return "ours" if source_id is None else f"src-{source_id}"


def overview_column(preset_id: str) -> str:
    """The id of a preset's column in the overview's key-numbers table."""
    return f"col-{preset_id}"


@dataclass(frozen=True)
class SourceRow:
    source_id: str | None  # None for "Our approach"
    anchor: str  # source_anchor(source_id), suffixed with the organisation when it has several
    title: str  # differences.source_names[source_id] (or "Our approach")
    organisation_id: str | None
    organisation_name: str | None
    group: str  # "ours" | "ranking" | "city"
    cells: dict[str, Markup]  # dimension id -> rendered prose with citation markers
    cities: list[tuple[str, str]]  # (city id, city name) whose Figures tab quotes it
    recomputed_anchor: str | None  # the overview key-numbers column id, else None
    city_name: str | None = None  # the city of a city source (its sort key)
    recomputed_label: str | None = None  # that overview column's own header label


@dataclass
class CitedSources:
    """The page's one citation list, in the shape `city/_cited.html` reads (`nar`)."""

    sources: list[tuple[int, Source]] = field(default_factory=list)
    refs: list[tuple[int, DataRef]] = field(default_factory=list)
    prefix: str = CITE_PREFIX
    ref_links: dict[int, str | None] = field(default_factory=dict)


def order_rows(rows: list) -> list:
    """Ours first, then the rankings by title, then the city sources by city name."""
    rank = {g: i for i, g in enumerate(GROUPS)}

    def key(r):
        second = r.title if r.group != "city" else (r.city_name or "")
        return rank[r.group], second.casefold(), r.title.casefold()

    return sorted(rows, key=key)


def _snapshot(data: ReportData) -> str | None:
    """The date (YYYY-MM-DD) of the latest current LAU run over the app's cities."""
    stamps = [
        p.osm_timestamp for c in data.cities() if (p := data.current(c.id, "lau")) is not None
    ]
    return max(stamps)[:10] if stamps else None


def source_rows(
    data: ReportData, config_dir: Path, content_dir: Path, lang: Lang = "en"
) -> tuple[list[SourceRow], CitedSources]:
    """The Sources table's rows, in page order, and the sources their cells cite, with their
    fixed words in `lang`."""
    config_dir, content_dir = Path(config_dir), Path(content_dir)
    diffs = load_differences(config_dir / "differences.yaml")
    shown = diffs.localised(lang)  # the words; `diffs` (English) keeps the ids and rules
    dims = [d.id for d in diffs.dimensions]
    mapping = load_organisation_map(config_dir / "organisations.yaml")
    registry = load_sources(content_dir / "sources")
    orgs = load_organisations(content_dir / "organisations")
    refs = {r.id: r for o in orgs.values() for r in o.data_refs}
    num = _Numbering(registry, refs, CITE_PREFIX, lang)

    preset_of: dict[str | None, str] = {}  # source -> the first preset that recomputes it
    for preset, source in data.preset_sources().items():
        preset_of.setdefault(source, preset)
    names = {c.id: c.name for c in data.all_cities()}
    labels = data.preset_labels()
    # the sources a city's Figures tab quotes: the rows that tab is built from
    quoted = {c.id: {r.source for r in difference_rows(data, c.id, diffs)} for c in data.cities()}
    owner = {c.id: org_of_sources(mapping, c.id, set(orgs)) for c in data.cities()}
    per_source: dict[str, int] = {}
    for m in mapping:
        per_source[m.source] = per_source.get(m.source, 0) + 1

    snapshot = _snapshot(data)
    ours_cells = {d: Markup.escape(shown.ours.get(d, "")) for d in dims}
    ours_cells["date"] = Markup.escape(
        t(lang, "sources.snapshot", date=snapshot) if snapshot else t(lang, "sources.no_snapshot")
    )
    rows = [
        SourceRow(
            source_id=None,
            anchor=source_anchor(None),
            title=t(lang, "sources.ours"),
            organisation_id=None,
            organisation_name=None,
            group="ours",
            cells=ours_cells,
            cities=[],
            recomputed_anchor=overview_column(preset_of[None]) if None in preset_of else None,
            recomputed_label=labels.get(preset_of.get(None)),
        )
    ]
    for m in mapping:
        org = orgs.get(m.organisation)
        section = next((s for s in org.sections if s.dimensions), None) if org else None
        given = section.dimensions if section else {}
        cells = {d: given.get(d) for d in dims}  # rendered below, numbered in page order
        anchor = source_anchor(m.source)
        if per_source[m.source] > 1:
            anchor = f"{anchor}-{m.organisation}"
        cities = sorted(
            (
                (cid, names.get(cid, cid))
                for cid, sources in quoted.items()
                if m.source in sources and owner[cid].get(m.source) == m.organisation
            ),
            key=lambda c: c[1],
        )
        rows.append(
            SourceRow(
                source_id=m.source,
                anchor=anchor,
                title=shown.source_names.get(m.source, m.source),
                organisation_id=m.organisation,
                organisation_name=org.name if org else m.organisation,
                group="ranking" if m.city == "*" else "city",
                cells=cells,
                cities=cities,
                recomputed_anchor=(
                    overview_column(preset_of[m.source]) if m.source in preset_of else None
                ),
                city_name=None if m.city == "*" else names.get(m.city, m.city),
                recomputed_label=labels.get(preset_of.get(m.source)),
            )
        )
    rows = [
        r
        if r.group == "ours"
        else replace(
            r,
            cells={
                d: _missing_cell(lang) if v is None else num.inline(v) for d, v in r.cells.items()
            },
        )
        for r in order_rows(rows)
    ]
    cited = CitedSources(
        sources=sorted((n, registry[sid]) for sid, n in num.source_no.items()),
        refs=sorted((n, refs[rid]) for rid, n in num.ref_no.items()),
        ref_links={n: _route(refs[rid].route) for rid, n in num.ref_no.items()},
    )
    return rows, cited
