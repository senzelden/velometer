import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

from tests.test_app_base import rich  # noqa: F401  (`rich` is a fixture)
from tests.test_export import _export
from velometer.app import export

ROOT = Path(__file__).resolve().parents[1]
AXE = ROOT / "tools" / "axe"
HAS_CHROME = shutil.which("google-chrome") is not None or Path("/usr/bin/google-chrome").exists()
needs_chrome = pytest.mark.skipif(not HAS_CHROME, reason="needs Chrome")


@pytest.fixture(scope="module")
def rp():
    spec = importlib.util.spec_from_file_location("render_pass", ROOT / "tools" / "render_pass.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_axe_is_pinned_and_unchanged():
    version, sha, *_ = (AXE / "VERSION").read_text().split()
    assert version.count(".") == 2
    assert hashlib.sha256((AXE / "axe.min.js").read_bytes()).hexdigest() == sha
    assert "Mozilla Public License" in (AXE / "LICENSE").read_text()


def test_axe_is_never_served_or_exported(rich, tmp_path):  # noqa: F811
    # the export copies the app's static/ only; axe lives outside it
    app_dir = Path(export.__file__).parent
    assert not any(p.name.lower().startswith("axe") for p in (app_dir / "static").rglob("*"))
    for t in (app_dir / "templates").rglob("*"):
        if t.is_file():
            assert "axe" not in t.read_text().lower(), t
    out = tmp_path / "site"
    _export(rich, out, base="/velometer/")
    files = [p for p in out.rglob("*") if p.is_file()]
    assert files
    assert not [p for p in files if p.name.lower().startswith("axe")]


def test_page_urls_finds_every_exported_page(rp, tmp_path):
    for rel in ["index.html", "cities/index.html", "city/berlin/tiers/index.html", "404.html"]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("<html></html>")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x.csv").write_text("a")
    urls = rp.page_urls(tmp_path, "/velometer/")
    assert urls == ["/velometer/", "/velometer/cities", "/velometer/city/berlin/tiers"]


def test_page_urls_skips_fragments(rp, tmp_path):
    # a city panel is an HTML fragment loaded into a page, not a page to visit
    (tmp_path / "index.html").write_text("<!doctype html>\n<html lang='en'></html>")
    (tmp_path / "city" / "berlin" / "panel").mkdir(parents=True)
    (tmp_path / "city" / "berlin" / "panel" / "index.html").write_text('<div class="panel-frag">')
    assert rp.page_urls(tmp_path, "/velometer/") == ["/velometer/"]


def test_type_urls_keeps_berlin_and_the_first_city_with_other_tabs(rp):
    b = "/velometer/"
    urls = [b, b + "plans", b + "plans/berlin"]
    for slug, tabs in [
        ("amsterdam", ["", "/time"]),
        ("berlin", ["", "/time", "/counts"]),
        ("bordeaux", ["", "/time"]),
        ("paris", ["", "/time", "/counts"]),
    ]:
        urls += [f"{b}city/{slug}{t}" for t in tabs]
    kept = rp.type_urls(sorted(urls), b)
    cities = {u.split("/")[3] for u in kept if "/city/" in u}
    assert cities == {"berlin", "amsterdam"}
    assert {b, b + "plans", b + "plans/berlin", b + "city/berlin/counts"} <= set(kept)
    assert len(kept) == 3 + 3 + 2


# --- run rules that need no browser ---


def _site(tmp_path: Path, pages: dict[str, str]) -> Path:
    site = tmp_path / "velometer"
    for rel, body in pages.items():
        f = site / rel / "index.html" if rel else site / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width'><title>t</title>"
            "<link rel='icon' href='data:,'></head>"
            f"<body><main><h1>T</h1>{body}</main></body></html>"
        )
    return site


def test_zero_visits_fail_the_run(rp, tmp_path):
    site = _site(tmp_path, {"": "<p>x</p>"})
    out = tmp_path / "out"
    assert rp.main(["--site", str(site), "--out", str(out), "--widths", ""]) == 1
    assert json.loads((out / "results.json").read_text()) == []


def test_results_are_saved_when_a_visit_crashes(rp, tmp_path, monkeypatch):
    site = _site(tmp_path, {"": "<p>x</p>", "b": "<p>y</p>"})
    out = tmp_path / "out"
    monkeypatch.setattr(rp, "find_chrome", lambda path: path)
    monkeypatch.setattr(rp, "serve", lambda site, base: contextlib.nullcontext("http://x"))
    monkeypatch.setattr(rp, "chrome", lambda binary: contextlib.nullcontext("http://d"))
    calls = []

    def fake_visit(devtools, origin, url, theme, width, shots, base, flip=False):
        calls.append(url)
        if len(calls) > 1:
            raise RuntimeError("chrome went away")
        return rp.entry(url, theme, width, "page")

    monkeypatch.setattr(rp, "visit", fake_visit)
    args = ["--site", str(site), "--out", str(out), "--widths", "320", "--themes", "light"]
    with pytest.raises(RuntimeError):
        rp.main(args)
    assert [r["url"] for r in json.loads((out / "results.json").read_text())] == ["/velometer/"]


def test_a_missing_chrome_is_a_clear_error(rp, tmp_path, monkeypatch, capsys):
    site = _site(tmp_path, {"": "<p>x</p>"})
    missing = tmp_path / "no-chrome"
    args = ["--site", str(site), "--out", str(tmp_path / "out")]
    with pytest.raises(SystemExit) as e:
        rp.main([*args, "--chrome", str(missing)])
    assert e.value.code == 2
    assert f"Chrome not found or not executable: {missing}" in capsys.readouterr().err
    # the environment variable is the default
    monkeypatch.setenv("VELOMETER_CHROME", str(missing) + "-env")
    with pytest.raises(SystemExit):
        rp.main(args)
    assert f"{missing}-env" in capsys.readouterr().err


def test_stop_kills_a_child_that_ignores_terminate(rp):
    proc = subprocess.Popen(
        ["python3", "-c", "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN);"
         " print('ready', flush=True); time.sleep(60)"],
        stdout=subprocess.PIPE,
    )  # fmt: skip
    assert proc.stdout.readline().strip() == b"ready"
    rp.stop(proc, timeout=0.5)
    assert proc.returncode is not None and proc.returncode < 0


def test_open_tab_closes_the_tab_when_setup_fails(rp, monkeypatch):
    info = json.dumps({"webSocketDebuggerUrl": "ws://x", "id": "T1"}).encode()
    monkeypatch.setattr(rp.urllib.request, "urlopen", lambda req: io.BytesIO(info))
    closed = []

    class FakeTab:
        def __init__(self, devtools, ws_url, target_id):
            self.id = target_id

        def call(self, method, **params):
            if method.startswith("Emulation"):
                raise RuntimeError("emulation failed")
            return {}

        def close(self):
            closed.append(self.id)

    monkeypatch.setattr(rp, "Tab", FakeTab)
    with pytest.raises(RuntimeError):
        rp.open_tab("http://d", 320, "light")
    assert closed == ["T1"]


# --- runs in headless Chrome ---

WIDE = "x" * 120


def _run(rp, site, out, *extra):
    code = rp.main(["--site", str(site), "--out", str(out), *extra])
    return code, json.loads((out / "results.json").read_text())


@pytest.mark.slow
@needs_chrome
def test_overflow_reports_real_overflow_and_only_that(rp, tmp_path):
    prose_css = (
        "<style>.prose{max-width:200px}.prose table{display:block;overflow-x:auto;"
        "width:max-content;max-width:300px}</style>"
    )
    site = _site(
        tmp_path,
        {
            "": "<p>fine</p>",
            # a phone zooms a too-wide page out (innerWidth grows): compare with the layout width
            "wide": "<div style='width:500px'>wide</div>",
            "nowrap": f"<p style='width:150px;white-space:nowrap'>{WIDE}</p>",
            # nothing in the DOM to inspect spills, yet the box overflows: it is still reported
            "pseudo": "<style>.w::after{content:'" + WIDE + "';white-space:nowrap}</style>"
            "<p class='w' style='width:150px'></p>",
            "longword": f"<p style='width:150px'>{WIDE}</p>",
            "clipped": "<div style='width:150px;overflow:hidden'>"
            "<table style='width:600px'><tr><td>a</td></tr></table></div>",
            "exempt": "<p style='width:150px;white-space:nowrap;overflow:hidden;"
            f"text-overflow:ellipsis'>{WIDE}</p>"
            "<span style='position:absolute;width:1px;height:1px;overflow:hidden;"
            f"clip:rect(0 0 0 0);white-space:nowrap'>{WIDE}</span>"
            f"{prose_css}<article class='prose'><table><tr><td>{WIDE}</td></tr></table></article>",
        },
    )
    # the inline <style> is allowed: no CSP on this synthetic site
    code, res = _run(rp, site, tmp_path / "out", "--widths", "390", "--themes", "light")
    by = {r["url"]: r["overflow"] for r in res}
    assert by["/velometer/"] == []
    assert by["/velometer/exempt"] == [], by["/velometer/exempt"]
    assert by["/velometer/wide"][0].startswith(":root ("), by["/velometer/wide"]
    assert any(o.startswith("html > body > main > p") for o in by["/velometer/nowrap"])
    assert any(o.startswith("html > body > main > p") for o in by["/velometer/longword"])
    assert any(o.startswith("html > body > main > p.w") for o in by["/velometer/pseudo"])
    assert any("div" in o and "clipped" in o for o in by["/velometer/clipped"])
    assert code == 1


class _Blackhole:
    """A port that accepts connections and never answers: a request to it never finishes."""

    def __enter__(self):
        self.s = socket.socket()
        self.s.bind(("127.0.0.1", 0))
        self.s.listen(16)
        return self.s.getsockname()[1]

    def __exit__(self, *exc):
        self.s.close()


@pytest.mark.slow
@needs_chrome
def test_a_missing_page_and_a_load_that_never_fires_are_findings(rp, tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "LOAD_TIMEOUT", 2.0)
    with _Blackhole() as port:
        site = _site(
            tmp_path, {"": "<p>x</p>", "hang": f"<img alt='' src='http://127.0.0.1:{port}/x.png'>"}
        )
        pages = "/velometer/,/velometer/missing,/velometer/hang"
        code, res = _run(
            rp, site, tmp_path / "out", "--widths", "390", "--themes", "light", "--pages", pages
        )
    by = {r["url"]: r["errors"] for r in res}
    assert by["/velometer/"] == []
    assert any("document HTTP 404" in e for e in by["/velometer/missing"])
    assert any("load event did not fire" in e for e in by["/velometer/hang"])
    assert code == 1


@pytest.mark.slow
@needs_chrome
def test_interact_opens_audits_and_closes_the_city_panel(rp, rich, tmp_path):  # noqa: F811
    site = tmp_path / "velometer"
    _export(rich, site, base="/velometer/")
    _, res = _run(
        rp, site, tmp_path / "out", "--pages", "", "--interact", "--widths", "1280,390",
        "--themes", "light,dark",
    )  # fmt: skip
    assert [(r["kind"], r["theme"], r["width"]) for r in res] == [
        ("interact", "light", 1280),
        ("interact", "light", 390),
        ("interact", "dark", 1280),
        ("interact", "dark", 390),
    ]
    for r in res:
        assert r["errors"] == [], r["errors"]
        assert r["screenshot"] and Path(r["screenshot"]).is_file()
        assert isinstance(r["axe"], list)
