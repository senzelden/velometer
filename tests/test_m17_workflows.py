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


def test_cli_help_tests_pass_under_the_ci_environment():
    """CI sets GITHUB_ACTIONS, which makes Typer colour its help text. The tests that read help
    text must pass there too, so the suite gives one answer on every machine."""
    env = {**os.environ, "GITHUB_ACTIONS": "true", "FORCE_COLOR": "1"}
    env.pop("_TYPER_FORCE_DISABLE_TERMINAL", None)
    env.pop("VELOMETER_TEST_SHARD", None)
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "tests/test_cli.py::test_content_help_keeps_its_options_and_stamp_has_help",
         "tests/test_content_check.py::test_cli_online_alone_implies_check",
         "tests/test_m16_server.py::test_unlock_needs_the_velometer_export"],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )  # fmt: skip
    assert r.returncode == 0, r.stdout[-2000:]


# --- deploy.yml (M17 Task 10, spec section 4.5) ---------------------------------------------

DEPLOY = WORKFLOWS / "deploy.yml"
MAIN_ONLY = "github.ref == 'refs/heads/main'"
SERVER_CMD = re.compile(r"tools/server\.py\s+(\S+)(?:\s+(\S+))?")
HEX128 = re.compile(r"\b[0-9a-f]{128}\b")
# the rsync reads deploy/ci-gate.py is tested to admit (task 9, ruling T9-g)
GATE_READ_OPTIONS = {"-t", "-a", "-av", "--checksum", "--partial"}


def _deploy_job() -> dict:
    return _load(DEPLOY)["jobs"]["deploy"]


def _run_texts(job: dict) -> list[str]:
    return [step.get("run", "") for step in job["steps"]]


def _indices(job: dict, pattern: str) -> list[int]:
    return [i for i, run in enumerate(_run_texts(job)) if re.search(pattern, run)]


def _commands(run: str) -> list[str]:
    """The shell commands of a `run:` text, one per line, continuation lines joined."""
    return [c.strip() for c in run.replace("\\\n", " ").splitlines() if c.strip()]


def test_deploy_steps_order():
    """Every check runs on the export before anything reaches the server: the R64 passes on the
    local dry run, their 0-findings check and the export tag come before the first deploy, and
    `verify` and the live pass after it, all in the job that waits for the `production`
    approval, after the gate."""
    doc = _load(DEPLOY)
    job = doc["jobs"]["deploy"]
    assert job["environment"] == "production"
    assert job["needs"] in ("gate", ["gate"])
    assert "environment" not in doc["jobs"]["gate"]  # the gate needs no approval and no secret
    deploys = _indices(job, r"tools/server\.py deploy ")
    assert deploys, "deploy.yml deploys nothing"
    first_deploy, last_deploy = min(deploys), max(deploys)
    dry_passes = [
        i
        for i in _indices(job, r"tools/render_pass\.py")
        if "localhost:$PORT" in _run_texts(job)[i]
    ]
    for wanted in (r"--pages all\b.*--keyboard", r"--pages types\b.*--interact.*--flip",
                   r"--lang de\b"):  # fmt: skip
        assert any(
            re.search(wanted, c) for i in dry_passes for c in _commands(_run_texts(job)[i])
        ), f"no dry-run pass {wanted}"
    order = [
        max(_indices(job, r"sha256sum -c")),  # the snapshot and the tiles
        min(_indices(job, r"gunzip")),
        min(_indices(job, r"velometer app export ")),
        min(_indices(job, r"velometer app deploy-check .*--public")),
        min(_indices(job, r"velometer datalab build .*--checked")),
        min(_indices(job, r"sha512sum -c")),  # Caddy
        min(_indices(job, r"tools/deploy_dryrun\.py .*--keep-running")),
        min(dry_passes),
        max(dry_passes),
        min(_indices(job, r"tools/pass_findings\.py")),
        min(_indices(job, r"git .*push .*refs/tags/")),
        first_deploy,
    ]
    assert order == sorted(order), order
    assert order[-5] < order[-4] < order[-3] < order[-2] < order[-1], order  # strictly, at the end
    assert max(_indices(job, r"tools/deploy_dryrun\.py")) < first_deploy
    verify = _indices(job, r"tools/server\.py verify --domain zaehlwerk-datalab\.de")
    assert verify and min(verify) > last_deploy
    live = [i for i in _indices(job, r"tools/render_pass\.py") if i not in dry_passes]
    assert live and min(live) > min(verify)
    assert all("https://" in _run_texts(job)[i] for i in live)
    held = [c for i in live for c in _commands(_run_texts(job)[i]) if "pass_findings" in c]
    assert {"live-velometer", "live-datalab"} <= {
        m for c in held for m in re.findall(r"live-[a-z]+", c)
    }  # the live passes are held to 0 findings too
    summary = [i for i, s in enumerate(job["steps"]) if "GITHUB_STEP_SUMMARY" in s.get("run", "")]
    assert summary and job["steps"][max(summary)].get("if") == "always()"
    assert "$GITHUB_RUN_ID" in _run_texts(job)[max(summary)]  # the run URL, R64's evidence


def test_deploy_fails_closed_on_sha():
    """A snapshot or tile file whose sha256 does not match stops the run: `sha256sum -c` runs
    under bash -e -o pipefail, and nothing in the workflow swallows a failure."""
    doc = _load(DEPLOY)
    text = DEPLOY.read_text(encoding="utf-8")
    job = doc["jobs"]["deploy"]
    sha = [c for run in _run_texts(job) for c in _commands(run) if "sha256sum -c" in c]
    assert any("velometer.sqlite.gz.sha256" in c for c in sha), sha
    assert any("velometer.pmtiles" in c for c in sha), sha
    for c in sha:
        assert "||" not in c, c
    assert doc["defaults"]["run"]["shell"] == "bash"  # bash --noprofile --norc -eo pipefail
    for name, j in doc["jobs"].items():
        assert not j.get("continue-on-error"), name
        for step in j["steps"]:
            assert not step.get("continue-on-error"), step
            assert step.get("shell", "bash") == "bash", step
    assert not re.search(r"\|\|\s*(true|:)\b|set \+e|set \+o pipefail", text)


def test_deploy_never_runs_setup_or_unlock():
    """CI holds the `ci` key only: it deploys velometer and the Datalab and probes over HTTP.
    `setup`, `unlock`, `snapshot`, `golive-check`, `stats` and `deploy tiles` stay local."""
    text = DEPLOY.read_text(encoding="utf-8")
    used = SERVER_CMD.findall(text)
    assert {cmd for cmd, _ in used} == {"deploy", "verify"}, used
    assert {what for cmd, what in used if cmd == "deploy"} == {"velometer", "datalab"}
    for run in _run_texts(_deploy_job()):
        for c in _commands(run):
            if "tools/server.py deploy" in c:
                # one answer to the one prompt (`yes |` would end on SIGPIPE under pipefail)
                assert c.startswith("printf 'yes\\n' | uv run python tools/server.py deploy "), c
                assert c.split("tools/server.py deploy", 1)[1].split()[2:6] == [
                    "--host", '"$HOST"', "--user", "ci"
                ], c  # fmt: skip
    runs = "\n".join(_run_texts(_deploy_job()))
    assert not re.search(r"\bsudo\b|ssh-keyscan|^\s*ssh\s", runs, re.MULTILINE)


def test_deploy_main_only():
    doc = _load(DEPLOY)
    triggers = _triggers(doc)
    assert set(triggers) == {"workflow_dispatch"}
    site = triggers["workflow_dispatch"]["inputs"]["site"]
    assert site["type"] == "choice" and site["options"] == ["velometer", "datalab", "both"]
    for name, job in doc["jobs"].items():
        assert MAIN_ONLY in job.get("if", ""), name


def test_deploy_gate_job_runs_every_gate_command():
    job = _load(DEPLOY)["jobs"]["gate"]
    runs = [line.strip() for run in _run_texts(job) for line in run.splitlines()]
    for command in _gate():
        assert any(run.startswith(command) for run in runs), f"the gate job does not run {command}"


def test_deploy_permissions_and_concurrency():
    """Read-only by default; the deploy job may write contents for the export tag, nothing
    else. One deploy at a time."""
    doc = _load(DEPLOY)
    assert doc["permissions"] == {"contents": "read"}
    assert doc["jobs"]["deploy"]["permissions"] == {"contents": "write"}
    assert doc["jobs"]["gate"].get("permissions", doc["permissions"]) == {"contents": "read"}
    assert doc["concurrency"] == "production"
    for step in _steps(doc):
        if step.get("uses", "").startswith("actions/checkout@"):
            assert step["with"]["persist-credentials"] is False, step


def test_deploy_key_stays_in_the_agent():
    """The one secret, CI_DEPLOY_KEY, reaches only the step that hands it to ssh-agent on stdin;
    no file holds it."""
    text = DEPLOY.read_text(encoding="utf-8")
    assert re.findall(r"secrets\.[A-Za-z_]+", text) == ["secrets.CI_DEPLOY_KEY"]
    holders = [s for s in _deploy_job()["steps"] if "CI_DEPLOY_KEY" in str(s)]
    assert len(holders) == 1
    step = holders[0]
    assert step["env"] == {"CI_DEPLOY_KEY": "${{ secrets.CI_DEPLOY_KEY }}"}
    uses = [c for c in _commands(step["run"]) if "CI_DEPLOY_KEY" in c]
    to_agent = re.compile(r"printf '%s\\n' \"\$CI_DEPLOY_KEY\" \| ssh-add -")
    assert uses and all(c.startswith("test -n ") or to_agent.fullmatch(c) for c in uses), uses


def test_deploy_pins_the_host_key():
    """ssh trusts only the committed deploy/known_hosts line, never a key it is shown."""
    step = next(s for s in _deploy_job()["steps"] if "CI_DEPLOY_KEY" in str(s))
    run = step["run"]
    assert "deploy/known_hosts" in run
    for line in ("StrictHostKeyChecking yes", "GlobalKnownHostsFile /dev/null",
                 "UpdateHostKeys no", "BatchMode yes", "User ci"):  # fmt: skip
        assert re.search(rf"^\s*{line}$", run, re.MULTILINE), line
    known = re.search(r"^\s*UserKnownHostsFile (\S+)$", run, re.MULTILINE)
    assert known and re.search(rf"deploy/known_hosts {re.escape(known.group(1))}\b", run)
    text = DEPLOY.read_text(encoding="utf-8")
    assert not re.search(r"StrictHostKeyChecking[ =](no|accept-new|off)|ssh-keyscan", text)
    host = _load(DEPLOY)["env"]["HOST"]
    line = (ROOT / "deploy" / "known_hosts").read_text(encoding="utf-8").split()[0]
    assert host == line == "2.31.133.185"


def test_deploy_reads_only_what_the_gate_admits():
    """The rsync reads use options and paths deploy/ci-gate.py admits for `ci` (ruling T9-g)."""
    import shlex

    bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        from tests.helpers import load_script

        gate = load_script("deploy/ci-gate.py")
    finally:
        sys.dont_write_bytecode = bytecode
    read = set()
    for run in _run_texts(_deploy_job()):
        for c in _commands(run):
            if not c.startswith("rsync "):
                continue
            words = shlex.split(c, posix=False)
            remote = [w.strip('"') for w in words if w.strip('"').startswith("ci@$HOST:")]
            assert remote, c
            assert {w for w in words[1:] if w.startswith("-")} <= GATE_READ_OPTIONS, c
            read |= {w.split(":", 1)[1] for w in remote}
    assert read == set(gate.READS)


def test_deploy_checks_caddy_by_setups_sha512():
    """The dry run's Caddy is the release binary `setup` installs (deploy/cloud-init.yaml): its
    version and SHA-512 are read from there, not typed again, the pin must be the official
    checksums file's line, and the dry run mounts that binary."""
    from tests.helpers import load_script

    dr = load_script("tools/deploy_dryrun.py")
    text = DEPLOY.read_text(encoding="utf-8")
    assert not HEX128.search(text)
    step = next(s for s in _deploy_job()["steps"] if "sha512sum -c" in s.get("run", ""))
    lines = _commands(step["run"])
    reads = [c for c in lines if re.match(r"(v|sha512)=\$\(sed .* deploy/cloud-init\.yaml\)$", c)]
    assert len(reads) == 2, lines
    got = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", "\n".join([*reads, 'echo "$v $sha512"'])],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()  # fmt: skip
    cloud_init = (ROOT / "deploy" / "cloud-init.yaml").read_text(encoding="utf-8")
    assert got[0] == re.fullmatch(r"caddy:(\d+\.\d+\.\d+)-alpine", dr.CADDY_IMAGE).group(1)
    assert HEX128.fullmatch(got[1]) and HEX128.findall(cloud_init) == [got[1]]
    assert any("caddy_${v}_checksums.txt" in c for c in lines)
    assert any(c.startswith('grep -qx "$sha512  $tgz"') for c in lines)
    dry = [c for run in _run_texts(_deploy_job()) for c in _commands(run) if "deploy_dryrun" in c]
    assert dry and all('--caddy-bin "$CADDY/caddy"' in c for c in dry), dry


def test_deploy_refuses_an_export_without_its_maps_and_plans(tmp_path):
    """The snapshot carries the database only; an export without data/maps and data/plans has
    no tier maps and no plan pages and still passes deploy-check, so the run stops before it."""
    job = _deploy_job()
    guard = next(s for s in job["steps"] if "data/maps" in s.get("run", ""))
    assert job["steps"].index(guard) < min(_indices(job, r"velometer app export "))

    def run_guard() -> int:
        r = subprocess.run(["bash", "-eo", "pipefail", "-c", guard["run"]], cwd=tmp_path,
                           capture_output=True, text=True)  # fmt: skip
        return r.returncode

    assert run_guard() != 0
    (tmp_path / "data" / "maps").mkdir(parents=True)
    (tmp_path / "data" / "maps" / "berlin_fua.png").write_bytes(b"png")
    assert run_guard() != 0  # still no plans
    (tmp_path / "data" / "plans" / "berlin").mkdir(parents=True)
    (tmp_path / "data" / "plans" / "berlin" / "retrieved.json").write_text("{}")
    assert run_guard() == 0


def _results(path: Path, entries: list[dict]) -> Path:
    path.mkdir(parents=True)
    (path / "results.json").write_text(json.dumps(entries), encoding="utf-8")
    return path


def _visit(**findings) -> dict:
    keys = ("errors", "axe", "overflow", "console", "csp", "hosts")
    return {"url": "/", "theme": "light", "width": 1280} | dict.fromkeys(keys, []) | findings


def test_pass_findings_holds_every_result_file_at_zero(tmp_path, capsys):
    from tests.helpers import load_script

    pf = load_script("tools/pass_findings.py")
    clean = _results(tmp_path / "all", [_visit(hosts=["velometer.localhost"]), _visit()])
    assert pf.main([f"{clean}=velometer.localhost"]) == 0
    assert "| all | 2 | 0 |" in capsys.readouterr().out
    # the pages' own host is only the one named for that pass
    assert pf.main([f"{clean}=localhost"]) == 1
    axe = _results(tmp_path / "types", [_visit(axe=[{"id": "color-contrast"}])])
    assert pf.main([f"{clean}=velometer.localhost", f"{axe}=velometer.localhost"]) == 1
    assert "| types | 1 | 1 |" in capsys.readouterr().out
    empty = _results(tmp_path / "datalab", [])
    assert pf.main([f"{empty}=localhost"]) == 1  # nothing visited is no pass
    assert pf.main([f"{tmp_path / 'missing'}=localhost"]) == 1
    assert pf.main([]) == 1


def test_the_dry_run_can_serve_a_given_caddy_binary(tmp_path, capsys):
    from tests.helpers import load_script

    dr = load_script("tools/deploy_dryrun.py")
    args = (tmp_path / "s", tmp_path / "d", tmp_path / "C", tmp_path / "l", "n")
    plain = dr.caddy_command(*args)
    assert not any(":/usr/bin/caddy" in x for x in plain)
    binary = tmp_path / "caddy"
    cmd = dr.caddy_command(*args, binary=binary)
    mount = f"{binary.resolve()}:/usr/bin/caddy:ro"
    assert mount in cmd and cmd[cmd.index(mount) - 1] == "-v" and cmd[-1] == dr.CADDY_IMAGE
    site = tmp_path / "site"
    site.mkdir()
    (site / "build.json").write_text('{"base": "/"}')
    (site / "_headers").write_text("/*\n")
    binary.write_bytes(b"\x7fELF")
    with pytest.raises(SystemExit):
        dr.main(["--site", str(site), "--server", "wrangler", "--caddy-bin", str(binary)])
    assert "--caddy-bin need --server caddy" in capsys.readouterr().err.replace("\n", " ")
    with pytest.raises(SystemExit):
        dr.main(["--site", str(site), "--server", "caddy", "--datalab", str(site),
                 "--caddy-bin", str(tmp_path / "none")])  # fmt: skip
    assert "--caddy-bin needs an existing file" in capsys.readouterr().err
