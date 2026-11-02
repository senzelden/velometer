"""M17 Task 8: the GitHub workflows (spec section 4.4) and the guard on skips.

`ci.yml` runs the gate on every push and PR from a fresh checkout, which has no
`velometer.sqlite`, no `data/` and no build output. The rules here are what keeps that run honest:
pinned actions, no secrets, no `pull_request_target`, full git history (sitemap `lastmod`, ruling
T3a), every gate command present, the test shards covering every test file once, and every skip
naming its reason, with the tests that skip for want of the database listed in the evidence.
"""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.shard import shard_index

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
EVIDENCE = ROOT / "docs" / "review" / "m17-ci.md"
DB_SECTION = "## Tests that skip without velometer.sqlite"
SHA_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def _workflow_files() -> list[Path]:
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    assert CI in files, "ci.yml is missing"
    return files


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(doc: dict) -> dict:
    on = doc.get("on", doc.get(True))  # YAML 1.1 reads a bare `on:` key as True
    if isinstance(on, str):
        return {on: None}
    if isinstance(on, list):
        return dict.fromkeys(on)
    return on or {}


def _steps(doc: dict) -> list[dict]:
    return [step for job in doc["jobs"].values() for step in job.get("steps", [])]


def _uses(doc: dict) -> list[str]:
    """Every `uses:` of a workflow: its steps' actions and jobs that call a reusable workflow."""
    jobs = doc["jobs"].values()
    return [s["uses"] for s in _steps(doc) if "uses" in s] + [
        j["uses"] for j in jobs if "uses" in j
    ]


def test_actions_pinned():
    for path in _workflow_files():
        uses = _uses(_load(path))
        assert uses, f"{path.name}: no actions found"
        for ref in uses:
            assert SHA_PIN.match(ref), f"{path.name}: {ref} is not pinned to a commit SHA"
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.match(r"\s*(-\s+)?uses:", line):
                assert re.search(r"#\s*v\d+(\.\d+)*\s*$", line), f"no version comment: {line}"


def test_no_pull_request_target():
    for path in _workflow_files():
        assert "pull_request_target" not in _triggers(_load(path)), path.name
        assert "pull_request_target" not in path.read_text(encoding="utf-8"), path.name


def test_ci_has_no_secrets():
    text = CI.read_text(encoding="utf-8")
    assert not re.search(r"\bsecrets\s*(\.|\[)", text)
    assert "secrets: inherit" not in text


def test_ci_runs_on_push_and_pr_with_read_only_permissions():
    doc = _load(CI)
    assert {"push", "pull_request"} <= set(_triggers(doc))
    assert doc["permissions"] == {"contents": "read"}
    assert {"lint", "test", "node"} <= set(doc["jobs"])
    for name, job in doc["jobs"].items():
        assert job.get("permissions", doc["permissions"]) == {"contents": "read"}, name


def test_every_checkout_fetches_the_full_history():
    """Sitemap `lastmod` comes from git and raises on a shallow clone (ruling T3a)."""
    checkouts = 0
    for path in _workflow_files():
        for step in _steps(_load(path)):
            if step.get("uses", "").startswith("actions/checkout@"):
                checkouts += 1
                assert (step.get("with") or {}).get("fetch-depth") == 0, f"{path.name}: {step}"
    assert checkouts


def _gate() -> list[str]:
    claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    gate = re.search(r"^- Gate: `(.+)`$", claude_md, re.MULTILINE)
    assert gate, "the gate line in CLAUDE.md moved"
    return [part.strip() for part in gate.group(1).split("&&")]


def test_ci_runs_every_gate_command_and_validates_the_citation():
    doc = _load(CI)
    runs = [line.strip() for s in _steps(doc) for line in s.get("run", "").splitlines()]
    for command in [*_gate(), "uvx cffconvert"]:
        assert any(run.startswith(command) for run in runs), f"ci.yml does not run {command}"
    assert any(run.startswith("uvx cffconvert") and "--validate" in run for run in runs)


def test_test_shards_cover_every_test_file_once():
    doc = _load(CI)
    job = doc["jobs"]["test"]
    shards = job["strategy"]["matrix"]["shard"]
    spec = job["env"]["VELOMETER_TEST_SHARD"]
    total = int(spec.rsplit("/", 1)[1])
    assert spec == "${{ matrix.shard }}/" + str(total)
    assert shards == list(range(1, total + 1))
    files = [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "tests").glob("test_*.py"))]
    by_shard = {k: [f for f in files if shard_index(f, total) == k] for k in shards}
    assert sorted(f for group in by_shard.values() for f in group) == files
    assert all(by_shard.values()), "a shard runs no test file"


@pytest.mark.parametrize("spec", ["0/4", "5/4", "1/0", "x/4", "1"])
def test_a_bad_shard_spec_is_refused(spec):
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--co", "-q", "tests/test_m17_workflows.py"],
        cwd=ROOT, env={**os.environ, "VELOMETER_TEST_SHARD": spec},
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert proc.returncode != 0 and "VELOMETER_TEST_SHARD" in proc.stdout + proc.stderr


def _evidence_db_skips() -> set[str]:
    text = EVIDENCE.read_text(encoding="utf-8")
    assert DB_SECTION in text, f"{EVIDENCE.name} has no '{DB_SECTION}' section"
    section = text.split(DB_SECTION, 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^- `(tests/[^`]+)`", section, re.MULTILINE))


def _runtime_skip_problems() -> list[str]:
    """`pytest.skip(...)` calls in test code whose reason is missing or empty, or that skip for
    want of the database: those take the `skipif` mark, so a collection sees and counts them."""
    bad = []
    for path in sorted((ROOT / "tests").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "skip"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "pytest"
            ):
                continue
            reason = node.args[0] if node.args else None
            reason = next((k.value for k in node.keywords if k.arg == "reason"), reason)
            empty = isinstance(reason, ast.Constant) and not str(reason.value).strip()
            if reason is None or empty:
                bad.append(f"{path.name}:{node.lineno}: no reason")
            elif "velometer.sqlite" in ast.unparse(reason):
                bad.append(f"{path.name}:{node.lineno}: a database skip at run time")
    return bad


def test_skips_have_reasons(tmp_path):
    """Collected the way CI's shards would, every skip names its reason, and the tests that skip
    for want of `velometer.sqlite` (a `skipif` whose reason names it, active or not on this
    machine) are exactly the ones the evidence lists."""
    out = tmp_path / "skips.json"
    env = {**os.environ, "VELOMETER_SKIP_AUDIT": str(out)}
    env.pop("VELOMETER_TEST_SHARD", None)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--co", "-q", "-p", "tests.skip_audit"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    audit = json.loads(out.read_text(encoding="utf-8"))
    assert audit["marks"], "the audit saw no skip marks at all"
    for mark in audit["marks"]:
        assert mark["reason"].strip(), f"{mark['nodeid']}: {mark['name']} without a reason"
    for module in audit["modules"]:
        assert module["reason"].strip(), f"{module['nodeid']} skipped without a reason"
    assert _runtime_skip_problems() == []
    db_skips = {m["nodeid"] for m in audit["marks"] if "velometer.sqlite" in m["reason"]}
    db_skips |= {m["nodeid"] for m in audit["modules"] if "velometer.sqlite" in m["reason"]}
    assert db_skips == _evidence_db_skips()
