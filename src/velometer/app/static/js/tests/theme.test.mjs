import { test } from "node:test";
import assert from "node:assert/strict";
import { token, seriesColours, tierColours, onThemeChange, MISSING } from "../theme.js";

const fake = (map) => (name) => map[name] ?? "";

test("token reads the stylesheet value", () => {
  assert.equal(token("--tier-a", fake({ "--tier-a": "#123456" })), "#123456");
});

test("a missing token logs once and falls back", (t) => {
  const errors = [];
  t.mock.method(console, "error", (m) => errors.push(m));
  assert.equal(token("--nope", fake({})), MISSING);
  token("--nope", fake({}));
  assert.equal(errors.length, 1);
});

test("series and tier colours come from their tokens", () => {
  const map = Object.fromEntries([
    ...Array.from({ length: 8 }, (_, i) => [`--series-${i + 1}`, `#00000${i}`]),
    ...[..."abcde"].map((t, i) => [`--tier-${t}`, `#11111${i}`]),
  ]);
  assert.deepEqual(seriesColours(fake(map)), Array.from({ length: 8 }, (_, i) => `#00000${i}`));
  assert.deepEqual(tierColours(fake(map)), { A: "#111110", B: "#111111", C: "#111112", D: "#111113", E: "#111114" });
});

test("onThemeChange subscribes and unsubscribes", () => {
  const listeners = new Set();
  const mm = () => ({ addEventListener: (_, f) => listeners.add(f), removeEventListener: (_, f) => listeners.delete(f) });
  let calls = 0;
  const off = onThemeChange(() => calls++, mm);
  [...listeners].forEach((f) => f());
  off();
  assert.equal(calls, 1);
  assert.equal(listeners.size, 0);
});
