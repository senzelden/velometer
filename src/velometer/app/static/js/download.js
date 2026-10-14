// Chart downloads (M11 decision 4): a chart as a self-contained SVG or PNG, and its data table as
// CSV. Built in the browser from what the page holds. A download is always the light theme: the
// page may show the dark one, so every colour is resolved through computed style and mapped back
// to its light token value. Pure apart from the DOM it is given; download-ui.js wires the page.
// The image's text is the page's language (M12); the CSV keeps machine number formats and its
// English two-line preamble (spec 4.5).
import { machine } from "./fmt.js";
import { t } from "./strings.js";

const NS = "http://www.w3.org/2000/svg";
// the CSV preamble, English in both editions
export const ATTRIBUTION = "Map data © OpenStreetMap contributors, ODbL 1.0";
const CSV_NOTE = "OSM mapped km, not built km";
// the added text and ground use the light tokens the caller passes in `meta` (no colour literal in a script)
const FALLBACK = { ground: "white", ink: "black", muted: "gray" };

/** The computed-style properties written as attributes (colour ones go through the light map). */
export const COLOUR_PROPS = ["fill", "stroke"];
export const PLAIN_PROPS = [
  "opacity", "fill-opacity", "stroke-opacity", "stroke-width", "stroke-dasharray",
  "stroke-linecap", "stroke-linejoin", "font-size", "font-weight", "text-anchor",
  "dominant-baseline",
]; // fmt: skip
const DEFAULTS = {
  opacity: "1", "fill-opacity": "1", "stroke-opacity": "1", "stroke-dasharray": "none",
  "stroke-linecap": "butt", "stroke-linejoin": "miter", "text-anchor": "start",
  "dominant-baseline": "auto", "font-weight": "400",
}; // fmt: skip
const SHAPES = new Set([
  "svg", "g", "path", "line", "rect", "circle", "ellipse", "polyline", "polygon", "text",
  "tspan", "title", "desc", "defs", "clipPath",
]);
const SKIP_ATTR = /^(class|style|role|tabindex|data-.*|aria-.*|on.*|xmlns.*)$/;

const two = (n) => n.toString(16).padStart(2, "0");

/** A computed rgb colour, or a 3 or 6 digit hex one, as 6 digit lower-case hex; any other string (a name, one with alpha, a variable) is null. */
export function hex(cssColour) {
  const s = String(cssColour ?? "").trim().toLowerCase();
  let m = s.match(/^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/) ?? s.match(/^rgb\(\s*(\d+)\s+(\d+)\s+(\d+)\s*\)$/);
  if (m) return `#${two(+m[1])}${two(+m[2])}${two(+m[3])}`;
  m = s.match(/^#([0-9a-f]{3})$/);
  if (m) return `#${[...m[1]].map((c) => c + c).join("")}`;
  return /^#[0-9a-f]{6}$/.test(s) ? s : null;
}

/** Map(darkHex -> lightHex) over the tokens ({name: [light, dark]}). */
export function lightOf(tokens) {
  const map = new Map();
  for (const [light, dark] of Object.values(tokens)) {
    const d = hex(dark);
    const l = hex(light);
    if (d && l) map.set(d, l);
  }
  return map;
}

const esc = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const attrs = (pairs) => pairs.map(([k, v]) => ` ${k}="${esc(v)}"`).join("");

const RGB = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)\s*(?:[,/]\s*([\d.]+)(%?))?\s*\)$/;

/** A computed colour as {value, alpha}: value a light hex (or "none"), alpha 0..1; null when it is
 * none of those (a paint server reference, a keyword). A colour with alpha keeps its rgb and says the alpha. */
function colour(value, toLight) {
  const s = String(value ?? "").trim().toLowerCase();
  if (s === "none" || s === "transparent") return { value: "none", alpha: 1 };
  let h = hex(s);
  let alpha = 1;
  const m = s.match(RGB);
  if (m) {
    h = `#${two(+m[1])}${two(+m[2])}${two(+m[3])}`;
    if (m[4] !== undefined) alpha = m[5] ? +m[4] / 100 : +m[4];
  }
  if (!h) return null;
  if (alpha <= 0) return { value: "none", alpha: 1 };
  return { value: toLight?.get(h) ?? h, alpha };
}

/** The size the chart is drawn at: its viewBox, else its width and height. */
export function sizeOf(svg) {
  const get = (n) => svg.attributes && Array.from(svg.attributes).find((a) => a.name === n)?.value;
  const vb = (get("viewBox") ?? "").trim().split(/[\s,]+/).map(Number);
  if (vb.length === 4 && vb.every(Number.isFinite) && vb[2] > 0 && vb[3] > 0) return { w: vb[2], h: vb[3] };
  return { w: parseFloat(get("width")) || 600, h: parseFloat(get("height")) || 300 };
}

function walk(el, styleOf, toLight, out) {
  const tag = el.tagName;
  if (!SHAPES.has(tag)) return;
  const st = styleOf(el) ?? {};
  if (st.display === "none" || st.visibility === "hidden") return;
  const own = Array.from(el.attributes ?? [])
    .filter(({ name, value }) => !SKIP_ATTR.test(name) && !/var\(/.test(value))
    .filter(({ name, value }) => !/^(xlink:)?href$/.test(name) || value.startsWith("#"))
    .map(({ name, value }) => [name, value]);
  const written = new Map(own);
  if (tag !== "svg") {
    const alphas = {};
    for (const p of COLOUR_PROPS) {
      const c = st[p] === undefined ? null : colour(st[p], toLight);
      if (c === null) continue;
      // a stroke of none is the default, and a line has no fill to speak of
      if (p === "stroke" && c.value === "none") continue;
      if (p === "fill" && (tag === "line" || tag === "title" || tag === "desc")) continue;
      written.set(p, c.value);
      if (c.alpha < 1) alphas[p] = c.alpha;
    }
    const strokeless = !written.has("stroke");
    const fromAlpha = () => {
      for (const [p, a] of Object.entries(alphas)) {
        const own = parseFloat(written.get(`${p}-opacity`) ?? 1);
        written.set(`${p}-opacity`, String(+(a * own).toFixed(3)));
      }
    };
    for (const p of PLAIN_PROPS) {
      const v = st[p];
      if (v === undefined || v === "" || v === DEFAULTS[p] || v === "normal") continue;
      if (p.startsWith("font-") || p === "text-anchor" || p === "dominant-baseline") {
        if (tag !== "text" && tag !== "tspan") continue;
      }
      if (p.startsWith("stroke-") && p !== "stroke-opacity" && strokeless) continue;
      written.set(p, v);
    }
    fromAlpha();
  }
  const kids = Array.from(el.children ?? []);
  const open = `<${tag}${attrs([...written])}`;
  if (!kids.length && !el.textContent) {
    out.push(`${open}/>`);
    return;
  }
  out.push(`${open}>`);
  if (kids.length) for (const k of kids) walk(k, styleOf, toLight, out);
  else out.push(esc(el.textContent));
  out.push(`</${tag}>`);
}

const TOP = 30;
const BOTTOM = 44;

const KEY_ROW = 18;
const CHAR = 6.6; // an estimate of the width of a character at 11px, to wrap the key

/** The key chips ({colour, text}) in rows that fit the width, each chip with its x. */
function layoutKey(chips, width) {
  const rows = [];
  let row = [];
  let x = 8;
  for (const c of chips) {
    const need = 14 + c.text.length * CHAR + 14;
    if (row.length && x + need > width) {
      rows.push(row);
      row = [];
      x = 8;
    }
    row.push({ ...c, x });
    x += need;
  }
  if (row.length) rows.push(row);
  return rows;
}

/** A swatch and a label per chip: the key of a chart whose key is HTML beside the SVG. */
function keySvg(rows, top, toLight, ink, txt) {
  if (!rows.length) return [];
  const out = ['<g id="velometer-key">'];
  rows.forEach((row, i) => {
    const y = top + 6 + i * KEY_ROW;
    for (const c of row) {
      const col = colour(c.colour, toLight);
      out.push(`<rect${attrs([["x", c.x], ["y", y], ["width", 10], ["height", 10], ["fill", col?.value ?? "none"]])}/>`); // fmt: skip
      out.push(txt(c.x + 14, y + 9, "11px", "400", ink, c.text));
    }
  });
  out.push("</g>");
  return out;
}

/**
 * The chart as one self-contained SVG string. Every colour and text property comes from
 * `styleOf(el)` (computed style, one object keyed by CSS property name), written as an attribute,
 * mapped through `toLight` (a Map, or null for the identity). No class, style, `var()`, external
 * reference or custom attribute is kept. A title, a source line and the attribution are added as
 * text, on a light ground.
 */
export function selfContained(svg, styleOf, toLight, meta) {
  const { w, h } = sizeOf(svg);
  const { ground, ink, muted } = { ...FALLBACK, ...Object.fromEntries(Object.entries(meta).filter(([k, v]) => k in FALLBACK && v)) };
  const keyRows = layoutKey(meta.key ?? [], w);
  const keyH = keyRows.length * KEY_ROW + (keyRows.length ? 6 : 0);
  const height = h + TOP + keyH + BOTTOM;
  const inner = [];
  for (const k of Array.from(svg.children ?? [])) walk(k, styleOf, toLight, inner);
  const txt = (x, y, size, weight, fill, text) =>
    `<text${attrs([["x", x], ["y", y], ["font-size", size], ["font-weight", weight], ["fill", fill]])}>${esc(text)}</text>`; // fmt: skip
  return [
    `<svg xmlns="${NS}"${attrs([["viewBox", `0 0 ${w} ${height}`], ["width", w], ["height", height], ["font-family", "system-ui, sans-serif"]])}>`, // fmt: skip
    `<rect${attrs([["width", w], ["height", height], ["fill", ground]])}/>`,
    txt(8, 20, "15px", "600", ink, meta.title),
    `<g transform="translate(0,${TOP})">`,
    ...inner,
    "</g>",
    ...keySvg(keyRows, h + TOP, toLight, ink, txt),
    `<g id="velometer-meta">`,
    txt(8, h + TOP + keyH + 18, "11px", "400", muted, meta.source),
    txt(8, h + TOP + keyH + 33, "11px", "400", muted,
      `${meta.attribution ?? t("js.download.attribution")} · ${t("js.download.note")}`),
    "</g>",
    "</svg>",
  ].join("");
}

const text = (n) => String(n?.textContent ?? "").replace(/\s+/g, " ").trim();
/** A cell a spreadsheet would run as a formula starts with a quote mark instead (OWASP CSV
 * injection): = + @ tab and CR always, and - unless the whole cell is a number or a lone dash
 * (a no-data mark: - – — or U+2212 alone runs nothing). The same rule is
 * `velometer.report.csvexport.safe_cell`. */
const NO_DATA = new Set(["-", "\u2013", "\u2014", "\u2212"]);
export function safeCell(s) {
  if (NO_DATA.has(s)) return s;
  if (/^[=+@\t\r]/.test(s)) return `'${s}`;
  if (s.startsWith("-") && !/^-\d[\d,]*(\.\d+)?$/.test(s)) return `'${s}`;
  return s;
}
const cell = (raw) => {
  const s = safeCell(raw);
  return /[",\r\n]|^\s|\s$/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

/**
 * The table as shown: a two-line preamble, the header texts, the rows (RFC 4180, CRLF). For a
 * German page (`loc` "de-DE") a cell that is wholly a German number is written as a machine
 * number (dot decimal, no grouping: "1.639,8" is 1639.8); every other cell, and every cell of an
 * English page, as shown.
 */
export function tableCsv(table, commit, generatedAt, loc = "en-GB") {
  const shown = (n) => {
    const s = text(n);
    return loc === "de-DE" ? (machine(s, loc) ?? s) : s;
  };
  const head = Array.from(table.querySelectorAll("thead th")).map(shown);
  const rows = Array.from(table.querySelectorAll("tbody tr")).map((tr) =>
    Array.from(tr.querySelectorAll("th, td")).map(shown),
  );
  return (
    [
      `# ${ATTRIBUTION} — ${CSV_NOTE}`,
      `# velometer ${commit} generated ${generatedAt}`,
      ...[head, ...rows].map((r) => r.map(cell).join(",")),
    ].join("\r\n") + "\r\n"
  );
}

/** An ASCII file-name part: ß is "ss", accents go, every other run of characters is one "-". */
export const slug = (s) =>
  String(s ?? "")
    .replace(/ß/g, "ss")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

/** "velometer-<page>-<chart>[-<state>].<ext>", ASCII. */
export function fileName(page, chart, state, ext) {
  return `${["velometer", page, chart, state].map(slug).filter(Boolean).join("-")}.${ext}`;
}

/** The SVG drawn on a canvas at `scale` (a data: URL image, so the canvas is never tainted). */
export function pngBlob(svgString, width, height, scale = 2, doc = document, ImageCtor = globalThis.Image) {
  return new Promise((resolve, reject) => {
    const img = new ImageCtor();
    img.onload = () => {
      try {
        const canvas = doc.createElement("canvas");
        canvas.width = Math.round(width * scale);
        canvas.height = Math.round(height * scale);
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        canvas.toBlob((b) => (b ? resolve(b) : reject(new Error(t("js.download.no_png")))), "image/png");
      } catch (e) {
        reject(e);
      }
    };
    img.onerror = () => reject(new Error(t("js.download.image_failed")));
    img.width = Math.round(width * scale);
    img.height = Math.round(height * scale);
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgString)}`;
  });
}
