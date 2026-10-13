import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fold, rank, move, keyAction } from "../search.js";

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
  const doc = { activeElement: null, listeners: {}, addEventListener() {}, createElement: (t) => fakeNode(t),
    getElementById: () => null }; // fmt: skip
  const focusable = (n) => Object.assign(n, { focus() { if (!this.hidden) doc.activeElement = this; } });
  const input = focusable(fakeNode("input"));
  const list = fakeNode("ul", { hidden: true });
  const box = fakeNode("div", { hidden: true, kids: [input, list] });
  box.querySelector = (s) => (s === "input" ? input : list);
  const fallback = focusable(fakeNode("a"));
  doc.querySelector = (s) => (s === ".search" ? box : s === ".search-fallback" ? fallback : null);
  return { doc, box, input, list, fallback };
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

// --- M12: every name form finds its city (tests/city_names.json, kept equal to cities.yaml) ---


const CITY_NAMES = JSON.parse(
  readFileSync(new URL("../../../../../../tests/city_names.json", import.meta.url), "utf8"),
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
