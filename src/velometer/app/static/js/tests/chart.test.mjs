import { test } from "node:test";
import assert from "node:assert/strict";

// Minimal stub DOM: enough for chart.js to build a tree. Any innerHTML write is a failure.
class Node {
  constructor(tag) {
    this.tag = tag;
    this.attrs = {};
    this.children = [];
    this.style = {};
    this.listeners = {};
    this._text = "";
    this.classList = { add() {}, remove() {}, toggle() {} };
    this.dataset = {};
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k]; }
  appendChild(c) { this.children.push(c); return c; }
  append(...cs) { for (const c of cs) this.children.push(c); }
  insertBefore(c, ref) {
    const i = ref ? this.children.indexOf(ref) : -1;
    this.children.splice(i < 0 ? this.children.length : i, 0, c);
    return c;
  }
  get firstChild() { return this.children[0] ?? null; }
  replaceChildren(...cs) { this.children = cs; }
  addEventListener(t, f) { this.listeners[t] = f; }
  getBoundingClientRect() { return { left: 0, top: 0 }; }
  set textContent(v) { this._text = String(v); }
  get textContent() { return this._text; }
  set innerHTML(_) { throw new Error("innerHTML must not be used"); }
  get clientWidth() { return 600; }
  find(tag, out = []) {
    if (this.tag === tag) out.push(this);
    for (const c of this.children) c.find?.(tag, out);
    return out;
  }
}
globalThis.document = {
  createElementNS: (_ns, tag) => new Node(tag),
  createElement: (tag) => new Node(tag),
  createTextNode: (t) => Object.assign(new Node("#text"), { _text: t }),
};
const { renderLines, renderTiers, renderSparkline, renderSmallMultiples } = await import(
  "../chart.js"
);

const labels = ["2018", "2019", "2020"];
const mk = (id, name, values, colour) => ({
  id, name, colour, points: values.map((value) => ({ value })),
});

test("renderLines builds an svg with one line path per series and an accessible name", () => {
  const el = new Node("div");
  renderLines(el, {
    labels,
    yTitle: "Mapped km",
    series: [mk("a", "<img onerror=x>", [1, 2, 3], "#111"), mk("b", "B", [3, 2, 1])],
  }, { height: 200 });
  const svg = el.children[0];
  assert.equal(svg.tag, "svg");
  assert.equal(svg.attrs["aria-label"], "Line chart: Mapped km");
  assert.equal(svg.find("title")[0].textContent, "Line chart: Mapped km");
  assert.equal(svg.find("path").filter((p) => p.attrs.class === "line").length, 2);
  const texts = svg.find("text").map((t) => t.textContent);
  assert.ok(texts.includes("<img onerror=x>"));
});

test("renderLines breaks the path at null and non-finite values and dots isolated points", () => {
  const el = new Node("div");
  renderLines(el, { labels: ["1", "2", "3", "4", "5"], series: [
    mk("a", "A", [1, null, 3, NaN, 5], "#111"),
  ] }, { height: 200 });
  const d = el.children[0].find("path")[0].attrs.d;
  assert.equal((d.match(/M/g) ?? []).length, 3);
  assert.ok(!d.includes("L"));
  assert.ok(el.children[0].find("circle").length >= 3);
});

test("renderLines shows an empty note when there are no finite values", () => {
  const el = new Node("div");
  renderLines(el, { labels, series: [mk("a", "A", [null, NaN, null])] });
  assert.equal(el.children[0].tag, "p");
});

test("renderTiers and renderSparkline carry accessible names", () => {
  const el = new Node("div");
  renderTiers(el, { labels, layers: [{ key: "A", name: "A", values: [1, 2, 3] }] });
  assert.ok(el.children[0].attrs["aria-label"]);
  const sp = new Node("span");
  renderSparkline(sp, labels.map((label, i) => ({ label, value: i })));
  assert.ok(sp.children[0].attrs["aria-label"]);
});

test("renderLines uses a series' short name when the full end label would be cut", () => {
  const el = new Node("div");
  const s = (id, name, short, v) => ({ ...mk(id, name, v, "#111"), short });
  renderLines(el, { labels, series: [
    s("lau", "City proper (LAU)", "City proper", [1, 2, 3]),
    s("fua", "Metro area (FUA)", "Metro area", [3, 2, 1]),
  ] }, { height: 200, width: 320 });
  const ends = el.children[0].find("text").filter((t) => t.attrs.class === "el").map((t) => t.textContent);
  assert.deepEqual(ends.sort(), ["City proper", "Metro area"]);
  const wide = new Node("div");
  renderLines(wide, { labels, series: [s("lau", "City proper (LAU)", "City proper", [1, 2, 3])] },
    { height: 200, width: 900 });
  assert.ok(wide.children[0].find("text").some((t) => t.textContent === "City proper (LAU)"));
});

/** Every attribute value and text of a stub tree. */
const strings = (n, out = []) => {
  out.push(...Object.values(n.attrs ?? {}), n._text ?? "");
  for (const c of n.children ?? []) strings(c, out);
  return out;
};

test("renderSmallMultiples' shared y domain ignores NaN and Infinity", () => {
  const el = new Node("div");
  renderSmallMultiples(el, {
    labels,
    series: [mk("a", "A", [1, NaN, 3]), mk("b", "B", [2, Infinity, 4])],
  }, { shared: true });
  const all = strings(el);
  assert.ok(el.find("path").length >= 2);
  assert.ok(!all.some((v) => /NaN|Infinity/.test(v)), all.filter((v) => /NaN|Infinity/.test(v)));
});

test("renderTiers stacks a non-finite tier value as 0, never NaN", () => {
  const el = new Node("div");
  renderTiers(el, { labels, layers: [
    { key: "A", name: "A", values: [1, NaN, 3] },
    { key: "B", name: "B", values: [2, 2, Infinity] },
  ] });
  const all = strings(el);
  assert.ok(el.find("path").length === 2);
  assert.ok(!all.some((v) => /NaN|Infinity/.test(v)), all.filter((v) => /NaN|Infinity/.test(v)));
});
