import { test } from "node:test";
import assert from "node:assert/strict";
import { describe } from "../describe.js";

const plot = () => {
  const attrs = {};
  return {
    attrs,
    setAttribute: (k, v) => (attrs[k] = v),
    removeAttribute: (k) => delete attrs[k],
  };
};
const doc = (ids) => ({ getElementById: (id) => (ids.includes(id) ? {} : null) });

test("a step with a table points the chart at it, one without clears the reference", () => {
  const p = plot();
  describe(p, "growth", doc(["step-values-growth"]));
  assert.equal(p.attrs["aria-describedby"], "step-values-growth");
  describe(p, "tail", doc(["step-values-growth"]));
  assert.equal("aria-describedby" in p.attrs, false);
});
