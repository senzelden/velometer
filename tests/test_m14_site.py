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
    "repo": {
        "url": "https://forge.example.org/owner/velometer",
        "file_url": "https://forge.example.org/owner/velometer/blob/{commit}/{path}",
    },
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


def test_the_datalab_name_carries_its_language_when_site_yaml_gives_one(inputs):
    # final review M8: "Zählwerk Berlin Datalab" is a German name; "Part of" stays English
    doc = {**COMPLETE, "datalab": {**COMPLETE["datalab"], "lang": "de"}}
    name = COMPLETE["datalab"]["name"]
    footers = _footers(inputs, doc)
    assert f'Part of <span lang="de">{name}</span></a>' in footers["en"]
    assert f'Teil von <span lang="de">{name}</span></a>' in footers["de"]
    # without a language the name is plain text in the page's language
    assert f"Part of {name}</a>" in _footers(inputs, COMPLETE)["en"]


def test_a_datalab_language_must_be_a_language_tag(tmp_path):
    with pytest.raises(ConfigError, match="datalab.lang"):
        _load(tmp_path, {**COMPLETE, "datalab": {**COMPLETE["datalab"], "lang": "German"}})


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
    names = ("datalab.name", "datalab.url", "impressum_url", "privacy_url", "repo.url")
    for name in names + ("repo.file_url",):
        assert name in str(e.value)
    assert not out.exists()


def test_public_export_refuses_without_the_repo(rich, tmp_path):  # noqa: F811
    _write_site(rich[1], {k: v for k, v in COMPLETE.items() if k != "repo"})
    with pytest.raises(export.ExportError, match=r"repo\.url, repo\.file_url"):
        _export(rich, tmp_path / "site", True)


CLEAN = "0123456789abcdef0123456789abcdef01234567"


@pytest.mark.parametrize("commit", [CLEAN + "-dirty", "unknown"])
def test_public_export_refuses_a_dirty_or_unknown_checkout(rich, tmp_path, monkeypatch, commit):  # noqa: F811
    # M16 (R42): the pages link repo files at the export's commit, which must hold the tree
    _write_site(rich[1], COMPLETE)
    monkeypatch.setattr(export, "public_commit", lambda: commit)
    out = tmp_path / "site"
    with pytest.raises(export.ExportError, match="clean git checkout"):
        _export(rich, out, True)
    assert not out.exists()


def test_an_untracked_file_does_not_make_the_checkout_dirty(monkeypatch):
    # M16 fix round: a sandbox shows stub files as untracked; they are not in what pages link
    calls = []

    def fake_git(*args):
        calls.append(args)
        return CLEAN + "\n" if args[0] == "rev-parse" else ""

    monkeypatch.setattr(export, "_git", fake_git)
    assert export.public_commit() == CLEAN
    assert ("status", "--porcelain", "--untracked-files=no") in calls
    monkeypatch.setattr(export, "_git", lambda *a: CLEAN if a[0] == "rev-parse" else " M x.py")
    assert export.public_commit() == CLEAN + "-dirty"


def test_public_export_reads_the_commit_once(rich, tmp_path, monkeypatch):  # noqa: F811
    _write_site(rich[1], COMPLETE)
    monkeypatch.setattr(export, "public_commit", lambda: CLEAN)
    monkeypatch.setattr(export, "git_commit", lambda: pytest.fail("git_commit asked again"))
    out = tmp_path / "site"
    _export(rich, out, True)
    assert json.loads((out / "build.json").read_text())["commit_full"] == CLEAN


def test_public_export_stamps_true(rich, tmp_path, monkeypatch):  # noqa: F811
    _write_site(rich[1], COMPLETE)
    monkeypatch.setattr(export, "public_commit", lambda: CLEAN)
    out = tmp_path / "site"
    _export(rich, out, True)
    assert json.loads((out / "build.json").read_text())["public"] is True


def test_plain_export_stamps_false(rich, tmp_path):  # noqa: F811
    out = tmp_path / "site"
    _export(rich, out, False)
    assert json.loads((out / "build.json").read_text())["public"] is False
