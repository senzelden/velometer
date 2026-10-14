import { test } from "node:test";
import assert from "node:assert/strict";
import { FIXTURE, fakeDoc, useLang } from "./strings-fixture.mjs";
import { compact, locale, monthYear, number, parse, percent, signed } from "../fmt.js";

const EN = fakeDoc("en");
const DE = fakeDoc("de");

test("locale comes from <html lang>: de-DE for German, en-GB otherwise", () => {
  assert.equal(locale(EN), "en-GB");
  assert.equal(locale(DE), "de-DE");
  assert.equal(locale(fakeDoc("de-AT")), "de-DE");
  assert.equal(locale(fakeDoc("")), "en-GB");
  assert.equal(locale(undefined), "en-GB"); // no document (node): English
});

test("number: grouping and decimal mark of the locale; a German minus is U+2212", () => {
  assert.equal(number(1639.8, 1, EN), "1,639.8");
  assert.equal(number(1639.8, 1, DE), "1.639,8");
  assert.equal(number(12, 1, DE), "12,0");
  assert.equal(number(-3.25, 1, DE), "−3,3");
  assert.equal(number(-3.2, 1, EN), "-3.2");
});

test("signed: always a sign; German uses U+2212", () => {
  assert.equal(signed(-3.2, 1, DE), "−3,2");
  assert.equal(signed(3.2, 1, DE), "+3,2");
  assert.equal(signed(-3.2, 1, EN), "-3.2");
  assert.equal(signed(3.2, 1, EN), "+3.2");
});

test("percent: German puts a narrow no-break space before %", () => {
  assert.equal(percent(12.3, 1, DE), "12,3 %");
  assert.equal(percent(12.3, 1, EN), "12.3%");
});

test("compact: thousands as k / Tsd.", () => {
  useLang("en");
  assert.equal(compact(12000, EN), "12k");
  useLang("de");
  assert.equal(compact(12000, DE), "12 Tsd.");
  useLang("en");
});

test("monthYear: month names from the strings block, short and long", () => {
  useLang("en");
  assert.equal(monthYear("2026-10-03", EN), "Oct 2026");
  assert.equal(monthYear(new Date(Date.UTC(2027, 0, 5)), EN), "Jan 2027");
  useLang("de");
  assert.equal(monthYear("2026-10", DE), "Okt. 2026");
  assert.equal(monthYear("2026-03", DE, false), "März 2026");
  assert.equal(FIXTURE.de["js.month.short.10"], "Okt.");
  useLang("en");
});

test("parse: the inverse of number for the locale; null for anything not wholly a number", () => {
  assert.equal(parse("1.639,8", "de-DE"), 1639.8);
  assert.equal(parse("−3,2", "de-DE"), -3.2);
  assert.equal(parse("12", "de-DE"), 12);
  assert.equal(parse("12,3 ⚑", "de-DE"), null);
  assert.equal(parse("Jahr", "de-DE"), null);
  assert.equal(parse("1.5", "de-DE"), null); // a dot is a German group mark: 1.5 is no number
  assert.equal(parse("12,3 %", "de-DE"), null);
  assert.equal(parse("2026-10-03", "de-DE"), null);
  assert.equal(parse("1,639.8", "en-GB"), 1639.8);
  assert.equal(parse("-3.2", "en-GB"), -3.2);
  assert.equal(parse("", "en-GB"), null);
  for (const v of [1639.8, -3.25, 0, 1234567.5]) {
    assert.equal(parse(number(v, 1, DE), "de-DE"), +v.toFixed(1), String(v));
    assert.equal(parse(number(v, 1, EN), "en-GB"), +v.toFixed(1), String(v));
  }
});
