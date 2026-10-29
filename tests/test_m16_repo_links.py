"""M16 (legal review 1.1c, ruling R42): repo paths on the pages link the public repository at
the commit the page was built from; with `repo` unset nothing changes."""

import json
import re
import shutil
import subprocess
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
            "accessibility_url": "https://d.example/b",
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
        ("Café ﻿x̃ — y", "café-x̃--y"),  # letters, marks; the dash and BOM dropped
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
    text = (
        "# R\n\n## berlin\n\n```\n## berlin\n```\n\n~~~\n## berlin\n~~~\n\n### x\n\n#### berlin\n"
    )
    assert heading_anchor("## berlin", text) == "berlin"
    assert heading_anchor("#### berlin", text) == "berlin-1"
    assert heading_anchor("### nowhere", text) is None


# a repo of its own for the link tests: what links never depends on this checkout's files
FIXTURE_FILES = {
    "docs/review/shifts.md": "# Shifts\n\n### warsaw/lau/2025\n\nText.\n",
    "docs/superpowers/rulings-m5.md": "# Rulings\n",
    "docs/review/trust/NO.md": "# NO\n",
    "config/cities.yaml": "cities: []\n",
    "config/activity.yaml": "x: 1\n",
}
TRACKED = frozenset(
    {*FIXTURE_FILES, "docs", "docs/review", "docs/review/trust", "docs/superpowers", "config"}
)


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    for rel, text in FIXTURE_FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    (root / "velometer.sqlite").write_bytes(b"")  # on disk, never tracked
    repo_links.file_anchor.cache_clear()
    yield root
    repo_links.file_anchor.cache_clear()


def _links(root: Path) -> RepoLinks:
    return RepoLinks(FILE_URL, SHA, root, TRACKED)


def test_a_url_pins_the_commit_and_quotes_the_path():
    links = RepoLinks(FILE_URL, SHA, paths=frozenset({"docs/a b.md"}))
    assert (
        links.url("docs/a b.md", "x")
        == f"https://forge.example/owner/velometer/blob/{SHA}/docs/a%20b.md#x"
    )


def test_code_spans_holding_a_repo_path_become_links(repo_root):
    links = _links(repo_root)
    page = (
        "<p><code>docs/superpowers/rulings-m5.md</code>, <code>docs/review</code>, "
        "<code>population</code>, <code>sources/boundaries.py</code>, "
        "<code>docs/no-such-file.md</code></p>"
        '<a href="/x"><code>config/cities.yaml</code></a>'
        '<a\nhref="/y"><code>config/activity.yaml</code></a>'
        "<script>x = '<code>config/cities.yaml</code>'</script>"
    )
    out = links.link_code(page)
    blob = f"https://forge.example/owner/velometer/blob/{SHA}/"
    assert (
        f'<a href="{blob}docs/superpowers/rulings-m5.md"><code>docs/superpowers/rulings-m5.md'
        "</code></a>"
    ) in out
    assert f'<a href="{blob}docs/review"><code>docs/review</code></a>' in out
    for plain in ("population", "sources/boundaries.py", "docs/no-such-file.md"):
        assert f"<p><code>{plain}</code>" in out or f", <code>{plain}</code>" in out
    assert '<a href="/x"><code>config/cities.yaml</code></a>' in out  # already a link
    assert '<a\nhref="/y"><code>config/activity.yaml</code></a>' in out  # a link over lines
    assert "<script>x = '<code>config/cities.yaml</code>'</script>" in out


def test_only_tracked_paths_link(repo_root):
    links = _links(repo_root)
    assert links.exists("config/cities.yaml") and links.exists("docs/review")
    assert (repo_root / "velometer.sqlite").exists() and not links.exists("velometer.sqlite")
    assert not links.exists("../etc/passwd") and not links.exists("/etc/passwd")
    # without a tracked set (no git), the disk decides
    assert RepoLinks(FILE_URL, SHA, repo_root, None).exists("velometer.sqlite")


def test_tracked_paths_are_git_ls_files_and_their_directories(tmp_path):
    git = shutil.which("git")
    if git is None:
        pytest.skip("no git")
    (tmp_path / "docs" / "review").mkdir(parents=True)
    (tmp_path / "docs" / "review" / "a.md").write_text("a")
    (tmp_path / "untracked.md").write_text("u")
    subprocess.run([git, "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run([git, "add", "docs/review/a.md"], cwd=tmp_path, check=True)
    assert repo_links.tracked_paths(tmp_path) == {"docs", "docs/review", "docs/review/a.md"}
    assert repo_links.tracked_paths(tmp_path / "no-repo-here") is None  # not a directory


def test_bare_repo_paths_finds_code_outside_links():
    page = (
        "<code>docs/a.md</code> <a href='x'><code>config/b.yaml</code></a> "
        "<code>population</code> <code>sources/x.py</code> <code>tools/</code> "
        "<code>tests/x</code> <code>HANDOVER.md</code> <code>pyproject.toml</code> "
        "<code>README.md</code> <code>highway=path</code> <code>v4</code> "
        "<a\nhref='y'><code>docs/c.md</code></a>"
    )
    assert bare_repo_paths(page) == [
        "docs/a.md", "sources/x.py", "tools/", "tests/x", "HANDOVER.md", "pyproject.toml",
        "README.md",
    ]  # fmt: skip


@pytest.mark.parametrize(
    "text",
    [
        "LICENSE", "CITATION.cff", "uv.lock", ".python-version", "scripts/x", "scripts/",
        "data/cities.csv", "deploy/run.sh", "page/index.html", "static/site.css",
        "maps/berlin.geojson", "notes/a.txt", "nb/a.ipynb", "x/y.cff",
    ],
)  # fmt: skip
def test_the_guard_catches_root_files_scripts_and_every_text_extension(text):
    """R45 M2: the files and extensions the repo holds that the first guard missed."""
    assert bare_repo_paths(f"<p><code>{text}</code></p>") == [text]


def test_deploy_check_tells_a_bare_file_name_from_an_unlinked_path(tmp_path):
    """R45 M4: a name with no directory (an error message's `retrieved.json`) is reported
    apart from a repo path left unlinked, and each says what to check."""
    from velometer.app.deploy_check import _bare_code_problems

    (tmp_path / "index.html").write_text(
        "<p><code>retrieved.json</code> <code>docs/review/x.md</code> <code>LICENSE</code></p>"
    )
    problems = _bare_code_problems(tmp_path)
    (paths,) = [p for p in problems if "repo path(s) not linked" in p]
    (names,) = [p for p in problems if "file name(s)" in p]
    assert "docs/review/x.md" in paths and "LICENSE" in paths and "retrieved.json" not in paths
    assert "retrieved.json" in names and "error message" in names
    assert "untracked" in paths


# --- the pages ----------------------------------------------------------------------------------


def _app(setup, content, repo: dict | None, root: Path, edition=EDITION):  # noqa: F811
    db_path, cfg, maps, docs = setup
    if repo is not None:
        _write(cfg, {"repo": repo})
    return create_app(
        db_path, cfg, maps, docs, content_dir=content, static_edition=edition,
        repo_root=root, repo_paths=TRACKED,
    )  # fmt: skip


def _ref_item(setup, content, repo, locator, root, edition=EDITION) -> str:  # noqa: F811
    (content / "narratives" / "berlin.yaml").write_text(
        NARRATIVE_YAML.replace(
            "    file: docs/review/m3_timeseries.md\n    route: /city/berlin/time",
            f"    file: docs/review/shifts.md\n    locator: '{locator}'",
        )
    )
    with _client(_app(setup, content, repo, root, edition)) as c:
        html = c.get("/city/berlin").text
    return html[html.index('<li id="ref-1">') :].split("</li>")[0]


def test_a_data_ref_links_its_file_at_the_heading(setup, content, repo_root):  # noqa: F811
    item = _ref_item(setup, content, REPO, "### warsaw/lau/2025", repo_root)
    href = f"https://forge.example/owner/velometer/blob/{SHA}/docs/review/shifts.md#warsawlau2025"
    assert f'<a href="{href}"><code>docs/review/shifts.md</code> · warsaw/lau/2025</a>' in item


def test_a_data_ref_whose_heading_the_file_lacks_has_no_anchor(setup, content, repo_root):  # noqa: F811
    item = _ref_item(setup, content, REPO, "#### warsaw/lau/2025", repo_root)  # another level
    href = f"https://forge.example/owner/velometer/blob/{SHA}/docs/review/shifts.md"
    assert f'<a href="{href}"><code>docs/review/shifts.md</code> · warsaw/lau/2025</a>' in item


def test_a_data_ref_without_a_heading_has_no_anchor(setup, content, repo_root):  # noqa: F811
    item = _ref_item(setup, content, REPO, "first table", repo_root)
    href = f"https://forge.example/owner/velometer/blob/{SHA}/docs/review/shifts.md"
    assert f'<a href="{href}"><code>docs/review/shifts.md</code> · first table</a>' in item


def test_without_repo_a_data_ref_stays_plain(setup, content, repo_root):  # noqa: F811
    item = _ref_item(setup, content, None, "### warsaw/lau/2025", repo_root)
    assert "<code>docs/review/shifts.md</code> · warsaw/lau/2025" in item and "<a " not in item


def test_the_dev_server_links_the_checkouts_head(setup, content, repo_root, monkeypatch):  # noqa: F811
    from velometer.app import main

    head = "fedcba9876543210fedcba9876543210fedcba98"
    monkeypatch.setattr(main, "git_commit", lambda: head + "-dirty")  # dirty: HEAD all the same
    item = _ref_item(setup, content, REPO, "### warsaw/lau/2025", repo_root, edition=None)
    assert f"/blob/{head}/docs/review/shifts.md#warsawlau2025" in item


METHODOLOGY = (
    "# Methodology\n\nSee `docs/superpowers/rulings-m5.md` and `population`.\n\n## Licences\n\n"
    "The code is MIT-licensed.<!-- repo: It is published in the [velometer repository]"
    "({repo_url}). --> External figures are cited.\n"
)


def _methodology(setup, content, repo: dict | None, root: Path) -> str:  # noqa: F811
    (setup[3] / "methodology.md").write_text(METHODOLOGY, encoding="utf-8")
    with _client(_app(setup, content, repo, root)) as c:
        html = c.get("/methodology").text
    return html[html.index('<article class="prose">') :].split("</article>")[0]


def test_methodology_links_the_repo_and_its_paths(setup, content, repo_root):  # noqa: F811
    body = _methodology(setup, content, REPO, repo_root)
    assert (
        'The code is MIT-licensed. It is published in the <a href="https://forge.example/owner/'
        'velometer">velometer repository</a>. External figures are cited.'
    ) in body
    blob = f"https://forge.example/owner/velometer/blob/{SHA}/"
    assert f'<a href="{blob}docs/superpowers/rulings-m5.md"><code>' in body
    assert "<code>population</code>" in body and bare_repo_paths(body) == []


def test_methodology_without_repo_is_as_before(setup, content, repo_root):  # noqa: F811
    body = _methodology(setup, content, None, repo_root)
    assert "The code is MIT-licensed. External figures are cited." in body
    assert "repository" not in body and "<a " not in body
    assert "<code>docs/superpowers/rulings-m5.md</code>" in body


# the shipped files are the rule under test here: their sentence and their paths
@pytest.mark.parametrize("name", ["methodology.md", "methodology.de.md"])
def test_the_shipped_methodology_carries_the_repo_sentence(name):
    text = (Path(__file__).parents[1] / "docs" / name).read_text(encoding="utf-8")
    assert len(re.findall(r"<!-- repo: [^>]*\(\{repo_url\}\)[^>]*-->", text)) == 1


@pytest.mark.parametrize("name", ["methodology.md", "methodology.de.md"])
def test_the_shipped_methodology_names_paths_from_the_repo_root(name):
    text = (Path(__file__).parents[1] / "docs" / name).read_text(encoding="utf-8")
    root = Path(__file__).parents[1]
    spans = set(re.findall(r"`([^`\n]+)`", text))
    wrong = [s for s in spans if repo_links.looks_like_repo_path(s) and not (root / s).exists()]
    assert wrong == []


# --- Compare's flag notes (R44) -------------------------------------------------------------------


def test_the_series_payload_maps_each_explanations_repo_paths(setup, repo_root):  # noqa: F811
    from tests.test_app import EXPLANATION
    from velometer.app.series import series_payload
    from velometer.report.data import ReportData, open_readonly

    db_path, cfg, _maps, docs = setup
    review = docs / "review" / "m3_timeseries.md"
    text = review.read_text(encoding="utf-8")
    assert EXPLANATION in text  # the fixture explanation the flag key carries
    review.write_text(
        text.replace(EXPLANATION, EXPLANATION + " See `config/activity.yaml` and `x=y`."),
        encoding="utf-8",
    )
    conn = open_readonly(db_path)
    try:
        data = ReportData(conn, cfg)
        plain = series_payload(data, review)
        linked = series_payload(data, review, _links(repo_root))
    finally:
        conn.close()
    assert "links" not in plain["explanations"]
    links = linked["explanations"]["links"]
    assert links and all(k in linked["explanations"]["timeseries"] for k in links)
    url = f"https://forge.example/owner/velometer/blob/{SHA}/config/activity.yaml"
    assert all(v == {"config/activity.yaml": url} for v in links.values())


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


def test_deploy_check_refuses_a_repo_link_at_another_commit(tmp_path):
    from velometer.app.deploy_check import _pinned_problems

    build = {"commit_full": SHA, "site": {"repo_file_url": FILE_URL}}
    blob = "https://forge.example/owner/velometer/blob/"
    (tmp_path / "data").mkdir()
    (tmp_path / "index.html").write_text(f'<a href="{blob}{SHA}/docs/a.md">a</a>')
    assert _pinned_problems(tmp_path, build) == []
    (tmp_path / "other.html").write_text(f'<a href="{blob}main/docs/a.md">a</a>')
    (tmp_path / "data" / "series.json").write_text(json.dumps({"u": f"{blob}main/x.md"}))
    problems = _pinned_problems(tmp_path, build)
    assert len(problems) == 2 and "other.html" in problems[1] and "series.json" in problems[0]
