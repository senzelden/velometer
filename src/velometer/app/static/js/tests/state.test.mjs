import { test } from "node:test";
import assert from "node:assert/strict";
import { DEFAULTS, PILOT5, parseState, serializeState } from "../state.js";

const known = {
  cities: [...PILOT5, "amsterdam", "oslo", "madrid", "prague", "lyon", "warsaw", "krakow", "utrecht", "oslo2"],
  metrics: ["headline", "ab_km", "tier_a", "qecio"],
};

test("defaults: empty query gives DEFAULTS and serialises to nothing", () => {
  assert.deepEqual(parseState("", known), DEFAULTS);
  assert.equal(serializeState(DEFAULTS), "");
  assert.deepEqual(DEFAULTS.c, ["berlin", "paris", "vienna", "copenhagen", "wroclaw"]);
});

test("round trip for a non-default state", () => {
  const s = "c=berlin,oslo,paris&m=ab_km&b=fua&mode=index&view=rank&hl=oslo,berlin";
  const state = parseState(s, known);
  assert.deepEqual(state.hl, ["oslo", "berlin"]);
  assert.equal(serializeState(state), s);
  assert.equal(serializeState(parseState("?" + s, known)), s);
});

test("serialize omits defaults and uses a stable key order", () => {
  const state = { ...DEFAULTS, mode: "index", m: "ab_km" };
  assert.equal(serializeState(state), "m=ab_km&mode=index");
});

test("unknown city dropped", () => {
  assert.deepEqual(parseState("c=berlin,atlantis", known).c, ["berlin"]);
});

test("all cities unknown falls back to the default set", () => {
  assert.deepEqual(parseState("c=atlantis", known).c, DEFAULTS.c);
});

test("unknown metric falls back to the default", () => {
  assert.equal(parseState("m=nope", known).m, "headline");
});

test("unknown boundary, mode and view fall back to the defaults", () => {
  const s = parseState("b=xx&mode=yy&view=zz", known);
  assert.equal(s.b, "lau");
  assert.equal(s.mode, "abs");
  assert.equal(s.view, "lines");
});

test("hl outside c is dropped", () => {
  assert.deepEqual(parseState("c=berlin,paris&hl=berlin,oslo", known).hl, ["berlin"]);
});

test("hl is truncated to 8 and de-duplicated", () => {
  const c = known.cities.slice(0, 10);
  const s = parseState(`c=${c.join(",")}&hl=${c.join(",")},${c[0]}`, known);
  assert.deepEqual(s.hl, c.slice(0, 8));
});

test("mode=index is kept", () => {
  assert.equal(parseState("mode=index", known).mode, "index");
});

test("parseState never mutates DEFAULTS", () => {
  const s = parseState("", known);
  s.c.push("x");
  assert.equal(DEFAULTS.c.length, 5);
});

test("default metric is checked against known.metrics", () => {
  const k = { cities: known.cities, metrics: ["ab_km", "qecio"] };
  assert.equal(parseState("", k).m, "ab_km");
  assert.equal(parseState("m=qecio", k).m, "qecio");
});

// ---- the cases table shared with the Python suite (tests/test_compare.py) ----
import { readFileSync } from "node:fs";
import { QUICK_SETS, METRICS, droppedMetric } from "../state.js";
import { repoFile } from "./repo.mjs";

const shared = JSON.parse(
  readFileSync(repoFile("tests/compare_cases.json"), "utf8"),
);

for (const c of shared.cases) {
  test(`shared case: ${c.name}`, () => {
    const state = parseState(c.query, shared.known);
    assert.deepEqual(state, c.expect);
    assert.equal(droppedMetric(c.query, state), c.dropped_metric);
  });
}

test("the shared cases know exactly the page's metrics", () => {
  assert.deepEqual(shared.known.metrics, METRICS);
});

test("quick sets: all is every city, the others list ids", () => {
  assert.equal(QUICK_SETS.all, null);
  assert.deepEqual(QUICK_SETS.pilot5, PILOT5);
  for (const [key, ids] of Object.entries(QUICK_SETS)) {
    if (key !== "all") assert.ok(ids.length >= 2 && new Set(ids).size === ids.length, key);
  }
});

test("a repeated c round-trips as a comma list", () => {
  const state = parseState("c=berlin&c=oslo", known);
  assert.equal(serializeState(state), "c=berlin,oslo");
});
