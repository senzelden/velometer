"""M17 Task 1: the public origin (`site.url`) and the committed public site values
(`config/site.public.yaml`, merged over `site.yaml` by `load_site(..., public=True)`)."""

import re
import shutil
import subprocess
from pathlib import Path

import yaml

from velometer.app import export
from velometer.config import SiteConfig, load_site

ROOT = Path(__file__).resolve().parents[1]
FULL = {
    "url": "https://velometer.example.org/",
    "datalab": {"name": "Datalab", "url": "https://datalab.example.org/"},
    "impressum_url": "https://datalab.example.org/impressum/",
    "privacy_url": "https://datalab.example.org/datenschutz/",
    "accessibility_url": "https://datalab.example.org/barrierefreiheit/",
    "repo": {
        "url": "https://forge.example.org/o/velometer",
        "file_url": "https://forge.example.org/o/velometer/blob/{commit}/{path}",
    },
}


def test_public_requires_url():
    site = SiteConfig.model_validate({**FULL, "url": None})
    assert site.missing() == ["url"]
    assert not site.complete
    full = SiteConfig.model_validate(FULL)
    assert full.missing() == []
    assert full.public_values()["url"] == FULL["url"]


def test_public_overlay_merges(tmp_path):
    (tmp_path / "site.yaml").write_text(
        "url: null\ndatalab:\n  name: null\n  url: null\nrepo:\n  url: null\n  file_url: null\n"
        "impressum_url: null\nprivacy_url: null\naccessibility_url: null\n",
        encoding="utf-8",
    )
    (tmp_path / "site.public.yaml").write_text(
        yaml.safe_dump(FULL, allow_unicode=True), encoding="utf-8"
    )
    assert load_site(tmp_path, public=True).complete
    assert not load_site(tmp_path).complete


def test_overlay_merges_key_by_key(tmp_path):
    """A nested block in the overlay replaces only the keys it names."""
    (tmp_path / "site.yaml").write_text("datalab:\n  name: Local\n  lang: de\n", encoding="utf-8")
    (tmp_path / "site.public.yaml").write_text(
        "datalab:\n  name: Public\n  url: https://datalab.example.org/\n", encoding="utf-8"
    )
    d = load_site(tmp_path, public=True).datalab
    assert (d.name, d.url, d.lang) == ("Public", "https://datalab.example.org/", "de")


def test_public_without_overlay_file_is_plain_site(tmp_path):
    (tmp_path / "site.yaml").write_text("url: https://a.example.org/\n", encoding="utf-8")
    assert load_site(tmp_path, public=True).url == "https://a.example.org/"


def test_citation_url_matches_site():
    cff = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert cff["url"] == load_site(ROOT / "config", public=True).url


def test_overlay_values_are_public():
    """No e-mail, no postal address: only https URLs and the Datalab's name."""
    doc = yaml.safe_load((ROOT / "config" / "site.public.yaml").read_text(encoding="utf-8"))
    values = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "name":
                    assert v == load_site(ROOT / "config", public=True).datalab.name
                else:
                    walk(v)
        else:
            values.append(node)

    walk(doc)
    assert values
    for v in values:
        assert isinstance(v, str) and re.fullmatch(r"https://\S+", v), v
        assert "@" not in v


def test_repo_config_is_complete_only_with_overlay():
    assert load_site(ROOT / "config", public=True).complete
    assert not load_site(ROOT / "config").complete


def _head_copy(tmp_path: Path) -> Path:
    copy = tmp_path / "config"
    shutil.copytree(ROOT / "config", copy)
    for p in copy.rglob("*"):
        if p.is_file():
            rel = p.relative_to(copy).as_posix()
            blob = subprocess.run(
                ["git", "-C", str(ROOT), "show", f"HEAD:config/{rel}"], capture_output=True
            )
            if blob.returncode == 0:
                p.write_bytes(blob.stdout)
            else:
                p.unlink()
    return copy


def test_config_guard_accepts_overlay(tmp_path):
    """The repo's config/ with the committed overlay passes; any other differing file is flagged."""
    copy = _head_copy(tmp_path)
    assert (copy / "site.public.yaml").is_file()
    assert export.config_drift(copy) == []
    (copy / "presets.yaml").write_text("changed: true\n", encoding="utf-8")
    assert export.config_drift(copy) == ["presets.yaml: differs from the commit"]
    (copy / "site.public.yaml").write_text("url: https://evil.example.org/\n", encoding="utf-8")
    assert "site.public.yaml: differs from the commit" in export.config_drift(copy)
