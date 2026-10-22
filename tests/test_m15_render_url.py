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


# --- M16: --auth, through the locked dry run ----------------------------------------------------


def test_auth_needs_url_and_a_user_and_password(stubbed):
    args, _ = stubbed
    for bad in (["--auth", "preview:pw"], ["--url", "http://localhost:1", "--auth", "nocolon"]):
        with pytest.raises(SystemExit) as e:
            rp.main([*args, *bad])
        assert e.value.code == 2


def test_auth_is_sent_while_waiting_for_the_server(stubbed, monkeypatch):
    args, seen = stubbed
    headers = []
    monkeypatch.setattr(rp, "wait_http", lambda url, *a, **k: headers.append(k.get("headers")))
    assert rp.main([*args, "--url", "http://localhost:8123", "--auth", "preview:pw"]) == 0
    assert headers == [{"Authorization": "Basic cHJldmlldzpwdw=="}]
    assert rp.AUTH == "Basic cHJldmlldzpwdw=="
    assert rp.main([*args, "--url", "http://localhost:8123"]) == 0
    assert rp.AUTH is None and headers[-1] is None


def test_every_tab_sends_the_authorization_header(monkeypatch):
    import io
    import json

    class FakeTab:
        def __init__(self, devtools, ws_url, target_id):
            self.calls = []

        def call(self, method, **params):
            self.calls.append((method, params))
            return {}

        def close(self):
            pass

    info = json.dumps({"webSocketDebuggerUrl": "ws://x", "id": "1"}).encode()
    monkeypatch.setattr(rp, "Tab", FakeTab)
    monkeypatch.setattr(
        rp.urllib.request, "urlopen", lambda req: contextlib.nullcontext(io.BytesIO(info))
    )
    monkeypatch.setattr(rp, "AUTH", "Basic abc")
    calls = [m for m, _ in rp.open_tab("http://devtools", 1280, "light").calls]
    i = calls.index("Network.setExtraHTTPHeaders")
    assert i > calls.index("Network.enable")
    assert rp.open_tab("http://devtools", 390, "dark").calls[i][1] == {
        "headers": {"Authorization": "Basic abc"}
    }
    monkeypatch.setattr(rp, "AUTH", None)
    calls = [m for m, _ in rp.open_tab("http://d", 1, "x").calls]
    assert "Network.setExtraHTTPHeaders" not in calls


def test_the_url_host_is_the_sites_own_host(stubbed):
    args, _ = stubbed
    assert rp.main([*args, "--url", "http://velometer.localhost:8123"]) == 0
    assert rp.SITE_HOST == "velometer.localhost"
    assert rp.main([*args, "--url", "http://127.0.0.1:8123"]) == 0
    assert rp.SITE_HOST == "127.0.0.1"
    assert rp.main(args) == 0
    assert rp.SITE_HOST is None


def test_a_page_may_load_from_its_own_host_and_no_other(monkeypatch):
    r = {"errors": [], "axe": [], "overflow": [], "console": [], "csp": []}
    monkeypatch.setattr(rp, "SITE_HOST", "velometer.localhost")
    assert rp.failures(r | {"hosts": ["velometer.localhost", "127.0.0.1"]}) == []
    assert rp.failures(r | {"hosts": ["localhost"]}) == ["hosts localhost"]
    monkeypatch.setattr(rp, "SITE_HOST", None)
    assert rp.failures(r | {"hosts": ["velometer.localhost"]}) == ["hosts velometer.localhost"]
