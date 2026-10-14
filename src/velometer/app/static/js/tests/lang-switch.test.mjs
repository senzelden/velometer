import test from "node:test";
import assert from "node:assert/strict";
import { switchHref } from "../lang-switch.js";

test("the switch keeps the permalink", () => {
  const loc = { search: "?cities=berlin,vienna&metric=x", hash: "#chart" };
  assert.equal(switchHref("/velometer/compare", loc), "/velometer/compare?cities=berlin,vienna&metric=x#chart");
  assert.equal(switchHref("/velometer/de/", { search: "", hash: "" }), "/velometer/de/");
  assert.equal(switchHref("/x?a=1", loc), "/x?a=1");
});
