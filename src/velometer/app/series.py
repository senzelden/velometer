"""`/data/series.json`: the chart data of every page, in the M7 spike's `data.json` shape.

One payload for the whole app (21 cities x 2 boundaries x 10 labels is small): the cities, each
city's yearly series per boundary, the subarea (Bezirk) series, the preset labels and the
explanations of flagged years, under the OSM notice (`attribution`, ODbL §4.2 b). Values are the
CSV export's (mapped km, ADR 0006).

The file is shared by both editions (M12): the display text is English, and each text a German
page shows differently has an additive `<key>_de` sibling, which static/js/data.js `localised`
swaps in on a German page.
"""

from pathlib import Path

from velometer import credits
from velometer import timeseries as ts
from velometer.app.counts import counter_payload, counters_config, no_data_notes
from velometer.app.names import country_name
from velometer.db import subarea_names
from velometer.report.data import HEADLINE_UNIT, KINDS, ReportData, headline_unit

# CSV column -> payload key (the spike's names)
PRESET_KEYS = {"ours_headline": "headline", "ecf_qecio": "ecf_qecio"}
PRESET_KEYS["clean_cities_2025"] = "clean_cities"


def _num(text: str) -> float | None:
    return None if text in ("", None) else round(float(text), 3)


def _point(row: dict[str, str]) -> dict:
    return {
        "label": row["label"],
        "run_id": int(row["run_id"]),
        "osm": row["osm_timestamp"][:10],
        **{t: _num(row[f"tier_{t}_km"]) for t in ts.TIERS},
        "ab_km": _num(row["ab_km"]),
        **{key: _num(row[col]) for col, key in PRESET_KEYS.items()},
        "flags": row["flags"],
    }


def _bezirke(data: ReportData, city_id: str) -> dict:
    names = subarea_names(data.conn, city_id)
    return {
        sid: {
            "name": names.get(sid, sid),
            "points": [
                {
                    "label": p.label,
                    "headline": None if p.headline is None else round(p.headline, 3),
                    **{t: round(p.tier_km.get(t, 0.0), 3) for t in ts.TIERS},
                }
                for p in points
            ],
        }
        for sid, points in data.subarea_series(city_id).items()
    }


def series_payload(data: ReportData, explanations: Path | None = None) -> dict:
    """The chart data: `cities`, `series` ("<id>/<kind>" -> points, years then `current`),
    `bezirke` (city id -> subarea id -> name and points; cities with subareas only), `presets`,
    `headline_unit`, `explanations.timeseries` (flag key -> text of `explanations`, the
    time-series review page, for every flag that has one) and `counters` (the counter index per
    counter city, `app/counts.counter_payload`). The German siblings: per city `name_de` and
    `country_name_de`, `headline_unit_de`, `presets_de`, `counters.none_de` and
    `explanations_de` (`german_explanations`)."""
    data = data.with_lang("en")  # one shared file in English (the pages localise it)
    names_de = {c.id: c.name for c in data.with_lang("de").cities()}
    cities = {
        c.id: {
            "id": c.id,
            "name": c.name,
            "country": c.country_iso2,
            "country_name": country_name(c.country_iso2),
            "population": c.population.value if c.population else None,
            "name_de": names_de.get(c.id, c.name),
            "country_name_de": country_name(c.country_iso2, "de"),
        }
        for c in data.cities()
    }
    series: dict[str, list[dict]] = {f"{c}/{k}": [] for c in cities for k in KINDS}
    for row in data.csv_rows():
        series[f"{row['city_id']}/{row['boundary_kind']}"].append(_point(row))
    bezirke = {c: b for c in cities if (b := _bezirke(data, c))}
    notes = {}
    if explanations is not None:
        for c in cities:
            for kind in KINDS:
                for flag in data.flags(c, kind):
                    text = ts.explanation(explanations, flag.key)
                    if text:
                        notes[flag.key] = text
    counters = counter_payload(data)
    counters["none_de"] = no_data_notes(counters_config(data.config_dir)[0], "de")
    return {
        "attribution": credits.OSM_NOTICE,
        "cities": cities,
        "series": series,
        "bezirke": bezirke,
        "presets": data.preset_labels(),
        "headline_unit": HEADLINE_UNIT,
        "explanations": {"timeseries": notes},
        "counters": counters,
        "headline_unit_de": headline_unit("de"),
        "presets_de": data.with_lang("de").preset_labels(),
        "explanations_de": german_explanations(notes, explanations),
    }


def german_explanations(notes: dict[str, str], explanations: Path | None) -> dict:
    """`explanations_de`: `timeseries` with the keys of `notes` (the English explanations), each
    the stamped German entry of the `.de.md` beside `explanations`, else the English one, and
    `fallback` the keys still English (a missing or unstamped German entry)."""
    de_path = None if explanations is None else ts.german_explanations(Path(explanations))
    german: dict[str, str] = {}
    fallback: list[str] = []
    for key, text in notes.items():
        de, stamp = (None, None) if de_path is None else ts.stamped_explanation(de_path, key)
        if de is None or stamp is None:
            german[key] = text
            fallback.append(key)
        else:
            german[key] = de
    return {"timeseries": german, "fallback": sorted(fallback)}
