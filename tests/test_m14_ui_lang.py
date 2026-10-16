"""M14 Task 4: an original national term inside a UI string carries `lang` through the same
`<i lang="xx">term</i>` mark content prose uses. Markup where markup is allowed, plain text
where only text is (attributes, the `#ui-strings` JSON, CSV, citations)."""

import glob
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml
from markupsafe import Markup, escape

from tests.test_app import setup  # noqa: F401 - the imported fixture
from velometer import i18n
from velometer.app.cite import cite_text
from velometer.app.narrative import TERM_MARK_RAW

ROOT = Path(__file__).resolve().parents[1]
TERMS_DOC = ROOT / "docs/review/m13-terms.md"
MARK = '<i lang="da">cykelsti</i>'


@pytest.fixture
def cat(tmp_path, monkeypatch):
    """A catalogue directory whose `figure.scope.cykelsti` is marked, as the shipped one is."""
    for lang in i18n.LANGS:
        doc = yaml.safe_load((i18n.CATALOGUE_DIR / f"{lang}.yaml").read_text(encoding="utf-8"))
        doc["figure.scope.cykelsti"] = f"{MARK} (kerbed cycle track)"
        (tmp_path / f"{lang}.yaml").write_text(
            yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8"
        )
    monkeypatch.setattr(i18n, "CATALOGUE_DIR", tmp_path)
    i18n.catalogue.cache_clear()
    yield tmp_path
    i18n.catalogue.cache_clear()


def test_t_markup_keeps_the_mark_and_t_gives_plain_text(cat):
    marked = i18n.t_markup("en", "figure.scope.cykelsti")
    assert isinstance(marked, Markup) and MARK in marked
    assert i18n.t("en", "figure.scope.cykelsti") == "cykelsti (kerbed cycle track)"
    assert i18n.plain(f"a {MARK} b") == "a cykelsti b"


def test_values_stay_escaped_and_only_the_template_is_stripped(cat):
    # a value that looks like a mark is data: `t` leaves it, `t_markup` escapes it
    fake = '<i lang="da">x</i>'
    en = yaml.safe_load((cat / "en.yaml").read_text(encoding="utf-8"))
    en["page.index.n_countries"] = f"{MARK} {{count}}"
    (cat / "en.yaml").write_text(yaml.safe_dump(en, allow_unicode=True), encoding="utf-8")
    i18n.catalogue.cache_clear()
    assert i18n.t("en", "page.index.n_countries", count=fake) == f"cykelsti {fake}"
    assert "&lt;i lang" in i18n.t_markup("en", "page.index.n_countries", count=fake)


def test_js_strings_are_plain(cat):
    en = yaml.safe_load((cat / "en.yaml").read_text(encoding="utf-8"))
    en["js.test_term"] = f"{MARK} here"
    (cat / "en.yaml").write_text(yaml.safe_dump(en, allow_unicode=True), encoding="utf-8")
    de = yaml.safe_load((cat / "de.yaml").read_text(encoding="utf-8"))
    de["js.test_term"] = "cykelsti hier"
    (cat / "de.yaml").write_text(yaml.safe_dump(de, allow_unicode=True), encoding="utf-8")
    i18n.catalogue.cache_clear()
    assert i18n.js_strings("en")["js.test_term"] == "cykelsti here"


@pytest.mark.parametrize(
    "bad",
    ['<i>cykelsti</i>', '<i lang="da">cykelsti', 'cykelsti</i>', "<i lang='da'>x</i>",
     '<i lang="da"><i lang="da">x</i></i>', '<i lang="Dansk!">x</i>'],
)  # fmt: skip
def test_check_catalogues_reports_a_malformed_mark(cat, bad):
    assert i18n.check_catalogues(cat) == []
    en = yaml.safe_load((cat / "en.yaml").read_text(encoding="utf-8"))
    en["figure.scope.cykelsti"] = f"{bad} (kerbed cycle track)"
    (cat / "en.yaml").write_text(yaml.safe_dump(en, allow_unicode=True), encoding="utf-8")
    i18n.catalogue.cache_clear()
    assert any("malformed mark" in p and "figure.scope.cykelsti" in p
               for p in i18n.check_catalogues(cat))  # fmt: skip


def test_other_catalogue_markup_is_not_a_malformed_mark(cat):
    # <b>, <code>, <a> are the catalogue's own markup, not marks
    assert i18n.check_catalogues(cat) == []


# --- every original term in a UI string is marked in its language ---------------------------


def _source_languages() -> dict[str, str]:
    out = {}
    for f in glob.glob(str(ROOT / "content/sources/*.yaml")):
        for s in yaml.safe_load(Path(f).read_text(encoding="utf-8"))["sources"]:
            out[s["id"]] = s["language"]
    return out


def _terms_by_language() -> dict[str, set[str]]:
    """{term: {language}} from the lookup table of docs/review/m13-terms.md. A cell holds
    several terms (`;` `,` `/`); a `(…)` is a gloss (or an optional ending: `Bezirke(n)` gives
    both forms). A row whose excerpt cell says "as X" takes row X's excerpts."""
    section = TERMS_DOC.read_text(encoding="utf-8").split("## Lookup for Task 7", 1)[1]
    rows = {}
    for line in section.splitlines():
        if line.startswith("| ") and not line.startswith(("| Hit", "|---")):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows[cells[0]] = cells
    langs = _source_languages()
    out: dict[str, set[str]] = {}
    for cells in rows.values():
        ids = re.findall(r"`([^`]+)`", cells[3])
        ref = re.match(r"as (\w+)", cells[3])
        if not ids and ref:
            ids = re.findall(r"`([^`]+)`", rows[ref.group(1)][3])
        found = {langs[i.split("/")[0]] for i in ids if i.split("/")[0] in langs}
        for cell in re.split(r"[;,]| / ", cells[2]):
            optional = re.search(r"(\w)\((\w+)\)", cell)
            forms = [re.sub(r"\(.*?\)", "", cell)]
            if optional:
                forms.append(re.sub(r"\((\w+)\)", r"\1", cell))
            for form in forms:
                if len(form.strip()) >= 3:
                    out.setdefault(form.strip(), set()).update(found)
    return out


def _values(cat: dict) -> list[tuple[str, str]]:
    return [
        (key, str(form))
        for key, value in cat.items()
        for form in (value.values() if isinstance(value, dict) else [value])
    ]


def test_the_term_table_is_parsed():
    terms = _terms_by_language()
    assert terms["cykelsti"] == {"da"} and terms["Bezirke"] == {"de"}
    assert terms["Bezirken"] == {"de"} and "kommunale veger" in terms


@pytest.mark.parametrize("lang", i18n.LANGS)
def test_every_original_term_in_a_ui_string_is_marked_in_its_language(lang):
    """A term of another language than the page's is inside `<i lang="xx">` with its own
    language. (A German term on a German page needs no mark: the page is German.)"""
    problems = []
    for term, term_langs in _terms_by_language().items():
        if not term_langs or term_langs == {lang}:
            continue
        word = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)
        for key, value in _values(i18n.catalogue(lang)):
            marks = list(TERM_MARK_RAW.finditer(value))
            for m in word.finditer(value):
                inside = [k for k in marks if k.start() <= m.start() and m.end() <= k.end()]
                if not inside or inside[0].group(1) not in term_langs:
                    problems.append(f"[{lang}] {key}: {term!r} not marked {sorted(term_langs)}")
    assert not problems, "\n".join(problems)


def test_mark_syntax_is_one_definition():
    from velometer.app.narrative import TERM_MARK, _open

    assert TERM_MARK_RAW.pattern.count(_open("i", escaped=False)) == 1
    assert TERM_MARK.search(escape('<i lang="da">x</i>')) and TERM_MARK_RAW.fullmatch(
        '<i lang="da">x</i>'
    )
    assert not TERM_MARK_RAW.fullmatch('<i lang="d a">x</i>')


# --- plain-text paths (Review Focus 3) ------------------------------------------------------


class _Attrs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values: list[str] = []
        self.text_only: list[str] = []  # script/style/title/textarea content
        self._in: str | None = None

    def handle_starttag(self, tag, attrs):
        self.values += [v for _k, v in attrs if v]
        self._in = tag if tag in {"script", "style", "title", "textarea"} else None

    def handle_endtag(self, tag):
        self._in = None

    def handle_data(self, data):
        if self._in:
            self.text_only.append(data)


def _assert_text_only_places_are_plain(url: str, body: str) -> None:
    p = _Attrs()
    p.feed(body)
    for v in p.values + p.text_only:
        assert "<i" not in v and "&lt;i" not in v, (url, v[:80])
    assert "&lt;i lang" not in body and "&lt;/i&gt;" not in body, url
    ui = re.search(r'id="ui-strings">(.*?)</script>', body, re.S)
    if ui:  # a panel is a fragment, without the block
        assert "<i" not in ui.group(1) and "\\u003ci" not in ui.group(1), url
        json.loads(ui.group(1))


def test_no_mark_leaks_into_attributes_json_or_text(page_site):
    for url, body in page_site.html.items():
        _assert_text_only_places_are_plain(url, body)


def test_ui_string_marks_render_as_markup_and_stay_out_of_attributes(setup):  # noqa: F811
    """The fixture site holds no figure with a marked scope, so add one: the Figures table
    shows the UI strings `figure.scope.cykelsti` and `figure.basis.streckenlaenge` (its `<td>`
    text, where the mark is wanted) beside attributes built from `t` (where it is not)."""
    from tests.test_app import CONTENT, _add_reported, _client
    from velometer.app.main import create_app

    db_path, cfg, maps, docs = setup
    _add_reported(db_path, network_scope="cykelsti", length_basis="streckenlaenge")
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        en = c.get("/city/berlin/figures").text
        de = c.get("/de/city/berlin/figures").text
        for url, body in (("/city/berlin/figures", en), ("/de/city/berlin/figures", de)):
            _assert_text_only_places_are_plain(url, body)
    assert '<i lang="da">cykelsti</i> (kerbed cycle track)' in en
    assert '<i lang="de">Streckenlänge</i> (route length)' in en
    assert '<i lang="da">Cykelsti</i> (Radweg)' in de
    assert '<i lang="de">Streckenlänge</i>' not in de  # a German word on a German page


def test_marked_ui_strings_are_plain_in_csv_labels_and_citations(cat, monkeypatch):
    """CSV labels and citations take `t`, so a mark in their catalogue strings comes out as the
    plain term (the shipped `subarea.remainder` is one such string)."""
    from velometer import config
    from velometer.app.cite import CiteFields

    assert "<i" not in config.remainder_label(12) and "Bezirke" in config.remainder_label(12)
    en = yaml.safe_load((cat / "en.yaml").read_text(encoding="utf-8"))
    en["cite.accessed"] = f"{MARK}: {{url}} (accessed {{accessed}})."
    (cat / "en.yaml").write_text(yaml.safe_dump(en, allow_unicode=True), encoding="utf-8")
    i18n.catalogue.cache_clear()
    f = CiteFields("T", "/p", "2026-10-03T00:00:00Z", None, "v1", "r1", "abc1234")
    text = cite_text(f, accessed="2026-10-16", url="https://x.example/p")
    assert "cykelsti: https://x.example/p" in text and "<i" not in text
