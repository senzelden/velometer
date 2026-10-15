import { test } from "node:test";
import assert from "node:assert/strict";
import { FIXTURE, useLang } from "./strings-fixture.mjs";
import { SELECTOR, control, keyOf, labelWidth, nameOf, scan, tableFor, titleOf, upgrade } from "../download-ui.js";
import { localised } from "../data.js";
import { buildModel } from "../compare-model.js";
import { t } from "../strings.js";

// A fake DOM, enough for the control: elements with attributes, a dataset, children, after().
// `matches` understands the selector forms SELECTOR uses ([a], [a=v], :not([a=v]), .c, commas),
// so the selector string itself is what is tested.
function matchesOne(el, sel) {
  const parts = sel.match(/(\.[\w-]+|\[[^\]]+\]|:not\(\[[^\]]+\]\))/g) ?? [];
  const attr = (a) => {
    const [k, v] = a.slice(1, -1).split("=");
    return [k, v];
  };
  return parts.every((p) => {
    if (p.startsWith(".")) return (el.attrs.class ?? "").split(" ").includes(p.slice(1));
    if (p.startsWith(":not(")) {
      const [k, v] = attr(p.slice(5, -1));
      return v === undefined ? !(k in el.attrs) : el.attrs[k] !== v;
    }
    const [k, v] = attr(p);
    return v === undefined ? k in el.attrs : el.attrs[k] === v;
  });
}
const matches = (el, selector) => selector.split(",").some((s) => matchesOne(el, s.trim()));

function make(tag, attrs = {}) {
  const el = {
    tag, attrs: { ...attrs }, children: [], dataset: {}, listeners: {}, after_: null,
    className: "", textContent: "",
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k] ?? null; },
    hasAttribute(k) { return k in this.attrs; },
    append(...n) { this.children.push(...n); },
    after(n) { this.after_ = n; },
    addEventListener(t, f) { this.listeners[t] = f; },
    matches(sel) { return matches({ attrs: { ...this.attrs, class: this.className || this.attrs.class } }, sel); },
    closest(t) { return t === this.tag ? this : this.parent?.closest?.(t) ?? null; },
    querySelector(t) { return this.children.find((c) => c.tag === t) ?? null; },
  };
  return el;
}
const doc = (ids = {}) => ({ createElement: make, getElementById: (id) => ids[id] ?? null });
const table = () => make("table");
const caption = (t) => Object.assign(make("caption"), { parent: t });

const CONTAINERS = {
  "data-chart": { "data-chart": "city-headline", "aria-label": "Headline over time, Berlin" },
  "data-compare-chart": { "data-compare-chart": "", "aria-label": "Chart of the selected cities" },
  "data-story-plot": { "data-story-plot": "", "aria-label": "Chart of the current step" },
  "plan-chart": { class: "chart plan-chart", "data-plan-item": "cycle", "aria-label": "Cycle plan chart" },
};

test("SELECTOR matches the four container types and not a sparkline", () => {
  for (const [name, attrs] of Object.entries(CONTAINERS)) assert.ok(matches({ attrs }, SELECTOR), name);
  assert.ok(!matches({ attrs: { class: "spark-mount", "data-chart": "sparkline" } }, SELECTOR));
  assert.ok(!matches({ attrs: { class: "plan-chart" } }, SELECTOR), "a plan chart needs its item");
});

test("each container type gets one control: details > summary + named buttons", () => {
  const ids = {};
  for (const [name, attrs] of Object.entries(CONTAINERS)) {
    const t = table();
    ids[`${name}-cap`] = caption(t);
    const c = make("div", { ...attrs, "aria-describedby": `${name}-cap` });
    upgrade(c, doc(ids));
    upgrade(c, doc(ids)); // once only
    const d = c.after_;
    assert.equal(d.tag, "details", name);
    assert.equal(d.className, "download");
    assert.equal(d.children[0].tag, "summary");
    assert.match(d.children[0].children[1].textContent, new RegExp(attrs["aria-label"].replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    const buttons = d.children[1].children;
    assert.deepEqual(buttons.map((b) => b.textContent), ["SVG", "PNG", "CSV"]);
    for (const b of buttons) {
      assert.equal(b.type, "button");
      assert.match(b.getAttribute("aria-label"), new RegExp(`^Download ${b.textContent}, `));
    }
  }
});

test("scan upgrades matching containers in a root and skips sparklines", () => {
  const good = make("div", CONTAINERS["data-chart"]);
  const spark = make("span", { class: "spark-mount", "data-chart": "sparkline" });
  scan({ querySelectorAll: (sel) => [good, spark].filter((e) => e.matches(sel)) }, doc());
  assert.ok(good.after_);
  assert.equal(spark.after_, null);
});

test("no CSV button without a data table; accessible names are unique per page", () => {
  const a = make("div", { "data-chart": "x", "aria-label": "Same name" });
  const b = make("div", { "data-chart": "x", "aria-label": "Same name" });
  upgrade(a, doc());
  upgrade(b, doc());
  assert.deepEqual(a.after_.children[1].children.map((x) => x.textContent), ["SVG", "PNG"]);
  const names = [a, b].flatMap((c) => ["Download" + c.after_.children[0].children[1].textContent, ...c.after_.children[1].children.map((x) => x.getAttribute("aria-label"))]);
  assert.equal(new Set(names).size, names.length, names.join(" | "));
});

test("the table is resolved at setup, so it survives the chart losing aria-describedby", () => {
  const ids = { cap: caption(table()) };
  const c = make("div", { "data-compare-chart": "", "aria-label": "Compare chart", "aria-describedby": "cap" });
  const d = control(c, doc(ids));
  assert.ok(d.children[1].children.some((b) => b.textContent === "CSV"));
  assert.equal(c.dataset.downloadTable, "cap");
});

test("a <summary> beside its table (the tier tables) resolves to that table, a <caption> inside it too", () => {
  const t = table();
  const details = make("details");
  const summary = Object.assign(make("summary"), { parent: details });
  details.children.push(summary, t);
  assert.equal(tableFor(summary), t);
  const cap = caption(t);
  assert.equal(tableFor(cap), t);
  assert.equal(tableFor(null), null);
  const c = make("div", { "data-chart": "city-tiers", "aria-label": "Tiers", "aria-describedby": "sum" });
  const d = control(c, doc({ sum: summary }));
  assert.ok(d.children[1].children.some((b) => b.textContent === "CSV"));
});

// ---- the title and source line of a download (final review findings 2 and 4) ----
// A small tree DOM: parentElement, nextElementSibling, matches/querySelector(All) for the simple
// selectors download-ui.js asks with (tag, .class, [attr], tag.class, comma lists).
function simpleMatch(el, sel) {
  if (/\s/.test(sel)) return false; // descendant selectors: not modelled, matches nothing
  const tag = sel.match(/^[a-z][\w-]*/)?.[0];
  if (tag && el.tag !== tag) return false;
  for (const c of sel.match(/\.[\w-]+/g) ?? []) if (!(el.attrs.class ?? "").split(" ").includes(c.slice(1))) return false;
  for (const a of sel.match(/\[[^\]]+\]/g) ?? []) {
    const [k, v] = a.slice(1, -1).split("=");
    if (!(k in el.attrs) || (v !== undefined && el.attrs[k] !== v)) return false;
  }
  return true;
}
function h(tag, attrs = {}, ...children) {
  const el = {
    tag, attrs, children, parentElement: null, textContent: attrs.text ?? "",
    getAttribute(k) { return this.attrs[k] ?? null; },
    hasAttribute(k) { return k in this.attrs; },
    matches(sel) { return sel.split(",").some((s) => simpleMatch(this, s.trim())); },
    querySelectorAll(sel) {
      return this.children.flatMap((c) => [...(c.matches(sel) ? [c] : []), ...c.querySelectorAll(sel)]);
    },
    querySelector(sel) { return this.querySelectorAll(sel)[0] ?? null; },
    get nextElementSibling() {
      const sibs = this.parentElement?.children ?? [];
      return sibs[sibs.indexOf(this) + 1] ?? null;
    },
    dataset: {},
  };
  for (const c of children) c.parentElement = el;
  return el;
}
const cite = (fields) => h("details", { class: "cite" }, h("script", { class: "cite-data", text: JSON.stringify(fields) }));
const fieldsAt = (title, ts, extra = {}) => ({ title, osm_timestamp: ts, classifier: "v4", commit: "abc1234", ...extra });
function page(...children) {
  const body = h("body", {}, ...children);
  const all = (n) => [n, ...n.children.flatMap(all)];
  globalThis.document = {
    body, title: "velometer page",
    getElementById: (id) => all(body).find((n) => n.attrs.id === id) ?? null,
    querySelector: () => null,
  };
  return globalThis.document;
}

test("a FUA chart's download names the run of its own Cite, not the LAU chart's above it", async () => {
  const { metaOf } = await import("../download-ui.js");
  const chart = (kind) => h("div", { "data-chart": "city-tiers", "data-kind": kind,
    "aria-label": `Tier composition over time, Berlin ${kind.toUpperCase()}`, "aria-describedby": `sum-${kind}` }); // fmt: skip
  const lau = chart("lau");
  const fua = chart("fua");
  page(h("section", {},
    h("h3"), lau, h("details", {}, h("summary", { id: "sum-lau" }), h("table")),
    cite(fieldsAt("Berlin: tiers, LAU", "2026-10-03T01:00:00Z", { classifier: "v4" })),
    h("h3"), fua, h("details", {}, h("summary", { id: "sum-fua" }), h("table")),
    cite(fieldsAt("Berlin: tiers, FUA", "2026-09-01T01:00:00Z", { classifier: "v3" })),
  )); // fmt: skip
  const m = metaOf(fua);
  assert.match(m.source, /OSM 2026-09-01/);
  assert.match(m.source, /classifier v3/);
  assert.doesNotMatch(m.source, /2026-10-03/);
  assert.match(metaOf(lau).source, /OSM 2026-10-03 · classifier v4/);
  assert.equal(m.title, "Tier composition over time, Berlin FUA"); // a specific label is kept
});

test("a chart with no Cite in its section does not borrow the next section's", async () => {
  const { metaOf } = await import("../download-ui.js");
  const lone = h("div", { "data-chart": "x", "aria-label": "Lone chart" });
  page(h("section", {}, lone), h("section", {}, cite(fieldsAt("Other", "2026-01-01T00:00:00Z"))));
  assert.doesNotMatch(metaOf(lone).source, /2026-01-01/);
});

test("a Compare download is titled with what it shows, not the container's generic label", async () => {
  const { metaOf } = await import("../download-ui.js");
  const svg = h("svg", { "aria-label": "Line chart: Mapped km per 1,000, City proper (LAU)" });
  const box = () => h("div", { "data-compare-chart": "", "aria-label": "Chart of the selected cities",
    "aria-describedby": "compare-caption" }, svg); // fmt: skip
  const title = "Compare: Mapped km per 1,000 · City proper (LAU); Berlin, Paris";
  let c = box();
  page(h("section", { class: "compare-out" }, h("h2"), c,
    h("div", { class: "scroll" }, h("table", {}, h("caption", { id: "compare-caption" }))),
    cite(fieldsAt(title, null, { snapshot_note: "OSM snapshot of 2026-10-03" })))); // fmt: skip
  assert.equal(metaOf(c).title, title);
  c = box(); // no run for the selection: no Cite, the drawn chart names itself
  page(h("section", { class: "compare-out" }, c));
  assert.equal(metaOf(c).title, svg.attrs["aria-label"]);
});

test("a Stories download is titled from the step it shows (the one its description names)", async () => {
  const { metaOf } = await import("../download-ui.js");
  const plot = h("div", { "data-story-plot": "", "aria-label": "Chart of the current step",
    "aria-describedby": "step-values-b" }, h("svg", { "aria-label": "Line chart: B" })); // fmt: skip
  const step = (id, title) => h("section", { class: "story-step" },
    h("details", { class: "step-values" }, h("summary", { id: `step-values-${id}` }), h("table")),
    cite(fieldsAt(title, "2026-10-03T01:00:00Z"))); // fmt: skip
  page(h("div", {}, h("aside", {}, plot), h("article", {}, step("a", "A (Stories)"), step("b", "B (Stories)"))));
  assert.equal(metaOf(plot).title, "B (Stories)");
});

test("a German page's download: German source line and attribution, the name without de/", async () => {
  const { metaOf } = await import("../download-ui.js");
  useLang("de");
  const chart = h("div", { "data-chart": "city-tiers", "data-kind": "fua", "aria-label": "Stufen" });
  chart.dataset = { chart: "city-tiers", kind: "fua" };
  page(h("section", {}, chart, cite(fieldsAt("Krakau: Stufen", "2026-10-03T01:00:00Z"))));
  const m = metaOf(chart);
  assert.match(m.source, /OSM-Stand 2026-10-03 · Klassifikator v4/);
  assert.equal(m.attribution, FIXTURE.de["js.download.attribution"]);
  assert.match(m.attribution, /OpenStreetMap-Mitwirkende/);
  useLang("en");
  assert.match(metaOf(chart).source, /OSM 2026-10-03 · classifier v4/);
  const at = (pathname) => ({ pathname, search: "" });
  const de = nameOf(chart, "png", at("/velometer/de/city/krakow/tiers"), "/velometer/");
  const en = nameOf(chart, "png", at("/velometer/city/krakow/tiers"), "/velometer/");
  assert.equal(de, en);
  assert.equal(en, "velometer-city-krakow-tiers-city-tiers-fua.png");
  assert.equal(nameOf(chart, "png", at("/de/"), "/"), nameOf(chart, "png", at("/"), "/"));
});

test("a German chart title names the city as the localised series does (Krakau)", () => {
  useLang("de");
  const D = localised({
    cities: { krakow: { id: "krakow", name: "Kraków", name_de: "Krakau", population: 1 } },
    series: { "krakow/lau": [{ label: "2019", headline: 2, flags: "" }] },
  }, "de");
  const model = buildModel(D, { c: ["krakow"], hl: [], m: "headline", b: "lau", mode: "abs" });
  const title = t("js.compare.cite_title", {
    heading: "Kennzahl", cities: model.series.map((s) => s.name).join(", "),
  });
  const container = Object.assign(make("div", { "data-compare-chart": "" }), { querySelectorAll: () => [] });
  assert.ok(titleOf(container, { title }).includes("Krakau"));
  assert.ok(!titleOf(container, { title }).includes("Kraków"));
  useLang("en");
});

// ---- the key in the image (M13: M11-4, M11-8) ----

/** A page that measures text as `measure` says (undefined: no getComputedTextLength). */
function measuringDoc(measure) {
  const appended = [];
  const el = (tag) => ({
    tag, style: {}, children: [], attrs: {}, textContent: "",
    setAttribute(k, v) { this.attrs[k] = v; },
    append(...n) { this.children.push(...n); },
    remove() { appended.splice(appended.indexOf(this), 1); },
    ...(tag === "text" && measure ? { getComputedTextLength() { return measure(this.textContent); } } : {}),
  });
  return { appended, createElementNS: (_ns, tag) => el(tag), body: { append: (n) => appended.push(n) } };
}

test("labelWidth: the browser's measure of the label at the image's font, else null", () => {
  const doc = measuringDoc((s) => s.length * 5);
  assert.equal(labelWidth("abcd", doc), 20);
  assert.deepEqual(doc.appended, [], "the measuring SVG is removed again");
  assert.equal(labelWidth("abcd", measuringDoc(undefined)), null, "no getComputedTextLength");
  assert.equal(labelWidth("abcd", measuringDoc(() => 0)), null, "nothing laid out");
  assert.equal(labelWidth("abcd", {}), null, "no DOM at all");
});

test("keyOf reads the .legend .chip key chart.js draws: colour, text and measured width", () => {
  const chip = (colour, text) => ({
    textContent: ` ${text} `,
    querySelector: (sel) => (sel === "i" ? { colour } : null),
  });
  const chips = [chip("rgb(1, 2, 3)", "A separated track"), chip("rgb(4, 5, 6)", "B shared path")];
  const container = { querySelectorAll: (sel) => (sel === ".legend .chip" ? chips : []) };
  const before = globalThis.getComputedStyle;
  globalThis.getComputedStyle = (i) => ({ backgroundColor: i.colour });
  try {
    assert.deepEqual(keyOf(container, measuringDoc((s) => s.length * 6)), [
      { colour: "rgb(1, 2, 3)", text: "A separated track", width: 102 },
      { colour: "rgb(4, 5, 6)", text: "B shared path", width: 78 },
    ]);
  } finally {
    globalThis.getComputedStyle = before;
  }
});

test("keyOf reads the key list a chart names (data-download-key): the plan and Counts keys", () => {
  // M13 Task 13a (M11-8, user review): the plan page's key and a Counts tab's key are lists beside
  // the chart; the chart names its list, and each entry's mark gives its glyph
  const mark = (style) => ({ style });
  const li = (style, text) => ({ textContent: `  ${text}\n `, querySelector: (sel) => (sel === ".key" ? mark(style) : null) });
  const dashed = { borderTopStyle: "dashed", borderTopColor: "rgb(9, 9, 9)", borderRadius: "0px", backgroundColor: "rgba(0, 0, 0, 0)", height: "0px" };
  const ring = { borderTopStyle: "solid", borderTopColor: "rgb(1, 2, 3)", borderRadius: "50%", backgroundColor: "rgb(255, 255, 255)", height: "12px" };
  const list = { querySelectorAll: (sel) => (sel === "li" ? [li(dashed, "target per year"), li(ring, "reported,   revision")] : []) };
  const page = { ...measuringDoc((s) => s.length * 6), getElementById: (id) => (id === "plan-key" ? list : null) };
  const container = {
    querySelectorAll: () => [],
    getAttribute: (k) => (k === "data-download-key" ? "plan-key" : null),
  };
  const before = globalThis.getComputedStyle;
  globalThis.getComputedStyle = (m) => m.style;
  try {
    assert.deepEqual(keyOf(container, page), [
      { shape: "dash", colour: "rgb(9, 9, 9)", text: "target per year", width: 90 },
      { shape: "ring", colour: "rgb(1, 2, 3)", fill: "rgb(255, 255, 255)", text: "reported, revision", width: 108 },
    ]);
    // a chart that names no key, or a key not on the page: no entries
    assert.deepEqual(keyOf({ ...container, getAttribute: () => null }, page), []);
    assert.deepEqual(keyOf({ ...container, getAttribute: () => "gone" }, page), []);
  } finally {
    globalThis.getComputedStyle = before;
  }
});

test("labelWidth measures at the size and weight it is asked for (the title is 15px, 600)", () => {
  const doc = measuringDoc((s) => s.length * 5);
  const seen = [];
  const create = doc.createElementNS;
  doc.createElementNS = (ns, tag) => {
    const el = create(ns, tag);
    if (tag === "text") seen.push(el.attrs);
    return el;
  };
  labelWidth("abcd", doc);
  labelWidth("abcd", doc, "15px", "600");
  assert.deepEqual(seen.map((a) => [a["font-size"], a["font-weight"]]), [["11px", "400"], ["15px", "600"]]);
});

test("metaOf hands the image a measure for its title and meta lines", async () => {
  const { metaOf } = await import("../download-ui.js");
  const chart = h("div", { "data-chart": "city-tiers", "aria-label": "Tiers" });
  chart.dataset = { chart: "city-tiers" };
  page(h("section", {}, chart));
  const m = metaOf(chart);
  assert.equal(typeof m.measure, "function");
  assert.equal(m.measure("abc", "15px", "600"), null); // no layout in this fake page: estimate
});
