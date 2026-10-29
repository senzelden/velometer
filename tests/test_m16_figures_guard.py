"""M16 Task 11: the database's curated external figures must match config/external/figures.csv.

Task 9 found `figures.csv` changed by the press rewordings but the database not reloaded: the
German figures page looked its notes up by the new English text and fell back to English. The
guard compares what `velometer external load` would store with what the database holds, reads
only, and leaves the QECIO and BikeNetKit rows out.
"""

import csv
import hashlib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from velometer.cli import app
from velometer.config import default_config_dir, load_cities
from velometer.db import create_schema, open_db, replace_external_figures, upsert_cities
from velometer.models import ExternalFigure
from velometer.sources import external as X

CFG = default_config_dir()
HEADER = (
    "city_id,source,metric_name,value,unit,reference_date,network_scope,length_basis,"
    "source_url,retrieved_at,note,note_de"
)
ROWS = [
    "berlin,official_berlin,protected_km,140.1,km,2025-12-31,whole_network,unknown,"
    "https://example.org/a,2026-10-01,Senate report p. 3,Senatsbericht S. 3",
    "vienna,official_vienna,network_km,1700,km,,whole_network,reallaenge,"
    "https://example.org/b,2026-10-01,city page,Seite der Stadt",
]


def _csv(path: Path, rows: list[str]) -> Path:
    path.write_text("\n".join([HEADER, *rows]) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def loaded(tmp_path) -> tuple[Path, Path]:
    """(db, csv): a database loaded from the CSV as `external load --no-qecio --no-bikenetkit`
    loads it, plus one QECIO row the CSV never holds."""
    figures = _csv(tmp_path / "figures.csv", ROWS)
    db = tmp_path / "v.sqlite"
    with open_db(db) as conn:
        create_schema(conn)
        upsert_cities(conn, load_cities(CFG / "cities.yaml"))
        X.load_all(conn, tmp_path / "data", CFG, qecio=False, bikenetkit=False, figures_csv=figures)
        qecio = ExternalFigure(
            city_id="berlin", source="qecio_v2_10", metric_name="main_roads_km", value=1.0,
            unit="km", reference_date=None, network_scope="nuts3_DE300", length_basis="unknown",
            source_url="https://example.org/q", retrieved_at="2026-10-01",
        )  # fmt: skip
        replace_external_figures(conn, "qecio_v2_10", [qecio])
    return db, figures


def _drift(db: Path, figures: Path) -> list[str]:
    from velometer.report.data import open_readonly

    conn = open_readonly(db)
    try:
        return X.curated_drift(conn, figures)
    finally:
        conn.close()


def test_a_database_loaded_from_the_csv_matches_it(loaded):
    assert _drift(*loaded) == []


def test_a_changed_note_is_named_with_both_values(loaded, tmp_path):
    db, _ = loaded
    changed = _csv(tmp_path / "changed.csv", [ROWS[0].replace("p. 3,", "p. 4,"), ROWS[1]])
    (problem,) = _drift(db, changed)
    assert problem.startswith("figures.csv line 2, berlin official_berlin protected_km")
    assert "note database 'Senate report p. 3', csv 'Senate report p. 4'" in problem


def test_a_changed_value_is_named(loaded, tmp_path):
    db, _ = loaded
    changed = _csv(tmp_path / "changed.csv", [ROWS[0].replace(",140.1,", ",140,"), ROWS[1]])
    (problem,) = _drift(db, changed)
    assert "value database 140.1, csv 140.0" in problem


def test_a_row_the_csv_dropped_is_named(loaded, tmp_path):
    db, _ = loaded
    (problem,) = _drift(db, _csv(tmp_path / "fewer.csv", ROWS[:1]))
    assert problem == "database row vienna official_vienna network_km: not in figures.csv"


def test_an_extra_curated_row_is_named(loaded, tmp_path):
    db, _ = loaded
    extra = ROWS[1].replace("network_km", "protected_km")
    (problem,) = _drift(db, _csv(tmp_path / "more.csv", [*ROWS, extra]))
    assert problem == "figures.csv line 4, vienna official_vienna protected_km: not in the database"


def test_qecio_and_bikenetkit_rows_are_never_compared():
    assert set(X.LOADER_SOURCES) == {"qecio_v2_10", "bikenetkit_v1"}
    with (CFG / "external" / "figures.csv").open(encoding="utf-8") as f:
        assert not {r["source"] for r in csv.DictReader(f)} & set(X.LOADER_SOURCES)


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def test_the_check_command_exits_1_on_drift_and_never_writes(loaded, tmp_path):
    db, figures = loaded
    before = _md5(db)
    ok = CliRunner().invoke(app, ["external", "check", "--db", str(db), "--figures", str(figures)])
    assert ok.exit_code == 0, ok.output
    assert "ok:" in ok.output
    changed = _csv(tmp_path / "changed.csv", [ROWS[0].replace("p. 3,", "p. 4,"), ROWS[1]])
    bad = CliRunner().invoke(app, ["external", "check", "--db", str(db), "--figures", str(changed)])
    assert bad.exit_code == 1
    assert "berlin official_berlin protected_km" in bad.output
    assert "velometer external load --no-qecio --no-bikenetkit" in bad.output
    assert _md5(db) == before


def test_the_check_command_refuses_a_missing_csv(loaded, tmp_path):
    db, _ = loaded
    r = CliRunner().invoke(
        app, ["external", "check", "--db", str(db), "--figures", str(tmp_path / "none.csv")]
    )
    assert r.exit_code == 1


def test_a_row_after_a_multi_line_note_is_named_by_its_own_line(loaded, tmp_path):
    """M10: a quoted note spanning lines shifts every later row; the line is where it starts."""
    db, _ = loaded
    first = ROWS[0].replace("Senate report p. 3,", '"Senate report p. 3,\nsecond line\nthird",')
    changed = _csv(tmp_path / "multi.csv", [first, ROWS[1].replace(",1700,", ",1701,")])
    problems = _drift(db, changed)
    assert any(p.startswith("figures.csv line 2, berlin") for p in problems), problems
    assert any(p.startswith("figures.csv line 5, vienna") for p in problems), problems


def test_row_lines_follow_the_csv_reader(tmp_path):
    path = tmp_path / "f.csv"
    path.write_text('a,b\n1,"x\ny"\n\n2,z\n3,"p\n\nq"\n4,w\n', encoding="utf-8")
    assert X.row_lines(path) == [2, 5, 6, 9]
    with path.open(newline="", encoding="utf-8") as f:
        assert len(X.row_lines(path)) == len(list(csv.DictReader(f)))
