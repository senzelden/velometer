"""M16 Task 6: the Zählwerk Berlin Datalab site (spec §4.5, §4.9 items 3 and 7).

The apex site is built from `sites/datalab/` and a finished velometer export: the Berlin counter
reads `data/all.csv`, so it cannot drift from velometer. Impressum and Datenschutz hold one
variant per operator form until the form is chosen (legal review 4.1-4.5, 5.1-5.9; fixes F8, F9,
F10, F14).
"""

import contextlib
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from tests.helpers import load_script
from velometer import datalab
from velometer.app.export import scan_references
from velometer.cli import app
from velometer.datalab import DatalabConfig, DatalabError, build, load_config, placeholders

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "datalab" / "all.csv"
SITE_YAML = ROOT / "sites" / "datalab" / "site.yaml"
PAGES = ("index.html", "impressum/index.html", "datenschutz/index.html", "404.html")
# the Berlin LAU tier A+B mapped km of the fixture, 2018-2026, rounded half up
BERLIN = {
    2018: 1640, 2019: 1612, 2020: 1634, 2021: 1677, 2022: 1494,
    2023: 1515, 2024: 1486, 2025: 1500, 2026: 1532,
}  # fmt: skip
FULL_PERSON = {
    "name": "Erika Mustermann",
    "address": "Musterstraße 1\n10115 Berlin",
    "email": "kontakt@example.org",
    "phone": None,
    "register": None,
    "vat": None,
    "responsible": "Erika Mustermann, Musterstraße 1, 10115 Berlin",
    "representative": None,
    "authority": "blnbdi",
    "mail_host": "Example Mail GmbH, Beispielweg 2, 20095 Hamburg",
}


def _export(tmp: Path, csv_text: str | None = None) -> Path:
    """A velometer export holding only what the Datalab build reads: `data/all.csv`."""
    export = tmp / "velometer-export"
    (export / "data").mkdir(parents=True)
    if csv_text is None:
        shutil.copy(FIXTURE, export / "data" / "all.csv")
    else:
        (export / "data" / "all.csv").write_text(csv_text, encoding="utf-8")
    return export


def _cfg(**over) -> DatalabConfig:
    base = {"domain": "example.org", "operator_form": None, "operator": {}, "contact_email": None}
    return DatalabConfig.model_validate({**base, **over})


def _person() -> DatalabConfig:
    return _cfg(operator_form="person", operator=FULL_PERSON, contact_email="hallo@example.org")


@pytest.fixture(scope="module")
def undecided(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("datalab-undecided")
    out = tmp / "out"
    build(_cfg(), _export(tmp), out)
    return out


@pytest.fixture(scope="module")
def person(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("datalab-person")
    out = tmp / "out"
    build(_person(), _export(tmp), out)
    return out


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict]] = []
        self.script_text: list[str] = []
        self._in_script = False

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        self._in_script = tag == "script"

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_script and data.strip():
            self.script_text.append(data)


def _tags(path: Path) -> _Tags:
    p = _Tags()
    p.feed(path.read_text(encoding="utf-8"))
    p.close()
    return p


def _series(index: Path) -> dict[int, int]:
    attrs = [a for t, a in _tags(index).tags if "data-series" in a]
    assert len(attrs) == 1
    pairs = (item.split(":") for item in attrs[0]["data-series"].split())
    return {int(y): int(km) for y, km in pairs}


def _shown_digits(index: Path, drums_id: str) -> str:
    """The digits a reader without JavaScript sees on the drums: each strip's `dN` class."""
    digits: dict[str, str] = {}
    current = None
    for _, a in _tags(index).tags:
        if (a.get("class") or "").startswith("drums"):
            current = a.get("id")
        m = re.fullmatch(r"strip d(\d)", a.get("class") or "")
        if m:
            digits[current] = digits.get(current, "") + m.group(1)
    return digits[drums_id]


# --- the counter reads the export --------------------------------------------------------------


def test_counter_values_come_from_the_export_csv(undecided):
    index = undecided / "index.html"
    assert _series(index) == BERLIN  # LAU only, years only (no `current`, no FUA, no Paris)
    assert _shown_digits(index, "km-drums") == "1532"
    assert _shown_digits(index, "yr-drums") == "2026"
    text = index.read_text(encoding="utf-8")
    assert "2018 bis 2026 abspielen" in text
    assert "Berlin 2026: 1.532 km" in text  # the live region's first reading


def test_changing_the_csv_changes_the_page(tmp_path):
    changed = FIXTURE.read_text(encoding="utf-8").replace(",1532.043,", ",1777.5,")
    assert changed != FIXTURE.read_text(encoding="utf-8")
    out = tmp_path / "out"
    build(_cfg(), _export(tmp_path, changed), out)
    index = out / "index.html"
    assert _series(index)[2026] == 1778  # rounded half up
    assert _shown_digits(index, "km-drums") == "1778"
    assert "Berlin 2026: 1.778 km" in index.read_text(encoding="utf-8")


def test_city_count_comes_from_the_export(undecided):
    assert "in 2 europäischen Städten" in (undecided / "index.html").read_text(encoding="utf-8")


def test_an_export_without_berlin_years_is_refused(tmp_path):
    text = "".join(
        line
        for line in FIXTURE.read_text(encoding="utf-8").splitlines(keepends=True)
        if not line.startswith("berlin,lau,20")
    )
    with pytest.raises(DatalabError, match="berlin"):
        build(_cfg(), _export(tmp_path, text), tmp_path / "out")


def test_an_export_without_all_csv_is_refused(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(DatalabError, match="all.csv"):
        build(_cfg(), tmp_path / "empty", tmp_path / "out")


def test_a_non_empty_out_is_refused(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("x")
    with pytest.raises(DatalabError, match="not empty"):
        build(_cfg(), _export(tmp_path), out)
    assert (out / "keep.txt").read_text() == "x"


# --- what the pages may load -------------------------------------------------------------------


@pytest.mark.parametrize("page", PAGES)
def test_no_inline_script_or_style(undecided, page):
    p = _tags(undecided / page)
    assert p.script_text == []
    assert all("src" in a for t, a in p.tags if t == "script")
    assert not any(t == "style" for t, _ in p.tags)
    assert not any("style" in a for _, a in p.tags)


def test_no_reference_to_another_host(undecided, person):
    assert scan_references(undecided, "/") == []
    assert scan_references(person, "/") == []


def test_fonts_referenced_exist_with_their_licences(undecided):
    css = (undecided / "static" / "datalab.css").read_text(encoding="utf-8")
    fonts = re.findall(r'url\("(fonts/[^"]+\.woff2)"\)', css)
    assert {Path(f).name for f in fonts} == {
        "MartianMono-Regular.woff2",
        "MartianMono-SemiBold.woff2",
        "PublicSans-Regular.woff2",
        "PublicSans-SemiBold.woff2",
    }
    for f in fonts:
        assert (undecided / "static" / f).read_bytes()[:4] == b"wOF2"
    licences = {
        "OFL-MartianMono.txt": "Copyright 2021 The Martian Mono Project Authors",
        "OFL-PublicSans.txt": "Copyright 2015 The Public Sans Project Authors",
    }
    for name, line in licences.items():
        text = (undecided / "static" / "fonts" / name).read_text(encoding="utf-8")
        assert text.startswith(line)
        assert "SIL OPEN FONT LICENSE Version 1.1" in text
        # ADR 0008: neither family declares a Reserved Font Name (it would follow the copyright)
        assert "with Reserved Font Name" not in text


def test_versions_pins_every_font_file():
    versions = (ROOT / "sites" / "datalab" / "VERSIONS").read_text(encoding="utf-8")
    shipped = sorted((ROOT / "sites" / "datalab" / "static" / "fonts").iterdir())
    assert shipped
    import hashlib

    for f in shipped:
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        assert f"{digest}  {f.name}" in versions, f.name


def test_no_site_file_is_executable():
    site = ROOT / "sites" / "datalab"
    executable = [p.name for p in site.rglob("*") if p.is_file() and p.stat().st_mode & 0o111]
    assert executable == []


def test_headers_carry_a_strict_policy(undecided):
    headers = (undecided / "_headers").read_text(encoding="utf-8")
    csp = re.search(r"Content-Security-Policy: (.*)", headers).group(1)
    assert "default-src 'self'" in csp
    assert "unsafe-inline" not in csp and "http" not in csp
    assert "frame-ancestors 'none'" in csp
    for page in PAGES:
        meta = [a for t, a in _tags(undecided / page).tags if a.get("http-equiv")]
        assert meta and meta[0]["content"].startswith("default-src 'self'")


def test_large_text_files_have_gz_siblings(undecided):
    assert (undecided / "datenschutz" / "index.html.gz").is_file()
    assert (undecided / "static" / "datalab.css.gz").is_file()


def test_build_returns_the_written_files(tmp_path):
    out = tmp_path / "out"
    written = build(_cfg(), _export(tmp_path), out)
    on_disk = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert written == on_disk
    assert set(PAGES) <= set(written)


# --- page furniture ----------------------------------------------------------------------------


@pytest.mark.parametrize("page", PAGES)
def test_every_page_is_german_with_the_footer(undecided, person, page):
    for out in (undecided, person):
        html = (out / page).read_text(encoding="utf-8")
        assert re.search(r'<html lang="de"', html)
        footer = re.search(r"<footer.*?</footer>", html, re.S).group(0)
        assert 'href="/impressum/"' in footer and ">Impressum<" in footer
        assert 'href="/datenschutz/"' in footer and ">Datenschutz<" in footer
        assert "Kontakt" in footer
    assert 'href="mailto:hallo@example.org"' in (person / page).read_text(encoding="utf-8")
    undecided_footer = re.search(
        r"<footer.*?</footer>", (undecided / page).read_text(encoding="utf-8"), re.S
    ).group(0)
    assert "[[" in undecided_footer and "mailto:" not in undecided_footer


def test_no_das_datalab_section(undecided):
    for page in PAGES:
        assert "Das Datalab" not in (undecided / page).read_text(encoding="utf-8")


def test_index_credits_the_data_it_shows(undecided):
    html = (undecided / "index.html").read_text(encoding="utf-8")
    assert 'href="https://www.openstreetmap.org/copyright"' in html
    assert "OpenStreetMap-Mitwirkende" in html
    assert "© EuroGeographics bezüglich der Verwaltungsgrenzen" in html
    assert "nicht gebaute" in html  # ADR 0006: mapped km


def test_domain_is_a_parameter(undecided):
    html = (undecided / "index.html").read_text(encoding="utf-8")
    assert 'href="https://velometer.example.org/"' in html
    impressum = (undecided / "impressum" / "index.html").read_text(encoding="utf-8")
    assert "example.org" in impressum and "velometer.example.org" in impressum
    for path in undecided.rglob("*"):
        if path.is_file() and path.suffix in (".html", ".css", ".js", "") and path.name != "":
            assert "zaehlwerk-datalab" not in path.read_text(encoding="utf-8", errors="replace")


# --- the 404 page and the favicon (rulings R21, R23) ------------------------------------------


def test_the_404_page_is_german_in_the_base_layout_with_a_link_home(undecided):
    html = (undecided / "404.html").read_text(encoding="utf-8")
    assert re.search(r"<title>Seite nicht gefunden · Zählwerk Berlin Datalab</title>", html)
    assert re.search(r"<h1>Seite nicht gefunden</h1>", html)
    assert '<a href="/">Zur Startseite</a>' in html
    assert 'href="/static/datalab.css"' in html  # base.html
    # served at whatever path was not found: every reference is absolute
    refs = [a.get("href") or a.get("src") for t, a in _tags(undecided / "404.html").tags]
    assert all(r.startswith(("/", "https://", "mailto:")) for r in refs if r)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_names_the_svg_favicon(undecided, page):
    icons = [a for t, a in _tags(undecided / page).tags if t == "link" and a.get("rel") == "icon"]
    assert icons == [{"rel": "icon", "href": "/static/favicon.svg", "type": "image/svg+xml"}]


def test_the_favicon_is_a_small_self_contained_svg(undecided):
    svg = (ROOT / "sites" / "datalab" / "static" / "favicon.svg").read_bytes()
    assert (undecided / "static" / "favicon.svg").read_bytes() == svg
    text = svg.decode("utf-8")
    assert text.startswith("<svg ") and 'xmlns="http://www.w3.org/2000/svg"' in text
    assert len(svg) < 2048
    # loads and runs nothing: no script, no link, no reference but the SVG namespace
    assert "<script" not in text and "href" not in text
    assert re.findall(r"https?://[^\s\"']+", text) == ["http://www.w3.org/2000/svg"]


# --- operator variants -------------------------------------------------------------------------

VARIANT_MARKS = {
    "person": "Privatperson",
    "verein": "Vereinsregister",
    "company": "Handelsregister",
}


def test_undecided_operator_renders_all_variants_with_placeholders(undecided):
    for page in ("impressum/index.html", "datenschutz/index.html"):
        html = (undecided / page).read_text(encoding="utf-8")
        for form, mark in VARIANT_MARKS.items():
            assert f'data-form="{form}"' in html, (page, form)
            assert mark in html
    found = placeholders(undecided)
    assert found
    assert all(re.fullmatch(r"[a-z0-9/]+\.html:\d+", f) for f in found)
    files = {f.split(":")[0] for f in found}
    assert files == set(PAGES)  # the footer contact is a placeholder everywhere


def test_placeholders_are_visible(undecided):
    html = (undecided / "impressum" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<span class="ph">\[\[Anschrift[^\]]*\]\]</span>', html)
    css = (undecided / "static" / "datalab.css").read_text(encoding="utf-8")
    assert re.search(r"\.ph\s*\{[^}]*outline", css)


def test_chosen_person_with_full_values_has_no_placeholder(person):
    assert placeholders(person) == []
    impressum = (person / "impressum" / "index.html").read_text(encoding="utf-8")
    assert 'data-form="person"' in impressum
    assert 'data-form="verein"' not in impressum and 'data-form="company"' not in impressum
    assert "Vereinsregister" not in impressum and "Handelsregister" not in impressum
    assert "Variante" not in impressum
    assert "Erika Mustermann" in impressum
    assert "Musterstraße 1<br>10115 Berlin" in impressum
    assert "Telefon" not in impressum  # optional, not given
    datenschutz = (person / "datenschutz" / "index.html").read_text(encoding="utf-8")
    assert 'data-form="verein"' not in datenschutz
    assert "Berliner Beauftragte für Datenschutz und Informationsfreiheit" in datenschutz
    assert "Example Mail GmbH" in datenschutz


def test_a_missing_required_value_stays_a_placeholder(tmp_path):
    values = {**FULL_PERSON, "responsible": None}
    cfg = _cfg(operator_form="person", operator=values, contact_email="hallo@example.org")
    out = tmp_path / "out"
    build(cfg, _export(tmp_path), out)
    found = placeholders(out)
    assert found and all(f.startswith("impressum/index.html:") for f in found)


def test_blank_values_count_as_not_given(tmp_path):
    values = {**FULL_PERSON, "name": "\n", "mail_host": " ", "phone": "  ", "vat": "\t"}
    cfg = _cfg(operator_form="person", operator=values, contact_email=" ")
    assert cfg.operator["name"] is None and cfg.contact_email is None
    out = tmp_path / "out"
    build(cfg, _export(tmp_path), out)
    found = placeholders(out)
    assert {f.split(":")[0] for f in found} == set(PAGES)  # the contact on every page
    impressum = (out / "impressum" / "index.html").read_text(encoding="utf-8")
    assert "[[Vor- und Nachname]]" in impressum  # a blank required value: a placeholder
    assert "Telefon" not in impressum and "Umsatzsteuer" not in impressum  # blank optional: out
    datenschutz = (out / "datenschutz" / "index.html").read_text(encoding="utf-8")
    assert "[[Anbieter des Postfachs" in datenschutz
    assert "mailto:" not in (out / "index.html").read_text(encoding="utf-8")


def test_values_are_escaped(tmp_path):
    values = {**FULL_PERSON, "name": "<script>x</script>"}
    out = tmp_path / "out"
    build(
        _cfg(operator_form="person", operator=values, contact_email="a@b.org"),
        _export(tmp_path),
        out,
    )
    html = (out / "impressum" / "index.html").read_text(encoding="utf-8")
    assert "<script>x" not in html and "&lt;script&gt;x" in html


# --- the legal facts the Datenschutzerklärung states (legal review 5.1-5.9) --------------------


def test_datenschutz_states_the_facts(undecided):
    html = (undecided / "datenschutz" / "index.html").read_text(encoding="utf-8")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    for fact in (
        "Hetzner Online GmbH",
        "Deutschland",
        "Art. 28 DSGVO",
        "letzten 8 Bit",  # IPv4 /24
        "letzten 80 Bit",  # IPv6 /48
        "Cookie",
        "Authorization",
        "täglich",
        "14 Tagen",
        "GoAccess",
        "DB-IP",
        "keine Cookies",
        "Let's Encrypt",
        "Art. 6 Abs. 1 lit. f DSGVO",
        "Art. 15",
        "Art. 21",
        "Art. 11 Abs. 2",
        "Beschwerde",
        "Datenschutzbeauftragt",
        "Stand:",
    ):
        assert fact in text, fact
    assert re.search(r"<h2[^>]*>\s*Widerspruchsrecht", html)  # set apart (Art. 21(4))
    assert "drittland" in text.lower() or "Drittland" in text
    assert "von einem anderen Anbieter" in text  # 5.9: nothing loaded from another host


def test_impressum_states_the_media_law_lines(undecided):
    html = (undecided / "impressum" / "index.html").read_text(encoding="utf-8")
    assert "§ 18 Abs. 2 MStV" in html
    assert "§ 5 DDG" in html
    assert "Diese Angaben gelten für example.org und velometer.example.org" in html
    assert "OFL-MartianMono.txt" in html and "OFL-PublicSans.txt" in html


# --- configuration -----------------------------------------------------------------------------


def test_site_yaml_is_undecided_with_the_default_domain():
    cfg = load_config(SITE_YAML)
    assert cfg.domain == "zaehlwerk-datalab.de"
    assert cfg.operator_form is None
    assert cfg.contact_email is None
    assert set(cfg.operator) == set(datalab.OPERATOR_KEYS)
    assert all(v is None for v in cfg.operator.values())


@pytest.mark.parametrize(
    "bad",
    [
        {"operator_form": "gmbh"},
        {"operator": {"nickname": "x"}},
        {"domain": "https://example.org/"},
        {"surprise": 1},
        {"contact_email": 3},
    ],
)
def test_config_is_strict(bad):
    with pytest.raises(ValidationError):
        _cfg(**bad)


def test_config_site_yaml_names_the_datalab_pages():
    text = (ROOT / "config" / "site.yaml").read_text(encoding="utf-8")
    assert "/impressum/" in text and "/datenschutz/" in text


def test_cli_builds(tmp_path):
    export = _export(tmp_path)
    out = tmp_path / "out"
    r = CliRunner().invoke(
        app,
        ["datalab", "build", "--velometer-export", str(export), "--out", str(out),
         "--config", str(SITE_YAML)],
    )  # fmt: skip
    assert r.exit_code == 0, r.output
    assert (out / "index.html").is_file()
    assert "placeholder" in r.output  # it says how many are left
    bad = CliRunner().invoke(
        app, ["datalab", "build", "--velometer-export", str(tmp_path / "nope"), "--out",
              str(tmp_path / "out2")],
    )  # fmt: skip
    assert bad.exit_code == 1
    assert "all.csv" in bad.output


# --- the render pass audits the Datalab as a German site ---------------------------------------


def test_render_pass_lang_option_sets_every_page_language(tmp_path, monkeypatch):
    rp = load_script("tools/render_pass.py")
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<html></html>", encoding="utf-8")
    seen = []
    monkeypatch.setattr(rp, "find_chrome", lambda path: "chrome")
    monkeypatch.setattr(rp, "chrome", lambda binary: contextlib.nullcontext("devtools"))
    monkeypatch.setattr(rp, "wait_http", lambda url, *a, **k: None)
    monkeypatch.setattr(rp, "failures", lambda r: [])
    monkeypatch.setattr(rp, "serve", lambda site, base: contextlib.nullcontext("http://own:1"))

    def visit(devtools, origin, url, theme, width, shots, base, flip=False):
        seen.append(rp.lang_of(url, base))
        return {"url": url, "theme": theme, "width": width, "axe": [], "errors": []}

    monkeypatch.setattr(rp, "visit", visit)
    args = ["--site", str(site), "--base", "/", "--out", str(tmp_path / "out"),
            "--pages", "/,/impressum", "--themes", "light", "--widths", "1280"]  # fmt: skip
    assert rp.main([*args, "--lang", "de"]) == 0
    assert seen == ["de", "de"]
    seen.clear()
    assert rp.main(args) == 0  # without it, velometer's rule: en outside /de
    assert seen == ["en", "en"]
    assert rp.lang_of("/de/cities", "/") == "de"
