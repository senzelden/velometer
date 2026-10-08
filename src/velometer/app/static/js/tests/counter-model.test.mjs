import { test } from "node:test";
import assert from "node:assert/strict";
import { DEFAULTS } from "../state.js";
import { buildModel } from "../compare-model.js";
import {
  AVG_DAILY, NO_COUNTERS, NO_COUNTER_LINE, counterLines, countsChart,
} from "../counter-model.js";

const r = (v) => (v == null ? v : +v.toFixed(6));
const pts = (o) => Object.entries(o).map(([year, idx]) => ({ year: Number(year), idx, sites: idx == null ? 0 : 5 }));
const km = (o) => [...Object.entries(o).map(([label, ab_km]) => ({ label, ab_km })), { label: "current", ab_km: 999 }];
const D = {
  cities: {
    ber: { name: "Berlin", population: 1 },
    bcn: { name: "Barcelona", population: 1 },
    mad: { name: "Madrid", population: 1 },
    cph: { name: "Copenhagen", population: 1 },
  },
  series: {
    "ber/lau": km({ 2018: 90, 2019: 100, 2020: 110 }),
    "mad/lau": km({ 2019: 40, 2020: 50, 2021: 55 }),
  },
  counters: {
    covid_year: 2020,
    cities: {
      ber: { series: "counts", base_year: 2019, line: true, points: pts({ 2017: 90, 2018: null, 2019: 100, 2020: 114.6, 2021: 0 }) },
      bcn: { series: "avg_daily_intensity", base_year: 2019, line: true, points: pts({ 2019: 100, 2020: 91.8, 2022: 132.9 }) },
      mad: { series: "counts", base_year: 2020, line: false, points: pts({ 2019: null, 2020: 100, 2021: null }) },
    },
  },
};

test("a year with idx = null is a gap (null), never 0; a stored 0 stays 0", () => {
  const m = counterLines(D, ["ber"]);
  assert.deepEqual(m.labels, ["2017", "2018", "2019", "2020", "2021"]);
  const v = m.series[0].points.map((p) => p.value);
  assert.deepEqual(v, [90, null, 100, 114.6, 0]);
  assert.strictEqual(v[1], null);
});

test("years between two cities' values are gaps, the axis spans every drawn city's years", () => {
  const m = counterLines(D, ["ber", "bcn"]);
  assert.deepEqual(m.labels, ["2017", "2018", "2019", "2020", "2021", "2022"]);
  assert.deepEqual(m.series[1].points.map((p) => p.value), [null, null, 100, 91.8, null, 132.9]);
  assert.deepEqual(m.notes, [`Barcelona: ${AVG_DAILY}`]);
});

test("no counter data and no index line are notes without values; Madrid draws nothing", () => {
  const m = counterLines(D, ["mad", "cph", "ber"]);
  assert.deepEqual(m.notes, [`Madrid: ${NO_COUNTER_LINE}`, `Copenhagen: ${NO_COUNTERS}`]);
  assert.ok(m.series[0].points.every((p) => p.value === null));
  assert.ok(m.series[1].points.every((p) => p.value === null));
  assert.deepEqual(counterLines(D, ["mad"]).labels, []);
});

test("the COVID year is marked when it is on the axis", () => {
  assert.deepEqual(counterLines(D, ["ber"]).marks, [{ label: "2020", text: "COVID year" }]);
  const early = { ...D, counters: { ...D.counters, cities: { x: { ...D.counters.cities.ber, points: pts({ 2017: 1, 2018: 2 }) } } } };
  assert.deepEqual(counterLines({ ...early, cities: { x: { name: "X" } } }, ["x"]).marks, []);
});

test("compare: m=counter_index is never rebased, whatever the mode and boundary", () => {
  const state = { ...DEFAULTS, c: ["ber", "cph"], m: "counter_index", mode: "index", b: "fua" };
  const m = buildModel(D, state);
  assert.ok(m.counter);
  assert.deepEqual(m.series[0].points.map((p) => p.value), [90, null, 100, 114.6, 0]);
  assert.deepEqual(m.notes, [`Copenhagen: ${NO_COUNTERS}`]);
});

test("Counts tab: counter index beside the A+B km index, both base year = 100", () => {
  const m = countsChart(D, "ber");
  assert.deepEqual(m.labels, ["2017", "2018", "2019", "2020", "2021"]);
  assert.deepEqual(m.series.map((s) => s.id), ["counter", "km"]);
  assert.deepEqual(m.series[0].points.map((p) => p.value), [90, null, 100, 114.6, 0]);
  assert.deepEqual(m.series[1].points.map((p) => r(p.value)), [null, 90, 100, 110, null]);
  assert.deepEqual(m.marks, [{ label: "2020", text: "COVID year" }]);
});

test("Counts tab without an index line (Madrid): the km line alone, rebased to its base year", () => {
  const m = countsChart(D, "mad");
  assert.equal(m.base, 2020);
  assert.deepEqual(m.series.map((s) => s.id), ["km"]);
  assert.deepEqual(m.series[0].points.map((p) => r(p.value)), [80, 100, 110]);
  assert.equal(countsChart(D, "cph"), null);
});

test("a city listed without open counter data gets its config note with the portals checked", () => {
  const note = "no open counter data found (portals checked: data.kk.dk)";
  const m = counterLines({ ...D, counters: { ...D.counters, none: { cph: note } } }, ["cph"]);
  assert.deepEqual(m.notes, [`Copenhagen: ${note}`]);
});

test("Counts tab end labels: each series has a short name that fits the narrow chart's margin", () => {
  // renderLines gives end labels at most 82 px at phone width (about 11 characters); the full
  // names ("Counts at counter sites", "A+B mapped km (1 Jan)") are in the key under the chart
  const m = countsChart(D, "ber", { counter: "Counts at counter sites", km: "A+B mapped km (1 Jan)" });
  assert.deepEqual(m.series.map((s) => s.short), ["Counts", "Mapped km"]);
  const avg = countsChart(D, "ber", { counterShort: "Intensity" });
  assert.equal(avg.series[0].short, "Intensity");
  for (const s of [...m.series, ...avg.series]) assert.ok(s.short.length <= 11, s.short);
});
