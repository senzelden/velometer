"""The base-path helper (`app/urls.py`) and the CSP meta tag's policy (M9 spec decisions 3, 6)."""

import json
from pathlib import Path

import pytest

from velometer.app import urls
from velometer.app.main import CSP, csp_meta
from velometer.app.urls import make_data_u, make_u, normalise_base

# shared with static/js/tests/base.test.mjs, so the two helpers agree
CASES = json.loads((Path(__file__).parent / "url_cases.json").read_text(encoding="utf-8"))
NORMALISE = [tuple(c) for c in CASES["normalise"]]  # (base as given, normalised)
EMIT = [tuple(c) for c in CASES["emit"]]  # (base, path, emitted URL)
UNTOUCHED = CASES["untouched"]  # URLs that are not ours: unchanged under any base
RELATIVE = CASES["relative"]  # paths u() refuses
EMIT_LANG = [tuple(c) for c in CASES["emit_lang"]]  # (base, lang, page path, emitted URL)
EMIT_DATA = [tuple(c) for c in CASES["emit_data"]]  # (base, lang|None, path, URL | "error")
DATA_ROOTS = ("data", "maps", "static")  # first path segments that only data_u emits
HEADER_ONLY = {"frame-ancestors", "report-uri", "report-to", "sandbox"}


def _directives(policy: str) -> dict[str, str]:
    out = {}
    for part in policy.split(";"):
        if part.strip():
            name, _, value = part.strip().partition(" ")
            out[name] = value
    return out


@pytest.mark.parametrize(("base", "expected"), NORMALISE)
def test_normalise_base(base, expected):
    assert normalise_base(base) == expected


@pytest.mark.parametrize(("base", "path", "expected"), EMIT)
def test_u_prefixes_the_base_and_keeps_query_and_fragment(base, path, expected):
    # one shared table for the JS url(); in Python a data, map or static path is data_u's
    if path.split("/")[1] in DATA_ROOTS:
        assert make_data_u(base)(path) == expected
    else:
        assert make_u(base)(path) == expected


@pytest.mark.parametrize(("base", "lang", "path", "expected"), EMIT_LANG)
def test_u_of_a_language_puts_its_prefix_after_the_base(base, lang, path, expected):
    assert make_u(base, lang)(path) == expected


@pytest.mark.parametrize(("base", "lang", "path", "expected"), EMIT_DATA)
def test_data_u_takes_data_paths_and_a_language_only_where_one_exists(base, lang, path, expected):
    data_u = make_data_u(base)
    if expected == "error":
        with pytest.raises(ValueError):
            data_u(path, lang)
    else:
        assert data_u(path, lang) == expected


@pytest.mark.parametrize("path", ["/data/x", "/maps/berlin_lau.png", "/static/app.css"])
@pytest.mark.parametrize("lang", ["en", "de"])
def test_u_refuses_data_map_and_static_paths(lang, path):
    with pytest.raises(ValueError):
        make_u("/velometer/", lang)(path)


@pytest.mark.parametrize(
    ("path", "lang", "stripped"),
    [
        ("/de", "de", "/"),
        ("/de/", "de", "/"),
        ("/de?x=1", "de", "/?x=1"),
        ("/de/city/berlin", "de", "/city/berlin"),
        ("/de/compare?c=berlin#t", "de", "/compare?c=berlin#t"),
        ("/methodology/de", "de", "/methodology"),
        ("/denmark", "en", "/denmark"),
        ("/", "en", "/"),
        ("/city/berlin", "en", "/city/berlin"),
    ],
)
def test_lang_of_and_strip_lang(path, lang, stripped):
    assert urls.lang_of(path) == lang
    assert urls.strip_lang(path) == stripped


@pytest.mark.parametrize(
    ("path", "de"),
    [("/", "/de/"), ("/cities?x=1", "/de/cities?x=1"), ("/de/cities", "/de/cities"),
     ("/methodology/de", "/de/methodology"), ("/city/berlin#map", "/de/city/berlin#map")],
)  # fmt: skip
def test_with_lang(path, de):
    assert urls.with_lang(path, "de") == de
    assert urls.with_lang(path, "en") == urls.strip_lang(path)
    assert urls.with_lang(de, "en") == urls.strip_lang(path)


@pytest.mark.parametrize("url", UNTOUCHED)
@pytest.mark.parametrize("base", ["/", "/velometer/"])
def test_u_leaves_external_and_fragment_urls_alone(base, url):
    assert make_u(base)(url) == url


@pytest.mark.parametrize("path", RELATIVE)
def test_u_refuses_a_relative_path(path):
    with pytest.raises(ValueError):
        make_u("/velometer/")(path)


def test_csp_meta_drops_exactly_the_header_only_directives():
    full = CSP + "; report-uri /csp; report-to grp; sandbox allow-scripts"
    header = _directives(full)
    meta = _directives(csp_meta(full))
    assert set(meta) == set(header) - HEADER_ONLY
    assert all(meta[k] == header[k] for k in meta)  # values kept verbatim


def test_csp_meta_of_the_app_policy_keeps_its_loading_rules():
    meta = _directives(csp_meta(CSP))
    assert "frame-ancestors" in _directives(CSP)  # the app sets one; only the header carries it
    assert "frame-ancestors" not in meta
    assert meta == {k: v for k, v in _directives(CSP).items() if k not in HEADER_ONLY}
