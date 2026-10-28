"""Links to the public repository (M16, legal review 1.1c, rulings R42 and R44).

A page that names a repo file (a data reference's file, a code span holding a path) links it to
`site.yaml` `repo.file_url` at the commit the page was built from, so a citation never rots. With
`repo` unset nothing is linked and pages render as before.
"""

import html
import re
import subprocess
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from markupsafe import Markup, escape

# the repository root: src/velometer/app/repo_links.py -> parents[3]
ROOT = Path(__file__).resolve().parents[3]

# what a public page must never print unlinked (the deploy-check guard): a path under one of
# these directories, one of these root files, or any path-like name of a source or text file
REPO_DIRS = ("docs", "config", "src", "tools", "content", "sites", "deploy", "tests")
REPO_ROOT_FILES = re.compile(r"(HANDOVER\.md|pyproject\.toml|README(\.[\w.-]+)?|CLAUDE\.md)")
FILE_LIKE = re.compile(r"[\w.-]+(/[\w.-]+)*\.(py|ya?ml|md|mjs|js|json|toml)")

_TOKEN = re.compile(
    r"(?P<script><script\b.*?</script\s*>)|(?P<comment><!--.*?-->)|(?P<open><a\b[^>]*>)"
    r"|(?P<close></a\s*>)|<code>(?P<code>[^<>]*)</code>",
    re.S | re.I,
)
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.M)
_FENCE = re.compile(r"^(```|~~~).*?^\1", re.M | re.S)


def heading_slug(text: str) -> str:
    """GitHub's and Forgejo's anchor for a heading: lowercase, every character that is not a
    letter, number or mark (Unicode categories L, N, M), space, hyphen or underscore dropped,
    each space a hyphen."""
    kept = "".join(c for c in text.lower() if unicodedata.category(c)[0] in "LNM" or c in " -_")
    return kept.replace(" ", "-")


def heading_anchor(locator: str | None, text: str | None = None) -> str | None:
    """The anchor of a heading locator (`### warsaw/lau/2025` -> `warsawlau2025`), None for a
    locator that is not a heading. With the file's `text`, a repeated heading gets the suffix
    the forges give it (`-1`, `-2`, ...) and a heading the file lacks (at that level) gets no
    anchor. Headings in code fences do not count."""
    if not locator or not locator.lstrip().startswith("#"):
        return None
    stripped = locator.strip()
    level = len(stripped) - len(stripped.lstrip("#"))
    wanted = stripped.lstrip("#").strip()
    slug = heading_slug(wanted)
    if not slug:
        return None
    if text is None:
        return slug
    seen: dict[str, int] = {}
    for m in _HEADING.finditer(_FENCE.sub("", text)):
        s = heading_slug(m.group(2))
        n = seen.get(s, 0)
        seen[s] = n + 1
        if len(m.group(1)) == level and m.group(2) == wanted:
            return s if n == 0 else f"{s}-{n}"
    return None


@lru_cache(maxsize=4096)
def file_anchor(path: Path, locator: str | None) -> str | None:
    """`heading_anchor` of `locator` in the file at `path` (cached per file and locator: tests
    that change a fixture file call `file_anchor.cache_clear()`)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = None
    return heading_anchor(locator, text)


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


def _outside_links(page: str) -> Iterator[re.Match]:
    """The `<code>` matches of `page` that are not inside an `<a>`, a script or a comment."""
    depth = 0
    for m in _TOKEN.finditer(page):
        if m.group("open"):
            depth += 1
        elif m.group("close"):
            depth = max(0, depth - 1)
        elif m.group("code") is not None and depth == 0:
            yield m


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
        return self.url(file, file_anchor(self.root / file.strip(), locator))

    def link_code(self, page: str) -> str:
        """`page` with every `<code>` that holds nothing but a repo path, and is not already
        inside a link, made a link to that path (scripts and comments are left alone)."""
        out, last = [], 0
        for m in _outside_links(page):
            path = html.unescape(m.group("code"))
            if self.exists(path):
                out.append(page[last : m.start()])
                out.append(f'<a href="{escape(self.url(path))}">{m.group(0)}</a>')
                last = m.end()
        out.append(page[last:])
        return "".join(out)

    def code_links(self, md: str) -> dict[str, str]:
        """`{path: url}` of the markdown code spans of `md` that hold a repo path (the client
        renders those as links, R44)."""
        spans = (s.strip() for s in re.findall(r"`([^`\n]+)`", md))
        return {s: self.url(s) for s in spans if self.exists(s)}


def make_links(
    site, commit: str | None, root: Path = ROOT, paths: frozenset[str] | None = None
) -> RepoLinks | None:
    """The links of `site` (a SiteConfig) at `commit`, over the repo at `root` with its tracked
    `paths` (default: `git ls-files` there); None when `repo` is unset or the commit unknown.
    A dev server or non-public export links HEAD even when the tree is dirty (accepted, R42):
    only `export --public` insists on a clean checkout."""
    repo = getattr(site, "repo", None)
    if repo is None or not commit or commit == "unknown":
        return None
    if paths is None:
        paths = tracked_paths(root)
    return RepoLinks(repo.file_url, commit.removesuffix("-dirty"), root, paths)


def data_ref_file(links: RepoLinks | None, file: str, locator: str | None) -> Markup:
    """A data reference's file line as `_cited.html` prints it: `<code>file</code> · locator`,
    a link to the repo when `links` has the file."""
    shown = Markup("<code>{}</code>").format(file)
    if locator:
        shown += Markup(" · {}").format(locator.strip().strip("# ").strip())
    href = links.data_ref(file, locator) if links is not None else None
    return Markup('<a href="{}">{}</a>').format(href, shown) if href else shown


def looks_like_repo_path(text: str) -> bool:
    """Whether a `<code>` text reads as a repo path: under a repo directory, a root file, or a
    path-like name of a source or text file (`sources/boundaries.py`)."""
    return (
        text.startswith(tuple(f"{d}/" for d in REPO_DIRS))
        or REPO_ROOT_FILES.fullmatch(text) is not None
        or FILE_LIKE.fullmatch(text) is not None
    )


def bare_repo_paths(page: str) -> list[str]:
    """The `<code>` texts of `page` that look like repo paths and are not inside a link: what a
    public page must not print (the deploy-check guard)."""
    texts = (html.unescape(m.group("code")).strip() for m in _outside_links(page))
    return [t for t in texts if looks_like_repo_path(t)]
