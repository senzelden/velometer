import { test } from "node:test";
import assert from "node:assert/strict";
import "./strings-fixture.mjs";
import { announce } from "../live.js";
import { compareSummary, panelAnnouncement } from "../compare-model.js";
import { mount, releaser } from "../data.js";

const fakeDoc = () => {
  const live = { textContent: "" };
  return { live, doc: { getElementById: (id) => (id === "live" ? live : null) } };
};
const frames = () => {
  const queue = [];
  globalThis.requestAnimationFrame = (f) => queue.push(f);
  return () => queue.splice(0).forEach((f) => f());
};

test("announce clears #live and sets the text in the next frame, so a repeat is read again", () => {
  const run = frames();
  const { live, doc } = fakeDoc();
  live.textContent = "same";
  announce("same", doc);
  assert.equal(live.textContent, "");
  run();
  assert.equal(live.textContent, "same");
});

test("announce is a no-op without #live", () => {
  const run = frames();
  assert.doesNotThrow(() => announce("x", { getElementById: () => null }));
  run();
  assert.doesNotThrow(() => announce("x", undefined));
});

test("a later announcement wins over an earlier one still waiting for its frame", () => {
  const run = frames();
  const { live, doc } = fakeDoc();
  announce("first", doc);
  announce("second", doc);
  run();
  assert.equal(live.textContent, "second");
});

test("the compare summary names the count, the metric and the scale", () => {
  const metrics = { headline: { label: "Protected km per 100k" } };
  assert.equal(
    compareSummary({ c: ["a", "b", "c"], m: "headline", mode: "abs" }, metrics),
    "Showing 3 cities, Protected km per 100k, absolute values",
  );
  assert.equal(
    compareSummary({ c: ["a"], m: "headline", mode: "index" }, metrics),
    "Showing 1 city, Protected km per 100k, indexed to the first year = 100",
  );
});

test("panel announcements: loading, loaded, failed", () => {
  assert.equal(panelAnnouncement("loading", "Berlin"), "Loading Berlin…");
  assert.equal(panelAnnouncement("loaded", "Berlin"), "Berlin");
  assert.match(panelAnnouncement("failed", "Berlin"), /could not be loaded/);
});

test("a chart released with its panel no longer listens for theme changes", () => {
  const listeners = new Set();
  globalThis.matchMedia = () => ({
    addEventListener: (_, f) => listeners.add(f),
    removeEventListener: (_, f) => listeners.delete(f),
  });
  let draws = 0;
  const el = { clientWidth: 100, isConnected: true };
  const off = mount(el, () => draws++);
  assert.equal(listeners.size, 1);
  off();
  assert.equal(listeners.size, 0);
  delete globalThis.matchMedia;
});

test("a releaser runs every release once and forgets them", () => {
  const r = releaser();
  let n = 0;
  r.add(() => n++);
  r.add(() => n++);
  r.run();
  r.run();
  assert.equal(n, 2);
});

test("a theme change redraws a connected chart, and a disconnected one lets go instead", () => {
  const listeners = new Set();
  globalThis.matchMedia = () => ({
    addEventListener: (_, f) => listeners.add(f),
    removeEventListener: (_, f) => listeners.delete(f),
  });
  let draws = 0;
  const el = { clientWidth: 100, isConnected: true };
  mount(el, () => draws++);
  assert.equal(draws, 1);
  [...listeners].forEach((f) => f()); // the OS switches scheme
  assert.equal(draws, 2);
  el.isConnected = false; // its container was replaced
  [...listeners].forEach((f) => f());
  assert.equal(draws, 2);
  assert.equal(listeners.size, 0);
  delete globalThis.matchMedia;
});
