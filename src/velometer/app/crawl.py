"""The crawl files of an export (M17 §4.1): `robots.txt`, `sitemap.xml` and `llms.txt`.

A public export lists its indexable pages (every exported HTML page of both editions except the
panel fragments, the data, map and tile paths and the legacy `/methodology/de`, which is
canonical to `/de/methodology`). A preview export is not for search engines: its `robots.txt`
disallows everything and it has no sitemap. `lastmod` is the date the page's content last changed
and never the build date: a city's latest OSM snapshot, else the last commit touching the files
that render the page, so a rebuild without a change writes the same bytes.
"""

import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

from velometer.app.urls import LEGACY_DE, absolute_url, with_lang

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
XHTML_NS = "http://www.w3.org/1999/xhtml"
ODBL_URL = "https://opendatacommons.org/licenses/odbl/1-0/"
REPO = Path(__file__).resolve().parents[3]
LLMS_TEMPLATE = "content/llms.md"
# the paths no crawler needs (§2.1), in both editions; `*` is understood by the major crawlers
NON_INDEX = ("/data/", "/maps/", "/tiles/", "/build.json", "/city/*/panel")
DISALLOW = [*NON_INDEX, *("/de" + p for p in NON_INDEX)]
_NOT_PAGES = ("/data/", "/maps/", "/static/", "/tiles/")
TEMPLATES = "src/velometer/app/templates"
# routes of the pages without a city: the files that render each (a template and its content)
_PAGE_SOURCES = {
    "/": ["index.html", "content/ui", "content/explainer.yaml"],
    "/cities": ["cities.html"],
    "/compare": ["compare.html", "content/explainer.yaml", "content/de/explainer.yaml"],
    "/stories": ["stories.html", "content/narratives"],
    "/differences": ["differences.html"],
    "/organisations": ["organisations.html", "content/organisations"],
    "/sources": ["sources.html", "content/sources"],
    "/plans": ["plans.html", "plans_berlin.html", "content/plans"],
    "/methodology": ["methodology.html", "docs/methodology.md", "docs/methodology.de.md"],
}


def indexable(urls: list[str]) -> list[str]:
    """The English HTML pages to list, sorted, each once (the German twins are derived)."""
    pages = set()
    for url in urls:
        if url in LEGACY_DE or url == "/build.json" or url.startswith(_NOT_PAGES):
            continue
        if url == "/de" or url.startswith("/de/") or url.endswith("/panel"):
            continue
        pages.add(url)
    return sorted(pages)


def robots_txt(origin: str, disallow: list[str]) -> str:
    rules = "".join(f"Disallow: {path}\n" for path in disallow)
    return (
        "# AI crawlers are welcome on purpose: no group names a bot.\n"
        f"User-agent: *\nAllow: /\n{rules}\nSitemap: {origin}sitemap.xml\n"
    )


def sitemap_xml(origin: str, pages: list[str], lastmod: dict[str, str], base: str = "/") -> str:
    """Every page in both editions with its `en`, `de` and `x-default` (the English page)
    alternates, which each page of a pair lists alike. `pages` are English routes."""
    ET.register_namespace("", SITEMAP_NS)
    ET.register_namespace("xhtml", XHTML_NS)
    root = ET.Element(f"{{{SITEMAP_NS}}}urlset")

    def absolute(route: str) -> str:
        return absolute_url(origin, base + route.lstrip("/"), base)

    for page in sorted(pages):
        en, de = absolute(page), absolute(with_lang(page, "de"))
        for loc in (en, de):
            url = ET.SubElement(root, f"{{{SITEMAP_NS}}}url")
            ET.SubElement(url, f"{{{SITEMAP_NS}}}loc").text = loc
            ET.SubElement(url, f"{{{SITEMAP_NS}}}lastmod").text = lastmod[page]
            for lang, href in (("en", en), ("de", de), ("x-default", en)):
                ET.SubElement(
                    url,
                    f"{{{XHTML_NS}}}link",
                    {"rel": "alternate", "hreflang": lang, "href": href},
                )
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=False).join(
        ['<?xml version="1.0" encoding="UTF-8"?>\n', "\n"]
    )


def SOURCES_FOR(path: str) -> list[str]:  # noqa: N802 (a lookup table, named as the spec does)
    """The repo files that render a page without a city: its template and its content. An unknown
    page gets every template (its date is then the latest template change)."""
    route = "/plans" if path.startswith("/plans/") else path
    names = _PAGE_SOURCES.get(route)
    if names is None:
        return [TEMPLATES]
    return [n if "/" in n else f"{TEMPLATES}/{n}" for n in names]


def _city_date(build: dict, city: str | None = None) -> str | None:
    stamps = build.get("osm_timestamps", {})
    pool = stamps.get(city, []) if city else [t for ts in stamps.values() for t in ts]
    return max(pool)[:10] if pool else None


def lastmod_for(path: str, build: dict, repo: Path) -> str:
    """`YYYY-MM-DD`. A city's page: the latest OSM snapshot of that city. Any other page: the
    date of the last commit touching its sources; without git history, the latest snapshot of
    any city, else 1970-01-01 (never today: the value must not move on a rebuild)."""
    parts = path.strip("/").split("/")
    if parts[0] == "city" and len(parts) > 1:
        found = _city_date(build, parts[1])
        if found:
            return found
    else:
        try:
            r = subprocess.run(
                ["git", "log", "-1", "--format=%cs", "--", *SOURCES_FOR(path)],
                cwd=repo, capture_output=True, text=True, check=False,
            )  # fmt: skip
        except OSError:
            r = None
        if r is not None and r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return _city_date(build) or "1970-01-01"


def llms_txt(
    origin: str,
    cities: list[tuple[str, str]],
    dois: dict,
    *,
    repo_url: str = "",
    datalab_url: str = "",
    template: str | None = None,
) -> str:
    """`content/llms.md` with its `{…}` fields filled; a line whose field is empty is left out
    (no DOI, no repository). `cities` are (name, English route) pairs."""
    if template is None:
        template = (REPO / LLMS_TEMPLATE).read_text(encoding="utf-8")
    fields = {
        "origin": origin,
        "n_cities": str(len(cities)),
        "cities": "\n".join(
            f"- [{name}]({absolute_url(origin, route, '/')})" for name, route in cities
        ),
        "dois": "".join(f"- {name}: https://doi.org/{doi}\n" for name, doi in dois.items()),
        "repo_url": repo_url,
        "datalab_url": datalab_url,
        "odbl_url": ODBL_URL,
    }
    out = []
    for line in template.splitlines():
        if any(f"{{{k}}}" in line and not v for k, v in fields.items()):
            continue
        for k, v in fields.items():
            line = line.replace(f"{{{k}}}", v)
        out.append(line)
    text = "\n".join(out) + "\n"
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text


def write_crawl_files(
    site: Path,
    origin: str | None,
    urls: list[str],
    build: dict,
    repo: Path = REPO,
    names: dict[str, str] | None = None,
    dois: dict | None = None,
) -> None:
    """The crawl files of an export into `site`. `origin` None is a preview export: it disallows
    everything and has no sitemap or llms.txt."""
    if origin is None:
        (site / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        return
    base = build["base"]
    pages = indexable(urls)
    lastmod = {p: lastmod_for(p, build, repo) for p in pages}
    names = names or {}
    (site / "robots.txt").write_text(robots_txt(origin, DISALLOW), encoding="utf-8")
    (site / "sitemap.xml").write_text(sitemap_xml(origin, pages, lastmod, base), encoding="utf-8")
    ids = sorted(build.get("osm_timestamps", {}))
    cities = [(names.get(i, i), f"/city/{i}") for i in ids]
    cities.sort(key=lambda c: c[0].casefold())
    values = build.get("site") or {}
    (site / "llms.txt").write_text(
        llms_txt(
            origin,
            cities,
            dois or {},
            repo_url=values.get("repo_url", ""),
            datalab_url=values.get("datalab_url", ""),
        ),  # fmt: skip
        encoding="utf-8",
    )
