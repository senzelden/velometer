// The tier map's popup for one tiered side (map.js binds it to each line). OSM tag values are
// user data: the popup is built with textContent, never innerHTML.
import { number } from "./fmt.js";
import { t } from "./strings.js";

function el(tag, text, attrs) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  for (const [k, v] of Object.entries(attrs ?? {})) node.setAttribute(k, v);
  return node;
}

/** The popup of a side's GeoJSON properties `p`, with the map config's tier labels and links. */
export function tierPopup(p, cfg) {
  const box = el("div", null, { class: "tiermap-popup" });
  // the tier opens the popup, by name ("A separated track"): the line's colour is not the only
  // thing that says which tier a side is
  box.appendChild(el("p", cfg.labels[p.tier] || p.tier, { class: "tiermap-popup-tier" }));
  const dl = el("dl");
  const row = (label, value) => {
    dl.appendChild(el("dt", label));
    const dd = el("dd");
    if (value !== null && typeof value === "object") dd.appendChild(value); // a node
    else dd.textContent = value === null || value === undefined ? "–" : String(value);
    dl.appendChild(dd);
  };
  const link = el("a", t("js.map.way", { id: p.way_id }), {
    href: cfg.links.way + encodeURIComponent(p.way_id),
    target: "_blank",
    rel: "noopener noreferrer",
  });
  row("OSM", link);
  row(t("js.map.side"), p.side);
  row(t("js.map.tier"), cfg.labels[p.tier] || p.tier);
  row(t("js.map.subtype"), p.subtype);
  row(t("js.map.rule"), p.rule_id);
  row("km", typeof p.km === "number" ? number(p.km, 3) : p.km);
  box.appendChild(dl);
  const keys = Object.keys(p.tags || {}).sort();
  if (keys.length) {
    const table = el("table");
    for (const k of keys) {
      const tr = el("tr");
      tr.appendChild(el("td", k));
      tr.appendChild(el("td", p.tags[k]));
      table.appendChild(tr);
    }
    box.appendChild(table);
  }
  return box;
}
