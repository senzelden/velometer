from pathlib import Path

import pytest
import yaml

from velometer.config import (
    ConfigError,
    default_config_dir,
    load_cities,
    load_classifier,
    load_presets,
)
from velometer.pipeline.match import matches, validate_expr

CFG = default_config_dir()


def test_pilot_cities_load_with_projected_epsg_and_integer_relations():
    cities = load_cities(CFG / "cities.yaml")
    assert {c.id for c in cities} == {"berlin", "paris", "vienna", "copenhagen", "wroclaw"}
    assert all(isinstance(c.osm_relation_id, int) and c.osm_relation_id > 0 for c in cities)


def test_geographic_epsg_is_rejected(tmp_path: Path):
    bad = tmp_path / "cities.yaml"
    bad.write_text(
        "cities:\n  - {id: x, name: X, country_iso2: DE, epsg: 4326,"
        " geofabrik_region: europe/x, osm_relation_id: 1}\n"
    )
    with pytest.raises(ConfigError, match=r"(?s)cities\.yaml.*EPSG:4326 is not a projected CRS"):
        load_cities(bad)


def test_presets_reference_known_denominators():
    classifier = load_classifier(CFG / "classifier" / "v1.yaml")
    presets = load_presets(CFG / "presets.yaml", classifier)
    assert {p.id for p in presets} == {"ours_headline", "ecf_qecio", "clean_cities_2025"}


def _classifier_with_rules(tmp_path: Path, rules: list[dict]) -> Path:
    data = yaml.safe_load((CFG / "classifier" / "v1.yaml").read_text())
    data["rules"] = rules
    p = tmp_path / "v1.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_shipped_classifier_loads():
    assert load_classifier(CFG / "classifier" / "v1.yaml").version == "v1"


def test_duplicate_rule_ids_rejected(tmp_path: Path):
    rule = {"id": "r", "applies_to": "standalone", "tier": "A", "match": {"highway": "cycleway"}}
    with pytest.raises(ConfigError, match="duplicate rule id"):
        load_classifier(_classifier_with_rules(tmp_path, [rule, rule]))


def test_unknown_value_list_rejected(tmp_path: Path):
    rule = {
        "id": "r",
        "applies_to": "road_side",
        "tier": "C",
        "match": {"cycleway:separation": {"in_list": "nope"}},
    }
    with pytest.raises(ConfigError, match="nope"):
        load_classifier(_classifier_with_rules(tmp_path, [rule]))


LISTS = {"phys": ["kerb", "bollard"]}


@pytest.mark.parametrize(
    ("expr", "tags", "expected"),
    [
        ({"highway": "cycleway"}, {"highway": "cycleway"}, True),
        ({"highway": ["path", "footway"]}, {"highway": "cycleway"}, False),
        ({"foot": {"absent": True}}, {}, True),
        ({"foot": {"absent": True}}, {"foot": "yes"}, False),
        ({"foot": {"not_in": ["designated"]}}, {}, True),
        ({"foot": {"not_in": ["designated"]}}, {"foot": "designated"}, False),
        ({"sep": {"in_list": "phys"}}, {"sep": "solid_line;kerb"}, True),
        ({"sep": {"in_list": "phys"}}, {"sep": " kerb "}, True),
        ({"sep": {"in_list": "phys"}}, {"sep": "solid_line"}, False),
        ({"segregated": True}, {"segregated": "yes"}, True),  # YAML 1.1 `yes` -> True
        ({"segregated": False}, {"segregated": "no"}, True),
        ({"any": [{"a": "1"}, {"b": "1"}]}, {"b": "1"}, True),
        ({"all": [{"a": "1"}, {"b": "1"}]}, {"b": "1"}, False),
        ({"not": {"a": "1"}}, {"a": "2"}, True),
        ({"highway": "cycleway", "foot": "designated"}, {"highway": "cycleway"}, False),
    ],
)
def test_match_semantics(expr, tags, expected):
    assert matches(expr, tags, LISTS) is expected


def test_validate_expr_rejects_unknown_operator():
    with pytest.raises(ValueError, match="unknown condition"):
        validate_expr({"a": {"regex": "x"}}, LISTS)


@pytest.mark.parametrize(
    "expr",
    [
        {"a": {"not_in": "designated"}},
        {"a": {"not_in": []}},
        {"a": {"absent": "no"}},
        {"a": {"in_list": ["phys"]}},
    ],
)
def test_validate_expr_rejects_bad_operator_payload(expr):
    with pytest.raises(ValueError, match="must be"):
        validate_expr(expr, LISTS)


def _presets_file(tmp_path: Path, tiers: list[str]) -> Path:
    p = tmp_path / "presets.yaml"
    preset = {"id": "p", "tiers": tiers, "basis": "per_side", "denominator": "all_public"}
    p.write_text(yaml.safe_dump({"presets": [preset]}))
    return p


@pytest.mark.parametrize("tiers", [["A", "B/segregated", "B/sidewalk", "E/bus"], ["C", "D"]])
def test_preset_tiers_accept_tiers_and_produced_subtypes(tmp_path: Path, tiers):
    classifier = load_classifier(CFG / "classifier" / "v1.yaml")
    (p,) = load_presets(_presets_file(tmp_path, tiers), classifier)
    assert p.tiers == tiers


@pytest.mark.parametrize(
    "tiers",
    [["F"], ["excluded"], ["a"], ["B/"], ["B/segregatd"], ["A/segregated"], ["E/sidewalk"], []],
)
def test_preset_tiers_reject_bad_grammar_or_unknown_subtype(tmp_path: Path, tiers):
    classifier = load_classifier(CFG / "classifier" / "v1.yaml")
    with pytest.raises(ConfigError, match="presets.yaml"):
        load_presets(_presets_file(tmp_path, tiers), classifier)
