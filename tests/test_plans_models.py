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


def test_the_shipped_plan_files_load():
    plans, rows = load_plans(default_config_dir() / "plans")
    assert isinstance(plans, list) and isinstance(rows, list)


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
    assert REPORT_COLUMNS[-2:] == ("suspect", "cumulative_from")
    header = (default_config_dir() / "plans" / "reports.csv").read_text().splitlines()[0]
    columns = tuple(header.split(","))
    # a shipped file may still lack the trailing optional columns, never reorder the rest
    assert columns == REPORT_COLUMNS[: len(columns)]
    assert len(columns) >= len(REPORT_COLUMNS) - 2


def test_rows_lacking_the_optional_columns_get_defaults(plan_dir):
    path = plan_dir / "reports.csv"
    lines = [",".join(ln.split(",")[:-2]) for ln in path.read_text().splitlines()]
    path.write_text("\n".join(lines) + "\n")
    _, rows = load_plans(plan_dir)
    assert all(r.suspect is False and r.cumulative_from is None for r in rows)


def test_optional_columns_are_read(plan_dir):
    _, rows = load_plans(plan_dir)
    assert rows[2].cumulative_from == 2020 and rows[2].suspect is False
    path = plan_dir / "reports.csv"
    lines = path.read_text().splitlines()
    lines[1] = lines[1][:-2] + ",true,"
    path.write_text("\n".join(lines) + "\n")
    assert load_plans(plan_dir)[1][0].suspect is True


def test_a_suspect_row_is_never_current_while_a_clean_one_exists():
    clean = _row("A", "2025-03-01", 1.0)
    suspect = _row("B", "2025-09-01", 2.0, suspect=True)
    for rows in ([clean, suspect], [suspect, clean]):
        current, revisions = next(iter(current_and_revisions(rows).values()))
        assert current.value == 1.0 and [r.value for r in revisions] == [2.0]
    only = current_and_revisions([suspect])
    assert next(iter(only.values()))[0].value == 2.0


def test_equal_dates_prefer_drucksache_and_rote_nummer_over_report_over_web():
    web = _row("W", "2025-03-01", 1.0, doc_type="web")
    report = _row("R", "2025-03-01", 2.0, doc_type="report")
    ds = _row("D", "2025-03-01", 3.0, doc_type="drucksache")
    rn = _row("N", "2025-03-01", 4.0, doc_type="rote_nummer")
    key = next(iter(current_and_revisions([web]).keys()))
    assert current_and_revisions([web, report])[key][0].value == 2.0
    assert current_and_revisions([report, web])[key][0].value == 2.0
    assert current_and_revisions([web, report, ds])[key][0].value == 3.0
    # drucksache = rote_nummer: then file order decides
    assert current_and_revisions([ds, rn])[key][0].value == 4.0
    assert current_and_revisions([rn, ds])[key][0].value == 3.0
    # a later date still beats a better type
    later = _row("L", "2025-04-01", 5.0, doc_type="web")
    assert current_and_revisions([ds, later])[key][0].value == 5.0
