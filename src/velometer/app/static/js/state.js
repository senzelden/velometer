// URL state for the compare page: parse and serialise the query string, nothing else.

export const PILOT5 = ["berlin", "paris", "vienna", "copenhagen", "wroclaw"];
export const BOUNDARIES = ["lau", "fua"];
export const MODES = ["abs", "index"];
export const VIEWS = ["lines", "small", "rank", "table"];
export const MAX_HIGHLIGHTED = 8;
export const METRICS = [
  "headline", "ab_km", "A", "B", "C", "D", "E", "ecf_qecio", "clean_cities", "ab_per_100k",
  "counter_index",
];
/** The metric that exists for the city proper (LAU) only. */
export const LAU_ONLY_METRIC = "ab_per_100k";
/** Quick city sets (app/compare.py: QUICK_SETS is the same table); `all` is every known city. */
export const QUICK_SETS = {
  all: null,
  pilot5: ["berlin", "paris", "vienna", "copenhagen", "wroclaw"],
  nordic: ["copenhagen", "stockholm", "oslo", "helsinki"],
  dach: ["berlin", "vienna"],
  west: ["paris", "lyon", "strasbourg", "bordeaux", "madrid", "barcelona", "amsterdam", "utrecht"],
  central: ["wroclaw", "warsaw", "krakow", "prague", "bratislava", "budapest", "ljubljana"],
};

export const DEFAULTS = {
  c: PILOT5,
  m: "headline",
  b: "lau",
  mode: "abs",
  view: "lines",
  hl: [],
};

// `c` and `hl` may be repeated (?c=a&c=b, what a plain form sends) or comma-separated, or both.
const list = (values) => values.flatMap((v) => v.split(",")).filter(Boolean);
const dedupe = (a) => [...new Set(a)];
const oneOf = (v, allowed, dflt) => (allowed.includes(v) ? v : dflt);

export function parseState(search, known) {
  const q = new URLSearchParams(search);
  let c = dedupe(list(q.getAll("c"))).filter((id) => known.cities.includes(id));
  if (!c.length) c = [...DEFAULTS.c];
  const b = oneOf(q.get("b"), BOUNDARIES, DEFAULTS.b);
  const wanted = q.get("m");
  // The default is checked too: if the known list lacks it, fall back to its first entry.
  // The LAU-only metric is dropped for the metro area (droppedMetric tells the page to say so).
  const m =
    known.metrics.includes(wanted) && !(b === "fua" && wanted === LAU_ONLY_METRIC)
      ? wanted
      : known.metrics.includes(DEFAULTS.m)
        ? DEFAULTS.m
        : (known.metrics[0] ?? DEFAULTS.m);
  const hl = dedupe(list(q.getAll("hl")))
    .filter((id) => c.includes(id))
    .slice(0, MAX_HIGHLIGHTED);
  return {
    c,
    m,
    b,
    mode: oneOf(q.get("mode"), MODES, DEFAULTS.mode),
    view: oneOf(q.get("view"), VIEWS, DEFAULTS.view),
    hl,
  };
}

/** The LAU-only metric the query asked for with b=fua (and parseState dropped), else null. */
export function droppedMetric(search, state) {
  const wanted = new URLSearchParams(search).get("m");
  return wanted === LAU_ONLY_METRIC && state.b === "fua" ? wanted : null;
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
