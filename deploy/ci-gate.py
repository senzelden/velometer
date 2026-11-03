#!/usr/bin/python3 -I
"""The `ci` user's gate (M17 spec §4.5): installed as /usr/local/sbin/velometer-ci-gate by
`tools/server.py setup --ci-key`, it is both that user's login shell and the forced command of its
one key (`restrict,command="/usr/local/sbin/velometer-ci-gate"` in authorized_keys), so every
SSH session of `ci` lands here, whatever it asked for.

It reads the asked command from SSH_ORIGINAL_COMMAND and runs it only when it is one of the forms
below; its own arguments (sshd's `-c <forced command>`) are ignored. Anything else exits 1 with
"refused", having run nothing. A command runs by absolute path, never through a shell.

- What `tools/server.py deploy velometer|datalab --user ci` issues (`deploy_site`), with paths that
  are releases or markers of a site (tools/server.py RELEASE, MARKER_PATH; a site is velometer or
  datalab): `mkdir -p <release>`, `readlink /srv/<site>/current`, `touch <marker>`, the switch
  `test -f <marker> && ln -sfn releases/<name> /srv/<site>/current.new && mv -T
  /srv/<site>/current.new /srv/<site>/current`, `ls -1A /srv/<site>/releases`, `rm -- <marker>`
  and `rm -r --one-file-system -- <release>`, never the release `current` points to.
- `rsync --server` receiving into a release, linking (`--link-dest`) only from a release.
- `rsync --server --sender` of /srv/snapshot/velometer.sqlite.gz, its `.sha256`, and
  /srv/tiles/velometer.pmtiles: the CD workflow's data snapshot and tiles.

An rsync server command is admitted with only the option letters a plain client sends (no `-s`,
whose paths would come on stdin unseen, no temp or backup directories, no filters) and no long
option but `--sender` and `--link-dest`. No sudo: `ci` has none (ruling R35 is fixed for CI only).
This file runs on the server's Debian python3 and imports nothing from the repository; the tests
(tests/test_m17_ci_gate.py) hold it to tools/server.py's release patterns.
"""

import os
import re
import subprocess
import sys

SITES = ("velometer", "datalab")
MARKER = ".complete"
# exactly tools/server.py's RELEASE and MARKER_PATH (a test keeps them equal)
RELEASE = re.compile(r"^/srv/[a-z]+/releases/[0-9a-f]{7,40}-\d{8}T\d{6}$", re.ASCII)
MARKER_PATH = re.compile(r"^/srv/[a-z]+/releases/[0-9a-f]{7,40}-\d{8}T\d{6}\.complete$", re.ASCII)
READS = (
    "/srv/snapshot/velometer.sqlite.gz",
    "/srv/snapshot/velometer.sqlite.gz.sha256",
    "/srv/tiles/velometer.pmtiles",
)
# one token: no shell syntax, no quoting, no whitespace inside (the command is split on spaces)
TOKEN = re.compile(r"[A-Za-z0-9_./=,:+-]+", re.ASCII)
# an rsync server's option cluster: letters, then `e.` and the protocol's capability letters.
# Letters admitted: what a client sends for -r -l -p -D -c -t -o -g -v -z -a -i -u -W -x -I -H.
RSYNC_FLAGS = re.compile(r"-([rlpDctogvziuWxIH]*)e\.([A-Za-z]*)", re.ASCII)
BIN = "/usr/bin/"


class Refused(Exception):
    pass


def _site(path: str) -> str:
    """The site a release or marker path belongs to; a path of any other directory is refused."""
    site = path.split("/")[2]
    if site not in SITES:
        raise Refused(path)
    return site


def _release(path: str) -> str:
    if not RELEASE.fullmatch(path):
        raise Refused(path)
    _site(path)
    return path


def _marker(path: str) -> str:
    if not MARKER_PATH.fullmatch(path):
        raise Refused(path)
    _site(path)
    return path


def _current(site: str) -> str | None:
    """The release name /srv/<site>/current points to, or None."""
    try:
        return os.readlink(f"/srv/{site}/current").removeprefix("releases/")
    except OSError:
        return None


def _rsync(args: list[str], current) -> list[list[str]]:
    if len(args) < 3 or args[0] != "--server":
        raise Refused("rsync")
    rest = args[1:]
    sender = rest[0] == "--sender"
    if sender:
        rest = rest[1:]
    if not rest or not RSYNC_FLAGS.fullmatch(rest[0]):
        raise Refused("rsync flags")
    rest = rest[1:]
    if not sender:
        if rest[:1] == ["--link-dest"] and len(rest) > 1:
            _release(rest[1])
            rest = rest[2:]
        elif rest and rest[0].startswith("--link-dest="):
            _release(rest[0].removeprefix("--link-dest="))
            rest = rest[1:]
    if len(rest) < 2 or rest[0] != ".":
        raise Refused("rsync paths")
    paths = rest[1:]
    if sender:
        if any(p not in READS for p in paths):
            raise Refused("rsync source")
    elif len(paths) != 1 or not RELEASE.fullmatch(paths[0].removesuffix("/")):
        raise Refused("rsync destination")
    else:
        _release(paths[0].removesuffix("/"))
    return [[BIN + "rsync", *args]]


def plan(command: str, current=_current) -> list[list[str]]:
    """The argv(s) to run for `command`, in order; `Refused` for anything not admitted.
    `current(site)` names the release /srv/<site>/current points to (None when none)."""
    t = command.split(" ")
    if not command or " ".join(t) != command or any(not TOKEN.fullmatch(x) for x in t if x != "&&"):
        raise Refused(command)
    if t[0] == "rsync":
        return _rsync(t[1:], current)
    if "&&" in t:
        if len(t) != 13 or t[3] != "&&" or t[8] != "&&":
            raise Refused(command)
        marker = _marker(t[2])
        site = _site(marker)
        name = marker.rsplit("/", 1)[1].removesuffix(MARKER)
        root = f"/srv/{site}"
        want = ["test", "-f", marker, "&&", "ln", "-sfn", f"releases/{name}", f"{root}/current.new",
                "&&", "mv", "-T", f"{root}/current.new", f"{root}/current"]  # fmt: skip
        if t != want:
            raise Refused(command)
        return [[BIN + "test", *t[1:3]], [BIN + "ln", *t[5:8]], [BIN + "mv", *t[10:13]]]
    if len(t) == 3 and t[:2] == ["mkdir", "-p"]:
        _release(t[2])
    elif len(t) == 2 and t[0] == "readlink" and t[1] in {f"/srv/{s}/current" for s in SITES}:
        pass
    elif len(t) == 2 and t[0] == "touch":
        _marker(t[1])
    elif len(t) == 3 and t[:2] == ["ls", "-1A"] and t[2] in {f"/srv/{s}/releases" for s in SITES}:
        pass
    elif len(t) == 3 and t[:2] == ["rm", "--"]:
        _marker(t[2])
    elif len(t) == 5 and t[:4] == ["rm", "-r", "--one-file-system", "--"]:
        path = _release(t[4])
        if current(_site(path)) == path.rsplit("/", 1)[1]:
            raise Refused(f"{path} is what current points to")
    else:
        raise Refused(command)
    return [[BIN + t[0], *t[1:]]]


def main(argv: list[str]) -> None:
    command = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    try:
        steps = plan(command)
    except Refused:
        print("refused", file=sys.stderr)
        sys.exit(1)
    if len(steps) == 1:
        os.execv(steps[0][0], steps[0])
        return
    for step in steps:
        rc = subprocess.run(step, stdin=subprocess.DEVNULL).returncode
        if rc != 0:
            sys.exit(rc)
    sys.exit(0)


if __name__ == "__main__":
    main(sys.argv[1:])
