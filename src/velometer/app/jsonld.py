"""schema.org JSON-LD of the public pages (M17 §4.2): a `Dataset` for the collection (home page)
and one per city (story page), a `WebSite`, and a `TechArticle` for the methodology.

Each object says only what the page shows (Google's rule): the cities are the ones in the
ranking, the description is the page's own meta description, the dates are the OSM snapshots of
the exported runs. The dataset's `identifier` is its Zenodo concept DOI; without one (`dataset_doi`
unset in the site config) it is left out, and `deploy-check --public` refuses the export.
"""

import json
from collections.abc import Iterable
from urllib.parse import urlsplit

from markupsafe import Markup

from velometer import i18n
from velometer.app import meta
from velometer.app.urls import absolute_url, make_u
from velometer.config import SiteConfig, load_cities
from velometer.credits import GISCO_TERMS_URL, ODBL_URL, OSM_COPYRIGHT_URL
from velometer.sources.boundaries import EUROSTAT_POP

CONTEXT = "https://schema.org"
CREATOR = {"@type": "Person", "name": "Dennis Senzel"}
ALL_CSV = "/data/all.csv"
MISSING_DOI = "JSON-LD identifier: no dataset DOI"


def script(obj: dict) -> Markup:
    """`obj` as a `<script type="application/ld+json">` element. `</` is written `<\\/` (the same
    JSON string) so no text of the object, a narrative that quotes `</script>` included, can end
    the element."""
    body = json.dumps({"@context": CONTEXT, **obj}, ensure_ascii=False).replace("</", "<\\/")
    return Markup('<script type="application/ld+json">{}</script>').format(Markup(body))


def _url(site: SiteConfig, lang: str, path: str) -> str:
    """The absolute URL of a page route in edition `lang`."""
    assert site.url, "JSON-LD is written for a site with a public origin"
    return absolute_url(site.url, make_u("/", lang)(path), "/")


def _data_url(site: SiteConfig, path: str) -> str:
    assert site.url
    return absolute_url(site.url, path, "/")


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/"


def based_on(data) -> list[dict]:
    """The sources the figures rest on, as the repo names them: the OSM copyright page and GISCO's
    terms (credits.py), the Eurostat portal (the API URL of sources/boundaries.py cut at
    `/api/`), and the INSEE and INE sites (the origins of the population sources of
    config/cities.yaml)."""
    urls = {
        "OpenStreetMap": OSM_COPYRIGHT_URL,
        "Eurostat GISCO": GISCO_TERMS_URL,
        "Eurostat": EUROSTAT_POP.split("/api/")[0],
    }
    hosts = {"INSEE": "insee.fr", "INE": "ine.es"}
    for city in load_cities(data.config_dir / "cities.yaml"):
        override = city.population_override
        host = urlsplit(override.source_url).hostname or "" if override else ""
        for name, domain in hosts.items():
            if name not in urls and (host == domain or host.endswith("." + domain)):
                urls[name] = _origin(override.source_url)
    return [{"@type": "Dataset", "name": name, "url": url} for name, url in urls.items()]


def _dates(data, city_id: str | None = None) -> str:
    """`<first>/<last>`: the earliest and latest OSM snapshot date of the exported runs."""
    stamps = sorted({r["osm_timestamp"][:10] for r in data.csv_rows(city_id) if r["osm_timestamp"]})
    return f"{stamps[0]}/{stamps[-1]}"


def collection(data, site: SiteConfig, lang: str, ranked: Iterable | None = None) -> dict:
    """The `Dataset` of the whole collection. `ranked` is the cities in the home page's ranking
    order (default: the report's order); `spatialCoverage` and `hasPart` follow it."""
    cities = data.cities()
    order = list(ranked) if ranked is not None else []
    order += [c for c in cities if c.id not in {o.id for o in order}]
    obj = {
        "@type": "Dataset",
        "@id": _url(site, lang, "/") + "#dataset",
        "name": meta.plain(i18n.t(lang, "page.index.h1", n=len(cities))),
        "description": meta.plain(i18n.t(lang, "meta.index", n=len(cities))),
        "url": _url(site, lang, "/"),
        "inLanguage": lang,
        "creator": CREATOR,
        "license": ODBL_URL,
        "isAccessibleForFree": True,
        "spatialCoverage": [{"@type": "Place", "name": c.name} for c in order],
        "temporalCoverage": _dates(data),
        "distribution": [
            {
                "@type": "DataDownload",
                "contentUrl": _data_url(site, ALL_CSV),
                "encodingFormat": "text/csv",
            }
        ],
        "isBasedOn": based_on(data),
        "hasPart": [{"@type": "Dataset", "url": _url(site, lang, f"/city/{c.id}")} for c in order],
    }
    if site.dataset_doi:
        obj["identifier"] = f"https://doi.org/{site.dataset_doi}"
    return obj


def city(city, data, site: SiteConfig, lang: str, description: str | None = None) -> dict:
    """The `Dataset` of one city: its CSV, part of the collection. `description` is the page's
    meta description (the dek, else the `meta.city_plain` sentence)."""
    text = description or meta.plain(i18n.t(lang, "meta.city_plain", city=city.name))
    return {
        "@type": "Dataset",
        "@id": _url(site, lang, f"/city/{city.id}") + "#dataset",
        "name": city.name,
        "description": text,
        "url": _url(site, lang, f"/city/{city.id}"),
        "inLanguage": lang,
        "creator": CREATOR,
        "license": ODBL_URL,
        "isAccessibleForFree": True,
        "spatialCoverage": {"@type": "Place", "name": city.name},
        "temporalCoverage": _dates(data, city.id),
        "distribution": [
            {
                "@type": "DataDownload",
                "contentUrl": _data_url(site, f"/data/{city.id}.csv"),
                "encodingFormat": "text/csv",
            }
        ],
        "isBasedOn": based_on(data),
        "isPartOf": {"@type": "Dataset", "@id": _url(site, lang, "/") + "#dataset"},
    }


def website(site: SiteConfig, lang: str = "en") -> dict:
    obj = {
        "@type": "WebSite",
        "name": "velometer",
        "url": _url(site, lang, "/"),
        "inLanguage": lang,
        "creator": CREATOR,
    }
    if site.datalab:
        obj["publisher"] = {
            "@type": "Organization",
            "name": site.datalab.name,
            "url": site.datalab.url,
        }
    return obj


def article(site: SiteConfig, lang: str) -> dict:
    """The methodology as a `TechArticle` (its canonical edition's URL: the legacy
    `/methodology/de` page is the German one)."""
    return {
        "@type": "TechArticle",
        "headline": "velometer · " + meta.plain(i18n.t(lang, "page.methodology.title")),
        "description": meta.plain(i18n.t(lang, "meta.methodology")),
        "url": _url(site, lang, "/methodology"),
        "inLanguage": lang,
        "author": CREATOR,
        "isPartOf": {"@type": "WebSite", "name": "velometer", "url": _url(site, lang, "/")},
    }


def datalab(name: str, url: str, project_url: str) -> dict:
    """The Datalab's home page: the `Organization` behind velometer, which it names as its
    project (a `WebSite`)."""
    return {
        "@type": "Organization",
        "name": name,
        "url": url,
        "owns": {"@type": "WebSite", "name": "velometer", "url": project_url, "creator": CREATOR},
    }
