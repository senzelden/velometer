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
    for rel in ["index.html", "cities/index.html", "city/berlin/tiers/index.html", "404.html",
                "de/index.html", "de/city/berlin/tiers/index.html"]:  # fmt: skip
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("<html></html>")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x.csv").write_text("a")
    urls = rp.page_urls(tmp_path, "/velometer/")
    assert urls == ["/velometer/", "/velometer/cities", "/velometer/city/berlin/tiers",
                    "/velometer/de", "/velometer/de/city/berlin/tiers"]  # fmt: skip


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


def test_type_urls_types_the_german_city_pages_too(rp):
    # the German twins are typed the same way: Berlin's tabs and the first city with other tabs,
    # never every German city page as an untyped one
    b = "/velometer/"
    urls = [b, b + "de", b + "de/plans"]
    for pre in ("", "de/"):
        for slug, tabs in [("amsterdam", ["", "/time"]), ("berlin", ["", "/time", "/counts"]),
                           ("bordeaux", ["", "/time"])]:  # fmt: skip
            urls += [f"{b}{pre}city/{slug}{t}" for t in tabs]
    kept = set(rp.type_urls(sorted(urls), b))
    de_cities = {u.split("/")[4] for u in kept if u.startswith(b + "de/city/")}
    assert de_cities == {"berlin", "amsterdam"}
    assert {b + "de", b + "de/plans", b + "de/city/berlin/counts", b + "de/city/amsterdam"} <= kept
    assert len(kept) == 3 + 2 * (3 + 2)


def test_lang_of_is_de_under_the_german_tree_only(rp):
    b = "/velometer/"
    assert [rp.lang_of(b + p, b) for p in ("de", "de/city/berlin", "de?x=1", "")] == ["de"] * 3 + [
        "en"
    ]
    assert rp.lang_of(b + "designs", b) == "en" and rp.lang_of(b + "city/de", b) == "en"


class _FakeTab:
    """Answers render-pass page scripts from a table: the expression's constant name -> value."""

    def __init__(self, rp, html="", lang="de", labels=(), fallback=0, frag=None, bad=()):
        self.answers = {
            "document.documentElement.outerHTML": html,
            "document.documentElement.getAttribute('lang')": lang,
            rp.LABELS_JS: list(labels),
            "document.querySelectorAll('[data-fallback]').length": fallback,
            rp.FRAGMENT_LANG_JS: frag,
            rp.ALTERNATES_JS: {"n": 2, "bad": list(bad)},
        }

    def js(self, expr, await_promise=False):
        return self.answers[expr]


def test_lang_checks_want_de_under_de_and_resolving_alternates(rp):
    b = "/velometer/"
    assert rp._lang_checks(_FakeTab(rp, lang="de"), b + "de/cities", b) == []
    assert rp._lang_checks(_FakeTab(rp, lang="en"), b + "cities", b) == []
    (wrong,) = rp._lang_checks(_FakeTab(rp, lang="en"), b + "de/cities", b)
    assert "<html lang> is 'en', want 'de'" in wrong
    (alt,) = rp._lang_checks(_FakeTab(rp, lang="en", bad=["/velometer/de/x (HTTP 404)"]), b, b)
    assert alt == "an alternate link does not resolve: /velometer/de/x (HTTP 404)"
    tab = _FakeTab(rp, lang="de", frag="en")
    (frag,) = rp._lang_checks(tab, b + "de/compare", b, fragment=True)
    assert "the panel fragment's lang is 'en', want 'de'" in frag
    assert rp._lang_checks(_FakeTab(rp, lang="de", frag="de"), b + "de/compare", b, True) == []


def test_english_leak_reads_text_labels_phrases_words_and_fallbacks(rp):
    phrase = rp._leak_phrases()[0]
    clean = '<html lang="de"><body><p>Deutscher Text</p><p lang="en">the English quote</p></body>'
    assert rp._english_leak(_FakeTab(rp, html=clean + "</html>"), "/de") == []
    leak = clean + f"<p>{phrase}</p></html>"
    errors = rp._english_leak(_FakeTab(rp, html=leak), "/de")
    assert any(f"English phrase on a German page: {phrase!r}" in e for e in errors), errors
    (words,) = rp._english_leak(_FakeTab(rp, html=clean, labels=["Download the chart"]), "/de")
    assert "English words on a German page: Download" not in words and "the" in words
    (fb,) = rp._english_leak(_FakeTab(rp, html=clean, fallback=2), "/de")
    assert "2 element(s) marked data-fallback" in fb


def test_csv_errors_want_the_german_header_and_dot_decimals(rp):
    pre = "# Map data © OpenStreetMap contributors, ODbL 1.0 — OSM mapped km\r\n# x\r\n"
    head = ["Stand", "A baulich getrennter Radweg"]
    good = pre + 'Stand,A baulich getrennter Radweg\r\n"Jan. 2019",12.5\r\n'
    assert rp._csv_errors(good, head, "de") == []
    assert rp._csv_errors(good.replace("# Map", "# Karte"), head, "de")  # the English preamble
    english = pre + "Snapshot,A separated track\r\n2019,12.5\r\n"
    assert any("not the table's" in e for e in rp._csv_errors(english, head, "de"))
    comma = pre + 'Stand,A baulich getrennter Radweg\r\n2019,"12,5"\r\n'
    assert any("dot-decimal" in e for e in rp._csv_errors(comma, head, "de"))
    assert rp._csv_errors(english, None, "en") == []


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


def _stamped_german_explanations(docs: Path) -> None:
    """A stamped German twin of the fixture's flagged-year explanations, as the shipped docs
    have one: without it the German Over time tab shows English (data-fallback)."""
    from velometer import timeseries as ts

    en = docs / "review" / "m3_timeseries.md"
    de = ts.german_explanations(en)
    de.write_text(
        "# M3 Zeitreihe\n\n## Erklärungen\n\n### berlin/lau/2025\n\nFixture-Ursache: ein "
        "Ausschlag von 50 Bearbeitungen.\n\n### paris/lau/2020\n\nKein Fixture-Hinweis.\n"
    )
    assert ts.stamp_explanations(en, de) == 2


@pytest.mark.slow
@needs_chrome
def test_interact_opens_audits_and_closes_the_city_panel(rp, rich, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(rp, "DE_SEARCH", ("berlin", "de/city/berlin"))  # the fixture's cities
    _stamped_german_explanations(rich[3])
    site = tmp_path / "velometer"
    _export(rich, site, base="/velometer/")
    _, res = _run(
        rp, site, tmp_path / "out", "--pages", "", "--interact", "--widths", "1280,390",
        "--themes", "light,dark",
    )  # fmt: skip
    # --interact runs, per theme and width, the city panel and the M11 cite, download and
    # permalinks visits, in English and (M12) in German, and the German search and switch;
    # every one must come back without an error
    visits = ["(city panel)", "(cite)", "(download)", "permalinks", "(search, switch)"]
    pages = [*visits, "/de/" + "(cite)", "/de/" + "(download)", "/de/" + "permalinks"]
    want = [(v, th, w) for v in pages for th in ("light", "dark") for w in (1280, 390)]

    def kind(url):
        v = next(v for v in visits if v in url)
        return "/de/" + v if "/de/city/" in url or url.endswith("/de/permalinks") else v

    got = [(kind(r["url"]), r["theme"], r["width"]) for r in res]
    assert sorted(got) == sorted(want)
    for r in res:
        assert r["errors"] == [], (r["url"], r["theme"], r["width"], r["errors"])
        if "steps" in r:  # the German search and switch: steps, no page audit
            assert r["steps"] and all(x.startswith("ok") for x in r["steps"]), r["steps"]
            continue
        assert r["screenshot"] and Path(r["screenshot"]).is_file(), r["url"]
        assert isinstance(r["axe"], list)


def test_key_params_send_a_real_key_press(rp):
    down, up = rp.key_params("Tab", True), rp.key_params("Tab", False)
    assert (down["type"], up["type"]) == ("keyDown", "keyUp")
    assert down["windowsVirtualKeyCode"] == 9 and down["modifiers"] == 0
    assert rp.key_params("Tab", True, shift=True)["modifiers"] == 8
    assert rp.key_params("+", True)["windowsVirtualKeyCode"] == 187  # what Leaflet zooms on
    assert "text" in rp.key_params(" ", True) and "text" not in rp.key_params(" ", False)


def test_a_failed_keyboard_step_fails_the_run(rp, tmp_path, monkeypatch):
    site = _site(tmp_path, {"": "<p>x</p>"})
    monkeypatch.setattr(rp, "find_chrome", lambda path: path)
    monkeypatch.setattr(rp, "serve", lambda site, base: contextlib.nullcontext("http://x"))
    monkeypatch.setattr(rp, "chrome", lambda binary: contextlib.nullcontext("http://d"))
    failing = {"light": ["compare: Escape closes it: focus lost"], "dark": []}

    def fake_keyboard(devtools, origin, base, theme):
        r = rp.entry(base, theme, 1280, "keyboard", errors=failing[theme])
        return r | {"steps": ["ok   a", *[f"FAIL {e}" for e in failing[theme]]]}

    monkeypatch.setattr(rp, "keyboard", fake_keyboard)
    out = tmp_path / "out"
    args = ["--site", str(site), "--out", str(out), "--pages", "", "--keyboard"]
    assert rp.main(args) == 1
    res = json.loads((out / "results.json").read_text())
    assert [(r["kind"], r["theme"]) for r in res] == [("keyboard", "light"), ("keyboard", "dark")]
    assert res[0]["steps"][-1].startswith("FAIL") and res[1]["errors"] == []
    failing["light"] = []
    assert rp.main(args) == 0


@pytest.mark.parametrize("step", ["cite", "download", "permalink"])
def test_a_failed_cite_download_or_permalink_step_fails_the_run(rp, tmp_path, monkeypatch, step):
    site = _site(tmp_path, {"": "<p>x</p>"})
    monkeypatch.setattr(rp, "find_chrome", lambda path: path)
    monkeypatch.setattr(rp, "serve", lambda site, base: contextlib.nullcontext("http://x"))
    monkeypatch.setattr(rp, "chrome", lambda binary: contextlib.nullcontext("http://d"))
    failing = [True]

    def fake(devtools, origin, base, theme, width, shots, lang="en"):
        return rp.entry(base + step, theme, width, "interact",
                        errors=["step failed"] if failing[0] else [])  # fmt: skip

    ok = lambda *a, **k: rp.entry("x", "light", 1280, "interact")  # noqa: E731
    for name in ("interact", "interact_cite", "interact_download", "interact_permalink"):
        monkeypatch.setattr(rp, name, ok)
    monkeypatch.setattr(rp, "_de_search", lambda *a: None)
    monkeypatch.setattr(rp, "_de_switch", lambda *a: None)
    monkeypatch.setattr(rp, f"interact_{step}", fake)
    args = ["--site", str(site), "--out", str(tmp_path / "out"), "--pages", "", "--interact"]
    args += ["--themes", "light", "--widths", "1280"]
    assert rp.main(args) == 1
    failing[0] = False
    assert rp.main(args) == 0


@pytest.mark.parametrize("part", ["cite", "download", "permalink", "search", "switch"])
def test_a_failed_german_interaction_fails_the_run(rp, tmp_path, monkeypatch, part):
    site = _site(tmp_path, {"": "<p>x</p>"})
    monkeypatch.setattr(rp, "find_chrome", lambda path: path)
    monkeypatch.setattr(rp, "serve", lambda site, base: contextlib.nullcontext("http://x"))
    monkeypatch.setattr(rp, "chrome", lambda binary: contextlib.nullcontext("http://d"))
    failing = [True]
    langs = []

    def visit_kind(name):
        def run(devtools, origin, base, theme, width, shots, lang="en"):
            langs.append((name, lang))
            bad = failing[0] and name == part and lang == "de"
            return rp.entry(base + name, theme, width, "interact", errors=["no"] if bad else [])

        return run

    def step(name):
        def run(devtools, origin, base, theme, width, st):
            st.check(f"de {name}", "failed" if failing[0] and name == part else None)

        return run

    monkeypatch.setattr(rp, "interact", lambda *a, **k: rp.entry("x", "light", 1280, "interact"))
    for name in ("cite", "download", "permalink"):
        monkeypatch.setattr(rp, f"interact_{name}", visit_kind(name))
    monkeypatch.setattr(rp, "_de_search", step("search"))
    monkeypatch.setattr(rp, "_de_switch", step("switch"))
    out = tmp_path / "out"
    args = ["--site", str(site), "--out", str(out), "--pages", "", "--interact"]
    args += ["--themes", "light", "--widths", "1280"]
    assert rp.main(args) == 1
    # the German cite, download and permalink visits run in German beside the English ones
    assert {("cite", "de"), ("download", "de"), ("permalink", "de")} <= set(langs)
    last = json.loads((out / "results.json").read_text())[-1]
    assert last["url"].endswith("de (search, switch)") and len(last["steps"]) == 2
    failing[0] = False
    assert rp.main(args) == 0


@pytest.mark.slow
@needs_chrome
def test_keyboard_pass_runs_every_step_with_real_keys(rp, rich, tmp_path):  # noqa: F811
    site = tmp_path / "velometer"
    _export(rich, site, base="/velometer/")
    code, res = _run(rp, site, tmp_path / "out", "--pages", "", "--keyboard", "--themes", "light")
    (r,) = res
    assert r["kind"] == "keyboard" and r["errors"] == [], r["steps"]
    for needle in (
        "skip link",
        "phone menu",
        "city tabs",
        "compare: Escape",
        "sort button",
        "chart view",
        "search 1280px: typing opens the list with the first city first",
        "search 1280px: Down moves aria-activedescendant",
        "search 1280px: Enter lands on the first city page",
        "search 1280px: Enter lands on the second city page",
        "search 320px: zzz offers the No match option",
        "search 1280px: axe finds nothing with the list open",
    ):
        lines = [x for x in r["steps"] if needle in x]
        assert lines and all(x.startswith("ok") for x in lines), (needle, lines)
    assert code == 0


def test_a_page_visit_runs_the_language_checks_and_the_leak_step_on_german_pages(
    rp, tmp_path, monkeypatch
):
    class Tab:
        events: list = []

        def pump(self, s):
            pass

        def js(self, expr, await_promise=False):
            return []

        def close(self):
            pass

    monkeypatch.setattr(rp, "open_tab", lambda devtools, width, theme: Tab())
    monkeypatch.setattr(rp, "navigate", lambda t, url: [])
    monkeypatch.setattr(rp, "screenshot", lambda t, path, width: str(path))
    monkeypatch.setattr(rp, "audit", lambda t: [])
    monkeypatch.setattr(rp, "_lang_checks", lambda t, url, base, fragment=False: [f"lang {url}"])
    monkeypatch.setattr(rp, "_english_leak", lambda t, url: [f"leak {url}"])
    b = "/velometer/"
    de = rp.visit("d", "o", b + "de/cities", "light", 1280, tmp_path, b)
    assert de["errors"] == [f"lang {b}de/cities", f"leak {b}de/cities"]
    en = rp.visit("d", "o", b + "cities", "light", 1280, tmp_path, b)
    assert en["errors"] == [f"lang {b}cities"]  # no leak step on an English page
