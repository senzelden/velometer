import { test } from "node:test";
import assert from "node:assert/strict";
import { fileName, hex, lightOf, pngBlob, selfContained, tableCsv } from "../download.js";

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
      ? { fill: "rgb(163, 161, 154)", "font-size": "11px", "font-weight": "400", opacity: "1" }
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
        getContext: () => ({ drawImage: (...a) => drawn.push(a), fillRect() {}, set fillStyle(v) {} }),
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
