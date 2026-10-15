"""M8 app pages: organisations, plans and the Berlin plan page (Task 9)."""

import csv
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

import pytest
import yaml
from markupsafe import escape

from tests.test_app import (  # noqa: F401 - `setup` is a fixture
    CONTENT,
    _client,
    _text,
    nolabels,
    setup,
)
from tests.test_app_m7 import CSP, INLINE_CODE, INLINE_SCRIPT, STATIC
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


# the record `velometer plans fetch berlin` writes beside the layers (plans/berlin.py); the
# licence is a value no template could hold, so a page showing it read it from the record
RETRIEVED = {
    "retrieved_at": "2026-10-07T10:40:42Z",
    "licence": "test-licence-from-record",
    "licence_url": "https://example.org/licence",
    "srs": "EPSG:25833",
    "layers": {
        name: {"url": f"https://example.org/{name}", "type_name": f"{name}:{name}",
               "record": "https://example.org/record", "features": 1}
        for name in ("radverkehrsnetz", "radverkehrsmassnahmen")
    },
}  # fmt: skip


@pytest.fixture
def plans_data(tmp_path) -> Path:
    d = tmp_path / "plans-data"
    (d / "berlin").mkdir(parents=True)
    (d / "berlin" / "radverkehrsmassnahmen.geojson").write_text(json.dumps(MEASURES))
    (d / "berlin" / "retrieved.json").write_text(json.dumps(RETRIEVED))
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


def test_the_german_document_title_renders_in_italics_with_its_translation(client):
    html = " ".join(client.get("/organisations").text.split())
    title = "Acht Jahre Mobilitätsgesetz – Zwischen Anspruch und Wirklichkeit im Radverkehr"
    assert f"Drucksache 19/25987, <em>{title}</em> (Eight years of the Mobility Act:" in html


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
    table = html[html.index('<table class="diffs stack figures">') : html.index("</table>")]
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
        replace_plan_overlay(conn, "berlin", version, rows)
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


def test_mapped_caption_states_the_change_since_the_baseline_in_mapped_km(
    setup,  # noqa: F811
    plans_data,
    monkeypatch,
):
    """Spec §4.4: the mapped series is the change since MAPPED_BASELINE (1 January 2022); the
    caption states it, to the latest snapshot, in mapped km. The fixture's snapshots start later,
    so the baseline is moved onto its first 1 January snapshot."""
    from velometer.app import plans_pages

    runs = _berlin_runs(setup[0])
    jan = [ts[:10] for _rid, ts in runs if ts[5:10] == "01-01"]
    assert jan  # the fixture has 1 January snapshots
    base = int(jan[0][:4])
    monkeypatch.setattr(plans_pages, "MAPPED_BASELINE", date(base, 1, 1))
    _overlay(setup[0], "overlay_v4", 50.0)  # A+B = 2 * (50 + run index)
    with _client(_app(setup, plans_data)) as c:
        html = c.get("/plans/berlin").text
    first = next(i for i, (_r, ts) in enumerate(runs) if ts[:10] == f"{base}-01-01")
    change = 2 * ((len(runs) - 1) - first)
    sec = _text(_section(html, "item-vorrangnetz"))
    assert f"since 1 January {base}, +{change:.1f} mapped km to the current snapshot of " in sec
    assert runs[-1][1][:10] in sec
    assert _config(html)["mapped_from"] == base


def test_the_baseline_is_mapped_baseline_not_the_plans_first_target_year(setup, plans_data):  # noqa: F811
    """Spec §4.4 names the day (MAPPED_BASELINE); a plan whose first target year is that of a
    snapshot does not move the baseline onto it."""
    from velometer.plans.models import MAPPED_BASELINE

    runs = _berlin_runs(setup[0])
    jan = sorted({ts[:4] for _rid, ts in runs if ts[5:10] == "01-01"})
    assert f"{MAPPED_BASELINE.year}" not in jan  # no snapshot on the baseline in the fixture
    first = int(jan[0])

    def rebase(ps):
        for p in ps:
            if p["city"] == "berlin":
                for item in p["items"]:
                    if item.get("targets"):
                        item["targets"] = {first + k: v for k, v in enumerate([10, 20])}
        return ps

    _edit_plans(setup[1], rebase)
    _overlay(setup[0], "overlay_v4", 50.0)
    with _client(_app(setup, plans_data)) as c:
        html = c.get("/plans/berlin").text
    sec = _text(_section(html, "item-vorrangnetz"))
    assert f"since 1 January {MAPPED_BASELINE.year}." in sec  # no change: no baseline snapshot
    assert f"since 1 January {first}" not in sec
    assert _config(html)["mapped_from"] == MAPPED_BASELINE.year
    vrn = next(i for i in _config(html)["items"] if i["id"] == "vorrangnetz")
    assert vrn["overlay"]  # the series is drawn, only its difference column is empty


def test_overlay_table_column_is_the_difference_from_the_baseline(setup, plans_data):  # noqa: F811
    # snapshots before the baseline are in the table too: "change since 1 Jan" misreads them,
    # "difference from 1 Jan" reads right on both sides (render check, Task 11)
    _overlay(setup[0], "overlay_v4", 50.0)
    with _client(_app(setup, plans_data)) as c:
        html = c.get("/plans/berlin").text
    head = html[html.index('<table class="plan-overlay stack">') :].split("</thead>")[0]
    assert re.search(r"Difference from 1 Jan \d{4}</th>", head)
    assert "Change since" not in head


def test_plan_tables_fit_a_phone_width(client):
    # Task 11 render check: at 390 px the plan tables were cut at the right. At phone width
    # the headers wrap, long cell text breaks, and the documents table is a stack with labels
    html = client.get("/plans/berlin").text
    docs = html[html.index('<table class="plan-docs stack">') :].split("</table>")[0]
    body = docs.split("<tbody>")[1]
    cells = re.findall(r"<td\b[^>]*>", body)
    assert cells and all("data-label=" in c for c in cells)
    css = (STATIC / "app.css").read_text()
    narrow = css[css.index("/* plan tables at phone width */") :]
    narrow = narrow[: narrow.index("\n}\n")]
    assert "@media (max-width: 600px)" in narrow
    assert re.search(r"\.plan-item th[^{]*\{[^}]*white-space: normal", narrow)
    assert re.search(r"\.plan-item td[^{]*\{[^}]*overflow-wrap: anywhere", narrow)


# ---------- notes for unreadable inputs, licences (M8 follow-ups, Task 2) ----------


def _data_line(html: str, start: str) -> str:
    """The text of the Data list item that starts with `start`."""
    items = re.findall(r"<li>(.*?)</li>", _section(html, "documents").split("<h3>Data</h3>")[1])
    return next(_text(i) for i in items if _text(i).startswith(start))


def test_planned_network_line_names_the_licence_of_its_record(client):
    html = client.get("/plans/berlin").text
    line = _data_line(html, "Planned network:")
    assert f"licence {RETRIEVED['licence']}" in line
    assert f"licence {RETRIEVED['licence']}" in _data_line(html, "Measures dataset:")


def test_a_record_without_the_network_layer_does_not_lend_it_its_licence(setup, plans_data):  # noqa: F811
    record = {
        **RETRIEVED,
        "layers": {"radverkehrsmassnahmen": RETRIEVED["layers"]["radverkehrsmassnahmen"]},
    }
    (plans_data / "berlin" / "retrieved.json").write_text(json.dumps(record))
    with _client(_app(setup, plans_data)) as c:
        html = c.get("/plans/berlin").text
    line = _data_line(html, "Planned network:")
    assert RETRIEVED["licence"] not in line and "licence not recorded" in line


@pytest.mark.parametrize(
    "body",
    ["{not json", "[]", json.dumps({"retrieved_at": "2026-10-07T10:40:42Z"})],
    ids=["not-json", "not-an-object", "no-licence"],
)
def test_an_unreadable_source_record_is_a_note_not_missing_licences(
    setup,  # noqa: F811
    plans_data,
    body,
    caplog,
):
    (plans_data / "berlin" / "retrieved.json").write_text(body)
    with _client(_app(setup, plans_data)) as c:
        r = c.get("/plans/berlin")
    assert r.status_code == 200
    text = _text(_section(r.text, "documents"))
    assert "data source record unreadable" in text
    assert "retrieved.json" in caplog.text  # the detail goes to the log


def test_a_readable_or_absent_source_record_has_no_note(setup, plans_data, tmp_path):  # noqa: F811
    with _client(_app(setup, plans_data)) as c:
        assert "data source record unreadable" not in _text(c.get("/plans/berlin").text)
    with _client(_app(setup, tmp_path / "absent")) as c:
        assert "data source record unreadable" not in _text(c.get("/plans/berlin").text)


def test_an_absent_source_record_never_leaves_a_drawn_network_unattributed(setup, tmp_path):  # noqa: F811
    # fresh checkout: the overlay rows are in the (tracked) DB, retrieved.json is in the
    # git-ignored data dir. The planned-network series is drawn, so its line must say that
    # its licence is not recorded instead of naming nothing (ADR 0008)
    _overlay(setup[0], "overlay_v4", 50.0)
    with _client(_app(setup, tmp_path / "absent")) as c:
        html = c.get("/plans/berlin").text
    line = _data_line(html, "Planned network:")
    assert "overlay_v4" in line, "the overlay is shown"
    assert "licence not recorded" in line


def test_a_broken_source_registry_is_a_note_on_the_plan_page(setup, plans_data, tmp_path):  # noqa: F811
    import shutil

    content = tmp_path / "content"
    shutil.copytree(CONTENT, content)
    db_path, cfg, maps, docs = setup

    def page() -> str:
        app = create_app(db_path, cfg, maps, docs, content_dir=content, plans_data_dir=plans_data)
        with _client(app) as c:
            return _text(c.get("/plans/berlin").text)

    note = "the source registry could not be loaded (see the server log)"
    assert note not in page()
    (content / "sources" / "zz-broken.yaml").write_text("sources: [unclosed\n")
    text = page()
    assert note in text
    assert text.count(note) == 1


# ---------- M8 follow-ups, Task 4 ----------


def _in_page_links(html: str) -> list[str]:
    return re.findall(r'href="#([^"]+)"', html)


def _dangling(html: str) -> list[str]:
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    return sorted(a for a in _in_page_links(html) if a not in ids)


def test_every_in_page_link_on_the_berlin_page_has_its_anchor(client):
    # the key's links ("reported", "completed projects", "mapped on the network") and the
    # mapped notes' "why" point at the explainer sections, whose ids come from berlin.yaml's
    # `dimension` values: the rule is over every in-page link, not a list of today's anchors
    html = client.get("/plans/berlin").text
    key = html[html.index('class="plan-key"') :].split("</div>")[0]
    assert _in_page_links(key), "the key links the three series"
    assert _dangling(html) == []


@pytest.mark.parametrize("change", ["rename", "drop"])
def test_key_links_never_dangle_when_the_page_text_changes(setup, plans_data, tmp_path, change):  # noqa: F811
    # a renamed dimension, or no page text at all: the key names the series without a link
    import shutil

    content = tmp_path / "content"
    shutil.copytree(CONTENT, content)
    text = content / "plans" / "berlin.yaml"
    if change == "rename":
        doc = yaml.safe_load(text.read_text())
        for s in doc["sections"]:
            s["dimension"] = f"{s['dimension']}-renamed"
        text.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
    else:
        text.write_text("title: [unclosed\n")
    db_path, cfg, maps, docs = setup
    app = create_app(db_path, cfg, maps, docs, content_dir=content, plans_data_dir=plans_data)
    with _client(app) as c:
        html = c.get("/plans/berlin").text
    assert _dangling(html) == []
    key = _text(html[html.index('class="plan-key"') :].split("</div>")[0])
    assert "reported" in key and "completed projects" in key and "mapped on the network" in key


def test_every_target_value_is_in_the_year_table(client):
    # off-scale targets are capped in the chart (plan-chart.js): the table keeps every value
    html = nolabels(client.get("/plans/berlin").text)
    plan = next(p for p in load_plans(CONTENT.parent / "config" / "plans")[0] if p.city == "berlin")
    for item in plan.items:
        sec = _section(html, f"item-{item.id}")
        for year, value in item.targets.items():
            row = re.search(
                rf"<tr>\s*<td class=\"num\">{year}</td>\s*<td class=\"num\">([^<]*)<", sec
            )
            assert row, (item.id, year)
            assert row.group(1).replace(",", "").startswith(f"{value:g} "), (item.id, year, row)


# ---------- colour tokens (M8 follow-ups, Task 5) ----------

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
COLOUR_FN = re.compile(r"(?<![\w-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(", re.I)
# the CSS named colours; `transparent`, `currentColor` and `inherit` are allowed (not colours)
NAMED = (  # noqa: SIM905 - one word list reads better than 148 quoted names
    "aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue "
    "blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk "
    "crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki "
    "darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen "
    "darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue "
    "dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite "
    "gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki "
    "lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan "
    "lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen "
    "lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen "
    "magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen "
    "mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream "
    "mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid "
    "palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum "
    "powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown "
    "seagreen seashell sienna silver skyblue slateblue slategray slategrey snow springgreen "
    "steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow "
    "yellowgreen"
).split()
NAMED_COLOUR = re.compile(rf"(?<![\w-])(?:{'|'.join(NAMED)})(?![\w-])", re.I)


def _colour_literal(value: str) -> bool:
    return bool(HEX.search(value) or COLOUR_FN.search(value) or NAMED_COLOUR.search(value))


def _stylesheet() -> str:
    return (STATIC / "app.css").read_text()


def test_no_colour_literal_outside_the_colour_tokens():
    # every colour is a token, defined in the light :root and the dark block: a literal in a rule
    # (hex, rgb()/hsl()/..., or a named colour) is a colour that changes in one place and not
    # the others, and that no theme redefines. Over the whole stylesheet, M7 rules included
    from tests.test_app import _css_outside_tokens, _css_rules

    rest = _css_outside_tokens(_stylesheet())
    found = [
        (sel, prop, value)
        for sels, decls in _css_rules(rest)
        for sel in sels[:1]
        for prop, value in decls.items()
        if _colour_literal(value)
    ]
    assert found == []


def test_the_literal_rule_sees_every_kind_of_colour():
    for literal in ("#fff", "rgb(0 0 0 / 0.1)", "rgba(0,0,0,.1)", "hsl(0 0% 0%)", "white",
                    "1px solid Grey", "0 4px 16px black"):  # fmt: skip
        assert _colour_literal(literal), literal
    for fine in ("transparent", "currentColor", "inherit", "var(--ink)", "nowrap",
                 "underline wavy var(--flag)", "1px solid var(--grid)"):  # fmt: skip
        assert not _colour_literal(fine), fine


def test_every_token_used_is_defined():
    from tests.test_app import _css_outside_tokens, _css_tokens

    tokens = _css_tokens(_stylesheet())
    used = set(re.findall(r"var\((--[\w-]+)\)", _css_outside_tokens(_stylesheet())))
    assert sorted(used - tokens.keys()) == []


def _rgb(hexcolour: str) -> tuple[float, float, float]:
    h = hexcolour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    srgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


def _lch_hue(hexcolour: str) -> float:
    """The CIELAB hue angle (D65) of an sRGB colour, in degrees."""
    import math

    r, g, b = _rgb(hexcolour)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

    a_, b_ = 500 * (f(x) - f(y)), 200 * (f(y) - f(z))
    return math.degrees(math.atan2(b_, a_)) % 360


# Hue distance between the mapped line and the plan chart's other colours. The M8 amber was
# 28 degrees of CIELAB hue from --flag (the suspect ring, orange) and read as its shade; 60
# degrees, a sixth of the circle, puts two colours in different hue families (orange, magenta,
# blue, green), whatever their lightness
MIN_HUE_DEGREES = 60


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_mapped_colour_is_apart_from_the_other_plan_chart_colours(theme):
    # the colours the plan chart actually draws with: every token its `.plan-svg` rules stroke
    # or fill, apart from the greys (ink, grid, halo), whose hue is noise
    from tests.test_app import _css_rules, _css_tokens

    tokens = _css_tokens(_stylesheet(), theme)
    drawn = {
        t
        for sels, decls in _css_rules(_stylesheet())
        if any(s.startswith(".plan-svg ") for s in sels)
        for p, v in decls.items()
        if p in ("fill", "stroke")
        for t in re.findall(r"var\((--[\w-]+)\)", v)
    } - {"--ink", "--ink-2", "--grid", "--grid-2", "--halo"}
    assert {"--mapped", "--series-1", "--flag", "--completed"} <= drawn
    mapped = _lch_hue(tokens["--mapped"])
    for other in sorted(drawn - {"--mapped"}):
        d = abs(mapped - _lch_hue(tokens[other])) % 360
        assert min(d, 360 - d) >= MIN_HUE_DEGREES, (other, round(min(d, 360 - d)))


def test_the_plan_chart_and_its_key_draw_with_the_same_tokens():
    # the key's swatch and the chart's mark are one token: a colour changed in one place
    # changes both
    from tests.test_app import _css_rules

    decl: dict[str, dict] = {}
    for sels, d in _css_rules(_stylesheet()):
        for s in sels:
            decl.setdefault(s, {}).update(d)
    assert decl[".plan-svg .mapped-line"]["stroke"] == "var(--mapped)"
    assert decl[".plan-svg .mapped-pt"]["fill"] == "var(--mapped)"
    assert decl[".key-mapped"]["border-top"].endswith("var(--mapped)")
    assert decl[".mapped-note"]["border-left"].endswith("var(--mapped)")
    assert decl[".plan-svg .projects .bar"]["fill"] == "var(--completed)"
    assert decl[".key-projects"]["border"].endswith("var(--completed)")
    cap = decl[".plan-svg .target-cap"]["stroke"]
    assert cap.startswith("var(") and decl[".key-cap"]["border-top"].endswith(cap)


def test_the_plan_key_explains_the_capped_marker(client):
    # plan-chart.js draws a target above the chart's scale as a cap on the top edge, labelled
    # "↑ <value>": the key says what the cap and the arrow mean and where the value is
    html = client.get("/plans/berlin").text
    key = html[html.index('class="plan-key"') :].split("</div>")[0]
    items = re.findall(r"<li\b[^>]*>(.*?)</li>", key, re.S)
    cap = [i for i in items if 'class="key key-cap"' in i]
    assert len(cap) == 1
    text = _text(cap[0])
    assert "↑" in text and "above the chart's scale" in text and "table" in text


# --- quote language (M10 spec decision 6, Language) ---
def _src(language="de", gloss="cycle paths"):
    from velometer.content.models import Excerpt, Source

    return {"s": Source(id="s", publisher="P", title="T", url="https://example.org/",
                        accessed="2026-01-01", language=language, kind="press",
                        excerpts=[Excerpt(id="e", text="Radwege", gloss_en=gloss,
                                          locator="p. 1")])}  # fmt: skip


def test_a_pullquote_carries_the_language_of_its_source_and_its_gloss_is_english():
    from velometer.app.narrative import pullquote

    html = str(pullquote(_src(), "s/e"))
    assert '<blockquote lang="de">' in html
    assert '<span class="gloss" lang="en">cycle paths</span>' in html
    # an English source needs no gloss, and the quote still says what it is written in
    en = str(pullquote(_src("en", None), "s/e"))
    assert '<blockquote lang="en">' in en and "gloss" not in en


def _para(text):
    from velometer.app.narrative import _Numbering

    return str(_Numbering({}, {}).paragraph(text))


def test_content_may_mark_an_inline_quote_with_its_language():
    assert _para('He said <q lang="de">Radwege</q> twice.') == (
        '<p>He said <q lang="de">Radwege</q> twice.</p>'
    )
    assert _para('<blockquote lang="fr">Les pistes.</blockquote>') == (
        '<blockquote lang="fr"><p>Les pistes.</p></blockquote>'
    )


@pytest.mark.parametrize(
    "text",
    [
        '<q lang="de" onclick="x()">a</q>',  # no other attribute
        '<q lang="de&quot; onclick=&quot;x">a</q>',  # the value is a language tag, nothing else
        '<q lang="d e">a</q>',
        "<q>a</q>",  # no language, no tag
        '<span lang="de">a</span>',  # only the two quote tags
        '<q lang="de">unclosed',
        'a <blockquote lang="de">mid-paragraph</blockquote> b',  # a block only as a paragraph
        '<script lang="de">x</script>',
    ],
)
def test_nothing_but_a_language_marked_quote_reaches_the_page_as_markup(text):
    out = _para(text)
    assert "<" not in re.sub(r"</?p>", "", out), out  # every tag was escaped to text
