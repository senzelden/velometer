import datetime as dt
import logging

import pytest

from velometer import i18n
from velometer.report import methodology


def _write(d, en, de):
    (d / "en.yaml").write_text(en, encoding="utf-8")
    (d / "de.yaml").write_text(de, encoding="utf-8")


@pytest.fixture
def cat(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n, "CATALOGUE_DIR", tmp_path)
    i18n.catalogue.cache_clear()
    yield tmp_path
    i18n.catalogue.cache_clear()


def test_catalogues_ship_with_the_same_keys_placeholders_and_plurals():
    assert i18n.check_catalogues() == []


@pytest.mark.parametrize(
    "en,de,needle",
    [
        ("a.b: x\n", "a.c: y\n", "a.b"),
        ("a.b: '{n} km'\n", "a.b: '{m} km'\n", "placeholder"),
        ("a.b: {one: x, other: y}\n", "a.b: z\n", "plural"),
        ("A.b: x\n", "A.b: y\n", "key"),
    ],
)
def test_catalogue_rules_are_enforced(tmp_path, en, de, needle):
    _write(tmp_path, en, de)
    assert any(needle in p for p in i18n.check_catalogues(tmp_path))


def test_t_falls_back_to_english_once_and_never_shows_a_key(cat, caplog):
    _write(cat, "x.y: Hello {name}\nx.z: only en\n", "x.y: Hallo {name}\n")
    assert i18n.t("de", "x.y", name="Wien") == "Hallo Wien"
    with caplog.at_level(logging.WARNING):
        assert i18n.t("de", "x.z") == "only en"
        assert i18n.t("de", "x.z") == "only en"
    assert sum("x.z" in r.message for r in caplog.records) == 1
    with pytest.raises(KeyError):
        i18n.t("en", "x.missing")


def test_plural_forms_pick_by_count(cat):
    _write(cat, "n.c: {one: '{count} city', other: '{count} cities'}\n",
           "n.c: {one: '{count} Stadt', other: '{count} Städte'}\n")  # fmt: skip
    assert i18n.t("de", "n.c", count=1) == "1 Stadt"
    assert i18n.t("de", "n.c", count=3) == "3 Städte"


def test_t_markup_escapes_values_not_the_template(cat):
    _write(cat, "m.k: '<b>{x}</b>'\n", "m.k: '<b>{x}</b>'\n")
    assert str(i18n.t_markup("en", "m.k", x="<i>")) == "<b>&lt;i&gt;</b>"


@pytest.mark.parametrize(
    "v,spec,lang,out",
    [
        (1639.8, ",.1f", "en", "1,639.8"),
        (1639.8, ",.1f", "de", "1.639,8"),
        (-3.2, ",.1f", "de", "−3,2"),
        (-3.2, ",.1f", "en", "-3.2"),
        (1234567, ",d", "de", "1.234.567"),
        (None, ",.1f", "en", "n/a"),
        (None, ",.1f", "de", "k. A."),
    ],
)
def test_fmt(v, spec, lang, out):
    assert i18n.fmt(v, spec, lang) == out


def test_signed_and_percent():
    assert i18n.signed(3.2, "en") == "+3.2"
    assert i18n.signed(-3.2, "en") == "%+.1f" % -3.2
    assert i18n.signed(-3.2, "de") == "−3,2"
    assert i18n.signed(3.2, "de") == "+3,2"
    assert i18n.percent(12.3, "en") == "12.3%"
    assert i18n.percent(12.3, "de") == "12,3 %"


def test_months_and_dates():
    assert i18n.month_year("2026-10-03T00:00:00Z", "de") == "Okt. 2026"
    assert i18n.month_year("2026-10-03T00:00:00Z", "en") == "Oct 2026"
    assert i18n.month_year("2019-09", "en", short=False) == "September 2019"
    assert i18n.january(2026, "de") == "Jan. 2026"
    assert i18n.long_day(dt.date(2022, 1, 1), "en") == "1 January 2022"
    assert i18n.long_day(dt.date(2022, 1, 1), "de") == "1. Januar 2022"
    assert i18n.day(dt.date(2026, 10, 12), "en") == "2026-10-12"
    assert i18n.iso_day("2026-10-12", "de") == "12. Oktober 2026"
    assert i18n.and_list(["a", "b", "c"], "de") == "a, b und c"


@pytest.mark.parametrize("lang", ["en", "de"])
def test_methodology_formatters_delegate_and_keep_their_output(lang):
    d = dt.date(2022, 1, 1)
    assert methodology._day(d, lang) == {"en": "1 January 2022", "de": "1. Januar 2022"}[lang]
    assert methodology._month("2019-09", lang) == {"en": "September 2019",
                                                   "de": "September 2019"}[lang]  # fmt: skip
    assert methodology._day(d, lang) == i18n.long_day(d, lang)
    for v in (0, 1.5, 1639.8, 100000, 0.125):
        assert methodology._number(v, lang) == i18n.number_trimmed(v, lang)
    assert methodology.Lang is i18n.Lang and methodology.MONTHS is i18n.MONTHS


def test_german_required_only_for_the_shipped_tree(monkeypatch, tmp_path):
    monkeypatch.setattr(i18n, "GERMAN_CONTENT_REQUIRED", True)
    assert i18n.german_required(i18n.SHIPPED_CONTENT_DIR)
    assert not i18n.german_required(tmp_path)
