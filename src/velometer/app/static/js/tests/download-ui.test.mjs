import { test } from "node:test";
import assert from "node:assert/strict";
import { SELECTOR, control, scan, tableFor, upgrade } from "../download-ui.js";

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
