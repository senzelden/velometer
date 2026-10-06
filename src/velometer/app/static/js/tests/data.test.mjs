import { test } from "node:test";
import assert from "node:assert/strict";
import { displayLabels, labelsOf, pointsOn } from "../data.js";

const lau = [
  { label: "2019", headline: 2, flags: "" },
  { label: "current", headline: 4, osm: "2026-10-03", flags: "km_jump;tag_drift" },
];
const fua = [{ label: "2018", headline: 1, flags: "" }, { label: "2019", headline: null, flags: "" }];

test("labelsOf: union of years in order, current last", () => {
  assert.deepEqual(labelsOf([lau, fua]), ["2018", "2019", "current"]);
  assert.deepEqual(labelsOf([fua]), ["2018", "2019"]);
  assert.deepEqual(labelsOf([]), []);
});

test("pointsOn: a value per label, null for missing or null points, flags as a list", () => {
  const pts = pointsOn(lau, ["2018", "2019", "current"], "headline");
  assert.deepEqual(pts.map((p) => p.value), [null, 2, 4]);
  assert.deepEqual(pts[2].flags, ["km_jump", "tag_drift"]);
  assert.deepEqual(pts[0].flags, []);
  assert.equal(pointsOn(fua, ["2019"], "headline")[0].value, null);
});

test("displayLabels: current becomes the snapshot month of the first list that has one", () => {
  assert.deepEqual(displayLabels(["2019", "current"], [fua, lau]), ["2019", "Oct 2026"]);
  assert.deepEqual(displayLabels(["2019"], [fua]), ["2019"]);
});
