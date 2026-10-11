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

test("multiFields mirrors fields_for_cities: a day range, natural classifier order, skipped runless", async () => {
  const { multiFields } = await import("../cite.js");
  const runs = {
    a: { osm_timestamp: "2026-10-05T01:00:00Z", classifier: "v10" },
    b: { osm_timestamp: "2026-10-03T01:00:00Z", classifier: "v9" },
    c: { osm_timestamp: "2026-10-04T01:00:00Z", classifier: "v9" },
  };
  const f = multiFields(runs, ["a", "b", "c", "nowhere"], "t", "/compare", "abc1234");
  assert.equal(f.snapshot_note, "OSM snapshots of 2026-10-03 to 2026-10-05");
  assert.equal(f.classifier, "v9/v10");
  assert.equal(f.run_id, null);
  assert.equal(f.osm_timestamp, null);
  assert.equal(f.commit, "abc1234");
  assert.equal(multiFields(runs, ["b", "b"], "t", "/compare", "x").snapshot_note, "OSM snapshot of 2026-10-03");
  assert.equal(multiFields(runs, ["nowhere"], "t", "/compare", "x"), null);
});
