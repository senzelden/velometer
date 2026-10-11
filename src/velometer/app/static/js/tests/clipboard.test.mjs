import { test } from "node:test";
import assert from "node:assert/strict";
import { copyText } from "../clipboard.js";

// a document with one <pre> holding `text`, and a selection that records what is selected
const docWith = (text) => {
  const pre = { textContent: text };
  const sel = { cleared: 0, ranges: [], removeAllRanges() { this.cleared++; }, addRange(r) { this.ranges.push(r); } };
  const doc = {
    querySelectorAll: (q) => (q === "pre" ? [{ textContent: "other" }, pre] : []),
    createRange: () => ({ selectNodeContents(n) { this.node = n; } }),
    getSelection: () => sel,
  };
  return { doc, sel, pre };
};

test("copyText writes to the clipboard and announces Copied", async () => {
  const said = [];
  const written = [];
  const nav = { clipboard: { writeText: async (t) => written.push(t) } };
  const { doc } = docWith("abc");
  const r = await copyText("abc", { nav, doc, announce: (t) => said.push(t) });
  assert.equal(r, "copied");
  assert.deepEqual(written, ["abc"]);
  assert.deepEqual(said, ["Copied"]);
});

test("copyText selects the matching <pre> and says to press Ctrl+C when the clipboard rejects", async () => {
  const said = [];
  const nav = { clipboard: { writeText: async () => { throw new Error("denied"); } } };
  const { doc, sel, pre } = docWith("abc");
  const r = await copyText("abc", { nav, doc, announce: (t) => said.push(t) });
  assert.equal(r, "selected");
  assert.deepEqual(said, ["Press Ctrl+C to copy"]);
  assert.equal(sel.ranges.length, 1);
  assert.equal(sel.ranges[0].node, pre);
});

test("copyText selects when there is no clipboard at all", async () => {
  const said = [];
  const { doc, sel } = docWith("abc");
  const r = await copyText("abc", { nav: {}, doc, announce: (t) => said.push(t) });
  assert.equal(r, "selected");
  assert.deepEqual(said, ["Press Ctrl+C to copy"]);
  assert.equal(sel.ranges.length, 1);
});
