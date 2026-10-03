"""The signed-off golden ways of each new country (tests/fixtures/golden/<cc>.yaml/.osm), checked
against the report classifier. Berlin's older set is tests/test_golden.py (classifier v1)."""

from collections import defaultdict
from pathlib import Path

import pytest
import yaml

from tests.golden_util import check_country_golden
from velometer.config import default_config_dir, load_classifier, load_report
from velometer.pipeline.classify import classify_ways
from velometer.pipeline.read import read_ways

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
CONFIG = default_config_dir()
REPORT_CLASSIFIER = load_report(CONFIG / "report.yaml", CONFIG / "presets.yaml").report_classifier


@pytest.mark.parametrize("yml", sorted(GOLDEN_DIR.glob("*.yaml")), ids=lambda p: p.stem)
def test_confirmed_ways_match_the_report_classifier(yml):
    cfg = load_classifier(CONFIG / "classifier" / f"{REPORT_CLASSIFIER}.yaml")
    observed: dict[int, set[tuple]] = defaultdict(set)
    for c in classify_ways(read_ways(yml.with_suffix(".osm")).ways, cfg):
        if c.tier is not None:
            observed[c.side.way_id].add((c.side.side, c.tier, c.rule_id))
    check_country_golden(yml.stem.upper(), yaml.safe_load(yml.read_text())["ways"], observed)
