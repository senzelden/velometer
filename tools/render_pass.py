"""Render pass: drive headless Chrome over an exported static edition and audit every page.

M10 spec decision 7. Serves the export with `python -m http.server` on 127.0.0.1 under the base
path, opens each page × theme × width in headless Chrome over the DevTools protocol and records
axe-core violations (WCAG 2.1 A/AA tags), sideways overflow, console messages, CSP violations,
the hosts contacted and a full-page screenshot. A failed navigation, a document that is not 200,
a load event that never fires and (with `--interact`) a panel that does not open, close or give
focus back are findings too (`errors`). `results.json` in `--out` holds one entry per visit and
is rewritten after each one; the exit status is 1 when any visit has a finding or nothing was
visited, else 0.

axe-core is vendored in `tools/axe/` (pinned in `tools/axe/VERSION`) and injected through
`Runtime.evaluate`, which the page's CSP does not apply to; it is never served by the app.

    uv run --group dev python tools/render_pass.py --site DIR --base /velometer/ \
        --out tools/out/NAME [--themes light,dark] [--widths 1280,390,320] \
        [--pages all|types|<url>,...] [--flip] [--interact] [--keyboard] [--chrome PATH]

`--flip` is a mode of its own: each page loads in light, the emulated scheme switches to dark
mid-page, and after 500 ms the page is audited and shot as `<slug>-flipped-<width>.png`.
`--interact` adds, per theme and width, a visit to `<base>compare` that opens a city panel with a
mouse click (table view, first city link), audits the page with the panel open, presses Escape and
checks focus returned to the link. `--keyboard` adds, per theme, a scripted keyboard pass driven by
real key events (`Input.dispatchKeyEvent`): skip link, phone menu, Cities menu, city tabs, compare
(tick, metric, view, sort, panel, Escape) and the tier and counter maps (+ and -); each step is a
line in the entry's `steps`, a failed one is an error. Chrome is `--chrome`, else
`$VELOMETER_CHROME`, else `/usr/bin/google-chrome`.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
AXE_JS = HERE / "axe" / "axe.min.js"
CHROME = "/usr/bin/google-chrome"  # default; --chrome or $VELOMETER_CHROME override it
LOAD_TIMEOUT = 30.0  # seconds for a page's load event; a load that never fires is a finding
OK_STATUS = {200, 304}  # 304: the browser cache revalidated a 200
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
ALLOWED_HOSTS = {"127.0.0.1", "tile.openstreetmap.org"}
# pages in a city are /city/<slug>/<tab>; --pages types keeps Berlin plus the first city (by
# slug) whose tab list differs from Berlin's
TYPES_CITY = "berlin"

# Overflow, as a reader on a phone meets it:
# - a box whose content is wider than it: a scroller, a box that clips it (content lost) or one
#   it spills out of, including a leaf whose own text spills (nowrap, a long word);
# - the document wider than the layout viewport, reported as ":root".
# Not counted: anything inside a prose table (allowed to scroll, spec decision 5), the Leaflet map
# (its panes sit beyond the viewport by design), text cut with `text-overflow: ellipsis`, the
# visually-hidden pattern (a box of 1px or less), and a box whose only spill is a prose table that
# actually sticks out of it (prose tables may be wider than the prose column).
OVERFLOW_JS = r"""
(() => {
  const sel = (el) => {
    const parts = [];
    for (let e = el; e && e.nodeType === 1 && parts.length < 4; e = e.parentElement) {
      let s = e.localName;
      if (e.id) { parts.unshift(s + '#' + e.id); break; }
      const cls = [...e.classList].slice(0, 2);
      if (cls.length) s += '.' + cls.join('.');
      parts.unshift(s);
    }
    return parts.join(' > ');
  };
  const inProse = (e) => !!e.closest('.prose table');
  // does the element's own text (its direct text nodes) reach past `right`?
  const textSpills = (el, right) => {
    for (const n of el.childNodes) {
      if (n.nodeType !== 3 || !n.textContent.trim()) continue;
      const r = document.createRange();
      r.selectNodeContents(n);
      for (const b of r.getClientRects()) if (b.right > right) return true;
    }
    return false;
  };
  // true only if a prose table really sticks out of el and nothing else does
  const onlyProse = (el) => {
    const right = el.getBoundingClientRect().left + el.clientLeft + el.clientWidth + 1;
    if (textSpills(el, right)) return false;
    let prose = false;
    for (const d of el.querySelectorAll('*')) {
      const spills = d.getBoundingClientRect().right > right || textSpills(d, right);
      if (!spills) continue;
      if (inProse(d)) prose = true;
      else return false;
    }
    return prose;
  };
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.scrollWidth <= el.clientWidth + 1) continue;
    if (inProse(el) || el.closest('.leaflet-container')) continue;
    const box = el.getBoundingClientRect();
    if (box.width <= 1 || box.height <= 1) continue;  // visually hidden
    const cs = getComputedStyle(el);
    if (cs.textOverflow === 'ellipsis') continue;
    const ox = cs.overflowX;
    if (ox === 'visible' && onlyProse(el)) continue;
    const how = ox === 'hidden' || ox === 'clip' ? ' clipped' : '';
    out.push(sel(el) + ' (' + el.scrollWidth + '>' + el.clientWidth + how + ')');
  }
  const root = document.documentElement;
  if (root.scrollWidth > root.clientWidth + 1)
    out.unshift(':root (' + root.scrollWidth + '>' + root.clientWidth + ')');
  return [...new Set(out)];
})()
"""

AXE_RUN_JS = """
axe.run(document, {runOnly: {type: 'tag', values: TAGS}, resultTypes: ['violations']})
  .then(r => r.violations.map(v => ({
    id: v.id, impact: v.impact,
    nodes: v.nodes.map(n => n.target.map(t => Array.isArray(t) ? t.join(' >>> ') : t)
                               .join(' >>> '))})))
""".replace("TAGS", json.dumps(AXE_TAGS))


def page_urls(site: Path, base: str) -> list[str]:
    """Every exported page: `<dir>/index.html` is `<base><dir>`, `index.html` is `<base>`.

    `404.html`, non-HTML files and HTML fragments (no `<html` element: the city panels, which are
    loaded into a page, not visited) are skipped.
    """
    base = _norm_base(base)
    urls = []
    for f in sorted(site.rglob("index.html")):
        head = f.read_text(encoding="utf-8", errors="replace")[:2048].lower()
        if "<html" not in head:
            continue
        rel = f.parent.relative_to(site).as_posix()
        urls.append(base if rel == "." else base + rel)
    return sorted(urls)


def type_urls(urls: list[str], base: str) -> list[str]:
    """One page per tab type: every page outside /city/, plus Berlin's and one other city's."""
    city_re = re.compile(re.escape(_norm_base(base)) + r"city/([^/]+)(?:/(.*))?$")
    tabs: dict[str, list[str]] = defaultdict(list)
    keep = []
    for u in urls:
        m = city_re.match(u)
        if m:
            tabs[m[1]].append(m[2] or "")
        else:
            keep.append(u)
    chosen = [TYPES_CITY] if TYPES_CITY in tabs else []
    ref = sorted(tabs.get(TYPES_CITY, []))
    for slug in sorted(tabs):
        if slug != TYPES_CITY and sorted(tabs[slug]) != ref:
            chosen.append(slug)
            break
    for slug in chosen:
        keep += [f"{_norm_base(base)}city/{slug}" + (f"/{t}" if t else "") for t in tabs[slug]]
    return sorted(keep)


def _norm_base(base: str) -> str:
    return "/" + base.strip("/") + "/" if base.strip("/") else "/"


def slug(url: str, base: str) -> str:
    path = url[len(_norm_base(base)) :] if url.startswith(_norm_base(base)) else url
    s = re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-")
    return s or "index"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_http(url: str, seconds: float = 15) -> None:
    end = time.time() + seconds
    while True:
        try:
            urllib.request.urlopen(url, timeout=2).close()
            return
        except OSError:
            if time.time() > end:
                raise
            time.sleep(0.2)


class Tab:
    """One Chrome tab over a DevTools websocket; events are kept in arrival order."""

    def __init__(self, devtools: str, ws_url: str, target_id: str):
        import websocket  # dev dependency group

        self._wsmod = websocket
        self.devtools = devtools
        self.id = target_id
        self.ws = websocket.create_connection(ws_url, timeout=120, suppress_origin=True)
        self.n = 0
        self.events: list[dict] = []

    def call(self, method: str, **params):
        self.n += 1
        my = self.n
        self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == my:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
            self.events.append(m)

    def pump(self, seconds: float) -> None:
        end = time.time() + seconds
        self.ws.settimeout(0.1)
        while time.time() < end:
            with contextlib.suppress(self._wsmod.WebSocketTimeoutException):
                self.events.append(json.loads(self.ws.recv()))
        self.ws.settimeout(120)

    def wait_event(self, method: str, since: int, cap: float) -> bool:
        """True when `method` arrived after event `since` within `cap` seconds."""
        end = time.time() + cap
        while True:
            if any(e.get("method") == method for e in self.events[since:]):
                return True
            if time.time() >= end:
                return False
            self.pump(0.1)

    def wait_js(self, expr: str, cap: float) -> bool:
        """True when the JS expression is truthy within `cap` seconds."""
        end = time.time() + cap
        while True:
            if self.js(expr):
                return True
            if time.time() >= end:
                return False
            self.pump(0.1)

    def js(self, expr: str, await_promise: bool = False):
        r = self.call(
            "Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=await_promise
        )
        if "exceptionDetails" in r:
            raise RuntimeError(f"js: {r['exceptionDetails']}")
        return r["result"].get("value")

    def close(self) -> None:
        self.ws.close()
        with contextlib.suppress(OSError):
            urllib.request.urlopen(f"{self.devtools}/json/close/{self.id}").close()


def open_tab(devtools: str, width: int, theme: str) -> Tab:
    req = urllib.request.Request(f"{devtools}/json/new?about:blank", method="PUT")
    with urllib.request.urlopen(req) as r:
        info = json.load(r)
    t = Tab(devtools, info["webSocketDebuggerUrl"], info["id"])
    try:
        for domain in ("Page", "Network", "Runtime", "Log", "Audits"):
            t.call(f"{domain}.enable")
        phone = width < 600
        t.call(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=844 if phone else 900,
            deviceScaleFactor=1,
            mobile=phone,
        )
        set_theme(t, theme)
    except BaseException:
        t.close()
        raise
    return t


def set_theme(t: Tab, theme: str) -> None:
    t.call(
        "Emulation.setEmulatedMedia",
        features=[{"name": "prefers-color-scheme", "value": theme}],
    )


def _args_text(args: list[dict]) -> str:
    return " ".join(str(a.get("value", a.get("description", a.get("type", "")))) for a in args)


def collect(events: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """(console, csp, hosts) from the DevTools events of one visit."""
    console, csp, hosts = [], [], set()
    for e in events:
        m, p = e.get("method"), e.get("params", {})
        if m == "Network.requestWillBeSent":
            parts = urlsplit(p["request"]["url"])
            if parts.scheme in ("http", "https", "ws", "wss"):
                hosts.add(parts.hostname or "")
        elif m == "Runtime.consoleAPICalled":
            console.append(f"console.{p['type']}: {_args_text(p.get('args', []))}")
        elif m == "Runtime.exceptionThrown":
            d = p["exceptionDetails"]
            console.append(f"exception: {d.get('exception', {}).get('description', d['text'])}")
        elif m == "Log.entryAdded" and p["entry"]["level"] in ("error", "warning"):
            en = p["entry"]
            console.append(f"log.{en['level']} [{en['source']}]: {en['text']} {en.get('url', '')}")
        elif m == "Audits.issueAdded" and p["issue"]["code"] == "ContentSecurityPolicyIssue":
            d = p["issue"]["details"].get("contentSecurityPolicyIssueDetails", {})
            loc = d.get("sourceCodeLocation", {})
            csp.append(
                f"{d.get('violatedDirective', '?')} {d.get('blockedURL', '')} "
                f"{d.get('contentSecurityPolicyViolationType', '')} "
                f"{loc.get('url', '')}:{loc.get('lineNumber', '')}".strip()
            )
    return console, csp, sorted(hosts)


def screenshot(t: Tab, path: Path, width: int) -> str:
    h = t.js("Math.max(1, Math.min(document.documentElement.scrollHeight, 16000))")
    shot = t.call(
        "Page.captureScreenshot",
        format="png",
        captureBeyondViewport=True,
        clip={"x": 0, "y": 0, "width": width, "height": h, "scale": 1},
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(shot["data"]))
    return str(path)


def navigate(t: Tab, url: str) -> list[str]:
    """Load `url`; the errors are a failed navigation, a non-200 document and a missing load."""
    since = len(t.events)
    res = t.call("Page.navigate", url=url)
    if res.get("errorText"):
        return [f"navigation failed: {res['errorText']} {url}"]
    errors = []
    if not t.wait_event("Page.loadEventFired", since, LOAD_TIMEOUT):
        errors.append(f"load event did not fire within {LOAD_TIMEOUT:g} s: {url}")
    docs = [
        e["params"]["response"]
        for e in t.events[since:]
        if e.get("method") == "Network.responseReceived"
        and e["params"].get("type") == "Document"
        and e["params"].get("frameId") == res.get("frameId")
    ]
    if not docs:
        errors.append(f"no document response: {url}")
    elif docs[-1]["status"] not in OK_STATUS:
        errors.append(f"document HTTP {docs[-1]['status']}: {url}")
    return errors


def audit(t: Tab) -> list[dict]:
    t.js(AXE_JS.read_text(encoding="utf-8"))
    return t.js(AXE_RUN_JS, await_promise=True)


def entry(url, theme, width, kind, *, axe=(), overflow=(), events=(), errors=(), shot=None):
    console, csp, hosts = collect(list(events))
    return {
        "url": url,
        "theme": theme,
        "width": width,
        "kind": kind,
        "axe": list(axe),
        "overflow": list(overflow),
        "console": console,
        "csp": csp,
        "hosts": hosts,
        "errors": list(errors),
        "screenshot": shot,
    }


def visit(devtools: str, origin: str, url: str, theme: str, width: int, shots: Path, base: str,
          flip: bool = False) -> dict:  # fmt: skip
    kind, label = ("flip", "light->dark") if flip else ("page", theme)
    t = None
    try:
        t = open_tab(devtools, width, "light" if flip else theme)
        errors = navigate(t, origin + url)
        if any(e.startswith("navigation failed") for e in errors):
            return entry(url, label, width, kind, events=t.events, errors=errors)
        t.pump(1.5)
        if flip:
            set_theme(t, "dark")
            t.pump(0.5)
        # console, CSP and hosts belong to the page, not to axe: collect before injecting it
        events = list(t.events)
        overflow = t.js(OVERFLOW_JS)
        name = f"{slug(url, base)}-{'flipped' if flip else theme}-{width}.png"
        shot = screenshot(t, shots / name, width)
        axe = audit(t)
        return entry(url, label, width, kind, axe=axe, overflow=overflow, events=events,
                     errors=errors, shot=shot)  # fmt: skip
    finally:
        if t is not None:
            t.close()


# The Compare city panel (a fragment, so never a page of its own): open it as a reader does, audit
# the page with it open, close it with Escape and check focus went back to the link that opened it.
PANEL_OPEN_JS = (
    "(() => { const p = document.querySelector('#city-panel');"
    " return !!p && !p.hidden && !!p.querySelector('.slideover-body .panel-frag'); })()"
)
PANEL_CLOSED_JS = (
    "(() => { const p = document.querySelector('#city-panel'); return !p || p.hidden; })()"
)


def click(t: Tab, selector: str) -> str | None:
    """Scroll the first visible match into view and click its centre with the mouse; None, or why
    it could not."""
    box = t.js(
        "(() => { const e = [...document.querySelectorAll(" + json.dumps(selector) + ")]"
        ".find(x => x.getClientRects().length); if (!e) return null;"
        " e.scrollIntoView({block: 'center'}); window.__clicked = e;"
        " const r = e.getBoundingClientRect(); return {x: r.left + r.width / 2,"
        " y: r.top + r.height / 2}; })()"
    )
    if not box:
        return f"nothing visible to click: {selector}"
    for typ in ("mouseMoved", "mousePressed", "mouseReleased"):
        t.call("Input.dispatchMouseEvent", type=typ, x=box["x"], y=box["y"], button="left",
               clickCount=1)  # fmt: skip
    return None


def interact(devtools: str, origin: str, base: str, theme: str, width: int, shots: Path) -> dict:
    url = base + "compare"
    label = url + " (city panel)"
    t = None
    try:
        t = open_tab(devtools, width, theme)
        errors = navigate(t, origin + url)
        if errors:
            return entry(label, theme, width, "interact", events=t.events, errors=errors)
        t.pump(1.5)
        # the table view lists every selected city as a link that opens its panel
        if why := click(t, ".view-tabs a[data-view=table]"):
            return entry(label, theme, width, "interact", events=t.events, errors=[why])
        if not t.wait_js("!!document.querySelector('table a[data-city]')", 5):
            return entry(label, theme, width, "interact", events=t.events,
                         errors=["the table view shows no city link"])  # fmt: skip
        if why := click(t, "table a[data-city]"):
            return entry(label, theme, width, "interact", events=t.events, errors=[why])
        t.js("window.__opener = window.__clicked")
        if not t.wait_js(PANEL_OPEN_JS, 10):
            return entry(label, theme, width, "interact", events=t.events,
                         errors=["the city panel did not open and load"])  # fmt: skip
        t.pump(1.0)
        before = len(t.events)
        overflow = t.js(OVERFLOW_JS)
        shot = screenshot(t, shots / f"compare-panel-{theme}-{width}.png", width)
        axe = audit(t)
        after = len(t.events)
        for typ in ("keyDown", "keyUp"):
            t.call("Input.dispatchKeyEvent", type=typ, key="Escape", code="Escape",
                   windowsVirtualKeyCode=27)  # fmt: skip
        if not t.wait_js(PANEL_CLOSED_JS, 3):
            errors.append("Escape did not close the city panel")
        else:
            t.pump(0.3)
            if not t.js("document.activeElement === window.__opener"):
                now = t.js(
                    "(e => e ? e.outerHTML.slice(0, 80) : 'nothing')(document.activeElement)"
                )
                errors.append(f"focus did not return to the opener after Escape (now on {now})")
        events = t.events[:before] + t.events[after:]
        return entry(label, theme, width, "interact", axe=axe, overflow=overflow, events=events,
                     errors=errors, shot=shot)  # fmt: skip
    finally:
        if t is not None:
            t.close()


# ---------- the keyboard pass (--keyboard) ----------
# (key, code, windowsVirtualKeyCode, text); anything not here is a single printable character
KEYS = {
    "Tab": ("Tab", "Tab", 9, ""),
    "Enter": ("Enter", "Enter", 13, "\r"),
    "Escape": ("Escape", "Escape", 27, ""),
    " ": (" ", "Space", 32, " "),
    "ArrowDown": ("ArrowDown", "ArrowDown", 40, ""),
    "+": ("+", "Equal", 187, "+"),  # Leaflet reads keyCode 187/107 for zoom in
    "-": ("-", "Minus", 189, "-"),
}
SHIFT = 8


def key_params(name: str, down: bool, shift: bool = False) -> dict:
    """`Input.dispatchKeyEvent` parameters for one key press half."""
    key, code, vk, text = KEYS[name]
    p = {"type": "keyDown" if down else "keyUp", "key": key, "code": code,
         "windowsVirtualKeyCode": vk, "modifiers": SHIFT if shift else 0}  # fmt: skip
    if down and text:
        p["text"] = text
    return p


def press(t: Tab, name: str, shift: bool = False, wait: float = 0.15) -> None:
    for down in (True, False):
        t.call("Input.dispatchKeyEvent", **key_params(name, down, shift))
    t.pump(wait)


FOCUS_JS = r"""
(() => {
  const e = document.activeElement;
  if (!e || e === document.body) return null;
  const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
  const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0)
    || (cs.boxShadow !== 'none');
  return {tag: e.localName, cls: typeof e.className === 'string' ? e.className : '',
    text: (e.getAttribute('aria-label') || e.textContent || e.value || '').trim().slice(0, 40),
    visible: r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight
      && r.right > 0 && r.left < innerWidth,
    ring, focusVisible: e.matches(':focus-visible')};
})()
"""


# the ids an aria-describedby/labelledby/controls names that no element has
IDREFS_JS = r"""
(() => {
  const missing = new Set();
  for (const a of ['aria-describedby', 'aria-labelledby', 'aria-controls'])
    for (const e of document.querySelectorAll('[' + a + ']'))
      for (const id of e.getAttribute(a).split(/\s+/).filter(Boolean))
        if (!document.getElementById(id)) missing.add(a + ' -> #' + id);
  return [...missing];
})()
"""


def where(t: Tab) -> str:
    f = t.js(FOCUS_JS)
    return "nothing focused" if not f else f"{f['tag']}.{f['cls']} '{f['text']}'"


def tab_to(t: Tab, selector: str, cap: int = 250) -> str | None:
    """Press Tab until the focused element matches `selector`; None, or why not within `cap`."""
    test = f"!!document.activeElement && document.activeElement.matches({json.dumps(selector)})"
    for _ in range(cap):
        if t.js(test):
            return None
        press(t, "Tab", wait=0.02)
    return f"Tab did not reach {selector} in {cap} presses (focus is on {where(t)})"


def focus_shown(t: Tab) -> str | None:
    """None when the focused element is on screen with a visible focus ring, else why not."""
    f = t.js(FOCUS_JS)
    if not f:
        return "nothing focused"
    if not f["visible"]:
        return f"focused {f['tag']} '{f['text']}' is off screen"
    if not (f["ring"] and f["focusVisible"]):
        return f"focused {f['tag']} '{f['text']}' shows no focus ring"
    return None


class Steps:
    """Records the steps of one keyboard pass."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.errors: list[str] = []

    def check(self, name: str, why: str | None, detail: str = "") -> bool:
        if why:
            self.lines.append(f"FAIL {name}: {why}")
            self.errors.append(f"{name}: {why}")
        else:
            self.lines.append(f"ok   {name}" + (f" ({detail})" if detail else ""))
        return why is None


def _page(devtools, origin, base, theme, width, path) -> tuple[Tab, list[str]]:
    t = open_tab(devtools, width, theme)
    errors = navigate(t, origin + base + path)
    t.pump(1.5)
    return t, errors


def _zoom(t: Tab) -> int:
    """The highest tile zoom level in the DOM (a tile's URL is .../{z}/{x}/{y}.png)."""
    return t.js(
        "Math.max(0, ...[...document.querySelectorAll('img.leaflet-tile')]"
        ".map(i => +((i.src.match(/\\/(\\d+)\\/\\d+\\/\\d+\\.png/) || [])[1] || 0)))"
    )


def _map_steps(devtools, origin, base, theme, path, label, st: Steps) -> None:
    t = None
    try:
        t, errs = _page(devtools, origin, base, theme, 1280, path)
        if not st.check(f"{label}: page loads", "; ".join(errs) or None):
            return
        if not st.check(f"{label}: Tab reaches the map", tab_to(t, ".leaflet-container", 400)):
            return
        st.check(f"{label}: the map shows a focus ring", focus_shown(t))
        t.pump(1.5)
        z0 = _zoom(t)
        press(t, "+", wait=1.5)
        z1 = _zoom(t)
        st.check(f"{label}: + zooms in", None if z1 > z0 else f"zoom stayed {z0}->{z1}",
                 f"{z0}->{z1}")  # fmt: skip
        press(t, "-", wait=1.5)
        press(t, "-", wait=1.5)
        t.pump(0.5)
        z2 = _zoom(t)
        st.check(f"{label}: - zooms out", None if z2 < z1 else f"zoom stayed {z1}->{z2}",
                 f"{z1}->{z2}")  # fmt: skip
    finally:
        if t is not None:
            t.close()


def _skip_link(devtools, origin, base, theme, st: Steps) -> None:
    t, errs = _page(devtools, origin, base, theme, 1280, "")
    try:
        if not st.check("skip link: page loads", "; ".join(errs) or None):
            return
        press(t, "Tab")
        on = t.js("document.activeElement.matches('a.skip')")
        st.check("skip link: the first Tab lands on it", None if on else f"on {where(t)}")
        st.check("skip link: visible with a focus ring", focus_shown(t))
        press(t, "Enter", wait=0.4)
        moved = t.js("document.activeElement === document.querySelector('main')")
        hashed = t.js("location.hash === '#main'")
        st.check("skip link: Enter moves focus to main",
                 None if moved and hashed else f"on {where(t)}")  # fmt: skip
        press(t, "Tab")
        inside = t.js("!!document.activeElement.closest('main')")
        st.check("skip link: the next Tab stays inside main",
                 None if inside else f"on {where(t)}")  # fmt: skip
    finally:
        t.close()


def _cities_menu(devtools, origin, base, theme, st: Steps) -> None:
    t, errs = _page(devtools, origin, base, theme, 1280, "")
    try:
        if not st.check("cities menu: page loads", "; ".join(errs) or None):
            return
        if not st.check("cities menu: Tab reaches the summary",
                        tab_to(t, "details.cities-menu > summary")):  # fmt: skip
            return
        st.check("cities menu: the summary has a focus ring", focus_shown(t))
        press(t, "Enter", wait=0.4)
        opened = t.js("document.querySelector('details.cities-menu').open")
        st.check("cities menu: Enter opens it", None if opened else "still closed")
        press(t, "Escape", wait=0.3)
        closed = t.js(
            "!document.querySelector('details.cities-menu').open && document.activeElement"
            " === document.querySelector('details.cities-menu > summary')"
        )
        st.check("cities menu: Escape closes it, focus back on the summary",
                 None if closed else f"on {where(t)}")  # fmt: skip
    finally:
        t.close()


def _phone_menu(devtools, origin, base, theme, st: Steps) -> None:
    t, errs = _page(devtools, origin, base, theme, 390, "")
    try:
        if not st.check("phone menu: page loads", "; ".join(errs) or None):
            return
        if not st.check("phone menu: Tab reaches the Menu button", tab_to(t, ".menu-toggle", 10)):
            return
        expanded = "document.querySelector('.menu-toggle').getAttribute('aria-expanded')"
        st.check("phone menu: the button has a focus ring", focus_shown(t))
        press(t, "Enter", wait=0.3)
        st.check("phone menu: Enter opens it",
                 None if t.js(expanded) == "true" else "aria-expanded stayed false")  # fmt: skip
        press(t, "Tab")
        st.check("phone menu: the next Tab enters the menu links",
                 None if t.js("!!document.activeElement.closest('#site-nav')")
                 else f"on {where(t)}")  # fmt: skip
        st.check("phone menu: that link is on screen with a focus ring", focus_shown(t))
        press(t, "Tab", shift=True)
        press(t, " ", wait=0.3)
        st.check("phone menu: Space on the button closes it",
                 None if t.js(expanded) == "false" else "still open")  # fmt: skip
    finally:
        t.close()


def _city_tabs(devtools, origin, base, theme, st: Steps) -> None:
    t, errs = _page(devtools, origin, base, theme, 1280, "city/berlin")
    try:
        if not st.check("city tabs: page loads", "; ".join(errs) or None):
            return
        n = t.js("document.querySelectorAll('nav.tabs a').length")
        if not st.check("city tabs: Tab reaches the first tab", tab_to(t, "nav.tabs a")):
            return
        bad = focus_shown(t)
        for _ in range(n - 1):
            press(t, "Tab", wait=0.05)
            bad = bad or focus_shown(t)
        st.check(f"city tabs: all {n} tabs take focus, on screen with a ring", bad)
        press(t, "Tab", shift=True)
        href = t.js("document.activeElement.getAttribute('href')").rstrip("/")
        press(t, "Enter", wait=0.2)
        there = f"location.pathname.replace(/\\/$/, '').endsWith({json.dumps(href)})"
        t.wait_js(there, 5)
        st.check("city tabs: Enter on a tab goes there",
                 None if t.js(there) else f"still on {t.js('location.pathname')}")  # fmt: skip
    finally:
        t.close()


def _compare(devtools, origin, base, theme, st: Steps) -> None:
    t, errs = _page(devtools, origin, base, theme, 1280, "compare")
    try:
        if not st.check("compare: page loads", "; ".join(errs) or None):
            return
        if not st.check("compare: Tab reaches a city checkbox", tab_to(t, "input[name=c]")):
            return
        st.check("compare: the checkbox has a focus ring", focus_shown(t))
        count = "document.querySelectorAll('input[name=c]:checked').length"
        before = t.js(count)
        press(t, " ", wait=0.4)
        after = t.js(count)
        st.check("compare: Space ticks or unticks a city",
                 None if after != before else "the checked count did not change",
                 f"{before}->{after}")  # fmt: skip
        if st.check("compare: Tab reaches the metric select", tab_to(t, "select[name=m]")):
            m0 = t.js("document.querySelector('select[name=m]').value")
            h0 = t.js("document.querySelector('[data-compare-title] h2').textContent")
            press(t, "ArrowDown", wait=0.8)
            m1 = t.js("document.querySelector('select[name=m]').value")
            h1 = t.js("document.querySelector('[data-compare-title] h2').textContent")
            st.check("compare: ArrowDown changes the metric and the title",
                     None if m1 != m0 and h1 != h0 else f"metric {m0}->{m1}, title kept",
                     f"{m0}->{m1}")  # fmt: skip
        if not st.check("compare: Tab reaches the table view tab",
                        tab_to(t, ".view-tabs a[data-view=table]")):  # fmt: skip
            return
        press(t, "Enter", wait=0.8)
        shown = t.js(
            "!!document.querySelector('table.compare-table') && document"
            ".querySelector('[data-compare-table]').getClientRects().length > 0"
        )
        st.check("compare: Enter switches to the table view",
                 None if shown else "no table on screen")  # fmt: skip
        if st.check(
            "compare: Tab reaches a sort button", tab_to(t, "th:not(:first-child) > button.sort")
        ):
            name = t.js("document.activeElement.textContent")
            order = "(document.querySelector('th[aria-sort=ascending], th[aria-sort=descending]')"
            order += " || {getAttribute: () => 'none'}).getAttribute('aria-sort')"
            on_sort = "document.activeElement.matches('button.sort')"
            press(t, "Enter", wait=0.5)
            first = t.js(order)
            why = None if first != "none" else "no column is marked as sorted"
            st.check("compare: Enter on a header sorts the table", why, name)
            st.check("compare: focus stays on the sort button after the table is rebuilt",
                     None if t.js(on_sort) else f"focus is on {where(t)}")  # fmt: skip
            press(t, "Enter", wait=0.5)
            second = t.js(order)
            st.check("compare: a second Enter reverses the order",
                     None if second not in ("none", first) else f"{first} then {second}",
                     f"{first} then {second}")  # fmt: skip
            st.check("compare: focus is still on the sort button",
                     None if t.js(on_sort) else f"focus is on {where(t)}")  # fmt: skip
        if not st.check("compare: Tab reaches a city link", tab_to(t, "table a[data-city]")):
            return
        t.js("window.__opener = document.activeElement")
        press(t, "Enter", wait=0.2)
        opened = t.wait_js(PANEL_OPEN_JS, 10)
        if not st.check("compare: Enter on a city opens its panel",
                        None if opened else "the panel did not open"):  # fmt: skip
            return
        t.pump(0.8)
        st.check("compare: focus moves into the panel",
                 None if t.js("!!document.activeElement.closest('#city-panel')")
                 else f"on {where(t)}")  # fmt: skip
        press(t, "Escape", wait=0.4)
        closed = t.wait_js(PANEL_CLOSED_JS, 3)
        back = t.js("document.activeElement === window.__opener")
        st.check("compare: Escape closes it and focus is back on the opener",
                 None if closed and back else f"closed={closed}, on {where(t)}")  # fmt: skip
        # back to the chart after the table was rebuilt: its description must still resolve
        if not st.check("compare: Tab reaches the lines view tab",
                        tab_to(t, ".view-tabs a[data-view=lines]")):  # fmt: skip
            return
        press(t, "Enter", wait=0.8)
        shown = t.js("document.querySelector('[data-compare-chart]').getClientRects().length > 0")
        st.check("compare: Enter switches back to the chart view",
                 None if shown else "the chart is not on screen")  # fmt: skip
        dangling = t.js(IDREFS_JS)
        st.check("compare: every aria-describedby/labelledby on the page resolves in chart view",
                 f"dangling: {', '.join(dangling)}" if dangling else None)  # fmt: skip
        bad = [v["id"] for v in audit(t)]
        st.check("compare: axe finds nothing in chart view after the table", ", ".join(bad) or None)
    finally:
        t.close()


def keyboard(devtools: str, origin: str, base: str, theme: str) -> dict:
    """One scripted keyboard pass in `theme`; the step lines are in the entry's `steps`."""
    st = Steps()
    _skip_link(devtools, origin, base, theme, st)
    _cities_menu(devtools, origin, base, theme, st)
    _phone_menu(devtools, origin, base, theme, st)
    _city_tabs(devtools, origin, base, theme, st)
    _compare(devtools, origin, base, theme, st)
    _map_steps(devtools, origin, base, theme, "city/berlin/tiers", "tier map", st)
    _map_steps(devtools, origin, base, theme, "city/berlin/counts", "counter map", st)
    return entry(base + " (keyboard)", theme, 1280, "keyboard", errors=st.errors) | {
        "steps": st.lines
    }


def failures(r: dict) -> list[str]:
    out = []
    if r["errors"]:
        out.append(f"errors {len(r['errors'])}")
    if r["axe"]:
        out.append(f"axe {len(r['axe'])}")
    if r["overflow"]:
        out.append(f"overflow {len(r['overflow'])}")
    if r["console"]:
        out.append(f"console {len(r['console'])}")
    if r["csp"]:
        out.append(f"csp {len(r['csp'])}")
    foreign = [h for h in r["hosts"] if h not in ALLOWED_HOSTS]
    if foreign:
        out.append(f"hosts {','.join(foreign)}")
    return out


def stop(proc: subprocess.Popen, timeout: float = 10) -> None:
    """Terminate a child; kill it if it has not gone within `timeout` seconds."""
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@contextlib.contextmanager
def serve(site: Path, base: str):
    """`python -m http.server` on 127.0.0.1 with the site reachable under `base`."""
    root = Path(tempfile.mkdtemp(prefix="render-pass-root-"))
    rel = base.strip("/")
    if rel:
        link = root / rel
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(site.resolve(), target_is_directory=True)
    else:
        root.rmdir()
        root = site.resolve()
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", "--bind", "127.0.0.1", str(port)],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    origin = f"http://127.0.0.1:{port}"
    try:
        wait_http(origin + base)
        yield origin
    finally:
        stop(proc)
        if rel:
            shutil.rmtree(root, ignore_errors=True)


@contextlib.contextmanager
def chrome(binary: str = CHROME):
    port = free_port()
    profile = tempfile.mkdtemp(prefix="render-pass-chrome-")
    proc = subprocess.Popen(
        [
            binary,
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-component-update",
            "--hide-scrollbars",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    devtools = f"http://127.0.0.1:{port}"
    try:
        wait_http(devtools + "/json/version", 30)
        yield devtools
    finally:
        stop(proc)
        shutil.rmtree(profile, ignore_errors=True)


def find_chrome(path: str) -> str | None:
    found = shutil.which(path)
    return found if found and os.access(found, os.X_OK) else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", type=Path, required=True, help="exported static edition")
    ap.add_argument("--base", default="/velometer/", help="base path the site was exported for")
    ap.add_argument("--out", type=Path, required=True, help="results.json and shots/ go here")
    ap.add_argument("--themes", default="light,dark")
    ap.add_argument("--widths", default="1280,390,320")
    ap.add_argument(
        "--pages", default="all", help="all, types, or comma-separated URLs (base included)"
    )
    ap.add_argument("--flip", action="store_true", help="light, then dark mid-page (own mode)")
    ap.add_argument(
        "--interact",
        action="store_true",
        help="also open a city panel on <base>compare per theme and width, audit, Escape",
    )
    ap.add_argument(
        "--keyboard",
        action="store_true",
        help="also run the scripted keyboard pass per theme (real key events)",
    )
    ap.add_argument(
        "--chrome",
        default=os.environ.get("VELOMETER_CHROME") or CHROME,
        help=f"Chrome binary (default: $VELOMETER_CHROME, else {CHROME})",
    )
    a = ap.parse_args(argv)

    base = _norm_base(a.base)
    site = a.site.resolve()
    if not (site / "index.html").is_file():
        ap.error(f"{site} has no index.html; export the static edition first")
    themes = [x for x in a.themes.split(",") if x]
    if bad := [x for x in themes if x not in ("light", "dark")]:
        ap.error(f"unknown theme(s): {bad}")
    widths = [int(x) for x in a.widths.split(",") if x]
    if a.pages == "all":
        urls = page_urls(site, base)
    elif a.pages == "types":
        urls = type_urls(page_urls(site, base), base)
    else:
        urls = [u for u in a.pages.split(",") if u]
    page_themes = ["light->dark"] if a.flip else themes
    plan = [("page", u, th, w) for u in urls for th in page_themes for w in widths]
    if a.interact:
        plan += [("interact", base + "compare", th, w) for th in themes for w in widths]
    if a.keyboard:
        plan += [("keyboard", base, th, 1280) for th in themes]

    out = a.out
    shots = out / "shots"
    if shots.exists():
        shutil.rmtree(shots)
    out.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    def save() -> None:
        (out / "results.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")

    if not plan:
        save()
        print("no visits: nothing was checked (check --pages, --themes and --widths)")
        return 1
    binary = find_chrome(a.chrome)
    if binary is None:
        ap.error(
            f"Chrome not found or not executable: {a.chrome} (set --chrome or $VELOMETER_CHROME)"
        )

    try:
        with serve(site, base) as origin, chrome(binary) as devtools:
            for kind, url, theme, width in plan:
                if kind == "interact":
                    r = interact(devtools, origin, base, theme, width, shots)
                elif kind == "keyboard":
                    r = keyboard(devtools, origin, base, theme)
                    print("\n".join(f"    [{theme}] {x}" for x in r["steps"]), flush=True)
                else:
                    r = visit(devtools, origin, url, theme, width, shots, base, flip=a.flip)
                results.append(r)
                save()
                bad = failures(r)
                print(f"[{len(results)}/{len(plan)}] {r['url']} {r['theme']} {width}: "
                      f"{'; '.join(bad) or 'ok'}", flush=True)  # fmt: skip
    finally:
        save()

    failed = [r for r in results if failures(r)]
    rules = Counter(v["id"] for r in results for v in r["axe"])
    print(f"\n{len(results)} visits, {len(failed)} with findings; results in {out}/results.json")
    for rule, n in rules.most_common():
        print(f"  axe {rule}: {n} visits")
    for r in results:
        for e in r["errors"]:
            print(f"  error {r['url']} {r['theme']} {r['width']}: {e}")
    return 1 if failed or len(results) < len(plan) else 0


if __name__ == "__main__":
    sys.exit(main())
