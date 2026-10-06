"""The Stories page's model (spec §3.4): the Compare state of each chart step, its no-JS table
and the config `story.js` draws from.

`STEP_COMPARE` (in main.py) names, per step, which cities and which metric/mode its chart shows.
The server resolves it once from the `/data/series.json` payload into a Compare state, so the
sticky chart, the "Explore this chart" link and the fallback table of a step cannot drift
apart: story.js draws the state it is given and never recomputes the selection.
"""

from velometer import timeseries as ts
from velometer.app import compare as cmp

TOP_N = 5  # leaders, tail and fastest risers
BOUNDARY = {"lau": "City proper (LAU)", "fua": "Metro area (FUA)"}
JUMP = "km_jump"  # the flag of a step in mapped km that the story explains
NOTE = "Mapped km in OpenStreetMap, not built km."


def _points(payload: dict, city_id: str) -> list[dict]:
    return payload["series"].get(f"{city_id}/lau", [])


def _current(payload: dict, city_id: str, metric: str = "headline") -> float | None:
    for p in _points(payload, city_id):
        if p["label"] == ts.CURRENT:
            return p.get(metric)
    return None


def _growth(payload: dict, city_id: str) -> float | None:
    """Current A+B km as a percentage of the first year's (None without either)."""
    pts = [p for p in _points(payload, city_id) if p["label"] != ts.CURRENT]
    first, now = (pts[0].get("ab_km") if pts else None), _current(payload, city_id, "ab_km")
    return None if not first or now is None else now / first * 100


def _top(values: dict[str, float | None], payload: dict, reverse: bool) -> list[str]:
    have = {i: v for i, v in values.items() if v is not None}
    name = payload["cities"]
    order = sorted(have, key=lambda i: (-have[i] if reverse else have[i], name[i]["name"]))
    return order[:TOP_N]


def _first_last_km(payload: dict, city_id: str) -> tuple[float | None, float | None]:
    pts = [p for p in _points(payload, city_id) if p["label"] != ts.CURRENT]
    return (pts[0].get("ab_km") if pts else None), _current(payload, city_id, "ab_km")


def _growth_highlights(payload: dict) -> list[str]:
    """The cities a growth story talks about, by data rules, at most MAX_HIGHLIGHTED in this
    priority: the largest A+B km gain, the four fastest risers by index, then every city below its
    first-year level (the lowest index first)."""
    ids = list(payload["cities"])
    gain = {}
    for i in ids:
        first, now = _first_last_km(payload, i)
        gain[i] = None if first is None or now is None else now - first
    index = {i: _growth(payload, i) for i in ids}
    below = [i for i in ids if index[i] is not None and index[i] < 100]
    below.sort(key=lambda i: (index[i], payload["cities"][i]["name"]))
    order = _top(gain, payload, True)[:1] + _top(index, payload, True)[: TOP_N - 1] + below
    return list(dict.fromkeys(order))[: cmp.MAX_HIGHLIGHTED]


def pick(payload: dict, how: str) -> list[str]:
    """The city ids of a selection rule: `all`, `leaders` / `tail` (top / bottom five by the
    current LAU headline, the extreme first), `risers` (the five that grew most, A+B indexed to the
    first year), `growth` (the cities the growth story names: see _growth_highlights) or
    `flagged` (cities with a km-jump flagged LAU year, in the payload's city order: the jumps the
    story is about, not every activity-spike or tag-drift flag)."""
    ids = list(payload["cities"])
    if how == "all":
        return ids
    if how in ("leaders", "tail"):
        return _top({i: _current(payload, i) for i in ids}, payload, how == "leaders")
    if how == "risers":
        return _top({i: _growth(payload, i) for i in ids}, payload, True)
    if how == "flagged":
        return [
            i
            for i in ids
            if any(JUMP in p.get("flags", "").split(";") for p in _points(payload, i))
        ]
    if how == "growth":
        return _growth_highlights(payload)
    raise ValueError(f"unknown selection {how!r}")


def step_state(payload: dict, spec: dict) -> cmp.CompareState:
    """The Compare state of a step spec ({"c": rule, "hl": rule or "c", "m", "mode"}). An empty
    selection falls back to every city. Highlights are omitted when every selected city is drawn
    in colour anyway."""
    c = pick(payload, spec["c"]) or pick(payload, "all")
    hl = c if spec.get("hl", "c") == "c" else pick(payload, spec["hl"])
    hl = [i for i in hl if i in c][: cmp.MAX_HIGHLIGHTED]
    if set(hl) == set(c) and len(c) <= cmp.MAX_HIGHLIGHTED:
        hl = []
    return cmp.CompareState(
        c=c,
        m=spec.get("m", cmp.DEFAULT_METRIC),
        mode=spec.get("mode", "abs"),
        view=spec.get("view", "lines"),
        hl=hl,
    )


def compare_href(state: cmp.CompareState) -> str:
    query = cmp.serialize(state)
    return "/compare?" + query if query else "/compare"


def _table(head, rows, notes=(), linked=True, row_head="City") -> dict:
    """A step's fallback table: `head` names the columns after the row head; a row is
    {"id", "name", "cells"} (numbers right-aligned, strings left)."""
    return {
        "head": list(head), "rows": rows, "notes": list(notes), "linked": linked,
        "row_head": row_head,
    }  # fmt: skip


def _jump_table(payload: dict, state: cmp.CompareState) -> dict | None:
    """The km-jump city-years of the selected cities: A+B km before and after, and the change."""
    rows = []
    for cid in state.c:
        pts = _points(payload, cid)
        for k, p in enumerate(pts):
            if JUMP not in p.get("flags", "").split(";"):
                continue
            before = pts[k - 1].get("ab_km") if k else None
            after = p.get("ab_km")
            change = None if before is None or after is None else after - before
            year = cmp.column_label(p["label"], p.get("osm"))
            rows.append(
                {"id": cid, "name": payload["cities"][cid]["name"],
                 "cells": [year, before, after, change]}
            )  # fmt: skip
    head = ["Year", "A+B km before", "A+B km after", "Change, km"]
    return _table(head, rows) if rows else None


def _growth_table(payload: dict, state: cmp.CompareState, first: str, last: str) -> dict:
    """First and current A+B km, the change in km and the index, best index first."""
    rows = []
    for cid in state.c:
        km0, km1 = _first_last_km(payload, cid)
        idx = _growth(payload, cid)
        change = None if km0 is None or km1 is None else km1 - km0
        rows.append(
            {"id": cid, "name": payload["cities"][cid]["name"], "cells": [km0, km1, change, idx]}
        )
    rows.sort(key=lambda r: (r["cells"][3] is None, -(r["cells"][3] or 0), r["name"]))
    head = [f"A+B km {first}", f"A+B km {last}", "Change, km", "Index, first year = 100"]
    return _table(head, rows)


def lines_step(payload: dict, spec: dict, metrics: dict[str, dict[str, str]]) -> dict:
    """A Compare-driven step: its state, its Explore link, the chart's title and note, and the
    fallback table (first and current value per city and the flagged years; the km-jump
    city-years for a `table: jumps` step; km and index for an indexed one)."""
    state = step_state(payload, spec)
    info = metrics[state.m]
    title = f"{info['label']} · {BOUNDARY[state.b]}"
    if state.mode == "index":
        title += " · index, first year = 100"
    if state.view == "small":
        title += " · each city on its own scale"
    base = cmp.table_model(payload, state)
    cols = base["columns"]
    table = None
    if spec.get("table") == "jumps":
        table = _jump_table(payload, state)
    elif cols and base["rows"]:
        first, last = cols[0]["text"], cols[-1]["text"]
        if state.mode == "index":
            table = _growth_table(payload, state, first, last)
        else:
            rows = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "cells": [r["values"][0], r["values"][-1]]
                    + ([", ".join(c["text"] for c in cols if c["label"] in r["flagged"])]
                       if any(x["flagged"] for x in base["rows"]) else []),
                }
                for r in base["rows"]
            ]  # fmt: skip
            rows.sort(key=lambda r: (r["cells"][1] is None, -(r["cells"][1] or 0), r["name"]))
            head = [first, last] + (["Flagged"] if any(x["flagged"] for x in base["rows"]) else [])
            table = _table(head, rows, base["notes"])
    return {
        "kind": "lines",
        "href": compare_href(state),
        "state": state.as_dict(),
        "title": title,
        "note": f"{info['unit']}. {NOTE}",
        "short": NOTE,
        "ring": spec.get("ring"),
        "table": table,
    }


def bezirke_step(payload: dict, city_id: str, href: str) -> dict | None:
    """The Bezirk step: the city's Bezirk headline lines (the highest and lowest now in colour)
    and a table; None when the city has no Bezirke in the data."""
    subareas = payload["bezirke"].get(city_id)
    if not subareas:
        return None
    rows = []
    for sid, sub in subareas.items():
        pts = sub["points"]
        years = [p for p in pts if p["label"] != ts.CURRENT]
        now = next((p["headline"] for p in pts if p["label"] == ts.CURRENT), None)
        rows.append(
            {
                "id": sid,
                "name": sub["name"],
                "first": years[0]["headline"] if years else None,
                "last": now,
            }
        )
    rows.sort(key=lambda r: (r["last"] is None, -(r["last"] or 0), r["name"]))
    have = [r["id"] for r in rows if r["last"] is not None]
    cols = [p["label"] for p in next(iter(subareas.values()))["points"]]
    first_text = cmp.column_label(cols[0], None) if cols else "first"
    return {
        "kind": "bezirke",
        "href": href,
        "city": city_id,
        "hl": have[:1] + have[-1:] if len(have) > 1 else have,
        "title": f"Headline by Bezirk · {payload['cities'][city_id]['name']}",
        "note": f"{payload['headline_unit']}. {NOTE}",
        "short": NOTE,
        "table": _table(
            [first_text, "current"],
            [{"id": r["id"], "name": r["name"], "cells": [r["first"], r["last"]]} for r in rows],
            linked=False,
            row_head="Bezirk",
        ),
    }
