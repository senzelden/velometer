"""M16 (legal review 1.1c, ruling R42): repo paths on the pages link the public repository at
the commit the page was built from; with `repo` unset nothing changes."""

import json
import re
from pathlib import Path

import pytest
import yaml

from tests.test_app import _client
from tests.test_app_m7 import NARRATIVE_YAML, content, setup  # noqa: F401 - fixtures
from velometer.app import deploy_check, repo_links
from velometer.app.main import create_app
from velometer.app.repo_links import RepoLinks, bare_repo_paths, heading_anchor, heading_slug
from velometer.config import ConfigError, SiteConfig, load_site

FILE_URL = "https://forge.example/owner/velometer/blob/{commit}/{path}"
REPO = {"url": "https://forge.example/owner/velometer", "file_url": FILE_URL}
SHA = "0123456789abcdef0123456789abcdef01234567"
EDITION = {"commit": SHA[:7], "commit_full": SHA}


def _write(cfg: Path, doc: dict) -> None:
    (cfg / "site.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")


# --- site.yaml `repo` -------------------------------------------------------------------------


def test_repo_is_read_and_all_null_is_unset(tmp_path):
    _write(tmp_path, {"repo": REPO})
    site = load_site(tmp_path)
    assert site.repo.url == REPO["url"] and site.repo.file_url == FILE_URL
    _write(tmp_path, {"repo": {"url": None, "file_url": None}})
    assert load_site(tmp_path).repo is None


def test_the_shipped_repo_is_unset():
    from velometer.config import default_config_dir

    assert load_site(default_config_dir()).repo is None


@pytest.mark.parametrize(
    ("repo", "says"),
    [
        ({"url": REPO["url"]}, "repo.file_url"),
        ({"file_url": FILE_URL}, "repo.url"),
        ({**REPO, "url": "http://forge.example/x"}, "http://forge.example/x"),
        ({**REPO, "file_url": "http://forge.example/{commit}/{path}"}, "https://"),
        ({**REPO, "file_url": "https://forge.example/blob/main/{path}"}, "{commit}"),
        ({**REPO, "file_url": "https://forge.example/blob/{commit}/"}, "{path}"),
    ],
)
def test_repo_validation_names_the_problem(tmp_path, repo, says):
    _write(tmp_path, {"repo": repo})
    with pytest.raises(ConfigError, match=re.escape(says)):
        load_site(tmp_path)


def test_a_public_export_needs_the_repo():
    full = SiteConfig.model_validate(
        {
            "datalab": {"name": "D", "url": "https://d.example/"},
            "impressum_url": "https://d.example/i",
            "privacy_url": "https://d.example/p",
        }
    )
    assert not full.complete
    assert full.missing() == ["repo.url", "repo.file_url"]
    with_repo = full.model_copy(update={"repo": SiteConfig.model_validate({"repo": REPO}).repo})
    assert with_repo.complete and with_repo.missing() == []
    values = with_repo.public_values()
    assert values["repo_url"] == REPO["url"] and values["repo_file_url"] == FILE_URL


# --- the link rules -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("warsaw/lau/2025", "warsawlau2025"),
        ("berlin (qecio_main_km row)", "berlin-qecio_main_km-row"),
        ("Mapped km per category", "mapped-km-per-category"),
        ("Ünter Straße - x", "ünter-straße---x"),
    ],
)
def test_heading_slug_follows_the_forges(text, slug):
    assert heading_slug(text) == slug


def test_only_a_heading_locator_has_an_anchor():
    assert heading_anchor("### warsaw/lau/2025") == "warsawlau2025"
    assert heading_anchor("#### berlin") == "berlin"
    assert heading_anchor("Mapped km per category") is None
    assert heading_anchor(None) is None


def test_a_repeated_heading_gets_the_forges_suffix_and_a_missing_one_none():
    text = "# R\n\n## berlin\n\n```\n## berlin\n```\n\n### x\n\n#### berlin\n"
    assert heading_anchor("## berlin", text) == "berlin"
    assert heading_anchor("#### berlin", text) == "berlin-1"
    assert heading_anchor("### nowhere", text) is None


def _links() -> RepoLinks:
    return RepoLinks(FILE_URL, SHA, paths=repo_links.tracked_paths())


def test_a_url_pins_the_commit_and_quotes_the_path():
    links = RepoLinks(FILE_URL, SHA, paths=frozenset({"docs/a b.md"}))
    assert (
        links.url("docs/a b.md", "x")
        == f"https://forge.example/owner/velometer/blob/{SHA}/docs/a%20b.md#x"
    )


def test_code_spans_holding_a_repo_path_become_links():
    links = _links()
    page = (
        "<p><code>docs/superpowers/rulings-m5.md</code>, <code>docs/review</code>, "
        "<code>population</code>, <code>sources/boundaries.py</code>, "
        "<code>docs/no-such-file.md</code></p>"
        '<a href="/x"><code>config/cities.yaml</code></a>'
        "<script>x = '<code>config/trust.yaml</code>'</script>"
    )
    out = links.link_code(page)
    assert (
        f'<a href="https://forge.example/owner/velometer/blob/{SHA}/docs/superpowers/rulings-m5.md">'
        "<code>docs/superpowers/rulings-m5.md</code></a>"
    ) in out
    assert (
        f'<a href="https://forge.example/owner/velometer/blob/{SHA}/docs/review"><code>docs/review</code></a>'
        in out
    )
    for plain in ("population", "sources/boundaries.py", "docs/no-such-file.md"):
        assert f"<p><code>{plain}</code>" in out or f", <code>{plain}</code>" in out
    assert '<a href="/x"><code>config/cities.yaml</code></a>' in out  # already a link
    assert "<script>x = '<code>config/trust.yaml</code>'</script>" in out


def test_only_tracked_paths_link():
    links = _links()
    assert links.exists("config/cities.yaml") and links.exists("docs/review")
    assert not links.exists("velometer.sqlite")  # on disk, never tracked
    assert not links.exists("../etc/passwd") and not links.exists("/etc/passwd")


def test_bare_repo_paths_finds_code_outside_links():
    page = (
        "<code>docs/a.md</code> <a href='x'><code>config/b.yaml</code></a> "
        "<code>population</code> <code>sources/x.py</code> <code>tools/</code>"
    )
    assert bare_repo_paths(page) == ["docs/a.md", "tools/"]


# --- the pages ----------------------------------------------------------------------------------


def _ref_item(setup, content, repo: dict | None, locator: str, edition=EDITION) -> str:  # noqa: F811
    db_path, cfg, maps, docs = setup
    if repo is not None:
        _write(cfg, {"repo": repo})
    (content / "narratives" / "berlin.yaml").write_text(
        NARRATIVE_YAML.replace(
            "    file: docs/review/m3_timeseries.md\n    route: /city/berlin/time",
            f"    file: docs/review/shifts.md\n    locator: '{locator}'",
        )
    )
    app = create_app(db_path, cfg, maps, docs, content_dir=content, static_edition=edition)
    with _client(app) as c:
        html = c.get("/city/berlin").text
    return html[html.index('<li id="ref-1">') :].split("</li>")[0]


def test_a_data_ref_links_its_file_at_the_heading(setup, content):  # noqa: F811
    item = _ref_item(setup, content, REPO, "### warsaw/lau/2025")
    href = f"https://forge.example/owner/velometer/blob/{SHA}/docs/review/shifts.md#warsawlau2025"
    assert f'<a href="{href}"><code>docs/review/shifts.md</code> · warsaw/lau/2025</a>' in item


def test_a_data_ref_without_a_heading_has_no_anchor(setup, content):  # noqa: F811
    item = _ref_item(setup, content, REPO, "first table")
    href = f"https://forge.example/owner/velometer/blob/{SHA}/docs/review/shifts.md"
    assert f'<a href="{href}"><code>docs/review/shifts.md</code> · first table</a>' in item


def test_without_repo_a_data_ref_stays_plain(setup, content):  # noqa: F811
    item = _ref_item(setup, content, None, "### warsaw/lau/2025")
    assert "<code>docs/review/shifts.md</code> · warsaw/lau/2025" in item and "<a " not in item


def test_the_dev_server_links_the_checkouts_head(setup, content):  # noqa: F811
    from velometer.run import git_commit

    head = git_commit().removesuffix("-dirty")
    item = _ref_item(setup, content, REPO, "### warsaw/lau/2025", edition=None)
    assert f"/blob/{head}/docs/review/shifts.md#warsawlau2025" in item


METHODOLOGY = (
    "# Methodology\n\nSee `docs/superpowers/rulings-m5.md` and `population`.\n\n## Licences\n\n"
    "The code is MIT-licensed.<!-- repo: It is published in the [velometer repository]"
    "({repo_url}). --> External figures are cited.\n"
)


def _methodology(setup, repo: dict | None) -> str:  # noqa: F811
    db_path, cfg, maps, docs = setup
    if repo is not None:
        _write(cfg, {"repo": repo})
    (docs / "methodology.md").write_text(METHODOLOGY, encoding="utf-8")
    from tests.test_app import CONTENT

    app = create_app(db_path, cfg, maps, docs, content_dir=CONTENT, static_edition=EDITION)
    with _client(app) as c:
        html = c.get("/methodology").text
    return html[html.index('<article class="prose">') :].split("</article>")[0]


def test_methodology_links_the_repo_and_its_paths(setup):  # noqa: F811
    body = _methodology(setup, REPO)
    assert (
        'The code is MIT-licensed. It is published in the <a href="https://forge.example/owner/'
        'velometer">velometer repository</a>. External figures are cited.'
    ) in body
    assert (
        f'<a href="https://forge.example/owner/velometer/blob/{SHA}/docs/superpowers/rulings-m5.md"><code>'
        in body
    )
    assert "<code>population</code>" in body and bare_repo_paths(body) == []


def test_methodology_without_repo_is_as_before(setup):  # noqa: F811
    body = _methodology(setup, None)
    assert "The code is MIT-licensed. External figures are cited." in body
    assert "repository" not in body and "<a " not in body
    assert "<code>docs/superpowers/rulings-m5.md</code>" in body


@pytest.mark.parametrize("name", ["methodology.md", "methodology.de.md"])
def test_the_shipped_methodology_carries_the_repo_sentence(name):
    text = (Path(__file__).parents[1] / "docs" / name).read_text(encoding="utf-8")
    assert len(re.findall(r"<!-- repo: [^>]*\(\{repo_url\}\)[^>]*-->", text)) == 1


# --- deploy-check -------------------------------------------------------------------------------


def test_deploy_check_refuses_a_bare_repo_path(tmp_path):
    from velometer.app.deploy_check import _bare_code_problems

    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "index.html").write_text("<p><code>docs/review/shifts.md</code></p>")
    (tmp_path / "index.html").write_text('<a href="x"><code>docs/review/shifts.md</code></a>')
    problems = _bare_code_problems(tmp_path)
    assert len(problems) == 1 and "a/index.html" in problems[0] and "shifts.md" in problems[0]


def test_deploy_check_wants_the_repo_values(tmp_path):
    assert "repo_url" in deploy_check.SITE_VALUES and "repo_file_url" in deploy_check.SITE_VALUES
    build = {"base": "/", "public": True, "site": {k: "x" for k in deploy_check.SITE_VALUES}}
    del build["site"]["repo_file_url"]
    (tmp_path / "build.json").write_text(json.dumps(build))
    assert any("repo_file_url" in p for p in deploy_check.deploy_problems(tmp_path, None))
