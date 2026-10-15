import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, relative, sep } from "node:path";
import { _resetBase, base, lang, url } from "../base.js";
import { compareUrl, panelUrl } from "../compare-model.js";
import { literals } from "./js-literals.mjs";
import { repoFile, repoRoot } from "./repo.mjs";

// shared with tests/test_urls.py, so the JS helper and the Python `u` agree
const CASES = JSON.parse(readFileSync(repoFile("tests/url_cases.json"), "utf8"));

test("the shared cases are found from the repository root, not a fixed run of ../", () => {
  const root = repoRoot();
  assert.ok(readFileSync(join(root, "pyproject.toml"), "utf8").includes("velometer"));
  assert.equal(repoRoot(join(root, "src", "velometer", "app", "static", "js", "tests", "x.mjs")), root);
  assert.throws(() => repoRoot("/"), /no pyproject.toml/);
});

/** A document whose <meta name="velometer-base"> says `content` (none when undefined) and whose
 * root element has `lang` (default "en"). */
const docWith = (content, lang_ = "en") => ({
  documentElement: { lang: lang_ },
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

test("lang: the root element's language, `en` unless it is German", () => {
  assert.equal(lang(), "en");
  assert.equal(lang(docWith("/", "de")), "de");
  assert.equal(lang(docWith("/", "de-DE")), "de");
  assert.equal(lang(docWith("/", "en")), "en");
  assert.equal(lang(docWith("/", "")), "en");
});

test("url: the shared language table; data, map and static paths never get the prefix", () => {
  for (const [b, l, path, expected] of [...CASES.emit_lang, ...CASES.emit_lang_js]) {
    assert.equal(url(path, docWith(b, l)), expected, `${b} ${l} ${path}`);
  }
});

test("url: external and fragment-only URLs are left alone under any base", () => {
  for (const b of ["/", "/velometer/"]) {
    for (const u of CASES.untouched) assert.equal(url(u, docWith(b)), u, `${b} ${u}`);
  }
});

test("url: a relative path is refused", () => {
  for (const p of CASES.relative) assert.throws(() => url(p, docWith("/velometer/")), Error, p);
});

test("base: read once per document, again after the test reset hook", () => {
  let reads = 0;
  const doc = docWith("/velometer/");
  const query = doc.querySelector;
  doc.querySelector = (sel) => (reads++, query(sel));
  _resetBase();
  assert.equal(base(doc), "/velometer/");
  assert.equal(url("/city/berlin", doc), "/velometer/city/berlin");
  assert.equal(base(doc), "/velometer/");
  assert.equal(reads, 1, "one DOM query for the document, however many url() calls");
  assert.equal(base(docWith("/other/")), "/other/", "another document has its own base");
  _resetBase();
  base(doc);
  assert.equal(reads, 2, "the reset hook forgets it");
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
// A string or template literal that starts with one of the app's routes and is not the argument
// of url(). What it covers: a literal (quoted or a template's lead) that *begins* with `/<route>`,
// the route ending at `/ ? # .`, a quote or the line end, anywhere in the code (comments too).
// What it does not: the bare root `"/"` (ROOT_LITERAL below has its own rule), a route a string
// builds by joining pieces (`"/" + "city"`, `["", "city"].join("/")`), a route after a template's
// first `${…}`, and a relative `"city/…"` (url() refuses those at run time). None exist today.
const LITERAL_ROUTE = new RegExp(`(?<!(?<![\\w.$])url\\(\\s*)["'\`]/(?:${ROUTES})(?=[/?#."'\`]|$)`, "gm");
// a call of url() whose argument is not a literal path: a URL a page config already based
// (tier and change maps, the Stories Explore links) would get the base twice
const URL_OF_NON_LITERAL = /(?<![\w.$])url\(\s*(?![`"']\/)/g;

// The bare root as a string literal: "/", or "/" with a query or fragment ("/?x", "/#y"). A "/"
// that is the argument of a string method (`.join("/")`, `.split("/")`, `.endsWith("/")` …) is a
// separator, not a URL. Comments and regular expressions are not literals (js-literals.mjs).
const SEPARATOR_CALL = /(?:(?<![\w.$])url|\.(?:join|split|startsWith|endsWith|includes|indexOf|lastIndexOf|replace|replaceAll))\(\s*$/;
const rootLiterals = (src) =>
  literals(src).filter((l) => /^\/(?:[?#].*)?$/s.test(l.text) && !SEPARATOR_CALL.test(l.before));

const lineOf = (text, index) => text.slice(0, index).split("\n").length;

test("the rule scan sees the app's scripts", () => {
  const names = SCRIPTS.map((s) => s.name);
  for (const n of ["js/base.js", "js/data.js", "js/panel.js", "js/compare.js", "map.js"]) assert.ok(names.includes(n), n);
  assert.ok(!names.some((n) => n.startsWith("vendor/") || n.includes("/tests/")));
});

test("the scan's root is the static directory: this file sits in its js/tests", () => {
  assert.equal(relative(STATIC, fileURLToPath(import.meta.url)).split(sep).join("/"), "js/tests/base.test.mjs");
});

test("rule: every internal URL in a script is built with url(), never a literal route", () => {
  const bad = [];
  for (const { name, text } of SCRIPTS) {
    if (name === "js/base.js") continue;
    for (const m of text.matchAll(LITERAL_ROUTE)) bad.push(`${name}:${lineOf(text, m.index)}: ${m[0]}`);
  }
  assert.deepEqual(bad, []);
});

test("rule: no script writes the bare root \"/\" as a URL literal (it goes through url())", () => {
  const bad = [];
  for (const { name, text } of SCRIPTS) {
    if (name === "js/base.js") continue;
    for (const l of rootLiterals(text)) bad.push(`${name}:${l.line}: ${JSON.stringify(l.text)}`);
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
  // the bare root
  const roots = (s) => rootLiterals(s).length;
  assert.equal(roots('a.href = "/";'), 1);
  assert.equal(roots("fetch('/')"), 1);
  assert.equal(roots('location.assign("/?x=1")'), 1);
  assert.equal(roots("const home = `/#top`;"), 1);
  assert.equal(roots('const p = "/" + id;'), 1);
  assert.equal(roots('url("/")'), 0);
  assert.equal(roots('parts.join("/")'), 0);
  assert.equal(roots("path.split('/')"), 0);
  assert.equal(roots('p.endsWith("/")'), 0);
  assert.equal(roots('// the root "/" in a comment'), 0);
  assert.equal(roots('"/city"'), 0);
});
