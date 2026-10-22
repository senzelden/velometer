"""M15, M16: the deploy dry run end to end, against real Caddy (Docker) and wrangler (npx).
Slow: needs Docker or npx and the network (an image pull, an npm fetch).

Caddy serves deploy/Caddyfile, the production file: the velometer export, the Datalab, the tile
fixture and the `www` redirect, unlocked (as after go-live), locked with a password made here, and
with the lock the server comes up with (ruling P4). Two runs with a broken copy of the Caddyfile
show that the probes see a lock that leaks and a log that keeps the client address.
"""

import secrets
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.helpers import load_script
from tests.test_app_base import build_rich
from tests.test_export import _content
from velometer import datalab
from velometer.app import export

pytestmark = pytest.mark.slow
dr = load_script("tools/deploy_dryrun.py")

ROOT = Path(__file__).parents[1]
TILES = ROOT / "tests" / "fixtures" / "tiles" / "berlin-z0-8.pmtiles"
COUNTER_CSV = ROOT / "tests" / "fixtures" / "datalab" / "all.csv"
SITE_VALUES = {
    "datalab": {
        "name": "Zählwerk Berlin Datalab",
        "url": "https://datalab.example.org/",
        "lang": "de",
    },
    "impressum_url": "https://datalab.example.org/impressum",
    "privacy_url": "https://datalab.example.org/datenschutz",
}


@pytest.fixture(scope="module")
def public_site(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("m15-dryrun")
    r = build_rich(tmp)
    db_path, cfg, maps, docs, plans = r
    (cfg / "site.yaml").write_text(
        yaml.safe_dump(SITE_VALUES, allow_unicode=True), encoding="utf-8"
    )
    out = tmp / "site"
    export.run_export(out, "/", db_path, cfg, maps, docs, _content(r), plans, False, public=True)
    return out


@pytest.fixture(scope="module")
def datalab_site(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("m16-datalab")
    counter = tmp / "velometer-export"
    (counter / "data").mkdir(parents=True)
    shutil.copy(COUNTER_CSV, counter / "data" / "all.csv")
    out = tmp / "datalab"
    datalab.build(datalab.load_config(), counter, out)
    return out


def _docker_ok() -> bool:
    return bool(shutil.which("docker")) and (
        subprocess.run(["docker", "info"], capture_output=True).returncode == 0
    )


@pytest.fixture
def caddy_args(public_site, datalab_site):
    if not _docker_ok():
        pytest.skip("Docker is not available")
    return [
        "--site", str(public_site), "--datalab", str(datalab_site), "--tiles", str(TILES),
        "--server", "caddy",
    ]  # fmt: skip


def test_caddy_serves_both_sites_unlocked_as_after_go_live(caddy_args, capsys):
    assert dr.main(caddy_args) == 0
    assert ", 0 problems" in capsys.readouterr().out


def test_caddy_locked_with_a_password_answers_401_everywhere_without_it(caddy_args, capsys):
    """Every path of both sites and www: 401 without the password, the content with it, each
    with Cache-Control: no-store (R26); a byte range 206, a malformed one 416; Caddy's error
    entries (DEBUG) and the access logs mask the client, keep no X-Forwarded-For (R25), and hold
    neither cookie, password nor its header."""
    password = secrets.token_urlsafe(16)  # made here, never stored
    assert dr.main([*caddy_args, "--lock", password, "--debug-log"]) == 0
    out = capsys.readouterr().out
    assert "(locked, user preview)" in out and ", 0 problems" in out


def test_caddy_with_the_default_lock_answers_401_to_everyone(caddy_args, capsys):
    assert dr.main([*caddy_args, "--lock-default"]) == 0
    out = capsys.readouterr().out
    assert "(locked for everyone)" in out and ", 0 problems" in out


def _broken(tmp_path, monkeypatch, old: str, new: str) -> None:
    text = dr.CADDYFILE.read_text(encoding="utf-8")
    assert old in text
    copy = tmp_path / "Caddyfile"
    copy.write_text(text.replace(old, new), encoding="utf-8")
    monkeypatch.setattr(dr, "CADDYFILE", copy)


def test_the_probes_see_the_default_lock_leak_without_the_order_rule(
    caddy_args, tmp_path, monkeypatch, capsys
):
    _broken(tmp_path, monkeypatch, "\torder respond after basic_auth\n", "")
    assert dr.main([*caddy_args, "--lock-default"]) == 1
    out = capsys.readouterr().out
    assert "problem: velometer /tiles/velometer.pmtiles" in out  # handle_path ran first
    assert "problem: www /:" in out  # redir ran first


def test_the_log_check_sees_an_unmasked_access_log(caddy_args, tmp_path, monkeypatch, capsys):
    text = dr.CADDYFILE.read_text(encoding="utf-8")
    snippet = text[text.index("(access_log) {") :]
    _broken(
        tmp_path,
        monkeypatch,
        snippet,
        snippet.replace("\t\t\t\trequest>remote_ip ip_mask 24 48\n", "", 1)
        .replace("\t\t\t\trequest>headers>X-Forwarded-For delete\n", "", 1)
        .replace("\t\t\t\trequest>headers>Cookie delete\n", "", 1),
    )
    assert dr.main(caddy_args) == 1
    out = capsys.readouterr().out
    for what in ("the client address", "the forged X-Forwarded-For"):
        assert f"problem: log velometer.log: holds {what} unmasked" in out
    # Caddy redacts the cookie's value itself; the rule is that the header is gone (and R25:
    # X-Forwarded-For too)
    assert "problem: log velometer.log: keeps the Cookie header" in out
    assert "problem: log velometer.log: keeps the X-Forwarded-For header" in out


def test_the_probes_see_a_locked_response_a_cache_may_keep(
    caddy_args, tmp_path, monkeypatch, capsys
):
    """Ruling R26: with the site's Cache-Control set unconditionally, it overrides the lock's
    no-store on the 401 and on the pages behind the password."""
    text = dr.CADDYFILE.read_text(encoding="utf-8")
    assert text.count('\t\t?Cache-Control "public, max-age=3600"\n') == 2
    copy = tmp_path / "Caddyfile"
    copy.write_text(text.replace("\t\t?Cache-Control", "\t\tCache-Control"), encoding="utf-8")
    monkeypatch.setattr(dr, "CADDYFILE", copy)
    assert dr.main([*caddy_args, "--lock", secrets.token_urlsafe(16)]) == 1
    out = capsys.readouterr().out
    assert "problem: velometer /: Cache-Control 'public, max-age=3600' while locked" in out
    assert "problem: /: header cache-control is 'public, max-age=3600', expected 'no-store'" in out


def test_the_log_check_sees_an_unmasked_default_logger(caddy_args, tmp_path, monkeypatch, capsys):
    """Caddy's own log (stderr, journald) carries error entries at DEBUG: without its own
    remote_ip mask they name the client."""
    text = dr.CADDYFILE.read_text(encoding="utf-8")
    default = text[: text.index("(access_log) {")]
    _broken(
        tmp_path,
        monkeypatch,
        default,
        default.replace("\t\t\t\trequest>remote_ip ip_mask 24 48\n", "", 1),
    )
    assert dr.main([*caddy_args, "--lock", "pw", "--debug-log"]) == 1
    out = capsys.readouterr().out
    assert "problem: log caddy output: holds the client address unmasked" in out
    assert "problem: log velometer.log" not in out  # the access logs keep their own mask


def test_wrangler_pages_dev_serves_the_export(public_site):
    if not shutil.which("npx"):
        pytest.skip("npx is not available")
    assert dr.main(["--site", str(public_site), "--server", "wrangler"]) == 0
