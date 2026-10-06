// URL state for the compare page: parse and serialise the query string, nothing else.

export const PILOT5 = ["berlin", "paris", "vienna", "copenhagen", "wroclaw"];
export const BOUNDARIES = ["lau", "fua"];
export const MODES = ["abs", "index"];
export const VIEWS = ["lines", "small", "rank", "table"];
export const MAX_HIGHLIGHTED = 8;

export const DEFAULTS = {
  c: PILOT5,
  m: "headline",
  b: "lau",
  mode: "abs",
  view: "lines",
  hl: [],
};

const list = (v) => (v ? v.split(",").filter(Boolean) : []);
const dedupe = (a) => [...new Set(a)];
const oneOf = (v, allowed, dflt) => (allowed.includes(v) ? v : dflt);

export function parseState(search, known) {
  const q = new URLSearchParams(search);
  let c = dedupe(list(q.get("c"))).filter((id) => known.cities.includes(id));
  if (!c.length) c = [...DEFAULTS.c];
  const m = known.metrics.includes(q.get("m")) ? q.get("m") : DEFAULTS.m;
  const hl = dedupe(list(q.get("hl")))
    .filter((id) => c.includes(id))
    .slice(0, MAX_HIGHLIGHTED);
  return {
    c,
    m,
    b: oneOf(q.get("b"), BOUNDARIES, DEFAULTS.b),
    mode: oneOf(q.get("mode"), MODES, DEFAULTS.mode),
    view: oneOf(q.get("view"), VIEWS, DEFAULTS.view),
    hl,
  };
}

const sameList = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);

/** Query string without the leading "?"; defaults are omitted, key order is fixed. */
export function serializeState(state) {
  const parts = [];
  const enc = (a) => a.map(encodeURIComponent).join(",");
  if (!sameList(state.c, DEFAULTS.c)) parts.push(`c=${enc(state.c)}`);
  for (const k of ["m", "b", "mode", "view"]) {
    if (state[k] !== DEFAULTS[k]) parts.push(`${k}=${encodeURIComponent(state[k])}`);
  }
  if (state.hl.length) parts.push(`hl=${enc(state.hl)}`);
  return parts.join("&");
}
