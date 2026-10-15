import { test } from "node:test";
import assert from "node:assert/strict";
import "./strings-fixture.mjs";

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

const { planSeries, renderPlanChart, yDomain, targetScale, OFFSCALE_FACTOR } = await import("../plan-chart.js");

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

test("renderPlanChart: a suspect note still in English is tagged lang=en on its tooltip", () => {
  const el = new Node("div");
  const s = planSeries({ 2023: 40 }, [
    row(2023, 5.1, "a", true),
    row(2023, 55.1, "b", false, { suspect: true, note: "stored as printed", note_fallback: true }),
    row(2023, 56.1, "c", false, { suspect: true, note: "wie gedruckt", note_fallback: false }),
  ], [], []);
  renderPlanChart(el, s, { label: "Vorrangnetz", years: [2022, 2023, 2024], unit: "km" });
  const titles = el.find((n) => n.tag === "title");
  const tagged = titles.filter((n) => n.attrs.lang === "en");
  assert.equal(tagged.length, 1);
  assert.ok(tagged[0].textContent.includes("stored as printed"));
  assert.equal(tagged[0].attrs["data-fallback"], "");
  assert.ok(titles.filter((n) => n.attrs.lang === undefined).length >= 2);
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

test("renderPlanChart: the date label of the last snapshot never sits on a target step", () => {
  // render check, Task 11: at 390 px the Ergänzungsnetz label "2026-10-03" (right-aligned left of
  // the point) ran across the 2025 target step just above the point. Narrow chart, the same shape:
  // a low target in the band left of the last snapshot, the snapshot late in its year
  const el = new Node("div");
  const overlay = [
    { date: "2022-01-01", ab_km: 100 }, { date: "2025-01-01", ab_km: 104 },
    { date: "2026-10-03", ab_km: 113.7 },
  ];
  const targets = { 2025: 50, 2026: 100, 2027: 100, 2028: 350, 2029: 450, 2030: 450 };
  const s = planSeries(targets, [row(2022, 10, "b", true)], overlay, [], { mappedFrom: 2022 });
  const years = [2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030];
  renderPlanChart(el, s, { label: "Ergänzungsnetz", years, unit: "km", width: 358 });
  const label = el.find((n) => n.attrs.class === "mapped-label")[0];
  const w = label.textContent.length * 6.2; // 10px labels: chart-core's textWidth
  const lx = Number(label.attrs.x);
  const [x1, x2] = label.attrs["text-anchor"] === "end" ? [lx - w, lx] : [lx, lx + w];
  const [y2, y1] = [Number(label.attrs.y) + 2, Number(label.attrs.y) - 9]; // baseline to cap height
  // the steps on the scale and the caps of those above it (Task 4 of the follow-ups)
  const d = el.find((n) => ["target-step", "target-cap"].includes(n.attrs.class)).map((n) => n.attrs.d).join("");
  assert.ok(d, "the targets are drawn");
  for (const [, sx, sy, ex] of d.matchAll(/M([\d.]+),([\d.]+)H([\d.]+)/g).map((m) => m.map(Number))) {
    const crosses = sx < x2 && ex > x1 && sy >= y1 && sy <= y2;
    assert.ok(!crosses, `label [${x1}..${x2}]x[${y1}..${y2}] crosses the step at y=${sy} [${sx}..${ex}]`);
  }
  // inside the plot, as labelSpot places it (M8-17: the test had been relaxed to the svg)
  const grid = marks(el, "gridl");
  const [left, right] = [Number(grid[0].attrs.x1), Number(grid[0].attrs.x2)];
  const top = Math.min(...grid.map((n) => Number(n.attrs.y1)));
  const bottom = Number(svgOf(el).attrs.height) - 26;
  assert.ok(x1 >= left && x2 <= right && y1 >= top && y2 <= bottom, `label [${x1}..${x2}]x[${y1}..${y2}]`);
});

test("renderPlanChart: the date label keeps off the cap lines; cap labels never overlap", () => {
  // M8-17: labelSpot was given the on-scale steps only, and adjacent caps' values were untested
  const boxes = (el, cls) =>
    marks(el, cls).map((n) => {
      const w = n.textContent.length * 6.2;
      const x = Number(n.attrs.x);
      const anchor = n.attrs["text-anchor"];
      const [x1, x2] = anchor === "end" ? [x - w, x] : anchor === "middle" ? [x - w / 2, x + w / 2] : [x, x + w];
      return { x1, x2, y1: Number(n.attrs.y) - 9, y2: Number(n.attrs.y) + 2 };
    });
  for (const width of [640, 358, 280]) {
    // the last snapshot high in a band whose target is capped: the label's first spot is the cap
    const el = new Node("div");
    const overlay = [{ date: "2022-01-01", ab_km: 100 }, { date: "2026-10-03", ab_km: 160 }];
    const targets = { 2025: 50, 2026: 900, 2027: 900, 2028: 1200, 2029: 1200, 2030: 1200, 2031: 1500 };
    const s = planSeries(targets, [row(2022, 10, "b", true), row(2026, 60, "c", true)], overlay, [], { mappedFrom: 2022 });
    const years = Array.from({ length: 10 }, (_, i) => 2022 + i);
    renderPlanChart(el, s, { years, unit: "km", width });
    assert.equal(marks(el, "target-cap").length, 6, "a cap per off-scale target");
    const caps = boxes(el, "target-cap-label");
    assert.ok(caps.length >= 3, "cap values labelled");
    caps.slice(1).forEach((c, i) => assert.ok(c.x1 >= caps[i].x2, `cap labels overlap at ${width}`));
    const [label] = boxes(el, "mapped-label");
    const capYs = marks(el, "target-cap").map((n) => [...n.attrs.d.matchAll(/M([\d.]+),([\d.]+)H([\d.]+)/g)].map((m) => m.slice(1).map(Number))).flat();
    for (const [sx, sy, ex] of capYs) {
      const crosses = sx < label.x2 && ex > label.x1 && sy >= label.y1 && sy <= label.y2;
      assert.ok(!crosses, `${width}: the date label crosses the cap at y=${sy}`);
    }
  }
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

// ---------- Task 4 (M8 follow-ups): axis by quantity, off-scale targets, labels inside ----------

const texts = (el) => el.find((n) => n.tag === "text");
const ylabText = (el) => texts(el).filter((n) => n.attrs.class === "ylab").map((n) => n.textContent).join(" ");

test("renderPlanChart: the y label follows the target quantity", () => {
  const cases = [
    ["km_per_year", "km per year"],
    ["none", "km per year"],
    ["km_cumulative", "km, cumulative"],
    ["km_total", "km, total"],
  ];
  for (const [quantity, label] of cases) {
    // a target alone: its own quantity is the axis
    const el = new Node("div");
    renderPlanChart(el, planSeries({ 2025: 100, 2030: 400 }, [], [], []), { years: [2025, 2030], unit: "km", quantity });
    assert.ok(ylabText(el).startsWith(label), `${quantity}: ${ylabText(el)}`);
  }
});

test("renderPlanChart: a cumulative or total target is never drawn on the per-year axis", () => {
  // the simpler of the two rulings: the chart draws the per-year figures and leaves the target
  // out (a note says so; the table lists it), never both quantities against one axis
  for (const quantity of ["km_cumulative", "km_total"]) {
    const el = new Node("div");
    const s = planSeries({ 2030: 400 }, [row(2024, 12, "a", true)], [], []);
    renderPlanChart(el, s, { years: [2024, 2030], unit: "km", quantity });
    assert.equal(marks(el, "target-step").length, 0, quantity);
    assert.equal(marks(el, "target-cap").length, 0, quantity);
    assert.ok(ylabText(el).startsWith("km per year"), ylabText(el));
    const note = el.children.find((c) => c.tag === "p");
    assert.ok(note && /not drawn/.test(note.textContent) && /table/.test(note.textContent), quantity);
  }
});

test("targetScale: a target above OFFSCALE_FACTOR x the largest figure is off scale", () => {
  assert.equal(OFFSCALE_FACTOR, 3);
  const steps = [50, 100, 350, 450].map((value, i) => ({ year: 2025 + i, value }));
  const { onScale, offScale } = targetScale(steps, [10, 55.1, -2]);
  assert.deepEqual(onScale.map((p) => p.value), [50, 100]);
  assert.deepEqual(offScale.map((p) => p.value), [350, 450]);
  // at exactly the factor a target stays on scale
  assert.equal(targetScale([{ year: 2025, value: 30 }], [10]).offScale.length, 0);
  // no figures (or none above 0): every target is on scale, the targets set the axis
  assert.equal(targetScale(steps, []).offScale.length, 0);
  assert.equal(targetScale(steps, [0, -3]).offScale.length, 0);
});

// the Berlin Ergänzungsnetz shape (controller observation 2026-10-08): 2028-2030 targets of
// 350-450 km per year flattened the figures near 0
const ERG_TARGETS = { 2025: 50, 2026: 100, 2027: 100, 2028: 350, 2029: 450, 2030: 450 };
const ERG_OVERLAY = [
  { date: "2022-01-01", ab_km: 606.4 }, { date: "2025-01-01", ab_km: 610 },
  { date: "2026-10-03", ab_km: 620.2 },
];
const ergChart = (width) => {
  const el = new Node("div");
  // as on the page: 2023 has a current 5.1 and a suspect revision of 55.1, a figure too
  const reports = [
    row(2023, 5.1, "a", true), row(2023, 55.1, "c", false, { suspect: true }), row(2025, 20.3, "b", true),
  ];
  const s = planSeries(ERG_TARGETS, reports, ERG_OVERLAY,
    [{ year: 2023, km: 1.2 }], { mappedFrom: 2022 });
  const years = [2022, 2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030];
  renderPlanChart(el, s, { label: "Ergänzungsnetz", years, unit: "km", quantity: "km_per_year", width });
  return el;
};

test("renderPlanChart: off-scale targets are capped at the top edge, labelled, the axis set by the data", () => {
  for (const width of [640, 358]) {
    const el = ergChart(width);
    const caps = marks(el, "target-cap");
    assert.equal(caps.length, 3, "one cap per off-scale target (2028, 2029, 2030)");
    const labels = marks(el, "target-cap-label").map((n) => n.textContent);
    assert.deepEqual(labels, ["↑ 350", "↑ 450", "↑ 450"]);
    // the cap sits on the plot's top edge: the highest gridline
    const gridYs = marks(el, "gridl").map((n) => Number(n.attrs.y1));
    const top = Math.min(...gridYs);
    for (const c of caps) {
      for (const [, , y] of c.attrs.d.matchAll(/M([\d.]+),([\d.]+)/g)) assert.equal(Number(y), top);
    }
    // the axis is the data's and the nearer targets': its top tick is far below 350
    const ticks = texts(el).filter((n) => n.attrs.class === "axis-t" && n.attrs["text-anchor"] === "end");
    const hi = Math.max(...ticks.map((n) => Number(n.textContent.replace(",", ""))));
    assert.ok(hi >= 100 && hi < 350, `top tick ${hi}`);
    // the on-scale steps exclude the off-scale years
    const d = marks(el, "target-step")[0].attrs.d;
    assert.equal([...d.matchAll(/M/g)].length, 3, d);
  }
});

test("renderPlanChart: no figures, no off-scale: the targets set the axis", () => {
  const el = new Node("div");
  renderPlanChart(el, planSeries(ERG_TARGETS, [], [], []), { years: [2025, 2030], unit: "km" });
  assert.equal(marks(el, "target-cap").length, 0);
});

test("renderPlanChart: every label fits inside the svg, at any width and scale", () => {
  // the rule the margins exist for: tick labels, the y label, year labels, the date label and
  // the off-scale caps all lie inside [0, width] x [0, height] (10-11 px text: about 6.2 px/char)
  const charts = [
    ergChart(640),
    ergChart(358),
    ergChart(280),
    (() => {
      const el = new Node("div");
      const s = planSeries({ 2022: 12000, 2023: 9000 }, [row(2022, -4200, "a", true), row(2023, 11500, "b", true)], [], []);
      renderPlanChart(el, s, { years: [2022, 2023], unit: "km", quantity: "km_cumulative", width: 280 });
      return el;
    })(),
  ];
  for (const el of charts) {
    const svg = svgOf(el);
    const [W, H] = [Number(svg.attrs.width), Number(svg.attrs.height)];
    for (const t of texts(el)) {
      const w = t.textContent.length * 6.2;
      const x = Number(t.attrs.x);
      const anchor = t.attrs["text-anchor"] ?? "start";
      const [x1, x2] = anchor === "end" ? [x - w, x] : anchor === "middle" ? [x - w / 2, x + w / 2] : [x, x + w];
      const y = Number(t.attrs.y);
      assert.ok(x1 >= 0 && x2 <= W, `W=${W}: "${t.textContent}" spans [${x1.toFixed(1)}, ${x2.toFixed(1)}]`);
      assert.ok(y - 9 >= 0 && y + 2 <= H, `H=${H}: "${t.textContent}" at y=${y}`);
    }
  }
});

test("yDomain with headroom: the top tick lies at least one step above the largest value", () => {
  for (const values of [[50, 100, 100, 55.1], [20], [3, 40], [-4.1, 250], [0.7, 1]]) {
    const d = yDomain(values, 5, { headroom: true });
    const step = d.ticks[1] - d.ticks[0];
    assert.ok(d.hi - Math.max(...values) >= step - 1e-9, `${values}: hi ${d.hi}, step ${step}`);
    assert.equal(d.hi, d.ticks.at(-1));
  }
  // without it, the top tick may be the largest value itself
  assert.equal(yDomain([50, 100]).hi, 100);
});

test("renderPlanChart: with caps on the top edge, no on-scale target or figure lies on the cap line", () => {
  // the Ergänzungsnetz 2026-2027 targets of 100 km were the domain top: their steps were drawn
  // on the line of the 2028-2030 caps. With caps the axis keeps a tick step of headroom
  for (const width of [640, 358]) {
    const el = ergChart(width);
    const capY = Number(marks(el, "target-cap")[0].attrs.d.match(/M[\d.]+,([\d.]+)/)[1]);
    const gridYs = [...new Set(marks(el, "gridl").map((n) => Number(n.attrs.y1)))].sort((a, b) => a - b);
    const gap = gridYs[1] - gridYs[0];
    const stepYs = [...marks(el, "target-step")[0].attrs.d.matchAll(/M[\d.]+,([\d.]+)/g)].map((m) => Number(m[1]));
    const figureYs = [...marks(el, "rep"), ...marks(el, "mapped-pt")].map((n) => Number(n.attrs.cy));
    for (const yy of [...stepYs, ...figureYs]) assert.ok(yy >= capY + gap - 0.5, `y ${yy}, cap ${capY}, gap ${gap}`);
  }
});

test("renderPlanChart: a target at or below the axis top is drawn on the scale, never as a cap", () => {
  // review finding: 290 is on scale and 310 off (> 3 x 100); headroom lifts the top from 300
  // to 400, so 310 lies inside the scale. The rule: caps only for targets above the final top
  for (const width of [640, 358]) {
    const el = new Node("div");
    const s = planSeries({ 2024: 290, 2025: 310 }, [row(2024, 100, "a", true)], [], []);
    renderPlanChart(el, s, { years: [2024, 2025], unit: "km", quantity: "km_per_year", width });
    const ticks = texts(el).filter((n) => n.attrs.class === "axis-t" && n.attrs["text-anchor"] === "end");
    const top = Math.max(...ticks.map((n) => Number(n.textContent.replace(",", ""))));
    const caps = marks(el, "target-cap-label").map((n) => Number(n.textContent.replace(/[^\d.]/g, "")));
    assert.ok(caps.every((v) => v > top), `caps ${caps} at or below the top tick ${top}`);
    const steps = [...(marks(el, "target-step")[0]?.attrs.d ?? "").matchAll(/M/g)].length;
    assert.equal(steps + caps.length, 2, "every target drawn once, as a step or a cap");
  }
});

// ---------- M13 Task 8 (M8-2): the mapped line has its own labelled axis ----------

const tickTexts = (el, anchor) =>
  texts(el).filter((n) => n.attrs.class?.split(" ").includes("axis-t") && n.attrs["text-anchor"] === anchor);
const tickY = (n) => Number(n.attrs.y) - 3.5;

const mappedChart = (overlay, reports, width = 640) => {
  const el = new Node("div");
  const s = planSeries({ 2022: 40, 2023: 60 }, reports, overlay, [], { mappedFrom: 2022 });
  renderPlanChart(el, s, { label: "Vorrangnetz", years: [2022, 2023, 2024], unit: "km", width });
  return el;
};

test("renderPlanChart: the cumulative mapped line is read on its own right axis, not the per-year axis", () => {
  // the mapped change (a cumulative quantity) ten times the per-year figures: it must not set the
  // per-year axis, and its points must be readable against a labelled axis of their own
  const overlay = [
    { date: "2022-01-01", ab_km: 400 }, { date: "2023-01-01", ab_km: 600 },
    { date: "2024-07-01", ab_km: 820 },
  ];
  for (const width of [640, 358]) {
    const el = mappedChart(overlay, [row(2022, 14.4, "a", true), row(2023, 13.6, "b", true)], width);
    const left = tickTexts(el, "end").map((n) => Number(n.textContent.replace(",", "")));
    assert.ok(Math.max(...left) <= 60, `per-year axis top ${Math.max(...left)}: set by the targets and figures`);
    const right = tickTexts(el, "start").filter((n) => n.attrs.class.includes("axis-r"));
    assert.ok(right.length >= 3, "the right axis has tick labels");
    const svg = svgOf(el);
    const plotRight = Math.max(...marks(el, "gridl").map((n) => Number(n.attrs.x2)));
    assert.ok(right.every((n) => Number(n.attrs.x) > plotRight), "right tick labels sit right of the plot");
    // each mapped point lies where the right axis says its value is
    const [a, b] = [right[0], right.at(-1)].map((n) => [Number(n.textContent.replace(",", "")), tickY(n)]);
    const at = (v) => a[1] + ((v - a[0]) / (b[0] - a[0])) * (b[1] - a[1]);
    const pts = marks(el, "mapped-pt");
    const values = [0, 200, 420];
    pts.forEach((p, i) => assert.ok(Math.abs(Number(p.attrs.cy) - at(values[i])) < 0.6, `point ${i}`));
    const gridYs = marks(el, "gridl").map((n) => Number(n.attrs.y1));
    for (const p of pts) {
      const cy = Number(p.attrs.cy);
      assert.ok(cy >= Math.min(...gridYs) - 0.5 && cy <= Math.max(...gridYs) + 0.5, `point at ${cy} inside the plot`);
    }
    // the right axis is labelled as the line's
    const ylab = texts(el).filter((n) => n.attrs.class === "ylab");
    const rlab = ylab.find((n) => n.textContent.includes("mapped km since 1 Jan 2022"));
    assert.ok(rlab && rlab.attrs["text-anchor"] === "end", ylab.map((n) => n.textContent).join(" | "));
    assert.ok(!ylab.some((n) => n.textContent.includes("per year") && n.textContent.includes("mapped")),
      "the per-year label does not claim the line");
    assert.ok(Number(rlab.attrs.x) <= Number(svg.attrs.width));
  }
});

test("renderPlanChart: the two axes share their zero line", () => {
  // a mapped change below zero: both axes keep 0 on the same gridline, so bars and the line
  // start from one baseline
  const overlay = [
    { date: "2022-01-01", ab_km: 400 }, { date: "2023-01-01", ab_km: 380 },
    { date: "2024-01-01", ab_km: 520 },
  ];
  const el = mappedChart(overlay, [row(2022, 14.4, "a", true)]);
  const zeroL = tickTexts(el, "end").find((n) => n.textContent === "0");
  const zeroR = tickTexts(el, "start").find((n) => n.attrs.class.includes("axis-r") && n.textContent === "0");
  assert.ok(zeroL && zeroR, "both axes label 0");
  assert.ok(Math.abs(tickY(zeroL) - tickY(zeroR)) < 0.01, `${tickY(zeroL)} vs ${tickY(zeroR)}`);
  const low = marks(el, "mapped-pt")[1];
  assert.ok(Number(low.attrs.cy) > tickY(zeroR), "the negative change lies below the zero line");
  const svg = svgOf(el);
  assert.ok(Number(low.attrs.cy) <= Number(svg.attrs.height) - 26, "and inside the plot");
});

test("renderPlanChart: a share target's axis and note name the share in its unit, never \"%, share\"", () => {
  // M8-24: the unit-then-quantity pattern reads "%, share" for a share target
  const alone = new Node("div");
  renderPlanChart(alone, planSeries({ 2025: 20, 2030: 30 }, [], [], []), { years: [2025, 2030], unit: "%", quantity: "share" });
  assert.equal(ylabText(alone), "share in %");
  const drawn = new Node("div");
  renderPlanChart(drawn, planSeries({ 2030: 30 }, [row(2024, 12, "a", true)], [], []), { years: [2024, 2030], unit: "%", quantity: "share" });
  const note = drawn.children.find((c) => c.tag === "p").textContent;
  assert.ok(note.includes("(share in %)") && !note.includes("%, share"), note);
});
