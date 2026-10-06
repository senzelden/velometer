// Compare page data model: what the views draw, computed from the series payload and the URL
// state. Pure (no DOM); app/compare.py computes the same Table for the no-JS page.
import { assignColours, indexSeries, ranks } from "./chart-core.js";
import { LAU_ONLY_METRIC, MAX_HIGHLIGHTED } from "./state.js";
import { PALETTE, labelsOf } from "./data.js";

export const NO_INDEX = "no index: first year is 0 or missing";

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
 * [{label, value, flags}]}], notes}. `index` mode rebases every city to its first year = 100;
 * a city whose first year is 0 or missing gets no values and a note.
 */
export function buildModel(D, state) {
  const ids = state.c.filter((id) => D.cities[id]);
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
  return { labels, series, notes };
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
