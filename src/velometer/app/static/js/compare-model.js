// Compare page data model: what the views draw, computed from the series payload and the URL
// state. Pure (no DOM); app/compare.py computes the same Table for the no-JS page.
import { assignColours, indexSeries, ranks } from "./chart-core.js";
import { LAU_ONLY_METRIC, MAX_HIGHLIGHTED, parseState, serializeState } from "./state.js";
import { labelsOf } from "./data.js";
import { COUNTER_METRIC, counterFoot, counterLines } from "./counter-model.js";
import { url } from "./base.js";
import { t } from "./strings.js";

/** The note of a city that has no index (app/compare.py: NO_INDEX). */
export const noIndex = () => t("js.compare.no_index");

/**
 * The footnote under the chart and table: the counter index has its own (no flagged years, not
 * the headline); every other metric the flag mark and the headline unit (app/compare.py: footnote).
 */
export function footnote(metric, headlineUnit) {
  if (metric === COUNTER_METRIC) return counterFoot();
  return t("js.compare.foot", { unit: headlineUnit });
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
      if (idx.every((p) => p.value == null)) notes.push(`${D.cities[id].name}: ${noIndex()}`);
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

/** The series palette's slots (theme.js seriesColours: --series-1 … --series-8). */
export const SLOTS = [0, 1, 2, 3, 4, 5, 6, 7];

/**
 * Stable colour slots for the plan, {cityId: slotIndex}: a city keeps the slot it had in `prev`,
 * newcomers take free slots. Slots, not colours, so a theme change (which changes every colour)
 * moves no city; drawing resolves seriesColours()[slot].
 */
export function slotPlan(state, prev) {
  return assignColours(prev, colouredIds(state), SLOTS);
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

/**
 * A flagged year's explanation as plain paragraphs, each with the attributes of its element:
 * `lang="en" data-fallback` when the text is still English on a German page (as the server
 * marks it); [] when the year has no explanation. `parts` are the paragraph's pieces: plain
 * `{ text }`, or `{ code }` for a code span, with `href` when the payload links that repo path
 * (`explanations.links`, M16 R44; only https addresses are taken).
 */
export function flagParagraphs(D, key) {
  const raw = D.explanations?.timeseries?.[key];
  if (!raw) return [];
  const attrs = D.explanationFallback?.has(key) ? { lang: "en", "data-fallback": "" } : {};
  const links = D.explanations?.links?.[key] ?? {};
  return markdownText(raw)
    .split(/\n{2,}/)
    .map((para) => {
      const parts = codeParts(para.trim(), links);
      return { attrs: { ...attrs }, text: parts.map((p) => p.text ?? p.code).join(""), parts };
    });
}

/** `text` split at its code spans: `{ text }` and `{ code, href? }` pieces, empty text left out. */
function codeParts(text, links) {
  return text
    .split(/`([^`]*)`/)
    .map((piece, i) => {
      if (i % 2 === 0) return { text: piece };
      const href = Object.hasOwn(links, piece.trim()) ? links[piece.trim()] : null;
      return isHttps(href) ? { code: piece, href } : { code: piece };
    })
    .filter((p) => p.code !== undefined || p.text);
}

function isHttps(href) {
  if (typeof href !== "string") return false;
  try {
    return new URL(href).protocol === "https:";
  } catch {
    return false;
  }
}

/**
 * A paragraph of `flagParagraphs` as a `<p>`: text nodes, `<code>` for code spans, inside an
 * `<a>` when linked. DOM methods only: nothing from the data is parsed as HTML.
 */
export function paragraphNode(p, doc = globalThis.document) {
  const node = doc.createElement("p");
  for (const [k, v] of Object.entries(p.attrs ?? {})) node.setAttribute(k, v);
  for (const part of p.parts ?? [{ text: p.text }]) {
    if (part.code === undefined) {
      node.appendChild(doc.createTextNode(part.text));
      continue;
    }
    const code = doc.createElement("code");
    code.textContent = part.code;
    if (part.href) {
      const a = doc.createElement("a");
      a.setAttribute("href", part.href);
      a.appendChild(code);
      node.appendChild(a);
    } else {
      node.appendChild(code);
    }
  }
  return node;
}

/** Explanation text without Markdown markers (the note shows plain text). */
export function plainText(md) {
  return markdownText(md).replace(/`([^`]*)`/g, "$1");
}

/** `plainText` that keeps the code spans' backticks (`flagParagraphs` makes them `<code>`). */
function markdownText(md) {
  return String(md)
    .replace(/```[a-z]*\n?/g, "")
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/(\*\*|__)(.+?)\1/g, "$2")
    .replace(/(^|[\s(])[*_]([^*_\n]+)[*_](?=[\s).,;:!?]|$)/g, "$1$2")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*>\s?/gm, "")
    // a single newline is a soft wrap of the source: join it, keep paragraph and list breaks
    .replace(/[ \t]+\n/g, "\n")
    .replace(/(?<!\n)\n(?!\n|[ \t]*(?:[-*]|\d+\.)\s)[ \t]*/g, " ");
}

/** What a screen reader hears after Compare redraws: how many cities, which metric, what scale. */
export function compareSummary(state, metrics) {
  const scale = state.mode === "index" ? t("js.compare.scale_index") : t("js.compare.scale_abs");
  return t("js.compare.summary", { count: state.c.length, metric: metrics[state.m]?.label ?? state.m, scale });
}

/** What a screen reader hears while the city panel loads, once it has, and when it failed. */
export function panelAnnouncement(phase, name) {
  if (phase === "loading") return t("js.panel.loading_city", { name });
  if (phase === "loaded") return name;
  return t("js.panel.failed", { name });
}
