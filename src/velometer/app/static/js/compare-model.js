// Compare page data model: what the views draw, computed from the series payload and the URL
// state. Pure (no DOM); app/compare.py computes the same Table for the no-JS page.
import { assignColours, indexSeries, ranks } from "./chart-core.js";
import { LAU_ONLY_METRIC, MAX_HIGHLIGHTED, parseState, serializeState } from "./state.js";
import { PALETTE, labelsOf } from "./data.js";
import { COUNTER_FOOT, COUNTER_METRIC, counterLines } from "./counter-model.js";
import { url } from "./base.js";

export const NO_INDEX = "no index: first year is 0 or missing";

/**
 * The footnote under the chart and table: the counter index has its own (no flagged years, not
 * the headline); every other metric the flag mark and the headline unit (app/compare.py: footnote).
 */
export function footnote(metric, headlineUnit) {
  if (metric === COUNTER_METRIC) return COUNTER_FOOT;
  return `⚑ flagged year (automatic check). Headline: ${headlineUnit}. Ranks in the Rank view depend on the cities selected.`;
}

/** One point's value of a metric; null where it is missing. */
export function metricValue(point, metric, population) {
  if (metric === LAU_ONLY_METRIC) {
    return point.ab_km == null || !population ? null : (point.ab_km / population) * 100000;
  }
  const v = point[metric];
  return Number.isFinite(v) ? v : null;
}

/**
 * The selection as lines: {labels (raw: years then "current"), series: [{id, name, points:
 * [{label, value, flags}]}], notes, marks}. `index` mode rebases every city to its first year =
 * 100; a city whose first year is 0 or missing gets no values and a note. The counter index
 * (calendar years, already an index, the same for both boundaries) is never rebased and marks
 * the COVID year.
 */
export function buildModel(D, state) {
  const ids = state.c.filter((id) => D.cities[id]);
  if (state.m === COUNTER_METRIC) return { ...counterLines(D, ids), counter: true };
  const lists = ids.map((id) => D.series[`${id}/${state.b}`] ?? []);
  const labels = labelsOf(lists);
  const base = labels.find((l) => l !== "current");
  const notes = [];
  const series = ids.map((id, i) => {
    const by = new Map(lists[i].map((p) => [p.label, p]));
    const raw = labels.map((l) => {
      const p = by.get(l);
      return {
        label: l,
        value: p ? metricValue(p, state.m, D.cities[id].population) : null,
        flags: p?.flags ? p.flags.split(";").filter(Boolean) : [],
      };
    });
    let points = raw;
    if (state.mode === "index") {
      const idx = indexSeries(raw, base);
      if (idx.every((p) => p.value == null)) notes.push(`${D.cities[id].name}: ${NO_INDEX}`);
      points = idx.map((p, k) => ({ ...p, flags: raw[k].flags }));
    }
    return { id, name: D.cities[id].name, points };
  });
  return { labels, series, notes, marks: [] };
}

/** The ids drawn in colour: the highlighted ones, else the first MAX_HIGHLIGHTED selected. */
export function colouredIds(state) {
  return state.hl.length ? state.hl : state.c.slice(0, MAX_HIGHLIGHTED);
}

/** Stable colours for the plan (previous colours are kept). */
export function colourPlan(state, prev) {
  return assignColours(prev, colouredIds(state), PALETTE);
}

/** Rank per label among the model's cities: series points get {rank}. */
export function rankSeries(series, labels) {
  const perLabel = labels.map((_, i) =>
    ranks(Object.fromEntries(series.map((s) => [s.id, s.points[i].value]))),
  );
  return series.map((s) => ({
    ...s,
    points: s.points.map((p, i) => ({ ...p, rank: perLabel[i][s.id] })),
  }));
}

/**
 * Table rows sorted by `sort` ({key: "name" | label | null, dir: 1 | -1}); missing values last
 * whatever the direction; unsorted keeps the selection order.
 */
export function sortRows(series, labels, sort) {
  const rows = series.map((s) => ({ ...s }));
  if (!sort?.key) return rows;
  const at = labels.indexOf(sort.key);
  const val = (r) => (sort.key === "name" ? r.name : r.points[at]?.value);
  return rows.sort((a, b) => {
    const x = val(a);
    const y = val(b);
    if (x == null || y == null) return x == null && y == null ? 0 : x == null ? 1 : -1;
    const d = typeof x === "string" ? x.localeCompare(y) : x - y;
    return d * sort.dir;
  });
}

/** Next sort when a column heading is clicked: numbers start descending, names ascending. */
export function nextSort(sort, key) {
  if (sort?.key === key) return { key, dir: -sort.dir };
  return { key, dir: key === "name" ? 1 : -1 };
}

// ---- history: what the URL must say, whatever the panel did ----

/** The Compare URL of a serialised query ("" is the default selection), under the base. */
export const compareUrl = (qs, doc) => url(`/compare${qs ? `?${qs}` : ""}`, doc);

/** The server-rendered fragment the city slide-over fetches. */
export const panelUrl = (id, doc) => url(`/city/${encodeURIComponent(id)}/panel`, doc);

/** The normalised query (what the page shows) of a search string. */
export const queryOf = (search, known) => serializeState(parseState(search, known));

/** Opening the panel adds one history entry; switching city inside it replaces that entry. */
export const openAction = (panelOpen) => (panelOpen ? "replace" : "push");

/** Closing goes through history only when the top entry is the panel's own. */
export const closeAction = (historyState) => (historyState?.panel ? "back" : "hide");

/**
 * What to do on `popstate`. `popState` is the state of the entry landed on, `shownQuery` the
 * query of the state the page shows, `urlQuery` the normalised query of the landed-on URL.
 * Landing on or leaving a panel entry never changes the page: the panel opens or closes and a
 * stale URL is rewritten to `restore`. Landing anywhere else with a different query re-reads
 * the URL and redraws (`rerender`).
 */
export function popPlan({ popState, panelOpen, shownQuery, urlQuery }) {
  const panel = popState?.panel ?? null;
  const stale = urlQuery !== shownQuery;
  if (panel || panelOpen) return { panel, restore: stale ? shownQuery : null, rerender: false };
  return { panel: null, restore: null, rerender: stale };
}

/**
 * City order of a form submission: the cities already selected keep their place, newly checked
 * ones follow in form order.
 */
export function orderCities(current, checked) {
  const set = new Set(checked);
  return [...current.filter((id) => set.has(id)), ...checked.filter((id) => !current.includes(id))];
}

/** Explanation text without Markdown markers (the note shows plain text). */
export function plainText(md) {
  return String(md)
    .replace(/```[a-z]*\n?/g, "")
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/(\*\*|__)(.+?)\1/g, "$2")
    .replace(/(^|[\s(])[*_]([^*_\n]+)[*_](?=[\s).,;:!?]|$)/g, "$1$2")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*>\s?/gm, "")
    // a single newline is a soft wrap of the source: join it, keep paragraph and list breaks
    .replace(/[ \t]+\n/g, "\n")
    .replace(/(?<!\n)\n(?!\n|[ \t]*(?:[-*]|\d+\.)\s)[ \t]*/g, " ");
}
