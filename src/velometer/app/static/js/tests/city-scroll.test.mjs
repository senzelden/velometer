// M17 Task 16: the phone-only charts of a city's story page are drawn lazily, once their block
// becomes visible (IntersectionObserver), and only then is the series fetched for them. Without
// IntersectionObserver every chart is drawn at once.
import { test } from "node:test";
import assert from "node:assert/strict";
import "./strings-fixture.mjs";

// A mount: `phone` mounts sit inside a `.phone-only` block.
const mount = (chart, phone = false) => ({
  dataset: { chart },
  closest: (sel) => (phone && sel === ".phone-only" ? {} : null),
  replaceChildren() {},
});

// A fake IntersectionObserver whose entries the test fires by hand.
function fakeIO() {
  const made = [];
  class IO {
    constructor(cb) {
      this.cb = cb;
      this.watched = new Set();
      made.push(this);
    }
    observe(el) { this.watched.add(el); }
    unobserve(el) { this.watched.delete(el); }
    disconnect() { this.watched.clear(); }
    fire(el, isIntersecting = true) { this.cb([{ target: el, isIntersecting }], this); }
  }
  return { IO, made };
}

function page(mounts) {
  let fetches = 0;
  globalThis.document = {
    documentElement: { lang: "en" },
    querySelector: () => null,
    querySelectorAll: (sel) => (sel === "[data-chart]" ? mounts : []),
  };
  globalThis.fetch = async () => {
    fetches += 1;
    return { ok: true, json: async () => ({ series: {}, cities: {} }) };
  };
  return { fetches: () => fetches };
}

const settle = () => new Promise((r) => setTimeout(r, 0));
// a fresh data.js per test: its series promise is per module instance
let n = 0;
const fresh = async () => (await import(`../data.js?t=${++n}`)).drawAll;

test("lazy charts init once when visible", async () => {
  const eager = mount("a");
  const phone = mount("a", true);
  const drawn = [];
  const p = page([eager, phone]);
  const { IO, made } = fakeIO();
  (await fresh())({ a: (el) => drawn.push(el) }, { lazy: ".phone-only", IO });
  await settle();
  assert.deepEqual(drawn, [eager]); // the phone chart waits
  assert.equal(made.length, 1);
  assert.ok(made[0].watched.has(phone) && !made[0].watched.has(eager));
  made[0].fire(phone, false); // not yet on screen
  await settle();
  assert.deepEqual(drawn, [eager]);
  made[0].fire(phone);
  await settle();
  assert.deepEqual(drawn, [eager, phone]);
  assert.ok(!made[0].watched.has(phone)); // let go once drawn
  made[0].fire(phone); // a late second entry draws nothing more
  await settle();
  assert.deepEqual(drawn, [eager, phone]);
  assert.equal(p.fetches(), 1); // one series fetch for the page
});

test("phone charts alone fetch nothing until a block is visible", async () => {
  const phone = mount("a", true);
  const drawn = [];
  const p = page([phone]);
  const { IO, made } = fakeIO();
  (await fresh())({ a: (el) => drawn.push(el) }, { lazy: ".phone-only", IO });
  await settle();
  assert.equal(p.fetches(), 0); // desktop: the block is hidden, never fetched for
  made[0].fire(phone);
  await settle();
  assert.deepEqual(drawn, [phone]);
  assert.equal(p.fetches(), 1);
});

test("init all immediately without IntersectionObserver", async () => {
  const eager = mount("a");
  const phones = [mount("a", true), mount("a", true)];
  const drawn = [];
  page([eager, ...phones]);
  (await fresh())({ a: (el) => drawn.push(el) }, { lazy: ".phone-only", IO: undefined });
  await settle();
  assert.deepEqual(new Set(drawn), new Set([eager, ...phones]));
  assert.equal(drawn.length, 3);
});

test("without a lazy selector every chart draws at once, as before", async () => {
  const a = mount("a", true);
  const drawn = [];
  const { IO, made } = fakeIO();
  page([a]);
  (await fresh())({ a: (el) => drawn.push(el) }, { IO });
  await settle();
  assert.deepEqual(drawn, [a]);
  assert.equal(made.length, 0);
});
