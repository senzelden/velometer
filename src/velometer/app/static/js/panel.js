// The Compare slide-over: fetches /city/<id>/panel (a server-rendered, escaped fragment), shows it
// beside the chart and draws its tier chart. Escape and the close button close it; history
// decisions are the pure functions of compare-model.js, and compare.js owns `popstate`.
// On phones the panel covers the page: it is modal there (aria-modal, inert background, Tab
// stays inside); on wide screens it is a side panel and the page stays usable.
import { loadSeries, releaser } from "./data.js";
import { announce } from "./live.js";
import { url } from "./base.js";
import { closeAction, openAction, panelAnnouncement, panelUrl } from "./compare-model.js";
import { drawTiers } from "./tier-chart.js";

const FOCUSABLE = 'a[href], button:not([disabled]), summary, input, select, [tabindex]:not([tabindex="-1"])';

/**
 * @param {HTMLElement} root the <aside>, with a .slideover-close button and a .slideover-body
 * @param {{fallbackFocus?: (id: string) => HTMLElement | null}} [opts] where focus goes on close
 *   when the element that opened the panel is gone (the page was redrawn meanwhile)
 */
export function createPanel(root, opts = {}) {
  const body = root.querySelector(".slideover-body");
  const closeBtn = root.querySelector(".slideover-close");
  const phone = window.matchMedia("(max-width: 700px)");
  document.body.append(root); // a sibling of header, main and footer, so they can be made inert
  let current = null;
  let returnTo = null;
  let token = 0; // a slow answer must not replace a newer one
  const charts = releaser(); // the panel's charts listen for theme changes: let go when it is replaced
  const nameOf = (id) => opts.nameOf?.(id) ?? id;

  const background = () => [...document.body.children].filter((e) => e !== root && e.tagName !== "SCRIPT");
  const modal = () => !root.hidden && phone.matches;
  function applyModal() {
    const on = modal();
    root.setAttribute("aria-modal", String(on));
    for (const e of background()) e.inert = on;
  }
  phone.addEventListener("change", applyModal);

  /** Show the panel for a city without touching history (compare.js does that on popstate). */
  async function show(id) {
    const mine = ++token;
    if (root.hidden) returnTo = document.activeElement;
    current = id;
    root.hidden = false;
    document.body.classList.add("panel-open");
    applyModal();
    charts.run();
    body.replaceChildren(Object.assign(document.createElement("p"), { className: "empty", textContent: "Loading…" }));
    announce(panelAnnouncement("loading", nameOf(id)));
    closeBtn.focus();
    try {
      const r = await fetch(panelUrl(id), { headers: { Accept: "text/html" } });
      if (!r.ok) throw new Error(`panel: HTTP ${r.status}`);
      const doc = new DOMParser().parseFromString(await r.text(), "text/html");
      if (mine !== token) return;
      body.replaceChildren(...doc.body.childNodes);
      announce(panelAnnouncement("loaded", body.querySelector("h2")?.textContent || nameOf(id)));
      const D = await loadSeries();
      if (mine !== token) return;
      for (const el of body.querySelectorAll('[data-chart="city-tiers"]')) charts.add(drawTiers(el, D));
    } catch (err) {
      if (mine !== token) return;
      charts.run();
      announce(panelAnnouncement("failed", nameOf(id)));
      body.replaceChildren(Object.assign(document.createElement("p"), {
        className: "note", textContent: `The city panel could not be loaded. Its page is ${url(`/city/${id}`)}.`,
      }));
      console.warn(err);
    }
  }

  /** Hide it without touching history; focus goes back to the opener, or to its replacement. */
  function hide() {
    const id = current;
    token++;
    root.hidden = true;
    charts.run(); // the content stays in the hidden body until the next city, but nothing redraws it
    document.body.classList.remove("panel-open");
    current = null;
    applyModal();
    const target = returnTo?.offsetParent && returnTo !== document.body ? returnTo : opts.fallbackFocus?.(id);
    returnTo = null;
    target?.focus?.();
  }

  /** Open the panel for a city (a history entry the first time, replaced afterwards). */
  function open(id, opener) {
    if (id === current && !root.hidden) return;
    if (opener) returnTo = opener;
    const action = openAction(!root.hidden);
    const state = { ...history.state, panel: id };
    if (action === "push") history.pushState(state, "", location.href);
    else history.replaceState(state, "", location.href);
    const keep = returnTo;
    show(id);
    if (action === "push" && opener) returnTo = keep;
  }

  /** Close it, through history so Back and the close button agree. */
  function close() {
    if (root.hidden) return;
    if (closeAction(history.state) === "back") history.back();
    else hide();
  }

  // a reload can keep the state of an open panel that no longer is: never let Back leave the page
  if (history.state?.panel) history.replaceState(null, "", location.href);

  closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", (e) => {
    if (root.hidden) return;
    if (e.key === "Escape") return close();
    if (e.key === "Tab" && modal()) {
      const items = [...root.querySelectorAll(FOCUSABLE)].filter((x) => !x.closest("[hidden]"));
      if (!items.length) return;
      const first = items[0];
      const last = items.at(-1);
      if (!root.contains(document.activeElement)) {
        e.preventDefault();
        first.focus();
      } else if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });

  return {
    open, close, show, hide,
    get isOpen() { return !root.hidden; },
    get current() { return current; },
  };
}
