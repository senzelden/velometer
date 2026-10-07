import { test } from "node:test";
import assert from "node:assert/strict";

// Minimal stub DOM for renderPlanChart (as chart.test.mjs): any innerHTML write is a failure.
class Node {
  constructor(tag) {
    this.tag = tag;
    this.attrs = {};
    this.children = [];
    this._text = "";
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
  set textContent(v) { this._text = String(v); }
  get textContent() { return this._text; }
  set innerHTML(_) { throw new Error("innerHTML must not be used"); }
  get clientWidth() { return 600; }
  find(pred, out = []) {
    if (pred(this)) out.push(this);
    for (const c of this.children) c.find?.(pred, out);
    return out;
  }
}
globalThis.document = {
  createElementNS: (_ns, tag) => new Node(tag),
  createElement: (tag) => new Node(tag),
};

const { planSeries, renderPlanChart, yDomain } = await import("../plan-chart.js");

const row = (year, value, doc, current, extra = {}) => ({
  year, value, doc, doc_type: "drucksache", doc_date: "2026-01-01",
  quantity: "implemented_in_year", current, suspect: false, note: null, ...extra,
});

test("planSeries: targets become sorted steps; a revision keeps current: false", () => {
  const s = planSeries(
    { 2023: 60, 2022: 40 },
    [row(2022, 14.4, "19/27049", true), row(2022, 15.0, "1064", false)],
    [],
    [],
  );
  assert.deepEqual(s.target, [{ year: 2022, value: 40 }, { year: 2023, value: 60 }]);
  assert.deepEqual(
    s.reported.map((r) => [r.year, r.value, r.doc, r.current]),
    [[2022, 15.0, "1064", false], [2022, 14.4, "19/27049", true]],
  );
});

test("planSeries: a suspect row stays a flagged revision, never dropped", () => {
  const s = planSeries({}, [
    row(2023, 5.1, "19/25987", true),
    row(2023, 55.1, "19/27049", false, { suspect: true, note: "stored as printed" }),
  ], [], []);
  const suspect = s.reported.find((r) => r.doc === "19/27049");
  assert.equal(suspect.current, false);
  assert.equal(suspect.suspect, true);
  assert.equal(suspect.note, "stored as printed");
});

test("planSeries: missing target (target_kind none) gives no target, reports stay", () => {
  for (const targets of [{}, null, undefined]) {
    const s = planSeries(targets, [row(2024, 3, "a", true)], [], []);
    assert.deepEqual(s.target, []);
    assert.equal(s.reported.length, 1);
  }
});

test("planSeries: only figures for the year are charted; cumulative and other quantities are not", () => {
  const s = planSeries({}, [
    row(2025, 8.6, "a", true),
    row(2025, 60, "a", true, { quantity: "implemented_cumulative" }),
    row(2025, 3, "a", true, { quantity: "under_construction" }),
  ], [], []);
  assert.deepEqual(s.reported.map((r) => r.value), [8.6]);
});

test("planSeries: empty overlay gives no mapped series; projects are sorted by year", () => {
  const s = planSeries({}, [], [], [{ year: 2024, km: 7.7 }, { year: 2022, km: 13.5 }]);
  assert.deepEqual(s.mapped, []);
  assert.deepEqual(s.projects, [{ year: 2022, value: 13.5 }, { year: 2024, value: 7.7 }]);
  assert.deepEqual(planSeries({}, [], null, null).mapped, []);
  assert.deepEqual(planSeries({}, [], null, null).projects, []);
});

test("planSeries: mapped is the change since 1 January of the base year, one point per snapshot", () => {
  const overlay = [
    { date: "2026-10-03", ab_km: 480.4 },
    { date: "2021-01-01", ab_km: 500 },
    { date: "2022-01-01", ab_km: 438.3 },
    { date: "2023-01-01", ab_km: 454.3 },
    { date: "2024-01-01", ab_km: 450.2 },
  ];
  const s = planSeries({}, [], overlay, [], { mappedFrom: 2022 });
  // 2021 lies before the baseline; the baseline itself is 0; the last point is the current snapshot
  assert.deepEqual(
    s.mapped.map((m) => [m.date, Math.round(m.value * 10) / 10]),
    [["2022-01-01", 0], ["2023-01-01", 16], ["2024-01-01", 11.9], ["2026-10-03", 42.1]],
  );
  assert.equal(s.mapped.at(-1).year, 2026);
  assert.ok(s.mapped.at(-1).at > 2026.7 && s.mapped.at(-1).at < 2026.8); // position in the year
});

test("planSeries: no baseline snapshot, no mapped series (never a change from another date)", () => {
  const overlay = [{ date: "2023-01-01", ab_km: 450 }, { date: "2024-01-01", ab_km: 460 }];
  assert.deepEqual(planSeries({}, [], overlay, [], { mappedFrom: 2022 }).mapped, []);
});

test("yDomain: a small negative value does not stretch the axis to a whole negative step", () => {
  const d = yDomain([-4.1, 250, 100]);
  assert.ok(d.lo < -4.1, "the negative value stays inside the plot");
  assert.ok(d.lo > -50, `lowest bound ${d.lo}`);
  assert.ok(Math.min(...d.ticks) > -50, `lowest tick ${Math.min(...d.ticks)}`);
  assert.ok(d.ticks.includes(0));
  assert.ok(d.hi >= 250);
  assert.ok(d.ticks.every((t) => t >= d.lo && t <= d.hi));
  // only non-negative values: the axis starts at 0
  assert.equal(yDomain([3, 40]).lo, 0);
  // only negative values still get a domain that holds them
  const neg = yDomain([-12, -3]);
  assert.ok(neg.lo <= -12 && neg.hi >= 0);
});

const svgOf = (el) => el.find((n) => n.tag === "svg")[0];
const marks = (el, cls) => el.find((n) => (n.attrs.class ?? "").split(" ").includes(cls));

test("renderPlanChart: current markers filled, revisions hollow, suspect marked, target steps", () => {
  const el = new Node("div");
  const s = planSeries(
    { 2022: 40, 2023: 60 },
    [
      row(2022, 14.4, "b", true),
      row(2022, 15.0, "a", false),
      row(2023, 55.1, "c", false, { suspect: true }),
    ],
    [],
    [],
  );
  renderPlanChart(el, s, { label: "Vorrangnetz", years: [2022, 2023], unit: "km" });
  assert.ok(svgOf(el));
  assert.equal(marks(el, "rep-current").length, 1);
  assert.equal(marks(el, "rep-revision").length, 2);
  assert.equal(marks(el, "rep-suspect").length, 1);
  assert.equal(marks(el, "target-step").length, 1);
});

test("renderPlanChart: the mapped series is a line labelled in mapped km, its last point dated", () => {
  const el = new Node("div");
  const overlay = [{ date: "2022-01-01", ab_km: 438.3 }, { date: "2026-10-03", ab_km: 480.4 }];
  const s = planSeries({ 2022: 40 }, [row(2022, 14.4, "b", true)], overlay, [], { mappedFrom: 2022 });
  renderPlanChart(el, s, { label: "Vorrangnetz", years: [2022, 2026], unit: "km" });
  assert.equal(marks(el, "mapped-line").length, 1);
  const titles = el.find((n) => n.tag === "title").map((n) => n.textContent);
  const mappedTitles = titles.filter((t) => t.startsWith("Mapped"));
  assert.equal(mappedTitles.length, 2);
  assert.ok(mappedTitles.every((t) => t.includes("mapped km")), mappedTitles.join(" | "));
  const texts = el.find((n) => n.tag === "text").map((n) => n.textContent);
  assert.ok(texts.some((t) => t.includes("2026-10-03")), "the last point is labelled with its date");
});

test("renderPlanChart: no target line for an item without a target", () => {
  const el = new Node("div");
  const s = planSeries({}, [row(2024, 3, "a", true)], [], []);
  renderPlanChart(el, s, { label: "Summe", years: [2024], unit: "km" });
  assert.equal(marks(el, "target-step").length, 0);
  assert.equal(marks(el, "rep-current").length, 1);
});

test("renderPlanChart: nothing to draw is a note, not an empty svg", () => {
  const el = new Node("div");
  renderPlanChart(el, planSeries({}, [], [], []), { label: "x", years: [], unit: "km" });
  assert.equal(svgOf(el), undefined);
  assert.equal(el.children.length, 1);
  assert.equal(el.children[0].tag, "p");
  assert.match(el.children[0].textContent, /no figures/i);
});
