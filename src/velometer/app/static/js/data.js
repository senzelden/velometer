// The chart data of every page: one fetch of /data/series.json, and the small helpers that turn
// its series into chart.js models. No DOM drawing here.
import { xLabels } from "./chart-core.js";

/** Series colours (charts.CITY_COLOURS on the Python side, plus one). */
export const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#7a5bd1", "#52514e", "#008300"];
export const TIER_NAMES = {
  A: "A separated track",
  B: "B shared foot/cycle path",
  C: "C protected lane",
  D: "D painted lane",
  E: "E cycle street / bus lane",
};

let pending = null;

/** The payload, fetched once per page. Rejects on a non-200 answer. */
export function loadSeries() {
  pending ??= fetch("/data/series.json").then((r) => {
    if (!r.ok) throw new Error(`series.json: HTTP ${r.status}`);
    return r.json();
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

/** Draw now and again when the element's width changes (charts size to their box). */
export function mount(el, draw) {
  let width = el.clientWidth;
  draw();
  if (typeof ResizeObserver === "undefined") return;
  let timer = null;
  new ResizeObserver(() => {
    if (el.clientWidth === width) return;
    width = el.clientWidth;
    clearTimeout(timer);
    timer = setTimeout(draw, 120);
  }).observe(el);
}

/** A short note in place of a chart that could not be drawn (the tables still hold the data). */
export function failed(el, err) {
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = "Chart not available; the table on this page has the values.";
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
