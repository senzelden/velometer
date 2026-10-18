"""M15: render_pass --url audits a server already running and starts no http.server."""

import contextlib

import pytest

from tests.helpers import load_script

rp = load_script("tools/render_pass.py")


@pytest.fixture
def stubbed(tmp_path, monkeypatch):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<html></html>", encoding="utf-8")
    seen = {"origins": [], "waited": []}
    monkeypatch.setattr(rp, "find_chrome", lambda path: "chrome")
    monkeypatch.setattr(rp, "chrome", lambda binary: contextlib.nullcontext("devtools"))
    monkeypatch.setattr(rp, "wait_http", lambda url, *a, **k: seen["waited"].append(url))
    monkeypatch.setattr(rp, "failures", lambda r: [])

    def visit(devtools, origin, url, theme, width, shots, base, flip=False):
        seen["origins"].append(origin)
        return {"url": url, "theme": theme, "width": width, "axe": [], "errors": []}

    monkeypatch.setattr(rp, "visit", visit)
    args = ["--site", str(site), "--base", "/", "--out", str(tmp_path / "out"),
            "--pages", "/", "--themes", "light", "--widths", "1280"]  # fmt: skip
    return args, seen


def test_url_audits_the_running_server_without_starting_one(stubbed, monkeypatch):
    args, seen = stubbed
    monkeypatch.setattr(rp, "serve", lambda *a, **k: pytest.fail("serve() ran despite --url"))
    assert rp.main([*args, "--url", "http://127.0.0.1:8123/"]) == 0
    assert seen["origins"] == ["http://127.0.0.1:8123"]
    assert seen["waited"] == ["http://127.0.0.1:8123/"]


def test_without_url_the_pass_serves_the_site_itself(stubbed, monkeypatch):
    args, seen = stubbed
    monkeypatch.setattr(rp, "serve", lambda site, base: contextlib.nullcontext("http://own:1"))
    assert rp.main(args) == 0
    assert seen["origins"] == ["http://own:1"]


@pytest.mark.parametrize("bad", ["127.0.0.1:8123", "http://127.0.0.1:8123/velometer/", "ftp://x"])
def test_url_must_be_an_origin(stubbed, bad):
    args, _ = stubbed
    with pytest.raises(SystemExit) as e:
        rp.main([*args, "--url", bad])
    assert e.value.code == 2
