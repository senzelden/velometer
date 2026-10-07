"""Plan config models and loader: figures stored as printed, later documents current (M8 §4.1)."""

import shutil
from datetime import date
from pathlib import Path

import pytest

from velometer.config import ConfigError, default_config_dir
from velometer.plans.models import (
    REPORT_COLUMNS,
    ReportRow,
    current_and_revisions,
    load_plans,
)

PLANS = Path(__file__).parent / "fixtures" / "content_m8" / "config" / "plans"


@pytest.fixture
def plan_dir(tmp_path) -> Path:
    d = tmp_path / "plans"
    shutil.copytree(PLANS, d)
    return d


def _row(doc_id: str, doc_date: str, value: float, **kw) -> ReportRow:
    base = dict(
        plan_id="berlin_rvp_2021",
        item_id="vorrangnetz",
        year=2025,
        value=value,
        unit="km",
        quantity="implemented_in_year",
        doc_type="drucksache",
        doc_id=doc_id,
        doc_date=doc_date,
        url="https://example.org/x",
        locator="p. 1",
        retrieved_at="2026-10-07",
        publisher="senmvku",
    )
    return ReportRow.model_validate({**base, **kw})


def test_fixture_plans_and_rows_load(plan_dir):
    plans, rows = load_plans(plan_dir)
    assert [p.id for p in plans] == ["berlin_rvp_2021", "paris_plan_velo"]
    assert plans[0].items[0].targets == {2025: 150.0}
    assert plans[0].adopted == date(2021, 11, 16) and plans[1].adopted is None
    assert [r.value for r in rows] == [10.8, 8.6, 1.0]
    assert rows[0].note is None and rows[1].note == "later document disagrees"


def test_the_shipped_plan_files_are_empty_and_load():
    plans, rows = load_plans(default_config_dir() / "plans")
    assert (plans, rows) == ([], [])


def test_later_document_is_current_and_the_earlier_a_revision():
    # Vorrangnetz 2025 printed 10.8 in one document and 8.6 in a later one (synthetic doc ids)
    early = _row("TEST/0001", "2025-03-01", 10.8)
    late = _row("TEST/0002", "2025-09-01", 8.6)
    for rows in ([early, late], [late, early]):
        got = current_and_revisions(rows)
        key = ("berlin_rvp_2021", "vorrangnetz", 2025, "implemented_in_year")
        assert list(got) == [key]
        current, revisions = got[key]
        assert current.value == 8.6 and [r.value for r in revisions] == [10.8]


def test_quantities_are_kept_apart():
    a = _row("A", "2025-03-01", 1.0)
    b = _row("B", "2025-09-01", 2.0, quantity="under_construction")
    got = current_and_revisions([a, b])
    assert len(got) == 2 and all(revs == [] for _, revs in got.values())


def test_bad_header_is_a_config_error(plan_dir):
    path = plan_dir / "reports.csv"
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0].replace(",publisher", "")] + lines[1:]) + "\n")
    with pytest.raises(ConfigError, match="header must be"):
        load_plans(plan_dir)


def test_unknown_doc_type_names_the_line(plan_dir):
    path = plan_dir / "reports.csv"
    path.write_text(path.read_text().replace("rote_nummer", "memo"))
    with pytest.raises(ConfigError, match=r"reports.csv:2"):
        load_plans(plan_dir)


def test_duplicate_plan_and_item_ids_are_refused(plan_dir):
    path = plan_dir / "plans.yaml"
    text = path.read_text()
    path.write_text(text.replace("id: paris_plan_velo", "id: berlin_rvp_2021"))
    with pytest.raises(ConfigError, match="duplicate plan id"):
        load_plans(plan_dir)
    item = "    - {id: total, label: Plan total, target_kind: none}\n"
    path.write_text(text.replace(item, item * 2))
    with pytest.raises(ConfigError, match="duplicate item id"):
        load_plans(plan_dir)


def test_report_columns_are_the_model_fields_in_order():
    assert REPORT_COLUMNS[:3] == ("plan_id", "item_id", "year")
    assert REPORT_COLUMNS[-2:] == ("note", "publisher")
    header = (default_config_dir() / "plans" / "reports.csv").read_text().strip()
    assert header == ",".join(REPORT_COLUMNS)
