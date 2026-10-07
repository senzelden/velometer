import pytest
import yaml

from tests.report_fixture import build_report_fixture, build_report_fixture_n
from velometer.report.data import ReportData, open_readonly


def pytest_collection_modifyitems(items):
    """Slow tests (network, full-size data) run without the suite's per-test timeout."""
    for item in items:
        if item.get_closest_marker("slow") and not item.get_closest_marker("timeout"):
            item.add_marker(pytest.mark.timeout(0))


@pytest.fixture
def fixture_db(tmp_path):
    """The shared report fixture: (db_path, config_dir, read-only connection, ReportData)."""
    db_path, cfg = build_report_fixture(tmp_path)
    conn = open_readonly(db_path)
    yield db_path, cfg, conn, ReportData(conn, cfg)
    conn.close()


@pytest.fixture
def report_db_with_trust(tmp_path):
    """Factory `(countries) -> (db_path, config_dir)`: the report fixture whose config copy's
    trust.yaml lists exactly `countries` (ISO2 -> CountryTrust fields); the rest are pending."""

    def build(countries: dict[str, dict]):
        db_path, cfg = build_report_fixture(tmp_path)
        trust = yaml.safe_load((cfg / "trust.yaml").read_text())
        trust["countries"] = countries
        (cfg / "trust.yaml").write_text(yaml.safe_dump(trust))
        return db_path, cfg

    return build


@pytest.fixture
def report_db_21(tmp_path):
    """(db_path, config_dir) of the report fixture grown to 21 cities (berlin, paris, c03..c21)."""
    return build_report_fixture_n(tmp_path, 21)
