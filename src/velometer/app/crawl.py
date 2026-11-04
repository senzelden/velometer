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

from velometer.app.urls import DE_PREFIX, LEGACY_DE, PER_LANGUAGE_DATA, absolute_url, with_lang
from velometer.config import ConfigError

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
XHTML_NS = "http://www.w3.org/1999/xhtml"
# the sitemap's prefixes, registered once (the registry is process-wide)
ET.register_namespace("", SITEMAP_NS)
ET.register_namespace("xhtml", XHTML_NS)
ODBL_URL = "https://opendatacommons.org/licenses/odbl/1-0/"
REPO = Path(__file__).resolve().parents[3]
LLMS_TEMPLATE = "content/llms.md"
# the paths no crawler needs (§2.1), in both editions; `*` is understood by the major crawlers
NON_INDEX = ("/data/", "/maps/", "/tiles/", "/build.json", "/city/*/panel")
DISALLOW = [*NON_INDEX, *("/de" + p for p in NON_INDEX)]
# the data the page scripts fetch to draw the charts and the search (data.js, search.js): open to
# crawlers so a renderer (Googlebot's) draws the pages as a reader sees them; the downloads stay
# disallowed (the user's decision of 2026-11-03, ruling M3-robots)
RENDER_DATA = ("/data/series.json", "/data/search.json")
ALLOW = [*RENDER_DATA, *(DE_PREFIX + p for p in RENDER_DATA if p in PER_LANGUAGE_DATA)]
_NOT_PAGES = ("/data/", "/maps/", "/static/", "/tiles/")
TEMPLATES = "src/velometer/app/templates"
# the UI catalogue (content/ui) is not a source: one file holds every page's strings, so an edit
# to one page's string would date every page later than its real change (spec §4.1; ruling FIX-6)
# routes of the pages without a city: the templates that render each (with every template they
# extend, include or import, found by SOURCES_FOR) and their own content
_PAGE_SOURCES = {
    "/": ["index.html", "content/explainer.yaml"],
    "/cities": ["cities.html"],
    "/compare": ["compare.html", "content/explainer.yaml", "content/de/explainer.yaml"],
    "/stories": ["stories.html", "content/narratives"],
    "/differences": ["differences.html"],
    "/organisations": ["organisations.html", "content/organisations"],
    "/sources": ["sources.html", "content/sources"],
    "/plans": ["plans.html", "plans_berlin.html", "content/plans"],
    # the glossary is the terms registry; the method text is the generated documents
    "/methodology": [
        "methodology.html", "docs/methodology.md", "docs/methodology.de.md", "content/terms.yaml",
    ],
}  # fmt: skip


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


def robots_txt(origin: str, disallow: list[str], allow: list[str] | None = None) -> str:
    """One group for every crawler. An `allow` path inside a disallowed one is open: it is the
    longer match (RFC 9309), and it comes first for a crawler that takes the first match."""
    rules = "".join(f"Allow: {path}\n" for path in allow or [])
    rules += "".join(f"Disallow: {path}\n" for path in disallow)
    return (
        "# AI crawlers are welcome on purpose: no group names a bot.\n"
        f"User-agent: *\nAllow: /\n{rules}\nSitemap: {origin}sitemap.xml\n"
    )


def sitemap_xml(
    origin: str,
    pages: list[str],
    lastmod: dict[str, str],
    base: str = "/",
    *,
    languages: bool = True,
) -> str:
    """Every page in both editions with its `en`, `de` and `x-default` (the English page)
    alternates, which each page of a pair lists alike. `pages` are English routes. A page
    without a `lastmod` entry has no `<lastmod>`. With `languages` False (a single-language
    site) each page is listed once, without alternates."""
    root = ET.Element(f"{{{SITEMAP_NS}}}urlset")

    def absolute(route: str) -> str:
        return absolute_url(origin, base + route.lstrip("/"), base)

    for page in sorted(pages):
        en, de = absolute(page), absolute(with_lang(page, "de"))
        for loc in (en, de) if languages else (en,):
            url = ET.SubElement(root, f"{{{SITEMAP_NS}}}url")
            ET.SubElement(url, f"{{{SITEMAP_NS}}}loc").text = loc
            if page in lastmod:
                ET.SubElement(url, f"{{{SITEMAP_NS}}}lastmod").text = lastmod[page]
            for lang, href in (("en", en), ("de", de), ("x-default", en)) if languages else ():
                ET.SubElement(
                    url,
                    f"{{{XHTML_NS}}}link",
                    {"rel": "alternate", "hreflang": lang, "href": href},
                )
    ET.indent(root)
    body = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{body}\n'


def SOURCES_FOR(path: str) -> list[str]:  # noqa: N802 (a lookup table, named as the spec does)
    """The repo files that render a page without a city: its templates (each with the templates
    it extends, includes or imports) and its content, not the shared UI catalogue. An unknown
    page gets every template (its date is then the latest template change)."""
    route = "/plans" if path.startswith("/plans/") else path
    names = _PAGE_SOURCES.get(route)
    if names is None:
        return [TEMPLATES]
    templates = _with_referenced([n for n in names if "/" not in n])
    return [*(f"{TEMPLATES}/{n}" for n in templates), *(n for n in names if "/" in n)]


def _with_referenced(names: list[str]) -> list[str]:
    """`names` and every template they reference (`extends`, `include`, `import`, `from`),
    transitively, sorted; a reference by a variable cannot be followed and is left out."""
    from jinja2 import Environment, FileSystemLoader, meta

    env = Environment(loader=FileSystemLoader(REPO / TEMPLATES), autoescape=True)
    found: set[str] = set()
    todo = list(names)
    while todo:
        name = todo.pop()
        if name in found:
            continue
        found.add(name)
        source = (REPO / TEMPLATES / name).read_text(encoding="utf-8")
        todo += [n for n in meta.find_referenced_templates(env.parse(source)) if n]
    return sorted(found)


def _city_date(build: dict, city: str) -> str | None:
    pool = build.get("osm_timestamps", {}).get(city, [])
    return max(pool)[:10] if pool else None


def _git(repo: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    except OSError as e:
        raise ConfigError(f"lastmod needs git, which cannot run: {e}") from e
    if r.returncode != 0:
        raise ConfigError(
            f"lastmod needs the git history of {repo}: git {args[0]} says {r.stderr.strip()!r}"
        )
    return r.stdout.strip()


def lastmod_for(path: str, build: dict, repo: Path) -> str:
    """`YYYY-MM-DD`. A city's page: the latest OSM snapshot of that city. Any other page: the
    date of the last commit touching its sources. There is no fallback date: a date later than
    the real change would be wrong, so without git, with a shallow clone (its commits all look
    recent) or with no commit touching the sources, ConfigError says what to fix."""
    parts = path.strip("/").split("/")
    if parts[0] == "city" and len(parts) > 1:
        found = _city_date(build, parts[1])
        if found is None:
            raise ConfigError(f"lastmod of {path}: build.json has no OSM snapshot for {parts[1]}")
        return found
    if _git(repo, "rev-parse", "--is-shallow-repository") != "false":
        raise ConfigError(
            f"lastmod of {path}: {repo} is a shallow clone (or not a git repository), so commit "
            "dates are not the content's; fetch the full history (fetch-depth: 0)"
        )
    sources = SOURCES_FOR(path)
    date = _git(repo, "log", "-1", "--format=%cs", "--", *sources)
    if not date:
        raise ConfigError(f"lastmod of {path}: no commit touches its sources {sources}")
    return date


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
    text = "\n".join(_without_empty_sections(out)) + "\n"
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text


def _without_empty_sections(lines: list[str]) -> list[str]:
    """`lines` without a `## ` heading whose section has no line left (no cities, say)."""
    out: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            rest = next((x for x in lines[i + 1 :] if x.strip()), None)
            if rest is None or rest.startswith("## "):
                continue
        out.append(line)
    return out


# the DOIs of build.json `site` that llms.txt names, with the label of each line
DOI_LABELS = {"dataset_doi": "Dataset", "software_doi": "Software"}


def dois_of(values: dict) -> dict[str, str]:
    """The DOIs set among a build's site values (`SiteConfig.public_values`), by their llms.txt
    label; an unset one is left out."""
    return {label: values[key] for key, label in DOI_LABELS.items() if values.get(key)}


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
    (site / "robots.txt").write_text(robots_txt(origin, DISALLOW, ALLOW), encoding="utf-8")
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
