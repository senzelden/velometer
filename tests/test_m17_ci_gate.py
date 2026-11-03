"""M17 Task 9: deploy/ci-gate.py, the forced command of the server's `ci` user (spec §4.5).

The gate reads `SSH_ORIGINAL_COMMAND` and runs only what `tools/server.py deploy --user ci` issues
and the two reads the CD workflow needs (the data snapshot and the tiles); anything else is
refused. Nothing here reaches a server: the deploy commands come from the fake runner of
tests/test_m16_server.py, and the rsync server commands from the local rsync with a capturing
`-e` program in place of ssh.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.helpers import ROOT, load_script
from tests.test_m16_server import HOST, NOW, PREV, FakeRunner, deploy_rules, site_dir, srv

# no __pycache__ in deploy/: everything there is a server file (and is scanned for secrets)
_bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
try:
    gate = load_script("deploy/ci-gate.py")
finally:
    sys.dont_write_bytecode = _bytecode

SITE = "/srv/velometer"
BUILD = "1234abc-20261022T093005"
OLD = ["0aa0000-20261001T000000", "0bb0000-20261002T000000", "0cc0000-20261003T000000"]
REL = f"{SITE}/releases/{BUILD}"


def plan(command: str, current: str | None = PREV):
    """The gate's plan for `command`, with `current` as the release each site's link names."""
    return gate.plan(command, current=lambda site: current)


def refused(command: str, current: str | None = PREV) -> bool:
    try:
        plan(command, current)
    except gate.Refused:
        return True
    return False


# --- what deploy issues -----------------------------------------------------------------------


@pytest.fixture
def ci_deploy(monkeypatch, tmp_path):
    """Every ssh command and the rsync argv of one `deploy velometer --user ci` with a previous
    release to link from and older releases (one partial, one orphaned marker) to prune."""
    runner = FakeRunner()
    monkeypatch.setattr(srv.DEPS, "runner", runner)
    monkeypatch.setattr(srv.DEPS, "now", lambda: NOW)
    monkeypatch.setattr(srv.DEPS, "check_site", lambda path: [])
    names = [OLD[0], OLD[0] + ".complete", OLD[1], OLD[2] + ".complete",
             PREV, PREV + ".complete", BUILD, BUILD + ".complete"]  # fmt: skip
    runner.rules = deploy_rules(listing="\n".join(names) + "\n")
    r = CliRunner().invoke(
        srv.app,
        ["deploy", "velometer", str(site_dir(tmp_path)), *HOST, "--user", "ci"],
        input="yes\n",
    )
    assert r.exit_code == 0, r.output
    ssh = [a[-1] for a, _ in runner.calls if a[0] == "ssh"]
    (rsync,) = [a for a, _ in runner.calls if a[0] == "rsync"]
    assert all(a[a.index("ssh") + 3] == "ci@203.0.113.10" for a, _ in runner.calls if a[0] == "ssh")
    return ssh, rsync


def test_the_sample_deploy_issues_every_form(ci_deploy):
    ssh, _ = ci_deploy
    heads = {" ".join(c.split()[:2]) for c in ssh}
    assert {"readlink /srv/velometer/current", "mkdir -p", f"touch {REL}.complete",
            "test -f", "ls -1A", "rm --", "rm -r"} <= heads, ssh  # fmt: skip


def test_gate_allows_deploy_forms(ci_deploy):
    ssh, _ = ci_deploy
    for command in ssh:
        steps = plan(command, current=BUILD)  # the prune runs after the switch
        # it runs exactly the command that was asked for, by absolute path, without a shell
        ran = " && ".join(" ".join([Path(s[0]).name, *s[1:]]) for s in steps)
        assert ran == command
        assert all(s[0].startswith("/usr/bin/") for s in steps)


def _remote_rsync(argv: list[str], tmp_path: Path) -> str:
    """The command the local rsync asks its remote shell to run for client `argv` (as sshd hands
    it to the gate in SSH_ORIGINAL_COMMAND), captured by an `-e` program that runs nothing."""
    if not shutil.which("rsync"):
        pytest.fail("rsync is not installed: the deploy and the CD workflow need it")
    out = tmp_path / "remote.json"
    capture = tmp_path / "capture.py"
    capture.write_text(
        f"import json, sys\nopen({str(out)!r}, 'w').write(json.dumps(sys.argv[1:]))\nsys.exit(1)\n",
        encoding="utf-8",
    )
    i = argv.index("-e")
    argv = [*argv[: i + 1], f"{sys.executable} {capture}", *argv[i + 2 :]]
    subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    args = json.loads(out.read_text(encoding="utf-8"))
    return " ".join(args[args.index("rsync") :])


def test_gate_allows_the_deploys_rsync_upload(ci_deploy, tmp_path):
    _, rsync = ci_deploy
    command = _remote_rsync(rsync, tmp_path)
    assert command.startswith("rsync --server ") and f" . {REL}/" in command
    assert f"--link-dest {SITE}/releases/{PREV}" in command
    # it runs as asked, with symlinks munged should one ever arrive (ruling T9-i)
    rest = command.split()[2:]
    assert plan(command) == [["/usr/bin/rsync", "--server", "--munge-links", *rest]]


def test_the_deploys_upload_asks_for_no_symlinks_and_no_devices(ci_deploy, tmp_path):
    """Caddy follows a symlink (to the TLS keys, the logs, the lock) and blocks on a FIFO: the
    upload carries neither (ruling T9-i)."""
    _, rsync = ci_deploy
    (flags,) = [
        a for a in _remote_rsync(rsync, tmp_path).split() if a.startswith("-") and "e." in a
    ]
    letters = flags[1:].split("e.")[0]
    assert not set(letters) & set("lDHog"), flags
    assert not any(set(a[1:]) & set("lD") for a in srv.RSYNC_SITE if not a.startswith("--"))
    assert not {"-a", "--links", "--devices", "--specials"} & set(srv.RSYNC_SITE)


@pytest.mark.parametrize(
    "flags", ["-rlpe.iLsfxCIvu", "-rDe.iLsfxCIvu", "-lDprce.iLsfxCIvu", "-prcHe.iLsfxCIvu",
              "-logDtpre.iLsfxCIvu"],
)  # fmt: skip
def test_gate_rejects_symlinks_and_devices_on_receive(flags):
    assert refused(f"rsync --server {flags} . {REL}/")
    assert refused(f"rsync --server {flags} --link-dest {SITE}/releases/{PREV} . {REL}/")
    # reading keeps them: `rsync -a` from the snapshot is fine
    assert not refused(f"rsync --server --sender {flags} . {TILES}")


def test_gate_allows_the_deploys_rsync_upload_without_a_previous_release(ci_deploy, tmp_path):
    _, rsync = ci_deploy
    rsync = [a for a in rsync if not a.startswith("--link-dest")]
    assert not refused(_remote_rsync(rsync, tmp_path))


SNAPSHOT = "/srv/snapshot/velometer.sqlite.gz"
TILES = "/srv/tiles/velometer.pmtiles"


@pytest.mark.parametrize("opts", [[], ["-t"], ["-a"], ["-a", "--checksum"], ["-av", "--partial"]])
@pytest.mark.parametrize("paths", [[SNAPSHOT, SNAPSHOT + ".sha256"], [SNAPSHOT], [TILES]])
def test_gate_allows_the_snapshot_and_tile_reads(opts, paths, tmp_path):
    argv = ["rsync", *opts, "-e", "ssh", *(f"ci@203.0.113.10:{p}" for p in paths), str(tmp_path)]
    command = _remote_rsync(argv, tmp_path)
    assert command.startswith("rsync --server --sender ")
    assert plan(command) == [["/usr/bin/rsync", *command.split()[1:]]]
    assert "--munge-links" not in plan(command)[0]


def test_the_gates_release_paths_are_the_deploys():
    """One rule for what a release is: the gate's patterns are tools/server.py's."""
    assert gate.RELEASE.pattern == srv.RELEASE.pattern
    assert gate.MARKER_PATH.pattern == srv.MARKER_PATH.pattern
    assert gate.SITES == srv.SITES
    assert gate.MARKER == srv.MARKER
    snapshot = f"{srv.SNAPSHOT_DIR}/{srv.SNAPSHOT_NAME}"
    assert set(gate.READS) == {snapshot, snapshot + ".sha256", f"{srv.TILES_DIR}/{srv.TILES_FILE}"}


KNOWN_HOSTS = ROOT / "deploy" / "known_hosts"


def test_known_hosts_pins_one_ed25519_host_key():
    """The CD workflow trusts the server by this committed line, never on first use (spec §4.5).
    It is read from the server in Task 9 step 5 (task-9-report.md), never typed."""
    if not KNOWN_HOSTS.exists():
        pytest.skip("deploy/known_hosts is not made yet: Task 9 step 5 reads it from the server")
    import base64

    text = KNOWN_HOSTS.read_text(encoding="utf-8")
    assert "PRIVATE KEY" not in text
    lines = [x for x in text.splitlines() if x.strip() and not x.startswith("#")]
    assert len(lines) == 1, lines
    host, kind, key = lines[0].split()
    assert host == "2.31.133.185" and kind == "ssh-ed25519"
    blob = base64.b64decode(key, validate=True)
    assert blob[:15] == b"\x00\x00\x00\x0bssh-ed25519" and len(blob) == 51


# --- what it refuses --------------------------------------------------------------------------

SHELLS = [
    "", " ", "bash", "sh", "/bin/sh", "sh -c id", "bash -i", "bash -lc id", "python3",
    "python3 -c 'import os'", "env", "id", "true", "exec sh", "scp -t /srv/velometer/releases",
    "sftp", "internal-sftp", "/usr/lib/openssh/sftp-server", "git-receive-pack x",
    "cat /etc/shadow",
    "ln -s /etc /srv/velometer/current", "chmod 777 /srv/velometer/releases",
]  # fmt: skip


@pytest.mark.parametrize("command", SHELLS)
def test_gate_rejects_shell(command):
    assert refused(command)


SUDO = [
    "sudo true", "sudo -n true", "sudo -i", "sudo sh", "sudo -l", "sudo -u root id",
    f"sudo mkdir -p {REL}", f"sudo rm -r --one-file-system -- {SITE}/releases/{OLD[0]}",
    f"sudo rsync --server -prce.iLsfxCIvu . {REL}/", "/usr/bin/sudo true", "su -", "doas true",
    "pkexec true",
]  # fmt: skip


@pytest.mark.parametrize("command", SUDO)
def test_gate_rejects_sudo(command):
    assert refused(command)


OUTSIDE = [
    "mkdir -p /etc/velometer",
    f"mkdir -p {SITE}/releases/../../../etc",
    f"mkdir -p {SITE}/releases/{BUILD}/../../../etc",
    f"mkdir -p {SITE}/releases/{BUILD}/x",
    "mkdir -p /srv/tiles/releases/1234abc-20261022T093005",  # a release name, but not a site
    "mkdir -p /srv/snapshot/releases/1234abc-20261022T093005",
    f"mkdir {REL}",
    f"mkdir -p {REL} /etc/x",
    f"mkdir -m 777 -p {REL}",
    "readlink /etc/shadow",
    "readlink -f /srv/velometer/current",
    "readlink /srv/tiles/current",
    "touch /etc/x.complete",
    f"touch {SITE}/releases/../{BUILD}.complete",
    f"touch {REL}",
    f"touch {REL}.complete {REL}.complete2",
    "ls -1A /etc",
    "ls -1A /srv/velometer/releases/..",
    "ls -la /srv/velometer/releases",
    f"rm -r --one-file-system -- {SITE}/current",
    f"rm -r --one-file-system -- {SITE}/releases",
    f"rm -r --one-file-system -- {SITE}",
    f"rm -r --one-file-system -- {SITE}/releases/../../../etc",
    f"rm -r --one-file-system -- {SITE}/releases/{PREV}",  # the release current points to
    f"rm -r --one-file-system -- {SITE}/releases/{OLD[0]}.complete",
    f"rm -r -- {SITE}/releases/{OLD[0]}",
    f"rm -rf -- {SITE}/releases/{OLD[0]}",
    f"rm -r -f --one-file-system -- {SITE}/releases/{OLD[0]}",
    f"rm -r --one-file-system {SITE}/releases/{OLD[0]}",
    f"rm -r --one-file-system -- {SITE}/releases/{OLD[0]} /etc",
    f"rm -- {SITE}/releases/{OLD[0]}",  # a release is no file
    "rm -- /etc/passwd",
    f"rm -- {SITE}/current",
    f"rm -f -- {SITE}/releases/{OLD[0]}.complete",
    "rm -r --one-file-system -- /srv/tiles/releases/1234abc-20261022T093005",
    # the switch: only to a release with its marker, only in one site, only to `current`
    f"test -f {REL}.complete && ln -sfn /etc {SITE}/current.new && "
    f"mv -T {SITE}/current.new {SITE}/current",
    f"test -f {REL}.complete && ln -sfn releases/{OLD[0]} {SITE}/current.new && "
    f"mv -T {SITE}/current.new {SITE}/current",
    f"test -f {REL}.complete && ln -sfn releases/{BUILD} /srv/datalab/current.new && "
    f"mv -T /srv/datalab/current.new /srv/datalab/current",
    f"test -f {REL}.complete && ln -sfn releases/{BUILD} {SITE}/current.new && "
    f"mv -T {SITE}/current.new /srv/datalab/current",
    f"test -f {REL}.complete && ln -sfn releases/{BUILD} {SITE}/x && mv -T {SITE}/x {SITE}/current",
    f"test -f {REL}.complete && ln -sfn releases/{BUILD} {SITE}/current.new && "
    f"mv -T {SITE}/current.new /etc/passwd",
    f"test -f /etc/passwd && ln -sfn releases/{BUILD} {SITE}/current.new && "
    f"mv -T {SITE}/current.new {SITE}/current",
    f"ln -sfn releases/{BUILD} {SITE}/current.new",
    f"mv -T {SITE}/current.new {SITE}/current",
    # uploads only into a release, linking only from a release
    "rsync --server -prce.iLsfxCIvu . /etc/",
    "rsync --server -prce.iLsfxCIvu . /srv/velometer/current/",
    "rsync --server -prce.iLsfxCIvu . /srv/tiles/",
    "rsync --server -prce.iLsfxCIvu . /srv/snapshot/",
    "rsync --server -prce.iLsfxCIvu . /srv/velometer/releases/",
    f"rsync --server -prce.iLsfxCIvu . {REL}/../../../etc/",
    f"rsync --server -prce.iLsfxCIvu . {REL}.complete",
    f"rsync --server -prce.iLsfxCIvu --link-dest /etc . {REL}/",
    f"rsync --server -prce.iLsfxCIvu --link-dest=/etc . {REL}/",
    f"rsync --server -prce.iLsfxCIvu --link-dest /srv/tiles . {REL}/",
    f"rsync --server -prce.iLsfxCIvu . {REL}/ /etc/",
    f"rsync --server -prce.iLsfxCIvu --temp-dir=/etc . {REL}/",
    f"rsync --server -prce.iLsfxCIvu --backup-dir=/etc . {REL}/",
    f"rsync --server -prce.iLsfxCIvu --delete . {REL}/",
    f"rsync --server -prce.iLsfxCIvu --log-file=/etc/x . {REL}/",
    f"rsync --server -prce.iLsfxCIvu --files-from=/etc/x . {REL}/",
    f"rsync --server -prcTe.iLsfxCIvu /etc . {REL}/",  # -T: a temp dir anywhere
    f"rsync --server -prcbe.iLsfxCIvu . {REL}/",  # -b: backups
    f"rsync --server -prcLe.iLsfxCIvu . {REL}/",
    f"rsync --server -prce.iLsfxCIvu -M--log-file=/etc/x . {REL}/",
    f"rsync --server -se.LsfxCIvu . {REL}/",  # -s: the paths would come on stdin
    f"rsync --server . {REL}/",
    f"rsync --daemon . {REL}/",
    f"rsync -prce.iLsfxCIvu . {REL}/",
]


@pytest.mark.parametrize("command", OUTSIDE)
def test_gate_rejects_path_outside_releases(command):
    assert refused(command)


SENDER_ELSEWHERE = [
    "rsync --server --sender -logDtpre.iLsfxCIvu . /etc/shadow",
    "rsync --server --sender -logDtpre.iLsfxCIvu . /srv/snapshot/",
    "rsync --server --sender -logDtpre.iLsfxCIvu . /srv/snapshot",
    "rsync --server --sender -logDtpre.iLsfxCIvu . /srv/snapshot/velometer.sqlite",
    "rsync --server --sender -logDtpre.iLsfxCIvu . /srv/snapshot/../../etc/shadow",
    "rsync --server --sender -logDtpre.iLsfxCIvu . /srv/snapshot/x/../velometer.sqlite.gz",
    "rsync --server --sender -logDtpre.iLsfxCIvu . /srv/tiles/velometer.pmtiles.new",
    "rsync --server --sender -logDtpre.iLsfxCIvu . /srv/tiles/",
    "rsync --server --sender -logDtpre.iLsfxCIvu . /srv/velometer/current/index.html",
    f"rsync --server --sender -logDtpre.iLsfxCIvu . {REL}",
    "rsync --server --sender -logDtpre.iLsfxCIvu . /home/ci/.ssh/authorized_keys",
    f"rsync --server --sender -logDtpre.iLsfxCIvu . {TILES} /etc/shadow",
    f"rsync --server --sender -logDtpre.iLsfxCIvu {TILES}",
    f"rsync --server --sender -logDtpre.iLsfxCIvu . {TILES[1:]}",
    f"rsync --server --sender -logDtpre.iLsfxCIvu --remove-source-files . {TILES}",
    f"rsync --server --sender -logDtpre.iLsfxCIvu --files-from=/etc/x . {TILES}",
    f"rsync --server --sender -logDtpre.iLsfxCIvu --include=* . {TILES}",
    f"rsync --server --sender -logDtpRre.iLsfxCIvu . {TILES}",
    f"rsync --server --sender -Le.LsfxCIvu . {TILES}",
    "rsync --server --sender -se.LsfxCIvu",
    f"rsync --server --sender -se.LsfxCIvu . {TILES}",
    f"rsync --server --sender . {TILES}",
]


@pytest.mark.parametrize("command", SENDER_ELSEWHERE)
def test_gate_rejects_rsync_sender_elsewhere(command):
    assert refused(command)


ALLOWED = [
    f"mkdir -p {REL}",
    "readlink /srv/velometer/current",
    f"touch {REL}.complete",
    f"test -f {REL}.complete && ln -sfn releases/{BUILD} {SITE}/current.new && "
    f"mv -T {SITE}/current.new {SITE}/current",
    "ls -1A /srv/velometer/releases",
    f"rm -- {SITE}/releases/{OLD[0]}.complete",
    f"rm -r --one-file-system -- {SITE}/releases/{OLD[0]}",
    f"rsync --server -prce.iLsfxCIvu --link-dest {SITE}/releases/{PREV} . {REL}/",
    f"rsync --server --sender -logDtpre.iLsfxCIvu . {SNAPSHOT} {SNAPSHOT}.sha256",
    f"rsync --server --sender -logDtpre.iLsfxCIvu . {TILES}",
]
CHAINS = ["; id", ";id", " ; sh", " | sh", "|sh", " || sh", " && id", " & id", " $(id)", "$(id)",
          " `id`", "`id`", "\nid", "\rid", " > /tmp/x", " < /etc/shadow", " 2>/tmp/x",
          " ${IFS}id", " #", "\x00id", " \\; id", " '", ' "']  # fmt: skip


def test_the_chain_cases_start_from_allowed_commands():
    for command in ALLOWED:
        assert not refused(command), command


@pytest.mark.parametrize("tail", CHAINS)
@pytest.mark.parametrize("command", ALLOWED)
def test_gate_rejects_chained_commands(command, tail):
    assert refused(command + tail)
    assert refused(tail.strip() + " " + command)
    head, _, rest = command.partition(" ")
    assert refused(f"{head}{tail} {rest}")


# --- running it -------------------------------------------------------------------------------


def test_main_refuses_with_exit_1_and_runs_nothing(monkeypatch, capsys):
    ran = []
    monkeypatch.setattr(gate.os, "execv", lambda *a: ran.append(a))
    monkeypatch.setattr(gate.subprocess, "run", lambda *a, **k: ran.append(a))
    for env in ({}, {"SSH_ORIGINAL_COMMAND": "sudo true"}):
        monkeypatch.delenv("SSH_ORIGINAL_COMMAND", raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        with pytest.raises(SystemExit) as e:
            gate.main(["-c", "/usr/local/sbin/velometer-ci-gate"])
        assert e.value.code == 1
        assert "refused" in capsys.readouterr().err
    assert ran == []


def test_main_execs_one_step_and_runs_a_chain_step_by_step(monkeypatch):
    execs, runs = [], []
    monkeypatch.setattr(gate.os, "execv", lambda path, argv: execs.append((path, argv)))
    monkeypatch.setattr(gate, "_current", lambda site: PREV)

    def run(argv, **kw):
        runs.append(argv)
        return subprocess.CompletedProcess(argv, 1 if argv[0] == "/usr/bin/ln" else 0)

    monkeypatch.setattr(gate.subprocess, "run", run)
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", f"mkdir -p {REL}")
    gate.main([])
    assert execs == [("/usr/bin/mkdir", ["/usr/bin/mkdir", "-p", REL])]
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", ALLOWED[3])
    with pytest.raises(SystemExit) as e:
        gate.main([])
    assert e.value.code == 1  # ln failed: mv never runs
    assert [r[0] for r in runs] == ["/usr/bin/test", "/usr/bin/ln"]


def test_the_gate_is_python_any_debian_server_has_and_ignores_its_arguments():
    text = (ROOT / "deploy" / "ci-gate.py").read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/python3 -I\n")  # isolated: no PYTHONPATH, no user site
    assert "SSH_ORIGINAL_COMMAND" in text
    assert "shell=True" not in text and "os.system" not in text
