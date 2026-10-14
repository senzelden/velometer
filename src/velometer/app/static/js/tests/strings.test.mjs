import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { FIXTURE, fakeDoc, useLang } from "./strings-fixture.mjs";
import { leafletPrefix, loadStrings, setStrings, t } from "../strings.js";
import { offenders } from "./js-literals.mjs";

test("with the German strings, t gives the German value", () => {
  useLang("de");
  assert.equal(t("js.search.no_match"), FIXTURE.de["js.search.no_match"]);
  assert.notEqual(t("js.search.no_match"), FIXTURE.en["js.search.no_match"]);
  useLang("en");
});

test("a key missing in German gives the English value, never the bare key", () => {
  const de = { ...FIXTURE.de };
  delete de["js.search.no_match"];
  setStrings(de, FIXTURE.en);
  assert.equal(t("js.search.no_match"), FIXTURE.en["js.search.no_match"]);
  useLang("en");
});

test("a plural picks one or other by count; placeholders are filled", () => {
  useLang("en");
  assert.equal(t("js.search.results", { count: 1 }), "1 result");
  assert.equal(t("js.search.results", { count: 3 }), "3 results");
  useLang("de");
  assert.equal(t("js.story.step", { n: 2, of: 5 }), "Schritt 2 von 5");
  useLang("en");
});

test("loadStrings reads the page's #ui-strings block", () => {
  assert.equal(loadStrings(fakeDoc("de", FIXTURE.de)), true);
  assert.equal(t("js.search.no_match"), FIXTURE.de["js.search.no_match"]);
  assert.equal(loadStrings(fakeDoc("de")), false); // no block: the strings stay
  assert.equal(t("js.search.no_match"), FIXTURE.de["js.search.no_match"]);
  useLang("en");
});

const JS_DIR = new URL("../", import.meta.url);
const STATIC = new URL("../../", import.meta.url);
const SOURCES = [
  ...readdirSync(JS_DIR).filter((f) => f.endsWith(".js")).map((f) => new URL(f, JS_DIR)),
  ...["map.js", "changemap.js", "countermap.js"].map((f) => new URL(f, STATIC)),
];

test("no English literal is left in a script: every user-facing text goes through t()", () => {
  const bad = SOURCES.flatMap((u) =>
    offenders(readFileSync(u, "utf8"), u.pathname.split("/").pop()).map((o) => `${o.file}:${o.line} ${JSON.stringify(o.text)}`),
  );
  assert.deepEqual(bad, []);
});

test("the literal guard finds English text, and passes keys, selectors, imports and console", () => {
  const src = [
    'import { x } from "./some module.js";',
    'const a = "Copied to clipboard";',
    "const b = `Step ${n} of ${m}`;",
    'el.querySelectorAll("thead th");',
    'console.warn("search index could not be loaded");',
    't("js.search.no_match");',
    'node.setAttribute("rel", "noopener noreferrer");',
    'const c = { class: big ? "gridl zero" : "gridl" };',
    'const d = "Copy";', // one word: below the guard's threshold
    "const re = /no match here/g;",
  ].join("\n");
  assert.deepEqual(
    offenders(src, "x.js").map((o) => o.text),
    ["Copied to clipboard", "Step \u0000 of \u0000"],
  );
});

test("every JS key a script reads exists in the strings (counter-model.js among them)", () => {
  const KEY = /\bt\(\s*["'](js\.[\w.]+)["']/g;
  const used = new Set();
  for (const u of SOURCES) for (const m of readFileSync(u, "utf8").matchAll(KEY)) used.add(m[1]);
  const counter = readFileSync(new URL("counter-model.js", JS_DIR), "utf8");
  const counterKeys = [...counter.matchAll(KEY)].map((m) => m[1]);
  assert.ok(counterKeys.filter((k) => k.startsWith("js.counts.")).length >= 10);
  for (const lang of ["en", "de"]) {
    assert.deepEqual([...used].filter((k) => !(k in FIXTURE[lang])), [], lang);
  }
});

// Leaflet's own attribution prefix (vendor/leaflet.js, 1.9): an English link title
const LEAFLET_PREFIX = '<a href="https://leafletjs.com" title="A JavaScript library for interactive maps">'
  + '<svg aria-hidden="true" width="12"></svg> Leaflet</a>';

test("leafletPrefix: English keeps Leaflet's prefix as it is, German gives the link a German title", () => {
  useLang("en");
  assert.equal(leafletPrefix(LEAFLET_PREFIX), LEAFLET_PREFIX);
  useLang("de");
  const de = leafletPrefix(LEAFLET_PREFIX);
  assert.ok(de.includes(`title="${FIXTURE.de["js.map.leaflet_title"]}"`), de);
  assert.ok(!de.includes("A JavaScript library") && de.includes("<svg") && de.endsWith("Leaflet</a>"));
  useLang("en");
});

test("the three Leaflet maps set the localised prefix", () => {
  for (const name of ["map.js", "countermap.js", "changemap.js"]) {
    const src = readFileSync(new URL(`../../${name}`, import.meta.url), "utf8");
    assert.match(src, /attributionControl\.setPrefix\(leafletPrefix\(/, name);
  }
});
