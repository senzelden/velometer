"""The README's relative links and images resolve to tracked files, so the GitHub page has no
broken link or missing picture."""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent

MD_LINK = re.compile(r"\]\(([^)\s]+)\)")
HTML_REF = re.compile(r'\b(?:href|src)="([^"]+)"')
SRCSET = re.compile(r'\bsrcset="([^"]+)"')


def relative_targets(text: str) -> list[str]:
    """Every link or image target in `text` that points into the repository."""
    refs = MD_LINK.findall(text) + HTML_REF.findall(text)
    refs += [part.split()[0] for s in SRCSET.findall(text) for part in s.split(",")]
    out = []
    for ref in refs:
        u = urlsplit(ref)
        if u.scheme or u.netloc or not u.path:  # absolute URLs and in-page anchors
            continue
        out.append(unquote(u.path))
    return out


def tracked(root: Path) -> set[str]:
    files = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.split()
    dirs = {str(Path(f).parent) for f in files} | {
        str(p) for f in files for p in Path(f).parents if str(p) != "."
    }
    return set(files) | dirs


def missing(text: str, root: Path) -> list[str]:
    have = tracked(root)
    return [t for t in relative_targets(text) if t.rstrip("/") not in have]


def test_readme_relative_links_and_images_are_tracked():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert relative_targets(text), "the README links nothing in the repository"
    assert missing(text, ROOT) == []


def test_a_broken_target_is_reported_in_every_form():
    text = (
        '[a](docs/nope.md) <img src="docs/img/nope.png"> '
        '<source srcset="docs/img/nope-dark.png 2x"> [web](https://example.org/x) [here](#why)'
        " [ok](LICENSE)"
    )
    assert missing(text, ROOT) == ["docs/nope.md", "docs/img/nope.png", "docs/img/nope-dark.png"]
