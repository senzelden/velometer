"""M16 Task 8: deploy/cloud-init.yaml, deploy/goaccess.conf and tools/server.py.

Nothing here reaches Hetzner, DNS or a server: the Hetzner API is an httpx MockTransport, ssh and
rsync a fake runner that records every argv and stdin, and the typed `yes` is injected input.
"""

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import yaml
from typer.testing import CliRunner

from tests.helpers import ROOT, load_script

srv = load_script("tools/server.py")
dr = load_script("tools/deploy_dryrun.py")

CLOUD_INIT = ROOT / "deploy" / "cloud-init.yaml"
GOACCESS = ROOT / "deploy" / "goaccess.conf"
PASSWORD = "pw-" + "x7Qe9-not-a-real-one"
PUBKEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFakeFakeFakeFakeFakeFakeFakeFakeFakeFake user@test"
HASH = "$2a$14$" + "a" * 53
NOW = datetime(2026, 10, 22, 9, 30, 5, tzinfo=UTC)
HOST = ["--host", "203.0.113.10"]


# --- fakes ----------------------------------------------------------------------------------


class FakeRunner:
    """Records (argv, input); answers by the first rule whose needle is in the joined argv."""

    def __init__(self, rules=None):
        self.calls: list[tuple[list[str], str | None]] = []
        self.rules = list(rules or [])

    def __call__(self, argv, input=None):
        self.calls.append((list(argv), input))
        joined = " ".join(argv)
        for needle, answer in self.rules:
            if needle in joined:
                if callable(answer):
                    answer = answer(argv, input)
                rc, out = answer if isinstance(answer, tuple) else (0, answer)
                return subprocess.CompletedProcess(argv, rc, out, "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def joined(self) -> list[str]:
        return [" ".join(a) for a, _ in self.calls]

    def index(self, needle: str) -> int:
        hits = [i for i, j in enumerate(self.joined()) if needle in j]
        assert hits, f"no call with {needle!r}: {self.joined()}"
        return hits[0]


def _no_network(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected HTTP request in a test: {request.method} {request.url}")


@pytest.fixture
def deps(monkeypatch, tmp_path):
    runner = FakeRunner()
    monkeypatch.setattr(srv.DEPS, "runner", runner)
    monkeypatch.setattr(srv.DEPS, "now", lambda: NOW)
    monkeypatch.setattr(srv.DEPS, "check_site", lambda path: [])
    monkeypatch.setattr(srv.DEPS, "git_commit", lambda: "abcdef1")
    monkeypatch.setattr(srv.DEPS, "git_dirty", lambda: False)
    monkeypatch.setattr(srv.DEPS, "transport", httpx.MockTransport(_no_network))
    monkeypatch.setattr(srv, "STATS_DIR", tmp_path / "data" / "stats")
    monkeypatch.setenv("HCLOUD_TOKEN", "test-token")
    monkeypatch.setenv("VELOMETER_PREVIEW_PASSWORD", PASSWORD)
    return runner


def invoke(*args, input=None):
    return CliRunner().invoke(srv.app, list(args), input=input)


def site_dir(tmp_path: Path, name="site") -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / "index.html").write_text("<!doctype html><title>x</title>", encoding="utf-8")
    (d / "_headers").write_text("/*\n", encoding="utf-8")
    (d / "build.json").write_text(json.dumps({"commit": "1234abc", "base": "/"}), encoding="utf-8")
    return d


# --- preflight (spec §4.9 item 9) -----------------------------------------------------------


def test_preflight_names_both_pass_insert_commands_when_both_secrets_are_missing(monkeypatch):
    monkeypatch.delenv("HCLOUD_TOKEN", raising=False)
    monkeypatch.delenv("VELOMETER_PREVIEW_PASSWORD", raising=False)
    r = invoke("preflight")
    assert r.exit_code == 1
    assert "pass insert velometer/hcloud-token" in r.output
    assert "pass insert velometer/preview-password" in r.output


def test_preflight_names_only_the_missing_secret_and_never_prints_a_value(monkeypatch):
    monkeypatch.setenv("HCLOUD_TOKEN", "tok-secret-value")
    monkeypatch.setenv("VELOMETER_PREVIEW_PASSWORD", "  ")  # blank is missing
    r = invoke("preflight")
    assert r.exit_code == 1
    assert "pass insert velometer/preview-password" in r.output
    assert "hcloud-token" not in r.output
    assert "tok-secret-value" not in r.output


def test_preflight_passes_with_both_secrets_set(monkeypatch):
    monkeypatch.setenv("HCLOUD_TOKEN", "tok")
    monkeypatch.setenv("VELOMETER_PREVIEW_PASSWORD", PASSWORD)
    r = invoke("preflight")
    assert r.exit_code == 0, r.output
    assert PASSWORD not in r.output


def test_create_without_a_token_stops_and_names_the_pass_entry(deps, monkeypatch):
    monkeypatch.delenv("HCLOUD_TOKEN")
    r = invoke("create", "--domain", "example.org", "--ssh-key", "k", input="yes\n")
    assert r.exit_code == 1
    assert "pass insert velometer/hcloud-token" in r.output


def test_envrc_example_wires_both_secrets_through_pass():
    text = (ROOT / ".envrc.example").read_text(encoding="utf-8")
    assert re.search(r"^use_pass HCLOUD_TOKEN velometer/hcloud-token$", text, re.M)
    assert re.search(
        r"^use_pass VELOMETER_PREVIEW_PASSWORD velometer/preview-password$", text, re.M
    )


def test_gitignore_keeps_stats_and_tiles_out_of_git():
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "data/stats/" in lines and "data/tiles/" in lines


# --- create ---------------------------------------------------------------------------------


def hetzner(
    requests: list[httpx.Request], *, server_exists=False, type_deprecated=False, arch="x86"
):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test-token"
        path, q = request.url.path, request.url.params
        if request.method == "GET" and path == "/v1/ssh_keys":
            keys = [{"id": 42, "name": "k", "public_key": PUBKEY}] if q.get("name") == "k" else []
            return httpx.Response(200, json={"ssh_keys": keys})
        if request.method == "GET" and path == "/v1/server_types":
            t = {
                "id": 1,
                "name": q.get("name"),
                "architecture": arch,
                "deprecation": {"announced": "2026-01-01"} if type_deprecated else None,
                "prices": [
                    {"location": "nbg1", "price_monthly": {"gross": "4.5100"}},
                    {"location": "fsn1", "price_monthly": {"gross": "4.5100"}},
                ],
            }
            return httpx.Response(200, json={"server_types": [t]})
        if request.method == "GET" and path == "/v1/servers":
            found = [srv_json()] if server_exists else []
            return httpx.Response(200, json={"servers": found})
        if request.method == "GET" and path == "/v1/firewalls":
            return httpx.Response(200, json={"firewalls": []})
        if request.method == "POST" and path == "/v1/firewalls":
            return httpx.Response(201, json={"firewall": {"id": 7}})
        if request.method == "POST" and path == "/v1/servers":
            return httpx.Response(201, json={"server": srv_json(), "root_password": None})
        return httpx.Response(404, json={"error": {"code": "not_found", "message": path}})

    return httpx.MockTransport(handler)


def srv_json():
    return {
        "id": 99,
        "name": "velometer",
        "public_net": {"ipv4": {"ip": "192.0.2.10"}, "ipv6": {"ip": "2001:db8:1:2::/64"}},
    }


def posts(requests, path):
    return [json.loads(r.content) for r in requests if r.method == "POST" and r.url.path == path]


def test_create_sends_type_location_image_key_firewall_and_user_data(deps, monkeypatch):
    requests: list[httpx.Request] = []
    monkeypatch.setattr(srv.DEPS, "transport", hetzner(requests))
    r = invoke("create", "--domain", "example.org", "--ssh-key", "k", input="yes\n")
    assert r.exit_code == 0, r.output
    (fw,) = posts(requests, "/v1/firewalls")
    rules = {(x["protocol"], x.get("port")) for x in fw["rules"]}
    assert rules == {("tcp", "22"), ("tcp", "80"), ("tcp", "443"), ("udp", "443")}
    for rule in fw["rules"]:
        assert rule["direction"] == "in"
        assert set(rule["source_ips"]) == {"0.0.0.0/0", "::/0"}
    (body,) = posts(requests, "/v1/servers")
    assert body["server_type"] == "cx23"  # cx22 is no longer offered (R40)
    assert body["location"] == "nbg1"
    assert body["image"] == "debian-13"
    assert body["ssh_keys"] == [42]
    assert body["firewalls"] == [{"firewall": 7}]
    assert body["public_net"] == {"enable_ipv4": True, "enable_ipv6": True}
    assert body["user_data"] == srv.user_data(PUBKEY)
    assert "192.0.2.10" in r.output


def test_create_takes_type_and_location_options(deps, monkeypatch):
    requests: list[httpx.Request] = []
    monkeypatch.setattr(srv.DEPS, "transport", hetzner(requests))
    r = invoke(
        "create", "--domain", "example.org", "--ssh-key", "k", "--type", "cx32",
        "--location", "fsn1", input="yes\n",
    )  # fmt: skip
    assert r.exit_code == 0, r.output
    (body,) = posts(requests, "/v1/servers")
    assert (body["server_type"], body["location"]) == ("cx32", "fsn1")


@pytest.mark.parametrize("answer", ["", "no\n", "y\n", "YES please\n"])
def test_create_does_nothing_without_a_typed_yes(deps, monkeypatch, answer):
    requests: list[httpx.Request] = []
    monkeypatch.setattr(srv.DEPS, "transport", hetzner(requests))
    r = invoke("create", "--domain", "example.org", "--ssh-key", "k", input=answer)
    assert r.exit_code != 0
    assert [q for q in requests if q.method != "GET"] == []
    assert "plan" in r.output.lower()


def test_create_refuses_a_location_outside_germany(deps, monkeypatch):
    requests: list[httpx.Request] = []
    monkeypatch.setattr(srv.DEPS, "transport", hetzner(requests))
    r = invoke("create", "--domain", "example.org", "--ssh-key", "k", "--location", "hel1",
               input="yes\n")  # fmt: skip
    assert r.exit_code != 0
    assert [q for q in requests if q.method != "GET"] == []


def test_create_refuses_an_unknown_key_an_existing_server_and_a_deprecated_type(deps, monkeypatch):
    cases = [
        ({}, "nope"),
        ({"server_exists": True}, "k"),
        ({"type_deprecated": True}, "k"),
        ({"arch": "arm"}, "k"),  # cloud-init installs the linux_amd64 Caddy
    ]
    for kwargs, key in cases:
        requests: list[httpx.Request] = []
        monkeypatch.setattr(srv.DEPS, "transport", hetzner(requests, **kwargs))
        r = invoke("create", "--domain", "example.org", "--ssh-key", key, input="yes\n")
        assert r.exit_code != 0, (kwargs, key, r.output)
        assert [q for q in requests if q.method != "GET"] == [], (kwargs, key)


def test_user_data_adds_the_key_to_the_deploy_user_and_keeps_everything_else():
    text = srv.user_data(PUBKEY)
    assert text.startswith("#cloud-config\n")
    data = yaml.safe_load(text)
    base = yaml.safe_load(CLOUD_INIT.read_text(encoding="utf-8"))
    (deploy,) = [u for u in data["users"] if isinstance(u, dict) and u["name"] == "deploy"]
    assert deploy["ssh_authorized_keys"] == [PUBKEY]
    deploy.pop("ssh_authorized_keys")
    assert data == base
    assert len(text.encode()) < 32 * 1024  # Hetzner's user-data limit


def test_user_data_refuses_anything_but_one_public_key():
    for bad in ("", "-----BEGIN OPENSSH PRIVATE KEY-----\nabc", PUBKEY + "\nssh-rsa AAAA x"):
        with pytest.raises(srv.ServerError):
            srv.user_data(bad)


# --- dns ------------------------------------------------------------------------------------


def test_dns_prints_a_and_aaaa_for_apex_www_and_velometer_and_writes_nothing(deps, monkeypatch):
    requests: list[httpx.Request] = []
    monkeypatch.setattr(srv.DEPS, "transport", hetzner(requests, server_exists=True))
    r = invoke("dns", "--domain", "example.org")
    assert r.exit_code == 0, r.output
    for name in ("example.org", "www.example.org", "velometer.example.org"):
        assert re.search(rf"^{re.escape(name)}\s+A\s+192\.0\.2\.10$", r.output, re.M), r.output
        assert re.search(rf"^{re.escape(name)}\s+AAAA\s+2001:db8:1:2::1$", r.output, re.M)
    assert all(q.method == "GET" for q in requests)
    assert deps.calls == []


# --- cloud-init -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ci():
    text = CLOUD_INIT.read_text(encoding="utf-8")
    assert text.startswith("#cloud-config\n")
    return yaml.safe_load(text)


def files(ci) -> dict[str, dict]:
    return {f["path"]: f for f in ci["write_files"]}


def runcmd_text(ci) -> str:
    return "\n".join(c if isinstance(c, str) else " ".join(c) for c in ci["runcmd"])


def test_cloud_init_pins_the_timezone_to_utc(ci):
    assert ci["timezone"] in ("Etc/UTC", "UTC")


def test_cloud_init_installs_caddy_at_the_pinned_version_with_a_checksum(ci):
    text = runcmd_text(ci)
    assert "v=2.11.4\n" in text
    assert "caddy_${v}_linux_amd64.tar.gz" in text
    sha = re.search(r"^sha512=([0-9a-f]{128})$", text, re.M)
    assert sha, "no pinned SHA-512"
    assert 'echo "$sha512  $tgz" | sha512sum -c -' in text
    # the check runs before the binary is installed
    assert text.index("sha512sum -c") < text.index("install -m 0755 /usr/local/src/caddy")
    assert "apt-get install caddy" not in text and "caddy" not in ci.get("packages", [])
    assert dr.CADDY_IMAGE == "caddy:2.11.4-alpine"  # the dry run tests the same version


def test_cloud_init_installs_goaccess_rsync_and_unattended_upgrades(ci):
    assert {"goaccess", "rsync", "unattended-upgrades", "curl"} <= set(ci["packages"])
    auto = files(ci)["/etc/apt/apt.conf.d/20auto-upgrades"]["content"]
    assert 'APT::Periodic::Unattended-Upgrade "1";' in auto
    assert 'APT::Periodic::Update-Package-Lists "1";' in auto
    assert "systemctl enable --now unattended-upgrades.service" in runcmd_text(ci)


def test_cloud_init_creates_the_deploy_user_with_key_only_ssh(ci):
    (deploy,) = [u for u in ci["users"] if isinstance(u, dict) and u["name"] == "deploy"]
    assert deploy["lock_passwd"] is True
    assert "ssh_authorized_keys" not in deploy  # create adds the chosen key; no key in the repo
    assert ci["ssh_pwauth"] is False
    sshd = files(ci)["/etc/ssh/sshd_config.d/10-velometer.conf"]["content"].splitlines()
    assert "PasswordAuthentication no" in sshd
    assert "PermitRootLogin no" in sshd
    assert "KbdInteractiveAuthentication no" in sshd
    # sshd keeps the first value: the drop-in sorts before cloud-init's own 50-cloud-init.conf
    assert "10-velometer.conf" < "50-cloud-init.conf"


def test_cloud_init_lock_is_the_dry_runs_default_and_locks(ci):
    lock = files(ci)["/etc/caddy/lock.caddy"]
    assert lock["content"] == dr.LOCK_DEFAULT
    assert 'respond "locked" 401' in lock["content"]
    assert lock["content"].startswith(dr.NO_STORE)
    assert lock["permissions"] == "0640"
    assert "chown root:caddy /etc/caddy/lock.caddy" in runcmd_text(ci)


def test_cloud_init_caddy_never_starts_without_the_caddyfile_and_reads_the_env(ci):
    unit = files(ci)["/etc/systemd/system/caddy.service"]["content"].splitlines()
    assert "ConditionPathExists=/etc/caddy/Caddyfile" in unit
    assert "EnvironmentFile=/etc/caddy/caddy.env" in unit
    assert "User=caddy" in unit
    assert not any(line.startswith("ExecStart=") and "--environ" in line for line in unit)
    # nothing in cloud-init writes a Caddyfile: `setup` does, after the lock is in place
    assert "/etc/caddy/Caddyfile" not in files(ci)


def test_cloud_init_makes_the_release_roots_and_a_monthly_dbip_timer(ci):
    text = runcmd_text(ci)
    for d in ("/srv/velometer/releases", "/srv/datalab/releases", "/srv/tiles"):
        assert d in text
    assert "install -d -m 0750 -o caddy -g caddy /var/log/caddy" in text
    timer = files(ci)["/etc/systemd/system/velometer-dbip.timer"]["content"]
    assert "OnCalendar=*-*-03" in timer and "Persistent=true" in timer
    script = files(ci)["/usr/local/sbin/velometer-dbip"]["content"]
    assert "https://download.db-ip.com/free/dbip-country-lite-" in script
    assert 'mv -f "$tmp" "$dir/dbip-country-lite.mmdb"' in script
    assert "systemctl enable --now velometer-dbip.timer" in text


def test_no_secret_and_no_key_in_the_deploy_files():
    for path in (CLOUD_INIT, GOACCESS):
        text = path.read_text(encoding="utf-8")
        assert not dr.BCRYPT.search(text)
        assert "PRIVATE KEY" not in text
        assert not re.search(r"ssh-(ed25519|rsa) AAAA", text)


# --- deploy: releases, marker, atomic switch (spec §4.2, §4.9 item 5) -----------------------

BUILD = "1234abc-20261022T093005"
REL = f"/srv/velometer/releases/{BUILD}"
PREV = "fedcba9-20261020T120000"


MARK = f"{REL}.complete"


def deploy_rules(rsync_rc=0, current=PREV, listing=None):
    listing = listing if listing is not None else f"{PREV}\n{PREV}.complete\n"
    return [
        ("readlink /srv/velometer/current", (0, f"releases/{current}\n") if current else (1, "")),
        ("ls -1A /srv/velometer/releases", listing),
        ("rsync", (rsync_rc, "")),
    ]


def test_deploy_uploads_into_a_new_release_marks_it_and_switches_atomically(deps, tmp_path):
    deps.rules = deploy_rules(listing=f"{PREV}\n{PREV}.complete\n{BUILD}\n{BUILD}.complete\n")
    r = invoke("deploy", "velometer", str(site_dir(tmp_path)), *HOST, input="yes\n")
    assert r.exit_code == 0, r.output
    (rsync,) = [a for a, _ in deps.calls if a[0] == "rsync"]
    assert rsync[-2:] == [f"{tmp_path / 'site'}/", f"deploy@203.0.113.10:{REL}/"]
    assert f"--link-dest=/srv/velometer/releases/{PREV}" in rsync
    assert "--delete" not in rsync
    # unchanged files are linked although an export rewrites them all: checksum, no times
    assert "--checksum" in rsync and "-a" not in rsync and "-t" not in rsync
    i_rsync, i_mark = deps.index("rsync"), deps.index(f"touch {MARK}")
    i_switch = deps.index("mv -T")
    assert i_rsync < i_mark < i_switch
    switch = deps.joined()[i_switch]
    assert f"test -f {MARK} && ln" in switch
    assert f"ln -sfn releases/{BUILD} /srv/velometer/current.new" in switch
    assert "mv -T /srv/velometer/current.new /srv/velometer/current" in switch


def test_the_build_name_is_the_exports_commit_and_the_deploy_time(deps, tmp_path):
    deps.rules = deploy_rules()
    invoke("deploy", "velometer", str(site_dir(tmp_path)), *HOST, input="yes\n")
    assert any(f"mkdir -p {REL}" in j for j in deps.joined())
    assert srv.RELEASE.fullmatch(REL)


def datalab_dir(tmp_path: Path, stamp_value: str | None = "repo") -> Path:
    """A Datalab build stamped from the repo's committed settings (or `stamp_value`)."""
    from velometer import datalab as dl

    d = site_dir(tmp_path, "datalab-build")
    (d / "build.json").unlink()
    if stamp_value == "repo":
        stamp_value = dl.inputs_stamp(dl.load_config(dl.DEFAULT_CONFIG))
    if stamp_value is not None:
        (d / "build.json").write_text(json.dumps({dl.STAMP_KEY: stamp_value}), encoding="utf-8")
    return d


def test_the_datalab_build_is_named_after_the_local_commit(deps, tmp_path):
    d = datalab_dir(tmp_path)
    deps.rules = [("readlink", (1, "")), ("ls -1A /srv/datalab/releases", "")]
    r = invoke("deploy", "datalab", str(d), *HOST, input="yes\n")
    assert r.exit_code == 0, r.output
    assert any("mkdir -p /srv/datalab/releases/abcdef1-20261022T093005" in j for j in deps.joined())
    (rsync,) = [a for a, _ in deps.calls if a[0] == "rsync"]
    assert not any(a.startswith("--link-dest") for a in rsync)  # no previous release


@pytest.mark.parametrize("case", ["dirty", "no stamp", "stale stamp"])
def test_deploy_datalab_refuses_a_dirty_tree_or_a_build_not_from_head(deps, tmp_path, case):
    """M7: the release is named after HEAD, so the tree is clean and the build carries the
    stamp of the committed settings."""
    stamp_value = {"dirty": "repo", "no stamp": None, "stale stamp": "0" * 64}[case]
    d = datalab_dir(tmp_path, stamp_value)
    if case == "dirty":
        srv.DEPS.git_dirty = lambda: True
    r = invoke("deploy", "datalab", str(d), *HOST, input="yes\n")
    assert r.exit_code == 1
    assert {"dirty": "uncommitted", "no stamp": "no build stamp", "stale stamp": "build it again"}[
        case
    ] in r.output
    assert deps.calls == []


@pytest.mark.parametrize("rc", [23, 255, -9, -15])
def test_an_interrupted_rsync_never_switches_current(deps, tmp_path, rc):
    """Review Focus 3: rsync failing halfway (23), the connection dropping (255) or rsync killed
    by a signal leaves `current` on the previous complete release."""
    deps.rules = deploy_rules(rsync_rc=rc)
    r = invoke("deploy", "velometer", str(site_dir(tmp_path)), *HOST, input="yes\n")
    assert r.exit_code != 0
    joined = deps.joined()
    assert not any(".complete" in j and "touch" in j for j in joined)
    assert not any("ln -s" in j or "mv -T" in j or "current.new" in j for j in joined)
    assert not any(j.startswith("ssh") and " rm " in f" {j} " for j in joined)
    assert "current" in r.output and PREV in r.output


def test_a_failed_marker_never_switches_current(deps, tmp_path):
    deps.rules = deploy_rules() + [("touch", (1, ""))]
    r = invoke("deploy", "velometer", str(site_dir(tmp_path)), *HOST, input="yes\n")
    assert r.exit_code != 0
    assert not any("mv -T" in j for j in deps.joined())


def test_the_marker_lies_beside_the_release_never_inside_it(deps, tmp_path):
    """Ruling R33: the served tree (the release) holds no `.complete`; the marker is the
    release's sibling `<release>.complete`, and the switch requires it."""
    deps.rules = deploy_rules()
    r = invoke("deploy", "velometer", str(site_dir(tmp_path)), *HOST, input="yes\n")
    assert r.exit_code == 0, r.output
    joined = deps.joined()
    assert not any(f"{REL}/.complete" in j or "/.complete" in j for j in joined)
    assert srv.MARKER_PATH.fullmatch(MARK) and not MARK.startswith(REL + "/")
    assert any(j.endswith(f"touch {MARK}") for j in joined)


@pytest.mark.parametrize(
    "link",
    [
        "../../etc",
        "releases/../../etc",
        "/etc",
        "releases/x",
        "releases/",
        "other/1234abc-20261020T120000",
    ],  # noqa: E501
)
def test_deploy_stops_when_current_points_to_no_release(deps, tmp_path, link):
    deps.rules = [("readlink /srv/velometer/current", (0, link + "\n"))]
    r = invoke("deploy", "velometer", str(site_dir(tmp_path)), *HOST, input="yes\n")
    assert r.exit_code != 0
    assert "not a release" in r.output
    assert not any("mkdir" in j or j.startswith("rsync") for j in deps.joined())


@pytest.mark.parametrize("content", [None, "{not json", "[1, 2]", '{"commit": null}'])
def test_deploy_stops_cleanly_without_a_usable_build_json(deps, tmp_path, content):
    d = site_dir(tmp_path)
    if content is None:
        (d / "build.json").unlink()
    else:
        (d / "build.json").write_text(content, encoding="utf-8")
    r = invoke("deploy", "velometer", str(d), *HOST, input="yes\n")
    assert r.exit_code == 1
    assert "error:" in r.output and "Traceback" not in r.output
    assert deps.calls == []


def test_deploy_does_nothing_without_a_typed_yes(deps, tmp_path):
    deps.rules = deploy_rules()
    r = invoke("deploy", "velometer", str(site_dir(tmp_path)), *HOST, input="no\n")
    assert r.exit_code != 0
    assert not any(a[0] == "rsync" for a, _ in deps.calls)
    assert not any("mkdir" in j or "mv " in j or "rm " in j for j in deps.joined())


def test_deploy_refuses_an_export_that_fails_deploy_check(deps, tmp_path, monkeypatch):
    monkeypatch.setattr(srv.DEPS, "check_site", lambda path: ["404.html missing"])
    r = invoke("deploy", "velometer", str(site_dir(tmp_path)), *HOST, input="yes\n")
    assert r.exit_code != 0
    assert "404.html missing" in r.output
    assert deps.calls == []


def test_deploy_tiles_writes_a_temp_name_in_the_same_directory_then_renames(deps, tmp_path):
    f = tmp_path / "x.pmtiles"
    f.write_bytes(b"PMTiles\x03")
    r = invoke("deploy", "tiles", str(f), *HOST, input="yes\n")
    assert r.exit_code == 0, r.output
    (rsync,) = [a for a, _ in deps.calls if a[0] == "rsync"]
    assert rsync[-1] == "deploy@203.0.113.10:/srv/tiles/velometer.pmtiles.new"
    i = deps.index("mv -f /srv/tiles/velometer.pmtiles.new /srv/tiles/velometer.pmtiles")
    assert i > deps.index("rsync")


@pytest.mark.parametrize("rc", [23, 255, -9])
def test_an_interrupted_tile_upload_never_replaces_the_tiles(deps, tmp_path, rc):
    f = tmp_path / "x.pmtiles"
    f.write_bytes(b"PMTiles\x03")
    deps.rules = [("rsync", (rc, ""))]
    r = invoke("deploy", "tiles", str(f), *HOST, input="yes\n")
    assert r.exit_code != 0
    assert not any("mv " in j for j in deps.joined())


# --- cleanup guard --------------------------------------------------------------------------

GOOD = [
    "/srv/velometer/releases/1234abc-20261022T093005",
    "/srv/datalab/releases/" + "a" * 40 + "-20260101T000000",
]
BAD = [
    "/srv/velometer/releases/1234ab-20261022T093005",  # sha too short
    "/srv/velometer/releases/" + "a" * 41 + "-20261022T093005",  # sha too long
    "/srv/velometer/releases/1234ABC-20261022T093005",  # capitals
    "/srv/velometer/releases/1234abc-20261022T093005/",
    "/srv/velometer/releases/1234abc-20261022T093005\n",
    "/srv/velometer/releases/1234abc-20261022T093005/..",
    "/srv/velometer/releases/../1234abc-20261022T093005",
    "/srv/velometer/releases/1234abc-2026102T093005",
    "/srv/velometer/releases/1234abc-20261022T09300٥",  # a non-ASCII digit
    "/srv/velometer/releases",
    "/srv/velometer/current",
    "/srv/velo-meter/releases/1234abc-20261022T093005",
    "/srv/Velometer/releases/1234abc-20261022T093005",
    "/srv//releases/1234abc-20261022T093005",
    "/srv/tiles",
    "/",
    "srv/velometer/releases/1234abc-20261022T093005",
]


def test_the_guard_is_the_briefs_regex():
    assert srv.RELEASE.pattern == r"^/srv/[a-z]+/releases/[0-9a-f]{7,40}-\d{8}T\d{6}$"
    assert srv.MARKER_PATH.pattern == (
        r"^/srv/[a-z]+/releases/[0-9a-f]{7,40}-\d{8}T\d{6}\.complete$"
    )


@pytest.mark.parametrize("path", [p + ".complete" for p in GOOD])
def test_the_guard_admits_markers(path):
    assert srv.guard_release(path) == path


@pytest.mark.parametrize(
    "path",
    [p + ".complete" for p in BAD if not p.endswith("\n")]
    + [
        GOOD[0] + "/.complete",
        GOOD[0] + ".completed",
        GOOD[0] + "xcomplete",
        GOOD[0] + ".complete\n",
    ],
)
def test_the_guard_refuses_marker_lookalikes(path):
    with pytest.raises(srv.ServerError):
        srv.guard_release(path)


@pytest.mark.parametrize("path", GOOD)
def test_the_guard_admits_release_paths(path):
    assert srv.guard_release(path) == path


@pytest.mark.parametrize("path", BAD)
def test_the_guard_refuses_anything_else(path):
    with pytest.raises(srv.ServerError):
        srv.guard_release(path)


def rel(n: int, sha="1234abc") -> str:
    return f"{sha}-2026102{n}T000000"


def complete(*names: str) -> list[str]:
    return [x for n in names for x in (n, n + ".complete")]


B = "/srv/velometer/releases/"


def test_cleanup_keeps_the_three_newest_complete_releases_and_current():
    names = complete(*(rel(n) for n in range(1, 7))) + [rel(0, "fff0000")]
    gone = srv.plan_cleanup("velometer", names, current=rel(2))
    assert gone == [
        B + rel(0, "fff0000"),  # partial: no marker
        B + rel(1) + ".complete",
        B + rel(1),
        B + rel(3) + ".complete",
        B + rel(3),
    ]


def test_cleanup_removes_a_marker_before_its_release_and_orphaned_markers():
    names = complete(*(rel(n) for n in range(1, 5))) + [rel(9, "abc1234") + ".complete"]
    gone = srv.plan_cleanup("velometer", names, current=rel(4))
    assert gone == [B + rel(1) + ".complete", B + rel(1), B + rel(9, "abc1234") + ".complete"]


def test_cleanup_orders_by_deploy_time_not_by_name():
    names = complete("fff0000-20261021T000000", "0000aaa-20261024T000000",
                     "aaa1111-20261023T000000", "bbb2222-20261022T000000")  # fmt: skip
    gone = srv.plan_cleanup("velometer", names, current="0000aaa-20261024T000000")
    assert gone == [B + "fff0000-20261021T000000.complete", B + "fff0000-20261021T000000"]


def test_cleanup_ignores_every_name_the_guard_does_not_admit():
    odd = ["..", ".", "current", "x", "1234abc-20261022T093005.old", "-rf", "*", "a b",
           "1234abc-20261022T093005\nx", "../../etc", ".complete", "x.complete",
           "1234abc-20261022T093005.complete.old", "1234abc-20261022T093005/.complete"]  # fmt: skip
    names = odd + complete(*(rel(n) for n in range(1, 4)))
    assert srv.plan_cleanup("velometer", names, current=rel(3)) == []


def test_cleanup_removes_only_guarded_paths_without_force(deps, tmp_path):
    old = [rel(n) for n in range(1, 5)]
    listing = "\n".join(complete(*old) + ["../../etc", "current", "x.complete"]) + "\n"
    deps.rules = deploy_rules(current=rel(4), listing=listing)
    r = invoke("deploy", "velometer", str(site_dir(tmp_path)), *HOST, input="yes\n")
    assert r.exit_code == 0, r.output
    rms = [j for j in deps.joined() if re.search(r"\brm\b", j)]
    assert rms, deps.joined()
    for j in rms:
        assert "-f" not in j.split() and "-rf" not in j and "-fr" not in j
        (path,) = re.findall(r"/srv/\S+", j)
        assert srv.RELEASE.fullmatch(path) or srv.MARKER_PATH.fullmatch(path), j
        if srv.MARKER_PATH.fullmatch(path):
            assert "-r" not in j.split()  # a marker is a file
    removed = [re.findall(r"/srv/\S+", j)[0].rsplit("/", 1)[1] for j in rms]
    # 2, 3, 4 are kept; the new BUILD is not listed in this fake; the marker goes first
    assert removed == [rel(1) + ".complete", rel(1)]


# --- setup (idempotent; the password only on stdin) -----------------------------------------


def sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()


def caddy_json(lock: str) -> str:
    """A loaded Caddy config as the admin API returns it, three sites importing `lock`."""
    state = srv.lock_state(lock)
    if state == "password":
        handler = {"handler": "authentication", "providers": {"http_basic": {
            "accounts": [{"password": lock.split()[-2], "username": "preview"}],
            "hash": {"algorithm": "bcrypt"}}}}  # fmt: skip
    elif state == "default":
        handler = {"body": "locked", "handler": "static_response", "status_code": 401}
    else:
        handler = {"handler": "vars"}
    route = {"handle": [{"handler": "subroute", "routes": [{"handle": [handler]}]}]}
    return json.dumps({"apps": {"http": {"servers": {"srv0": {"routes": [route] * 3}}}}})


def server_state(
    lock: str, *, synced=False, domain="example.org", active=True, running=None, on_disk=None
):
    sums = ""
    if synced:
        sums = "".join(
            f"{sha(t)}  {p}\n"
            for p, t in (
                ("/etc/caddy/Caddyfile", (ROOT / "deploy" / "Caddyfile").read_text("utf-8")),
                ("/etc/caddy/caddy.env", srv.caddy_env(domain)),
                ("/etc/goaccess/velometer.conf", GOACCESS.read_text("utf-8")),
            )
        )
    running = lock if running is None else running
    on_disk = lock if on_disk is None else on_disk
    return [
        ("cat /etc/caddy/lock.caddy", lock),
        ("sha256sum", sums),
        ("hash-password", HASH + "\n"),
        ("systemctl is-active caddy", "active\n" if active else (3, "inactive\n")),
        ("curl -fsS http://localhost:2019/config/", caddy_json(running) if active else (7, "")),
        ("caddy adapt --config /etc/caddy/Caddyfile", caddy_json(on_disk)),
    ]


def test_setup_on_a_fresh_server_hashes_on_the_server_and_writes_the_lock(deps):
    deps.rules = server_state(dr.LOCK_DEFAULT)
    r = invoke("setup", *HOST, "--domain", "example.org", input="yes\n")
    assert r.exit_code == 0, r.output
    (hash_argv, hash_in) = deps.calls[deps.index("hash-password")]
    assert hash_argv[0] == "ssh" and hash_argv[-1].endswith("caddy hash-password")
    assert hash_in == PASSWORD + "\n"
    lock_writes = [i for a, i in deps.calls if "/etc/caddy/lock.caddy" in " ".join(a) and i]
    assert lock_writes == [dr.lock_text(HASH)]
    assert any("systemctl reload-or-restart caddy" in j for j in deps.joined())


def test_the_password_never_appears_on_any_command_line(deps):
    deps.rules = server_state(dr.LOCK_DEFAULT)
    invoke("setup", *HOST, "--domain", "example.org", input="yes\n")
    assert deps.calls
    for argv, _ in deps.calls:
        assert not any(PASSWORD in a for a in argv), argv
        assert not any(HASH in a for a in argv), argv
    for _, stdin in deps.calls:
        if stdin and PASSWORD in stdin:
            assert stdin == PASSWORD + "\n"  # only the hash-password call sees it


def test_setup_validates_the_caddyfile_as_the_caddy_user_before_it_goes_live(deps):
    deps.rules = server_state(dr.LOCK_DEFAULT)
    invoke("setup", *HOST, "--domain", "example.org", input="yes\n")
    i_val = deps.index("caddy validate --config /etc/caddy/Caddyfile.new")
    assert "sudo -u caddy" in deps.joined()[i_val]
    assert "--envfile /etc/caddy/caddy.env" in deps.joined()[i_val]
    assert i_val < deps.index("mv -f /etc/caddy/Caddyfile.new /etc/caddy/Caddyfile")
    assert i_val < deps.index("reload-or-restart caddy")
    uploads = {i for _, i in deps.calls if i}
    assert (ROOT / "deploy" / "Caddyfile").read_text("utf-8") in uploads
    assert srv.caddy_env("example.org") in uploads
    assert GOACCESS.read_text("utf-8") in uploads


def test_caddy_env_names_the_domain_and_site_root():
    lines = srv.caddy_env("example.org").splitlines()
    assert lines[-2:] == ["DOMAIN=example.org", "SITE_ROOT=/srv"]
    with pytest.raises(srv.ServerError):
        srv.caddy_env("https://example.org")


def test_setup_run_twice_changes_nothing_and_asks_nothing(deps):
    deps.rules = server_state(dr.lock_text(HASH), synced=True)
    r = invoke("setup", *HOST, "--domain", "example.org", input="")
    assert r.exit_code == 0, r.output
    assert "nothing to change" in r.output
    assert all(i is None for _, i in deps.calls)  # nothing uploaded
    assert not any("hash-password" in j or "reload" in j for j in deps.joined())


HASH2 = "$2a$14$" + "b" * 53


def test_a_failed_reload_says_what_still_runs_and_the_next_setup_reloads(deps):
    deps.rules = [("reload-or-restart", (1, ""))] + server_state(dr.LOCK_DEFAULT)
    r = invoke("setup", *HOST, "--domain", "example.org", input="yes\n")
    assert r.exit_code == 1
    assert "still serves the previous lock" in r.output
    assert "default lock" in r.output
    # on disk now: the password lock and the files; running: still the default lock
    second = FakeRunner(server_state(dr.lock_text(HASH), synced=True, running=dr.LOCK_DEFAULT))
    srv.DEPS.runner = second
    r2 = invoke("setup", *HOST, "--domain", "example.org", input="yes\n")
    assert r2.exit_code == 0, r2.output
    assert "nothing to change" not in r2.output
    assert "reload or start Caddy" in r2.output
    assert any("reload-or-restart caddy" in j for j in second.joined())
    assert all(i is None for _, i in second.calls)  # nothing uploaded, nothing hashed


def test_setup_starts_a_stopped_caddy_even_when_the_files_are_current(deps):
    deps.rules = server_state(dr.lock_text(HASH), synced=True, active=False)
    r = invoke("setup", *HOST, "--domain", "example.org", input="yes\n")
    assert r.exit_code == 0, r.output
    assert "not running" in r.output
    assert any("reload-or-restart caddy" in j for j in deps.joined())


def test_setup_reloads_when_the_running_config_differs_from_disk(deps):
    deps.rules = server_state(dr.lock_text(HASH), synced=True, running=dr.lock_text(HASH2))
    r = invoke("setup", *HOST, "--domain", "example.org", input="no\n")
    assert r.exit_code != 0  # it asked: a reload is planned
    assert "reload or start Caddy" in r.output


def test_served_lock_reads_the_three_forms():
    assert srv.served_lock(json.loads(caddy_json(dr.LOCK_DEFAULT))) == "default"
    assert srv.served_lock(json.loads(caddy_json(""))) == "open"
    assert srv.served_lock(json.loads(caddy_json(dr.lock_text(HASH)))) == "password " + HASH


def test_setup_relock_locks_an_unlocked_server_again(deps):
    deps.rules = server_state("", synced=True)
    r = invoke("setup", *HOST, "--domain", "example.org", "--relock", input="yes\n")
    assert r.exit_code == 0, r.output
    (_, stdin) = deps.calls[deps.index("hash-password")]
    assert stdin == PASSWORD + "\n"
    writes = [i for a, i in deps.calls if "/etc/caddy/lock.caddy" in " ".join(a) and i]
    assert writes == [dr.lock_text(HASH)]
    assert deps.index("lock.caddy.XXXXXX") < deps.index("reload-or-restart caddy")


def test_setup_new_password_rehashes_a_locked_server(deps):
    deps.rules = server_state(dr.lock_text(HASH2), synced=True)
    r = invoke("setup", *HOST, "--domain", "example.org", "--new-password", input="yes\n")
    assert r.exit_code == 0, r.output
    writes = [i for a, i in deps.calls if "/etc/caddy/lock.caddy" in " ".join(a) and i]
    assert writes == [dr.lock_text(HASH)]
    assert any("reload-or-restart caddy" in j for j in deps.joined())


def test_setup_without_flags_keeps_a_locked_servers_hash(deps):
    deps.rules = server_state(dr.lock_text(HASH2), synced=True)
    r = invoke("setup", *HOST, "--domain", "example.org", input="")
    assert r.exit_code == 0, r.output
    assert "nothing to change" in r.output
    assert not any("hash-password" in j for j in deps.joined())


def test_a_command_without_input_never_inherits_the_tools_stdin(monkeypatch):
    """Task 9: `echo yes | server.py setup` lost its `yes` to ssh, which read the inherited
    stdin. Without input, the runner gives the process /dev/null; with input, the input."""
    seen: list[dict] = []

    def fake_run(argv, **kw):
        seen.append(kw)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(srv.subprocess, "run", fake_run)
    monkeypatch.setattr(srv.DEPS, "runner", srv._run)
    srv.Target("203.0.113.10").ssh("true")
    srv.Target("203.0.113.10").put("/etc/x", "text")
    no_input, with_input = seen
    assert no_input.get("stdin") is subprocess.DEVNULL and no_input.get("input") is None
    assert with_input.get("input") == "text" and "stdin" not in with_input


def test_the_runner_really_closes_stdin(monkeypatch):
    """The same rule on a real process: `cat` without input ends at once, reading nothing,
    even when the tool's own stdin holds a waiting `yes`."""
    r_fd, w_fd = os.pipe()
    os.write(w_fd, b"yes\n")
    os.close(w_fd)  # an inherited stdin would give cat the `yes`, then end-of-file
    saved = os.dup(0)
    try:
        os.dup2(r_fd, 0)
        r = srv._run(["cat"])
    finally:
        os.dup2(saved, 0)
        for fd in (saved, r_fd):
            os.close(fd)
    assert r.returncode == 0 and r.stdout == ""


def test_put_removes_its_temp_file_on_every_exit(deps):
    srv.Target("h").put("/etc/x", "text")
    ((argv, stdin),) = deps.calls
    assert "trap 'rm -f \"$t\"' EXIT" in argv[-1].replace("'\"'\"'", "'")
    assert stdin == "text"


def test_setup_keeps_an_unlocked_server_unlocked(deps):
    deps.rules = server_state("", synced=False)
    r = invoke("setup", *HOST, "--domain", "example.org", input="yes\n")
    assert r.exit_code == 0, r.output
    assert not any("hash-password" in j for j in deps.joined())
    assert not any("lock.caddy" in " ".join(a) and i is not None for a, i in deps.calls)


def test_setup_needs_the_password_only_to_write_the_lock(deps, monkeypatch):
    monkeypatch.delenv("VELOMETER_PREVIEW_PASSWORD")
    deps.rules = server_state(dr.LOCK_DEFAULT)
    r = invoke("setup", *HOST, "--domain", "example.org", input="yes\n")
    assert r.exit_code == 1
    assert "pass insert velometer/preview-password" in r.output
    assert all(i is None for _, i in deps.calls)


def test_setup_does_nothing_without_a_typed_yes(deps):
    deps.rules = server_state(dr.LOCK_DEFAULT)
    r = invoke("setup", *HOST, "--domain", "example.org", input="no\n")
    assert r.exit_code != 0
    assert all(i is None for _, i in deps.calls)
    assert not any("hash-password" in j or "reload" in j or "mv " in j for j in deps.joined())


def test_setup_refuses_a_lock_file_it_does_not_recognise(deps):
    deps.rules = server_state("import somewhere-else\n")
    r = invoke("setup", *HOST, "--domain", "example.org", input="yes\n")
    assert r.exit_code != 0
    assert all(i is None for _, i in deps.calls)


# --- unlock ---------------------------------------------------------------------------------


def golive_fixture(tmp_path: Path, *, open_items: bool) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / "sites" / "datalab").mkdir(parents=True)
    (root / "docs" / "review").mkdir(parents=True)
    op = {k: (None if open_items else "v") for k in ("name", "address", "email")}
    cfg = {
        "domain": "example.org",
        "operator_form": None if open_items else "person",
        "operator": op,
        "contact_email": None if open_items else "kontakt@example.org",
    }
    (root / "sites" / "datalab" / "site.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    verdict = "decision for the user" + ("" if open_items else " (decided 2026-10-22: A)")
    (root / "docs" / "review" / "m16-legal.md").write_text(
        "# Review\n\n- Verdicts (ruling P3): `ok` / `decision for the user`.\n\n"
        "## Contents (2 topics, one verdict each)\n\n| § | Topic | Verdict |\n|---|---|---|\n"
        "| 4.6 | Source code | decision for the user |\n| 4.7 | Other | ok |\n\n"
        f"### 4.6 Source code\n\nText.\n\n**Verdict:** {verdict}\n\n"
        "### 4.7 Other\n\n**Verdict:** ok\n",
        encoding="utf-8",
    )
    status = "open" if open_items else "reviewed"
    (root / "docs" / "review" / "m16-press.md").write_text(
        "# Press\n\n| Risk | Claims | Rows |\n|---|---|---|\n| low | 1 | 2 |\n\n## Table\n\n"
        "| # | File | Key | Lang | Sentence | Source | Fact or opinion | Risk | Proposed rewording | Status |\n"  # noqa: E501
        "|---|---|---|---|---|---|---|---|---|---|\n"
        "| 1 (1) | a.yaml | `k` | en | A said. | s | fact | low | keep | reviewed |\n"
        f"| 2 (1) | a.yaml | `k` | de | A sagte. | s | fact | low | keep | {status} |\n",
        encoding="utf-8",
    )
    datalab = tmp_path / "datalab-out"
    (datalab / "impressum").mkdir(parents=True)
    body = "[[Name des Betreibers]]" if open_items else "Erika Mustermann"
    (datalab / "impressum" / "index.html").write_text(f"<p>{body}</p>\n", encoding="utf-8")
    (datalab / "index.html").write_text("<p>ok</p>\n", encoding="utf-8")
    stamp(root, datalab)
    return root, datalab


def stamp(root: Path, datalab: Path) -> None:
    """The build stamp `velometer datalab build` writes, for the fixture's settings."""
    from velometer import datalab as dl

    site = root / "sites" / "datalab"
    value = dl.inputs_stamp(dl.load_config(site / "site.yaml"), site)
    (datalab / "build.json").write_text(json.dumps({dl.STAMP_KEY: value}), encoding="utf-8")


def test_golive_check_lists_every_open_item_and_exits_1(tmp_path):
    root, datalab = golive_fixture(tmp_path, open_items=True)
    r = invoke("golive-check", "--datalab", str(datalab), "--root", str(root))
    assert r.exit_code == 1
    out = r.output
    assert "operator_form" in out
    assert "impressum/index.html:1" in out  # the placeholder, from placeholders()
    assert "contact_email" in out
    assert "4.6 Source code" in out and "decision for the user" in out
    assert out.count("decision for the user") == 1  # the summary table holds no verdict
    assert re.search(r"press row 2 \(1\).*open", out)
    assert "press row 1 (1)" not in out


def test_golive_check_passes_when_nothing_is_open_and_still_prints_the_manual_items(tmp_path):
    root, datalab = golive_fixture(tmp_path, open_items=False)
    r = invoke("golive-check", "--datalab", str(datalab), "--root", str(root))
    assert r.exit_code == 0, r.output
    for needle in ("AVV", "lock", "roll_keep_for", "15 days"):
        assert needle in r.output


def test_golive_check_always_prints_the_manual_confirmations_when_failing_too(tmp_path):
    root, datalab = golive_fixture(tmp_path, open_items=True)
    r = invoke("golive-check", "--datalab", str(datalab), "--root", str(root))
    assert "AVV" in r.output and "roll_keep_for" in r.output


def test_golive_items_reads_each_rule_separately(tmp_path):
    root, datalab = golive_fixture(tmp_path, open_items=False)
    assert srv.golive_items(root, datalab) == []
    legal = root / "docs" / "review" / "m16-legal.md"
    legal.write_text(legal.read_text("utf-8").replace(" (decided 2026-10-22: A)", ""), "utf-8")
    (item,) = srv.golive_items(root, datalab)
    assert "4.6 Source code" in item
    root2, datalab2 = golive_fixture(tmp_path / "b", open_items=False)
    cfg = root2 / "sites" / "datalab" / "site.yaml"
    data = yaml.safe_load(cfg.read_text("utf-8"))
    data["contact_email"] = "   "
    cfg.write_text(yaml.safe_dump(data), "utf-8")
    stamp(root2, datalab2)
    (item,) = srv.golive_items(root2, datalab2)
    assert "contact_email" in item


def test_golive_a_chosen_form_without_an_address_is_open(tmp_path):
    # the pages leave the address out without a trace, so only this check still sees it
    root, datalab = golive_fixture(tmp_path, open_items=False)
    cfg = root / "sites" / "datalab" / "site.yaml"
    data = yaml.safe_load(cfg.read_text("utf-8"))
    data["operator"]["address"] = None
    cfg.write_text(yaml.safe_dump(data), "utf-8")
    stamp(root, datalab)  # built from these settings
    (item,) = srv.golive_items(root, datalab)
    assert "operator.address is null" in item


WAIVER = (
    "**Go-live without:** operator.address (decided 2026-10-28: the user goes live without it "
    "and accepts the risk)"
)


def _no_address(tmp_path: Path, legal_extra: str) -> tuple[Path, Path]:
    root, datalab = golive_fixture(tmp_path, open_items=False)
    cfg = root / "sites" / "datalab" / "site.yaml"
    data = yaml.safe_load(cfg.read_text("utf-8"))
    data["operator"]["address"] = None
    cfg.write_text(yaml.safe_dump(data), "utf-8")
    stamp(root, datalab)
    legal = root / "docs" / "review" / "m16-legal.md"
    legal.write_text(legal.read_text("utf-8") + legal_extra, "utf-8")
    return root, datalab


def test_golive_a_recorded_waiver_lets_the_missing_address_through_and_says_so(tmp_path):
    # ruling R43: the user decided (2026-10-28) to go live without the address; the waiver is a
    # dated line in m16-legal.md, and the check names it instead of dropping the address silently
    root, datalab = _no_address(tmp_path, f"\n{WAIVER}\n")
    assert srv.golive_items(root, datalab) == []
    (w,) = srv.golive_waivers(root)
    assert "operator.address" in w and "2026-10-28" in w
    r = invoke("golive-check", "--datalab", str(datalab), "--root", str(root))
    assert r.exit_code == 0, r.output
    assert "waived: operator.address" in r.output


@pytest.mark.parametrize(
    "extra",
    [
        "",  # no waiver at all
        "\n**Go-live without:** operator.address\n",  # undated: not a decision
        "\n**Go-live without:** operator.address (decided soon: maybe)\n",
        "\n**Go-live without:** operator.email (decided 2026-10-28: no)\n",  # another key
        "\nWe could note **Go-live without:** operator.address (decided 2026-10-28: x) here.\n",
    ],
)
def test_golive_without_an_exact_waiver_the_missing_address_stays_open(tmp_path, extra):
    root, datalab = _no_address(tmp_path, extra)
    items = srv.golive_items(root, datalab)
    assert any("operator.address is null" in i for i in items), items


def test_golive_only_deferred_keys_can_be_waived(tmp_path):
    # a waiver line naming a key that is not deferred (email) waives nothing and is itself open
    root, datalab = golive_fixture(tmp_path, open_items=False)
    legal = root / "docs" / "review" / "m16-legal.md"
    legal.write_text(
        legal.read_text("utf-8")
        + "\n**Go-live without:** operator.email (decided 2026-10-28: no)\n",
        "utf-8",
    )
    items = srv.golive_items(root, datalab)
    assert any("operator.email cannot be waived" in i for i in items), items


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text("utf-8")
    assert old in text, old
    path.write_text(text.replace(old, new), "utf-8")


DECIDED = "**Verdict:** decision for the user (decided 2026-10-22: A)"
LEGAL_DRIFT = {
    "list item": (DECIDED, "- " + DECIDED),
    "bold colon outside": (DECIDED, DECIDED.replace("**Verdict:**", "**Verdict**:")),
    "capitalised value": (DECIDED, "**Verdict:** Decision for the user (decided 2026-10-22: A)"),
    "decided without a date": (DECIDED, "**Verdict:** decision for the user (decided later)"),
    "decided without the decision": (
        DECIDED,
        "**Verdict:** decision for the user (decided 2026-10-22)",
    ),  # noqa: E501
    "unknown verdict": ("**Verdict:** ok", "**Verdict:** fine"),
    "trailing words": ("**Verdict:** ok", "**Verdict:** ok, mostly"),
    "decided on another verdict": ("**Verdict:** ok", "**Verdict:** ok (decided 2026-10-22: x)"),
    "upper-case label": ("**Verdict:** ok", "VERDICT: ok"),
    "a verdict line lost": ("\n\n**Verdict:** ok\n", "\n\nok\n"),
    "every verdict line lost": ("**Verdict:**", "**Ruling:**"),
    # the count still matches: only the label check sees these
    "an extra drifted label": ("Text.\n", "Text.\n\n- **Verdict:** see 4.7\n"),
    "an extra lower-case label": ("Text.\n", "Text.\n\nverdict: decision for the user\n"),
    "no contents table": ("| § | Topic | Verdict |", "| § | Topic | Result |"),
}


def test_golive_legal_without_any_verdict_is_open(tmp_path):
    root, datalab = golive_fixture(tmp_path, open_items=False)
    (root / "docs" / "review" / "m16-legal.md").write_text(
        "# Review\n\n| § | Topic | Verdict |\n|---|---|---|\n\nNothing reviewed yet.\n", "utf-8"
    )
    items = srv.golive_items(root, datalab)
    assert any("no verdict line" in i for i in items), items


@pytest.mark.parametrize("case", sorted(LEGAL_DRIFT))
def test_golive_legal_parser_fails_closed_on_format_drift(tmp_path, case):
    root, datalab = golive_fixture(tmp_path, open_items=False)
    path = root / "docs" / "review" / "m16-legal.md"
    assert srv.golive_items(root, datalab) == []
    old, new = LEGAL_DRIFT[case]
    text = path.read_text("utf-8")
    assert old in text
    path.write_text(text.replace(old, new), "utf-8")
    items = srv.golive_items(root, datalab)
    assert items and all("m16-legal.md" in i for i in items), items


HEADER = "| # | File | Key | Lang | Sentence | Source | Fact or opinion | Risk | Proposed rewording | Status |"  # noqa: E501
ROW2 = "| 2 (1) | a.yaml | `k` | de | A sagte. | s | fact | low | keep | open |"
PRESS_FORMAT_DRIFT = {
    "No. for #": [("| # |", "| No. |")],
    "status in lower case": [("| Status |", "| status |")],
    "STATUS in capitals": [("| Status |", "| STATUS |")],
    "a column after Status": [
        ("| Status |", "| Status | Note |"),
        (
            "|---|---|---|---|---|---|---|---|---|---|",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ),  # noqa: E501
        ("| reviewed |", "| reviewed | x |"),
        ("| open |", "| open | x |"),
    ],
    "rows without a leading pipe": [("\n| 1 (1)", "\n1 (1)"), ("\n| 2 (1)", "\n2 (1)")],
}


@pytest.mark.parametrize("case", sorted(PRESS_FORMAT_DRIFT))
def test_golive_press_parser_still_finds_the_open_row_after_format_drift(tmp_path, case):
    root, datalab = golive_fixture(tmp_path, open_items=True)
    path = root / "docs" / "review" / "m16-press.md"
    for old, new in PRESS_FORMAT_DRIFT[case]:
        _edit(path, old, new)
    items = srv.golive_items(root, datalab)
    press = [i for i in items if i.startswith(("press row", "m16-press.md"))]
    assert press == [press[0]] and press[0].startswith("press row 2 (1)"), press
    assert press[0].endswith("status open")


PRESS_BROKEN = {
    "status not open or reviewed": [("keep | reviewed |", "keep | done |")],
    "Reviewed with a capital": [("keep | reviewed |", "keep | Reviewed |")],
    "empty status": [("keep | reviewed |", "keep |  |")],
    "a cell missing": [("| low | keep | reviewed |", "| low | reviewed |")],
    "an extra cell": [("| keep | reviewed |", "| keep | x | reviewed |")],
    "no Status column": [("| Status |", "| State |")],
    "two Status tables": [("| Risk | Claims | Rows |", "| Risk | Claims | Status |")],
    "no rows": [
        (ROW2.replace("open", "reviewed") + "\n", ""),
        ("| 1 (1) | a.yaml | `k` | en | A said. | s | fact | low | keep | reviewed |\n", ""),
    ],  # noqa: E501
}


@pytest.mark.parametrize("case", sorted(PRESS_BROKEN))
def test_golive_press_parser_fails_closed(tmp_path, case):
    root, datalab = golive_fixture(tmp_path, open_items=False)
    assert srv.golive_items(root, datalab) == []
    path = root / "docs" / "review" / "m16-press.md"
    for old, new in PRESS_BROKEN[case]:
        _edit(path, old, new)
    items = srv.golive_items(root, datalab)
    assert items and all(i.startswith(("press row", "m16-press.md")) for i in items), items


@pytest.mark.parametrize("name", ["m16-legal.md", "m16-press.md"])
def test_golive_a_missing_or_unreadable_review_file_is_open(tmp_path, name):
    root, datalab = golive_fixture(tmp_path, open_items=False)
    path = root / "docs" / "review" / name
    path.unlink()
    (item,) = srv.golive_items(root, datalab)
    assert item.startswith(f"{name}: not readable")
    path.write_bytes(b"\xff\xfe not utf-8 \x80")
    (item,) = srv.golive_items(root, datalab)
    assert item.startswith(f"{name}: not readable")


def test_golive_a_missing_datalab_config_is_open(tmp_path):
    root, datalab = golive_fixture(tmp_path, open_items=False)
    (root / "sites" / "datalab" / "site.yaml").unlink()
    (item,) = srv.golive_items(root, datalab)
    assert "site.yaml" in item


def test_golive_the_real_review_files_parse(tmp_path):
    """The repo's own files are in the form the parsers read: every row and verdict is seen."""
    legal = (ROOT / "docs" / "review" / "m16-legal.md").read_text("utf-8")
    assert not [i for i in srv._legal_open(legal) if "decision for the user is open" not in i]
    press = (ROOT / "docs" / "review" / "m16-press.md").read_text("utf-8")
    assert all(i.startswith("press row ") for i in srv._press_open(press))


def live_transport(seen: list[httpx.Request], *, port80=308, apex=200):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        host = request.url.host
        if request.url.scheme == "http":
            loc = f"https://{host}{request.url.raw_path.decode()}"
            return httpx.Response(port80, headers={"location": loc})
        if host.startswith("www."):
            return httpx.Response(308, headers={"location": "https://example.org/"})
        if request.url.path.startswith("/tiles/"):
            return httpx.Response(206, content=b"PMTiles")
        return httpx.Response(apex, headers={"cache-control": "public, max-age=3600"})

    return httpx.MockTransport(handler)


def test_live_verification_checks_port_80_answers_308_to_https():
    seen: list[httpx.Request] = []
    assert srv.verify_live("example.org", live_transport(seen)) == []
    http = [q for q in seen if q.url.scheme == "http"]
    assert {q.url.host for q in http} == {"example.org", "www.example.org", "velometer.example.org"}
    problems = srv.verify_live("example.org", live_transport([], port80=200))
    assert problems and all("308" in p for p in problems)


def test_live_verification_finds_a_site_still_locked():
    problems = srv.verify_live("example.org", live_transport([], apex=401))
    assert any("401" in p for p in problems)


def ssh_calls(runner: FakeRunner) -> list[str]:
    return [j for j in runner.joined() if j.startswith("ssh ")]


def writes(runner: FakeRunner) -> list[str]:
    """ssh calls that are more than the go-live check's reads (readlink and the digest)."""
    reads = ("readlink /srv/", "| LC_ALL=C sort -z | xargs -0 -r sha256sum")
    return [j for j in ssh_calls(runner) if not any(r in j for r in reads)]


LIVE = "1234abc-20261022T093005"


def digest_text(path: Path) -> str:
    return "".join(f"{h}  ./{p}\n" for p, h in srv.tree_digest(path).items())


def live_rules(site: Path | None, datalab: Path, *, velometer_text=None, datalab_text=None):
    """The server's answers: both `current` links and the digests of what they hold."""
    rules = []
    for name, path, text in (
        ("velometer", site, velometer_text),
        ("datalab", datalab, datalab_text),
    ):
        rules.append((f"readlink /srv/{name}/current", f"releases/{LIVE}\n"))
        body = text if text is not None else (digest_text(path) if path else "")
        rules.append((f"cd /srv/{name}/releases/{LIVE} && find", body))
    return rules


def test_unlock_needs_a_passing_golive_check(deps, tmp_path):
    root, datalab = golive_fixture(tmp_path, open_items=True)
    site = _export_with_repo(tmp_path)
    r = invoke("unlock", *HOST, "--domain", "example.org", "--datalab", str(datalab),
               "--site", str(site), "--root", str(root), input="yes\n")  # fmt: skip
    assert r.exit_code == 1
    assert writes(deps) == []


def test_unlock_needs_the_velometer_export(deps, tmp_path):
    root, datalab = golive_fixture(tmp_path, open_items=False)
    r = invoke("unlock", *HOST, "--domain", "example.org", "--datalab", str(datalab),
               "--root", str(root), input="yes\n")  # fmt: skip
    assert r.exit_code != 0
    assert "--site" in r.output
    assert deps.calls == []


@pytest.mark.parametrize("broken", ["private", "untagged"])
def test_unlock_stays_locked_when_the_exports_repo_links_do_not_resolve(
    deps, tmp_path, monkeypatch, broken
):
    """The repo probe runs on unlock: a 404 (private repo) or a commit without a pushed tag
    keeps the lock (M16, R45 I1/I2)."""
    root, datalab = golive_fixture(tmp_path, open_items=False)
    site = _export_with_repo(tmp_path)
    forge_status = 404 if broken == "private" else 200
    monkeypatch.setattr(
        srv.DEPS, "transport", httpx.MockTransport(lambda q: httpx.Response(forge_status))
    )
    deps.rules = [("ls-remote", "" if broken == "untagged" else TAGS)]
    r = invoke("unlock", *HOST, "--domain", "example.org", "--datalab", str(datalab),
               "--site", str(site), "--root", str(root), input="yes\n")  # fmt: skip
    assert r.exit_code == 1, r.output
    assert writes(deps) == []


def test_unlock_empties_the_lock_after_a_typed_yes_and_verifies(deps, tmp_path, monkeypatch):
    root, datalab = golive_fixture(tmp_path, open_items=False)
    site = _export_with_repo(tmp_path)
    seen: list[httpx.Request] = []
    monkeypatch.setattr(srv.DEPS, "transport", live_transport(seen))
    deps.rules = [
        ("ls-remote", TAGS),
        *live_rules(site, datalab),
        *server_state(dr.lock_text(HASH)),
    ]
    r = invoke("unlock", *HOST, "--domain", "example.org", "--datalab", str(datalab),
               "--site", str(site), "--root", str(root), input="yes\n")  # fmt: skip
    assert r.exit_code == 0, r.output
    assert any(q.url.host == "forge.example.org" for q in seen)  # the repo probe ran
    writes = [(a, i) for a, i in deps.calls if "lock.caddy" in " ".join(a) and i is not None]
    assert [i for _, i in writes] == [""]
    assert deps.index("lock.caddy") < deps.index("reload-or-restart caddy")


def test_unlock_does_nothing_without_a_typed_yes(deps, tmp_path, monkeypatch):
    root, datalab = golive_fixture(tmp_path, open_items=False)
    site = _export_with_repo(tmp_path)
    monkeypatch.setattr(srv.DEPS, "transport", httpx.MockTransport(lambda q: httpx.Response(200)))
    deps.rules = [("ls-remote", TAGS), *live_rules(site, datalab)]
    r = invoke("unlock", *HOST, "--domain", "example.org", "--datalab", str(datalab),
               "--site", str(site), "--root", str(root), input="\n")  # fmt: skip
    assert r.exit_code != 0
    assert writes(deps) == []


# --- stats (spec §4.4, ruling R3) -----------------------------------------------------------


def test_stats_writes_the_report_under_data_stats(deps):
    deps.rules = [("bash -s", "<!DOCTYPE html><html>report</html>")]
    r = invoke("stats", *HOST)
    assert r.exit_code == 0, r.output
    out = srv.STATS_DIR / "2026-10-22.html"
    assert out.read_text("utf-8").startswith("<!DOCTYPE html>")
    r2 = invoke("stats", *HOST)  # a second run the same day keeps the first
    assert r2.exit_code == 0
    assert sorted(p.name for p in srv.STATS_DIR.iterdir()) == [
        "2026-10-22-2.html",
        "2026-10-22.html",
    ]


def test_stats_dir_is_data_stats_in_the_repo():
    fresh = load_script("tools/server.py")  # a new module, untouched by the fixtures
    assert fresh.STATS_DIR == ROOT / "data" / "stats"


def test_stats_reads_14_days_of_live_and_rolled_logs_as_root(deps):
    deps.rules = [("bash -s", "<!DOCTYPE html>")]
    invoke("stats", *HOST)
    (argv, script) = deps.calls[deps.index("bash -s")]
    assert argv[0] == "ssh" and argv[-1] == "sudo bash -s"
    assert "/var/log/caddy/*.log" in script and "/var/log/caddy/*.log.gz" in script
    assert "zcat -f" in script
    assert "14 * 86400" in script
    assert "-p /etc/goaccess/velometer.conf" in script


def test_stats_refuses_an_answer_that_is_no_report(deps):
    deps.rules = [("bash -s", (1, ""))]
    r = invoke("stats", *HOST)
    assert r.exit_code != 0
    assert not srv.STATS_DIR.exists() or not any(srv.STATS_DIR.iterdir())


def test_goaccess_conf_ignores_hosts_and_credits_dbip():
    lines = [x.strip() for x in GOACCESS.read_text("utf-8").splitlines() if not x.startswith("#")]
    assert "ignore-panel HOSTS" in lines
    assert "log-format CADDY" in lines
    assert "geoip-database /var/lib/goaccess/dbip-country-lite.mmdb" in lines
    (title,) = [x for x in lines if x.startswith("html-report-title ")]
    assert "IP Geolocation by DB-IP (https://db-ip.com), CC BY 4.0" in title


# --- docs -----------------------------------------------------------------------------------


def test_deploy_doc_step_4_describes_the_tool_not_the_hand_copy():
    text = (ROOT / "docs" / "deploy.md").read_text("utf-8")
    hetzner = text.split("\n## 1. Hetzner", 1)[1].split("\n## 2.", 1)[0]
    step4 = hetzner.split("\n4. ", 1)[1]
    assert "uperseded" not in step4
    assert "tools/server.py deploy" in step4
    assert "releases/<build>/" in step4
    assert "mv -T" in step4
    assert "/srv/velometer/current/" not in step4  # no rsync into the live directory


# --- the repo links reach the repository (M16, R42 fix round) --------------------------------

REPO_SHA = "0123456789abcdef0123456789abcdef01234567"
FILE_URL = "https://forge.example.org/owner/velometer/blob/{commit}/{path}"
REPO_URL = "https://forge.example.org/owner/velometer"
TAGS = f"1111111111111111111111111111111111111111\trefs/tags/export-0123456\n{REPO_SHA}\trefs/tags/export-0123456^{{}}\n"  # noqa: E501


def _export_with_repo(tmp_path: Path, build: dict | None = None) -> Path:
    site = tmp_path / "velometer-export"
    site.mkdir(parents=True)
    build = build or {
        "commit_full": REPO_SHA,
        "site": {"repo_url": REPO_URL, "repo_file_url": FILE_URL},
    }
    (site / "build.json").write_text(json.dumps(build), encoding="utf-8")
    return site


def test_golive_manual_items_name_the_pushed_commit(tmp_path):
    """The rule: a manual line asks that the export's commit be readable at the repo."""
    root, datalab = golive_fixture(tmp_path, open_items=False)
    r = invoke("golive-check", "--datalab", str(datalab), "--root", str(root))
    manual = r.output.split("Manual confirmations", 1)[1]
    (line,) = [x for x in manual.splitlines() if "commit_full" in x]
    assert "repo.url" in line and "public" in line


@pytest.mark.parametrize(("status", "open_items"), [(200, 0), (404, 1)])
def test_golive_site_fetches_one_repo_link_at_the_exports_commit(
    deps, tmp_path, monkeypatch, status, open_items
):
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return httpx.Response(status)

    monkeypatch.setattr(srv.DEPS, "transport", httpx.MockTransport(handler))
    deps.rules = [("ls-remote", TAGS)]
    root, datalab = golive_fixture(tmp_path, open_items=False)
    site = _export_with_repo(tmp_path)
    r = invoke("golive-check", "--datalab", str(datalab), "--root", str(root), "--site", str(site))
    assert asked == [f"https://forge.example.org/owner/velometer/blob/{REPO_SHA}/pyproject.toml"]
    assert r.exit_code == open_items, r.output
    assert f"golive-check: {open_items} open item(s)" in r.output
    if open_items:
        assert "404, want 200" in r.output
        assert "0123456 pushed and publicly readable at repo.url" in r.output


def test_golive_site_without_repo_values_or_a_reachable_forge_is_open(tmp_path, monkeypatch):
    def down(request):
        raise httpx.ConnectError("no route", request=request)

    monkeypatch.setattr(srv.DEPS, "transport", httpx.MockTransport(down))
    (item,) = srv.repo_link_items(_export_with_repo(tmp_path), srv.DEPS.transport)
    assert "ConnectError" in item and "publicly readable" in item
    bare = _export_with_repo(tmp_path / "b", {"commit_full": REPO_SHA, "site": {}})
    (item,) = srv.repo_link_items(bare, httpx.MockTransport(_no_network))
    assert "no repo_file_url" in item


def test_golive_site_asks_the_remote_for_a_tag_on_the_exports_commit(deps, tmp_path):
    """I2 (R45): the pinned commit must carry a pushed tag, asked anonymously at repo_url."""
    site = _export_with_repo(tmp_path)
    deps.rules = [("ls-remote", TAGS)]
    assert srv.repo_tag_items(site) == []
    (argv, _) = deps.calls[deps.index("ls-remote")]
    assert argv[-1] == REPO_URL and "GIT_TERMINAL_PROMPT=0" in argv
    other = "2222222222222222222222222222222222222222\trefs/tags/export-old\n"
    deps.rules = [("ls-remote", other)]
    (item,) = srv.repo_tag_items(site)
    assert "no tag" in item and "0123456" in item and "deploy.md" in item
    deps.rules = [("ls-remote", (128, ""))]
    (item,) = srv.repo_tag_items(site)
    assert "exited 128" in item
    bare = _export_with_repo(tmp_path / "b", {"commit_full": REPO_SHA, "site": {}})
    (item,) = srv.repo_tag_items(bare)
    assert "no repo_url" in item


# --- go-live judges what is live (final review I1, M2) ----------------------------------------


def test_golive_a_build_without_a_stamp_or_with_a_stale_one_is_open(tmp_path):
    """The rule: the Datalab build must have been made from the settings golive-check reads."""
    root, datalab = golive_fixture(tmp_path, open_items=False)
    assert srv.golive_items(root, datalab) == []
    cfg = root / "sites" / "datalab" / "site.yaml"
    data = yaml.safe_load(cfg.read_text("utf-8"))
    data["operator"]["address"] = "Neue Straße 3\n10115 Berlin"  # set after the build
    cfg.write_text(yaml.safe_dump(data), "utf-8")
    (item,) = srv.golive_items(root, datalab)
    assert "stale build" in item
    (datalab / "build.json").unlink()
    (item,) = srv.golive_items(root, datalab)
    assert "no build stamp" in item


def _golive_host(root, datalab, site):
    return invoke("golive-check", "--datalab", str(datalab), "--site", str(site), "--root",
                  str(root), *HOST)  # fmt: skip


def _live_ok(deps, monkeypatch, tmp_path):
    root, datalab = golive_fixture(tmp_path, open_items=False)
    site = _export_with_repo(tmp_path)
    (site / "index.html").write_text("<p>v</p>\n", encoding="utf-8")
    monkeypatch.setattr(srv.DEPS, "transport", httpx.MockTransport(lambda q: httpx.Response(200)))
    return root, datalab, site


def test_golive_host_passes_when_both_live_releases_are_the_checked_directories(
    deps, tmp_path, monkeypatch
):
    root, datalab, site = _live_ok(deps, monkeypatch, tmp_path)
    deps.rules = [("ls-remote", TAGS), *live_rules(site, datalab)]
    r = _golive_host(root, datalab, site)
    assert r.exit_code == 0, r.output
    digests = [j for j in deps.joined() if "sha256sum" in j]
    assert [d.split(" && ")[0].split()[-1] for d in digests] == [
        f"/srv/datalab/releases/{LIVE}", f"/srv/velometer/releases/{LIVE}"
    ]  # fmt: skip


@pytest.mark.parametrize("change", ["changed", "missing", "extra", "stale stamp"])
@pytest.mark.parametrize("which", ["velometer", "datalab"])
def test_golive_host_refuses_a_live_release_that_differs(
    deps, tmp_path, monkeypatch, change, which
):
    root, datalab, site = _live_ok(deps, monkeypatch, tmp_path)
    local = site if which == "velometer" else datalab
    text = digest_text(local)
    if change == "changed":
        text = text.replace(srv.tree_digest(local)["index.html"], "0" * 64)
    elif change == "missing":
        text = "".join(x for x in text.splitlines(True) if not x.endswith("./index.html\n"))
    elif change == "extra":
        text += f"{'1' * 64}  ./old/page.html\n"
    else:  # the server holds the build from before a settings change: build.json differs
        assert "build.json" in text
        text = text.replace(srv.tree_digest(local)["build.json"], "2" * 64)
    deps.rules = [("ls-remote", TAGS), *live_rules(site, datalab, **{f"{which}_text": text})]
    r = _golive_host(root, datalab, site)
    assert r.exit_code == 1, r.output
    (line,) = [x for x in r.output.splitlines() if "the live release" in x]
    assert line.startswith(f"open: {which}: the live release {LIVE} is not {local}")


def test_golive_host_without_anything_deployed_or_without_site_is_open(deps, tmp_path, monkeypatch):
    root, datalab, site = _live_ok(deps, monkeypatch, tmp_path)
    deps.rules = [("ls-remote", TAGS), ("readlink", (1, ""))]
    r = _golive_host(root, datalab, site)
    assert r.exit_code == 1
    assert "datalab: cannot compare" in r.output and "velometer: cannot compare" in r.output
    deps.rules = live_rules(None, datalab)
    r = invoke("golive-check", "--datalab", str(datalab), "--root", str(root), *HOST)
    assert r.exit_code == 1
    assert "--host given without --site" in r.output


def test_unlock_refuses_when_the_live_release_is_not_the_checked_export(
    deps, tmp_path, monkeypatch
):
    """The review's scenario: a new export is checked, the old release is still live."""
    root, datalab, site = _live_ok(deps, monkeypatch, tmp_path)
    old = tmp_path / "old-export"
    old.mkdir()
    (old / "index.html").write_text("<p>old</p>\n", encoding="utf-8")
    deps.rules = [
        ("ls-remote", TAGS),
        *live_rules(site, datalab, velometer_text=digest_text(old)),
        *server_state(dr.lock_text(HASH)),
    ]
    r = invoke("unlock", *HOST, "--domain", "example.org", "--datalab", str(datalab),
               "--site", str(site), "--root", str(root), input="yes\n")  # fmt: skip
    assert r.exit_code == 1, r.output
    assert "velometer: the live release" in r.output
    assert writes(deps) == []


def test_the_digest_command_holds_only_the_guarded_release_path(deps):
    deps.rules = [("readlink /srv/velometer/current", "releases/$(reboot)\n")]
    with pytest.raises(srv.ServerError, match="not a release"):
        srv.live_digest(srv.Target("203.0.113.10"), "velometer")
    assert not [j for j in deps.joined() if "sha256sum" in j]


@pytest.mark.parametrize(
    "host", ["-oProxyCommand=touch /tmp/x", "deploy@203.0.113.10", "a b", "", "203.0.113.10;id"]
)
def test_a_host_that_is_no_address_or_name_stops_every_command(deps, host):
    for args in (("stats",), ("deploy", "tiles", "/nonexistent"), ("setup", "--domain", "e.org")):
        r = invoke(*args, "--host", host)
        assert r.exit_code == 1, (args, r.output)
        assert "not an IP address or a host name" in r.output
    assert deps.calls == []


@pytest.mark.parametrize("host", ["203.0.113.10", "2001:db8::1", "velometer.example.org", "vm"])
def test_addresses_and_host_names_are_hosts(host):
    assert srv.check_host(host) == host
