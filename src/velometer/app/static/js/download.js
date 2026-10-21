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
export const ATTRIBUTION =
  "Map data © OpenStreetMap contributors (https://www.openstreetmap.org/copyright), ODbL 1.0 (https://opendatacommons.org/licenses/odbl/1-0/)";
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
const KEY_LINE = 14; // a wrapped key label's next line
const CHAR = 6.6; // an estimate of the width of a character at 11px, where none was measured
const TITLE_CHAR = 15 * 0.62; // the same at 15px, weight 600 (the title)
const TITLE_LINE = 19; // a wrapped title's next line
const META_LINE = 15; // the next source or attribution line

/**
 * A key entry's glyph, from the computed style (camelCase, as getComputedStyle gives it) of its
 * mark in the page's key (`<span class="key ...">`, drawn by app.css): a round mark is a dot, or a
 * ring when it has a ground of its own; a mark drawn by its top border alone is a line, dashed when
 * that border is;
 * any other is a swatch. The colour is the border's, or the ground's where the mark has no border.
 */
export function glyphOf(st) {
  const solid = (c) => {
    const v = colour(c, null);
    return v && v.value !== "none" ? c : null;
  };
  const border = st.borderTopStyle && st.borderTopStyle !== "none" ? solid(st.borderTopColor) : null;
  const ground = solid(st.backgroundColor);
  if (String(st.borderRadius ?? "").startsWith("50%") && border) {
    return ground ? { shape: "ring", colour: border, fill: ground } : { shape: "dot", colour: border };
  }
  // a line is a top border alone (with border-box sizing its computed height is the border's)
  const topOnly = st.borderBottomStyle ? st.borderBottomStyle === "none" : parseFloat(st.height) === 0;
  if (topOnly && border) return { shape: st.borderTopStyle === "dashed" ? "dash" : "line", colour: border };
  return { shape: "swatch", colour: border ?? ground ?? "" };
}

/** A label's lines, each at most `room` px wide by `measure(line)` (a string's width in px), broken
 * at spaces: a word joins the line only if the longer line still measures within the room. A single
 * word wider than the room stays whole on its own line. */
export function wrap(text, measure, room) {
  const lines = [];
  let line = "";
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const next = line ? `${line} ${word}` : word;
    if (line && measure(next) > room) {
      lines.push(line);
      line = word;
    } else line = next;
  }
  if (line) lines.push(line);
  return lines;
}

/** `text` in lines at most `room` px wide by `measure`. */
export function fit(text, measure, room) {
  return measure(text) <= room ? [text] : wrap(text, measure, room);
}

/** A width measure for text at one size and weight: the page's (`meta.measure`) where it gives a
 * number, else `perChar` px a character. */
function measureOf(meta, size, weight, perChar) {
  return (s) => {
    const w = typeof meta.measure === "function" ? meta.measure(s, size, weight) : null;
    return Number.isFinite(w) && w > 0 ? w : s.length * perChar;
  };
}

/** The key chips ({shape?, colour, fill?, text, width?}) in rows that fit the width, each chip with
 * its x and its label's lines. A chip's `width` is its label measured in the page
 * (getComputedTextLength); without one the label's width is estimated from its length. A label
 * wider than the image wraps onto lines of its own, each line by `measure(line)` (the key font's
 * measure; without one, the chip's own average character width); a row is as tall as its tallest
 * chip. */
function layoutKey(chips, width, measure) {
  const rows = [];
  let row = [];
  let x = 8;
  const room = Math.max(40, width - 8 - 14 - 8);
  for (const c of chips) {
    const measured = Number.isFinite(c.width) && c.width > 0 ? c.width : c.text.length * CHAR;
    const per = measured / Math.max(1, c.text.length);
    const lineWidth = measure ?? ((s) => s.length * per);
    const lines = measured <= room ? [c.text] : wrap(c.text, lineWidth, room);
    const label = lines.length > 1 ? room : measured;
    const need = 14 + label + 14;
    if (row.length && x + need > width) {
      rows.push(row);
      row = [];
      x = 8;
    }
    row.push({ ...c, x, lines });
    x += need;
  }
  if (row.length) rows.push(row);
  return rows.map((r) => ({ chips: r, h: KEY_ROW + (Math.max(...r.map((c) => c.lines.length)) - 1) * KEY_LINE }));
}

/** A glyph per chip (swatch, line, dashed line, dot or ring, as the page's key draws it) and its
 * label: the key of a chart whose key is HTML beside the SVG. */
function keySvg(rows, top, toLight, ink, txt) {
  if (!rows.length) return [];
  const out = ['<g id="velometer-key">'];
  let y = top + 6;
  for (const row of rows) {
    for (const c of row.chips) {
      const col = colour(c.colour, toLight)?.value ?? "none";
      const [cx, cy] = [c.x + 5, y + 5];
      const glyph = {
        line: () => `<line${attrs([["x1", c.x - 1], ["y1", cy], ["x2", c.x + 11], ["y2", cy], ["stroke", col], ["stroke-width", 3]])}/>`, // fmt: skip
        dash: () => `<line${attrs([["x1", c.x - 1], ["y1", cy], ["x2", c.x + 11], ["y2", cy], ["stroke", col], ["stroke-width", 2], ["stroke-dasharray", "4 2"]])}/>`, // fmt: skip
        dot: () => `<circle${attrs([["cx", cx], ["cy", cy], ["r", 5], ["fill", col]])}/>`,
        ring: () => `<circle${attrs([["cx", cx], ["cy", cy], ["r", 4], ["fill", colour(c.fill, toLight)?.value ?? "none"], ["stroke", col], ["stroke-width", 2]])}/>`, // fmt: skip
      }[c.shape];
      out.push(glyph ? glyph() : `<rect${attrs([["x", c.x], ["y", y], ["width", 10], ["height", 10], ["fill", col]])}/>`); // fmt: skip
      c.lines.forEach((line, i) => out.push(txt(c.x + 14, y + 9 + i * KEY_LINE, "11px", "400", ink, line)));
    }
    y += row.h;
  }
  out.push("</g>");
  return out;
}

/**
 * The chart as one self-contained SVG string. Every colour and text property comes from
 * `styleOf(el)` (computed style, one object keyed by CSS property name), written as an attribute,
 * mapped through `toLight` (a Map, or null for the identity). No class, style, `var()`, external
 * reference or custom attribute is kept. A title, a source line and the attribution are added as
 * text, on a light ground. Each of them wraps at spaces where it is wider than the image: by the
 * width `meta.measure(text, size, weight)` gives (the page measures it, getComputedTextLength),
 * else by an estimate from its length. The chart moves down by the extra title lines, and the
 * canvas grows by them and by the extra meta lines.
 */
export function selfContained(svg, styleOf, toLight, meta) {
  const { w, h } = sizeOf(svg);
  const { ground, ink, muted } = { ...FALLBACK, ...Object.fromEntries(Object.entries(meta).filter(([k, v]) => k in FALLBACK && v)) };
  const titleWidth = measureOf(meta, "15px", "600", TITLE_CHAR);
  const noteWidth = measureOf(meta, "11px", "400", CHAR);
  const room = Math.max(40, w - 16);
  const title = String(meta.title ?? "");
  const titleLines = fit(title, titleWidth, room);
  const notes = [String(meta.source ?? ""), `${meta.attribution ?? t("js.download.attribution")} · ${t("js.download.note")}`];
  const metaLines = notes.flatMap((line) => fit(line, noteWidth, room));
  const top = TOP + (titleLines.length - 1) * TITLE_LINE;
  const keyRows = layoutKey(meta.key ?? [], w, typeof meta.measure === "function" ? noteWidth : null);
  const keyH = keyRows.reduce((sum, r) => sum + r.h, 0) + (keyRows.length ? 6 : 0);
  const height = h + top + keyH + BOTTOM + (metaLines.length - 2) * META_LINE;
  const inner = [];
  for (const k of Array.from(svg.children ?? [])) walk(k, styleOf, toLight, inner);
  const txt = (x, y, size, weight, fill, text) =>
    `<text${attrs([["x", x], ["y", y], ["font-size", size], ["font-weight", weight], ["fill", fill]])}>${esc(text)}</text>`; // fmt: skip
  return [
    `<svg xmlns="${NS}"${attrs([["viewBox", `0 0 ${w} ${height}`], ["width", w], ["height", height], ["font-family", "system-ui, sans-serif"]])}>`, // fmt: skip
    `<rect${attrs([["width", w], ["height", height], ["fill", ground]])}/>`,
    ...titleLines.map((line, i) => txt(8, 20 + i * TITLE_LINE, "15px", "600", ink, line)),
    `<g transform="translate(0,${top})">`,
    ...inner,
    "</g>",
    ...keySvg(keyRows, h + top, toLight, ink, txt),
    `<g id="velometer-meta">`,
    ...metaLines.map((line, i) => txt(8, h + top + keyH + 18 + i * META_LINE, "11px", "400", muted, line)),
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
