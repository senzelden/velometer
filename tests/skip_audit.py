"""A pytest plugin for `test_m17_workflows`: records every skip a collection can see.

Loaded with `-p tests.skip_audit` in a `--collect-only` subprocess, it writes one JSON file (path
in `VELOMETER_SKIP_AUDIT`) with each test's `skip`/`skipif` marks and each module that skipped
itself while being collected. Runtime `pytest.skip(...)` calls are checked from the source.
"""

import json
import os
from pathlib import Path

_MARKS: list[dict] = []
_MODULES: list[dict] = []


def _reason(mark) -> str:
    if "reason" in mark.kwargs:
        return str(mark.kwargs["reason"] or "")
    if mark.name == "skip" and mark.args:
        return str(mark.args[0] or "")
    return ""


def pytest_collection_modifyitems(items):
    for item in items:
        for mark in item.iter_markers():
            if mark.name in ("skip", "skipif"):
                _MARKS.append({"nodeid": item.nodeid, "name": mark.name, "reason": _reason(mark)})


def pytest_collectreport(report):
    if report.skipped:
        longrepr = report.longrepr
        reason = longrepr[2] if isinstance(longrepr, tuple) else str(longrepr)
        _MODULES.append({"nodeid": report.nodeid, "reason": reason.removeprefix("Skipped: ")})


def pytest_sessionfinish(session):
    out = os.environ.get("VELOMETER_SKIP_AUDIT")
    if out:
        Path(out).write_text(json.dumps({"marks": _MARKS, "modules": _MODULES}), encoding="utf-8")
