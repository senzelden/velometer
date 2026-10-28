"""Links to the public repository (M16, legal review 1.1c, ruling R42).

A page that names a repo file (a data reference's file, a code span holding a path) links it to
`site.yaml` `repo.file_url` at the commit the page was built from, so a citation never rots. With
`repo` unset nothing is linked and pages render as before.
"""

import html
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from markupsafe import Markup, escape

# the repository root: src/velometer/app/repo_links.py -> parents[3]
ROOT = Path(__file__).resolve().parents[3]

# the first directories of the repo paths a public page must never print unlinked (the guard)
REPO_DIRS = ("docs", "config", "src", "tools", "content", "sites", "deploy")

_TOKEN = re.compile(
    r"<script\b.*?</script\s*>|<!--.*?-->|<a\b[^>]*>|</a\s*>|<code>([^<>]*)</code>",
    re.S | re.I,
)
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.M)


def heading_slug(text: str) -> str:
    """GitHub's and Forgejo's anchor for a heading: lowercase, every character that is not a
    letter, digit, space, hyphen or underscore dropped, each space a hyphen."""
    kept = "".join(c for c in text.lower() if c.isalnum() or c in " -_")
    return kept.replace(" ", "-")


def heading_anchor(locator: str | None, text: str | None = None) -> str | None:
    """The anchor of a heading locator (`### warsaw/lau/2025` -> `warsawlau2025`), None for a
    locator that is not a heading. With the file's `text`, a repeated heading gets the suffix
    the forges give it (`-1`, `-2`, ...) and a heading the file lacks gets no anchor."""
    if not locator or not locator.lstrip().startswith("#"):
        return None
    level = len(locator.strip()) - len(locator.strip().lstrip("#"))
    wanted = locator.strip().lstrip("#").strip()
    slug = heading_slug(wanted)
    if not slug:
        return None
    if text is None:
        return slug
    seen: dict[str, int] = {}
    for m in _HEADING.finditer(re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)):
        s = heading_slug(m.group(2))
        n = seen.get(s, 0)
        seen[s] = n + 1
        if len(m.group(1)) == level and m.group(2) == wanted:
            return s if n == 0 else f"{s}-{n}"
    return None


def tracked_paths(root: Path = ROOT) -> frozenset[str] | None:
    """The repo's tracked files and their directories, relative to `root`; None when git cannot
    say (no checkout), in which case paths are checked on disk."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], capture_output=True, check=True, cwd=root
        ).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        return None
    files = [f for f in out.split("\0") if f]
    dirs = {str(p) for f in files for p in PurePosixPath(f).parents if str(p) != "."}
    return frozenset(files) | frozenset(dirs)


@dataclass(frozen=True)
class RepoLinks:
    """`file_url` (with `{commit}` and `{path}`) at `commit`, over the repo at `root`."""

    file_url: str
    commit: str
    root: Path = ROOT
    paths: frozenset[str] | None = None  # tracked files and directories; None: check on disk

    def exists(self, path: str) -> bool:
        path = path.strip().rstrip("/")
        if not path or path.startswith(("/", ".")) or ".." in PurePosixPath(path).parts:
            return False
        if self.paths is not None:
            return path in self.paths
        return (self.root / path).exists()

    def url(self, path: str, anchor: str | None = None) -> str:
        path = path.strip().rstrip("/")
        out = self.file_url.replace("{commit}", quote(self.commit, safe="")).replace(
            "{path}", quote(path, safe="/")
        )
        return out + (f"#{quote(anchor, safe='-_')}" if anchor else "")

    def data_ref(self, file: str, locator: str | None) -> str | None:
        """The link of a data reference's file, anchored at its heading locator; None when the
        file is not in the repo."""
        if not self.exists(file):
            return None
        try:
            text = (self.root / file.strip()).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = None
        return self.url(file, heading_anchor(locator, text))

    def link_code(self, page: str) -> str:
        """`page` with every `<code>` that holds nothing but a repo path, and is not already
        inside a link, made a link to that path (scripts and comments are left alone)."""
        out, last, depth = [], 0, 0
        for m in _TOKEN.finditer(page):
            token = m.group(0)
            low = token[:3].lower()
            if low.startswith("<a ") or low == "<a>":
                depth += 1
            elif low == "</a":
                depth = max(0, depth - 1)
            elif m.group(1) is not None and depth == 0:
                path = html.unescape(m.group(1))
                if self.exists(path):
                    out.append(page[last : m.start()])
                    out.append(f'<a href="{escape(self.url(path))}">{token}</a>')
                    last = m.end()
        out.append(page[last:])
        return "".join(out)


def make_links(site, commit: str | None, root: Path = ROOT) -> RepoLinks | None:
    """The links of `site` (a SiteConfig) at `commit`, None when `repo` is unset or the commit
    is unknown."""
    repo = getattr(site, "repo", None)
    if repo is None or not commit or commit == "unknown":
        return None
    return RepoLinks(repo.file_url, commit.removesuffix("-dirty"), root, tracked_paths(root))


def data_ref_file(links: RepoLinks | None, file: str, locator: str | None) -> Markup:
    """A data reference's file line as `_cited.html` prints it: `<code>file</code> · locator`,
    a link to the repo when `links` has the file."""
    shown = Markup("<code>{}</code>").format(file)
    if locator:
        shown += Markup(" · {}").format(locator.strip().strip("# ").strip())
    href = links.data_ref(file, locator) if links is not None else None
    return Markup('<a href="{}">{}</a>').format(href, shown) if href else shown


def bare_repo_paths(page: str) -> list[str]:
    """The `<code>` texts of `page` that look like repo paths (`docs/…`, `config/…`, …) and are
    not inside a link: what a public page must not print (the deploy-check guard)."""
    found, depth = [], 0
    for m in _TOKEN.finditer(page):
        token = m.group(0)
        low = token[:3].lower()
        if low.startswith("<a ") or low == "<a>":
            depth += 1
        elif low == "</a":
            depth = max(0, depth - 1)
        elif m.group(1) is not None and depth == 0:
            text = html.unescape(m.group(1)).strip()
            if text.startswith(tuple(f"{d}/" for d in REPO_DIRS)):
                found.append(text)
    return found
