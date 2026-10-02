import pytest

from tests.report_fixture import build_report_fixture
from velometer.report.data import ReportData, open_readonly


@pytest.fixture
def fixture_db(tmp_path):
    """The shared report fixture: (db_path, config_dir, read-only connection, ReportData)."""
    db_path, cfg = build_report_fixture(tmp_path)
    conn = open_readonly(db_path)
    yield db_path, cfg, conn, ReportData(conn, cfg)
    conn.close()
