"""The base-path helper (`app/urls.py`) and the CSP meta tag's policy (M9 spec decisions 3, 6)."""

import pytest

from velometer.app.main import CSP, csp_meta
from velometer.app.urls import make_u, normalise_base

# (base as given, normalised)
NORMALISE = [
    ("", "/"),
    ("/", "/"),
    ("velometer", "/velometer/"),
    ("/velometer", "/velometer/"),
    ("velometer/", "/velometer/"),
    ("/a/b", "/a/b/"),
]
# (base, path, emitted URL)
EMIT = [
    ("/", "/", "/"),
    ("/", "/city/berlin", "/city/berlin"),
    ("/velometer/", "/", "/velometer/"),
    ("/velometer/", "/city/berlin", "/velometer/city/berlin"),
    ("/velometer/", "/compare?q=1#x", "/velometer/compare?q=1#x"),
    ("/velometer/", "/plans#berlin", "/velometer/plans#berlin"),
    ("/a/b/", "/static/app.css", "/a/b/static/app.css"),
    ("velometer", "/data/all.csv", "/velometer/data/all.csv"),
]
# URLs that are not ours: unchanged under any base
UNTOUCHED = [
    "https://www.openstreetmap.org/copyright",
    "http://example.org/x",
    "mailto:someone@example.org",
    "//tile.openstreetmap.org/1/2/3.png",
    "#x",
    "#",
]
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
    assert make_u(base)(path) == expected


@pytest.mark.parametrize("url", UNTOUCHED)
@pytest.mark.parametrize("base", ["/", "/velometer/"])
def test_u_leaves_external_and_fragment_urls_alone(base, url):
    assert make_u(base)(url) == url


@pytest.mark.parametrize("path", ["city/berlin", "", "compare?c=berlin"])
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
