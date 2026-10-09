"""The base path every URL the app emits carries (M9 spec decision 3).

The routes stay at `/…`; a page built for a host that serves the site under a sub-path
(`/velometer/`) writes every internal `href`, `src`, `action` and every URL a script reads from
a JSON config through `u(path)`. The live app runs with base `/`, where `u` is the identity.
"""

from collections.abc import Callable


def normalise_base(base: str) -> str:
    """`base` with exactly one leading and one trailing `/` ("" and "/" are `/`)."""
    inner = base.strip("/")
    return "/" if not inner else f"/{inner}/"


def _is_external(url: str) -> bool:
    """A scheme (`https:`, `mailto:`) or a protocol-relative `//host`: not ours to prefix."""
    if url.startswith("//"):
        return True
    scheme, colon, _ = url.partition(":")
    return bool(colon) and scheme.isalpha() and "/" not in scheme


def make_u(base: str) -> Callable[[str], str]:
    """The URL helper of a base path: `u("/city/berlin")` is `<base>city/berlin` (query and
    fragment kept). External URLs (a scheme or `//host`) and fragment-only `#x` come back
    unchanged; any other path must start with `/` (a relative path would resolve against the
    page, not the base), else ValueError."""
    prefix = normalise_base(base)

    def u(path: str) -> str:
        if path.startswith("#") or _is_external(path):
            return path
        if not path.startswith("/"):
            raise ValueError(f"an internal URL must start with '/': {path!r}")
        return prefix + path[1:]

    return u
