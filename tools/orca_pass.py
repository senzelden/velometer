"""Orca pass: a real Orca screen reader over the exported static edition, isolated from the desktop.

M13 Task 11. Everything runs inside `dbus-run-session`, so Orca, Chrome and the AT-SPI bus they
share are private to this run; nothing touches the session's own bus, display or speakers:

- no display: DISPLAY is unset and WAYLAND_DISPLAY names a socket that does not exist (libatspi
  then picks its legacy key device instead of the X11 one, which needs a display);
- Chrome is headless (`--ozone-platform=headless --headless=new`, `--app=URL`: no toolbar to
  Tab into) with `--force-renderer-accessibility`; it still registers with the private AT-SPI
  bus. Each page loads in a fresh Chrome: navigating one tab left Orca's caret context on the
  previous page's objects, so H and Tab after a load spoke nothing;
- no audio: Orca's `speechd` import is blocked by a stub, and the speech server Orca gets is a
  stub that only writes what it is given into Orca's debug log (`SPEECH OUTPUT: '<text>' <voice>`,
  the voice carrying the language Orca switched to); PULSE_SERVER and PIPEWIRE_REMOTE point at
  nothing and XDG_RUNTIME_DIR is a private directory;
- Orca runs from `/usr/bin/orca` through a shim that tolerates the missing display (no keymap,
  no clipboard); HOME, XDG_* and GSETTINGS_BACKEND=memory keep its settings out of the user's.

Keys go to the page as real key events through CDP `Input.dispatchKeyEvent` (Tab, Shift+Tab,
Enter, Escape, arrows, typed letters); Orca hears the focus and caret changes they cause. Orca's
own browse-mode keys (H for the next heading, table navigation, say all) cannot reach it without
a display, so they are sent as the same commands over Orca's D-Bus remote control
(`org.gnome.Orca.Service`, e.g. `StructuralNavigator.NextHeading`). Since Orca never sees the
CDP keys, its "last input event" would stay the last D-Bus command and it would ignore the focus
changes the keys cause; the shim lets a key the pass marks (`ORCA_PASS_KEYMARK`) supersede it.
After each action the pass waits until Orca's debug log stops growing and keeps what Orca said in
that slice.

    uv run --group dev python tools/orca_pass.py --site DIR --base /velometer/ --out DIR \
        [--editions en,de] [--steps name,...] [--chrome PATH] [--locale de_DE.UTF-8 --locpath DIR]

`--locale` gives the whole private session (Orca, Chrome, the AT-SPI clients) that process locale:
`LANG` and `LC_ALL` are set to it, `LOCPATH` to `--locpath` (a directory made without root by
`localedef -i de_DE -f UTF-8 DIR/de_DE.UTF-8`), and Chrome gets `--lang=<language part>`. Without
it the run inherits the caller's locale (M13: `en_US.UTF-8`). Every other isolation property
stays as above.

`--out` gets `transcript.md` (per step: the keys, what Orca said and in which language) and
`steps.json`, plus Orca's raw `orca-debug.log`. Every process the pass starts (server, Orca,
Chrome) is stopped by its own handle; the private bus ends with `dbus-run-session`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import render_pass as rp  # noqa: E402

ORCA = "/usr/bin/orca"

# blocks speech-dispatcher, so Orca can never reach an audio device
SPEECHD_STUB = """raise ImportError("speechd is blocked in the isolated Orca pass (no audio)")
"""

# a speech server that speaks nothing: speech.py already logs each utterance with its voice
LOG_SERVER = '''"""Orca speech server stub for the isolated pass: it writes, it never sounds."""
from orca import debug, speechserver


class SpeechServer(speechserver.SpeechServer):
    _active = None

    @staticmethod
    def get_factory_name():
        return "log only"

    @staticmethod
    def get_speech_servers():
        return [SpeechServer.get_speech_server()]

    @staticmethod
    def get_speech_server(_info=None):
        if SpeechServer._active is None:
            SpeechServer._active = SpeechServer()
        return SpeechServer._active

    def get_info(self):
        return ["log only", "log"]

    def speak(self, text=None, acss=None):
        pass

    def speak_character(self, character, acss=None, cap_style=None):
        pass

    def speak_key_event(self, event, acss=None):
        pass

    def say_all(self, utterance_iterator, progress_callback):
        last = None
        for context, acss in utterance_iterator:
            debug.print_message(
                debug.LEVEL_INFO, f"SPEECH OUTPUT: '{context.utterance}' {acss} [say all]", True
            )
            progress_callback(context, speechserver.SayAllContext.PROGRESS)
            last = context
        if last is not None:
            progress_callback(last, speechserver.SayAllContext.COMPLETED)
'''

# runs /usr/bin/orca without a display: Gdk has no keymap and there is no clipboard
SHIM = """import runpy, sys
from orca import clipboard, debug, keybindings, speech_manager

Gdk = keybindings.Gdk
_keycodes = keybindings.get_keycodes


def get_keycodes(keysym):
    if Gdk.Keymap.get_default() is None:
        return (Gdk.keyval_from_name(keysym), 0) if keysym else (0, 0)
    return _keycodes(keysym)


keybindings.get_keycodes = get_keycodes
_cls = type(clipboard.get_presenter())
_activate = _cls.activate


def activate(self, *a, **k):
    try:
        return _activate(self, *a, **k)
    except AttributeError:  # no display, no clipboard
        return None


_cls.activate = activate
# Orca opens its debug file block-buffered; flush each line so the pass can follow it live
_print_text = debug._print_text


def print_text(*a, **k):
    _print_text(*a, **k)
    if debug.debugFile:
        debug.debugFile.flush()


debug._print_text = print_text
speech_manager.SPEECH_FACTORY_MODULES[:] = ["orca_log_speech"]

# Keys reach the page, not Orca, so Orca's "last input event" stays the last D-Bus command and
# it ignores every later focus change as caused by that command. The pass touches KEYMARK on
# each real key; a navigation command older than that key is no longer the last input event.
import os
from orca import caret_navigator, structural_navigator, table_navigator

KEYMARK = os.environ["ORCA_PASS_KEYMARK"]


def _newer_key(orig):
    def last_input_event_was_navigation_command(self):
        ev = self._last_input_event
        if ev is not None and os.path.exists(KEYMARK) and os.path.getmtime(KEYMARK) > ev.time:
            return False
        return orig(self)
    return last_input_event_was_navigation_command


for _m, _get in ((structural_navigator, "get_navigator"), (table_navigator, "get_navigator"),
                 (caret_navigator, "get_navigator")):
    _c = type(getattr(_m, _get)())
    _c.last_input_event_was_navigation_command = _newer_key(
        _c.last_input_event_was_navigation_command)
sys.argv[0] = "/usr/bin/orca"
runpy.run_path("/usr/bin/orca", run_name="__main__")
"""

SPEECH_RE = re.compile(
    r"^\d\d:\d\d:\d\d\.\d+ - SPEECH OUTPUT: '(.*)'(?: (\{.*\}))?( \[say all\])?$"
)
LANG_RE = re.compile(r"'lang': '([A-Za-z-]*)'")
LOCUS_RE = re.compile(r"FOCUS MANAGER: Locus of focus is \[(.*?)\] ")


# --- outer: the isolated environment -------------------------------------------------------


def isolated_env(
    scratch: Path, locale: str | None = None, locpath: Path | None = None
) -> dict[str, str]:
    """The environment for the private session: own dirs, no display, no audio server.

    `locale` (e.g. de_DE.UTF-8) becomes LANG and LC_ALL and `locpath` LOCPATH."""
    dirs = {k: scratch / k for k in ("home", "config", "data", "cache", "run", "tmp", "stub")}
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    dirs["run"].chmod(0o700)
    (dirs["stub"] / "speechd").mkdir(exist_ok=True)
    (dirs["stub"] / "speechd" / "__init__.py").write_text(SPEECHD_STUB)
    (dirs["stub"] / "orca_log_speech.py").write_text(LOG_SERVER)
    (dirs["stub"] / "orca_shim.py").write_text(SHIM)
    env = {k: v for k, v in os.environ.items() if k not in DROP}
    env |= {
        "HOME": str(dirs["home"]),
        "XDG_CONFIG_HOME": str(dirs["config"]),
        "XDG_DATA_HOME": str(dirs["data"]),
        "XDG_CACHE_HOME": str(dirs["cache"]),
        "XDG_RUNTIME_DIR": str(dirs["run"]),
        "TMPDIR": str(dirs["tmp"]),
        "WAYLAND_DISPLAY": str(dirs["run"] / "no-such-wayland-socket"),
        "XDG_SESSION_TYPE": "wayland",
        "GSETTINGS_BACKEND": "memory",
        "PULSE_SERVER": "unix:/nonexistent",
        "PIPEWIRE_REMOTE": "/nonexistent",
        "ORCA_PASS_STUB": str(dirs["stub"]),
        "ORCA_PASS_KEYMARK": str(dirs["run"] / "last-key"),
    }
    if locale:
        env |= {"LANG": locale, "LC_ALL": locale}
        env.pop("LANGUAGE", None)  # would override LANG for message catalogues
        if locpath:
            env["LOCPATH"] = str(locpath.resolve())
    return env


DROP = {
    "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "AT_SPI_BUS_ADDRESS",
    "SPEECHD_ADDRESS", "PULSE_SERVER", "PIPEWIRE_REMOTE", "SSH_AUTH_SOCK", "GPG_AGENT_INFO",
    "GTK_MODULES",
}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", type=Path, required=True)
    ap.add_argument("--base", default="/velometer/")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--editions", default="en,de")
    ap.add_argument("--steps", default="all")
    ap.add_argument("--chrome", default=os.environ.get("VELOMETER_CHROME", rp.CHROME))
    ap.add_argument("--locale", help="process locale for the session, e.g. de_DE.UTF-8")
    ap.add_argument("--locpath", type=Path, help="LOCPATH: where a locale made by localedef lives")
    ap.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.inner:
        return inner(a)
    for tool in ("dbus-run-session", ORCA):
        if not shutil.which(tool):
            print(f"orca pass: {tool} is not installed", file=sys.stderr)
            return 2
    a.out.mkdir(parents=True, exist_ok=True)
    env = isolated_env(a.out / "env", a.locale, a.locpath)
    cmd = ["dbus-run-session", "--", sys.executable, str(Path(__file__).resolve()), "--inner"]
    cmd += ["--site", str(a.site.resolve()), "--base", a.base, "--out", str(a.out.resolve())]
    cmd += ["--editions", a.editions, "--steps", a.steps, "--chrome", a.chrome]
    if a.locale:
        cmd += ["--locale", a.locale]
    with open(a.out / "bus.log", "w") as bus_log:
        return subprocess.call(cmd, env=env, stderr=bus_log)


# --- inner: inside the private session bus ---------------------------------------------------


def gdbus(module: str, method: str, *args: str, timeout: float = 20) -> str:
    path = "/org/gnome/Orca/Service" + (f"/{module}" if module else "")
    iface = "org.gnome.Orca.Module" if module else "org.gnome.Orca.Service"
    out = subprocess.run(
        ["gdbus", "call", "--session", "--dest", "org.gnome.Orca.Service",
         "--object-path", path, "--timeout", str(int(timeout)), "--method", f"{iface}.{method}",
         *args],
        capture_output=True, text=True, timeout=timeout,
    )  # fmt: skip
    if out.returncode:
        raise RuntimeError(f"gdbus {module}.{method}: {out.stderr.strip()}")
    return out.stdout.strip()


class Orca:
    """The Orca process and its debug log."""

    def __init__(self, out: Path):
        self.log = out / "orca-debug.log"
        self.log.write_text("")
        stub = os.environ["ORCA_PASS_STUB"]
        env = os.environ | {"PYTHONPATH": stub}
        with open(out / "orca.out", "w") as console:
            self.proc = subprocess.Popen(
                ["/usr/bin/python3", f"{stub}/orca_shim.py", f"--debug-file={self.log}"],
                env=env, stdout=console, stderr=subprocess.STDOUT,
            )  # fmt: skip
        end = time.time() + 30
        while True:
            try:
                gdbus("", "ListModules")
                break
            except RuntimeError:
                if time.time() > end or self.proc.poll() is not None:
                    raise RuntimeError("Orca did not start its D-Bus service") from None
                time.sleep(0.5)
        # a page load speaks its first line instead of reading the whole page
        gdbus("DocumentPresenter", "ExecuteRuntimeSetter", "SayAllOnLoad", "<false>")

    def offset(self) -> int:
        return self.log.stat().st_size

    def settle(self, quiet: float = 0.6, cap: float = 10.0) -> None:
        """Wait until the debug log has not grown for `quiet` seconds (at most `cap`)."""
        end, last, since = time.time() + cap, self.offset(), time.time()
        while time.time() < end:
            time.sleep(0.1)
            now = self.offset()
            if now != last:
                last, since = now, time.time()
            elif time.time() - since >= quiet:
                return

    def _since(self, start: int) -> str:
        with open(self.log, "rb") as f:
            f.seek(start)
            return f.read().decode("utf-8", "replace")

    def locus(self, start: int) -> str:
        """Orca's own locus of focus (role: 'name') at the end of the slice since `start`."""
        found = LOCUS_RE.findall(self._since(start))
        return found[-1] if found else ""

    def said(self, start: int) -> list[dict]:
        """What Orca spoke since byte `start`: text, the voice's language, say all or not."""
        text = self._since(start)
        out = []
        for line in text.splitlines():
            m = SPEECH_RE.match(line)
            if m:
                lang = LANG_RE.search(m[2] or "")
                out.append({"text": m[1], "lang": lang[1] if lang else "", "sayall": bool(m[3])})
        return out

    def stop(self) -> None:
        rp.stop(self.proc)


def start_chrome(
    binary: str, out: Path, url: str = "about:blank", locale: str | None = None
) -> tuple[subprocess.Popen, str]:
    lang = [f"--lang={re.split(r'[_.@-]', locale)[0]}"] if locale else []
    port = rp.free_port()
    profile = out / "chrome-profile"
    (profile / "Default").mkdir(parents=True, exist_ok=True)
    # no "Translate this page?" bubble on the German pages: Tab would land in it
    prefs = profile / "Default" / "Preferences"
    if not prefs.exists():
        prefs.write_text(json.dumps({"translate": {"enabled": False}}))
    proc = subprocess.Popen(
        [binary, "--ozone-platform=headless", "--headless=new", "--force-renderer-accessibility",
         f"--remote-debugging-port={port}", f"--user-data-dir={profile}", "--window-size=1280,900",
         "--no-first-run", "--no-default-browser-check", "--disable-extensions",
         "--disable-background-networking", "--disable-sync", "--disable-component-update",
         "--password-store=basic", "--mute-audio", "--disable-features=Translate,TranslateUI",
         *lang, f"--app={url}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    devtools = f"http://127.0.0.1:{port}"
    rp.wait_http(devtools + "/json/version", 30)
    return proc, devtools


def page_tab(devtools: str) -> rp.Tab:
    """The window's page target."""
    with urllib.request.urlopen(devtools + "/json/list") as r:
        info = next(i for i in json.load(r) if i["type"] == "page")
    t = rp.Tab(devtools, info["webSocketDebuggerUrl"], info["id"])
    for domain in ("Page", "Network", "Runtime"):
        t.call(f"{domain}.enable")
    return t


# where the focus is and the language a sighted reader's text is in there
DOM_JS = r"""(() => {
  const e = document.activeElement;
  const live = document.getElementById('live');
  const name = (x) => (x.getAttribute('aria-label') || x.textContent || x.value || '')
    .replace(/\s+/g, ' ').trim().slice(0, 80);
  return {url: location.pathname + location.search + location.hash,
          focus: e && e !== document.body ? e.localName + ' "' + name(e) + '"' : 'body',
          lang: e ? (e.closest('[lang]') || document.documentElement).getAttribute('lang') : '',
          live: live ? live.textContent : null};
})()"""


class Driver:
    def __init__(
        self, chrome: str, out: Path, orca: Orca, origin: str, base: str, locale: str | None = None
    ):
        self.locale = locale
        self.chrome, self.out, self.orca, self.origin, self.base = chrome, out, orca, origin, base
        self.proc: subprocess.Popen | None = None
        self.t: rp.Tab | None = None
        self.steps: list[dict] = []
        self.step: dict | None = None

    def close(self) -> None:
        if self.t:
            self.t.ws.close()
            self.t = None
        if self.proc:
            rp.stop(self.proc)
            self.proc = None

    def begin(self, name: str, edition: str) -> None:
        self.step = {"name": name, "edition": edition, "actions": []}
        self.steps.append(self.step)

    def _act(self, label: str, do) -> dict:
        start = self.orca.offset()
        err = None
        try:
            do()
        except Exception as e:  # noqa: BLE001 - recorded, the pass goes on
            err = f"{type(e).__name__}: {e}"
        self.orca.settle()
        rec = {"keys": label, "said": self.orca.said(start), "locus": self.orca.locus(start),
               "dom": self.t.js(DOM_JS)}  # fmt: skip
        if err:
            rec["error"] = err
        self.step["actions"].append(rec)
        return rec

    def load(self, path: str) -> dict:
        """Open `path` in a freshly started Chrome. Navigating one tab leaves Orca's caret
        context on the previous page's objects (Chrome keeps the document accessible across a
        same-site navigation) and a second tab leaves its locus on the closed one, so H and
        Tab after a load spoke nothing; a new browser is a new application to Orca, which then
        picks up the page as a reader opening it would."""

        def do():
            self.close()
            url = self.origin + self.base + path
            self.proc, devtools = start_chrome(self.chrome, self.out, url, self.locale)
            self.t = page_tab(devtools)
            if not self.t.wait_js("document.readyState === 'complete'", rp.LOAD_TIMEOUT):
                raise RuntimeError(f"{url} did not finish loading")
            nav = "performance.getEntriesByType('navigation')[0]?.responseStatus"
            self.t.wait_js(f"({nav}) > 0", 5)
            status = self.t.js(nav)
            if status not in rp.OK_STATUS:
                raise RuntimeError(f"document HTTP {status}: {url}")

        rec = self._act(f"load {self.base}{path}", do)
        # Orca sometimes settles a fresh page in focus mode, where H and T do nothing; a reader
        # who hears "Focus mode" presses Orca+A, and so does the pass
        if "true" in gdbus("DocumentPresenter", "ExecuteRuntimeGetter", "InFocusMode"):
            self.orca_cmd("DocumentPresenter", "TogglePresentationMode", "Orca+A")
        return rec

    @staticmethod
    def mark_key() -> None:
        """Tell the Orca shim a real key was pressed (see SHIM)."""
        Path(os.environ["ORCA_PASS_KEYMARK"]).touch()

    def key(self, name: str, shift: bool = False, times: int = 1) -> None:
        def do():
            self.mark_key()
            rp.press(self.t, name, shift=shift, wait=0.05)

        for _ in range(times):
            self._act(("Shift+" if shift else "") + ("Space" if name == " " else name), do)

    def type(self, text: str) -> None:
        def do():
            self.mark_key()
            for ch in text:
                for kind in ("keyDown", "keyUp"):
                    p = {"type": kind, "key": ch, "code": f"Key{ch.upper()}",
                         "windowsVirtualKeyCode": ord(ch.upper())}  # fmt: skip
                    if kind == "keyDown":
                        p["text"] = ch
                    self.t.call("Input.dispatchKeyEvent", **p)
                self.t.pump(0.15)

        self._act(f"type '{text}'", do)

    def orca_cmd(self, module: str, command: str, label: str, times: int = 1) -> None:
        for _ in range(times):
            self._act(
                f"{label} (Orca {module}.{command})",
                lambda: gdbus(module, "ExecuteCommand", command, "true", timeout=300),
            )

    def tab_to(self, selector: str, cap: int = 200) -> None:
        """Tab until `selector` has focus; one record for the run, with Orca's last words."""
        test = f"!!document.activeElement && document.activeElement.matches({json.dumps(selector)})"

        def do():
            for _ in range(cap):
                if self.t.js(test):
                    return
                self.mark_key()
                rp.press(self.t, "Tab", wait=0.03)
            raise RuntimeError(f"Tab did not reach {selector}")

        rec = self._act(f"Tab until {selector}", do)
        rec["said"] = rec["said"][-6:]

    def wait_js(self, expr: str, cap: float = 8) -> None:
        self.t.wait_js(expr, cap)


def steps_for(d: Driver, pre: str, edition: str, only: set[str]) -> None:
    """The sample, in one edition (`pre` is "" or "de/")."""

    def want(name: str) -> bool:
        if "all" in only or name in only:
            d.begin(name, edition)
            return True
        return False

    H = ("StructuralNavigator", "NextHeading", "H")
    T = ("StructuralNavigator", "NextTable", "T")
    if want("home"):
        d.load(pre)
        d.key("Tab", times=3)
        d.key("Tab", shift=True)
        d.orca_cmd(*H, times=4)
    if want("compare-table"):
        d.load(pre + "compare")
        d.orca_cmd(*H, times=2)
        d.tab_to(".view-tabs a[data-view=table]")
        d.key("Enter")
        d.wait_js("!!document.querySelector('table.compare-table')")
        d.orca_cmd(*T)
        d.orca_cmd("TableNavigator", "MoveDown", "Alt+Shift+Down")
        d.orca_cmd("TableNavigator", "MoveRight", "Alt+Shift+Right", times=2)
        d.orca_cmd("TableNavigator", "MoveDown", "Alt+Shift+Down")
        d.tab_to("th:not(:first-child) > button.sort")
        d.key("Enter")
        d.key("Enter")
    if want("compare-panel"):
        d.load(pre + "compare?view=table")
        d.wait_js("!!document.querySelector('table.compare-table')")
        d.tab_to("table a[data-city]")
        d.key("Enter")
        d.wait_js(rp.PANEL_OPEN_JS)
        d.key("Tab", times=2)
        d.key("Escape")
    if want("compare-chart"):
        d.load(pre + "compare")
        d.tab_to(".view-tabs a[data-view=lines]")
        d.key("Enter")
        d.key("Tab", times=3)
        d.orca_cmd(*H, times=2)
    if want("city-tabs"):
        d.load(pre + "city/berlin")
        d.tab_to("nav.tabs a")
        n = d.t.js("document.querySelectorAll('nav.tabs a').length") or 0
        d.key("Tab", times=max(n - 1, 0))
        for tab in ("", "/tiers", "/time", "/counts", "/bezirke", "/figures"):
            d.load(pre + "city/berlin" + tab)
            d.orca_cmd(*H, times=2)
    if want("figures"):
        d.load(pre + "city/copenhagen/figures")
        d.orca_cmd(*H, times=2)
        d.orca_cmd(*T)
        d.orca_cmd("TableNavigator", "MoveDown", "Alt+Shift+Down")
        d.orca_cmd("TableNavigator", "MoveRight", "Alt+Shift+Right")
        d.orca_cmd("SayAllPresenter", "SayAll", "KP_Add say all")
    if want("methodology"):
        d.load(pre + "methodology")
        d.orca_cmd(*H, times=4)
        d.orca_cmd(*T)
        d.orca_cmd("TableNavigator", "MoveDown", "Alt+Shift+Down")
    if want("sources"):
        d.load(pre + "sources")
        d.orca_cmd(*H, times=3)
        d.key("Tab", times=3)
        d.orca_cmd("SayAllPresenter", "SayAll", "KP_Add say all")
    if want("differences"):
        d.load(pre + "differences")
        d.orca_cmd("SayAllPresenter", "SayAll", "KP_Add say all")
    if want("organisations"):
        d.load(pre + "organisations")
        d.orca_cmd("SayAllPresenter", "SayAll", "KP_Add say all")
    if want("search"):
        d.load(pre)
        d.tab_to("#site-search")
        d.type("ber")
        d.key("ArrowDown")
        d.key("Enter")
        d.load(pre)
        d.tab_to("#site-search")
        d.type("zzz")
        d.key("Escape")
    if want("cite"):
        d.load(pre + rp.CITE_PAGE)
        d.tab_to("details.cite > summary")
        d.key("Enter")
        d.key("Tab", times=2)
        d.tab_to(".cite-copy")
        d.key("Enter")
        d.tab_to("details.cite > summary")
        d.key("Enter")
    if want("download"):
        d.load(pre + rp.DOWNLOAD_PAGE)
        d.tab_to("details.download > summary")
        d.key("Enter")
        d.key("Tab", times=3)
        d.key("Escape")
    if want("404") and not pre:
        d.load("404.html")
        d.orca_cmd(*H, times=2)
        d.orca_cmd("SayAllPresenter", "SayAll", "KP_Add say all")


def transcript(steps: list[dict]) -> str:
    lines = ["# Orca pass transcript", ""]
    for s in steps:
        lines += [f"## {s['edition']}: {s['name']}", ""]
        for a in s["actions"]:
            dom = a["dom"] or {}
            focus = f"DOM focus {dom.get('focus')} (lang {dom.get('lang')})"
            lines.append(f"- **{a['keys']}** -> {focus}; Orca locus [{a.get('locus', '')}]")
            if dom.get("live"):
                lines.append(f"  - #live: {dom['live']!r}")
            if a.get("error"):
                lines.append(f"  - ERROR {a['error']}")
            for u in a["said"]:
                lang = f" [{u['lang']}]" if u["lang"] else ""
                lines.append(f'  - {"(say all) " if u["sayall"] else ""}"{u["text"]}"{lang}')
        lines.append("")
    return "\n".join(lines)


def inner(a) -> int:
    out: Path = a.out
    only = set(a.steps.split(","))
    orca = d = None
    with rp.serve(a.site, a.base) as origin:
        try:
            orca = Orca(out)
            d = Driver(a.chrome, out, orca, origin, a.base, a.locale)
            for ed in a.editions.split(","):
                steps_for(d, "de/" if ed == "de" else "", ed, only)
                (out / "steps.json").write_text(json.dumps(d.steps, indent=1, ensure_ascii=False))
            (out / "transcript.md").write_text(transcript(d.steps))
        finally:
            if d:
                d.close()
            if orca:
                orca.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
