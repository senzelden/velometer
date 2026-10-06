import { test } from "node:test";
import assert from "node:assert/strict";
import { DEFAULTS } from "../state.js";
import {
  NO_INDEX, buildModel, colourPlan, colouredIds, metricValue, nextSort, rankSeries, sortRows,
} from "../compare-model.js";

const pt = (label, o = {}) => ({ label, headline: 10, ab_km: 50, C: 0, flags: "", ...o });
const D = {
  cities: {
    a: { name: "Aa", population: 100000 },
    b: { name: "Bb", population: null },
    z: { name: "Zero", population: 1 },
  },
  series: {
    "a/lau": [pt("2018", { headline: 10 }), pt("2019", { headline: 20, flags: "spike" }), pt("current", { headline: 30 })],
    "b/lau": [pt("2018", { headline: 40 }), pt("2019", { headline: 20 })],
    "z/lau": [pt("2018", { headline: 0 }), pt("2019", { headline: 5 })],
  },
};
const state = (o) => ({ ...DEFAULTS, c: ["a", "b", "z"], ...o });

test("metricValue: ab_per_100k divides by residents, and is null without them", () => {
  assert.equal(metricValue({ ab_km: 50 }, "ab_per_100k", 100000), 50);
  assert.equal(metricValue({ ab_km: 50 }, "ab_per_100k", null), null);
  assert.equal(metricValue({ C: 0 }, "C", 1), 0);
  assert.equal(metricValue({}, "headline", 1), null);
});

test("absolute model: raw labels, missing point is null, flags kept", () => {
  const m = buildModel(D, state({}));
  assert.deepEqual(m.labels, ["2018", "2019", "current"]);
  assert.deepEqual(m.series[1].points.map((p) => p.value), [40, 20, null]);
  assert.deepEqual(m.series[0].points[1].flags, ["spike"]);
  assert.deepEqual(m.notes, []);
});

test("index model: first year = 100; a zero first year gets the note and no values", () => {
  const m = buildModel(D, state({ mode: "index" }));
  assert.deepEqual(m.series[0].points.map((p) => p.value), [100, 200, 300]);
  assert.deepEqual(m.series[0].points[1].flags, ["spike"]);
  assert.ok(m.series[2].points.every((p) => p.value === null));
  assert.deepEqual(m.notes, [`Zero: ${NO_INDEX}`]);
});

test("unknown cities are skipped; b picks the boundary", () => {
  const m = buildModel(D, state({ c: ["a", "nowhere"], b: "fua" }));
  assert.deepEqual(m.series.map((s) => s.id), ["a"]);
  assert.deepEqual(m.labels, []);
});

test("coloured ids: highlighted ones, else the first eight selected", () => {
  const c = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"];
  assert.deepEqual(colouredIds({ c, hl: [] }), c.slice(0, 8));
  assert.deepEqual(colouredIds({ c, hl: ["j", "b"] }), ["j", "b"]);
});

test("colours stay with a city while the others change", () => {
  const first = colourPlan({ c: ["a", "b"], hl: [] }, {});
  const next = colourPlan({ c: ["b", "c"], hl: [] }, first);
  assert.equal(next.b, first.b);
  assert.notEqual(next.c, next.b);
});

test("ranks per label among the selected cities, ties share a rank", () => {
  const m = buildModel(D, state({ c: ["a", "b"] }));
  const r = rankSeries(m.series, m.labels);
  assert.deepEqual(r[0].points.map((p) => p.rank), [2, 1, 1]);
  assert.deepEqual(r[1].points.map((p) => p.rank), [1, 1, null]);
});

test("sortRows: by value descending, missing last, by name, and unsorted keeps the order", () => {
  const m = buildModel(D, state({}));
  assert.deepEqual(sortRows(m.series, m.labels, { key: "2018", dir: -1 }).map((r) => r.id), ["b", "a", "z"]);
  assert.deepEqual(sortRows(m.series, m.labels, { key: "current", dir: -1 }).map((r) => r.id), ["a", "b", "z"]);
  assert.deepEqual(sortRows(m.series, m.labels, { key: "current", dir: 1 }).map((r) => r.id), ["a", "b", "z"]);
  assert.deepEqual(sortRows(m.series, m.labels, { key: "name", dir: -1 }).map((r) => r.id), ["z", "b", "a"]);
  assert.deepEqual(sortRows(m.series, m.labels, null).map((r) => r.id), ["a", "b", "z"]);
});

test("nextSort toggles the direction of the same column", () => {
  assert.deepEqual(nextSort(null, "2018"), { key: "2018", dir: -1 });
  assert.deepEqual(nextSort({ key: "2018", dir: -1 }, "2018"), { key: "2018", dir: 1 });
  assert.deepEqual(nextSort({ key: "2018", dir: 1 }, "name"), { key: "name", dir: 1 });
});
