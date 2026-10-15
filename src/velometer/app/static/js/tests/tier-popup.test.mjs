import { test } from "node:test";
import assert from "node:assert/strict";
import "./strings-fixture.mjs";

// a stub DOM: enough for the popup to build its tree
class Node {
  constructor(tag) {
    this.tag = tag;
    this.attrs = {};
    this.children = [];
    this.textContent = "";
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  appendChild(c) { this.children.push(c); return c; }
  set innerHTML(_) { throw new Error("innerHTML must not be used"); }
}
globalThis.document = { createElement: (tag) => new Node(tag) };
const { tierPopup } = await import("../tier-popup.js");

const CFG = {
  labels: { A: "A separated track", B: "B protected lane" },
  links: { way: "https://osm.example/way/" },
};
const SIDE = { tier: "A", way_id: 7, side: "left", subtype: "track", rule_id: "r1", km: 0.1234,
  tags: { highway: "cycleway", "<b>": "<i>x</i>" } };

test("the tier map popup opens with the side's tier by its full name, not a colour", () => {
  const box = tierPopup(SIDE, CFG);
  assert.equal(box.attrs.class, "tiermap-popup");
  const first = box.children[0];
  assert.equal(first.tag, "p");
  assert.equal(first.attrs.class, "tiermap-popup-tier");
  assert.equal(first.textContent, "A separated track");
  assert.equal(tierPopup({ ...SIDE, tier: "Z" }, CFG).children[0].textContent, "Z");
});

test("the popup lists the side and its tags as text, the way as a link", () => {
  const [, dl, table] = tierPopup(SIDE, CFG).children;
  const terms = dl.children.filter((c) => c.tag === "dt").map((c) => c.textContent);
  assert.deepEqual(terms.slice(0, 2), ["OSM", "side"]);
  const link = dl.children[1].children[0];
  assert.equal(link.tag, "a");
  assert.equal(link.attrs.href, "https://osm.example/way/7");
  assert.equal(link.attrs.rel, "noopener noreferrer");
  const cells = table.children.map((tr) => tr.children.map((td) => td.textContent));
  assert.deepEqual(cells, [["<b>", "<i>x</i>"], ["highway", "cycleway"]]);
});
