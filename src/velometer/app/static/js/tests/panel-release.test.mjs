import { test } from "node:test";
import assert from "node:assert/strict";

// A minimal page for panel.js: just enough DOM for show / hide, with an event log.
function setup({ throwOnSecond = false } = {}) {
  const log = [];
  const chart = { dataset: {} };
  const body = {
    replaceChildren: (...n) => log.push(`replace:${n[0]?.textContent ?? "fragment"}`),
    querySelector: () => ({ textContent: "Berlin" }),
    querySelectorAll: () => (throwOnSecond ? [chart, chart] : [chart]),
  };
  const closeBtn = { addEventListener() {}, focus() {} };
  const root = {
    hidden: true,
    append() {},
    setAttribute() {},
    contains: () => false,
    querySelectorAll: () => [],
    querySelector: (s) => (s === ".slideover-body" ? body : closeBtn),
  };
  globalThis.window = { matchMedia: () => ({ matches: false, addEventListener() {} }) };
  globalThis.document = {
    body: { append() {}, children: [], classList: { add() {}, remove() {} } },
    activeElement: null,
    querySelector: () => null,
    createElement: () => ({}),
    addEventListener() {},
  };
  globalThis.history = { state: null, replaceState() {}, pushState() {} };
  globalThis.location = { href: "http://x/" };
  globalThis.DOMParser = class { parseFromString() { return { body: { childNodes: [] } }; } };
  globalThis.fetch = async () => ({ ok: true, text: async () => "<p>x</p>" });
  let n = 0;
  const opts = {
    load: async () => ({}),
    draw: () => {
      const id = ++n;
      if (throwOnSecond && id === 2) throw new Error("draw failed");
      log.push(`draw:${id}`);
      return () => log.push(`release:${id}`);
    },
  };
  return { root, opts, log };
}

const loadPanel = async () => (await import("../panel.js")).createPanel;
const quiet = (t) => t.mock.method(console, "warn", () => {});

test("showing another city releases the previous panel's charts before replacing its body", async () => {
  const { root, opts, log } = setup();
  const panel = (await loadPanel())(root, opts);
  await panel.show("berlin");
  assert.deepEqual(log.filter((e) => e.startsWith("draw")), ["draw:1"]);
  log.length = 0;
  await panel.show("paris");
  assert.ok(log.indexOf("release:1") >= 0, log.join());
  assert.ok(log.indexOf("release:1") < log.indexOf("replace:Loading…"), log.join());
});

test("a failure after some charts were drawn releases them", async (t) => {
  quiet(t);
  const { root, opts, log } = setup({ throwOnSecond: true });
  const panel = (await loadPanel())(root, opts);
  await panel.show("berlin"); // chart 1 draws, chart 2 throws
  assert.ok(log.includes("draw:1") && log.includes("release:1"), log.join());
});

test("hiding the panel releases its charts", async () => {
  const { root, opts, log } = setup();
  const panel = (await loadPanel())(root, opts);
  await panel.show("berlin");
  log.length = 0;
  panel.hide();
  assert.deepEqual(log, ["release:1"]);
});

test("a frame that refuses history changes still opens and hides the panel", async () => {
  const { root, opts, log } = setup();
  const panel = (await loadPanel())(root, opts);
  const refuse = () => {
    throw new DOMException("history is not allowed here", "SecurityError");
  };
  globalThis.history = { state: null, replaceState: refuse, pushState: refuse, back() {} };
  globalThis.location = { href: "http://x/compare?panel=berlin", pathname: "/compare", search: "?panel=berlin", hash: "" };
  assert.doesNotThrow(() => panel.open("berlin"));
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(panel.isOpen, true);
  assert.ok(log.includes("draw:1"), log.join());
  assert.doesNotThrow(() => panel.hide());
  assert.equal(panel.isOpen, false);
});
