import { test } from "node:test";
import assert from "node:assert/strict";
import {
  scaleLinear,
  niceTicks,
  indexSeries,
  ranks,
  placeLabels,
  assignColours,
  xLabels,
  formatValue,
  tickIndices,
} from "../chart-core.js";

test("scaleLinear maps domain to range, including inverted ranges", () => {
  const s = scaleLinear([0, 10], [100, 0]);
  assert.equal(s(0), 100);
  assert.equal(s(10), 0);
  assert.equal(s(2.5), 75);
  assert.equal(scaleLinear([5, 5], [0, 10])(5), 0);
});

test("indexSeries: base 2018 = 100, missing base gives nulls", () => {
  assert.deepEqual(
    indexSeries([{ label: "2018", value: 50 }, { label: "2019", value: 75 }], "2018"),
    [{ label: "2018", value: 100 }, { label: "2019", value: 150 }],
  );
  assert.deepEqual(
    indexSeries([{ label: "2018", value: 0 }, { label: "2019", value: 5 }], "2018"),
    [{ label: "2018", value: null }, { label: "2019", value: null }],
  );
  assert.deepEqual(
    indexSeries([{ label: "2019", value: 5 }], "2018"),
    [{ label: "2019", value: null }],
  );
  assert.deepEqual(
    indexSeries([{ label: "2018", value: null }, { label: "2019", value: 5 }], "2018"),
    [{ label: "2018", value: null }, { label: "2019", value: null }],
  );
  // a missing year stays missing even when the base exists
  assert.deepEqual(
    indexSeries([{ label: "2018", value: 50 }, { label: "2019", value: null }], "2018"),
    [{ label: "2018", value: 100 }, { label: "2019", value: null }],
  );
});

test("ranks: ties share, nulls unranked", () => {
  assert.deepEqual(ranks({ a: 3, b: 5, c: 5, d: null }), { b: 1, c: 1, a: 3, d: null });
});

test("placeLabels keeps order and spacing within bounds", () => {
  const y = placeLabels([{ id: "a", y: 10 }, { id: "b", y: 11 }, { id: "c", y: 12 }], 10, 0, 100);
  assert.ok(y.b - y.a >= 10 && y.c - y.b >= 10 && y.a >= 0 && y.c <= 100);
});

test("placeLabels clamps at the bottom and keeps the sorted order", () => {
  const y = placeLabels([{ id: "a", y: 99 }, { id: "b", y: 100 }, { id: "c", y: 98 }], 10, 0, 100);
  assert.ok(y.c < y.a && y.a < y.b);
  assert.ok(y.a - y.c >= 10 && y.b - y.a >= 10 && y.b <= 100 && y.c >= 0);
});

test("placeLabels leaves well-spaced labels where they are", () => {
  assert.deepEqual(placeLabels([{ id: "a", y: 10 }, { id: "b", y: 50 }], 10, 0, 100), { a: 10, b: 50 });
});

test("assignColours keeps existing colours when one city leaves", () => {
  const p = ["#1", "#2", "#3"];
  const a = assignColours({}, ["x", "y", "z"], p);
  const b = assignColours(a, ["x", "z", "w"], p);
  assert.equal(b.x, a.x);
  assert.equal(b.z, a.z);
  assert.equal(b.w, a.y);
  assert.equal(b.y, undefined);
});

test("assignColours colours at most palette.length cities", () => {
  const out = assignColours({}, ["a", "b", "c", "d"], ["#1", "#2"]);
  assert.deepEqual(Object.keys(out), ["a", "b"]);
});

test("niceTicks covers the range", () => {
  const t = niceTicks(3, 97, 5);
  assert.ok(t[0] <= 3 && t.at(-1) >= 97);
  assert.deepEqual(niceTicks(0, 100, 5), [0, 20, 40, 60, 80, 100]);
  assert.ok(niceTicks(5, 5, 5).length >= 2);
});

test("xLabels turns current into the snapshot month", () => {
  assert.deepEqual(xLabels(["2018", "2025", "current"], "2026-10-03"), ["2018", "2025", "Oct 2026"]);
  assert.deepEqual(xLabels(["current"], new Date(Date.UTC(2027, 0, 5))), ["Jan 2027"]);
});

test("placeLabels compresses the gap when labels exceed the range", () => {
  const items = Array.from({ length: 21 }, (_, i) => ({ id: `c${i}`, y: 100 + (i % 3) }));
  const y = placeLabels(items, 12, 0, 200);
  const ys = items.map((it) => y[it.id]).sort((a, b) => a - b);
  for (let i = 1; i < ys.length; i++) assert.ok(ys[i] - ys[i - 1] >= 10 - 1e-9);
  assert.ok(Math.min(...ys) >= 0 && Math.max(...ys) <= 200);
});

test("niceTicks ignores non-finite input instead of returning garbage", () => {
  assert.deepEqual(niceTicks(NaN, 10), []);
  assert.deepEqual(niceTicks(0, Infinity), []);
});

test("formatValue is exact to one decimal and never abbreviates", () => {
  assert.equal(formatValue(12345.678), "12,345.7");
  assert.equal(formatValue(42), "42");
});

test("tickIndices keeps every label when they fit and always ends on the last", () => {
  const years = ["2018", "2019", "2020", "2021"];
  assert.deepEqual(tickIndices(years, 60), [0, 1, 2, 3]);
  assert.deepEqual(tickIndices([], 60), []);
});

test("tickIndices never lets the last year and the wide snapshot label collide", () => {
  const labels = ["2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026", "Oct 2026"];
  const idx = tickIndices(labels, 36);
  assert.equal(idx.at(-1), 9);
  assert.ok(!idx.includes(8), "2026 sits on top of Oct 2026");
  const w = (t) => t.length * 6.2;
  for (let k = 1; k < idx.length; k++) {
    assert.ok((idx[k] - idx[k - 1]) * 36 >= w(labels[idx[k]]) / 2 + w(labels[idx[k - 1]]) / 2);
  }
});

test("tickIndices thins to every other label at narrow widths, regularly", () => {
  const years = ["2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026"];
  assert.deepEqual(tickIndices(years, 24), [0, 2, 4, 6, 8]);
  assert.deepEqual(tickIndices(["a-long-label", "b-long-label"], 1), [1]);
});
