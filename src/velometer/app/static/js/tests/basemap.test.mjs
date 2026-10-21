import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { ROLES, addBasemap, credits, flavour } from "../basemap.js";
import { setStrings } from "../strings.js";
import { repoFile } from "./repo.mjs";

const CFG = {
  tiles: "/velometer/tiles/velometer.pmtiles",
  links: { copyright: "https://www.openstreetmap.org/copyright" },
};
setStrings({
  "js.map.osm_contributors": "OpenStreetMap contributors",
  "js.map.basemap_credit": "Protomaps, ESA WorldCover (CC BY 4.0)",
});

// a Leaflet map as far as addBasemap touches it
function fakeMap() {
  const map = { credits: [], layers: [] };
  map.attributionControl = { addAttribution: (s) => map.credits.push(s) };
  return map;
}

// protomaps-leaflet as far as addBasemap touches it: the rules record the flavour they were made of
function fakePm({ header = Promise.resolve({ maxZoom: 13 }) } = {}) {
  const pm = { made: [] };
  pm.PmtilesSource = class {
    constructor(url, cancel) {
      this.p = { url, cancel, getHeader: () => header };
    }
  };
  pm.paintRules = (f) => ({ paint: f });
  pm.labelRules = (f, lang) => ({ label: f, lang });
  pm.leafletLayer = (opts) => {
    const layer = {
      ...opts,
      cleared: 0,
      rerendered: 0,
      addTo(m) { m.layers.push(this); return this; },
      clearLayout() { this.cleared++; },
      rerenderTiles() { this.rerendered++; },
    };
    pm.made.push(layer);
    return layer;
  };
  return pm;
}

// the stylesheet's tokens of one theme (`:root` block, or the dark media block's)
function tokens(dark) {
  const css = readFileSync(repoFile("src/velometer/app/static/app.css"), "utf8");
  const block = dark
    ? css.match(/@media \(prefers-color-scheme: dark\)\s*\{\s*:root[^{]*\{([^}]*)\}/)[1]
    : css.match(/:root\s*\{([^}]*)\}/)[1];
  return Object.fromEntries([...block.matchAll(/(--[\w-]+):\s*(#[0-9a-f]{6})/g)].map((m) => [m[1], m[2]]));
}
const THEME = { light: tokens(false), dark: tokens(true) };
const FLAVOURS = {
  light: flavour((n) => THEME.light[n] ?? ""),
  dark: flavour((n) => THEME.dark[n] ?? ""),
};

// matchMedia for the dark query, flippable; `flip` calls the change listeners
function fakeMedia(dark) {
  const listeners = new Set();
  const q = {
    matches: dark,
    addEventListener: (_, f) => listeners.add(f),
    removeEventListener: (_, f) => listeners.delete(f),
  };
  const mm = (query) => {
    assert.equal(query, "(prefers-color-scheme: dark)");
    return q;
  };
  mm.flip = () => { q.matches = !q.matches; listeners.forEach((f) => f()); };
  // the stylesheet as the page reads it: the token block of the scheme the query matches
  mm.read = (name) => THEME[q.matches ? "dark" : "light"][name] ?? "";
  return mm;
}

function fetchAnswering(status, calls = []) {
  return (url, init) => {
    calls.push([url, init]);
    return Promise.resolve({ ok: status >= 200 && status < 300, status });
  };
}

// every console method a test must leave silent
function silence(t) {
  const said = [];
  for (const m of ["error", "warn", "log", "info", "debug"]) {
    t.mock.method(console, m, (...args) => said.push([m, ...args]));
  }
  return said;
}

test("a missing tile file: no layer, nothing logged, the OSM credit stays", async (t) => {
  const said = silence(t);
  for (const status of [404, 403, 500, 204]) {
    const map = fakeMap();
    const pm = fakePm();
    const layer = await addBasemap(map, CFG, fakeMedia(false), { fetch: fetchAnswering(status), pm, read: fakeMedia(false).read });
    assert.equal(layer, null, String(status));
    assert.equal(pm.made.length, 0);
    assert.deepEqual(map.credits, [credits(CFG).data]);
  }
  assert.deepEqual(said, []);
});

test("an unreachable tile file (fetch rejects): no layer, nothing logged", async (t) => {
  const said = silence(t);
  const map = fakeMap();
  const pm = fakePm();
  const fetch = () => Promise.reject(new TypeError("Failed to fetch"));
  assert.equal(await addBasemap(map, CFG, fakeMedia(false), { fetch, pm }), null);
  assert.equal(pm.made.length, 0);
  assert.deepEqual(said, []);
});

test("a header that cannot be read (no byte ranges): no layer, nothing logged", async (t) => {
  const said = silence(t);
  const pm = fakePm({ header: Promise.reject(new Error("no byte serving")) });
  const map = fakeMap();
  assert.equal(await addBasemap(map, CFG, fakeMedia(false), { fetch: fetchAnswering(200), pm }), null);
  assert.equal(pm.made.length, 0);
  assert.deepEqual(said, []);
});

test("a vendored library that throws: no layer, no rejection, nothing logged", async (t) => {
  const said = silence(t);
  for (const where of ["leafletLayer", "paintRules", "labelRules", "addTo"]) {
    const map = fakeMap();
    const pm = fakePm();
    if (where === "addTo") {
      const make = pm.leafletLayer;
      pm.leafletLayer = (o) => ({ ...make(o), addTo() { throw new Error("addTo"); } });
    } else {
      pm[where] = () => { throw new TypeError(where); };
    }
    const layer = await addBasemap(map, CFG, fakeMedia(false), {
      fetch: fetchAnswering(200), pm, read: fakeMedia(false).read,
    });
    assert.equal(layer, null, where);
    assert.deepEqual(map.credits, [credits(CFG).data], where);
  }
  assert.deepEqual(said, []);
});

test("a config without tiles asks nothing and draws no layer", async () => {
  const calls = [];
  const map = fakeMap();
  const out = await addBasemap(map, { links: CFG.links }, fakeMedia(false), {
    fetch: fetchAnswering(200, calls),
    pm: fakePm(),
  });
  assert.equal(out, null);
  assert.deepEqual(calls, []);
  assert.deepEqual(map.credits, [credits(CFG).data]);
});

test("the file answers: one HEAD, then the vector layer over the extract's zoom range", async () => {
  for (const status of [200, 206]) {
    const calls = [];
    const map = fakeMap();
    const pm = fakePm({ header: Promise.resolve({ maxZoom: 13 }) });
    const mm = fakeMedia(false);
    const layer = await addBasemap(map, CFG, mm, {
      fetch: fetchAnswering(status, calls),
      pm,
      lang: "de",
      read: mm.read,
    });
    assert.deepEqual(calls, [[CFG.tiles, { method: "HEAD" }]]);
    assert.equal(map.layers.length, 1);
    assert.equal(layer, map.layers[0]);
    assert.equal(layer.url.url, CFG.tiles); // the PMTiles object whose header was read
    assert.equal(layer.maxDataZoom, 13); // overzoomed beyond the extract (R12)
    assert.equal(layer.maxZoom, 19);
    assert.deepEqual(layer.paintRules, { paint: FLAVOURS.light });
    assert.deepEqual(layer.labelRules, { label: FLAVOURS.light, lang: "de" });
    assert.equal(layer.backgroundColor, FLAVOURS.light.background);
    assert.equal(layer.attribution, credits(CFG).basemap);
    assert.deepEqual(map.credits, [credits(CFG).data]);
  }
});

test("the dark theme draws the dark flavour and a theme change swaps it in place", async () => {
  // `mm.read` stands in for the stylesheet: in the page the CSS media query picks the token block
  // (light or dark); addBasemap only reads the tokens again on a change, it never picks a theme
  const mm = fakeMedia(true);
  const map = fakeMap();
  const pm = fakePm();
  const layer = await addBasemap(map, CFG, mm, {
    fetch: fetchAnswering(200),
    pm,
    lang: "en",
    read: mm.read,
  });
  assert.deepEqual(layer.paintRules, { paint: FLAVOURS.dark });
  assert.equal(layer.backgroundColor, FLAVOURS.dark.background);
  mm.flip();
  assert.deepEqual(layer.paintRules, { paint: FLAVOURS.light });
  assert.deepEqual(layer.labelRules, { label: FLAVOURS.light, lang: "en" });
  assert.equal(layer.backgroundColor, FLAVOURS.light.background);
  assert.equal(layer.cleared, 1); // labels laid out again in the new colours
  assert.equal(layer.rerendered, 1);
  assert.equal(pm.made.length, 1); // the same layer: no tile is fetched again
});

test("the flavour is read from the --map-* tokens, defined in both themes", () => {
  for (const name of ["light", "dark"]) {
    for (const r of ROLES) assert.match(THEME[name][`--map-${r}`] ?? "", /^#[0-9a-f]{6}$/, `${name} --map-${r}`);
  }
  assert.notDeepEqual(FLAVOURS.light, FLAVOURS.dark);
  assert.equal(FLAVOURS.dark.earth, THEME.dark["--map-earth"]);
});

test("the credit names OpenStreetMap contributors (linked), Protomaps and ESA WorldCover", () => {
  const c = credits(CFG);
  assert.match(c.data, /OpenStreetMap/);
  assert.ok(c.data.includes(`<a href="${CFG.links.copyright}">`));
  assert.match(c.basemap, /Protomaps/);
  // the extract carries the landcover layer (R11): credited although it is never drawn
  assert.ok(c.basemap.includes("ESA WorldCover (CC BY 4.0)"));
  assert.match(`${c.data}, ${c.basemap}`, /OpenStreetMap.*Protomaps/);
});

// ---- the flavours ----

// the vendored bundle's rule builders, run in a sandbox: they name every flavour key they read
function vendoredRules() {
  const src = readFileSync(repoFile("src/velometer/app/static/vendor/protomaps-leaflet.js"), "utf8");
  const ctx = { console, URL, TextDecoder, setTimeout };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  return ctx.protomapsL;
}

function keysRead(fn) {
  const code = fn.toString();
  const param = code.match(/^\s*(?:function\s*\w*\s*)?\(?\s*([A-Za-z_$][\w$]*)/)[1];
  return new Set([...code.matchAll(new RegExp(`\\b${param.replace("$", "\\$")}\\.([A-Za-z_]\\w*)`, "g"))]
    .map((m) => m[1]));
}

test("each flavour has every key the vendored rules read, and no landcover", () => {
  const pm = vendoredRules();
  const keys = new Set([...keysRead(pm.paintRules), ...keysRead(pm.labelRules)]);
  keys.delete("landcover"); // read only to test for it: absent means not drawn (R11)
  assert.ok(keys.size >= 30, `found ${keys.size} keys`);
  for (const [name, f] of Object.entries(FLAVOURS)) {
    assert.ok(!("landcover" in f), name);
    for (const k of keys) assert.ok(typeof f[k] === "string" && f[k], `${name}.${k}`);
    // the vendored builders accept it: no rule paints `undefined`
    assert.ok(pm.paintRules(f).length > 20 && pm.labelRules(f, "en").length > 5, name);
    const layers = pm.paintRules(f).map((r) => r.dataLayer);
    assert.ok(layers.includes("earth") && !layers.includes("landcover"), name);
  }
});

const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
const lum = (hex) => {
  const [r, g, b] = rgb(hex).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

test("the flavours are near-grey: no road or area hue that reads as a tier or a change", () => {
  for (const [name, f] of Object.entries(FLAVOURS)) {
    for (const [k, v] of Object.entries(f)) {
      if (typeof v !== "string") continue;
      assert.match(v, /^#[0-9a-f]{6}$/, `${name}.${k}`);
      const c = rgb(v);
      assert.ok(Math.max(...c) - Math.min(...c) <= 0.06, `${name}.${k} ${v} is too colourful`);
    }
  }
  assert.ok(lum(FLAVOURS.light.earth) > 0.75 && lum(FLAVOURS.dark.earth) < 0.03);
});

// Every fill a line may cross keeps at least 2.5:1; the roads (light) and the ground (dark), the
// lighter and the darker extreme the lines lie on, keep WCAG 1.4.11's 3:1. A road must stand out
// from the ground to be seen at all, so in the light theme the ground is a shade below 3:1 for the
// lightest lines (tiers C and D).
const UNDER = {
  light: { major: 3, earth: 2.5, park_a: 2.5, water: 2.5, hospital: 2.5, buildings: 2.5 },
  dark: { earth: 3, major: 2.5, park_a: 2.5, water: 2.5, hospital: 2.5, buildings: 2.5 },
};

test("the tier, change and marker colours stay readable on the ground in both themes", () => {
  for (const [name, dark] of [["light", false], ["dark", true]]) {
    const tk = tokens(dark);
    const f = FLAVOURS[name];
    const lines = Object.keys(tk).filter((k) => /^--(tier-[a-e]|change-|marker-fill)/.test(k));
    assert.equal(lines.length, 10, name);
    for (const k of lines) {
      for (const [ground, min] of Object.entries(UNDER[name])) {
        const c = contrast(tk[k], f[ground]);
        assert.ok(c >= min, `${name}: ${k} ${tk[k]} on ${ground} ${f[ground]}: ${c.toFixed(2)}`);
      }
    }
  }
});
