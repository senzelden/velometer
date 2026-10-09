"""Commands that do not write the database open it read-only: a report run leaves its bytes
(header change counter included) as they were, and a missing or other-version database is a
clear exit 1, never a new or migrated file."""

import hashlib
import sqlite3

import pytest
from typer.testing import CliRunner

from tests.report_fixture import build_report_fixture_subareas
from velometer.cli import app
from velometer.db import SCHEMA_VERSION


def _md5(path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


READ_ONLY = [
    ["results"],
    ["results", "--subareas", "--city", "berlin"],
    ["reconcile"],
    ["reconcile", "--check", "--report", "{report}"],
    ["reconcile", "--write", "--report", "{report}"],  # writes the report file, not the DB
    ["timeseries"],
    ["timeseries", "--write", "--report", "{report}"],
    ["timeseries", "--subareas", "--city", "berlin"],
    ["counters", "--check"],
]


@pytest.mark.parametrize("args", READ_ONLY, ids=" ".join)
def test_a_command_that_does_not_write_leaves_the_db_bytes_identical(tmp_path, args):
    db_path, cfg = build_report_fixture_subareas(tmp_path)
    report = tmp_path / "r.md"
    argv = [a.format(report=report) for a in args]
    before = _md5(db_path)
    res = CliRunner().invoke(app, [*argv, "--db", str(db_path), "--config-dir", str(cfg)])
    assert res.exception is None or isinstance(res.exception, SystemExit), res.output
    assert "database error" not in res.output and "no subareas" not in res.output, res.output
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
