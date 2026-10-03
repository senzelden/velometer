"""A report database built with the M3 fakes, shared by the report tests (Tasks 4-8).

`build_report_fixture(tmp_path) -> (db_path, config_dir)`:

- config_dir: a copy of config/ whose history.yaml series is 2024-2026 (report.yaml still names v2);
- berlin/lau: history 2024-2026 plus a current run (2026-09-30), with population 100000 (2024);
  2025 carries an activity spike, so it is flagged `activity_spike`;
- berlin/fua: history 2024-2026 plus a current run, with no population (FUA runs carry none);
- paris/lau: history 2024-2026 but NO current run;
- external figures: berlin has Clean Cities and a complete QECIO set; paris has Clean Cities and
  QECIO without `cycle_lanes_km` (so it drops out of the QECIO ratio ranking).
"""

import re
import shutil
from datetime import date
from pathlib import Path

import yaml

from tests.test_run_history import CFG_DIR, CITY, Fakes, _current_deps
from velometer import run as R
from velometer.config import load_cities
from velometer.db import (
    create_schema,
    fetch_activity,
    open_db,
    replace_activity,
    replace_external_figures,
    upsert_cities,
)
from velometer.models import ExternalFigure

YEARS = range(2024, 2027)
CLASSIFIER = "v2"
PARIS = CITY.model_copy(update={"id": "paris", "name": "Paris"})
SPIKE_YEAR = "2025"


def _config_dir(tmp_path: Path) -> Path:
    d = tmp_path / "config"
    shutil.copytree(CFG_DIR, d)
    text = (CFG_DIR / "history.yaml").read_text()
    (d / "history.yaml").write_text(re.sub(r'years: "[^"]*"', 'years: "2024-2026"', text))
    return d


def _figure(city_id, source, metric, value, scope="whole_network", unit="km"):
    return ExternalFigure(
        city_id=city_id,
        source=source,
        metric_name=metric,
        value=value,
        unit=unit,
        reference_date=date(2025, 1, 1),
        network_scope=scope,
        length_basis="unknown",
        source_url="https://example.invalid/fixture",
        retrieved_at=date(2026, 10, 1),
    )


QECIO_NUTS3 = {"berlin": "DE300", "paris": "FR101"}  # nuts3_code of config/cities.yaml


def _qecio(city_id, **km):
    scope = f"nuts3_{QECIO_NUTS3[city_id]}"
    return [_figure(city_id, "qecio_v2_10", m, v, scope=scope) for m, v in km.items()]


def external_figures() -> dict[str, list[ExternalFigure]]:
    return {
        "clean_cities_2025": [
            # a figure of another scope, listed first: a ranking that ignored scope would use it
            _figure("berlin", "clean_cities_2025", "protected_share_pct", 99.0, "city_core", "pct"),
            _figure("berlin", "clean_cities_2025", "protected_share_pct", 30.0, unit="pct"),
            _figure("paris", "clean_cities_2025", "protected_share_pct", 20.0, unit="pct"),
        ],
        "qecio_v2_10": _qecio(
            "berlin",
            cycle_tracks_km=100.0,
            cycle_lanes_km=50.0,
            shared_pedestrians_km=50.0,
            main_roads_km=400.0,
        )  # (100 + 50 + 50) / 400 = 50 %
        + _qecio("paris", cycle_tracks_km=40.0, shared_pedestrians_km=10.0, main_roads_km=200.0),
    }


def synthetic_cities(n: int) -> list:
    """`n - 2` copies of berlin, ids c03..cNN, country DE (so trust.yaml trusts them)."""
    return [
        CITY.model_copy(
            update={
                "id": f"c{i:02d}",
                "name": f"City {i:02d}",
                "osm_relation_id": 900000 + i,
                "lau_code": f"DE_9{i:07d}",
                "fua_code": f"DE9{i:02d}F",
                "nuts3_code": f"DE9{i:02d}",
                "bikenetkit_id": f"city{i:02d}_de",
            }
        )
        for i in range(3, n + 1)
    ]


def build_report_fixture(tmp_path: Path) -> tuple[Path, Path]:
    return build_report_fixture_n(tmp_path, 2)


def build_report_fixture_n(tmp_path: Path, n_cities: int) -> tuple[Path, Path]:
    """berlin and paris as `build_report_fixture`, plus `n_cities - 2` synthetic DE cities
    (history 2024-2026 and a current LAU run each). The synthetic cities are appended to the
    config copy's cities.yaml so report.yaml / trust validation see them."""
    db_path = tmp_path / "report.sqlite"
    cfg = _config_dir(tmp_path)
    extra = synthetic_cities(n_cities)
    if extra:
        doc = yaml.safe_load((cfg / "cities.yaml").read_text())
        doc["cities"] += [c.model_dump(mode="json", exclude_none=True) for c in extra]
        (cfg / "cities.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    fakes = Fakes(tmp_path)
    cities = [c for c in load_cities(CFG_DIR / "cities.yaml") if c.id in ("berlin", "paris")]
    cities += extra
    deps = _current_deps(tmp_path)
    hdeps = fakes.deps()

    def no_population_boundary(city, kind, data_dir, region_path=None):
        rec, _ = hdeps.city_boundary(city, kind, data_dir, region_path)
        return rec, None

    with open_db(db_path) as conn:
        create_schema(conn)
        upsert_cities(conn, cities)
        for city in (CITY, PARIS):
            R.run_history(
                conn, city, YEARS, data_dir=tmp_path, config_dir=cfg, classifier=CLASSIFIER,
                deps=hdeps,
            )  # fmt: skip
        R.run_city(conn, CITY, data_dir=tmp_path, config_dir=cfg, classifier=CLASSIFIER, deps=deps)
        for city in extra:
            R.run_history(
                conn, city, YEARS, data_dir=tmp_path, config_dir=cfg, classifier=CLASSIFIER,
                deps=hdeps,
            )  # fmt: skip
            R.run_city(
                conn, city, data_dir=tmp_path, config_dir=cfg, classifier=CLASSIFIER, deps=deps
            )
        fua_deps = fakes.deps(city_boundary=no_population_boundary)
        R.run_history(
            conn, CITY, YEARS, data_dir=tmp_path, config_dir=cfg, classifier=CLASSIFIER,
            boundary_kind="fua", deps=fua_deps,
        )  # fmt: skip
        fua_cur = _current_deps(tmp_path)
        fua_cur = R.RunDeps(**{**fua_cur.__dict__, "city_boundary": no_population_boundary})
        R.run_city(
            conn, CITY, data_dir=tmp_path, config_dir=cfg, classifier=CLASSIFIER,
            boundary_kind="fua", deps=fua_cur,
        )  # fmt: skip
        sha = R.file_sha256(cfg / "activity.yaml")
        rows = fetch_activity(conn, "berlin", "lau", fakes.set_md5, sha)
        rows = [
            r.model_copy(update={"n_edits": 50}) if r.year == int(SPIKE_YEAR) else r for r in rows
        ]
        replace_activity(conn, "berlin", "lau", fakes.set_md5, sha, rows)
        for source, figures in external_figures().items():
            replace_external_figures(conn, source, figures)
    return db_path, cfg
