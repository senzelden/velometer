import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { absoluteUrl, citeBibtex, citeCsl, citeText } from "../cite.js";

// shared with tests/test_m11.py, so the Python and JS formatting rules agree
const CASES = JSON.parse(
  readFileSync(new URL("../../../../../../tests/cite_cases.json", import.meta.url), "utf8"),
);

const docWithBase = (content) => ({
  querySelector: (sel) =>
    sel === 'meta[name="velometer-base"]'
      ? { getAttribute: (name) => (name === "content" ? content : null) }
      : null,
});

test("cite: the shared cases give the same text, BibTeX and CSL-JSON", () => {
  assert.ok(CASES.length >= 5);
  for (const c of CASES) {
    assert.equal(citeText(c.fields, c.accessed, c.url), c.text, c.name);
    assert.equal(citeBibtex(c.fields, c.accessed, c.url), c.bibtex, c.name);
    assert.deepEqual(citeCsl(c.fields, c.accessed, c.url), c.csl, c.name);
  }
});

test("absoluteUrl: origin + base + path + search + hash", () => {
  assert.equal(
    absoluteUrl("/city/berlin/tiers", { origin: "https://x.org", search: "?kind=fua", hash: "" }, docWithBase("/velometer/")),
    "https://x.org/velometer/city/berlin/tiers?kind=fua",
  );
  assert.equal(
    absoluteUrl("/city/berlin", { origin: "https://x.org", search: "", hash: "#map" }, docWithBase("/")),
    "https://x.org/city/berlin#map",
  );
});
