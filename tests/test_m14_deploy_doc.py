"""docs/deploy.md's Caddyfile sends the headers the export's `_headers` file holds (final review
M6), on every response including the 404 page (T3)."""

import re
from pathlib import Path

from velometer.app.export import headers_text
from velometer.app.main import CSP, csp_meta

DOC = Path(__file__).parents[1] / "docs" / "deploy.md"


def _caddyfile(doc: str) -> str:
    blocks = re.findall(r"```\n(.*?)```", doc, re.S)
    found = [b for b in blocks if "handle_errors" in b]
    assert len(found) == 1, "one Caddyfile in docs/deploy.md"
    return found[0]


def _block(text: str, opener: str) -> str:
    """The body of the `{ … }` block whose line starts with `opener`."""
    start = text.index(opener)
    i, depth = text.index("{", start), 0
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[i + 1 : j]
    raise AssertionError(f"unclosed block {opener}")


def _caddy_headers(caddyfile: str) -> dict[str, str]:
    snippet = _block(caddyfile, "(security_headers)")
    out = {}
    for line in _block(snippet, "header").strip().splitlines():
        name, value = line.strip().split(" ", 1)
        out[name] = value.strip().removeprefix('"').removesuffix('"')
    return out


def _headers_file(text: str) -> dict[str, str]:
    lines = text.splitlines()[1:]  # the first line is the path pattern
    return dict(line.strip().split(": ", 1) for line in lines if line.strip())


def test_the_caddyfile_headers_equal_the_exported_headers_file():
    caddy = _caddy_headers(_caddyfile(DOC.read_text(encoding="utf-8")))
    assert caddy == _headers_file(headers_text("/", csp_meta(CSP)))


def test_the_caddyfile_sends_the_headers_on_the_404_page_too():
    caddyfile = _caddyfile(DOC.read_text(encoding="utf-8"))
    site = _block(caddyfile, "velometer.<domain>")
    errors = _block(site, "handle_errors")
    assert "import security_headers" in site.replace(errors, "")
    assert "import security_headers" in errors
