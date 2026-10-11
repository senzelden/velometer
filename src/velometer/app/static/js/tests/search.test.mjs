import { test } from "node:test";
import assert from "node:assert/strict";
import { fold, rank, move } from "../search.js";

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
