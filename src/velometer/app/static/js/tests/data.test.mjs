import { test } from "node:test";
import assert from "node:assert/strict";
import { fakeDoc, useLang } from "./strings-fixture.mjs";
import { displayLabels, labelsOf, localised, mapStatus, pointsOn } from "../data.js";

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

// a series.json as app/series.py writes it: English values, the German ones as `_de` siblings
const SERIES = {
  cities: {
    krakow: { id: "krakow", name: "Kraków", country_name: "Poland", population: 800000,
              name_de: "Krakau", country_name_de: "Polen" },
    paris: { id: "paris", name: "Paris", country_name: "France", population: 2e6 },
  },
  series: { "krakow/lau": [{ label: "2019", headline: 2 }] },
  presets: { ours_headline: "velometer headline", ecf_qecio: "QECIO, our OSM data" },
  presets_de: { ours_headline: "velometer-Kennzahl", ecf_qecio: "QECIO, unsere OSM-Daten" },
  headline_unit: "A+B km per 100 km of main roads",
  headline_unit_de: "A+B-km je 100 km Hauptstraßen",
  explanations: { timeseries: { "krakow/lau/2019": "English cause.", "paris/lau/2020": "Other." } },
  explanations_de: {
    timeseries: { "krakow/lau/2019": "Deutsche Ursache.", "paris/lau/2020": "Other." },
    fallback: ["paris/lau/2020"],
  },
  counters: { cities: {}, none: { paris: "no open counter data found" },
              none_de: { paris: "keine offenen Zähldaten gefunden" } },
};

test("localised: English is the payload itself", () => {
  assert.equal(localised(SERIES, "en"), SERIES);
});

test("localised: German swaps in every _de sibling and leaves the payload alone", () => {
  const before = JSON.stringify(SERIES);
  const D = localised(SERIES, "de");
  assert.equal(D.cities.krakow.name, "Krakau");
  assert.equal(D.cities.krakow.country_name, "Polen");
  assert.equal(D.headline_unit, "A+B-km je 100 km Hauptstraßen");
  assert.equal(D.presets.ours_headline, "velometer-Kennzahl");
  assert.equal(D.counters.none.paris, "keine offenen Zähldaten gefunden");
  assert.equal(D.explanations.timeseries["krakow/lau/2019"], "Deutsche Ursache.");
  assert.equal(JSON.stringify(SERIES), before);
});

test("localised: explanation keys still English are in explanationFallback", () => {
  const D = localised(SERIES, "de");
  assert.ok(D.explanationFallback instanceof Set);
  assert.ok(D.explanationFallback.has("paris/lau/2020"));
  assert.ok(!D.explanationFallback.has("krakow/lau/2019"));
});

test("localised: a field without a _de sibling keeps its English value", () => {
  const D = localised(SERIES, "de");
  assert.equal(D.cities.paris.name, "Paris");
  assert.equal(D.cities.paris.country_name, "France");
  assert.equal(D.cities.krakow.population, 800000);
  assert.deepEqual(D.series, SERIES.series);
});

