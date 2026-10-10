import hashlib
from pathlib import Path

from velometer.app import export

ROOT = Path(__file__).resolve().parents[1]
AXE = ROOT / "tools" / "axe"


def test_axe_is_pinned_and_unchanged():
    version, sha, *_ = (AXE / "VERSION").read_text().split()
    assert version.count(".") == 2
    assert hashlib.sha256((AXE / "axe.min.js").read_bytes()).hexdigest() == sha
    assert "Mozilla Public License" in (AXE / "LICENSE").read_text()


def test_axe_is_never_served_or_exported(tmp_path):
    # the export copies the app's static/ only; axe lives outside it
    static = Path(export.__file__).parent / "static"
    assert not any(p.name.startswith("axe") for p in static.rglob("*"))


def test_page_urls_finds_every_exported_page(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("render_pass", ROOT / "tools" / "render_pass.py")
    rp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rp)
    for rel in ["index.html", "cities/index.html", "city/berlin/tiers/index.html", "404.html"]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("<html></html>")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x.csv").write_text("a")
    urls = rp.page_urls(tmp_path, "/velometer/")
    assert urls == ["/velometer/", "/velometer/cities", "/velometer/city/berlin/tiers"]


def test_page_urls_skips_fragments(tmp_path):
    # a city panel is an HTML fragment loaded into a page, not a page to visit
    import importlib.util

    spec = importlib.util.spec_from_file_location("render_pass", ROOT / "tools" / "render_pass.py")
    rp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rp)
    (tmp_path / "index.html").write_text("<!doctype html>\n<html lang='en'></html>")
    (tmp_path / "city" / "berlin" / "panel").mkdir(parents=True)
    (tmp_path / "city" / "berlin" / "panel" / "index.html").write_text('<div class="panel-frag">')
    assert rp.page_urls(tmp_path, "/velometer/") == ["/velometer/"]


def test_type_urls_keeps_berlin_and_the_first_city_with_other_tabs():
    import importlib.util

    spec = importlib.util.spec_from_file_location("render_pass", ROOT / "tools" / "render_pass.py")
    rp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rp)
    b = "/velometer/"
    urls = [b, b + "plans", b + "plans/berlin"]
    for slug, tabs in [
        ("amsterdam", ["", "/time"]),
        ("berlin", ["", "/time", "/counts"]),
        ("bordeaux", ["", "/time"]),
        ("paris", ["", "/time", "/counts"]),
    ]:
        urls += [f"{b}city/{slug}{t}" for t in tabs]
    kept = rp.type_urls(sorted(urls), b)
    cities = {u.split("/")[3] for u in kept if "/city/" in u}
    assert cities == {"berlin", "amsterdam"}
    assert {b, b + "plans", b + "plans/berlin", b + "city/berlin/counts"} <= set(kept)
    assert len(kept) == 3 + 3 + 2
