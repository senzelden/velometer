// Download this chart (M11): after each chart that has a data table, a disclosure with SVG, PNG and
// CSV buttons. The file is built from the chart on the page at the moment of the click, in the
// light theme whatever the page shows. The cities-page sparklines have no table and get none.
import { base } from "./base.js";
import { fileName, lightOf, pngBlob, PLAIN_PROPS, selfContained, sizeOf, tableCsv } from "./download.js";
import { announce } from "./live.js";

const SELECTOR = [
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

/** The citation fields next to the chart (its section's `.cite-data`), else the page's first. */
function citeFields(container) {
  for (let n = container; n && n !== document.body; n = n.parentElement) {
    const blob = n.querySelector(".cite-data");
    if (blob) {
      try {
        return JSON.parse(blob.textContent);
      } catch {
        return null;
      }
    }
  }
  return null;
}

/** The light-theme ground, ink and muted ink for the text the image adds. */
function light() {
  const t = tokens();
  return { ground: t["--surface"]?.[0], ink: t["--ink"]?.[0], muted: t["--ink-2"]?.[0] };
}

const day = (iso) => String(iso ?? "").slice(0, 10);

/** The title, source line and attribution the image carries. */
export function metaOf(container) {
  const f = citeFields(container);
  const snapshot = f?.snapshot_note ?? (f?.osm_timestamp ? `OSM ${day(f.osm_timestamp)}` : "");
  const source = [
    "velometer",
    snapshot,
    f?.classifier ? `classifier ${f.classifier}` : "",
    f?.commit ?? commit(),
  ]
    .filter(Boolean)
    .join(" · ");
  return {
    title: container.getAttribute("aria-label") || f?.title || document.title,
    source,
    ...light(),
    attribution: f?.attribution ?? "Map data © OpenStreetMap contributors, ODbL 1.0",
  };
}

/** The chart drawn in the container: its one SVG, or the small-multiple cards stacked. */
function chartOf(container) {
  const svgs = [...container.querySelectorAll("svg")].filter((s) => !s.closest(".legend"));
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
  if (!svg) throw new Error("There is no chart to download yet");
  const out = selfContained(svg, styleOf, isDark() ? lightOf(tokens()) : null, metaOf(container));
  const vb = out.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  return { out, w: +vb[1], h: +vb[2] };
}

function tableOf(container) {
  const id = container.getAttribute("aria-describedby");
  const table = id ? document.getElementById(id)?.closest("table") : null;
  if (!table) throw new Error("This chart has no data table to download");
  return table;
}

function nameOf(container, ext) {
  const path = location.pathname.slice(base().length - 1);
  const chart = container.dataset.chart ?? (container.hasAttribute("data-compare-chart") ? "compare"
    : container.hasAttribute("data-story-plot") ? "story" : container.dataset.planItem) ?? "chart"; // fmt: skip
  const state = [container.dataset.kind, location.search.replace(/^\?/, "")].filter(Boolean).join("-");
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
    new Blob([tableCsv(tableOf(c), commit(), new Date().toISOString().replace(/\.\d+Z$/, "Z"))], {
      type: "text/csv;charset=utf-8",
    }),
};

async function download(container, kind) {
  const name = nameOf(container, kind);
  try {
    save(await MAKE[kind](container), name);
    announce(`Downloaded ${name}`);
  } catch (e) {
    announce(`Could not make the ${kind.toUpperCase()} download. ${e.message}`);
  }
}

function control(container) {
  const d = document.createElement("details");
  d.className = "download";
  const s = document.createElement("summary");
  s.append("Download");
  const hidden = document.createElement("span");
  hidden.className = "visually-hidden";
  hidden.textContent = " chart";
  s.append(hidden);
  const row = document.createElement("div");
  row.className = "download-row";
  for (const kind of ["svg", "png", "csv"]) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = kind.toUpperCase();
    b.setAttribute("aria-label", `Download ${kind.toUpperCase()}`);
    b.addEventListener("click", () => download(container, kind));
    row.append(b);
  }
  d.append(s, row);
  return d;
}

function upgrade(container) {
  if (container.dataset.downloadBound !== undefined) return;
  container.dataset.downloadBound = "";
  container.after(control(container));
}

if (typeof document !== "undefined") {
  const scan = (root) => {
    for (const c of root.matches?.(SELECTOR) ? [root] : []) upgrade(c);
    for (const c of root.querySelectorAll?.(SELECTOR) ?? []) upgrade(c);
  };
  scan(document);
  // the city panel is fetched after load
  new MutationObserver((records) => {
    for (const r of records) for (const n of r.addedNodes) if (n.nodeType === 1) scan(n);
  }).observe(document.body, { childList: true, subtree: true });
}
