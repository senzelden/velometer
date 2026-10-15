// Download this chart (M11): after each chart that has a data table, a disclosure with SVG, PNG and
// CSV buttons. The file is built from the chart on the page at the moment of the click, in the
// light theme whatever the page shows. The cities-page sparklines have no table and get none.
import { base } from "./base.js";
import { fileName, glyphOf, lightOf, pngBlob, PLAIN_PROPS, selfContained, sizeOf, tableCsv } from "./download.js";
import { locale } from "./fmt.js";
import { announce } from "./live.js";
import { t } from "./strings.js";

export const SELECTOR = [
  "[data-chart]:not([data-chart=sparkline])",
  "[data-compare-chart]",
  "[data-story-plot]",
  ".plan-chart[data-plan-item]",
].join(",");
const STYLE_PROPS = ["fill", "stroke", "color", "display", "visibility", ...PLAIN_PROPS];

const tokens = () => {
  try {
    return JSON.parse(document.getElementById("theme-tokens")?.textContent ?? "{}");
  } catch {
    return {};
  }
};
const isDark = () => globalThis.matchMedia?.("(prefers-color-scheme: dark)")?.matches === true;
const commit = () => document.querySelector('meta[name="velometer-commit"]')?.content || "unknown";

/** Computed style of a page element as one object keyed by property; synthetic nodes carry theirs. */
function styleOf(el) {
  if (el.style_) return el.style_;
  const cs = getComputedStyle(el);
  return Object.fromEntries(STYLE_PROPS.map((p) => [p, cs.getPropertyValue(p)]));
}

const SVG_NS = "http://www.w3.org/2000/svg";

/** A text's width in px as the downloaded image sets it (system-ui, at `size` and `weight`: 11px
 * for a key label and the meta lines, 15px 600 for the title), measured by the browser
 * (getComputedTextLength) in a hidden SVG; null where that is not available, and the image then
 * estimates it. */
export function labelWidth(text, doc = document, size = "11px", weight = "400") {
  try {
    const svg = doc.createElementNS(SVG_NS, "svg");
    svg.setAttribute("aria-hidden", "true");
    Object.assign(svg.style, { position: "absolute", visibility: "hidden", width: "0", height: "0" });
    const el = doc.createElementNS(SVG_NS, "text");
    el.setAttribute("font-size", size);
    el.setAttribute("font-weight", weight);
    el.setAttribute("font-family", "system-ui, sans-serif");
    el.textContent = text;
    svg.append(el);
    doc.body.append(svg);
    try {
      const w = typeof el.getComputedTextLength === "function" ? el.getComputedTextLength() : NaN;
      return Number.isFinite(w) && w > 0 ? w : null;
    } finally {
      svg.remove();
    }
  } catch {
    return null;
  }
}

/** The key chips of a chart whose key is HTML: colour (computed), text and the text's measured
 * width. Two forms are read. A `.legend` inside the container with a `.chip` per entry, its
 * colour on the chip's `<i>` (chart.js renderTiers draws it). And a list beside the chart that the
 * container names by id in `data-download-key` (the plan page's key, a Counts tab's key): an `li`
 * per entry, its mark the `.key` in it, whose computed style gives the glyph (glyphOf). */
export function keyOf(container, doc = document) {
  const tiers = [...container.querySelectorAll(".legend .chip")].map((chip) => {
    const sw = chip.querySelector("i");
    const text = chip.textContent.trim();
    return { colour: sw ? getComputedStyle(sw).backgroundColor : "", text, width: labelWidth(text, doc) };
  });
  const id = container.getAttribute?.("data-download-key");
  const list = id ? doc.getElementById?.(id) : null;
  const beside = [...(list?.querySelectorAll("li") ?? [])].map((li) => {
    const mark = li.querySelector(".key");
    const text = li.textContent.replace(/\s+/g, " ").trim();
    return { ...(mark ? glyphOf(getComputedStyle(mark)) : { shape: "swatch", colour: "" }), text, width: labelWidth(text, doc) };
  });
  return [...tiers, ...beside];
}

/** The `.cite-data` of the chart's own Cite: the first that follows the chart's data table (the
 * element its description names, which for a story plot is the current step's), else the chart,
 * in document order, without leaving the section it is in. A tier page's FUA chart thus cites the
 * FUA run, not the LAU chart's Cite above it. */
export function citeOf(container, doc = document) {
  const id = tableId(container);
  const start = (id && doc.getElementById(id)) || container;
  for (let n = start; n && n !== doc.body; n = n.parentElement) {
    for (let s = n.nextElementSibling; s; s = s.nextElementSibling) {
      if (s.matches?.(".cite-data")) return s;
      const blob = s.querySelector?.(".cite-data");
      if (blob) return blob;
    }
    if (n.parentElement?.matches?.("section")) break; // the chart's section ends the search
  }
  return null;
}

function citeFields(container) {
  const blob = citeOf(container);
  if (!blob) return null;
  try {
    return JSON.parse(blob.textContent);
  } catch {
    return null;
  }
}

// containers whose own label is generic ("Chart of the selected cities"): what they show is named
// by their Cite (metric, boundary, cities) and by the drawn SVG
const GENERIC = "[data-compare-chart],[data-story-plot]";

/** The title a downloaded image carries: a chart's own specific label; for a generic container,
 * its Cite's title, else the drawn SVG's label, else the container's. */
export function titleOf(container, f) {
  const own = container.getAttribute("aria-label");
  if (!container.matches?.(GENERIC)) return own || f?.title || document.title;
  const svgs = [...container.querySelectorAll("svg")];
  const drawn = svgs.length === 1 ? svgs[0].getAttribute("aria-label") : null;
  return f?.title || drawn || own || document.title;
}

/** The light-theme ground, ink and muted ink for the text the image adds. */
function light() {
  const tk = tokens();
  return { ground: tk["--surface"]?.[0], ink: tk["--ink"]?.[0], muted: tk["--ink-2"]?.[0] };
}

const day = (iso) => String(iso ?? "").slice(0, 10);

/** The title, source line and attribution the image carries, in the page's language. */
export function metaOf(container) {
  const f = citeFields(container);
  const snapshot = f?.snapshot_note ?? (f?.osm_timestamp ? t("js.download.snapshot", { day: day(f.osm_timestamp) }) : "");
  const source = [
    "velometer",
    snapshot,
    f?.classifier ? t("js.download.classifier", { version: f.classifier }) : "",
    f?.commit ?? commit(),
  ]
    .filter(Boolean)
    .join(" · ");
  return {
    title: titleOf(container, f),
    source,
    ...light(),
    key: keyOf(container),
    attribution: t("js.download.attribution"),
    measure: (text, size, weight) => labelWidth(text, document, size, weight),
  };
}

/** The chart drawn in the container: its one SVG, or the small-multiple cards stacked. */
function chartOf(container) {
  const svgs = [...container.querySelectorAll("svg")];
  if (svgs.length <= 1) return svgs[0] ?? null;
  const sizes = svgs.map(sizeOf);
  const w = Math.max(...sizes.map((s) => s.w));
  const GAP = 22;
  let y = 0;
  const children = svgs.map((s, i) => {
    const caption = s.closest(".sm-card")?.querySelector("figcaption")?.textContent?.trim();
    const at = y;
    y += sizes[i].h + GAP;
    const kids = [...s.children];
    if (caption)
      kids.unshift({
        tagName: "text", attributes: [{ name: "x", value: "4" }, { name: "y", value: "-6" }],
        children: [], textContent: caption,
        style_: { fill: light().ink ?? "black", "font-size": "12px", "font-weight": "600" },
      }); // fmt: skip
    return { tagName: "g", attributes: [{ name: "transform", value: `translate(0,${at + GAP - 4})` }], children: kids, style_: {} };
  });
  return {
    tagName: "svg",
    attributes: [{ name: "viewBox", value: `0 0 ${w} ${Math.max(y, 1)}` }],
    children,
  };
}

function svgFor(container) {
  const svg = chartOf(container);
  if (!svg) throw new Error(t("js.download.no_chart"));
  const out = selfContained(svg, styleOf, isDark() ? lightOf(tokens()) : null, metaOf(container));
  const vb = out.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  return { out, w: +vb[1], h: +vb[2] };
}

/** The table a description element belongs to: a <caption> is inside it, a <summary> is beside it
 * in the same <details>. */
export const tableFor = (el) => el?.closest("table") ?? el?.closest("details")?.querySelector("table") ?? null;

/** The data table a chart's description names: the id is the one the chart names now, else the one
 * seen at setup (a chart's `aria-describedby` can come and go; the table stays). */
const tableId = (container) => container.getAttribute("aria-describedby") || container.dataset.downloadTable;

function tableOf(container, doc = document) {
  const id = tableId(container);
  const table = id ? tableFor(doc.getElementById(id)) : null;
  if (!table) throw new Error(t("js.download.no_table"));
  return table;
}

/** The file name: the page's path (without the base and without a leading `de/`, so both
 * editions name a chart alike), the chart, its state. */
export function nameOf(container, ext, loc = globalThis.location, b = base()) {
  const path = loc.pathname.slice(b.length - 1).replace(/^\/de(?=\/|$)/, "");
  const chart = container.dataset.chart ?? (container.hasAttribute("data-compare-chart") ? "compare"
    : container.hasAttribute("data-story-plot") ? "story" : container.dataset.planItem) ?? "chart"; // fmt: skip
  const state = [container.dataset.kind, loc.search.replace(/^\?/, "")].filter(Boolean).join("-");
  return fileName(path, chart, state, ext);
}

function save(blob, name) {
  const a = document.createElement("a");
  const href = URL.createObjectURL(blob);
  a.href = href;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

const MAKE = {
  svg: async (c) => new Blob([svgFor(c).out], { type: "image/svg+xml" }),
  png: async (c) => {
    const { out, w, h } = svgFor(c);
    return pngBlob(out, w, h, 2);
  },
  csv: async (c) =>
    new Blob([tableCsv(tableOf(c), commit(), new Date().toISOString().replace(/\.\d+Z$/, "Z"), locale())], {
      type: "text/csv;charset=utf-8",
    }),
};

async function download(container, kind) {
  const name = nameOf(container, kind);
  try {
    save(await MAKE[kind](container), name);
    announce(t("js.download.done", { name }));
  } catch (e) {
    announce(t("js.download.failed", { kind: kind.toUpperCase(), reason: e.message }));
  }
}

const labelsSeen = new Map();

/** The chart's name for a screen reader, unique on the page ("... (2)" for a repeat). */
function chartName(container) {
  const base = container.getAttribute("aria-label") || container.dataset.chart || t("js.download.chart");
  const n = (labelsSeen.get(base) ?? 0) + 1;
  labelsSeen.set(base, n);
  return n === 1 ? base : `${base} (${n})`;
}

/** The Download disclosure: SVG, PNG and, when the chart has a data table, CSV. */
export function control(container, doc = document) {
  const name = chartName(container);
  const hasTable = Boolean(tableFor(doc.getElementById(tableId(container) ?? "")));
  if (hasTable) container.dataset.downloadTable = tableId(container);
  const d = doc.createElement("details");
  d.className = "download";
  const s = doc.createElement("summary");
  s.append(t("js.download.label"));
  const hidden = doc.createElement("span");
  hidden.className = "visually-hidden";
  hidden.textContent = ` ${name}`;
  s.append(hidden);
  const row = doc.createElement("div");
  row.className = "download-row";
  for (const kind of hasTable ? ["svg", "png", "csv"] : ["svg", "png"]) {
    const b = doc.createElement("button");
    b.type = "button";
    b.textContent = kind.toUpperCase();
    b.setAttribute("aria-label", t("js.download.button", { kind: kind.toUpperCase(), name }));
    b.addEventListener("click", () => download(container, kind));
    row.append(b);
  }
  d.append(s, row);
  return d;
}

/** Give a chart container its control (once). */
export function upgrade(container, doc = document) {
  if (container.dataset.downloadBound !== undefined) return;
  container.dataset.downloadBound = "";
  container.after(control(container, doc));
}

/** Upgrade every chart container in (or being) `root`. */
export function scan(root, doc = document) {
  if (root.matches?.(SELECTOR)) upgrade(root, doc);
  for (const c of root.querySelectorAll?.(SELECTOR) ?? []) upgrade(c, doc);
}

if (typeof document !== "undefined" && typeof MutationObserver !== "undefined") {
  scan(document);
  // the city panel is fetched after load
  new MutationObserver((records) => {
    for (const r of records) for (const n of r.addedNodes) if (n.nodeType === 1) scan(n);
  }).observe(document.body, { childList: true, subtree: true });
}
