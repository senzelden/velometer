// Permalinks (M11): page state in the URL, pure and DOM-free. A schema maps a query key to
// {parse(str, ctx) -> value | undefined, format(value) -> string, fallback}. `read` never throws:
// a missing, malformed, hostile or stale value is the key's fallback. `write` returns the
// address (path, the keys that differ from their fallback in schema order, the hash) for
// `history.replaceState`; there is no server route behind any of it, so a permalink opens the
// same state on the static export under its base path. Compare's own state.js stays as it is.
import { base } from "./base.js";
import { absoluteUrl } from "./cite.js";

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const NUM = /^-?\d+(\.\d+)?$/;

/** `{key: value}` for every key of the schema; a bad or missing value is that key's fallback. */
export function read(search, schema, ctx) {
  const q = new URLSearchParams(search);
  const out = {};
  for (const [key, spec] of Object.entries(schema)) {
    let value;
    try {
      const raw = q.get(key);
      value = raw === null ? undefined : spec.parse(raw, ctx);
    } catch {
      value = undefined;
    }
    out[key] = value === undefined ? spec.fallback : value;
  }
  return out;
}

/** pathname + "?" + the keys whose value differs from the fallback + hash. */
export function write(state, schema, loc = globalThis.location) {
  const parts = [];
  for (const [key, spec] of Object.entries(schema)) {
    const value = state[key];
    if (value === undefined || same(value, spec.fallback)) continue;
    parts.push(`${key}=${encodeURIComponent(spec.format(value)).replaceAll("%2C", ",")}`);
  }
  return loc.pathname + (parts.length ? `?${parts.join("&")}` : "") + (loc.hash ?? "");
}

export const TIERMAP = {
  // `kinds` (the boundaries #tiermap-config offers) is the ctx of `read`
  kind: { parse: (s, kinds = []) => (kinds.includes(s) ? s : undefined), format: String, fallback: null },
  tiers: {
    parse: (s) => (/^[A-E]{0,5}$/.test(s) ? [...new Set(s)].sort() : undefined),
    format: (a) => a.join(""),
    fallback: ["A", "B", "C", "D", "E"],
  },
  at: {
    parse: (s) => {
      const p = s.split(",");
      if (p.length !== 3 || !p.every((x) => NUM.test(x))) return undefined;
      const [la, lo, z] = p.map(Number);
      return Math.abs(la) <= 90 && Math.abs(lo) <= 180 && z >= 3 && z <= 19
        ? [la, lo, Math.round(z)]
        : undefined;
    },
    format: ([la, lo, z]) => `${la.toFixed(5)},${lo.toFixed(5)},${z}`,
    fallback: null,
  },
};

/** "#step-x" -> "x" when x is one of `steps`, else null. */
export function stepFromHash(hash, steps) {
  const m = /^#step-(.+)$/.exec(hash ?? "");
  if (!m) return null;
  try {
    const id = decodeURIComponent(m[1]);
    return steps.includes(id) ? id : null;
  } catch {
    return null;
  }
}

/** The Stories permalink: which step in view is written to the address. `next(step)` is the
 * hash to write (`#step-<id>`), or null when there is nothing to write: the step written last
 * (or the one the address came with), or the first step while the page came without a step and
 * none has been written (its top is the page itself). */
export function stepMemory(steps, hash) {
  let written = stepFromHash(hash, steps);
  return {
    next(step) {
      if (step === written || (step === steps[0] && written === null)) return null;
      written = step;
      return `#step-${encodeURIComponent(step)}`;
    },
  };
}

/** `search` with `key` set to `value` (or removed for null); the other pairs stay as written. */
export function setParam(search, key, value) {
  const parts = String(search).replace(/^\?/, "").split("&").filter(Boolean);
  const rest = parts.filter((p) => decodeURIComponent_(p.split("=")[0]) !== key);
  if (value !== null) rest.push(`${key}=${encodeURIComponent(value)}`);
  return rest.length ? `?${rest.join("&")}` : "";
}

function decodeURIComponent_(s) {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

/** The page's absolute address now: origin + base + the path below the base + query + hash. */
export function currentAddress(loc = globalThis.location, doc = globalThis.document) {
  const b = base(doc);
  const below = loc.pathname.startsWith(b) ? loc.pathname.slice(b.length) : loc.pathname;
  return absoluteUrl(below, loc, doc);
}

/** Which map `moveend`s are the reader's: not one while the app fits the map itself (`fitting`),
 * and not the one a resize sends (Leaflet's `invalidateSize` keeps the centre and fires `moveend`
 * after `resize`, 200 ms later for a window resize), so resizing never writes `at`. */
export function readerMoves() {
  let resized = false;
  return {
    resize() {
      resized = true;
    },
    moveend(fitting) {
      const reader = !fitting && !resized;
      resized = false;
      return reader;
    },
  };
}
