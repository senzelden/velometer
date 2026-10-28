"""M15: render_pass --url audits a server already running and starts no http.server."""

import contextlib
import re
from pathlib import Path

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
    monkeypatch.delenv("VELOMETER_PREVIEW_PASSWORD", raising=False)
    headers = []
    monkeypatch.setattr(rp, "wait_http", lambda url, *a, **k: headers.append(k.get("headers")))
    assert rp.main([*args, "--url", "http://localhost:8123", "--auth", "preview:pw"]) == 0
    assert headers == [{"Authorization": "Basic cHJldmlldzpwdw=="}]
    assert rp.AUTH == "Basic cHJldmlldzpwdw==" and rp.AUTH_ORIGIN == "http://localhost:8123"
    assert rp.main([*args, "--url", "http://localhost:8123"]) == 0
    assert rp.AUTH is None and headers[-1] is None


def test_without_auth_the_password_comes_from_the_environment(stubbed, monkeypatch):
    """Final review I2: the documented route keeps the password off the command line."""
    args, _ = stubbed
    monkeypatch.setenv("VELOMETER_PREVIEW_PASSWORD", "pw")
    assert rp.main([*args, "--url", "http://localhost:8123/"]) == 0
    assert rp.AUTH == "Basic cHJldmlldzpwdw=="  # preview:pw
    assert rp.AUTH_ORIGIN == "http://localhost:8123"
    assert rp.main(args) == 0  # no --url: nothing to authenticate to
    assert rp.AUTH is None and rp.AUTH_ORIGIN is None


def test_the_header_goes_to_the_origin_under_test_only():
    auth = ("https://velometer.example.org", "Basic abc")
    own = {"requestId": "1", "request": {"url": "https://velometer.example.org/tiles/x.pmtiles",
                                         "headers": {"Range": "bytes=0-6"}}}  # fmt: skip
    reply = rp.fetch_reply(own, auth)
    assert {"name": "Authorization", "value": "Basic abc"} in reply["headers"]
    assert {"name": "Range", "value": "bytes=0-6"} in reply["headers"]
    for url in (
        "https://elsewhere.example.net/a.js",
        "http://velometer.example.org/",  # another scheme is another origin
        "https://velometer.example.org.evil.net/",
        "https://velometer.example.org:8443/",
    ):
        reply = rp.fetch_reply({"requestId": "2", "request": {"url": url, "headers": {}}}, auth)
        assert reply == {"requestId": "2"}, url


def test_every_tab_intercepts_only_its_own_origin(monkeypatch):
    import io
    import json

    class FakeTab:
        def __init__(self, devtools, ws_url, target_id):
            self.calls = []
            self.auth = None

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
    monkeypatch.setattr(rp, "AUTH_ORIGIN", "https://velometer.example.org")
    tab = rp.open_tab("http://devtools", 1280, "light")
    calls = dict(tab.calls)
    assert "Network.setExtraHTTPHeaders" not in calls  # it would reach every host
    assert calls["Fetch.enable"] == {
        "patterns": [{"urlPattern": "https://velometer.example.org/*", "requestStage": "Request"}]
    }
    assert tab.auth == ("https://velometer.example.org", "Basic abc")
    monkeypatch.setattr(rp, "AUTH", None)
    calls = [m for m, _ in rp.open_tab("http://d", 1, "x").calls]
    assert "Fetch.enable" not in calls


def test_the_tab_answers_a_paused_request_and_keeps_other_events():
    class WS:
        def __init__(self):
            self.sent = []

        def send(self, text):
            self.sent.append(__import__("json").loads(text))

    t = rp.Tab.__new__(rp.Tab)
    t.ws, t.n, t.events, t._sent = WS(), 0, [], set()
    t.auth = ("https://a.example", "Basic abc")
    paused = {"requestId": "9", "request": {"url": "https://b.example/x", "headers": {}}}
    t._take({"method": "Fetch.requestPaused", "params": paused})
    (sent,) = t.ws.sent
    assert sent["method"] == "Fetch.continueRequest" and sent["params"] == {"requestId": "9"}
    t._take({"id": sent["id"], "result": {}})  # its reply is nobody's event
    t._take({"method": "Network.requestWillBeSent", "params": {}})
    assert [e.get("method") for e in t.events] == ["Network.requestWillBeSent"]


def test_waiting_for_the_server_never_forwards_the_header_on_a_redirect(monkeypatch):
    seen = []

    def urlopen(req, timeout):
        seen.append(req)
        return __import__("io").BytesIO()

    monkeypatch.setattr(rp.urllib.request, "urlopen", urlopen)
    rp.wait_http("https://a.example/", headers={"Authorization": "Basic abc"})
    (req,) = seen
    assert req.unredirected_hdrs == {"Authorization": "Basic abc"}
    assert "Authorization" not in req.headers


def test_readme_shots_take_the_password_from_the_environment(monkeypatch):
    rs = load_script("tools/readme_shots.py")
    monkeypatch.setenv("VELOMETER_PREVIEW_PASSWORD", "pw")
    monkeypatch.setattr(rs.rp, "running", lambda origin, base: pytest.fail("stop"))
    with pytest.raises(pytest.fail.Exception):
        rs.main(["--url", "https://velometer.example.org"])
    assert rs.rp.AUTH == "Basic cHJldmlldzpwdw=="
    assert rs.rp.AUTH_ORIGIN == "https://velometer.example.org"
    doc = Path(rs.__file__).read_text(encoding="utf-8")
    assert "--auth preview:" not in doc


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


def test_no_documented_command_puts_the_preview_password_on_its_command_line():
    """Final review I2: argv is world-readable (/proc/<pid>/cmdline) and lands in shell history."""
    root = Path(__file__).resolve().parents[1]
    on_argv = re.compile(
        r"--auth[ =]\S*:[\"<$]|--auth[ =]preview:|--lock[ =][<$\"]|--lock PASSWORD"
    )
    for rel in ("docs/deploy.md", "tools/README.md", "README.md", "tools/render_pass.py",
                "tools/readme_shots.py", "tools/deploy_dryrun.py", "tools/server.py"):  # fmt: skip
        text = (root / rel).read_text(encoding="utf-8")
        assert not on_argv.findall(text), rel
