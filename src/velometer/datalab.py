"""The Zählwerk Berlin Datalab site: the apex page, Impressum, Datenschutz and the accessibility
statement (M16 spec §4.5; the statement: user request 2026-10-29, ruling R63).

`build` renders `sites/datalab/` into a small static site, with a 404 page for the server (ruling
R21). The Berlin counter on the main page is read from a finished velometer export's
`data/all.csv` (spec §4.9 item 7), so it cannot drift from velometer: Berlin's LAU tier A+B
mapped km (`ab_km`) of each year snapshot, rounded to whole km. Impressum and Datenschutz hold
one variant per operator form (legal review 4.1, 5.1); with `operator_form` null all three are
rendered, each under its own heading, and every value not given is a visible `[[…]]`
placeholder (`placeholders` lists those left; the go-live check refuses while there is one).
Nothing is invented: a null stays a placeholder. The accessibility statement takes its e-mail from
the Impressum's (`operator.email`) and its date from `accessibility.checked`, null until go-live.

The site loads nothing from another host (fonts self-hosted, legal review 5.9) and has no inline
script or style; its own CSP says so. The output gets `.gz` siblings and a `_headers` file the
way the velometer export does (`export.write_gz`, `export.headers_text`), and a `build.json` with
`inputs_stamp`, the hash of what it was built from (the go-live check compares it).
"""

import csv
import hashlib
import io
import json
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
# Required by law but rendered nowhere, not even as a placeholder, until set (the user's call,
# 2026-10-24: the address waits until the last moment); the go-live check refuses while one is null.
DEFERRED = ("address",)
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
         "datenschutz.html": "datenschutz/index.html",
         "barrierefreiheit.html": "barrierefreiheit/index.html",
         "404.html": "404.html"}  # fmt: skip
# The accessibility statement's address in a build (golive-check asks for it, R63).
STATEMENT_PAGE = PAGES["barrierefreiheit.html"]


class DatalabError(Exception):
    """A build that cannot complete; the message names what and why."""


def _blank_is_none(value: str | None) -> str | None:
    """A value of only whitespace is not given: it stays a placeholder (or is left out)."""
    return None if value is None or not value.strip() else value


class Accessibility(BaseModel):
    """`accessibility:` in site.yaml: the date the statement's checks were last done (R63)."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    checked: date | None = None

    @field_validator("checked", mode="before")
    @classmethod
    def _iso_day(cls, v: object) -> object:
        """YAML reads `2026-11-02` as a date; a string must be the same ISO day."""
        if isinstance(v, str):
            try:
                return date.fromisoformat(v)
            except ValueError:
                raise ValueError(f"not an ISO day (YYYY-MM-DD): {v!r}") from None
        return v


class DatalabConfig(BaseModel):
    """`sites/datalab/site.yaml`."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    domain: str
    operator_form: Literal["person", "verein", "company"] | None = None
    operator: dict[str, str | None] = {}
    contact_email: str | None = None
    accessibility: Accessibility = Accessibility()

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
    (line breaks kept) or a placeholder; `shown(key)` is False for an optional value left
    out of a chosen form and for an unset deferred one."""

    def __init__(self, cfg: DatalabConfig):
        self.cfg = cfg

    def v(self, key: str, label: str) -> Markup:
        value = self.cfg.operator.get(key)
        if key == "authority" and value and value.strip().lower() == "blnbdi":
            value = BLNBDI
        return _lines(value) if value else placeholder(label)

    def mail(self, key: str, label: str) -> Markup:
        """The value as a mailto link, or a placeholder."""
        value = self.cfg.operator.get(key)
        return Markup('<a href="mailto:{0}">{0}</a>').format(value) if value else placeholder(label)

    def shown(self, key: str) -> bool:
        if self.cfg.operator.get(key):
            return True
        if key in DEFERRED:
            return False
        return self.cfg.operator_form is None or key not in OPTIONAL


def deferred_missing(cfg: DatalabConfig) -> list[str]:
    """The deferred values (DEFERRED) still unset; the pages leave them out without a trace."""
    return [k for k in DEFERRED if not cfg.operator.get(k)]


# The build's stamp (M16 final review I1): a hash of everything the pages are rendered from but the
# counter, so golive-check can refuse a build made from other settings than the ones it checks.
STAMP_FILE = "build.json"
STAMP_KEY = "inputs_sha256"


def _shared_strings() -> tuple[str, str]:
    """The velometer strings the pages carry (credits), as rendered."""
    osm = str(i18n.t_markup("de", "site.footer.attribution", osm=credits.OSM_COPYRIGHT_URL))
    return osm, i18n.t("de", "credit.boundaries")


def inputs_stamp(cfg: DatalabConfig, site_dir: Path = SITE_DIR) -> str:
    """sha256 over what a build is made from, the counter aside: the validated settings, every
    file under `site_dir`'s `templates/` and `static/` (path and content), and the shared
    strings. A change to any of them makes an older build's stamp differ."""
    h = hashlib.sha256()
    h.update(json.dumps(cfg.model_dump(mode="json"), sort_keys=True).encode("utf-8"))
    for sub in ("templates", "static"):
        base = site_dir / sub
        files = sorted(p for p in base.rglob("*") if p.is_file()) if base.is_dir() else []
        for path in files:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            h.update(f"\n{path.relative_to(site_dir).as_posix()}\0{digest}".encode())
    for text in _shared_strings():
        h.update(b"\n" + text.encode("utf-8"))
    return h.hexdigest()


def read_stamp(out: Path) -> str | None:
    """The stamp a build recorded in its `build.json`; None when there is none."""
    try:
        value = json.loads((out / STAMP_FILE).read_text(encoding="utf-8")).get(STAMP_KEY)
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) else None


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
    osm, boundary = _shared_strings()
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
        "osm_credit": Markup(osm),
        "boundary_credit": boundary,
        "checked": (
            i18n.long_day(cfg.accessibility.checked, "de")
            if cfg.accessibility.checked
            else placeholder("Datum der Veröffentlichung")
        ),
    }
    env = _env()
    return {out: env.get_template(name).render(**context) for name, out in PAGES.items()}


def build(cfg: DatalabConfig, velometer_export: Path, out: Path) -> list[str]:
    """The site in `out` (absent or empty): pages, `static/`, `.gz` siblings and `_headers`.
    Everything is read and rendered before the first write. Returns the written paths, relative
    to `out`, sorted."""
    from velometer.app.export import headers_text, write_gz

    pages = render(cfg, read_counter(velometer_export))
    stamp = json.dumps({STAMP_KEY: inputs_stamp(cfg)}, indent=2) + "\n"
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
    (out / STAMP_FILE).write_text(stamp, encoding="utf-8")
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
