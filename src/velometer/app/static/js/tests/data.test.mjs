import { test } from "node:test";
import assert from "node:assert/strict";
import { fakeDoc, useLang } from "./strings-fixture.mjs";
import { displayLabels, labelsOf, mapStatus, pointsOn } from "../data.js";

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

test("mapStatus: the side count as a locale number in both languages", () => {
  const p = { osm_timestamp: "2026-10-03T20:20:50Z", classifier: "v4", run_id: 713 };
  const en = mapStatus("lau", 31842, p, fakeDoc("en"));
  assert.ok(en.startsWith("LAU · 31,842 sides · OSM 2026-10-03T20:20:50Z · classifier v4 · run 713."), en);
  assert.ok(mapStatus("lau", 999, p, fakeDoc("en")).startsWith("LAU · 999 sides"));
  useLang("de");
  const de = mapStatus("fua", 31842, p, fakeDoc("de"));
  assert.ok(de.startsWith("FUA · 31.842 Seiten · OSM 2026-10-03T20:20:50Z · Klassifikator v4"), de);
  useLang("en");
});
