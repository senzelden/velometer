"""The plan pages' models: `/plans` (one row per city) and `/plans/berlin` (per plan item: the
yearly target against the reported figures, every document's value kept, the infraVelo
"completed projects" and our "mapped on the network"), M8 spec §4.4.

Reported figures are shown as printed (spec §2.8): the current row of each (plan, item, year,
quantity, cumulative_from) comes from `current_and_revisions`, every other row is listed as a
revision, and a `suspect` row is shown with a marker and its note wherever it appears.
"""

import json
import re
import sqlite3
from datetime import date
from pathlib import Path

from velometer.app.narrative import safe_url
from velometer.content.facts import version_key
from velometer.content.models import Organisation
from velometer.db import OverlayRow
from velometer.i18n import Lang, number_trimmed, t
from velometer.plans.berlin import NETWORK_LAYER
from velometer.plans.models import (
    MAPPED_BASELINE,
    Plan,
    PlanItem,
    ReportRow,
    current_and_revisions,
)

DETAIL_CITY = "berlin"  # the one city with a plan page of its own (spec §4.4)
MEASURES_FILE = Path("berlin") / "radverkehrsmassnahmen.geojson"
MEASURES_RETRIEVED = Path("berlin") / "retrieved.json"
PROJECTS_ORG = "infravelo"  # the measures dataset is fed from infraVelo's project database
COMPLETED = "Abgeschlossen"
PARTS = range(1, 6)  # netz_art1..5 / streckenlaenge1..5: a project's parts by network class
# Plan item -> (overlay network class, measures-dataset network classes). The Radverkehrsnetz
# has no overlay series: a way along both classes would count once in each.
ITEM_NETWORK = {
    "vorrangnetz": ("vorrangnetz", ("Vorrangnetz",)),
    "ergaenzungsnetz": ("ergaenzungsnetz", ("Ergänzungsnetz",)),
    "radverkehrsnetz": (None, ("Vorrangnetz", "Ergänzungsnetz")),
}
QUANTITY_ORDER = {
    "implemented_in_year": 0,
    "implemented_cumulative": 1,
    "under_construction": 2,
    "in_planning": 3,
}
YEAR_END = re.compile(r"(\d{4})\s*$")  # bauende: "4. Quartal 2022"


def num(v: float, lang: Lang = "en") -> str:
    """A printed figure as printed: thousands separators, up to two decimals, no trailing 0."""
    return number_trimmed(v, lang)


def quantity_text(r: ReportRow, lang: Lang = "en") -> str:
    if r.quantity == "implemented_in_year":
        return t(lang, "plan.quantity.in_year", year=r.year)
    if r.quantity == "implemented_cumulative":
        return t(lang, "plan.quantity.cumulative", since=r.cumulative_from, year=r.year)
    if r.quantity == "under_construction":
        return t(lang, "plan.quantity.under_construction", year=r.year)
    return t(lang, "plan.quantity.in_planning", year=r.year)


def series_text(r: ReportRow, lang: Lang = "en") -> str:
    """The series a row belongs to (cumulative series are told apart by their start year)."""
    if r.quantity == "implemented_in_year":
        return t(lang, "plan.series.in_year")
    if r.quantity == "implemented_cumulative":
        return t(lang, "plan.series.cumulative", since=r.cumulative_from)
    if r.quantity == "under_construction":
        return t(lang, "plan.series.under_construction")
    return t(lang, "plan.series.in_planning")


def target_text(item: PlanItem, lang: Lang = "en") -> str:
    """The item's target as the plan prints it, or that it states none in km."""
    years = sorted(item.targets)
    unit = item.unit
    if item.target_kind == "none" or not years:
        return t(lang, "plan.no_km_target")
    by = ", ".join(
        t(lang, "plan.target_by", value=num(item.targets[y], lang), unit=unit, year=y)
        for y in years
    )
    if item.target_kind == "km_per_year":
        steps = " · ".join(f"{y}: {num(item.targets[y], lang)}" for y in years)
        return t(lang, "plan.per_year", unit=unit, steps=steps)
    if item.target_kind == "share":
        return f"{t(lang, 'plan.no_km_target')}; {by}"
    return by


def _publisher(name: str, orgs: dict[str, Organisation]) -> dict:
    org = orgs.get(name)
    return {"name": org.name if org else name, "href": f"/organisations#{name}" if org else None}


def row_view(r: ReportRow, current: bool, orgs: dict[str, Organisation], lang: Lang = "en") -> dict:
    return {
        "row": r,
        "value": num(r.value, lang),
        "unit": t(lang, f"plan.unit.{r.unit}"),  # the stored unit, in `lang`
        "quantity": quantity_text(r, lang),
        "series": series_text(r, lang),
        "doc_type": t(lang, f"plan.doc_type.{r.doc_type}"),
        "url": safe_url(r.url),
        "publisher": _publisher(r.publisher, orgs),
        "current": current,
    }


def _latest(groups: dict, item_id: str, quantities: set[str]) -> list[ReportRow]:
    """The current row of the latest year of each of the item's series."""
    best: dict[tuple, ReportRow] = {}
    for (_plan, item, _year, quantity, base), (cur, _rev) in groups.items():
        if item != item_id or quantity not in quantities:
            continue
        key = (quantity, base)
        if key not in best or cur.year > best[key].year:
            best[key] = cur
    return sorted(
        best.values(),
        key=lambda r: (QUANTITY_ORDER[r.quantity], r.cumulative_from or 0, r.year),
    )


def plans_table(
    plans: list[Plan],
    rows: list[ReportRow],
    cities: list[tuple[str, str]],
    orgs: dict[str, Organisation],
    lang: Lang = "en",
) -> list[dict]:
    """One entry per city (id, name) in the given order, each with its plans (none: a note on
    the page). A plan shows every item that has a target or a reported figure, with the latest
    current figure of each series; the plan with its own page shows only the items with a
    target and their implemented figures, and links that page for the rest."""
    out = []
    for city_id, name in cities:
        views = []
        for plan in (p.localised(lang) for p in plans if p.city == city_id):
            plan_rows = [r for r in rows if r.plan_id == plan.id]
            groups = current_and_revisions(plan_rows)
            detail = plan.city == DETAIL_CITY
            quantities = (
                {"implemented_in_year", "implemented_cumulative"} if detail else set(QUANTITY_ORDER)
            )
            items = []
            for item in plan.items:
                latest = _latest(groups, item.id, quantities)
                has_target = item.target_kind != "none" and bool(item.targets)
                if detail and not has_target:
                    continue
                if not has_target and not latest:
                    continue
                items.append(
                    {
                        "item": item,
                        "target": target_text(item, lang),
                        "latest": [row_view(r, True, orgs, lang) for r in latest],
                    }
                )
            status = t(lang, f"plan.status.{plan.status}")
            if plan.status != "current":
                status += "; " + (
                    t(lang, "plan.successor", successor=plan.successor)
                    if plan.successor
                    else t(lang, "plan.no_successor")
                )
            views.append(
                {
                    "plan": plan,
                    "status_text": status,
                    "publisher": _publisher(plan.publisher, orgs),
                    "url": safe_url(plan.url),
                    "detail_href": f"/plans/{plan.city}" if detail else None,
                    "entries": items,
                }
            )
        out.append({"id": city_id, "name": name, "plans": views})
    return out


# ---------- /plans/berlin ----------


def completed_projects(path: Path) -> tuple[dict[str, dict[int, float]], int] | None:
    """Metres of completed projects (`status` Abgeschlossen) per network class and `bauende`
    year, from each part's `streckenlaenge<i>` and `netz_art<i>` (the total `streckenlaenge` of a
    feature is mostly 0 in the served data and carries no class), and how many completed
    projects had no readable end year (not counted). None when the file is absent."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    metres: dict[str, dict[int, float]] = {}
    undated = 0
    for f in doc.get("features", []):
        p = f.get("properties") or {}
        if p.get("status") != COMPLETED:
            continue
        m = YEAR_END.search(p.get("bauende") or "")
        if m is None:
            undated += 1
            continue
        year = int(m.group(1))
        for i in PARTS:
            cls, length = p.get(f"netz_art{i}"), p.get(f"streckenlaenge{i}")
            if cls and length:
                by_year = metres.setdefault(cls, {})
                by_year[year] = by_year.get(year, 0.0) + float(length)
    return metres, undated


def measures_retrieved(plans_data_dir: Path) -> tuple[dict | None, str | None]:
    """(record, error) of the `retrieved.json` that `velometer plans fetch berlin` writes beside
    the layers: the licence, the retrieval time and the layers fetched. Absent: (None, None), the
    page says the dataset is not present and a drawn planned network that its licence is not
    recorded; present but unreadable, or without a licence: (None,
    the reason), a note on the page instead of licence lines that silently vanish."""
    path = plans_data_dir / MEASURES_RETRIEVED
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as e:
        return None, f"{path}: {e}"
    if not isinstance(record, dict) or not isinstance(record.get("licence"), str):
        return None, f"{path}: not a record with a licence"
    return record, None


def network_licence(record: dict | None) -> str | None:
    """The planned-network layer's licence: the record's, when the record lists that layer."""
    layers = (record or {}).get("layers")
    return record["licence"] if isinstance(layers, dict) and NETWORK_LAYER in layers else None


def _projects_of(item_id: str, metres: dict[str, dict[int, float]] | None) -> list[dict] | None:
    if metres is None or item_id not in ITEM_NETWORK:
        return None
    classes = ITEM_NETWORK[item_id][1]
    years = sorted({y for c in classes for y in metres.get(c, {})})
    return [
        {"year": y, "km": round(sum(metres.get(c, {}).get(y, 0.0) for c in classes) / 1000, 2)}
        for y in years
    ]


def latest_overlay(rows: list[OverlayRow]) -> tuple[str | None, list[OverlayRow]]:
    """The latest overlay version (numeric order, `overlay_v10` after `overlay_v2`) and its rows."""
    if not rows:
        return None, []
    version = max((r.overlay_version for r in rows), key=version_key)
    return version, [r for r in rows if r.overlay_version == version]


def run_dates(conn: sqlite3.Connection, run_ids: set[int]) -> dict[int, str]:
    """Each LAU run's snapshot date (YYYY-MM-DD), as the overlay facts read it."""
    if not run_ids:
        return {}
    ids = sorted(run_ids)
    marks = ",".join("?" * len(ids))
    return {
        rid: ts[:10]
        for rid, ts in conn.execute(
            f"SELECT id, osm_timestamp FROM runs WHERE boundary_kind='lau' AND id IN ({marks})",
            ids,
        )
    }


def _overlay_of(item_id: str, rows: list[OverlayRow], dates: dict[int, str]) -> list[dict] | None:
    cls = ITEM_NETWORK.get(item_id, (None, ()))[0]
    if cls is None:
        return None
    ab: dict[str, float] = {}
    for r in rows:
        if r.network_class == cls and r.tier in ("A", "B") and r.run_id in dates:
            ab[dates[r.run_id]] = ab.get(dates[r.run_id], 0.0) + r.mapped_km
    return [{"date": d, "ab_km": round(ab[d], 3)} for d in sorted(ab)] or None


def _overlay_table(points: list[dict] | None, baseline: date) -> list[dict]:
    base = next((p["ab_km"] for p in points or [] if p["date"] == baseline.isoformat()), None)
    out, prev = [], None
    for p in points or []:
        out.append(
            {
                "date": p["date"],
                "ab_km": p["ab_km"],
                "step": None if prev is None else p["ab_km"] - prev,
                "since_base": None if base is None else p["ab_km"] - base,
            }
        )
        prev = p["ab_km"]
    return out


def _report_json(r: ReportRow, current: bool) -> dict:
    return {
        "year": r.year,
        "value": r.value,
        "doc": r.doc_id,
        "doc_type": r.doc_type,
        "doc_date": r.doc_date.isoformat(),
        "quantity": r.quantity,
        "current": current,
        "suspect": r.suspect,
        "note": r.note,
    }


def documents(
    rows: list[ReportRow], plan: Plan, orgs: dict[str, Organisation], lang: Lang = "en"
) -> list[dict]:
    """The plan's progress documents, oldest first: type, number, date, what it reports, link."""
    labels = {i.id: i.label.split(" (")[0] for i in plan.localised(lang).items}
    docs: dict[tuple, dict] = {}
    for r in rows:
        d = docs.setdefault(
            (r.doc_date, r.doc_type, r.doc_id),
            {
                "doc_id": r.doc_id,
                "doc_type": t(lang, f"plan.doc_type.{r.doc_type}"),
                "doc_date": r.doc_date.isoformat(),
                "url": safe_url(r.url),
                "publisher": _publisher(r.publisher, orgs),
                "reports_on": {},
                "years": set(),
                "figures": 0,
                "suspect": 0,
            },
        )
        d["reports_on"].setdefault(labels.get(r.item_id, r.item_id), None)
        d["years"].add(r.year)
        d["figures"] += 1
        d["suspect"] += r.suspect
    out = []
    for key in sorted(docs):
        d = docs[key]
        years = sorted(d.pop("years"))
        d["years"] = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"
        d["reports_on"] = list(d["reports_on"])
        out.append(d)
    return out


def berlin_context(
    plan: Plan,
    rows: list[ReportRow],
    orgs: dict[str, Organisation],
    overlay_rows: list[OverlayRow],
    dates: dict[int, str],
    projects: tuple[dict[str, dict[int, float]], int] | None,
    lang: Lang = "en",
) -> dict:
    """Everything `/plans/berlin` shows: per item the chart config and its tables, the document
    table, and which overlay version and measures dataset the series come from."""
    plan = plan.localised(lang)
    rows = [r for r in rows if r.plan_id == plan.id]
    groups = current_and_revisions(rows)
    version, latest = latest_overlay(overlay_rows)
    baseline = MAPPED_BASELINE  # spec §4.4, not the plan's first target year
    base_year = baseline.year
    metres = projects[0] if projects else None
    items, config = [], []
    for item in plan.items:
        series: dict[tuple, list] = {}
        reports = []
        for key, (cur, revisions) in groups.items():
            if key[1] != item.id:
                continue
            views = [row_view(cur, True, orgs, lang)]
            views += [row_view(r, False, orgs, lang) for r in revisions]
            series.setdefault(
                (QUANTITY_ORDER[key[3]], key[4] or 0, series_text(cur, lang)), []
            ).append((key[2], views))
            if key[3] == "implemented_in_year":
                reports += [_report_json(cur, True)] + [_report_json(r, False) for r in revisions]
        overlay = _overlay_of(item.id, latest, dates)
        cfg = {
            "id": item.id,
            "label": item.label,
            "target_kind": item.target_kind,
            "unit": item.unit,
            "targets": {str(y): v for y, v in sorted(item.targets.items())},
            "reports": sorted(reports, key=lambda r: (r["year"], r["doc_date"])),
            "projects": _projects_of(item.id, metres),
            "overlay": overlay,
        }
        config.append(cfg)
        in_year = {y: v for (q, _b, _t), ys in series.items() if q == 0 for y, v in ys}
        projects_by_year = {p["year"]: p["km"] for p in cfg["projects"] or []}
        years = sorted(set(item.targets) | set(in_year))
        items.append(
            {
                "item": item,
                "target": target_text(item, lang),
                "network": item.id in ITEM_NETWORK,
                "has_overlay_class": ITEM_NETWORK.get(item.id, (None,))[0] is not None,
                "yearly": [
                    {
                        "year": y,
                        "target": item.targets.get(y),
                        "reported": in_year.get(y, []),
                        "projects": projects_by_year.get(y),
                    }
                    for y in years
                ],
                "projects": cfg["projects"],
                "series": [
                    {"text": text, "years": sorted(ys, key=lambda t: t[0])}
                    for (_q, _b, text), ys in sorted(series.items())
                ],
                "overlay": (table := _overlay_table(overlay, baseline)),
                # the spec's quantity (§4.4): the change since MAPPED_BASELINE, to the latest
                # snapshot
                "mapped_change": table[-1]
                if table and table[-1]["since_base"] is not None
                else None,
                "figures": sum(1 for r in rows if r.item_id == item.id),
            }
        )
    network_retrieved = latest[0].network_retrieved_at if latest else None
    return {
        "plan": plan,
        "publisher": _publisher(plan.publisher, orgs),
        "url": safe_url(plan.url),
        "items": items,
        "config": {"items": config, "mapped_from": base_year, "overlay_version": version},
        "documents": documents(rows, plan, orgs, lang),
        "overlay_version": version,
        "network_retrieved_at": network_retrieved,
        "base_year": base_year,
        "projects_present": projects is not None,
        "projects_undated": projects[1] if projects else 0,
        "projects_org": _publisher(PROJECTS_ORG, orgs),
    }
