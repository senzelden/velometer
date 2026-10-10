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
        [--pages all|types|<url>,...] [--flip] [--interact] [--chrome PATH]

`--flip` is a mode of its own: each page loads in light, the emulated scheme switches to dark
mid-page, and after 500 ms the page is audited and shot as `<slug>-flipped-<width>.png`.
`--interact` adds, per theme and width, a visit to `<base>compare` that opens a city panel with a
mouse click (table view, first city link), audits the page with the panel open, presses Escape and
checks focus returned to the link. Chrome is `--chrome`, else `$VELOMETER_CHROME`, else
`/usr/bin/google-chrome`.
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
