"""The base path every URL the app emits carries (M9 spec decision 3).

The routes stay at `/…`; a page built for a host that serves the site under a sub-path
(`/velometer/`) writes every internal `href`, `src`, `action` and every URL a script reads from
a JSON config through `u(path)`. The live app runs with base `/`, where `u` is the identity.

M12 (spec decision 1): every page has a German twin under `/de/`. A page helper is bound to a
language (`make_u(base, "de")` puts `de/` after the base); data, map and static files are shared
by both editions and go through `make_data_u`, whose only per-language file is the search index.
The language of a request comes from its route registration; `lang_of` and `strip_lang` read a
path only where no route ran (the 404) or for the export's URL list and a page's twin links.
"""

import re
from collections.abc import Callable

from velometer.i18n import Lang

DE_PREFIX = "/de"
# the legacy German methodology URL (before M12), still served with a canonical link
LEGACY_DE = {"/methodology/de": "/methodology"}
# the data files that exist once per language (`<base>de/data/search.json`)
PER_LANGUAGE_DATA = frozenset({"/data/search.json"})
DATA_ROOTS = ("/data/", "/maps/", "/static/")
_DATA_PATH = re.compile(r"^/(data|maps|static)(?=[/?#]|$)")
_QUERY_OR_HASH = re.compile(r"[?#]")
# an RFC 3986 scheme: a letter, then letters, digits, `+`, `.` or `-`, then `:`
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


def normalise_base(base: str) -> str:
    """`base` with exactly one leading and one trailing `/` ("" and "/" are `/`)."""
    inner = base.strip("/")
    return "/" if not inner else f"/{inner}/"


def _is_external(url: str) -> bool:
    """A scheme (`https:`, `mailto:`, `web+foo:`; RFC 3986) or a protocol-relative `//host`:
    not ours to prefix."""
    return url.startswith("//") or _SCHEME.match(url) is not None


def _split(path: str) -> tuple[str, str]:
    """(path, query and fragment)."""
    m = _QUERY_OR_HASH.search(path)
    return (path, "") if m is None else (path[: m.start()], path[m.start() :])


def _under_de(path: str) -> bool:
    p, _ = _split(path)
    return p == DE_PREFIX or p.startswith(DE_PREFIX + "/")


def make_u(base: str, lang: Lang = "en") -> Callable[[str], str]:
    """The page-link helper of a base path and a language: `u("/city/berlin")` is
    `<base>city/berlin`, or `<base>de/city/berlin` for German (query and fragment kept). A path
    already under `/de`, external URLs (a scheme or `//host`) and fragment-only `#x` come back
    unchanged apart from the base; any other path must start with `/` (a relative path would
    resolve against the page, not the base), else ValueError. A data, map or static path is
    refused (ValueError): those go through `make_data_u`."""
    prefix = normalise_base(base)

    def u(path: str) -> str:
        if path.startswith("#") or _is_external(path):
            return path
        if not path.startswith("/"):
            raise ValueError(f"an internal URL must start with '/': {path!r}")
        if _DATA_PATH.match(path):
            raise ValueError(f"a data, map or static URL goes through data_u: {path!r}")
        if lang == "de" and not _under_de(path):
            path = DE_PREFIX + path
        return prefix + path[1:]

    return u


def make_data_u(base: str) -> Callable[[str, Lang | None], str]:
    """The data-link helper of a base path: `data_u("/data/series.json")` is
    `<base>data/series.json`. Only `/data/`, `/maps/` and `/static/` paths are accepted, and
    `lang="de"` only for a file in PER_LANGUAGE_DATA (`<base>de/data/search.json`); anything else
    is a ValueError."""
    prefix = normalise_base(base)

    def data_u(path: str, lang: Lang | None = None) -> str:
        if not path.startswith(DATA_ROOTS):
            raise ValueError(f"not a data, map or static URL: {path!r}")
        if lang == "de":
            if path not in PER_LANGUAGE_DATA:
                raise ValueError(f"{path!r} is the same file in every language")
            path = DE_PREFIX + path
        return prefix + path[1:]

    return data_u


def lang_of(path: str) -> Lang:
    """The language of an unprefixed request path (query or hash allowed): `de` under `/de` and
    for the legacy `/methodology/de`. Only for the 404 handler and the export; a route knows its
    language from its registration."""
    p, _ = _split(path)
    return "de" if _under_de(p) or p in LEGACY_DE else "en"


def strip_lang(path: str) -> str:
    """The English twin of an unprefixed path: `/de/cities` -> `/cities`, `/de` -> `/`,
    `/methodology/de` -> `/methodology`; English paths unchanged."""
    p, rest = _split(path)
    if p in LEGACY_DE:
        return LEGACY_DE[p] + rest
    if _under_de(p):
        return (p[len(DE_PREFIX) :] or "/") + rest
    return path


def with_lang(path: str, lang: Lang) -> str:
    """The twin of an unprefixed path in `lang`: `/` -> `/de/`, `/cities?x=1` ->
    `/de/cities?x=1`; for English it is `strip_lang`."""
    english = strip_lang(path)
    return english if lang == "en" else DE_PREFIX + english
