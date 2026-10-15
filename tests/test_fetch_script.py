import re
from pathlib import Path

import pytest

from tests.helpers import load_script

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "fetch_berlin_golden.py"
fetch = load_script("scripts/fetch_berlin_golden.py")

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def test_script_contains_no_email_address():
    assert not EMAIL.search(_PATH.read_text())


def test_user_agent_has_no_contact_unless_env_set(monkeypatch):
    monkeypatch.delenv("VELOMETER_CONTACT", raising=False)
    assert fetch.user_agent() == "velometer-golden-fetch/0.1 (Berlin golden set for tests)"
    monkeypatch.setenv("VELOMETER_CONTACT", "https://example.org/velometer")
    assert fetch.user_agent().endswith("; https://example.org/velometer")


def test_overpass_remark_in_json_raises():
    with pytest.raises(RuntimeError, match="remark"):
        fetch.check_json({"elements": [], "remark": "runtime error: timeout"}, "g")
    assert fetch.check_json({"elements": [{"id": 1}]}, "g") == [{"id": 1}]


def test_phase2_xml_with_remark_or_missing_ids_raises():
    ok = '<osm><way id="1"></way><way id="2"></way></osm>'
    fetch.check_xml(ok, [1, 2])
    with pytest.raises(RuntimeError, match=r"\[2\]"):
        fetch.check_xml('<osm><way id="1"></way></osm>', [1, 2])
    with pytest.raises(RuntimeError, match="remark"):
        fetch.check_xml(ok + "<remark> runtime error </remark>", [1, 2])


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_downloads_are_stripped_of_editor_metadata():
    xml = '<node id="1" version="2" timestamp="t" changeset="3" uid="4" user="someone"/>'
    assert fetch.strip_editor_metadata(xml) == '<node id="1" version="2" timestamp="t"/>'


@pytest.mark.parametrize("path", sorted(FIXTURES.rglob("*.osm")), ids=lambda p: p.name)
def test_no_osm_fixture_carries_a_mapper_name_or_uid(path):
    assert not re.search(r'\s(?:user|uid)="', path.read_text(encoding="utf-8"))
