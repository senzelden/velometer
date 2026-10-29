"""The UI catalogue rules (M12 spec decision 2): no template text outside `t()`, every key the
code uses exists, every defined key is used, every id-built key family is declared and complete,
and the CLI's English constants equal the English catalogue."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

from velometer import i18n

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src/velometer/app/templates"
PY = list((ROOT / "src/velometer").rglob("*.py"))
HTML = list(TEMPLATES.rglob("*.html"))
# our modules only: the vendored third-party scripts (Leaflet) call their own `t("top")`
JS = [p for p in (ROOT / "src/velometer/app/static").rglob("*.js") if "vendor" not in p.parts]
ATTRS = {"aria-label", "title", "alt", "placeholder", "data-label"}
# brand and language-neutral symbols; a word here must read the same in both editions. The logo
# writes the brand in two halves (`velo<span>meter</span>`).
ALLOWED = {"velometer", "velo", "meter", "km", "m", "CSV", "PNG", "SVG", "JSON", "BibTeX", "CSL",
           "LAU", "FUA", "OSM", "A", "B", "C", "D", "E", "A+B", "ODbL", "n", "×", "·", "›", "▾",
           "→", "%"}  # fmt: skip
JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.S)
# a key written as a literal in a lookup: Python t(lang, "k") / t("en", "k"), Jinja t('k') /
# t_in('de', 'k'), JS t("js.k")
KEY_CALL = re.compile(
    r"""\bt(?:_in|_markup)?\(\s*(?:(?:['"](?:en|de)['"]|lang)\s*,\s*)?['"]([a-z][\w.]*)['"]"""
    r"""(?!\s*~)"""  # a Jinja 'prefix.' ~ id is composed (KEY_COMPOSED), not a key
)
# a key composed from an id: Python f"prefix.{x}", Jinja 'prefix.' ~ x, JS `prefix.${x}`
KEY_COMPOSED = re.compile(
    r"""\bt(?:_in|_markup)?\(\s*(?:(?:['"](?:en|de)['"]|lang)\s*,\s*)?"""
    r"""(?:f['"]([a-z][\w.]*\.)\{|['"]([a-z][\w.]*\.)['"]\s*~|`([a-z][\w.]*\.)\$\{)"""
)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        self.skip += tag in {"script", "style", "code", "pre"}
        self.found += [v for k, v in attrs if k in ATTRS and v]

    def handle_endtag(self, tag):
        self.skip -= tag in {"script", "style", "code", "pre"}

    def handle_data(self, data):
        if not self.skip:
            self.found.append(data)


def _words(text):
    return [w for w in re.findall(r"[^\W\d_][\w'’+-]*", text.replace("\x00", " "))
            if w not in ALLOWED]  # fmt: skip


def _read(paths):
    return {p: p.read_text(encoding="utf-8") for p in paths}


def test_no_template_has_literal_text():
    bad = []
    for path, text in _read(HTML).items():
        p = _Text()
        p.feed(JINJA.sub("\x00", text))
        bad += [f"{path.name}: {s.strip()!r}" for s in p.found if _words(s)]
    assert bad == []


def test_no_jinja_string_literal_of_two_or_more_words():
    lit = re.compile(r"""(['"])([A-Za-z][^'"{}]*\s[^'"{}]*)\1""")
    bad = []
    for path, text in _read(HTML).items():
        for block in re.findall(r"\{\{.*?\}\}|\{%.*?%\}", text, re.S):
            bad += [f"{path.name}: {m[1]!r}" for m in lit.findall(block) if len(m[1].split()) >= 2]
    assert bad == []


def _calls():
    texts = _read(PY + HTML + JS).values()
    called = {k for t_ in texts for k in KEY_CALL.findall(t_)}
    composed = {p for t_ in texts for m in KEY_COMPOSED.findall(t_) for p in m if p}
    return called, composed


def test_every_used_key_exists():
    called, _ = _calls()
    assert sorted(called - set(i18n.catalogue("en"))) == []


def test_every_composed_key_belongs_to_a_declared_family():
    # the JS month names are injected into the JS strings (js_strings), not catalogue keys
    _, composed = _calls()
    assert sorted(composed - set(i18n.DYNAMIC_FAMILIES) - set(i18n.JS_INJECTED)) == []


def test_every_defined_key_is_used():
    called, _ = _calls()
    family_keys = {f"{p}{i}" for p, ids in i18n.DYNAMIC_FAMILIES.items() for i in ids()}
    assert sorted(set(i18n.catalogue("en")) - called - family_keys) == []


def test_dynamic_families_are_complete():
    en = i18n.catalogue("en")
    missing = [f"{p}{i}" for p, ids in i18n.DYNAMIC_FAMILIES.items() for i in ids()
               if f"{p}{i}" not in en]  # fmt: skip
    assert missing == []


def test_cli_constants_equal_the_english_catalogue():
    from velometer.report import charts, data

    for t_, label in charts.TIER_LABEL.items():
        assert i18n.t("en", f"tier.{t_}") == label
    for rc, text in data.ROAD_CLASS_TEXT.items():
        assert i18n.t("en", f"road_class.{rc}") == text
    assert data.headline_unit("en") == data.HEADLINE_UNIT


def test_js_strings_fixture_is_generated_from_i18n():
    data = json.loads((ROOT / "tests/ui_js_strings.json").read_text(encoding="utf-8"))
    assert data == {lang: i18n.js_strings(lang) for lang in i18n.LANGS}


def test_js_months_come_from_i18n():
    for lang in i18n.LANGS:
        js = i18n.js_strings(lang)
        assert [js[f"js.month.short.{m}"] for m in range(1, 13)] == list(i18n.MONTHS_SHORT[lang])
        assert [js[f"js.month.long.{m}"] for m in range(1, 13)] == list(i18n.MONTHS[lang])
        assert not any(k.startswith(i18n.JS_INJECTED) for k in i18n.catalogue("en"))


def test_js_strings_are_every_js_key_english_underneath():
    en, de = i18n.catalogue("en"), i18n.catalogue("de")
    js_keys = {k for k in en if k.startswith("js.")}
    for lang, cat in (("en", en), ("de", de)):
        js = i18n.js_strings(lang)
        assert {k for k in js if not k.startswith(i18n.JS_INJECTED)} == js_keys
        assert all(js[k] == cat.get(k, en[k]) for k in js_keys)


def test_python_counter_label_keys_exist():
    from velometer.app import compare, counts

    en = i18n.catalogue("en")
    keys = [*compare.COUNTER_KEYS, *counts.LABEL_KEYS]  # the keys the constants are read from
    assert keys and all(k in en for k in keys)


def test_catalogues_agree():
    assert i18n.check_catalogues() == []


def test_german_values_differ_from_english_unless_the_same_word():
    """A German value equal to its English one is a missed translation, unless the text has no
    word that is English only (a name, an abbreviation, a symbol or a word both languages use)."""
    same_in_both = {
        "Bezirk",
        "Bezirke",
        "Index",
        "Status",
        "Name",
        "Plan",
        "Tier",
        "Link",
        "Region",
        "km",  # the unit, in both languages
    }
    en, de = i18n.catalogue("en"), i18n.catalogue("de")
    shared = [k for k in en if en[k] == de.get(k) and isinstance(en[k], str)]
    words = {}
    for k in shared:
        text = re.sub(r"\{[^}]*\}|<[^>]*>", " ", en[k])
        found = re.findall(r"[^\W\d_][\w'’+-]*", text)
        words[k] = [w for w in found if w not in same_in_both and not w.isupper() and len(w) > 1]
    # proper names and brand words that read the same in German
    names = {
        "velometer",
        "OpenStreetMap",
        "QECIO",
        "Clean",
        "Cities",
        "infraVelo",
        "Pilot",
        "Berlin",
        "Drucksache",
        "Protomaps",  # the basemap credit (M16)
        "WorldCover",
    }
    bad = {k: ws for k, ws in words.items() if [w for w in ws if w not in names]}
    assert bad == {}


# --- German change table (report/change.py bezirk_table) ------------------------------------

CHANGE_PAGE = ROOT / "docs/review/berlin_change_2023-01-01_current.md"


def _cells(table: str) -> list[list[str]]:
    return [[c.strip() for c in line.strip("|").split("|")] for line in table.splitlines()]


def test_german_bezirk_table_parses_back_to_the_english_values():
    from velometer.report.change import CATEGORIES, bezirk_table

    text = CHANGE_PAGE.read_text(encoding="utf-8")
    en, de = _cells(bezirk_table(text)), _cells(bezirk_table(text, "de"))
    assert len(en) == len(de) > 3
    assert de[0][1:] == [i18n.t("de", f"change.category.{c}") for c in CATEGORIES]
    assert en[1] == de[1]  # the alignment row
    for en_row, de_row in zip(en[2:], de[2:], strict=True):
        assert len(en_row) == len(de_row)
        for e, d in zip(en_row[1:], de_row[1:], strict=True):
            back = float(d.replace(".", "").replace(",", ".").replace(i18n.MINUS, "-"))
            assert back == float(e) and ("," in d) and "." not in e.split(".")[0]
    names = [r[0] for r in de]
    assert i18n.t("en", "subarea.remainder", n=12) in [r[0] for r in en]
    assert i18n.t("de", "subarea.remainder", n=12) in names
    assert i18n.t("en", "subarea.remainder", n=12) not in names
    assert bezirk_table(text) == bezirk_table(text, "en")


def test_the_english_remainder_label_glosses_the_original_term():
    # M13 G1 (user review): the original term first, its translation in brackets, as Task 7's UI
    # labels do ("Vorrangnetz (priority network)"); the gloss is the excerpt's, "the districts"
    # (`infravelo-organisation/responsibility`). German needs no gloss.
    en = i18n.t("en", "subarea.remainder", n=12)
    assert "12 Bezirke (districts)" in en
    assert "(districts)" not in i18n.t("de", "subarea.remainder", n=12)
