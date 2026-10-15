import { test } from "node:test";
import assert from "node:assert/strict";
import "./strings-fixture.mjs";

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
// the page's colour tokens, as a stylesheet would supply them: every chart here draws from them
const TOKENS = {
  ...Object.fromEntries(Array.from({ length: 8 }, (_, i) => [`--series-${i + 1}`, `#10${i}0${i}0`])),
  ...Object.fromEntries([..."abcde"].map((t, i) => [`--tier-${t}`, `#a${i}b${i}c0`])),
  "--axis": "#777777", "--ctx": "#999999", "--halo": "#ffffff",
};
globalThis.getComputedStyle = () => ({ getPropertyValue: (name) => TOKENS[name] ?? "" });
const consoleErrors = [];
console.error = (...a) => consoleErrors.push(a.join(" "));
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

test("more than 8 series: only the focus series get end labels, at any width; 8 or fewer: all", () => {
  const focus = [mk("a", "Focus A", [1, 2, 3], "#111"), mk("b", "Focus B", [3, 2, 1], "#222")];
  const grey = Array.from({ length: 8 }, (_, i) => mk(`g${i}`, `Context ${i}`, [i, i, i]));
  const ends = (series, width) => {
    const el = new Node("div");
    renderLines(el, { labels, series }, { height: 300, width });
    return el.children[0].find("text").filter((t) => t.attrs.class === "el").map((t) => t.textContent).sort();
  };
  for (const width of [400, 900, 1400]) {
    assert.deepEqual(ends([...focus, ...grey], width), ["Focus A", "Focus B"], `width ${width}`);
  }
  const few = [...focus, ...grey.slice(0, 6)];
  assert.equal(ends(few, 900).length, 8, "8 series: every line is labelled");
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

test("renderLines draws a mark at its label with its text, and skips a label not on the axis", () => {
  const el = new Node("div");
  renderLines(el, { labels, series: [mk("a", "A", [1, 2, 3], "#111")] },
    { height: 200, marks: [{ label: "2019", text: "COVID year" }, { label: "1999", text: "x" }] });
  const marks = el.children[0].find("g").filter((g) => g.attrs.class === "mark");
  assert.equal(marks.length, 1);
  assert.equal(marks[0].attrs["data-mark"], "2019");
  assert.ok(marks[0].find("text").some((t) => t.textContent === "COVID year"));
});

test("renderTiers keys every tier by name beside its colour, in the order they stack", () => {
  const el = new Node("div");
  const names = { A: "A separated track", B: "B shared path", C: "C lane" };
  renderTiers(el, { labels, layers: Object.entries(names).map(([key, name]) => (
    { key, name, values: [1, 2, 3] })) });
  const legend = el.children.find((c) => c.attrs.class === "legend" || c.className === "legend");
  assert.ok(legend, "a visible key under the chart");
  const text = (n) => (n._text ?? "") + (n.children ?? []).map(text).join("");
  assert.deepEqual(legend.children.map(text), Object.values(names).reverse());
  // the one HTML key form a download reads (download-ui.js keyOf): `.legend` > `.chip` > `<i>`
  assert.equal(legend.className, "legend");
  for (const chip of legend.children) {
    assert.equal(chip.className, "chip");
    assert.equal(chip.children[0].tag, "i");
    assert.match(chip.children[0].style.background, /^#/);
  }
});

test("a series without a colour is drawn in its slot's token, a tier in its tier's token", () => {
  const el = new Node("div");
  renderLines(el, { labels, series: [
    { id: "a", name: "A", slot: 0, points: [1, 2, 3].map((value) => ({ value })) },
    { id: "b", name: "B", slot: 1, points: [3, 2, 1].map((value) => ({ value })) },
  ] }, { height: 200 });
  const strokes = el.find("path").filter((p) => p.attrs.class === "line").map((p) => p.attrs.stroke);
  assert.deepEqual(strokes, [TOKENS["--series-1"], TOKENS["--series-2"]]);
  const t = new Node("div");
  renderTiers(t, { labels, layers: [
    { key: "A", name: "A", values: [1, 2, 3] }, { key: "B", name: "B", values: [2, 2, 2] },
  ] });
  const fills = t.find("path").map((p) => p.attrs.fill);
  assert.ok(fills.includes(TOKENS["--tier-a"]) && fills.includes(TOKENS["--tier-b"]), fills);
});

test("no chart drew from the missing-token fallback", () => {
  assert.deepEqual(consoleErrors, []);
});

// M10-7: a redraw (a resize, a theme switch) under a resting pointer keeps what it showed
const hitOf = (el) => el.children[0].find("rect").find((r) => r.attrs.class === "hit");
const hoverX = (el) => el.children[0].find("line").find((l) => l.attrs.class === "hover-x");
const tipOf = (el) => el.children.find((c) => c.className === "tip");
const firstPoint = (el, i) => {
  const d = el.children[0].find("path").filter((p) => p.attrs.class === "line")[i].attrs.d;
  const [x, y] = d.slice(1).split(/[L ]/)[0].split(",").map(Number);
  return { clientX: x, clientY: y };
};

test("renderLines: a redraw keeps the hovered series and point, until the pointer leaves", () => {
  const el = new Node("div");
  const model = { labels, series: [mk("a", "A", [1, 2, 3], "#111"), mk("b", "B", [9, 8, 7], "#222")] };
  renderLines(el, model, { height: 200 });
  hitOf(el).listeners.pointermove(firstPoint(el, 1));
  const shown = tipOf(el).textContent;
  assert.match(shown, /^B · 2018/);
  renderLines(el, model, { height: 200 });
  assert.equal(hoverX(el).attrs.visibility, "visible");
  assert.equal(tipOf(el).hidden, false);
  assert.equal(tipOf(el).textContent, shown);
  hitOf(el).listeners.pointerleave();
  renderLines(el, model, { height: 200 });
  assert.equal(hoverX(el).attrs.visibility, "hidden");
  assert.equal(tipOf(el).hidden, true);
  // a redraw without the hovered series shows nothing
  hitOf(el).listeners.pointermove(firstPoint(el, 1));
  renderLines(el, { labels, series: [model.series[0]] }, { height: 200 });
  assert.equal(tipOf(el).hidden, true);
});

test("renderTiers: a redraw keeps the hovered year", () => {
  const el = new Node("div");
  const model = { labels, layers: [{ key: "a", name: "A", values: [1, 2, 3] }] };
  renderTiers(el, model, { width: 600 });
  const svgOf = () => el.children[0];
  const hit = svgOf().find("rect").find((r) => r.attrs.class === "hit");
  hit.listeners.pointermove({ clientX: 600 });
  const shown = tipOf(el).textContent;
  renderTiers(el, model, { width: 600 });
  assert.equal(tipOf(el).hidden, false);
  assert.equal(tipOf(el).textContent, shown);
});
