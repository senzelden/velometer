import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import yaml

from tests.report_fixture import build_report_fixture, build_report_fixture_n
from velometer.config import default_config_dir
from velometer.report.data import ReportData, open_readonly


def make_source(language: str, gloss_en: str | None = "Gloss", gloss_de: str | None = None):
    """A one-excerpt `Source` ("s", excerpt "e") in `language`: the shared synthetic source."""
    from velometer.content.models import Source

    excerpt = {"id": "e", "text": "Quote.", "gloss_en": gloss_en, "locator": "p. 1"}
    if gloss_de is not None:
        excerpt["gloss_de"] = gloss_de
    return Source(id="s", publisher="P", title="T", url="https://example.org/",
                  accessed="2026-01-01", language=language, kind="press",
                  excerpts=[excerpt])  # fmt: skip


def pytest_collection_modifyitems(items):
    """Slow tests (network, full-size data) run without the suite's per-test timeout."""
    for item in items:
        if item.get_closest_marker("slow") and not item.get_closest_marker("timeout"):
            item.add_marker(pytest.mark.timeout(0))


@pytest.fixture
def fixture_db(tmp_path):
    """The shared report fixture: (db_path, config_dir, read-only connection, ReportData)."""
    db_path, cfg = build_report_fixture(tmp_path)
    conn = open_readonly(db_path)
    yield db_path, cfg, conn, ReportData(conn, cfg)
    conn.close()


def app_for(setup, *, content=None, name_de: dict[str, str] | None = None):
    """A TestClient of a fresh app on the `setup` paths (test_app's (db, config, maps, docs)),
    reading `content` (default: the shipped content). `name_de` ({city id: German name}) is
    written into the fixture's own config copy's cities.yaml, never the real config."""
    from tests.test_app import CONTENT, _client
    from velometer.app.main import create_app

    db_path, cfg, maps, docs = setup
    if name_de:
        assert cfg.resolve() != default_config_dir().resolve(), "never edit the real config"
        doc = yaml.safe_load((cfg / "cities.yaml").read_text(encoding="utf-8"))
        for city in doc["cities"]:
            if city["id"] in name_de:
                city["name_de"] = name_de[city["id"]]
        (cfg / "cities.yaml").write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    return _client(create_app(db_path, cfg, maps, docs, content_dir=content or CONTENT))


@dataclass(frozen=True)
class PageSite:
    """Every HTML page of the export of the `client` app, rendered once: `html` maps each
    URL (both language trees, panels included) to its body and `status` to its status code;
    `data` is that app's ReportData."""

    html: dict[str, str]
    status: dict[str, int]
    data: ReportData


@pytest.fixture(scope="session")
def page_site(tmp_path_factory):
    """The pages the whole-site rule tests read (a11y, cites, language links), rendered once
    per session from the same inputs as `client` (test_app.app_inputs). Read-only: a test that
    changes the app's inputs builds its own client."""
    from tests.test_app import CONTENT, _client, app_inputs
    from velometer.app import export
    from velometer.app.main import create_app

    tmp = tmp_path_factory.mktemp("page_site")
    db_path, cfg = build_report_fixture(tmp)
    inputs = app_inputs(db_path, cfg, tmp)
    conn = open_readonly(db_path)
    data = ReportData(conn, cfg)
    with _client(create_app(*inputs, content_dir=CONTENT)) as c:
        html, status = {}, {}
        for url in export.export_urls(data, c.app):
            r = c.get(url)
            if r.headers["content-type"].startswith("text/html"):
                html[url], status[url] = r.text, r.status_code
    yield PageSite(html, status, data)
    conn.close()


@pytest.fixture
def report_db_with_trust(tmp_path):
    """Factory `(countries) -> (db_path, config_dir)`: the report fixture whose config copy's
    trust.yaml lists exactly `countries` (ISO2 -> CountryTrust fields); the rest are pending."""

    def build(countries: dict[str, dict]):
        db_path, cfg = build_report_fixture(tmp_path)
        trust = yaml.safe_load((cfg / "trust.yaml").read_text())
        trust["countries"] = countries
        (cfg / "trust.yaml").write_text(yaml.safe_dump(trust))
        return db_path, cfg

    return build


@pytest.fixture
def report_db_21(tmp_path):
    """(db_path, config_dir) of the report fixture grown to 21 cities (berlin, paris, c03..c21)."""
    return build_report_fixture_n(tmp_path, 21)


@pytest.fixture
def agent_server():
    """A local HTTP server on 127.0.0.1: `(base_url, agents)`, `agents` the User-Agent header of
    each request it answered (GET or POST, answered with a small JSON body)."""
    agents: list[str | None] = []

    class Handler(BaseHTTPRequestHandler):
        def _answer(self):
            agents.append(self.headers.get("User-Agent"))
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                self.rfile.read(n)
            body = b'{"data": {}}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = _answer

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/x", agents
    server.shutdown()
    server.server_close()
