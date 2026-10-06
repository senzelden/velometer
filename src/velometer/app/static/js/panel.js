// The Compare slide-over: fetches /city/<id>/panel (a server-rendered, escaped fragment), shows it
// beside the chart and draws its tier chart. Escape and the browser's Back close it; opening one
// adds a history entry, switching cities inside the panel replaces it.
import { loadSeries } from "./data.js";
import { drawTiers } from "./tier-chart.js";

/** @param {HTMLElement} root the <aside>, with a .slideover-close button and a .slideover-body */
export function createPanel(root) {
  const body = root.querySelector(".slideover-body");
  const closeBtn = root.querySelector(".slideover-close");
  let current = null;
  let returnTo = null;
  let token = 0; // a slow answer must not replace a newer one

  const hide = () => {
    token++;
    root.hidden = true;
    document.body.classList.remove("panel-open");
    current = null;
    returnTo?.focus?.();
    returnTo = null;
  };

  async function show(id) {
    const mine = ++token;
    const wasOpen = !root.hidden;
    if (!wasOpen) returnTo = document.activeElement;
    current = id;
    root.hidden = false;
    document.body.classList.add("panel-open");
    body.replaceChildren(Object.assign(document.createElement("p"), { className: "empty", textContent: "Loading…" }));
    closeBtn.focus();
    try {
      const r = await fetch(`/city/${encodeURIComponent(id)}/panel`, { headers: { Accept: "text/html" } });
      if (!r.ok) throw new Error(`panel: HTTP ${r.status}`);
      const doc = new DOMParser().parseFromString(await r.text(), "text/html");
      if (mine !== token) return;
      body.replaceChildren(...doc.body.childNodes);
      const D = await loadSeries();
      if (mine !== token) return;
      for (const el of body.querySelectorAll('[data-chart="city-tiers"]')) drawTiers(el, D);
    } catch (err) {
      if (mine !== token) return;
      body.replaceChildren(Object.assign(document.createElement("p"), {
        className: "note", textContent: "The city panel could not be loaded. Its page is /city/" + id + ".",
      }));
      console.warn(err);
    }
  }

  /** Open the panel for a city (a history entry the first time, replaced afterwards). */
  function open(id) {
    if (id === current && !root.hidden) return;
    if (root.hidden) history.pushState({ panel: id }, "", location.href);
    else history.replaceState({ ...history.state, panel: id }, "", location.href);
    show(id);
  }

  /** Close it, through history so Back and the close button agree. */
  function close() {
    if (root.hidden) return;
    if (history.state?.panel) history.back();
    else hide();
  }

  // a reload can keep the state of an open panel that no longer is: never let Back leave the page
  if (history.state?.panel) history.replaceState(null, "", location.href);

  closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !root.hidden) close();
  });
  window.addEventListener("popstate", (e) => {
    const id = e.state?.panel;
    if (id) show(id);
    else if (!root.hidden) hide();
  });

  return { open, close, get current() { return current; } };
}
