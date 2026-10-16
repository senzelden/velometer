"""M14 task 1: `config/site.yaml`, the Datalab footer line and `app export --public`."""

import json
import re
from pathlib import Path

import pytest
import yaml

from tests.test_app import CONTENT, _client, app_inputs
from tests.test_app_base import rich  # noqa: F401  (a fixture)
from tests.test_export import _content
from velometer import i18n
from velometer.app import export
from velometer.app.main import create_app
from velometer.config import ConfigError, SiteConfig, default_config_dir, load_site

COMPLETE = {
    "datalab": {"name": "Zählwerk Berlin Datalab", "url": "https://datalab.example.org/"},
    "impressum_url": "https://datalab.example.org/impressum",
    "privacy_url": "https://datalab.example.org/datenschutz",
}


def _write_site(cfg: Path, doc: dict) -> None:
    (cfg / "site.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")


def _load(tmp_path: Path, doc: dict) -> SiteConfig:
    _write_site(tmp_path, doc)
    return load_site(tmp_path)


def test_shipped_site_yaml_is_empty():
    site = load_site(default_config_dir())
    assert site == SiteConfig()
    assert site.datalab is None and site.impressum_url is None and site.privacy_url is None
    assert not site.complete


def test_missing_file_is_empty(tmp_path):
    assert load_site(tmp_path) == SiteConfig()


def test_complete(tmp_path):
    assert _load(tmp_path, COMPLETE).complete


@pytest.mark.parametrize(
    ("doc", "field"),
    [
        ({"datalab": {"name": "X"}}, "datalab.url"),
        ({"datalab": {"url": "https://a.example/"}}, "datalab.name"),
        (
            {"impressum_url": "https://a.example/i"},
            "impressum_url and privacy_url must be set together",
        ),
        (
            {"privacy_url": "https://a.example/p"},
            "impressum_url and privacy_url must be set together",
        ),
        ({**COMPLETE, "impressum_url": "http://a.example/i"}, "http://a.example/i"),
        ({"datalab": {"name": "X", "url": "https://"}}, "https://"),
        ({"datalab": None, "colour": "red"}, "colour"),
    ],
)
def test_validation_names_the_field(tmp_path, doc, field):
    with pytest.raises(ConfigError, match=re.escape(field)):
        _load(tmp_path, doc)


@pytest.fixture
def inputs(fixture_db, tmp_path):
    return app_inputs(*fixture_db[:2], tmp_path)


def _footer(html: str) -> str:
    return html.split("<footer>")[1].split("</footer>")[0]


def _footers(inputs, doc: dict | None) -> dict[str, str]:
    db_path, cfg, maps, docs = inputs
    assert cfg.resolve() != default_config_dir().resolve()
    if doc is not None:
        _write_site(cfg, doc)
    with _client(create_app(db_path, cfg, maps, docs, content_dir=CONTENT)) as c:
        return {"en": _footer(c.get("/").text), "de": _footer(c.get("/de/").text)}


def test_footer_with_complete_settings(inputs):
    footers = _footers(inputs, COMPLETE)
    name, url = COMPLETE["datalab"]["name"], COMPLETE["datalab"]["url"]
    for lang, privacy in (("en", "Privacy"), ("de", "Datenschutz")):
        f = footers[lang]
        assert re.search(rf'<a href="{re.escape(url)}">[^<]*{name}[^<]*</a>', f)
        assert f'<a href="{COMPLETE["impressum_url"]}">' in f
        assert re.search(rf'<a href="{re.escape(COMPLETE["privacy_url"])}">{privacy}</a>', f)
    assert re.search(r'<a href="[^"]*impressum">\s*<i lang="de">Impressum</i></a>', footers["en"])
    assert "Teil von" in footers["de"] and "Part of" in footers["en"]
    assert 'lang="de"' not in footers["de"]


def test_footer_without_settings_has_no_datalab_line(inputs):
    for lang, f in _footers(inputs, None).items():
        # the line's own words, from the catalogue (the name filled in with a marker)
        prefix = i18n.t(lang, "site.footer.datalab", name="\x00").split("\x00")[0]
        assert prefix.strip()
        assert prefix not in f
        assert "Impressum" not in f
        # attribution and run lines only: the fixture has no static edition
        assert f.count("<p>") == 2


def test_footer_datalab_line_comes_first(inputs):
    f = _footers(inputs, COMPLETE)["en"]
    assert f.index("Part of") < f.index("OpenStreetMap")


def _export(rich, out: Path, public: bool):  # noqa: F811
    db_path, cfg, maps, docs, plans = rich
    return export.run_export(
        out, "/", db_path, cfg, maps, docs, _content(rich), plans, False, public=public
    )


def test_public_export_refuses_empty_settings(rich, tmp_path):  # noqa: F811
    out = tmp_path / "site"
    with pytest.raises(export.ExportError) as e:
        _export(rich, out, True)
    for name in ("datalab.name", "datalab.url", "impressum_url", "privacy_url"):
        assert name in str(e.value)
    assert not out.exists()


def test_public_export_stamps_true(rich, tmp_path):  # noqa: F811
    _write_site(rich[1], COMPLETE)
    out = tmp_path / "site"
    _export(rich, out, True)
    assert json.loads((out / "build.json").read_text())["public"] is True


def test_plain_export_stamps_false(rich, tmp_path):  # noqa: F811
    out = tmp_path / "site"
    _export(rich, out, False)
    assert json.loads((out / "build.json").read_text())["public"] is False
