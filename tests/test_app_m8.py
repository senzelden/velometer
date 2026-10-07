"""M8 app pages: organisations, plans and the Berlin plan page (Task 9)."""

import csv
import json
import re
import sqlite3
from pathlib import Path

import pytest
import yaml
from markupsafe import escape

from tests.test_app import (  # noqa: F401 - `setup` is a fixture
    CONTENT,
    _client,
    _text,
    setup,
)
from tests.test_app_m7 import CSP, INLINE_CODE, INLINE_SCRIPT
from velometer.app.main import create_app
from velometer.content.loader import load_organisations
from velometer.db import OverlayRow, replace_plan_overlay
from velometer.plans.models import load_plans

M8_ROUTES = ["/organisations", "/plans", "/plans/berlin"]
ORGS = load_organisations(CONTENT / "organisations")


def _measures(*features: dict) -> dict:
    """A radverkehrsmassnahmen GeoJSON as `velometer plans fetch berlin` writes it."""

    def feature(props: dict) -> dict:
        base = {f"netz_art{i}": None for i in range(1, 6)}
        base |= {f"streckenlaenge{i}": None for i in range(1, 6)}
        base |= {"streckenlaenge": 0, "status": "Abgeschlossen", "bauende": "4. Quartal 2022"}
        geom = {"type": "MultiLineString", "coordinates": [[[390000, 5820000], [390100, 5820000]]]}
        return {"type": "Feature", "geometry": geom, "properties": base | props}

    return {"type": "FeatureCollection", "features": [feature(p) for p in features]}


MEASURES = _measures(
    {"netz_art1": "Vorrangnetz", "streckenlaenge1": 850, "bauende": "4. Quartal 2022"},
    {"netz_art1": "Sonstiges", "streckenlaenge1": 300, "netz_art2": "Vorrangnetz",
     "streckenlaenge2": 250, "bauende": "2. Quartal 2022"},
    {"netz_art1": "Ergänzungsnetz", "streckenlaenge1": 1200, "bauende": "1. Quartal 2023"},
    {"netz_art1": "Vorrangnetz", "streckenlaenge1": 9999, "status": "In Bau"},
)  # fmt: skip


@pytest.fixture
def plans_data(tmp_path) -> Path:
    d = tmp_path / "plans-data"
    (d / "berlin").mkdir(parents=True)
    (d / "berlin" / "radverkehrsmassnahmen.geojson").write_text(json.dumps(MEASURES))
    (d / "berlin" / "retrieved.json").write_text(
        json.dumps({"retrieved_at": "2026-10-07T10:40:42Z", "licence": "dl-de-zero-2.0"})
    )
    return d


def _app(setup, plans_data_dir):  # noqa: F811
    db_path, cfg, maps, docs = setup
    return create_app(db_path, cfg, maps, docs, content_dir=CONTENT, plans_data_dir=plans_data_dir)


@pytest.fixture
def client(setup, plans_data):  # noqa: F811
    with _client(_app(setup, plans_data)) as c:
        yield c


def _section(html: str, anchor: str) -> str:
    """The HTML of the element with id=anchor (a section or a table row; neither nests)."""
    m = re.search(rf'<(\w+)\b[^>]*\bid="{re.escape(anchor)}"', html)
    assert m, anchor
    return html[m.start() : html.index(f"</{m.group(1)}>", m.start())]


@pytest.mark.parametrize("path", M8_ROUTES)
def test_each_route_is_200_with_the_csp_and_no_inline_code(client, path):
    r = client.get(path)
    assert r.status_code == 200, path
    assert r.headers["content-security-policy"] == CSP
    assert not INLINE_SCRIPT.search(r.text), path
    assert not INLINE_CODE.search(r.text), path


@pytest.mark.parametrize("path", M8_ROUTES)
def test_no_page_repeats_an_element_id(client, path):
    ids = re.findall(r'\bid="([^"]+)"', client.get(path).text)
    assert len(ids) == len(set(ids)), sorted({i for i in ids if ids.count(i) > 1})


def test_plans_of_other_cities_have_no_page(client):
    assert client.get("/plans/paris").status_code == 404
    assert client.get("/plans/nowhere").status_code == 404


def test_nav_links_plans_and_organisations_and_marks_the_current_one(client):
    html = client.get("/plans").text
    nav = html[html.index('<nav class="site-nav"') : html.index("</nav>")]
    assert 'href="/plans" aria-current="page"' in nav
    assert 'href="/organisations"' in nav
    assert 'href="/organisations" aria-current="page"' in client.get("/organisations").text


# ---------- organisations ----------


def _plain(paragraph: str) -> str:
    """The start of a paragraph as the page shows it: escaped, `code` marked, up to its first
    citation marker."""
    text = " ".join(paragraph.split()).split(" [", 1)[0].split("[", 1)[0]
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", str(escape(text)))


def test_every_profile_renders_with_its_anchor_text_and_quotes(client):
    html = client.get("/organisations").text
    assert ORGS  # the shipped profiles
    for org in ORGS.values():
        sec = " ".join(_section(html, org.id).split())
        assert str(escape(org.name)) in sec, org.id
        for s in org.sections:
            assert str(escape(s.heading)) in sec, (org.id, s.heading)
            for p in s.paragraphs:
                assert _plain(p)[:60] in sec, (org.id, p[:40])
        assert sec.count('class="pullquote"') == len(org.quotes), org.id


def test_profile_dimensions_use_the_differences_labels(client):
    sec = _section(client.get("/organisations").text, "clean_cities")
    labels = yaml.safe_load((Path(__file__).parents[1] / "config" / "differences.yaml").read_text())
    first = labels["dimensions"][0]
    assert f"<dt>{str(escape(first['label']))}</dt>" in sec


def test_profile_citations_point_at_their_own_source_list(client):
    html = client.get("/organisations").text
    for org in ORGS.values():
        sec = _section(html, org.id)
        for target in re.findall(r'href="#([^"]+)"', sec):
            assert f'id="{target}"' in sec, (org.id, target)


def test_a_profile_names_the_figures_it_stands_behind(client):
    sec = _text(_section(client.get("/organisations").text, "senmvku"))
    assert "Berlin" in sec and 'href="/plans/berlin"' in _section(
        client.get("/organisations").text, "senmvku"
    )


def test_figures_rows_link_to_the_organisation_anchor(client):
    html = client.get("/city/berlin/figures").text
    table = html[html.index('<table class="diffs">') : html.index("</table>")]
    assert 'href="/organisations#clean_cities"' in table
    assert 'href="/organisations#ecf"' in table


# ---------- plans ----------


def test_city_pages_link_their_plan(client):
    assert 'href="/plans/berlin"' in client.get("/city/berlin").text
    assert 'href="/plans#paris"' in client.get("/city/paris/figures").text


def test_plans_table_has_a_row_per_city_with_plan_status_target_and_progress(client):
    html = client.get("/plans").text
    berlin = _text(_section(html, "berlin"))
    assert "Radverkehrsplan" in berlin and "current" in berlin
    assert 'href="/plans/berlin"' in _section(html, "berlin")
    assert "km per year" in berlin
    paris = _text(_section(html, "paris"))
    assert "Plan Vélo 2021-2026" in paris and "180" in paris


def _edit_plans(cfg: Path, edit) -> None:
    path = cfg / "plans" / "plans.yaml"
    plans = yaml.safe_load(path.read_text(encoding="utf-8"))
    path.write_text(yaml.safe_dump(edit(plans), allow_unicode=True), encoding="utf-8")


def _add_rows(cfg: Path, *rows: dict) -> None:
    path = cfg / "plans" / "reports.csv"
    with path.open(encoding="utf-8", newline="") as f:
        header = next(csv.reader(f))
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        for r in rows:
            w.writerow(r)


def test_a_city_without_a_plan_shows_a_note(setup, plans_data):  # noqa: F811
    _edit_plans(setup[1], lambda ps: [p for p in ps if p["city"] != "paris"])
    with _client(_app(setup, plans_data)) as c:
        paris = _text(_section(c.get("/plans").text, "paris"))
    assert "no plan recorded" in paris


def test_an_expired_plan_without_successor_says_so(setup, plans_data):  # noqa: F811
    def expire(ps):
        for p in ps:
            if p["city"] == "paris":
                p["status"], p["successor"] = "expired", None
        return ps

    _edit_plans(setup[1], expire)
    with _client(_app(setup, plans_data)) as c:
        paris = _text(_section(c.get("/plans").text, "paris"))
    assert "expired" in paris and "no successor found" in paris


def test_every_shipped_expired_plan_without_successor_is_labelled():
    from velometer.app.plans_pages import plans_table

    cfg = Path(__file__).parents[1] / "config"
    plans, rows = load_plans(cfg / "plans")
    cities = [(p.city, p.city.title()) for p in plans]
    table = plans_table(plans, rows, cities, ORGS)
    lonely = {p.city for p in plans if p.status != "current" and not p.successor}
    assert lonely  # Madrid, Barcelona, Oslo, Helsinki, Kraków at the time of writing
    for row in table:
        for plan in row["plans"]:
            assert ("no successor found" in plan["status_text"]) == (
                row["id"] in lonely and plan["plan"].status != "current"
            ), row["id"]


PARIS_ROW = {
    "plan_id": "paris_plan_velo_2021", "item_id": "pistes_securisees", "year": "2024",
    "value": "99", "unit": "km", "quantity": "implemented_cumulative", "doc_type": "web",
    "doc_id": "Fixture page", "doc_date": "2024-06-01", "url": "https://example.org/paris",
    "locator": "p. 1", "retrieved_at": "2026-10-07", "note": "a forecast, not a count",
    "publisher": "Ville de Paris", "suspect": "true", "cumulative_from": "2021",
}  # fmt: skip


def test_an_item_whose_only_row_is_suspect_still_shows_flagged_with_its_note(
    setup,  # noqa: F811
    plans_data,
):
    _add_rows(setup[1], PARIS_ROW)
    with _client(_app(setup, plans_data)) as c:
        sec = _section(c.get("/plans").text, "paris")
    text = _text(sec)
    assert "99" in text and "suspect" in text and "a forecast, not a count" in text
    assert "since 2021" in text  # a cumulative figure names its start year
    assert 'href="https://example.org/paris"' in sec


# ---------- the Berlin plan page ----------


def _config(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="plan-config">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def test_berlin_page_has_a_chart_mount_and_table_per_item(client):
    html = client.get("/plans/berlin").text
    plan = next(p for p in load_plans(CONTENT.parent / "config" / "plans")[0] if p.city == "berlin")
    config = _config(html)
    assert [i["id"] for i in config["items"]] == [i.id for i in plan.items]
    for item in plan.items:
        assert f'data-plan-item="{item.id}"' in html
        assert f'id="item-{item.id}"' in html


def test_an_item_without_target_gets_reported_markers_only(client):
    config = _config(client.get("/plans/berlin").text)
    total = next(i for i in config["items"] if i["id"] == "total")
    assert total["target_kind"] == "none" and total["targets"] == {}
    assert total["reports"]
    vrn = next(i for i in config["items"] if i["id"] == "vorrangnetz")
    assert vrn["targets"]["2022"] == 40


def test_document_table_lists_every_document_with_type_and_link(client):
    html = client.get("/plans/berlin").text
    docs = _section(html, "documents")
    _, rows = load_plans(CONTENT.parent / "config" / "plans")
    for r in (r for r in rows if r.plan_id == "berlin_rvp_2021"):
        assert str(escape(r.doc_id)) in docs, r.doc_id
        assert f'href="{escape(r.url)}"' in docs, r.doc_id
    assert "Drucksache" in docs and "rote Nummer" in docs


def test_revisions_are_listed_and_a_suspect_figure_is_flagged_with_its_note(client):
    html = client.get("/plans/berlin").text
    sec = _section(html, "item-ergaenzungsnetz")
    text = _text(sec)
    assert "55.1" in text and "suspect" in text and "revision" in text
    assert "stored as printed" in text  # the row's note
    erg = next(i for i in _config(html)["items"] if i["id"] == "ergaenzungsnetz")
    flagged = [r for r in erg["reports"] if r["value"] == 55.1]
    assert flagged and flagged[0]["suspect"] and not flagged[0]["current"]


def test_cumulative_series_show_their_start_year(client):
    text = _text(_section(client.get("/plans/berlin").text, "item-vorrangnetz"))
    assert "since 2017" in text and "since 2022" in text


def test_completed_projects_are_summed_by_end_year_and_class(client):
    config = _config(client.get("/plans/berlin").text)
    by_id = {i["id"]: i for i in config["items"]}
    assert by_id["vorrangnetz"]["projects"] == [{"year": 2022, "km": 1.1}]
    assert by_id["ergaenzungsnetz"]["projects"] == [{"year": 2023, "km": 1.2}]
    assert by_id["radverkehrsnetz"]["projects"] == [
        {"year": 2022, "km": 1.1},
        {"year": 2023, "km": 1.2},
    ]
    assert by_id["total"]["projects"] is None  # no network class of the dataset


def test_without_the_measures_file_the_page_says_so(setup, tmp_path):  # noqa: F811
    with _client(_app(setup, tmp_path / "absent")) as c:
        r = c.get("/plans/berlin")
    assert r.status_code == 200
    assert "measures dataset is not present" in _text(r.text)
    assert all(i["projects"] is None for i in _config(r.text)["items"])


def test_projects_follow_a_changed_measures_file(setup, plans_data):  # noqa: F811
    with _client(_app(setup, plans_data)) as c:
        first = _config(c.get("/plans/berlin").text)
        path = plans_data / "berlin" / "radverkehrsmassnahmen.geojson"
        path.write_text(
            json.dumps(_measures({"netz_art1": "Vorrangnetz", "streckenlaenge1": 4000}))
        )
        second = _config(c.get("/plans/berlin").text)
    vrn = [next(i for i in cfg["items"] if i["id"] == "vorrangnetz") for cfg in (first, second)]
    assert vrn[0]["projects"] == [{"year": 2022, "km": 1.1}]
    assert vrn[1]["projects"] == [{"year": 2022, "km": 4.0}]


def _berlin_runs(db_path: Path) -> list[tuple[int, str]]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT id, osm_timestamp FROM runs WHERE city_id='berlin' AND boundary_kind='lau' "
            "ORDER BY osm_timestamp"
        ).fetchall()
    finally:
        conn.close()


def _overlay(db_path: Path, version: str, km: float) -> None:
    conn = sqlite3.connect(db_path)
    try:
        rows = [
            OverlayRow(rid, "berlin", cls, tier, km + i, 800.0, version, "2026-10-07T10:40:42Z")
            for i, (rid, _ts) in enumerate(_berlin_runs(db_path))
            for cls in ("vorrangnetz", "ergaenzungsnetz")
            for tier in ("A", "B")
        ]
        replace_plan_overlay(conn, "berlin", rows)
    finally:
        conn.close()


def test_mapped_series_names_the_latest_overlay_version_and_its_caveat(setup, plans_data):  # noqa: F811
    _overlay(setup[0], "overlay_v2", 10.0)
    _overlay(setup[0], "overlay_v10", 100.0)  # v10 is later than v2 (numeric order)
    with _client(_app(setup, plans_data)) as c:
        html = c.get("/plans/berlin").text
    vrn = next(i for i in _config(html)["items"] if i["id"] == "vorrangnetz")
    runs = _berlin_runs(setup[0])
    assert [o["date"] for o in vrn["overlay"]] == [ts[:10] for _rid, ts in runs]
    assert vrn["overlay"][0]["ab_km"] == 200.0  # A + B of the latest version, first run
    sec = _text(_section(html, "item-vorrangnetz"))
    assert "overlay_v10" in sec and "overlay_v2" not in sec
    assert "not km of new infrastructure" in sec
    assert "mapped km" in sec


def test_without_overlay_rows_the_mapped_series_is_a_note(client):
    html = client.get("/plans/berlin").text
    vrn = next(i for i in _config(html)["items"] if i["id"] == "vorrangnetz")
    assert vrn["overlay"] is None
    assert "no plan overlay" in _text(_section(html, "item-vorrangnetz"))


def test_berlin_page_renders_the_cited_text_on_why_the_series_differ(client):
    html = client.get("/plans/berlin").text
    text = " ".join(html.split())
    doc = yaml.safe_load((CONTENT / "plans" / "berlin.yaml").read_text(encoding="utf-8"))
    for s in doc["sections"]:
        assert str(escape(s["heading"])) in text
        for p in s["paragraphs"]:
            assert _plain(p)[:60] in text
    assert text.count('class="pullquote"') == len(doc["quotes"])


def test_mapped_caption_states_the_change_since_the_baseline_in_mapped_km(setup, plans_data):  # noqa: F811
    """Spec §4.4: the mapped series is the change since 1 January of the plan's first target
    year; the caption states it, to the latest snapshot, in mapped km."""
    runs = _berlin_runs(setup[0])
    jan = [ts[:10] for _rid, ts in runs if ts[5:10] == "01-01"]
    assert jan  # the fixture has 1 January snapshots
    base = int(jan[0][:4])

    def rebase(ps):
        for p in ps:
            if p["city"] == "berlin":
                for item in p["items"]:
                    if item.get("targets"):
                        item["targets"] = {base + k: v for k, v in enumerate([10, 20])}
        return ps

    _edit_plans(setup[1], rebase)
    _overlay(setup[0], "overlay_v4", 50.0)  # A+B = 2 * (50 + run index)
    with _client(_app(setup, plans_data)) as c:
        html = c.get("/plans/berlin").text
    first = next(i for i, (_r, ts) in enumerate(runs) if ts[:10] == f"{base}-01-01")
    change = 2 * ((len(runs) - 1) - first)
    sec = _text(_section(html, "item-vorrangnetz"))
    assert f"since 1 January {base}, +{change:.1f} mapped km to the current snapshot of " in sec
    assert runs[-1][1][:10] in sec
