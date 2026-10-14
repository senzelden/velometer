import { test } from "node:test";
import assert from "node:assert/strict";
import "./strings-fixture.mjs";
import { DEFAULTS } from "../state.js";
import {
  buildModel, slotPlan, colouredIds, metricValue, nextSort, rankSeries, sortRows,
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
  assert.deepEqual(m.notes, ["Zero: no index: first year is 0 or missing"]);
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

test("colour slots stay with a city while the others change", () => {
  const first = slotPlan({ c: ["a", "b"], hl: [] }, {});
  const next = slotPlan({ c: ["b", "c"], hl: [] }, first);
  assert.equal(next.b, first.b);
  assert.notEqual(next.c, next.b);
});

test("a plan holds slot indices 0..7, never colours, and keeps a city's slot (Review Focus 2)", () => {
  const c = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"];
  const first = slotPlan({ c, hl: [] }, {});
  const all = Object.values(first);
  assert.equal(all.length, 8);
  for (const v of all) assert.ok(Number.isInteger(v) && v >= 0 && v <= 7, String(v));
  assert.equal(new Set(all).size, all.length);
  // a selection change: "a" and "c" leave, "h" is highlighted with "b"; both keep their slots
  const next = slotPlan({ c: c.filter((id) => id !== "a" && id !== "c"), hl: ["h", "b"] }, first);
  assert.deepEqual(next, { h: first.h, b: first.b });
  // the same plan again (a theme change redraws with the previous plan): nothing moves
  assert.deepEqual(slotPlan({ c, hl: ["h", "b"] }, next), next);
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

import { closeAction, openAction, orderCities, plainText, popPlan, queryOf } from "../compare-model.js";

test("openAction pushes once, then replaces; closeAction goes back only from a panel entry", () => {
  assert.equal(openAction(false), "push");
  assert.equal(openAction(true), "replace");
  assert.equal(closeAction({ panel: "berlin" }), "back");
  assert.equal(closeAction(null), "hide");
  assert.equal(closeAction({}), "hide");
});

test("popPlan: closing the panel after a view change keeps the page and rewrites the stale URL", () => {
  // the entry landed on is the pre-panel one (?view=table); the page shows ?view=rank
  const plan = popPlan({ popState: null, panelOpen: true, shownQuery: "view=rank", urlQuery: "view=table" });
  assert.deepEqual(plan, { panel: null, restore: "view=rank", rerender: false });
});

test("popPlan: an unchanged state needs no restore", () => {
  const plan = popPlan({ popState: null, panelOpen: true, shownQuery: "view=rank", urlQuery: "view=rank" });
  assert.deepEqual(plan, { panel: null, restore: null, rerender: false });
});

test("popPlan: Forward onto a panel entry opens it and fixes its URL", () => {
  const plan = popPlan({ popState: { panel: "paris" }, panelOpen: false, shownQuery: "m=ab_km", urlQuery: "" });
  assert.deepEqual(plan, { panel: "paris", restore: "m=ab_km", rerender: false });
});

test("popPlan: with no panel involved a different URL is re-read and redrawn", () => {
  assert.equal(popPlan({ popState: null, panelOpen: false, shownQuery: "", urlQuery: "m=A" }).rerender, true);
  assert.equal(popPlan({ popState: null, panelOpen: false, shownQuery: "m=A", urlQuery: "m=A" }).rerender, false);
});

test("queryOf normalises through parseState", () => {
  const known = { cities: ["berlin", "paris"], metrics: ["headline", "A"] };
  assert.equal(queryOf("?m=nope&c=berlin&c=atlantis&view=table", known), "c=berlin&view=table");
});

test("orderCities keeps the user's order and appends new cities", () => {
  assert.deepEqual(orderCities(["oslo", "berlin"], ["berlin", "paris", "oslo"]), ["oslo", "berlin", "paris"]);
  assert.deepEqual(orderCities([], ["a", "b"]), ["a", "b"]);
});

test("plainText strips Markdown markers", () => {
  assert.equal(plainText("**campaign** (re-mapping) of `highway=path` see [way 1](https://x.org/1)."),
    "campaign (re-mapping) of highway=path see way 1.");
  assert.equal(plainText("a *b* c and snake_case_name"), "a b c and snake_case_name");
});

test("plainText joins soft-wrapped lines but keeps paragraphs and list items", () => {
  assert.equal(plainText("only part of\nthe separate ways"), "only part of the separate ways");
  assert.equal(plainText("one\n\ntwo"), "one\n\ntwo");
  assert.equal(plainText("intro\n- a\n- b"), "intro\n- a\n- b");
});

test("a flag explanation still in English on a German page is marked lang=en data-fallback", async () => {
  const { flagParagraphs } = await import("../compare-model.js");
  const D = {
    explanations: { timeseries: { "b/lau/2022": "First **cause**.\n\nSecond.", "b/lau/2023": "Ursache." } },
    explanationFallback: new Set(["b/lau/2022"]),
  };
  const english = { lang: "en", "data-fallback": "" };
  assert.deepEqual(flagParagraphs(D, "b/lau/2022"), [
    { attrs: english, text: "First cause." },
    { attrs: english, text: "Second." },
  ]);
  assert.deepEqual(flagParagraphs(D, "b/lau/2023"), [{ attrs: {}, text: "Ursache." }]);
  assert.deepEqual(flagParagraphs(D, "b/lau/2024"), []);
  // an English page has no fallback set: nothing is marked
  assert.deepEqual(flagParagraphs({ explanations: D.explanations }, "b/lau/2022")[0].attrs, {});
});
