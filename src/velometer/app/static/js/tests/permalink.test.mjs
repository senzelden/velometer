import { test } from "node:test";
import assert from "node:assert/strict";
import { TIERMAP, currentAddress, read, setParam, stepFromHash, write } from "../permalink.js";
import { PILOT5, panelOf } from "../state.js";

const KINDS = ["lau", "fua"];
const FALLBACK = { kind: null, tiers: ["A", "B", "C", "D", "E"], at: null };
const loc = (pathname = "/city/berlin/tiers", hash = "") => ({ pathname, hash });

test("read gives the fallbacks for an empty query", () => {
  assert.deepEqual(read("", TIERMAP, KINDS), FALLBACK);
  assert.deepEqual(read("?", TIERMAP, KINDS), FALLBACK);
});

test("read and write round-trip every TIERMAP field", () => {
  const state = { kind: "fua", tiers: ["A", "B"], at: [52.52, 13.4, 12] };
  const href = write(state, TIERMAP, loc());
  assert.equal(href, "/city/berlin/tiers?kind=fua&tiers=AB&at=52.52000,13.40000,12");
  assert.deepEqual(read(href.split("?")[1], TIERMAP, KINDS), state);
  // no tier at all is a state too, and survives the trip
  const none = { ...state, tiers: [] };
  assert.deepEqual(read(write(none, TIERMAP, loc()).split("?")[1], TIERMAP, KINDS), none);
});

test("bad values fall back, one by one, and never throw", () => {
  assert.deepEqual(read("?kind=nope&tiers=XYZ&at=NaN,1,5", TIERMAP, KINDS), FALLBACK);
  const bad = [
    "kind=__proto__", "kind=%E0%A4%A", "tiers=ABCDEF", "tiers=a", "tiers=%00", "at=1,2",
    "at=1,2,3,4", "at=,,", "at=52,,10", "at=0x10,1,5", "at=1e1,1,5", "at=Infinity,1,5",
    "at=52.5,13.4,2", "at=52.5,13.4,20", "at=91,0,10", "at=0,181,10", "at=<script>",
  ];
  for (const q of bad) assert.deepEqual(read(q, TIERMAP, KINDS), FALLBACK, q);
});

test("a zoom beyond the range gives the fallback (not a clamp)", () => {
  assert.equal(read("at=52.5,13.4,99", TIERMAP, KINDS).at, null);
  assert.deepEqual(read("at=52.5,13.4,12.4", TIERMAP, KINDS).at, [52.5, 13.4, 12]);
});

test("a good key survives a bad neighbour", () => {
  assert.deepEqual(read("kind=fua&tiers=XYZ", TIERMAP, KINDS), { ...FALLBACK, kind: "fua" });
  assert.deepEqual(read("tiers=AAB", TIERMAP, KINDS).tiers, ["A", "B"]);
});

test("unknown keys are ignored", () => {
  assert.deepEqual(read("utm=1&kind=lau", TIERMAP, KINDS), { ...FALLBACK, kind: "lau" });
});

test("write drops values equal to the fallback and keeps the hash", () => {
  assert.equal(write(FALLBACK, TIERMAP, loc("/x", "#map")), "/x#map");
  assert.equal(
    write({ ...FALLBACK, kind: "lau", tiers: ["A", "B", "C", "D", "E"] }, TIERMAP, loc("/x", "#a")),
    "/x?kind=lau#a",
  );
  assert.equal(write({ ...FALLBACK, tiers: ["C"] }, TIERMAP, loc("/x")), "/x?tiers=C");
});

test("write has a stable key order whatever the state's", () => {
  const state = { at: [1, 2, 5], tiers: ["A"], kind: "lau" };
  assert.match(write(state, TIERMAP, loc()), /\?kind=lau&tiers=A&at=/);
});

test("stepFromHash: a known step, else null", () => {
  const steps = ["a", "b"];
  assert.equal(stepFromHash("#step-b", steps), "b");
  assert.equal(stepFromHash("#step-gone", steps), null);
  assert.equal(stepFromHash("#b", steps), null);
  assert.equal(stepFromHash("", steps), null);
  assert.equal(stepFromHash("#step-%E0%A4%A", steps), null); // malformed escape: no throw
  assert.equal(stepFromHash("#step-__proto__", steps), null);
});

test("setParam adds, replaces and removes one key and leaves the rest as written", () => {
  assert.equal(setParam("?c=a,b&m=x", "panel", "paris"), "?c=a,b&m=x&panel=paris");
  assert.equal(setParam("?panel=oslo&c=a,b", "panel", "paris"), "?c=a,b&panel=paris");
  assert.equal(setParam("?c=a&panel=oslo", "panel", null), "?c=a");
  assert.equal(setParam("?panel=oslo", "panel", null), "");
  assert.equal(setParam("", "panel", "p q"), "?panel=p%20q");
});

test("compare: a panel query keeps the compare state and exposes the panel", () => {
  const known = { cities: [...PILOT5, "oslo"], metrics: ["headline"] };
  assert.equal(panelOf("?c=berlin,paris&panel=paris", known), "paris");
  assert.equal(panelOf("?panel=atlantis", known), null); // an unknown city is ignored
  assert.equal(panelOf("?panel=", known), null);
  assert.equal(panelOf("?panel=%E0%A4%A", known), null);
  assert.equal(panelOf("", known), null);
});

const doc = (content) => ({
  querySelector: (sel) =>
    sel === 'meta[name="velometer-base"]'
      ? { getAttribute: (n) => (n === "content" ? content : null) }
      : null,
});

test("currentAddress: origin + base + path without base + query + hash", () => {
  const l = {
    origin: "https://x.org", pathname: "/velometer/city/berlin/tiers",
    search: "?kind=fua&tiers=AB", hash: "#a",
  };
  assert.equal(
    currentAddress(l, doc("/velometer/")), "https://x.org/velometer/city/berlin/tiers?kind=fua&tiers=AB#a",
  );
  assert.equal(
    currentAddress({ ...l, pathname: "/city/berlin/tiers" }, doc("/")),
    "https://x.org/city/berlin/tiers?kind=fua&tiers=AB#a",
  );
});

test("readerMoves: a resize's moveend and the app's own fit are not the reader's; the next move is", async () => {
  const { readerMoves } = await import("../permalink.js");
  const moves = readerMoves();
  assert.equal(moves.moveend(true), false, "the app fitting the map");
  assert.equal(moves.moveend(false), true, "a drag or zoom");
  moves.resize(); // Leaflet's invalidateSize: moveend follows (200 ms later on a window resize)
  moves.resize();
  assert.equal(moves.moveend(false), false, "the moveend a resize sends");
  assert.equal(moves.moveend(false), true, "the reader's next move counts again");
});

test("stepMemory: the step in view writes #step-<id>, once; the first step of a bare page writes nothing", async () => {
  const { stepMemory } = await import("../permalink.js");
  const ids = ["intro", "jumps", "a b"];
  const bare = stepMemory(ids, "");
  assert.equal(bare.next("intro"), null, "the top of a page that came without a step");
  assert.equal(bare.next("jumps"), "#step-jumps");
  assert.equal(bare.next("jumps"), null, "already written");
  assert.equal(bare.next("intro"), "#step-intro", "back to the first step once another was written");
  assert.equal(bare.next("a b"), "#step-a%20b");
  const linked = stepMemory(ids, "#step-jumps");
  assert.equal(linked.next("jumps"), null, "the permalink's own step is written already");
  assert.equal(linked.next("intro"), "#step-intro");
  const stale = stepMemory(ids, "#step-gone");
  assert.equal(stale.next("intro"), null, "an unknown step is no step");
});
