"""Fake subareas for the run fakes: one strip per configured relation, as production would load.

The shipped config gives Berlin its Bezirke, so every fake run of "berlin" takes the real subarea
path (`run._attribute_subareas`). `config_subareas()` returns a `(load_subareas, subarea_shas)`
pair for `RunDeps` / `HistoryDeps`: `load_subareas(city, data_dir)` builds one polygon per
relation in `city.subareas`, as vertical strips that tile the plane (inner edges across the fake
Berlin box in EPSG:25833, outer strips reaching +-1e9 m), so the per-tier sum check holds for any
fake boundary. `subarea_shas(conn, city_id)` returns the shas of the polygons last loaded for that
city, so the stale-file check passes. City totals do not depend on subareas.
"""

import hashlib
import shutil
from pathlib import Path

import numpy as np
import yaml
from shapely import box

from velometer.config import default_config_dir
from velometer.subareas import SubareaPolygon

_X0, _X1 = 380_000, 410_000  # the fake Berlin box of tests/test_run_history.py, EPSG:25833
_FAR = 1e9


def _sha(city_id: str, slug: str) -> str:
    return hashlib.sha256(f"{city_id}/{slug}".encode()).hexdigest()


def strips(city) -> list[SubareaPolygon]:
    """One polygon per configured relation, tiling the plane in config order."""
    rels = city.subareas.relations if city.subareas else []
    edges = list(np.linspace(_X0, _X1, len(rels) + 1))
    if rels:
        edges[0], edges[-1] = -_FAR, _FAR
    return [
        SubareaPolygon(
            r.slug, r.name, r.id, box(edges[i], -_FAR, edges[i + 1], _FAR), _sha(city.id, r.slug)
        )
        for i, r in enumerate(rels)
    ]


def config_subareas():
    """A fresh `(load_subareas, subarea_shas)` pair; the shas follow what was loaded."""
    loaded: dict[str, dict[str, str]] = {}

    def load_subareas(city, data_dir):
        polys = strips(city)
        loaded[city.id] = {p.subarea_id: p.sha256 for p in polys}
        return polys

    def subarea_shas(conn, city_id):
        return dict(loaded.get(city_id, {}))

    return load_subareas, subarea_shas


# --- fixtures that model a city without subareas -------------------------------------------------
# The report and timeseries fixtures (and the "city without subareas" tests) predate Berlin's
# Bezirke: their berlin has no subareas until a test adds its own (`report_fixture.add_subareas`,
# West/East). They run a subarea-free copy of the shipped city against a config copy without
# `subareas`, so the shipped cities.yaml can carry the real Bezirke.


def without_subareas(city):
    """`city` with no subareas configured."""
    return city.model_copy(update={"subareas": None})


def strip_subareas(config_dir: Path) -> Path:
    """Drop every city's `subareas` block from `config_dir/cities.yaml` (a copy, never config/)."""
    path = config_dir / "cities.yaml"
    assert path.resolve() != (default_config_dir() / "cities.yaml").resolve()
    doc = yaml.safe_load(path.read_text())
    for c in doc["cities"]:
        c.pop("subareas", None)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    return config_dir


def plain_config_dir(tmp_path: Path) -> Path:
    """A copy of config/ whose cities have no subareas."""
    d = tmp_path / "config_plain"
    shutil.copytree(default_config_dir(), d)
    return strip_subareas(d)
