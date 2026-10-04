from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml
from pydantic import ValidationError

from velometer.config import (
    CityConfig,
    ConfigError,
    default_config_dir,
    load_cities,
    load_classifier,
    load_history,
    load_presets,
    load_report,
)
from velometer.pipeline.match import matches, validate_expr

CFG = default_config_dir()


def test_pilot_cities_load_with_projected_epsg_and_integer_relations():
    cities = load_cities(CFG / "cities.yaml")
    ids = [c.id for c in cities]
    assert {"berlin", "paris", "vienna", "copenhagen", "wroclaw"} <= set(ids)
    assert len(ids) == len(set(ids))
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
    presets = load_presets(CFG / "presets.yaml", classifier).presets
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


def test_prefix_key_collects_every_matching_key():
    tags = {"mtb:scale:imba": "2"}
    assert matches({"mtb:scale*": {"absent": False}}, tags, {})
    assert matches({"mtb:scale*": {"absent": False}}, {"mtb:scale": "0"}, {})
    assert not matches({"mtb:scale*": {"absent": False}}, {"mtb": "yes"}, {})
    assert matches({"mtb:scale*": ["2"]}, {"mtb:scale": "1", "mtb:scale:imba": "2"}, {})


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
    (p,) = load_presets(_presets_file(tmp_path, tiers), classifier).presets
    assert p.tiers == tiers


@pytest.mark.parametrize(
    "tiers",
    [["F"], ["excluded"], ["a"], ["B/"], ["B/segregatd"], ["A/segregated"], ["E/sidewalk"], []],
)
def test_preset_tiers_reject_bad_grammar_or_unknown_subtype(tmp_path: Path, tiers):
    classifier = load_classifier(CFG / "classifier" / "v1.yaml")
    with pytest.raises(ConfigError, match="presets.yaml"):
        load_presets(_presets_file(tmp_path, tiers), classifier)


def test_plain_cycleway_on_oneway_parameter_defaults_and_validates(tmp_path):
    cfg = load_classifier(CFG / "classifier" / "v1.yaml")
    assert cfg.parameters.plain_cycleway_on_oneway == "traffic_side"
    raw = yaml.safe_load((CFG / "classifier" / "v1.yaml").read_text())
    raw["parameters"]["plain_cycleway_on_oneway"] = "sometimes"
    bad = tmp_path / "v1.yaml"
    bad.write_text(yaml.safe_dump(raw))
    with pytest.raises(ConfigError, match="plain_cycleway_on_oneway"):
        load_classifier(bad)


def _basis_presets(tmp_path: Path, basis, parameters=None) -> Path:
    preset = {"id": "p", "tiers": ["A"], "basis": basis, "denominator": "all_public"}
    doc = {"presets": [preset]}
    if parameters is not None:
        doc["parameters"] = parameters
    p = tmp_path / "presets.yaml"
    p.write_text(yaml.safe_dump(doc))
    return p


def test_shipped_presets_parameterise_only_clean_cities_and_default_to_per_side():
    classifier = load_classifier(CFG / "classifier" / "v1.yaml")
    config = load_presets(CFG / "presets.yaml", classifier)
    assert config.parameters.clean_cities_basis == "per_side"  # ADR 0003 default
    assert {p.id for p in config.presets if p.parameterised} == {"clean_cities_2025"}
    cc = config.preset("clean_cities_2025")
    assert config.parameters.resolve(cc.basis) == "per_side"
    switched = config.with_parameters(clean_cities_basis="qecio_weighted")
    assert switched.parameters.resolve(cc.basis) == "qecio_weighted"


def test_basis_parameter_reference_must_name_a_known_parameter(tmp_path: Path):
    classifier = load_classifier(CFG / "classifier" / "v1.yaml")
    ok = _basis_presets(tmp_path, {"parameter": "clean_cities_basis"})
    assert load_presets(ok, classifier).presets[0].parameterised
    bad = _basis_presets(tmp_path, {"parameter": "no_such_parameter"})
    with pytest.raises(ConfigError, match=r"(?s)presets\.yaml.*no_such_parameter"):
        load_presets(bad, classifier)


def test_basis_parameter_value_must_be_a_valid_basis(tmp_path: Path):
    classifier = load_classifier(CFG / "classifier" / "v1.yaml")
    bad = _basis_presets(tmp_path, {"parameter": "clean_cities_basis"}, {"clean_cities_basis": "x"})
    with pytest.raises(ConfigError, match="clean_cities_basis"):
        load_presets(bad, classifier)
    with pytest.raises(ConfigError, match="presets.yaml"):
        load_presets(_basis_presets(tmp_path, "sideways"), classifier)


def _report(tmp_path: Path, text: str) -> Path:
    (tmp_path / "presets.yaml").write_text((CFG / "presets.yaml").read_text())
    path = tmp_path / "report.yaml"
    path.write_text(text)
    return path


def test_load_report_accepts_the_shipped_file():
    report = load_report(CFG / "report.yaml")
    shipped = CFG / "classifier" / f"{report.report_classifier}.yaml"
    assert shipped.is_file()
    assert {r.kind for r in report.rankings} == {"preset", "external", "external_ratio"}
    presets = {p.id for p in load_presets(CFG / "presets.yaml", load_classifier(shipped)).presets}
    assert {r.preset for r in report.rankings if r.kind == "preset"} <= presets


def test_load_report_rejects_an_unknown_key(tmp_path: Path):
    path = _report(tmp_path, "report_classifier: v2\nrankings: []\nextra: 1\n")
    with pytest.raises(ConfigError, match=r"(?s)report\.yaml.*extra"):
        load_report(path)


def test_load_report_rejects_an_unknown_kind(tmp_path: Path):
    path = _report(
        tmp_path, "report_classifier: v2\nrankings:\n  - {id: x, label: X, kind: magic}\n"
    )
    with pytest.raises(ConfigError, match=r"(?s)report\.yaml.*magic"):
        load_report(path)


def test_load_report_rejects_a_preset_not_in_presets_yaml(tmp_path: Path):
    path = _report(
        tmp_path,
        "report_classifier: v2\nrankings:\n"
        "  - {id: x, label: X, kind: preset, preset: no_such_preset}\n",
    )
    with pytest.raises(ConfigError, match=r"(?s)report\.yaml.*no_such_preset.*presets\.yaml"):
        load_report(path)


def test_load_report_rejects_duplicate_ranking_ids(tmp_path: Path):
    row = "  - {id: x, label: X, kind: preset, preset: ours_headline}\n"
    path = _report(tmp_path, "report_classifier: v2\nrankings:\n" + row + row)
    with pytest.raises(ConfigError, match="duplicate ranking ids"):
        load_report(path)


def test_history_yaml_with_report_classifier_points_to_report_yaml(tmp_path: Path):
    path = tmp_path / "history.yaml"
    path.write_text((CFG / "history.yaml").read_text() + "report_classifier: v2\n")
    with pytest.raises(ConfigError, match=r"(?s)history\.yaml.*config/report\.yaml"):
        load_history(path)


BERLIN = {
    "id": "berlin",
    "name": "Berlin",
    "country_iso2": "DE",
    "epsg": 25833,
    "geofabrik_region": "europe/germany/berlin",
    "osm_relation_id": 62422,
}


def test_epsg_must_be_etrs89_utm():
    assert CityConfig.model_validate(BERLIN).admin_boundary == "gisco"
    for bad in (3857, 32633, 25827, 25839):
        with pytest.raises(ValidationError):
            CityConfig.model_validate({**BERLIN, "epsg": bad})


def test_admin_boundary_and_urau_fields():
    c = CityConfig.model_validate(
        {**BERLIN, "admin_boundary": "osm_relation", "population_urau": "FR003C"}
    )
    assert c.admin_boundary == "osm_relation" and c.population_urau == "FR003C"
    with pytest.raises(ValidationError):
        CityConfig.model_validate({**BERLIN, "admin_boundary": "other"})


def test_real_cities_epsg_in_range_and_blank_exception_is_rejected():
    cities = load_cities(CFG / "cities.yaml")
    assert all(25828 <= c.epsg <= 25838 for c in cities)
    with pytest.raises(ValidationError):
        CityConfig.model_validate({**BERLIN, "epsg_exception": "  "})


def _role_report(tmp_path: Path, **lists: str) -> Path:
    extra = "".join(f"{k}: {v}\n" for k, v in lists.items())
    return _report(tmp_path, "report_classifier: v2\nrankings: []\n" + extra)


def test_report_roles_default_to_berlin_and_no_comparison_set(tmp_path: Path):
    report = load_report(_role_report(tmp_path))
    assert report.highlight == ["berlin"] and report.comparison_set == []


def test_shipped_report_roles_are_cities(tmp_path: Path):
    report = load_report(CFG / "report.yaml", cities_path=CFG / "cities.yaml")
    assert report.highlight == ["berlin"]
    assert report.comparison_set


@pytest.mark.parametrize("field", ["highlight", "comparison_set"])
def test_unknown_highlight_city_is_a_config_error(tmp_path: Path, field: str):
    path = _role_report(tmp_path, **{field: "[atlantis]"})
    load_report(path)  # unchecked without a cities file
    with pytest.raises(ConfigError, match=rf"(?s)report\.yaml.*{field}.*'atlantis'"):
        load_report(path, cities_path=CFG / "cities.yaml")


def test_a_city_in_both_role_lists_is_a_config_error(tmp_path: Path):
    path = _role_report(tmp_path, highlight="[berlin]", comparison_set="[berlin, paris]")
    with pytest.raises(ConfigError, match=r"(?s)report\.yaml.*both.*berlin"):
        load_report(path)


@pytest.mark.parametrize("field", ["highlight", "comparison_set"])
def test_a_duplicate_id_within_a_role_list_is_a_config_error_naming_it(tmp_path: Path, field):
    path = _role_report(tmp_path, **{field: "[paris, wien, paris]"})
    with pytest.raises(ConfigError, match=rf"(?s)report\.yaml.*duplicate.*{field}.*'paris'"):
        load_report(path)
    load_report(_role_report(tmp_path, **{field: "[paris, wien]"}))  # distinct ids are fine


SK = {**BERLIN, "lau_code": None, "lau_codes": ["SK_A", "SK_B"]}


def test_lau_codes_are_accepted_without_lau_code():
    c = CityConfig.model_validate(SK)
    assert c.lau_codes == ["SK_A", "SK_B"] and c.lau_code is None


def test_lau_codes_and_lau_code_are_exclusive():
    with pytest.raises(ValidationError, match="not both"):
        CityConfig.model_validate({**SK, "lau_code": "DE_1"})


def test_a_single_code_belongs_in_lau_code_not_lau_codes():
    with pytest.raises(ValidationError):
        CityConfig.model_validate({**SK, "lau_codes": ["SK_A"]})


def test_lau_codes_default_to_none():
    assert CityConfig.model_validate({**BERLIN, "lau_code": None}).lau_codes is None


def test_lau_codes_with_an_osm_relation_admin_boundary_is_a_config_error(tmp_path: Path):
    cities = {"cities": [{**SK, "admin_boundary": "osm_relation"}]}
    path = tmp_path / "cities.yaml"
    path.write_text(yaml.safe_dump(cities))
    with pytest.raises(ConfigError, match=r"(?s)cities\.yaml.*lau_codes.*osm_relation.*two admin"):
        load_cities(path)
    cities["cities"][0]["admin_boundary"] = "gisco"  # the same city is fine on the GISCO layer
    path.write_text(yaml.safe_dump(cities))
    assert load_cities(path)[0].lau_codes == ["SK_A", "SK_B"]


OVERRIDE = {
    "value": 522250,
    "year": 2022,
    "source": "INSEE population légale 2022",
    "source_url": "https://www.insee.fr/fr/statistiques/example",
}


def test_population_override_validation():
    c = CityConfig.model_validate({**BERLIN, "population_override": OVERRIDE})
    assert c.population_override.value == 522250 and c.population_override.year == 2022
    assert CityConfig.model_validate(BERLIN).population_override is None
    for bad in (
        {"value": 0},
        {"value": -3},
        {"year": 1999},
        {"year": 2031},
        {"source": "  "},
        {"source_url": "http://insee.fr/x"},
        {"source_url": "insee.fr/x"},
    ):
        with pytest.raises(ValidationError):
            CityConfig.model_validate({**BERLIN, "population_override": {**OVERRIDE, **bad}})


def test_population_override_source_urls_are_https_and_not_a_js_page():
    # the INE table page (Tabla.htm) renders its numbers in JavaScript: cite the data API instead
    overrides = [c for c in load_cities(CFG / "cities.yaml") if c.population_override]
    assert overrides
    for c in overrides:
        url = c.population_override.source_url
        assert url.startswith("https://"), c.id
        assert not urlparse(url).path.endswith((".htm", ".html")), c.id
