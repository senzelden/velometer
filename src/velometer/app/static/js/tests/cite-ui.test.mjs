import { test } from "node:test";
import assert from "node:assert/strict";
import "./strings-fixture.mjs";

// A fake DOM, enough for cite-ui.js to render a Cite's blocks: elements with attributes,
// children and text. The module upgrades the page's cites at import, so the globals come first.
function make(tag) {
  return {
    tag, attrs: {}, children: [], textContent: "", listeners: {}, parent: null,
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return this.attrs[k] ?? null; },
    append(...n) { for (const c of n) { c.parent = this; this.children.push(c); } },
    addEventListener(t, f) { this.listeners[t] = f; },
    remove() { if (this.parent) this.parent.children.splice(this.parent.children.indexOf(this), 1); },
    all() { return [this, ...this.children.flatMap((c) => c.all())]; },
    querySelector(sel) {
      const cls = sel.startsWith(".") ? sel.slice(1) : null;
      return this.all().slice(1).find((e) => (cls ? (e.attrs.class ?? "").split(" ").includes(cls) : e.tag === sel)) ?? null;
    },
  };
}
globalThis.document = { createElement: make, querySelectorAll: () => [], querySelector: () => null, body: make("body") };
globalThis.MutationObserver = class { observe() {} };
globalThis.location = { origin: "https://x.org", pathname: "/city/berlin/time", search: "", hash: "" };
const { render } = await import("../cite-ui.js");

function details(title) {
  const d = make("details");
  const blob = make("script");
  blob.setAttribute("class", "cite-data");
  blob.textContent = JSON.stringify({
    title, path: "city/berlin/time", osm_timestamp: "2026-10-03T01:00:00Z", snapshot_note: null,
    classifier: "v4", run_id: "7", commit: "abc1234", attribution: "Map data © OpenStreetMap contributors, ODbL 1.0",
  }); // fmt: skip
  d.append(blob);
  return d;
}

test("an open Cite adds no heading (it sits under h2 or h3 sections) and no unreferenced id", () => {
  const d = details("Berlin: headline over time");
  render(d);
  const els = d.all();
  assert.equal(els.filter((e) => e.attrs.class === "cite-block").length, 3);
  assert.deepEqual(els.filter((e) => /^h[1-6]$/.test(e.tag)).map((e) => e.tag), []);
  assert.deepEqual(els.filter((e) => "id" in e.attrs).map((e) => e.attrs.id), []);
  const labels = els.filter((e) => e.attrs.class === "cite-label").map((e) => e.textContent);
  assert.deepEqual(labels, ["Text", "BibTeX", "CSL-JSON"]);
});

test("every Copy button is named by its format and its figure's title, unique on the page", () => {
  const a = details("Berlin: headline over time");
  const b = details("Berlin: tier composition over time, LAU");
  render(a);
  render(b);
  const names = [a, b].flatMap((d) => d.all().filter((e) => e.tag === "button").map((e) => e.getAttribute("aria-label")));
  assert.equal(names.length, 6);
  assert.equal(new Set(names).size, 6, names.join(" | "));
  assert.ok(names.includes("Copy BibTeX, Berlin: headline over time"), names.join(" | "));
  for (const n of names.slice(3)) assert.match(n, /Berlin: tier composition over time, LAU$/);
});
