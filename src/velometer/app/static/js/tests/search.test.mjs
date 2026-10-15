import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import "./strings-fixture.mjs";
import { fold, rank, move, keyAction } from "../search.js";
import { repoFile } from "./repo.mjs";

const e = (label, kind, terms = [label]) => ({ label, kind, url: "/x", terms });
const idx = [
  e("Wrocław (Poland)", "city", ["Wrocław", "wroclaw"]),
  e("Kraków (Poland)", "city", ["Kraków", "krakow", "Cracow"]),
  e("Wien (Austria)", "city", ["Wien", "vienna", "Vienna"]),
  e("København (Denmark)", "city", ["København", "copenhagen", "Copenhagen"]),
  e("Poland", "country", ["Poland", "pl"]),
  e("Cities", "page"),
  e("City story: Berlin", "story"),
  e("Why the figures differ", "page"),
  e("Compare", "page"),
  e("Clean Cities Campaign", "organisation"),
];

test("fold strips diacritics, handles letters that do not decompose, lowercases and trims", () => {
  assert.equal(fold("  Kraków "), "krakow");
  assert.equal(fold("Wrocław"), "wroclaw");
  assert.equal(fold("København"), "kobenhavn");
  assert.equal(fold("Straße"), "strasse");
  assert.equal(fold("Why   THE  figures"), "why the figures");
});

test("an empty query ranks nothing", () => {
  assert.deepEqual(rank(idx, ""), []);
  assert.deepEqual(rank(idx, "   "), []);
});

test("krakow finds Kraków first, vienna finds Wien, wroclaw finds Wrocław", () => {
  assert.ok(rank(idx, "krakow")[0].label.startsWith("Kraków"));
  assert.equal(rank(idx, "  VIENNA ")[0].label, "Wien (Austria)");
  assert.equal(rank(idx, "wroclaw")[0].label, "Wrocław (Poland)");
  assert.equal(rank(idx, "cracow")[0].label, "Kraków (Poland)");
});

test("no match is an empty list", () => {
  assert.deepEqual(rank(idx, "zzz"), []);
});

test("every query word must match: two-word queries find the page", () => {
  assert.equal(rank(idx, "why figures")[0].label, "Why the figures differ");
  assert.deepEqual(rank(idx, "why zzz"), []);
});

test("a prefix match outranks a substring match", () => {
  const got = rank([e("Pre-Compare", "page"), e("Compare", "page")], "comp");
  assert.equal(got[0].label, "Compare");
});

test("a city outranks a page with the same prefix", () => {
  const got = rank([e("Cities", "page"), e("Cieszyn (Poland)", "city")], "ci");
  assert.equal(got[0].kind, "city");
});

test("kinds order city, country, page, story, organisation at equal score", () => {
  const same = ["organisation", "story", "page", "country", "city"].map((k) => e("Zed", k));
  assert.deepEqual(rank(same, "zed").map((r) => r.kind), [
    "city", "country", "page", "story", "organisation",
  ]);
});

test("the cap is 8 by default and settable", () => {
  const many = Array.from({ length: 20 }, (_, i) => e(`Town ${i}`, "city"));
  assert.equal(rank(many, "town").length, 8);
  assert.equal(rank(many, "town", 3).length, 3);
});

test("move wraps Down and Up and starts from nothing", () => {
  assert.equal(move(-1, 1, 3), 0);
  assert.equal(move(-1, -1, 3), 2);
  assert.equal(move(2, 1, 3), 0);
  assert.equal(move(0, -1, 3), 2);
  assert.equal(move(0, 1, 0), -1);
});

test("with no match, Down, Up and Enter do nothing and nothing becomes active", () => {
  for (const key of ["ArrowDown", "ArrowUp", "Enter"]) {
    assert.equal(keyAction({ active: -1, count: 0 }, key), null, key);
  }
});

test("keyAction moves with the arrows, wrapping, and Enter picks the active or first option", () => {
  assert.deepEqual(keyAction({ active: -1, count: 3 }, "ArrowDown"), { type: "move", to: 0 });
  assert.deepEqual(keyAction({ active: 2, count: 3 }, "ArrowDown"), { type: "move", to: 0 });
  assert.deepEqual(keyAction({ active: 0, count: 3 }, "ArrowUp"), { type: "move", to: 2 });
  assert.deepEqual(keyAction({ active: 1, count: 3 }, "Enter"), { type: "pick", index: 1 });
  assert.deepEqual(keyAction({ active: -1, count: 3 }, "Enter"), { type: "pick", index: 0 });
  assert.equal(keyAction({ active: -1, count: 3 }, "a"), null);
});

// ---- the DOM part (final review 10, parked: empty query) with a fake page ----
function fakeNode(tag, extra = {}) {
  return {
    tag, hidden: false, attrs: {}, children: [], listeners: {}, value: "", textContent: "",
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return this.attrs[k] ?? null; },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener(t, f) { (this.listeners[t] ??= []).push(f); },
    fire(t, e = {}) { for (const f of this.listeners[t] ?? []) f({ preventDefault() {}, stopPropagation() {}, ...e }); },
    replaceChildren(...n) { this.children = n; },
    append(...n) { this.children.push(...n); },
    contains(n) { return n === this || this.kids?.includes(n); },
    ...extra,
  };
}
function fakePage() {
  const live = fakeNode("div"); // #live, the page's polite live region (live.js)
  const doc = { activeElement: null, listeners: {}, createElement: (t) => fakeNode(t),
    addEventListener(t, f) { (this.listeners[t] ??= []).push(f); },
    getElementById: (id) => (id === "live" ? live : null) }; // fmt: skip
  const focusable = (n) => Object.assign(n, { focus() { if (!this.hidden) doc.activeElement = this; } });
  const input = focusable(fakeNode("input"));
  const list = fakeNode("ul", { hidden: true });
  const status = fakeNode("p");
  const box = fakeNode("div", { hidden: true, kids: [input, list, status] });
  box.querySelector = (s) =>
    s === "input" ? input : s === "[role=listbox]" ? list : s === ".search-status" ? status : null;
  const fallback = focusable(fakeNode("a"));
  doc.querySelector = (s) => (s === ".search" ? box : s === ".search-fallback" ? fallback : null);
  return { doc, box, input, list, status, fallback, live };
}
const settle = () => new Promise((r) => setTimeout(r, 0));

test("when the index fails to load, focus moves from the box to the fallback link", async (t) => {
  const { mount } = await import("../search.js");
  t.mock.method(console, "error", () => {});
  t.mock.method(globalThis, "fetch", async () => ({ ok: false, status: 404 }));
  const { doc, box, input, fallback } = fakePage();
  mount(doc);
  input.focus();
  input.fire("focus");
  await settle();
  await settle();
  assert.equal(box.hidden, true);
  assert.equal(fallback.hidden, false);
  assert.equal(doc.activeElement, fallback, "focus is not dropped to the body");
});

test("clearing the input before the index arrives closes the list", async (t) => {
  const { mount } = await import("../search.js");
  t.mock.method(globalThis, "fetch", () => new Promise(() => {})); // never answers
  const { doc, input, list } = fakePage();
  mount(doc);
  list.hidden = false; // a list left open
  input.setAttribute("aria-expanded", "true");
  input.value = "";
  input.fire("input");
  assert.equal(list.hidden, true);
  assert.equal(input.getAttribute("aria-expanded"), "false");
});

test("a German page loads the index its velometer-search meta names, the German one", async (t) => {
  const { mount } = await import("../search.js");
  const asked = [];
  t.mock.method(globalThis, "fetch", (u) => { asked.push(u); return new Promise(() => {}); });
  const { doc, input } = fakePage();
  const meta = { getAttribute: (k) => (k === "content" ? "/velometer/de/data/search.json" : null) };
  const plain = doc.querySelector;
  doc.querySelector = (s) => (s === 'meta[name="velometer-search"]' ? meta : plain(s));
  mount(doc);
  input.fire("focus");
  assert.deepEqual(asked, ["/velometer/de/data/search.json"]);
});

test("an option shows the entry's kind label (the German index's), else its kind", async (t) => {
  const { mount } = await import("../search.js");
  const index = [
    { label: "Krakau (Polen)", kind: "city", kind_label: "Stadt", url: "/city/krakow", terms: ["Krakau"] },
    { label: "Krakow story", kind: "story", url: "/city/krakow", terms: ["Krakau"] },
  ];
  t.mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => index }));
  const { doc, input, list } = fakePage();
  mount(doc);
  input.value = "krakau";
  input.fire("focus");
  await settle();
  await settle();
  input.fire("input");
  const kinds = list.children.map((li) => li.children[1].textContent);
  assert.deepEqual(kinds, ["Stadt", "story"]);
});

// --- M12: every name form finds its city (tests/city_names.json, kept equal to cities.yaml) ---


const CITY_NAMES = JSON.parse(
  readFileSync(repoFile("tests/city_names.json"), "utf8"),
);
// the letters a reader without them types instead, written out here (not fold's mapping)
const BY_HAND = { ó: "o", ø: "o", ł: "l", ß: "ss", ä: "a", ö: "o", ü: "u", é: "e", á: "a", ř: "r" };
const plain = (s) => [...s].map((c) => BY_HAND[c] ?? BY_HAND[c.toLowerCase()] ?? c).join("");

test("krakau, KRAKOW and kraków all rank Kraków first", () => {
  const krakow = e("Krakau (Polen)", "city", ["Kraków", "Krakau", "Krakow", "Cracow"]);
  const index = [...idx.filter((x) => !x.label.startsWith("Kraków")), krakow];
  for (const q of ["krakau", "KRAKOW", "kraków"]) assert.equal(rank(index, q)[0], krakow, q);
});

test("Weißensee is found by weissensee", () => {
  const w = e("Weißensee", "page", ["Weißensee"]);
  assert.equal(rank([...idx, w], "weissensee")[0], w);
});

test("every name form of every city, plain, upper case and without diacritics, ranks it first", () => {
  // the index as app/search.py builds it: the edition's name first, then the id and every form
  const index = Object.entries(CITY_NAMES).map(([id, names]) => ({
    label: names[0], kind: "city", url: `/city/${id}`, terms: [names[0], id, ...names],
  }));
  assert.ok(index.length > 10 && index.some((x) => x.terms.includes("Krakau")));
  for (const [id, names] of Object.entries(CITY_NAMES)) {
    for (const form of names) {
      for (const q of [form, form.toUpperCase(), plain(form)]) {
        assert.equal(rank(index, q)[0]?.url, `/city/${id}`, `${q} -> ${id}`);
      }
    }
  }
});

// ---- M13 (M11-6): No match is a status outside the listbox; the keys, dispatched ----

/** A mounted search over `index`, the index loaded, `query` typed. */
async function typed(t, index, query) {
  const { mount } = await import("../search.js");
  t.mock.method(globalThis, "fetch", async () => ({ ok: true, json: async () => index }));
  const page = fakePage();
  mount(page.doc);
  page.input.fire("focus");
  await settle();
  await settle();
  page.input.value = query;
  page.input.fire("input");
  return page;
}
const key = (input, k) => {
  let prevented = false;
  input.fire("keydown", { key: k, preventDefault() { prevented = true; } });
  return prevented;
};
const INDEX = [
  { label: "Berlin (Germany)", kind: "city", url: "/city/berlin", terms: ["Berlin"] },
  { label: "Bern (Switzerland)", kind: "city", url: "/city/bern", terms: ["Bern"] },
];

test("no match: the status says so outside the listbox, the list stays closed and empty", async (t) => {
  const { input, list, status } = await typed(t, INDEX, "zzz");
  assert.equal(status.textContent, "No match");
  assert.deepEqual(list.children, [], "a listbox holds options only");
  assert.equal(list.hidden, true);
  assert.equal(input.getAttribute("aria-expanded"), "false");
  assert.equal(key(input, "ArrowDown"), false, "Down does nothing");
  assert.equal(input.getAttribute("aria-activedescendant"), null);
  input.value = "ber";
  input.fire("input");
  assert.equal(status.textContent, "", "a match clears it");
  assert.equal(list.children.length, 2);
});

test("keys: Down and Up move the active option, wrapping; Enter goes to it; Escape closes, then clears", async (t) => {
  const { input, list } = await typed(t, INDEX, "ber");
  assert.equal(list.hidden, false);
  assert.equal(input.getAttribute("aria-expanded"), "true");
  assert.equal(key(input, "ArrowDown"), true);
  assert.equal(input.getAttribute("aria-activedescendant"), "site-search-opt-0");
  key(input, "ArrowDown");
  key(input, "ArrowDown");
  assert.equal(input.getAttribute("aria-activedescendant"), "site-search-opt-0", "wraps");
  key(input, "ArrowUp");
  assert.equal(input.getAttribute("aria-activedescendant"), "site-search-opt-1");
  assert.deepEqual(list.children.map((li) => li.getAttribute("aria-selected")), ["false", "true"]);
  const before = globalThis.location;
  globalThis.location = { href: "" };
  try {
    assert.equal(key(input, "Enter"), true);
    assert.equal(globalThis.location.href, "/city/bern");
  } finally {
    globalThis.location = before;
  }
  key(input, "Escape");
  assert.equal(list.hidden, true);
  assert.equal(input.value, "ber", "the first Escape closes the list");
  key(input, "Escape");
  assert.equal(input.value, "", "the second clears the box");
});

// M13 fix round (review I1, I2, M4): every way out of the search clears "No match", and the
// no-match is also said through #live, since the status may not be in the AX tree in time.

test("no match, then Escape: the box is cleared and so is the status", async (t) => {
  const { input, status } = await typed(t, INDEX, "zzz");
  assert.equal(status.textContent, "No match");
  key(input, "Escape");
  assert.equal(input.value, "");
  assert.equal(status.textContent, "", "no No match under an empty box");
});

test("no match, then focus leaves the search: the status is cleared", async (t) => {
  const { doc, input, status } = await typed(t, INDEX, "zzz");
  doc.activeElement = null; // focus went elsewhere on the page
  input.fire("blur");
  await settle();
  assert.equal(status.textContent, "");
});

test("no match, then a click outside the search: the status is cleared", async (t) => {
  const { doc, status } = await typed(t, INDEX, "zzz");
  for (const f of doc.listeners.click ?? []) f({ target: {} });
  assert.equal(status.textContent, "");
});

test("no match is also announced through #live", async (t) => {
  const { live } = await typed(t, INDEX, "zzz");
  await settle();
  assert.equal(live.textContent, "No match");
});

test("the search status is never display:none, so its live region is in the AX tree empty", () => {
  const css = readFileSync(repoFile("src/velometer/app/static/app.css"), "utf8");
  const rules = [...css.matchAll(/([^{}]*\.search-status[^{}]*)\{([^}]*)\}/g)];
  assert.ok(rules.length >= 2, "the status is styled (and its empty state)");
  for (const [, sel, body] of rules) {
    assert.doesNotMatch(body, /display\s*:\s*none|visibility\s*:\s*hidden/, sel.trim());
  }
});

// ---- M13 fix round (review 10, I1): an organisation's option is in its name's language ----

test("an organisation's option label carries its lang, its bracket its own", async (t) => {
  const index = [
    { label: "Københavns Kommune (City of Copenhagen)", kind: "organisation", lang: "da",
      bracket_lang: "en", url: "/organisations#copenhagen_kommune", terms: ["copenhagen_kommune"] },
    { label: "Stadt Wien", kind: "organisation", lang: "de", url: "/organisations#wien", terms: [] },
    { label: "Wien (Österreich)", kind: "city", url: "/city/vienna", terms: ["Wien"] },
  ]; // fmt: skip
  const kk = (await typed(t, index, "kobenhavns")).list.children[0].children[0];
  assert.equal(kk.getAttribute("lang"), "da");
  const [lead, bracket, close] = kk.children;
  assert.equal(lead, "Københavns Kommune (");
  assert.equal(bracket.getAttribute("lang"), "en");
  assert.equal(bracket.textContent, "City of Copenhagen");
  assert.equal(close, ")");
  const wien = (await typed(t, index, "wien")).list.children.map((li) => li.children[0]);
  assert.deepEqual(wien.map((l) => [l.textContent, l.getAttribute("lang")]),
    [["Wien (Österreich)", null], ["Stadt Wien", "de"]]); // a city is in the page's language
});
