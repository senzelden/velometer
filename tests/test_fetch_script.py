import importlib.util
import re
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "fetch_berlin_golden.py"
_spec = importlib.util.spec_from_file_location("fetch_berlin_golden", _PATH)
fetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch)

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
