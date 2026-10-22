"""The operator tool for the Hetzner server (M16 spec §4.2, §4.4, §4.6, §4.7, §4.9).

Every step that reaches outside this machine and changes something (create, setup, deploy,
unlock) prints its plan and goes ahead only after a typed `yes`. Reads (dns, stats, verify,
golive-check) ask nothing. Secrets come from the environment, wired by direnv + pass
(`.envrc.example`): HCLOUD_TOKEN and VELOMETER_PREVIEW_PASSWORD. A missing one stops the step and
names its `pass insert` command. The preview password only ever travels on stdin, to
`caddy hash-password` on the server; it is never on a command line, here or there.

    uv run python tools/server.py preflight
    uv run python tools/server.py create --domain D --ssh-key NAME [--type cx22] [--location nbg1]
    uv run python tools/server.py dns --domain D
    uv run python tools/server.py setup --host IP --domain D [--new-password] [--relock]
    uv run python tools/server.py deploy velometer|datalab|tiles PATH --host IP
    uv run python tools/server.py verify --domain D [--locked]
    uv run python tools/server.py stats --host IP
    uv run python tools/server.py golive-check --datalab DIR
    uv run python tools/server.py unlock --host IP --domain D --datalab DIR

Releases: `deploy` uploads a site with rsync (`--link-dest` to the live release, so only changed
files travel) into a fresh `/srv/<site>/releases/<commit>-<UTC time>/`, writes `.complete` into
it only after rsync exits 0, and then switches `/srv/<site>/current` with `ln -sfn` + `mv -T`
(an atomic rename). An interrupted upload leaves `current` where it was. The three newest
complete releases are kept; older ones are removed one by one, each path checked against
`RELEASE` first. The tile file is no release: it is uploaded to a temporary name in
`/srv/tiles/` and renamed into place.
"""

import hashlib
import importlib.util
import ipaddress
import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import typer
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
CLOUD_INIT = DEPLOY / "cloud-init.yaml"
CADDYFILE = DEPLOY / "Caddyfile"
GOACCESS_CONF = DEPLOY / "goaccess.conf"
STATS_DIR = ROOT / "data" / "stats"


def _load_dryrun():
    """tools/deploy_dryrun.py: the lock texts (LOCK_DEFAULT, lock_text) live there, once."""
    name = "deploy_dryrun"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dr = _load_dryrun()

API = "https://api.hetzner.cloud/v1"
SECRETS = {  # env var -> pass entry
    "HCLOUD_TOKEN": "velometer/hcloud-token",
    "VELOMETER_PREVIEW_PASSWORD": "velometer/preview-password",
}
IMAGE = "debian-13"
LOCATIONS = ("nbg1", "fsn1")  # Germany (spec §4.2)
SERVER_NAME = "velometer"
FIREWALL_NAME = "velometer-web"
ANY = ["0.0.0.0/0", "::/0"]
FIREWALL_RULES = [
    {"direction": "in", "protocol": "tcp", "port": "22", "source_ips": ANY},
    {"direction": "in", "protocol": "tcp", "port": "80", "source_ips": ANY},
    {"direction": "in", "protocol": "tcp", "port": "443", "source_ips": ANY},
    {"direction": "in", "protocol": "udp", "port": "443", "source_ips": ANY},  # HTTP/3
]
PUBLIC_KEY = re.compile(
    r"(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(256|384|521)) [A-Za-z0-9+/=]+( [^\n]*)?"
)

SITE_ROOT = "/srv"
SITES = ("velometer", "datalab")
USER = "deploy"
KEEP = 3
# The only paths a cleanup may remove (ASCII digits only).
RELEASE = re.compile(r"^/srv/[a-z]+/releases/[0-9a-f]{7,40}-\d{8}T\d{6}$", re.ASCII)
MARKER = ".complete"
TILES_DIR = f"{SITE_ROOT}/tiles"
TILES_FILE = "velometer.pmtiles"  # the name the maps fetch (/tiles/velometer.pmtiles)
RSYNC_CHMOD = "--chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r"
# A site release: no `-t`, and files compared by checksum, because an export writes every file
# anew: with modification times kept, `--link-dest` would link nothing (rsync links only files
# equal in every kept attribute). An unchanged file thus keeps the time of its first upload.
RSYNC_SITE = ["-rlpD", "--checksum", RSYNC_CHMOD]
SSH_OPTS = ["-o", "BatchMode=yes"]

LOCK = "/etc/caddy/lock.caddy"
REMOTE_CADDYFILE = "/etc/caddy/Caddyfile"
REMOTE_ENV = "/etc/caddy/caddy.env"
REMOTE_GOACCESS = "/etc/goaccess/velometer.conf"
DOMAIN = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+")
STATS_DAYS = 14

# Confirmations no file can show; printed by every golive-check, never failing it (ruling R31).
MANUAL = [
    "the AVV (data processing agreement, Art. 28 GDPR) with Hetzner is concluded",
    "the Datalab page's velometer link relies on the lock until go-live: check it is meant to "
    "go live now",
    "15 days after the first log line on the server: check that roll_keep_for pruned every "
    "rolled log older than 14 days (ls -l /var/log/caddy)",
]


class ServerError(Exception):
    """A step that cannot go on; the message says why and what to do."""


Runner = Callable[..., subprocess.CompletedProcess]


def _run(argv: list[str], input: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, input=input, capture_output=True, text=True)


def _git_commit() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--short=7", "HEAD"], cwd=ROOT, capture_output=True, text=True
    )
    return r.stdout.strip() if r.returncode == 0 else ""


def _check_site(path: Path) -> list[str]:
    from velometer.app.deploy_check import deploy_problems

    return deploy_problems(path, "/", True)


@dataclass
class Deps:
    """What the tests replace: the process runner, the HTTP transport, the clock, the checks."""

    runner: Runner = _run
    transport: httpx.BaseTransport | None = None
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    check_site: Callable[[Path], list[str]] = _check_site
    git_commit: Callable[[], str] = _git_commit


DEPS = Deps()

app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__.split("\n\n")[0])


# --- small helpers --------------------------------------------------------------------------


def secret(name: str) -> str:
    """The secret from the environment, or a stop naming its `pass insert` command."""
    value = os.environ.get(name, "")
    if not value.strip():
        raise ServerError(
            f"${name} is not set: run `pass insert {SECRETS[name]}`, then `direnv allow`"
        )
    return value


def missing_secrets(env=os.environ) -> list[str]:
    return [n for n in SECRETS if not env.get(n, "").strip()]


def confirm(plan: list[str]) -> None:
    """Print the plan; go on only after a typed `yes`."""
    typer.echo("Plan:")
    for line in plan:
        typer.echo(f"  - {line}")
    answer = typer.prompt("Type yes to go ahead", default="", show_default=False)
    if answer.strip() != "yes":
        raise ServerError("not confirmed; nothing was done")


def check_domain(domain: str) -> str:
    if not DOMAIN.fullmatch(domain):
        raise ServerError(f"not a bare domain (no scheme, path or capitals): {domain!r}")
    return domain


def caddy_env(domain: str) -> str:
    """/etc/caddy/caddy.env: what deploy/Caddyfile reads (deploy/caddy.env.example)."""
    check_domain(domain)
    return (
        "# Written by tools/server.py setup; see deploy/caddy.env.example. No secret here.\n"
        f"DOMAIN={domain}\nSITE_ROOT={SITE_ROOT}\n"
    )


def user_data(public_key: str) -> str:
    """deploy/cloud-init.yaml with `public_key` added to the deploy user."""
    if not PUBLIC_KEY.fullmatch(public_key.strip()):
        raise ServerError("the SSH key from Hetzner is not one public key")
    data = yaml.safe_load(CLOUD_INIT.read_text(encoding="utf-8"))
    users = [u for u in data["users"] if isinstance(u, dict) and u.get("name") == USER]
    if len(users) != 1:
        raise ServerError(f"deploy/cloud-init.yaml: no single user {USER!r}")
    users[0]["ssh_authorized_keys"] = [public_key.strip()]
    return "#cloud-config\n" + yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Target:
    host: str
    user: str = USER

    @property
    def login(self) -> str:
        return f"{self.user}@{self.host}"

    def ssh(self, command: str, input: str | None = None, check: bool = True):
        r = DEPS.runner(["ssh", *SSH_OPTS, self.login, command], input=input)
        if check and r.returncode != 0:
            raise ServerError(f"on {self.host}: `{command}` exited {r.returncode}: {r.stderr}")
        return r

    def put(self, path: str, text: str, mode: str = "0644", group: str = "root") -> None:
        """Write `text` (sent on stdin) to `path` as root, atomically (temp file, then rename)."""
        q = shlex.quote(path)
        script = (
            f't=$(mktemp {q}.XXXXXX) && cat >"$t" && chmod {mode} "$t" && '
            f'chown root:{group} "$t" && mv -f "$t" {q}'
        )
        self.ssh(f"sudo sh -c {shlex.quote(script)}", input=text)


def _host_option() -> str:
    return typer.Option(..., "--host", envvar="VELOMETER_SERVER", help="The server's address.")


def _fail(e: Exception) -> None:
    typer.echo(f"error: {e}", err=True)
    raise typer.Exit(1)


# --- Hetzner API ----------------------------------------------------------------------------


def hetzner() -> httpx.Client:
    token = secret("HCLOUD_TOKEN")
    return httpx.Client(
        base_url=API,
        headers={"Authorization": f"Bearer {token}"},
        transport=DEPS.transport,
        timeout=30,
    )


def api(client: httpx.Client, method: str, path: str, **kw) -> dict:
    r = client.request(method, path, **kw)
    if r.status_code >= 400:
        try:
            err = r.json().get("error", {})
        except ValueError:
            err = {}
        raise ServerError(f"Hetzner API {method} {path}: {r.status_code} {err.get('message', '')}")
    return r.json()


def find_server(client: httpx.Client, name: str) -> dict | None:
    found = api(client, "GET", "/servers", params={"name": name})["servers"]
    return found[0] if found else None


def server_addresses(server: dict) -> tuple[str, str]:
    net = server["public_net"]
    v4 = net["ipv4"]["ip"]
    v6 = str(ipaddress.IPv6Network(net["ipv6"]["ip"], strict=False).network_address + 1)
    return v4, v6


# --- preflight ------------------------------------------------------------------------------


@app.command()
def preflight() -> None:
    """Check that both secrets are in the environment (never prints a value)."""
    missing = missing_secrets()
    for name in SECRETS:
        state = "missing" if name in missing else "set"
        typer.echo(f"{name}: {state}")
    for name in missing:
        typer.echo(f"  run: pass insert {SECRETS[name]}   (then: direnv allow)")
    if missing:
        raise typer.Exit(1)


# --- create ---------------------------------------------------------------------------------


@app.command()
def create(
    domain: str = typer.Option(..., "--domain", help="The apex the server will serve."),
    ssh_key: str = typer.Option(..., "--ssh-key", help="The SSH key's name at Hetzner."),
    server_type: str = typer.Option("cx22", "--type", help="Hetzner server type."),
    location: str = typer.Option("nbg1", "--location", help="nbg1 or fsn1 (Germany)."),
    name: str = typer.Option(SERVER_NAME, "--name"),
) -> None:
    """Create the server through the Hetzner API (costs money: asks for a typed yes)."""
    try:
        check_domain(domain)
        if location not in LOCATIONS:
            raise ServerError(f"location {location!r} is not in Germany; use one of {LOCATIONS}")
        with hetzner() as client:
            keys = api(client, "GET", "/ssh_keys", params={"name": ssh_key})["ssh_keys"]
            if len(keys) != 1:
                raise ServerError(f"no SSH key named {ssh_key!r} at Hetzner; upload it first")
            key = keys[0]
            types = api(client, "GET", "/server_types", params={"name": server_type})
            if len(types["server_types"]) != 1:
                raise ServerError(f"no server type {server_type!r}")
            stype = types["server_types"][0]
            if stype.get("deprecation") or stype.get("deprecated"):
                raise ServerError(f"server type {server_type!r} is deprecated; choose another")
            prices = [p for p in stype.get("prices", []) if p.get("location") == location]
            if not prices:
                raise ServerError(f"server type {server_type!r} is not offered at {location}")
            if find_server(client, name):
                raise ServerError(f"a server named {name!r} exists already; nothing created")
            fws = api(client, "GET", "/firewalls", params={"name": FIREWALL_NAME})["firewalls"]
            data = user_data(key["public_key"])
            price = prices[0].get("price_monthly", {}).get("gross", "?")
            confirm(
                [
                    f"create server {name!r}: {server_type} ({stype.get('architecture', '?')}) "
                    f"at {location}, {IMAGE}, IPv4 and IPv6, about EUR {price} a month",
                    f"SSH key {ssh_key!r} (id {key['id']}) for root and the user {USER!r}",
                    (
                        f"reuse firewall {FIREWALL_NAME!r} (id {fws[0]['id']})"
                        if fws
                        else f"create firewall {FIREWALL_NAME!r}: in 22, 80, 443/tcp, 443/udp"
                    ),
                    "user data: deploy/cloud-init.yaml (comes up locked: 401 everywhere)",
                    f"for the domain {domain} (DNS is yours to set at INWX, see `dns`)",
                ]
            )
            if fws:
                fw_id = fws[0]["id"]
            else:
                body = {"name": FIREWALL_NAME, "rules": FIREWALL_RULES}
                fw_id = api(client, "POST", "/firewalls", json=body)["firewall"]["id"]
            body = {
                "name": name,
                "server_type": server_type,
                "location": location,
                "image": IMAGE,
                "ssh_keys": [key["id"]],
                "firewalls": [{"firewall": fw_id}],
                "public_net": {"enable_ipv4": True, "enable_ipv6": True},
                "user_data": data,
                "labels": {"project": "velometer"},
            }
            server = api(client, "POST", "/servers", json=body)["server"]
    except ServerError as e:
        _fail(e)
    v4, v6 = server_addresses(server)
    typer.echo(f"created {name!r} (id {server['id']}): {v4}, {v6}")
    typer.echo(f"next: `dns --domain {domain}`, then `setup --host {v4} --domain {domain}`")


# --- dns ------------------------------------------------------------------------------------


@app.command()
def dns(
    domain: str = typer.Option(..., "--domain"),
    name: str = typer.Option(SERVER_NAME, "--name"),
) -> None:
    """Print the A and AAAA records to enter at INWX (writes nothing)."""
    try:
        check_domain(domain)
        with hetzner() as client:
            server = find_server(client, name)
        if not server:
            raise ServerError(f"no server named {name!r}")
    except ServerError as e:
        _fail(e)
    v4, v6 = server_addresses(server)
    for host in (domain, f"www.{domain}", f"velometer.{domain}"):
        typer.echo(f"{host:<40} A     {v4}")
        typer.echo(f"{host:<40} AAAA  {v6}")


# --- setup ----------------------------------------------------------------------------------


def lock_state(text: str) -> str:
    if text == dr.LOCK_DEFAULT:
        return "default"
    if not text.strip():
        return "open"
    m = re.fullmatch(re.escape(dr.NO_STORE) + r"basic_auth \{\n\t\S+ (\S+)\n\}\n", text)
    if m and dr.BCRYPT.fullmatch(m.group(1)):
        return "password"
    return "unknown"


@app.command()
def setup(
    host: str = _host_option(),
    domain: str = typer.Option(..., "--domain"),
    new_password: bool = typer.Option(False, "--new-password", help="Re-hash the password."),
    relock: bool = typer.Option(False, "--relock", help="Lock an unlocked server again."),
    user: str = typer.Option(USER, "--user"),
) -> None:
    """Bring the server's Caddy and GoAccess files up to date (idempotent; asks for yes)."""
    t = Target(host, user)
    try:
        wanted = {
            REMOTE_CADDYFILE: CADDYFILE.read_text(encoding="utf-8"),
            REMOTE_ENV: caddy_env(domain),
            REMOTE_GOACCESS: GOACCESS_CONF.read_text(encoding="utf-8"),
        }
        state = lock_state(t.ssh(f"sudo cat {LOCK}").stdout)
        if state == "unknown":
            raise ServerError(f"{LOCK} holds something setup does not know; look at it by hand")
        write_lock = (
            state == "default"
            or (state == "password" and new_password)
            or (state == "open" and relock)
        )
        sums = t.ssh(f"sudo sha256sum {' '.join(wanted)}", check=False).stdout
        have = {}
        for line in sums.splitlines():
            parts = line.split()
            if len(parts) == 2:
                have[parts[1]] = parts[0]
        changed = [p for p, text in wanted.items() if have.get(p) != sha256(text)]
        plan = [f"upload {p}" for p in changed]
        if write_lock:
            plan.append(
                f"lock both sites: {LOCK} gets a basic_auth block (hash made on the server)"
            )
        elif state == "open":
            typer.echo(f"{LOCK} is empty: the sites are live; setup leaves them so (--relock)")
        if not plan:
            typer.echo("nothing to change")
            return
        password = secret("VELOMETER_PREVIEW_PASSWORD") if write_lock else None
        plan.append("reload Caddy")
        confirm(plan)
        for p in (REMOTE_ENV, REMOTE_GOACCESS):
            if p in changed:
                t.put(p, wanted[p])
        if write_lock:
            r = t.ssh("/usr/bin/caddy hash-password", input=password + "\n")
            lines = r.stdout.strip().splitlines()
            t.put(LOCK, dr.lock_text(lines[-1] if lines else ""), mode="0640", group="caddy")
        if REMOTE_CADDYFILE in changed:
            new = REMOTE_CADDYFILE + ".new"
            t.put(new, wanted[REMOTE_CADDYFILE])
            t.ssh(
                f"sudo -u caddy /usr/bin/caddy validate --config {new} --adapter caddyfile "
                f"--envfile {REMOTE_ENV}"
            )
            t.ssh(f"sudo mv -f {new} {REMOTE_CADDYFILE}")
        t.ssh("sudo systemctl enable caddy && sudo systemctl reload-or-restart caddy")
    except (ServerError, dr.DryRunError) as e:
        _fail(e)
    typer.echo("setup done")


# --- deploy ---------------------------------------------------------------------------------


def guard_release(path: str) -> str:
    """`path` if it is a release directory; anything else stops the cleanup."""
    if not RELEASE.fullmatch(path):
        raise ServerError(f"refusing to remove {path!r}: not a release path")
    return path


def _stamp(name: str) -> str:
    return name.rsplit("-", 1)[1]


def plan_cleanup(site: str, listing: list[tuple[str, bool]], current: str | None) -> list[str]:
    """The release paths to remove: all but the `KEEP` newest complete ones (by deploy time)
    and `current`. Names the guard does not admit are never touched."""
    base = f"{SITE_ROOT}/{site}/releases"
    ok = [(n, c) for n, c in listing if RELEASE.fullmatch(f"{base}/{n}")]
    complete = sorted((n for n, c in ok if c), key=_stamp, reverse=True)
    keep = set(complete[:KEEP]) | {current}
    return sorted(guard_release(f"{base}/{n}") for n, _ in ok if n not in keep)


def build_name(site: str, src: Path, now: datetime) -> str:
    commit = ""
    build = src / "build.json"
    if site == "velometer":
        commit = json.loads(build.read_text(encoding="utf-8")).get("commit", "")
    else:
        commit = DEPS.git_commit()
    if not re.fullmatch(r"[0-9a-f]{7,40}", commit or ""):
        raise ServerError(f"no commit to name the release after (got {commit!r})")
    return f"{commit}-{now.strftime('%Y%m%dT%H%M%S')}"


def _current(t: Target, site: str) -> str | None:
    r = t.ssh(f"readlink {SITE_ROOT}/{site}/current", check=False)
    link = r.stdout.strip()
    if r.returncode != 0 or not link.startswith("releases/"):
        return None
    return link.removeprefix("releases/")


def _rsync_failed(rc: int) -> str:
    return f"killed by signal {-rc}" if rc < 0 else f"exited {rc}"


def deploy_site(t: Target, site: str, src: Path) -> None:
    if not src.is_dir() or not (src / "index.html").is_file():
        raise ServerError(f"{src} is no built site (no index.html)")
    if site == "velometer":
        problems = DEPS.check_site(src)
        if problems:
            raise ServerError("deploy-check: " + "; ".join(problems))
    build = build_name(site, src, DEPS.now())
    root = f"{SITE_ROOT}/{site}"
    release = guard_release(f"{root}/releases/{build}")
    prev = _current(t, site)
    confirm(
        [
            f"upload {src}/ to {t.login}:{release}/"
            + (f" (unchanged files hard-linked from {prev})" if prev else ""),
            f"write {MARKER} last, then switch {root}/current to releases/{build}",
            f"keep the {KEEP} newest complete releases, remove older ones",
        ]
    )
    t.ssh(f"mkdir -p {release}")
    argv = ["rsync", *RSYNC_SITE, "-e", " ".join(["ssh", *SSH_OPTS])]
    if prev:
        argv.append(f"--link-dest={root}/releases/{prev}")
    argv += [f"{src}/", f"{t.login}:{release}/"]
    r = DEPS.runner(argv)
    still = f"current still points to releases/{prev}" if prev else "current is unchanged"
    if r.returncode != 0:
        raise ServerError(f"rsync {_rsync_failed(r.returncode)}; {still}")
    try:
        t.ssh(f"touch {release}/{MARKER}")
    except ServerError as e:
        raise ServerError(f"{e}; {still}") from None
    t.ssh(
        f"test -f {release}/{MARKER} && ln -sfn releases/{build} {root}/current.new && "
        f"mv -T {root}/current.new {root}/current"
    )
    typer.echo(f"{site}: current -> releases/{build}")
    listing = t.ssh(
        f'cd {root}/releases && for d in *; do if [ -f "$d/{MARKER}" ]; then '
        'echo "complete $d"; else echo "partial $d"; fi; done',
        check=False,
    ).stdout
    entries = []
    for line in listing.splitlines():
        kind, _, name = line.partition(" ")
        entries.append((name, kind == "complete"))
    for path in plan_cleanup(site, entries, current=build):
        t.ssh(f"rm -r --one-file-system -- {guard_release(path)}")
        typer.echo(f"removed {path}")


def deploy_tiles(t: Target, src: Path) -> None:
    if not src.is_file():
        raise ServerError(f"{src} is no file")
    final = f"{TILES_DIR}/{TILES_FILE}"
    tmp = final + ".new"
    confirm([f"upload {src} to {t.login}:{tmp}", f"then rename it to {final}"])
    r = DEPS.runner(["rsync", "-a", RSYNC_CHMOD, "-e", " ".join(["ssh", *SSH_OPTS]), str(src),
                     f"{t.login}:{tmp}"])  # fmt: skip
    if r.returncode != 0:
        raise ServerError(f"rsync {_rsync_failed(r.returncode)}; {final} is unchanged")
    t.ssh(f"mv -f {tmp} {final}")
    typer.echo(f"tiles: {final} replaced")


@app.command()
def deploy(
    what: str = typer.Argument(..., help="velometer, datalab or tiles"),
    path: Path = typer.Argument(..., help="The built site, or the .pmtiles file."),  # noqa: B008
    host: str = _host_option(),
    user: str = typer.Option(USER, "--user"),
) -> None:
    """Upload a build as a new release and switch to it (asks for yes)."""
    t = Target(host, user)
    try:
        if what in SITES:
            deploy_site(t, what, path)
        elif what == "tiles":
            deploy_tiles(t, path)
        else:
            raise ServerError(f"deploy what? {what!r} is not velometer, datalab or tiles")
    except ServerError as e:
        _fail(e)


# --- stats ----------------------------------------------------------------------------------

STATS_SCRIPT = f"""set -euo pipefail
shopt -s nullglob
db=/var/lib/goaccess/dbip-country-lite.mmdb
[ -s "$db" ] || /usr/local/sbin/velometer-dbip >&2
logs=(/var/log/caddy/*.log /var/log/caddy/*.log.gz)
[ "${{#logs[@]}}" -gt 0 ] || {{ echo "no access logs in /var/log/caddy" >&2; exit 1; }}
out=$(mktemp --suffix=.html)
trap 'rm -f "$out"' EXIT
zcat -f -- "${{logs[@]}}" </dev/null | python3 -c '
import json, sys, time
cut = time.time() - {STATS_DAYS} * 86400
for line in sys.stdin:
    try:
        if float(json.loads(line)["ts"]) >= cut:
            sys.stdout.write(line)
    except (ValueError, KeyError, TypeError):
        pass
' | goaccess - -p {REMOTE_GOACCESS} --no-progress -o "$out" >&2
cat "$out"
"""


def stats_path(now: datetime, base: Path | None = None) -> Path:
    base = base or STATS_DIR
    stem = now.strftime("%Y-%m-%d")
    path, n = base / f"{stem}.html", 1
    while path.exists():
        n += 1
        path = base / f"{stem}-{n}.html"
    return path


@app.command()
def stats(host: str = _host_option(), user: str = typer.Option(USER, "--user")) -> None:
    """GoAccess over the last 14 days of both sites' logs, built on the server (as root: the logs
    are 0600) and saved to data/stats/<date>.html."""
    t = Target(host, user)
    try:
        r = t.ssh("sudo bash -s", input=STATS_SCRIPT, check=False)
        if r.returncode != 0 or not re.match(r"\s*<!DOCTYPE html|\s*<html", r.stdout, re.I):
            raise ServerError(f"no report (exit {r.returncode}): {r.stderr.strip()[-500:]}")
    except ServerError as e:
        _fail(e)
    out = stats_path(DEPS.now())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(r.stdout, encoding="utf-8")
    typer.echo(f"report: {out}")


# --- go-live --------------------------------------------------------------------------------


def _legal_open(text: str) -> list[str]:
    items, heading = [], "(no section)"
    for line in text.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        elif (
            line.startswith("**Verdict:**")
            and "decision for the user" in line
            and "(decided " not in line
        ):
            items.append(f"m16-legal.md §{heading}: decision for the user is open")
    return items


def _press_open(text: str) -> list[str]:
    items, header = [], None
    for line in text.splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if set("".join(cells)) <= set("-: ") or header[-1] != "Status" or header[0] != "#":
            continue
        if cells[-1] != "reviewed":
            items.append(f"press row {cells[0]} ({cells[1]}, {cells[2]}): status {cells[-1]}")
    return items


def golive_items(root: Path, datalab: Path) -> list[str]:
    """Every automatable reason not to go live (spec §4.7, ruling R31); [] when none is open."""
    from velometer.datalab import load_config, placeholders

    items = []
    cfg = load_config(root / "sites" / "datalab" / "site.yaml")
    if cfg.operator_form is None:
        items.append("sites/datalab/site.yaml: operator_form is null (operator undecided)")
    if not cfg.contact_email:
        items.append("sites/datalab/site.yaml: contact_email is null (no contact mailbox)")
    if not (datalab / "index.html").is_file():
        items.append(f"{datalab}: no built Datalab site (velometer datalab build)")
    items += [f"placeholder left in the Datalab build: {p}" for p in placeholders(datalab)]
    review = root / "docs" / "review"
    items += _legal_open((review / "m16-legal.md").read_text(encoding="utf-8"))
    items += _press_open((review / "m16-press.md").read_text(encoding="utf-8"))
    return items


def _golive(root: Path, datalab: Path) -> list[str]:
    items = golive_items(root, datalab)
    for item in items:
        typer.echo(f"open: {item}")
    typer.echo("Manual confirmations (not checked here):")
    for m in MANUAL:
        typer.echo(f"  - {m}")
    typer.echo(f"golive-check: {len(items)} open item(s)")
    return items


@app.command("golive-check")
def golive_check(
    datalab: Path = typer.Option(..., "--datalab", help="The Datalab build to go live."),  # noqa: B008
    root: Path = typer.Option(ROOT, "--root", hidden=True),  # noqa: B008
) -> None:
    """Exit 1 listing every open go-live item; always print the manual confirmations."""
    if _golive(root, datalab):
        raise typer.Exit(1)


def verify_live(domain: str, transport=None, locked: bool = False) -> list[str]:
    """Probe the live server: port 80 answers 308 to https on every host (ruling R30); over
    https the sites answer 200 (or 401 with no-store while `locked`), www 308 to the apex, and
    the tile file 206 to a byte range."""
    problems = []
    hosts = [domain, f"www.{domain}", f"velometer.{domain}"]
    with httpx.Client(transport=transport, follow_redirects=False, timeout=20) as c:

        def get(url, **kw):
            try:
                return c.get(url, **kw)
            except httpx.HTTPError as e:
                problems.append(f"{url}: {e}")
                return None

        for h in hosts:
            r = get(f"http://{h}/probe?q=1")
            if r is not None and (
                r.status_code != 308 or r.headers.get("location") != f"https://{h}/probe?q=1"
            ):
                problems.append(f"http://{h}/: want 308 to https, got {r.status_code}")
        for h in (domain, f"velometer.{domain}"):
            r = get(f"https://{h}/")
            if r is None:
                continue
            if locked:
                if r.status_code != 401 or r.headers.get("cache-control") != "no-store":
                    problems.append(f"https://{h}/: want 401 no-store, got {r.status_code}")
            elif r.status_code != 200:
                problems.append(f"https://{h}/: want 200, got {r.status_code}")
        r = get(f"https://www.{domain}/")
        if (
            r is not None
            and not locked
            and (r.status_code != 308 or r.headers.get("location") != f"https://{domain}/")
        ):
            problems.append(f"https://www.{domain}/: want 308 to the apex, got {r.status_code}")
        if not locked:
            r = get(
                f"https://velometer.{domain}/tiles/{TILES_FILE}", headers={"Range": "bytes=0-6"}
            )
            if r is not None and r.status_code != 206:
                problems.append(f"tiles: want 206 to a byte range, got {r.status_code}")
    return problems


@app.command()
def verify(
    domain: str = typer.Option(..., "--domain"),
    locked: bool = typer.Option(False, "--locked", help="Expect the lock (401 no-store)."),
) -> None:
    """Probe the live sites over HTTP and HTTPS (reads only)."""
    problems = verify_live(check_domain(domain), DEPS.transport, locked)
    for p in problems:
        typer.echo(f"problem: {p}")
    typer.echo(f"verify: {len(problems)} problem(s)")
    if problems:
        raise typer.Exit(1)


@app.command()
def unlock(
    host: str = _host_option(),
    domain: str = typer.Option(..., "--domain"),
    datalab: Path = typer.Option(..., "--datalab", help="The Datalab build that is live."),  # noqa: B008
    root: Path = typer.Option(ROOT, "--root", hidden=True),  # noqa: B008
    user: str = typer.Option(USER, "--user"),
) -> None:
    """Go live: empty the lock file (only when golive-check passes; asks for yes)."""
    t = Target(host, user)
    try:
        check_domain(domain)
        if _golive(root, datalab):
            raise ServerError("golive-check has open items; the sites stay locked")
        confirm([f"empty {LOCK} on {host}: both sites go public", "reload Caddy", "probe them"])
        t.put(LOCK, "", mode="0640", group="caddy")
        t.ssh("sudo systemctl reload-or-restart caddy")
    except ServerError as e:
        _fail(e)
    problems = verify_live(domain, DEPS.transport)
    for p in problems:
        typer.echo(f"problem: {p}")
    if problems:
        raise typer.Exit(1)
    typer.echo(f"live: https://{domain}/ and https://velometer.{domain}/")


if __name__ == "__main__":
    app()
