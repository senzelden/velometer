"""The signed-off golden ways of each new country (tests/fixtures/golden/<cc>.yaml/.osm), checked
against the report classifier. Berlin's older set is tests/test_golden.py (classifier v1)."""

from pathlib import Path

import pytest
import yaml

from tests.golden_util import check_country_golden
from velometer.config import default_config_dir, load_classifier, load_report
from velometer.pipeline.read import read_ways
from velometer.trust import ODBL, observed_tiers

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
CONFIG = default_config_dir()
REPORT_CLASSIFIER = load_report(CONFIG / "report.yaml", CONFIG / "presets.yaml").report_classifier


@pytest.mark.parametrize("yml", sorted(GOLDEN_DIR.glob("*.yaml")), ids=lambda p: p.stem)
def test_confirmed_ways_match_the_report_classifier(yml):
    cfg = load_classifier(CONFIG / "classifier" / f"{REPORT_CLASSIFIER}.yaml")
    observed = observed_tiers(read_ways(yml.with_suffix(".osm")).ways, cfg)
    ways = yaml.safe_load(yml.read_text())["ways"]
    check_country_golden(yml.stem.upper(), ways, observed, cfg.version)


@pytest.mark.parametrize("osm", sorted(GOLDEN_DIR.glob("*.osm")), ids=lambda p: p.stem)
def test_every_golden_osm_carries_the_odbl_note(osm):
    # ADR 0008: each test fixture with real OSM data carries an attribution note
    head = osm.read_text().splitlines()[:3]
    assert f"<!-- {ODBL} -->" in head, head


def _golden_ids_missing_from_osm(yml: Path, osm: Path) -> set[int]:
    want = {w["way_id"] for w in yaml.safe_load(yml.read_text())["ways"]}
    return want - {w.id for w in read_ways(osm).ways}


@pytest.mark.parametrize("yml", sorted(GOLDEN_DIR.glob("*.yaml")), ids=lambda p: p.stem)
def test_every_golden_way_is_in_the_osm_fixture(yml):
    # a way expecting `proposed: []` (unrecognised) would otherwise match vacuously when absent
    assert _golden_ids_missing_from_osm(yml, yml.with_suffix(".osm")) == set()


def test_a_golden_way_missing_from_the_osm_is_caught(tmp_path):
    import re
    import shutil

    yml = GOLDEN_DIR / "sk.yaml"
    gone = yaml.safe_load(yml.read_text())["ways"][0]["way_id"]
    osm = tmp_path / "sk.osm"
    text = (GOLDEN_DIR / "sk.osm").read_text()
    osm.write_text(re.sub(rf'  <way id="{gone}".*?</way>\n', "", text, flags=re.S))
    shutil.copy(yml, tmp_path / "sk.yaml")
    assert _golden_ids_missing_from_osm(tmp_path / "sk.yaml", osm) == {gone}
