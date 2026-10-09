import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, relative, sep } from "node:path";
import { base, url } from "../base.js";
import { compareUrl, panelUrl } from "../compare-model.js";

// shared with tests/test_urls.py, so the JS helper and the Python `u` agree
const CASES = JSON.parse(
  readFileSync(new URL("../../../../../../tests/url_cases.json", import.meta.url), "utf8"),
);

/** A document whose <meta name="velometer-base"> says `content` (none when undefined). */
const docWith = (content) => ({
  querySelector: (sel) =>
    sel === 'meta[name="velometer-base"]' && content !== undefined
      ? { getAttribute: (name) => (name === "content" ? content : null) }
      : null,
});

test("base: `/` without a document (node) and without the meta tag", () => {
  assert.equal(globalThis.document, undefined);
  assert.equal(base(), "/");
  assert.equal(base(docWith(undefined)), "/");
});

test("base: the meta tag's content, normalised as the Python side normalises it", () => {
  assert.equal(base(docWith("/")), "/");
  assert.equal(base(docWith("/velometer/")), "/velometer/");
  for (const [given, normalised] of CASES.normalise) assert.equal(base(docWith(given)), normalised, given);
});

test("url: the shared emit table", () => {
  for (const [b, path, expected] of CASES.emit) assert.equal(url(path, docWith(b)), expected, `${b} ${path}`);
});

test("url: external and fragment-only URLs are left alone under any base", () => {
  for (const b of ["/", "/velometer/"]) {
    for (const u of CASES.untouched) assert.equal(url(u, docWith(b)), u, `${b} ${u}`);
  }
});

test("url: a relative path is refused", () => {
  for (const p of CASES.relative) assert.throws(() => url(p, docWith("/velometer/")), Error, p);
});

test("url: without a document it is the identity on paths (the live app)", () => {
  assert.equal(url("/city/berlin"), "/city/berlin");
});

test("compareUrl: the history URL of Compare carries the base", () => {
  const doc = docWith("/velometer/");
  assert.equal(compareUrl("c=berlin,paris&m=ab_km", doc), "/velometer/compare?c=berlin,paris&m=ab_km");
  assert.equal(compareUrl("", doc), "/velometer/compare");
  assert.equal(compareUrl("c=berlin", docWith("/")), "/compare?c=berlin");
  assert.equal(compareUrl(""), "/compare");
});

test("panelUrl: the slide-over fetches its fragment under the base", () => {
  assert.equal(panelUrl("berlin", docWith("/velometer/")), "/velometer/city/berlin/panel");
  assert.equal(panelUrl("a b", docWith("/velometer/")), "/velometer/city/a%20b/panel");
  assert.equal(panelUrl("berlin"), "/city/berlin/panel");
});

// ---- rules over every app script ----

const STATIC = fileURLToPath(new URL("../../", import.meta.url));
const SCRIPTS = readdirSync(STATIC, { recursive: true })
  .map((f) => String(f))
  .filter((f) => f.endsWith(".js"))
  .filter((f) => !f.split(sep).some((part) => part === "vendor" || part === "tests"))
  .map((f) => ({ name: f.split(sep).join("/"), text: readFileSync(join(STATIC, f), "utf8") }));
const ROUTES = "city|compare|data|maps|static|plans|organisations|methodology|cities|stories|differences";
// a string or template literal that starts with one of the app's routes and is not the
// argument of url()
const LITERAL_ROUTE = new RegExp(`(?<!(?<![\\w.$])url\\(\\s*)["'\`]/(?:${ROUTES})(?=[/?#."'\`]|$)`, "gm");
// a call of url() whose argument is not a literal path: a URL a page config already based
// (tier and change maps, the Stories Explore links) would get the base twice
const URL_OF_NON_LITERAL = /(?<![\w.$])url\(\s*(?![`"']\/)/g;

const lineOf = (text, index) => text.slice(0, index).split("\n").length;

test("the rule scan sees the app's scripts", () => {
  const names = SCRIPTS.map((s) => s.name);
  for (const n of ["js/base.js", "js/data.js", "js/panel.js", "js/compare.js", "map.js"]) assert.ok(names.includes(n), n);
  assert.ok(!names.some((n) => n.startsWith("vendor/") || n.includes("/tests/")));
  assert.ok(relative(STATIC, fileURLToPath(import.meta.url)).startsWith("js"));
});

test("rule: every internal URL in a script is built with url(), never a literal route", () => {
  const bad = [];
  for (const { name, text } of SCRIPTS) {
    if (name === "js/base.js") continue;
    for (const m of text.matchAll(LITERAL_ROUTE)) bad.push(`${name}:${lineOf(text, m.index)}: ${m[0]}`);
  }
  assert.deepEqual(bad, []);
});

test("rule: url() is only given a literal path (config URLs already carry the base)", () => {
  const bad = [];
  for (const { name, text } of SCRIPTS) {
    if (name === "js/base.js") continue;
    for (const m of text.matchAll(URL_OF_NON_LITERAL)) bad.push(`${name}:${lineOf(text, m.index)}`);
  }
  assert.deepEqual(bad, []);
});

test("the rule patterns catch what they are for", () => {
  const hits = (re, s) => [...s.matchAll(re)].length;
  assert.equal(hits(LITERAL_ROUTE, 'fetch("/data/series.json")'), 1);
  assert.equal(hits(LITERAL_ROUTE, "fetch(`/city/${id}/panel`)"), 1);
  assert.equal(hits(LITERAL_ROUTE, "x = '/compare'"), 1);
  assert.equal(hits(LITERAL_ROUTE, 'url("/data/series.json")'), 0);
  assert.equal(hits(LITERAL_ROUTE, "url(`/compare${qs}`)"), 0);
  assert.equal(hits(LITERAL_ROUTE, 'myurl("/data/series.json")'), 1);
  assert.equal(hits(LITERAL_ROUTE, 'x.url("/data/series.json")'), 1);
  assert.equal(hits(LITERAL_ROUTE, "// fetches /city/<id>/panel"), 0);
  assert.equal(hits(LITERAL_ROUTE, '"/cityscape"'), 0);
  assert.equal(hits(URL_OF_NON_LITERAL, "fetch(url(entry.url))"), 1);
  assert.equal(hits(URL_OF_NON_LITERAL, "a.href = url(spec.href)"), 1);
  assert.equal(hits(URL_OF_NON_LITERAL, "url(`/city/${id}`)"), 0);
  assert.equal(hits(URL_OF_NON_LITERAL, "fetch(entry.url)"), 0);
  assert.equal(hits(URL_OF_NON_LITERAL, "compareUrl(qs)"), 0);
});
