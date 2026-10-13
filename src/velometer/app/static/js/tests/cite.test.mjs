import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { useLang } from "./strings-fixture.mjs";
import { absoluteUrl, citeBibtex, citeCsl, citeText, cslJson, multiFields } from "../cite.js";

// shared with tests/test_m11.py, so the Python and JS formatting rules agree
const SHARED = JSON.parse(
  readFileSync(new URL("../../../../../../tests/cite_cases.json", import.meta.url), "utf8"),
);
const CASES = SHARED.cases;

const docWithBase = (content) => ({
  querySelector: (sel) =>
    sel === 'meta[name="velometer-base"]'
      ? { getAttribute: (name) => (name === "content" ? content : null) }
      : null,
});

test("cite: the shared cases give the same text, BibTeX and CSL-JSON", () => {
  assert.ok(CASES.length >= 5);
  assert.deepEqual([...new Set(CASES.map((c) => c.lang))].sort(), ["de", "en"]);
  for (const c of CASES) {
    useLang(c.lang); // a page has the strings of its own language
    assert.equal(citeText(c.fields, c.accessed, c.url, c.lang), c.text, c.name);
    assert.equal(citeBibtex(c.fields, c.accessed, c.url, c.lang), c.bibtex, c.name);
    assert.deepEqual(citeCsl(c.fields, c.accessed, c.url, c.lang), c.csl, c.name);
    assert.equal(cslJson(citeCsl(c.fields, c.accessed, c.url, c.lang)), c.csl_text, c.name);
  }
  useLang("en");
});

test("German BibTeX says language = {german} and CSL-JSON says language de; English neither", () => {
  for (const c of CASES) {
    assert.equal(c.bibtex.includes("language = {german}"), c.lang === "de", c.name);
    assert.equal(c.csl.language === "de", c.lang === "de", c.name);
  }
});

test("absoluteUrl: origin + base + path + search + hash", () => {
  assert.equal(
    absoluteUrl("/city/berlin/tiers", { origin: "https://x.org", pathname: "/velometer/city/berlin/tiers/", search: "?kind=fua", hash: "" }, docWithBase("/velometer/")),
    "https://x.org/velometer/city/berlin/tiers?kind=fua",
  );
  assert.equal(
    absoluteUrl("/city/berlin", { origin: "https://x.org", pathname: "/city/berlin", search: "", hash: "#map" }, docWithBase("/")),
    "https://x.org/city/berlin#map",
  );
});

test("a citation of another page (the city panel on Compare) does not take this page's query", () => {
  const loc = { origin: "https://x.org", pathname: "/velometer/compare/", search: "?c=berlin,paris&panel=berlin", hash: "#x" };
  assert.equal(absoluteUrl("city/berlin", loc, docWithBase("/velometer/")), "https://x.org/velometer/city/berlin");
  assert.equal(
    absoluteUrl("compare", loc, docWithBase("/velometer/")),
    "https://x.org/velometer/compare?c=berlin,paris&panel=berlin#x",
  );
  const home = { origin: "https://x.org", pathname: "/velometer/", search: "?q=1", hash: "" };
  assert.equal(absoluteUrl("", home, docWithBase("/velometer/")), "https://x.org/velometer/?q=1");
  const index = { ...home, pathname: "/velometer/index.html" };
  assert.equal(absoluteUrl("", index, docWithBase("/velometer/")), "https://x.org/velometer/?q=1");
});

test("cslJson puts every date-parts array on one line", () => {
  const text = cslJson({ issued: { "date-parts": [[2026]] }, accessed: { "date-parts": [[2026, 10, 11]] } });
  assert.match(text, /"date-parts": \[\[2026\]\]/);
  assert.match(text, /"date-parts": \[\[2026, 10, 11\]\]/);
});

test("absoluteUrl takes the slashless path the page emits, under / and a base", () => {
  const loc = { origin: "https://x.org", search: "", hash: "" };
  assert.equal(absoluteUrl("city/berlin/time", loc, docWithBase("/")), "https://x.org/city/berlin/time");
  assert.equal(
    absoluteUrl("city/berlin/time", loc, docWithBase("/velometer/")),
    "https://x.org/velometer/city/berlin/time",
  );
});

test("multiFields agrees with the shared cases (tests/cite_cases.json, multi)", () => {
  assert.ok(SHARED.multi.length >= 3);
  for (const c of SHARED.multi) {
    useLang(c.lang);
    assert.deepEqual(multiFields(c.runs, c.ids, c.title, c.path, c.commit), c.expected, c.name);
  }
  useLang("en");
});
