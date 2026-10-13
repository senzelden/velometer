// The chart data of every page: one fetch of /data/series.json, and the small helpers that turn
// its series into chart.js models. No DOM drawing here.
import { lang, url } from "./base.js";
import { xLabels } from "./chart-core.js";
import { number } from "./fmt.js";
import { onThemeChange } from "./theme.js";
import { t } from "./strings.js";

/** The tiers, A (bottom of a stack) to E. */
export const TIERS = ["A", "B", "C", "D", "E"];
/** A tier's name in the page's language ("A separated track"). */
export const tierName = (tier) => t(`js.tier.${tier}`);

/** The tier map's status line: the boundary kind, the side count as a locale number
 * ("31,842" / "31.842") and the run's provenance (the GeoJSON's `properties`). */
export const mapStatus = (kind, n, p = {}, doc = globalThis.document) =>
  t("js.map.status", {
    kind: kind.toUpperCase(), n: number(n, 0, doc), osm: p.osm_timestamp,
    classifier: p.classifier, run: p.run_id,
  });

// a `<key>_de` sibling replaces `<key>` on a German page (app/series.py writes them)
const withDe = (o) => {
  const out = { ...o };
  for (const [k, v] of Object.entries(o ?? {})) {
    if (k.endsWith("_de") && v != null) out[k.slice(0, -3)] = v;
  }
  return out;
};

/**
 * The series payload in the page's language. English: the payload itself. German: a copy with
 * every `<key>_de` in place of `<key>` (the cities' names and countries, `headline_unit`, the
 * preset labels, the counter `none` notes) and `explanations` from `explanations_de`;
 * `explanationFallback` is the Set of explanation keys still in English (mark them lang="en").
 */
export function localised(series, pageLang) {
  if (pageLang !== "de") return series;
  const out = withDe(series);
  out.cities = Object.fromEntries(Object.entries(series.cities ?? {}).map(([id, c]) => [id, withDe(c)]));
  out.presets = { ...series.presets, ...series.presets_de };
  if (series.counters) out.counters = { ...series.counters, none: { ...series.counters.none, ...series.counters.none_de } };
  const de = series.explanations_de;
  if (de) out.explanations = { ...series.explanations, timeseries: { ...series.explanations?.timeseries, ...de.timeseries } };
  out.explanationFallback = new Set(de?.fallback ?? []);
  return out;
}

let pending = null;

/** The payload in the page's language (`localised`), fetched once per page. Rejects on a non-200
 * answer. */
export function loadSeries(doc = globalThis.document) {
  pending ??= fetch(url("/data/series.json")).then((r) => {
    if (!r.ok) throw new Error(`series.json: HTTP ${r.status}`);
    return r.json().then((D) => localised(D, lang(doc)));
  });
  return pending;
}

/** Labels of the given point lists: years in order, then `current`. */
export function labelsOf(lists) {
  const seen = new Set(lists.flatMap((pts) => pts.map((p) => p.label)));
  const years = [...seen].filter((l) => l !== "current").sort();
  return seen.has("current") ? [...years, "current"] : years;
}

/** The current run's snapshot date, from the first list that has one. */
export function snapshotOf(lists) {
  for (const pts of lists) {
    const cur = pts.find((p) => p.label === "current");
    if (cur?.osm) return cur.osm;
  }
  return null;
}

/** Axis text for the labels ("2018" … "Oct 2026"). */
export const displayLabels = (labels, lists) => xLabels(labels, snapshotOf(lists));

/** One value per label (null where a point is missing), with its flags as a list. */
export function pointsOn(points, labels, key) {
  const by = new Map(points.map((p) => [p.label, p]));
  return labels.map((l) => {
    const p = by.get(l);
    const v = p?.[key];
    return { label: l, value: Number.isFinite(v) ? v : null, flags: p?.flags ? p.flags.split(";") : [] };
  });
}

/**
 * Draw now, again when the element's width changes (charts size to their box) and again when the
 * OS theme changes (chart.js reads the colour tokens at draw time; the data and selection stay).
 * Returns a release function that stops both; a chart in a replaceable container (the city
 * panel) must call it when the container's content goes. A disconnected node also lets go on
 * the next theme change.
 */
export function mount(el, draw) {
  let width = el.clientWidth;
  draw();
  const unsubscribe = onThemeChange(() => (el.isConnected ? draw() : off()));
  let timer = null;
  const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => {
    if (el.clientWidth === width) return;
    width = el.clientWidth;
    clearTimeout(timer);
    timer = setTimeout(draw, 120);
  });
  observer?.observe(el);
  function off() {
    unsubscribe();
    observer?.disconnect();
    clearTimeout(timer);
  }
  return off;
}

/** A bag of release functions: `add` one, `run` calls them all once and empties the bag. */
export function releaser() {
  let fns = [];
  return {
    add: (fn) => { if (typeof fn === "function") fns.push(fn); },
    run() {
      const todo = fns;
      fns = [];
      for (const fn of todo) fn();
    },
  };
}

/** A short note in place of a chart that could not be drawn (the tables still hold the data). */
export function failed(el, err) {
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = t("js.data.failed");
  el.replaceChildren(p);
  console.warn(err);
}

/**
 * Draw every [data-chart] mount that has a drawer in `draw` ({name: (el, D) => void}) from the
 * one series payload; a mount that throws, or a failed load, shows the table-fallback note.
 */
export function drawAll(draw) {
  const mounts = [...document.querySelectorAll("[data-chart]")].filter((el) => draw[el.dataset.chart]);
  if (!mounts.length) return;
  loadSeries()
    .then((D) => {
      for (const el of mounts) {
        try {
          draw[el.dataset.chart](el, D);
        } catch (err) {
          failed(el, err);
        }
      }
    })
    .catch((err) => mounts.forEach((el) => failed(el, err)));
}
