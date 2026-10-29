import { test } from "node:test";
import assert from "node:assert/strict";
import "./strings-fixture.mjs";
import { DEFAULTS } from "../state.js";
import { buildModel } from "../compare-model.js";
import { readFileSync } from "node:fs";
import { counterLines, counterTip, countsChart } from "../counter-model.js";
import { repoFile } from "./repo.mjs";

// the English texts (js.counts.*) an English page shows
const AVG_DAILY = "index of average daily intensity (monthly values), not of counts";
const COUNTER_DATA = "Counter data";
const NO_COUNTERS = "no open counter data";
const NO_COUNTER_LINE = "no counter index line (an index value for one year only; see its Counts tab)";
const NOT_RECORDED = "not recorded";

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
      ber: { series: "counts", base_year: 2019, line: true, source: "Senate", licence: "dl-de-zero-2.0", points: pts({ 2017: 90, 2018: null, 2019: 100, 2020: 114.6, 2021: 0 }) },
      bcn: { series: "avg_daily_intensity", base_year: 2019, line: true, source: "Ajuntament", licence: "CC BY 4.0", points: pts({ 2019: 100, 2020: 91.8, 2022: 132.9 }) },
      mad: { series: "counts", base_year: 2020, line: false, points: pts({ 2019: null, 2020: 100, 2021: null }) },
    },
  },
};

const ATT_BER = `${COUNTER_DATA}, Berlin: Senate, licence dl-de-zero-2.0; index and totals computed by velometer`;
const ATT_BCN = `${COUNTER_DATA}, Barcelona: Ajuntament, licence CC BY 4.0; index and totals computed by velometer`;

test("every drawn city carries its counter data attribution; an undrawn city none (ADR 0008)", () => {
  const notes = counterLines(D, ["ber", "bcn", "mad"]).notes;
  assert.deepEqual(notes.filter((n) => n.startsWith(COUNTER_DATA)), [ATT_BER, ATT_BCN]);
  const bare = { ...D, counters: { ...D.counters, cities: { ber: { ...D.counters.cities.ber, source: null, licence: undefined } } } };
  assert.deepEqual(counterLines(bare, ["ber"]).notes, [`${COUNTER_DATA}, Berlin: source ${NOT_RECORDED}, licence ${NOT_RECORDED}; index and totals computed by velometer`]);
});

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
  assert.deepEqual(m.notes, [`Barcelona: ${AVG_DAILY}`, ATT_BER, ATT_BCN]);
});

test("no counter data and no index line are notes without values; Madrid draws nothing", () => {
  const m = counterLines(D, ["mad", "cph", "ber"]);
  assert.deepEqual(m.notes, [`Madrid: ${NO_COUNTER_LINE}`, `Copenhagen: ${NO_COUNTERS}`, ATT_BER]);
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
  assert.deepEqual(m.notes, [`Copenhagen: ${NO_COUNTERS}`, ATT_BER]);
});

test("Counts tab: counter index beside the A+B km index, both base year = 100", () => {
  const m = countsChart(D, "ber");
  assert.deepEqual(m.labels, ["2017", "2018", "2019", "2020", "2021"]);
  assert.deepEqual(m.series.map((s) => s.id), ["counter", "km"]);
  assert.deepEqual(m.series[0].points.map((p) => p.value), [90, null, 100, 114.6, 0]);
  assert.deepEqual(m.series[1].points.map((p) => r(p.value)), [null, 90, 100, 110, null]);
  assert.deepEqual(m.marks, [{ label: "2020", text: "COVID year" }]);
});

test("Counts tab: no index line (Madrid), no chart: the tab shows a note instead (counts.html)", () => {
  // M8-4: the tab mounts the chart only for a city with a line; a km line alone was unreachable
  assert.equal(countsChart(D, "mad"), null);
  assert.equal(countsChart(D, "cph"), null);
});

test("Compare's counter tooltip names the city's base year = 100 and, on its point, the COVID year", () => {
  // M8-14: the unit's "2019 = 100; 2020 is the COVID year", per point and per city
  assert.equal(counterTip(D, "ber", 114.6, "2020"), "Berlin · 2020: index 114.6 (2019 = 100; 2020 is the COVID year)");
  assert.equal(counterTip(D, "ber", 90, "2017"), "Berlin · 2017: index 90 (2019 = 100)");
  const mad = { ...D, counters: { ...D.counters, cities: { mad: { ...D.counters.cities.mad, line: true } } } };
  assert.equal(counterTip(mad, "mad", 100, "2020"), "Madrid · 2020: index 100 (2020 = 100; 2020 is the COVID year)");
});

test("Compare's counter tooltip names no base year a city does not have", () => {
  // review M3: a city without base_year printed "(undefined = 100)"
  const bare = { ...D, counters: { ...D.counters, cities: { ber: { ...D.counters.cities.ber, base_year: null } } } };
  assert.equal(counterTip(bare, "ber", 114.6, "2020"), "Berlin · 2020: index 114.6 (2020 is the COVID year)");
  assert.equal(counterTip(bare, "ber", 90, "2017"), "Berlin · 2017: index 90");
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

// ---- the cases table shared with the Python suite (tests/test_app_m8_counts.py) ----

const shared = JSON.parse(
  readFileSync(repoFile("tests/counter_cases.json"), "utf8"),
);

for (const c of shared.cases) {
  test(`shared counter case: ${c.name}`, () => {
    // a case's `counters` replaces those keys of the payload's
    const payload = { ...shared.payload, counters: { ...shared.payload.counters, ...c.counters } };
    const m = counterLines(payload, c.ids);
    const values = Object.fromEntries(m.series.map((s) => [s.id, s.points.map((p) => p.value)]));
    assert.deepEqual({ labels: m.labels, values, notes: m.notes, unit: m.unit }, c.expect);
  });
}
