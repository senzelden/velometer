import csv
import io
import shutil

import pytest
from typer.testing import CliRunner

from tests.report_fixture import (
    CLASSIFIER,
    SPIKE_YEAR,
)
from tests.sqlite_util import committing
from velometer.cli import app
from velometer.db import fetch_run_results
from velometer.pipeline.measure import select_metric
from velometer.report.csvexport import CSV_COLUMNS, to_csv
from velometer.timeseries import Flag

STAMP = "2026-10-02T00:00:00Z"


def _parse(text):
    body = [ln for ln in text.splitlines() if not ln.startswith("#")]
    return list(csv.DictReader(io.StringIO("\n".join(body))))


def test_csv_header_comments_columns_and_no_user_columns(fixture_db):
    _, cfg, conn, data = fixture_db
    text = to_csv(data.csv_rows(), "abc123", STAMP)
    lines = text.splitlines()
    assert (
        lines[0]
        == "# Map data © OpenStreetMap contributors, ODbL 1.0 — OSM mapped km, not built km"
    )
    assert lines[1] == "# velometer abc123 generated 2026-10-02T00:00:00Z"
    header = lines[2].split(",")
    assert header == CSV_COLUMNS and not {"uid", "user", "username"} & set(header)
    assert header[:3] == ["city_id", "boundary_kind", "label"] and header[-1] == "flags"


def test_csv_has_one_row_per_city_kind_label(fixture_db):
    rows = _parse(to_csv(fixture_db[3].csv_rows(), "c", STAMP))
    keys = [(r["city_id"], r["boundary_kind"], r["label"]) for r in rows]
    assert len(keys) == len(set(keys))
    assert ("berlin", "lau", "current") in keys and ("paris", "lau", "2025") in keys
    assert ("paris", "lau", "current") not in keys  # no current run: no row, not an error
    assert ("berlin", "fua", "current") in keys
    assert {r["city_id"] for r in fixture_db[3].csv_rows("paris")} == {"paris"}


def test_csv_row_values_match_db(fixture_db):
    _, cfg, conn, data = fixture_db
    rows = {
        (r["city_id"], r["boundary_kind"], r["label"]): r
        for r in _parse(to_csv(data.csv_rows(), "c", STAMP))
    }
    row = rows[("berlin", "lau", "current")]
    cur = data.current("berlin", "lau")
    results = fetch_run_results(conn, cur.run_id)
    head = select_metric(results.metrics, "ours_headline", data.selector.presets)
    assert row["run_id"] == str(cur.run_id) and row["osm_timestamp"] == cur.osm_timestamp
    assert row["classifier_version"] == CLASSIFIER and row["config_sha256"] == cur.config_sha256
    assert row["ours_headline"] == f"{head.value:.3f}"
    assert row["ab_km"] == f"{cur.ab_km:.3f}"
    assert all(row[f"tier_{t}_km"] == f"{cur.tiers_km[t]:.3f}" for t in "ABCDE")
    assert (row["population_value"], row["population_year"]) == ("100000", "2024")
    fua = rows[("berlin", "fua", "current")]
    assert fua["population_value"] == "" and fua["population_year"] == ""


def test_csv_flags_cell_is_semicolon_joined_rule_names(fixture_db):
    rows = _parse(to_csv(fixture_db[3].csv_rows(), "c", STAMP))
    by = {(r["city_id"], r["boundary_kind"], r["label"]): r["flags"] for r in rows}
    assert by[("berlin", "lau", SPIKE_YEAR)] == "activity_spike"
    assert by[("berlin", "lau", "2024")] == ""


def test_csv_joins_several_flags_with_semicolons(fixture_db, monkeypatch):
    data = fixture_db[3]
    real = data.flags("berlin", "lau")[0]
    two = Flag("berlin", "lau", real.label, ("km_jump", "activity_spike"), "")
    monkeypatch.setattr(data, "flags", lambda c, k: [two] if (c, k) == ("berlin", "lau") else [])
    rows = {(r["city_id"], r["boundary_kind"], r["label"]): r for r in data.csv_rows("berlin")}
    assert rows[("berlin", "lau", real.label)]["flags"] == "km_jump;activity_spike"


def test_cli_report_csv_stdout_and_out_file(fixture_db, tmp_path):
    db_path, cfg, _, _ = fixture_db
    args = ["report", "csv", "--db", str(db_path), "--config-dir", str(cfg)]
    res = CliRunner().invoke(app, [*args, "--city", "paris"])
    assert res.exit_code == 0, res.output
    lines = res.output.splitlines()
    assert lines[0].startswith("# Map data © OpenStreetMap contributors")
    assert lines[1].startswith("# velometer ") and lines[1].endswith("Z")
    assert {r["city_id"] for r in _parse(res.output)} == {"paris"}
    out = tmp_path / "all.csv"
    res = CliRunner().invoke(app, [*args, "--out", str(out)])
    assert res.exit_code == 0 and res.output == ""
    assert {r["city_id"] for r in _parse(out.read_text())} == {"berlin", "paris"}


def test_cli_report_csv_errors(fixture_db, tmp_path):
    db_path, cfg, _, _ = fixture_db
    res = CliRunner().invoke(app, ["report", "csv", "--db", str(tmp_path / "no.sqlite")])
    assert res.exit_code == 1 and "not found" in res.output
    res = CliRunner().invoke(
        app,
        ["report", "csv", "--db", str(db_path), "--config-dir", str(cfg), "--city", "nowhere"],
    )
    assert res.exit_code == 1 and "unknown city" in res.output


REPORT_COMMANDS = [["csv"], ["charts"], ["methodology", "--check"], ["maps"]]


def _report_args(command, db_path, cfg, tmp_path):
    args = ["report", *command, "--db", str(db_path), "--config-dir", str(cfg)]
    if command[0] == "charts":
        args += ["--out", str(tmp_path / "charts")]
    if command[0] == "methodology":
        args += ["--docs", str(tmp_path / "docs")]
    if command[0] == "maps":
        args += ["--data", str(tmp_path / "data")]
    return args


@pytest.mark.parametrize("command", REPORT_COMMANDS, ids=lambda c: c[0])
def test_report_commands_exit_1_on_a_bad_config(fixture_db, tmp_path, command):
    db_path, cfg, _, _ = fixture_db
    (cfg / "report.yaml").write_text("report_classifier: v2\nrankings: [{kind: nope}]\n")
    res = CliRunner().invoke(app, _report_args(command, db_path, cfg, tmp_path))
    assert res.exit_code == 1, res.output
    assert "report.yaml" in res.output  # names the bad file
    assert isinstance(res.exception, SystemExit)  # a message, not a traceback


@pytest.mark.parametrize("command", REPORT_COMMANDS, ids=lambda c: c[0])
def test_report_commands_exit_1_on_an_unmigrated_db(fixture_db, tmp_path, command):
    db_path, cfg, _, _ = fixture_db
    old = tmp_path / "v5.sqlite"
    shutil.copy(db_path, old)
    with committing(old) as c:
        c.execute("PRAGMA user_version = 5")
    res = CliRunner().invoke(app, _report_args(command, old, cfg, tmp_path))
    assert res.exit_code == 1, res.output
    assert "velometer migrate" in res.output
    assert isinstance(res.exception, SystemExit)
