"""The colour tokens of `static/app.css` as `{token: [light, dark]}` (M11 chart downloads).

A download is always drawn in the light theme. The page may be showing the dark one, where the
browser's computed style gives the dark values, so `download.js` maps each dark value back to its
light value with this table. Only plain hex tokens are kept: they are the colours a chart draws.
"""

import re

_BLOCK = re.compile(r":root\s*\{([^}]*)\}")
_DARK = re.compile(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{([^}]*)\}")
_DECL = re.compile(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;")


def _decls(block: str) -> dict[str, str]:
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    return {k: v.lower() for k, v in _DECL.findall(block)}


def theme_tokens(css: str) -> dict[str, list[str]]:
    """Token name -> [light, dark], from the light `:root` and the dark `:root` block; a token the
    dark block leaves out keeps its light value."""
    dark_m = _DARK.search(css)
    dark = _decls(dark_m.group(1)) if dark_m else {}
    light_m = _BLOCK.search(css)
    light = _decls(light_m.group(1)) if light_m else {}
    return {k: [v, dark.get(k, v)] for k, v in light.items()}
