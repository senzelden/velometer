"""Commands that do not write the database open it read-only: a report run leaves its bytes
(header change counter included) as they were, and a missing or other-version database is a
clear exit 1, never a new or migrated file."""

import hashlib
import sqlite3
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from tests.report_fixture import build_report_fixture_subareas
from velometer import reconcile as rc
from velometer import timeseries as ts
from velometer.cli import app
from velometer.db import SCHEMA_VERSION


def _md5(path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


# (arguments, exit code): each command runs to its end on the report fixture
READ_ONLY = [
    (["results"], 0),
    (["results", "--subareas", "--city", "berlin"], 0),
    (["reconcile"], 0),
    (["reconcile", "--check", "--city", "berlin", "--report", "{report}"], 0),
    (["reconcile", "--write", "--report", "{report}"], 0),  # writes the report file, not the DB
    (["timeseries"], 0),
    (["timeseries", "--write", "--report", "{report}"], 0),
    (["timeseries", "--subareas", "--city", "berlin"], 0),
    (["counters", "--check"], 1),  # the fixture stores no counter data: every city is reported
]


def _seed_report(report: Path, argv: list[str], tail: list[str]) -> None:
    """The report file with both generated blocks; for `reconcile --check`, its block written,
    each flagged gap explained and the explained-against marker set, so the check passes."""
    report.write_text(f"# Report\n\n{rc.BEGIN}\n{rc.END}\n\n{ts.BEGIN}\n{ts.END}\n")
    if argv[:2] != ["reconcile", "--check"]:
        return
    cfg = Path(tail[tail.index("--config-dir") + 1])
    doc = yaml.safe_load((cfg / "reconcile.yaml").read_text())
    for comp in doc["comparisons"]:  # the fixture has no BikeNetKit figure
        comp.pop("required", None)
    (cfg / "reconcile.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    write = ["reconcile", "--write", "--report", str(report), *tail]
    assert CliRunner().invoke(app, write).exit_code == 0
    first = CliRunner().invoke(app, [*argv, *tail]).stderr.splitlines()
    marker = [ln.split("set: ", 1)[1] for ln in first if "set: <!-- explained-against:" in ln]
    gaps = [ln.removeprefix("missing explanation: ") for ln in first if ln.startswith("missing")]
    assert marker and gaps, first  # the fixture's flagged gaps, explained below
    explained = "".join(f"\n{heading}\n\nExplained.\n" for heading in gaps)
    report.write_text(report.read_text() + f"\n{marker[0]}\n{explained}")


@pytest.mark.parametrize(("args", "code"), READ_ONLY, ids=[" ".join(a) for a, _ in READ_ONLY])
def test_a_command_that_does_not_write_leaves_the_db_bytes_identical(tmp_path, args, code):
    db_path, cfg = build_report_fixture_subareas(tmp_path)
    report = tmp_path / "r.md"
    argv = [a.format(report=report) for a in args]
    tail = ["--db", str(db_path), "--config-dir", str(cfg)]
    _seed_report(report, argv, tail)
    before = _md5(db_path)
    res = CliRunner().invoke(app, [*argv, *tail])
    assert res.exit_code == code, res.output
    assert res.exception is None or isinstance(res.exception, SystemExit), res.output
    assert "database error" not in res.output and "no subareas" not in res.output, res.output
    if code:
        assert "no counter sites" in res.output, res.output  # it read the database
    assert _md5(db_path) == before


@pytest.mark.parametrize("args", [["results"], ["reconcile"], ["timeseries"], ["counters"]])
def test_a_missing_db_is_an_error_and_not_created(tmp_path, args):
    db = tmp_path / "none.sqlite"
    argv = [*args, "--check"] if args == ["counters"] else args
    res = CliRunner().invoke(app, [*argv, "--db", str(db)])
    assert res.exit_code == 1 and isinstance(res.exception, SystemExit), res.output
    assert "database not found" in res.output
    assert not db.exists()


@pytest.mark.parametrize("args", [["results"], ["reconcile"], ["timeseries"], ["counters"]])
def test_an_older_schema_is_an_error_and_not_migrated(tmp_path, args):
    db = tmp_path / "old.sqlite"
    with sqlite3.connect(db) as c:
        c.execute(f"PRAGMA user_version = {SCHEMA_VERSION - 1}")
    before = _md5(db)
    argv = [*args, "--check"] if args == ["counters"] else args
    res = CliRunner().invoke(app, [*argv, "--db", str(db)])
    assert res.exit_code == 1 and isinstance(res.exception, SystemExit), res.output
    assert "database error" in res.output and "velometer migrate" in res.output
    assert _md5(db) == before
