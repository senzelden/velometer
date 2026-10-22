"""The Zählwerk Berlin Datalab site: the apex page, Impressum and Datenschutz (M16 spec §4.5).

`build` renders `sites/datalab/` into a small static site, with a 404 page for the server (ruling
R21). The Berlin counter on the main page is read from a finished velometer export's
`data/all.csv` (spec §4.9 item 7), so it cannot drift from velometer: Berlin's LAU tier A+B
mapped km (`ab_km`) of each year snapshot, rounded to whole km. Impressum and Datenschutz hold
one variant per operator form (legal review 4.1, 5.1); with `operator_form` null all three are
rendered, each under its own heading, and every value not given is a visible `[[…]]`
placeholder (`placeholders` lists those left; the go-live check refuses while there is one).
Nothing is invented: a null stays a placeholder.

The site loads nothing from another host (fonts self-hosted, legal review 5.9) and has no inline
script or style; its own CSP says so. The output gets `.gz` siblings and a `_headers` file the
way the velometer export does (`export.write_gz`, `export.headers_text`).
"""

import csv
import io
import re
import shutil
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Literal

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape
from pydantic import BaseModel, ConfigDict, field_validator

from velometer import credits, i18n

SITE_DIR = Path(__file__).resolve().parents[2] / "sites" / "datalab"
DEFAULT_CONFIG = SITE_DIR / "site.yaml"
CITY, BOUNDARY = "berlin", "lau"
# The operator's details (sites/datalab/site.yaml documents each).
OPERATOR_KEYS = (
    "name", "address", "email", "phone", "register", "vat", "representative", "responsible",
    "authority", "mail_host",
)  # fmt: skip
# Shown as a placeholder while unset in every case; `phone` and `vat` are optional (legal review
# 4.1, 4.4) and left out once a form is chosen without them.
REQUIRED = {
    "person": ("name", "address", "email", "responsible", "authority", "mail_host"),
    "verein": (
        "name", "address", "email", "register", "representative", "responsible", "authority",
        "mail_host",
    ),
    "company": (
        "name", "address", "email", "register", "representative", "responsible", "authority",
        "mail_host",
    ),
}  # fmt: skip
OPTIONAL = ("phone", "vat")
FORMS = (
    ("person", "Privatperson"),
    ("verein", "Eingetragener Verein (e.V.)"),
    ("company", "Unternehmen (z. B. GmbH oder UG)"),
)
# The authority competent for an operator in Berlin (legal review 5.8, read 2026-10-21).
BLNBDI = (
    "Berliner Beauftragte für Datenschutz und Informationsfreiheit\n"
    "Alt-Moabit 59-61, 10555 Berlin\n"
    "Telefon +49 30 13889-0, E-Mail mailbox@datenschutz-berlin.de"
)
# The pages' policy: everything from the site's own origin, nothing inline (the header adds
# frame-ancestors, which a <meta> policy cannot carry).
CSP = "default-src 'self'; base-uri 'none'; form-action 'none'"
PLACEHOLDER = re.compile(r"\[\[[^\]\n]*\]\]")
HOSTNAME = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+")
# 404.html is the page the server sends for any address the site does not have (ruling R21)
PAGES = {"index.html": "index.html", "impressum.html": "impressum/index.html",
         "datenschutz.html": "datenschutz/index.html", "404.html": "404.html"}  # fmt: skip


class DatalabError(Exception):
    """A build that cannot complete; the message names what and why."""


def _blank_is_none(value: str | None) -> str | None:
    """A value of only whitespace is not given: it stays a placeholder (or is left out)."""
    return None if value is None or not value.strip() else value


class DatalabConfig(BaseModel):
    """`sites/datalab/site.yaml`."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    domain: str
    operator_form: Literal["person", "verein", "company"] | None = None
    operator: dict[str, str | None] = {}
    contact_email: str | None = None

    @field_validator("domain")
    @classmethod
    def _hostname(cls, v: str) -> str:
        if not HOSTNAME.fullmatch(v):
            raise ValueError(f"not a bare host name (no scheme, path or capitals): {v!r}")
        return v

    @field_validator("operator")
    @classmethod
    def _known_keys(cls, v: dict[str, str | None]) -> dict[str, str | None]:
        unknown = sorted(set(v) - set(OPERATOR_KEYS))
        if unknown:
            raise ValueError(f"unknown operator keys {unknown}; known: {list(OPERATOR_KEYS)}")
        return {k: _blank_is_none(v.get(k)) for k in OPERATOR_KEYS}

    @field_validator("contact_email")
    @classmethod
    def _contact(cls, v: str | None) -> str | None:
        return _blank_is_none(v)


def load_config(path: Path = DEFAULT_CONFIG) -> DatalabConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise DatalabError(f"{path}: {e}") from e
    return DatalabConfig.model_validate(raw)


@dataclass(frozen=True)
class Counter:
    """What the main page's counter shows: Berlin's tier A+B mapped km per year snapshot."""

    series: list[tuple[int, int]]  # (year, whole km), ascending
    as_of: date  # the OSM timestamp of the last year snapshot
    cities: int  # the cities in the export


def _round(value: str) -> int:
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def read_counter(velometer_export: Path) -> Counter:
    """The counter's figures from the export's `data/all.csv` (comment lines skipped)."""
    path = velometer_export / "data" / "all.csv"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise DatalabError(f"no velometer export at {velometer_export}: cannot read {path}") from e
    body = "".join(line for line in text.splitlines(keepends=True) if not line.startswith("#"))
    rows = list(csv.DictReader(io.StringIO(body)))
    years = sorted(
        (int(r["label"]), r["ab_km"], r["osm_timestamp"])
        for r in rows
        if r.get("city_id") == CITY and r.get("boundary_kind") == BOUNDARY
        and (r.get("label") or "").isdigit()
    )  # fmt: skip
    if not years:
        raise DatalabError(f"{path} has no {CITY} {BOUNDARY} year rows")
    try:
        series = [(y, _round(km)) for y, km, _ in years]
        as_of = date.fromisoformat(years[-1][2][:10])
    except (ArithmeticError, ValueError) as e:
        raise DatalabError(f"{path}: an unreadable {CITY} {BOUNDARY} row ({e})") from e
    return Counter(series, as_of, len({r["city_id"] for r in rows}))


def meta_csp() -> str:
    """The policy as the pages' <meta> carries it (velometer's `csp_meta`)."""
    from velometer.app.main import csp_meta

    return csp_meta(CSP)


def _lines(value: str) -> Markup:
    return Markup("<br>").join(escape(line.strip()) for line in value.splitlines())


def placeholder(label: str) -> Markup:
    return Markup('<span class="ph">[[{}]]</span>').format(label)


class _Fields:
    """The operator's values as the templates use them: `v(key, label)` is the escaped value
    (line breaks kept) or a placeholder; `shown(key)` is False only for an optional value left
    out of a chosen form."""

    def __init__(self, cfg: DatalabConfig):
        self.cfg = cfg

    def v(self, key: str, label: str) -> Markup:
        value = self.cfg.operator.get(key)
        if key == "authority" and value and value.strip().lower() == "blnbdi":
            value = BLNBDI
        return _lines(value) if value else placeholder(label)

    def shown(self, key: str) -> bool:
        if self.cfg.operator.get(key):
            return True
        return self.cfg.operator_form is None or key not in OPTIONAL


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(SITE_DIR / "templates"),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render(cfg: DatalabConfig, counter: Counter) -> dict[str, str]:
    """Each page's HTML by its output path."""
    last_year, last_km = counter.series[-1]
    digits = len(str(max(km for _, km in counter.series)))
    forms = [f for f in FORMS if cfg.operator_form in (None, f[0])]
    context = {
        "domain": cfg.domain,
        "velometer_url": f"https://velometer.{cfg.domain}/",
        "csp": meta_csp(),
        "contact": (
            Markup('<a href="mailto:{0}">{0}</a>').format(cfg.contact_email)
            if cfg.contact_email
            else placeholder("Kontakt-E-Mail")
        ),
        "decided": cfg.operator_form is not None,
        "forms": forms,
        "f": _Fields(cfg),
        "km_digits": str(last_km).zfill(digits),
        "year_digits": str(last_year),
        "series": " ".join(f"{y}:{km}" for y, km in counter.series),
        "first_year": counter.series[0][0],
        "last_year": last_year,
        "reading": f"Berlin {last_year}: {i18n.number(last_km, 'de', 0)} km",
        "as_of": i18n.long_day(counter.as_of, "de"),
        "cities": counter.cities,
        "osm_credit": i18n.t_markup("de", "site.footer.attribution", osm=credits.OSM_COPYRIGHT_URL),
        "boundary_credit": i18n.t("de", "credit.boundaries"),
    }
    env = _env()
    return {out: env.get_template(name).render(**context) for name, out in PAGES.items()}


def build(cfg: DatalabConfig, velometer_export: Path, out: Path) -> list[str]:
    """The site in `out` (absent or empty): pages, `static/`, `.gz` siblings and `_headers`.
    Everything is read and rendered before the first write. Returns the written paths, relative
    to `out`, sorted."""
    from velometer.app.export import headers_text, write_gz

    pages = render(cfg, read_counter(velometer_export))
    if out.is_symlink():
        raise DatalabError(f"refusing --out {out}: it is a symlink; name the directory itself")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise DatalabError(f"{out} is not empty (or not a directory); name a new directory")
    out.mkdir(parents=True, exist_ok=True)
    for rel, html in pages.items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    shutil.copytree(SITE_DIR / "static", out / "static")
    write_gz(out)
    (out / "_headers").write_text(headers_text("/", meta_csp()), encoding="utf-8")
    return sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())


def placeholders(out: Path) -> list[str]:
    """Every visible placeholder left in the built pages, as `file:line` (one per placeholder,
    in file and line order)."""
    found = []
    for path in sorted(out.rglob("*.html")):
        rel = path.relative_to(out).as_posix()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            found += [f"{rel}:{n}"] * len(PLACEHOLDER.findall(line))
    return found
