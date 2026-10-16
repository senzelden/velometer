import { test } from "node:test";
import assert from "node:assert/strict";
import { FIXTURE, useLang } from "./strings-fixture.mjs";
import { fileName, fit, glyphOf, hex, lightOf, pngBlob, safeCell, selfContained, slug, tableCsv, wrap } from "../download.js";

// A minimal fake DOM: tagName, attributes ([{name, value}]), children, textContent.
const node = (tagName, attrs = {}, children = [], textContent = "") => ({
  tagName,
  attributes: Object.entries(attrs).map(([name, value]) => ({ name, value })),
  children,
  textContent,
});

const TOKENS = { "--series-1": ["#2a78d6", "#5e98ed"], "--ink": ["#0b0b0b", "#ecebe6"], "--axis": ["#6b6a66", "#a3a19a"] };
const META = {
  title: "Headline over time, Berlin",
  source: "velometer · OSM 2026-10-03 · classifier v4 · abc1234",
  attribution: "Map data © OpenStreetMap contributors, ODbL 1.0",
};

const chart = () =>
  node("svg", { class: "chart-svg", viewBox: "0 0 400 200", width: "400", height: "200", style: "x:y" }, [
    node("path", { class: "line", d: "M0 0L10 10", stroke: "var(--series-1)", "data-x": "1" }),
    node("text", { class: "axis-t", x: "5", y: "9" }, [], "2018 < 2019"),
    node("g", { class: "hover", style: "display:none" }, [node("circle", { r: "3" })]),
  ]);

// the computed style of a page in the dark theme
const darkStyle = (el) =>
  el.tagName === "path"
    ? { fill: "none", stroke: "rgb(94, 152, 237)", "stroke-width": "2", opacity: "1" }
    : el.tagName === "text"
      ? { fill: "rgb(163, 161, 154)", "font-size": "11px", "font-weight": "600", "text-anchor": "end", opacity: "1" }
      : el.tagName === "g"
        ? { display: "none" }
        : { fill: "rgb(0, 0, 0)", opacity: "1" };

test("hex: rgb(), #abc and #aabbcc become #aabbcc; anything else is null", () => {
  assert.equal(hex("rgb(26, 102, 194)"), "#1a66c2");
  assert.equal(hex("#ABC"), "#aabbcc");
  assert.equal(hex("#1a66c2"), "#1a66c2");
  assert.equal(hex("rgba(1, 2, 3, 0.5)"), null);
  assert.equal(hex("none"), null);
  assert.equal(hex("var(--ink)"), null);
});

test("lightOf maps every dark value to its light value", () => {
  const m = lightOf(TOKENS);
  assert.equal(m.get("#5e98ed"), "#2a78d6");
  assert.equal(m.get("#ecebe6"), "#0b0b0b");
});

test("selfContained: no var(, class= or style=; a dark colour is written as its light value", () => {
  const out = selfContained(chart(), darkStyle, lightOf(TOKENS), META);
  assert.ok(out.startsWith("<svg") || out.startsWith("<?xml"));
  assert.match(out, /xmlns="http:\/\/www\.w3\.org\/2000\/svg"/);
  assert.doesNotMatch(out, /var\(/);
  assert.doesNotMatch(out, / class=/);
  assert.doesNotMatch(out, / style=/);
  assert.doesNotMatch(out, / data-x=/);
  assert.match(out, /stroke="#2a78d6"/); // dark #5e98ed, back to the light series-1
  assert.match(out, /fill="#6b6a66"/); // the axis text
  assert.doesNotMatch(out, /#5e98ed|#a3a19a/);
});

test("selfContained: the title, source line and attribution are text in the image, escaped", () => {
  const out = selfContained(chart(), darkStyle, null, META);
  for (const t of [META.title, META.source, META.attribution]) assert.ok(out.includes(t), t);
  assert.ok(out.includes("2018 &lt; 2019"));
  assert.match(out, /font-family="system-ui, sans-serif"/);
  // an element the page hides is not drawn
  assert.doesNotMatch(out, /<circle/);
});

test("selfContained: the canvas grows to hold the title above and the lines below", () => {
  const out = selfContained(chart(), darkStyle, null, META);
  const [, , w, h] = out.match(/<svg[^>]* viewBox="([^"]+)"/)[1].split(" ").map(Number);
  assert.equal(w, 400);
  assert.ok(h > 200);
});

test("selfContained: with no mapping the page's own colours stay", () => {
  const out = selfContained(chart(), darkStyle, null, META);
  assert.match(out, /stroke="#5e98ed"/);
});

test("tableCsv: two # lines, the header texts, the rows, RFC 4180 quoting", () => {
  const th = (t) => ({ textContent: ` ${t} ` });
  const td = (t) => ({ textContent: t });
  const table = {
    querySelectorAll: (q) =>
      q === "thead th"
        ? [th("Year"), th("Headline, km")]
        : q === "tbody tr"
          ? [
              { querySelectorAll: () => [td("2018"), td('a "b" c')] },
              { querySelectorAll: () => [td("2019"), td("12,3 ⚑")] },
            ]
          : [],
  };
  const lines = tableCsv(table, "abc1234", "2026-10-11T10:00:00Z").split("\r\n");
  assert.match(lines[0], /^# Map data © OpenStreetMap contributors, ODbL 1\.0/);
  assert.equal(lines[1], "# velometer abc1234 generated 2026-10-11T10:00:00Z");
  assert.equal(lines[2], 'Year,"Headline, km"');
  assert.equal(lines[3], '2018,"a ""b"" c"');
  assert.equal(lines[4], '2019,"12,3 ⚑"');
});

test("fileName: an ASCII slug velometer-<page>-<chart>[-<state>].<ext>", () => {
  const n = fileName("city berlin", "tiers", "kind=fua", "svg");
  assert.match(n, /^[\x20-\x7e]+$/);
  assert.equal(n, "velometer-city-berlin-tiers-kind-fua.svg");
  assert.equal(fileName("Über/Köln", "x", "", "png"), "velometer-uber-koln-x.png");
});

test("pngBlob: draws the SVG at 2x on a canvas and resolves with its PNG blob", async () => {
  const drawn = [];
  const doc = {
    createElement: (t) => {
      assert.equal(t, "canvas");
      return {
        getContext: () => ({ drawImage: (...a) => drawn.push(a) }), // no fillRect: the SVG draws its own ground
        toBlob(cb, type) { cb({ type, size: 9 }); },
      };
    },
  };
  const Img = class { set src(v) { this.s = v; assert.match(v, /^data:image\/svg\+xml;charset=utf-8,/); queueMicrotask(() => this.onload()); } };
  const blob = await pngBlob("<svg/>", 400, 200, 2, doc, Img);
  assert.equal(blob.type, "image/png");
  assert.equal(drawn.length, 1);
});

test("pngBlob rejects when the image fails to load", async () => {
  const doc = { createElement: () => ({ getContext: () => ({}), toBlob() {} }) };
  const Img = class { set src(v) { queueMicrotask(() => this.onerror(new Error("x"))); } };
  await assert.rejects(pngBlob("<svg/>", 4, 2, 2, doc, Img));
});

test("selfContained: the ground and the added text take the light colours the caller passes", () => {
  const out = selfContained(chart(), darkStyle, null, { ...META, ground: "#fafafa", ink: "#101010", muted: "#505050" });
  assert.match(out, /<rect[^>]*fill="#fafafa"/);
  assert.match(out, /font-weight="600" fill="#101010"/);
  assert.match(out, /fill="#505050">velometer/);
});

test("selfContained: a text keeps its anchor, font size and weight as attributes", () => {
  const out = selfContained(chart(), darkStyle, null, META);
  const t = out.match(/<text x="5"[^>]*>/)[0];
  assert.match(t, /text-anchor="end"/);
  assert.match(t, /font-size="11px"/);
  assert.match(t, /font-weight="600"/);
});

test("selfContained: a colour with alpha keeps its rgb and writes the alpha as an opacity", () => {
  const style = (el) => (el.tagName === "path" ? { fill: "rgba(94, 152, 237, 0.4)", stroke: "rgb(94 152 237 / 50%)", opacity: "1" } : {});
  const out = selfContained(chart(), style, lightOf(TOKENS), META);
  const p = out.match(/<path[^>]*>/)[0];
  assert.match(p, /fill="#2a78d6"/);
  assert.match(p, /fill-opacity="0\.4"/);
  assert.match(p, /stroke="#2a78d6"/);
  assert.match(p, /stroke-opacity="0\.5"/);
  // fully transparent is no fill at all
  const none = selfContained(chart(), () => ({ fill: "rgba(0, 0, 0, 0)" }), null, META);
  assert.match(none, /<path[^>]* fill="none"/);
});

test("selfContained: a chart's HTML key is drawn as swatches and labels in light colours", () => {
  const key = [
    { colour: "rgb(94, 152, 237)", text: "A separated track" },
    { colour: "rgb(163, 161, 154)", text: "B shared foot/cycle path" },
  ];
  const out = selfContained(chart(), darkStyle, lightOf(TOKENS), { ...META, key });
  assert.ok(out.includes("A separated track") && out.includes("B shared foot/cycle path"));
  assert.match(out, /<rect x="8"[^>]*fill="#2a78d6"/);
  assert.match(out, /<rect[^>]*fill="#6b6a66"/);
  const [, , , h] = out.match(/viewBox="([^"]+)"/)[1].split(" ").map(Number);
  const plain = selfContained(chart(), darkStyle, null, META).match(/viewBox="([^"]+)"/)[1].split(" ")[3];
  assert.ok(h > +plain, "the key makes room for itself");
  // the key sits above the source line
  assert.ok(out.indexOf("A separated track") < out.indexOf(META.source));
});

test("selfContained: a long key wraps to a second row", () => {
  const key = Array.from({ length: 12 }, (_, i) => ({ colour: "rgb(94, 152, 237)", text: `Tier number ${i}` }));
  const out = selfContained(chart(), darkStyle, null, { ...META, key });
  const ys = new Set([...out.matchAll(/<rect x="\d+" y="(\d+)" width="10"/g)].map((m) => m[1]));
  assert.ok(ys.size >= 2);
});

test("selfContained: the key wraps by each chip's measured width when the page gave one", () => {
  const rows = (key) =>
    new Set([...selfContained(chart(), darkStyle, null, { ...META, key }).matchAll(/<rect x="[\d.]+" y="([\d.]+)" width="10"/g)].map((m) => m[1])).size;
  const long = "x".repeat(40); // estimated at 6.6 px a character: two of these do not fit in 400 px
  assert.equal(rows([{ colour: "red", text: long }, { colour: "red", text: long }]), 2, "estimated");
  assert.equal(rows([{ colour: "red", text: long, width: 60 }, { colour: "red", text: long, width: 60 }]), 1, "measured narrow");
  assert.equal(rows([{ colour: "red", text: "A", width: 300 }, { colour: "red", text: "B", width: 300 }]), 2, "measured wide");
});

test("safeCell: formula starters get a quote, a plain number does not", () => {
  for (const bad of ["=1+1", "+cmd", "@SUM(A1)", "\tx", "\rx", "-cmd|' /C calc'!A0", "-1+1", "--x", "--", "- "])
    assert.equal(safeCell(bad), `'${bad}`, bad);
  for (const ok of ["-3.2", "-1,639.8", "-0", "12", "abc", "a=b", "", "2018"]) assert.equal(safeCell(ok), ok, ok);
});

test("safeCell: a lone dash is a no-data mark, not a formula, and keeps no quote", () => {
  for (const mark of ["-", "\u2013", "\u2014", "\u2212"]) assert.equal(safeCell(mark), mark, JSON.stringify(mark));
});

test("tableCsv: a cell that would run as a formula is quoted off in header and body", () => {
  const c = (t) => ({ textContent: t });
  const table = {
    querySelectorAll: (q) =>
      q === "thead th" ? [c("=HEAD()")] : q === "tbody tr" ? [{ querySelectorAll: () => [c('=HYPERLINK("x")')] }, { querySelectorAll: () => [c("-3.2")] }] : [],
  };
  const lines = tableCsv(table, "abc", "t").split("\r\n");
  assert.equal(lines[2], "'=HEAD()");
  assert.equal(lines[3], `"'=HYPERLINK(""x"")"`);
  assert.equal(lines[4], "-3.2");
});

// ---- M12: German downloads ----

/** A table fake: header texts and rows of cell texts. */
const tableOf = (head, rows) => ({
  querySelectorAll: (q) =>
    q === "thead th"
      ? head.map((t) => ({ textContent: ` ${t} ` }))
      : q === "tbody tr"
        ? rows.map((r) => ({ querySelectorAll: () => r.map((t) => ({ textContent: t })) }))
        : [],
});

test("slug: ß is ss before the accents go; a German title gives an ASCII name", () => {
  assert.equal(slug("Straße"), "strasse");
  assert.equal(slug("Größe"), "grosse");
  const n = fileName("Krakau: Zeitverlauf", "Stufen", "kind=fua", "png");
  assert.match(n, /^[\x20-\x7e]+$/);
  assert.ok(n.startsWith("velometer-krakau"), n);
  assert.equal(n, "velometer-krakau-zeitverlauf-stufen-kind-fua.png");
});

test("tableCsv in German: the header as shown, number cells as machine numbers, the preamble English", () => {
  useLang("de");
  const table = tableOf(["Jahr", "A+B km"], [["2019", "1.639,8", "12,3 ⚑"], ["2020", "\u22123,2", "–"]]);
  const lines = tableCsv(table, "abc1234", "2026-10-12T10:00:00Z", "de-DE").split("\r\n");
  assert.equal(lines[0], "# Map data © OpenStreetMap contributors, ODbL 1.0 — OSM mapped km, not built km");
  assert.equal(lines[1], "# velometer abc1234 generated 2026-10-12T10:00:00Z");
  assert.equal(lines[2], "Jahr,A+B km");
  assert.equal(lines[3], '2019,1639.8,"12,3 ⚑"');
  assert.equal(lines[4], "2020,-3.2,–");
  useLang("en");
});

test("tableCsv in English converts nothing: no locale is en-GB, and a grouped number stays as shown", () => {
  // "1.639" and "12,345" also read as German numbers (1639 and 12.345): English must keep them
  const table = tableOf(
    ["Year", "Headline, km"],
    [["2018", "1,639.8"], ["2019", "12,3 ⚑"], ["2020", "1.639"], ["2021", "12,345"]],
  );
  const plain = tableCsv(table, "abc1234", "2026-10-11T10:00:00Z");
  assert.equal(plain, tableCsv(table, "abc1234", "2026-10-11T10:00:00Z", "en-GB"));
  const lines = plain.split("\r\n");
  assert.equal(lines[3], '2018,"1,639.8"');
  assert.equal(lines[4], '2019,"12,3 ⚑"');
  assert.equal(lines[5], "2020,1.639");
  assert.equal(lines[6], '2021,"12,345"');
});

test("the SVG source line on a German page has the German note and attribution", () => {
  useLang("de");
  const out = selfContained(chart(), darkStyle, null, { ...META, attribution: FIXTURE.de["js.download.attribution"] });
  assert.ok(out.includes(FIXTURE.de["js.download.note"]), out);
  assert.ok(out.includes("OpenStreetMap-Mitwirkende"));
  assert.notEqual(FIXTURE.de["js.download.note"], FIXTURE.en["js.download.note"]);
  assert.ok(!out.includes(FIXTURE.en["js.download.note"]));
  useLang("en");
});

test("tableCsv in German: formula-shaped header and cells are quoted off, converted numbers are not", () => {
  useLang("de");
  const table = tableOf(
    ["=Jahr", "+A km"],
    [
      ["@SUMME(A1)", "=HYPERLINK(\"x\")"],
      ["-1,5 ⚑", "−1,5"],
      ["-1.639,8", "+1,5"],
      ["=1+1", "-x"],
    ],
  );
  const lines = tableCsv(table, "abc", "t", "de-DE").split("\r\n");
  assert.equal(lines[2], "'=Jahr,'+A km");
  assert.equal(lines[3], `'@SUMME(A1),"'=HYPERLINK(""x"")"`);
  assert.equal(lines[4], `"'-1,5 ⚑",-1.5`); // the U+2212 number converts to a plain negative
  assert.equal(lines[5], "-1639.8,1.5"); // a signed German number converts; nothing left to run
  assert.equal(lines[6], "'=1+1,'-x");
  useLang("en");
});

// ---- the plan and Counts keys in the image (M13 Task 13a: M11-8, user review) ----

// the computed style of a key mark (`<span class="key key-...">`) as app.css draws it, dark theme;
// with border-box sizing a line mark's computed height is its border's (the render check found
// the lines drawn as swatches when the rule read height 0)
const MARK = {
  target: { borderTopStyle: "dashed", borderBottomStyle: "none", borderTopColor: "rgb(163, 161, 154)", borderRadius: "0px", backgroundColor: "rgba(0, 0, 0, 0)", height: "2px" },
  current: { borderTopStyle: "solid", borderBottomStyle: "solid", borderTopColor: "rgb(94, 152, 237)", borderRadius: "50%", backgroundColor: "rgba(0, 0, 0, 0)", height: "12px" },
  revision: { borderTopStyle: "solid", borderBottomStyle: "solid", borderTopColor: "rgb(94, 152, 237)", borderRadius: "50%", backgroundColor: "rgb(236, 235, 230)", height: "12px" },
  projects: { borderTopStyle: "solid", borderBottomStyle: "solid", borderTopColor: "rgb(163, 161, 154)", borderRadius: "0px", backgroundColor: "rgba(0, 0, 0, 0)", height: "12px" },
  mapped: { borderTopStyle: "solid", borderBottomStyle: "none", borderTopColor: "rgb(94, 152, 237)", borderRadius: "0px", backgroundColor: "rgba(0, 0, 0, 0)", height: "3px" },
};

test("glyphOf: a key mark's computed style says its glyph: line, dashed line, dot, ring or swatch", () => {
  assert.deepEqual(glyphOf(MARK.target), { shape: "dash", colour: "rgb(163, 161, 154)" });
  assert.deepEqual(glyphOf(MARK.mapped), { shape: "line", colour: "rgb(94, 152, 237)" });
  assert.deepEqual(glyphOf(MARK.current), { shape: "dot", colour: "rgb(94, 152, 237)" });
  assert.deepEqual(glyphOf(MARK.revision), { shape: "ring", colour: "rgb(94, 152, 237)", fill: "rgb(236, 235, 230)" });
  assert.deepEqual(glyphOf(MARK.projects), { shape: "swatch", colour: "rgb(163, 161, 154)" });
  // a mark coloured by its ground (no border) is a swatch of that ground
  assert.deepEqual(glyphOf({ borderTopStyle: "none", borderTopColor: "rgb(0, 0, 0)", borderRadius: "0px", backgroundColor: "rgb(1, 2, 3)", height: "12px" }),
    { shape: "swatch", colour: "rgb(1, 2, 3)" });
});

test("selfContained: line, dashed, dot and ring key glyphs are drawn as such, in light colours", () => {
  const key = Object.entries(MARK).map(([k, st]) => ({ ...glyphOf(st), text: `key ${k}` }));
  const out = selfContained(chart(), darkStyle, lightOf({ ...TOKENS, "--surface": ["#ffffff", "#ecebe6"] }), { ...META, key });
  const g = out.match(/<g id="velometer-key">(.*?)<\/g>/)[1];
  for (const k of Object.keys(MARK)) assert.ok(g.includes(`key ${k}`), k);
  assert.match(g, /<line[^>]*stroke="#6b6a66"[^>]*stroke-dasharray="[^"]+"/, "the target's dashed line");
  assert.match(g, /<line(?![^>]*dasharray)[^>]*stroke="#2a78d6"/, "the mapped line, solid");
  assert.match(g, /<circle[^>]*fill="#2a78d6"(?![^>]*stroke=)/, "the current figure's dot");
  assert.match(g, /<circle[^>]*fill="#ffffff"[^>]*stroke="#2a78d6"/, "the revision's ring, on the light ground");
  assert.match(g, /<rect[^>]*fill="#6b6a66"/, "the projects' swatch");
  assert.doesNotMatch(g, /rgb\(|NaN/);
});

test("selfContained: a key label wider than the image wraps inside the image", () => {
  const text = "mapped on the network, mapped km since 1 Jan 2022 (ours; a line, one point per OpenStreetMap snapshot, the last at the current snapshot)";
  for (const w of [400, 300]) {
    const svg = node("svg", { viewBox: `0 0 ${w} 200` }, []);
    const out = selfContained(svg, darkStyle, null, { ...META, key: [{ shape: "line", colour: "rgb(1, 2, 3)", text }] });
    const g = out.match(/<g id="velometer-key">(.*?)<\/g>/)[1];
    const lines = [...g.matchAll(/<text x="([\d.]+)"[^>]*>([^<]*)<\/text>/g)].map((m) => [Number(m[1]), m[2]]);
    assert.ok(lines.length >= 2, `${w}: wrapped`);
    assert.equal(lines.map((l) => l[1]).join(" "), text.replace(/&/g, "&amp;"));
    for (const [x, s] of lines) assert.ok(x + s.length * 6.6 <= w, `${w}: "${s}" ends at ${x + s.length * 6.6}`);
    // the source line stays below the wrapped key
    const ys = [...g.matchAll(/<text x="[\d.]+" y="([\d.]+)"/g)].map((m) => Number(m[1]));
    const src = Number(out.match(/<g id="velometer-meta"><text x="8" y="([\d.]+)"/)[1]);
    assert.ok(Math.max(...ys) + 8 <= src, `key ends at ${Math.max(...ys)}, source at ${src}`);
  }
});

// M13 Task 13b: at phone width the title and the two meta lines wrap inside the image
const LONG = {
  ...META,
  title: "Vorrangnetz (ohne Radschnellverbindungen): Zielvorgaben je Jahr, gemeldete Kilometer und kartierte Kilometer",
  source: "velometer · OSM-Stand 2026-10-03 · Klassifikator v4 · 64759cb-dirty",
  attribution: "Kartendaten © OpenStreetMap-Mitwirkende, ODbL 1.0",
};
const textsOf = (s) => [...s.matchAll(/<text x="([\d.]+)" y="([\d.]+)" font-size="([\d.]+)px"[^>]*>([^<]*)<\/text>/g)]
  .map((m) => ({ x: Number(m[1]), y: Number(m[2]), size: Number(m[3]), text: m[4] }));

test("selfContained: a title and meta lines wider than the image wrap inside it (390 px)", () => {
  useLang("de");
  const svg = node("svg", { viewBox: "0 0 390 200" }, []);
  const out = selfContained(svg, darkStyle, null, LONG);
  const [, , w, h] = out.match(/<svg[^>]* viewBox="([^"]+)"/)[1].split(" ").map(Number);
  const head = out.split("<g transform=")[0];
  const meta = out.match(/<g id="velometer-meta">(.*?)<\/g>/)[1];
  const title = textsOf(head);
  const lines = textsOf(meta);
  assert.ok(title.length >= 2, "the title wraps");
  assert.equal(title.map((l) => l.text).join(" "), LONG.title);
  const full = `${LONG.attribution} · ${FIXTURE.de["js.download.note"]}`;
  assert.equal(lines.map((l) => l.text).join(" "), `${LONG.source} ${full}`.replace(/&/g, "&amp;"));
  // every line fits by the estimate: 0.6 em a character (bold title 0.62 em)
  for (const l of [...title, ...lines]) {
    const per = l.size === 15 ? 15 * 0.62 : 6.6;
    assert.ok(l.x + l.text.length * per <= w, `"${l.text}" ends at ${l.x + l.text.length * per}`);
  }
  // the chart moves down below the last title line, and the meta lines stay inside the canvas
  const top = Number(out.match(/<g transform="translate\(0,([\d.]+)\)">/)[1]);
  assert.ok(Math.max(...title.map((l) => l.y)) + 8 <= top, `title ends ${Math.max(...title.map((l) => l.y))}, chart at ${top}`);
  assert.ok(Math.min(...lines.map((l) => l.y)) - 11 >= top + 200);
  assert.ok(Math.max(...lines.map((l) => l.y)) + 4 <= h, "the last line is inside the image");
  useLang("en");
});

test("selfContained: the title and meta lines wrap by the width the page measured", () => {
  const svg = node("svg", { viewBox: "0 0 390 200" }, []);
  const short = { ...META, title: "Headline", source: "velometer", attribution: "OSM" };
  const count = (measure) => textsOf(selfContained(svg, darkStyle, null, { ...short, measure })).length;
  const plain = count(undefined);
  assert.equal(plain, 3); // one title line, the source and the attribution
  // a page that measures every text as very wide breaks each into one word a line
  const wide = count((text) => text.length * 100);
  assert.ok(wide > plain, `${wide} lines with a wide measure`);
  // a measure the page could not take (null) falls back to the estimate
  assert.equal(count(() => null), plain);
});

test("selfContained: a short title and meta lines keep the one-line layout", () => {
  const out = selfContained(node("svg", { viewBox: "0 0 800 200" }, []), darkStyle, null, META);
  assert.match(out, /<g transform="translate\(0,30\)">/);
  assert.equal(textsOf(out.match(/<g id="velometer-meta">(.*?)<\/g>/)[1]).length, 2);
});

// M14 Task 7: a title wraps by the measured width of each candidate line
const glyph = (ch) => ("WÄ".includes(ch) ? 14 : ch === "i" ? 4 : 8);
const stub = (s) => [...s].reduce((n, ch) => n + glyph(ch), 0);
const WIDE = "WWWW ÄÖÜ WWW iii WWWW ÄÄ iiii WWWW WWW";

test("wrap: no line of several words is wider than the room by the measure", () => {
  const room = 120;
  const lines = wrap(WIDE, stub, room);
  assert.ok(lines.length >= 2);
  assert.equal(lines.join(" "), WIDE);
  for (const l of lines.filter((l) => l.includes(" "))) assert.ok(stub(l) <= room, `"${l}" is ${stub(l)} px`);
});

test("wrap: one word wider than the room stays whole on its own line", () => {
  const lines = wrap("ab WWWWWWWWWWWWWWWW cd", stub, 100);
  assert.deepEqual(lines, ["ab", "WWWWWWWWWWWWWWWW", "cd"]);
  assert.ok(stub(lines[1]) > 100);
});

test("fit: a text that fits is one line; one that does not wraps by the measure", () => {
  assert.deepEqual(fit("iii iii", stub, 200), ["iii iii"]);
  assert.ok(fit(WIDE, stub, 120).length >= 2);
});

test("selfContained: without a measure a plain ASCII title wraps as it did before M14", () => {
  const svg = node("svg", { viewBox: "0 0 300 200" }, []);
  const title = "Cycling infrastructure growth across the whole region compared with last year";
  const out = selfContained(svg, darkStyle, null, { ...META, title });
  // recorded from the pre-change code (average 15 * 0.62 px a character)
  assert.deepEqual(textsOf(out.split("<g transform=")[0]).map((l) => l.text), [
    "Cycling infrastructure growth",
    "across the whole region",
    "compared with last year",
  ]);
});

test("selfContained: title lines are wrapped by the measure the page gave", () => {
  const svg = node("svg", { viewBox: "0 0 300 200" }, []);
  const measure = (text) => stub(text) * 15 / 8;
  const out = selfContained(svg, darkStyle, null, { ...META, title: WIDE, measure });
  const lines = textsOf(out.split("<g transform=")[0]).map((l) => l.text);
  assert.ok(lines.length >= 2);
  for (const l of lines.filter((l) => l.includes(" "))) assert.ok(measure(l) <= 300 - 16, `"${l}"`);
});

// M14 Task 7: a key label wraps by the page's measure of the key font, not the chip's average
test("selfContained: a long key label wraps by the width the page measured for the key font", () => {
  const text = Array.from({ length: 24 }, (_, i) => `w${i}xx`).join(" ");
  const svg = node("svg", { viewBox: "0 0 300 200" }, []);
  // the chip was measured wide (the page's own label), so it wraps; the page's 11px measure is
  // narrower than the chip's average character, so lines hold more words by it
  const chip = { shape: "line", colour: "rgb(1, 2, 3)", text, width: text.length * 9 };
  const keyLines = (measure) => {
    const out = selfContained(svg, darkStyle, null, { ...META, key: [chip], measure });
    const g = out.match(/<g id="velometer-key">(.*?)<\/g>/)[1];
    return [...g.matchAll(/<text x="([\d.]+)"[^>]*>([^<]*)<\/text>/g)].map((m) => [Number(m[1]), m[2]]);
  };
  const sizes = [];
  const measure = (s, size) => {
    sizes.push(size);
    return s.length * 5;
  };
  const byPage = keyLines(measure);
  const byChip = keyLines(undefined);
  assert.ok(byPage.length >= 2, "wrapped");
  assert.equal(byPage.map((l) => l[1]).join(" "), text);
  assert.ok(sizes.includes("11px"), "the key is measured in the key font");
  for (const [x, s] of byPage) assert.ok(x + measure(s, "11px") <= 300, `"${s}" ends at ${x + s.length * 5}`);
  // a line can hold more than the chip's average would allow: the page's measure decided
  assert.ok(byPage.length < byChip.length, `${byPage.length} lines by the page, ${byChip.length} by the chip`);
});
