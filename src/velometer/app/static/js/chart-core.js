// Pure chart maths: no DOM, no I/O. chart.js draws what these functions compute.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Linear scale from a domain to a range; a zero-width domain maps to the range start. */
export function scaleLinear([d0, d1], [r0, r1]) {
  const span = d1 - d0;
  return (v) => (span === 0 ? r0 : r0 + ((v - d0) / span) * (r1 - r0));
}

/** "Nice" tick values that cover [min, max], about `count` of them. */
export function niceTicks(min, max, count = 5) {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [];
  let lo = min;
  let hi = max;
  if (hi === lo) hi = lo + 1;
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const ticks = [];
  for (let v = Math.floor(lo / step) * step; v <= hi + step * 1e-9; v += step) {
    ticks.push(+v.toFixed(10));
  }
  if (ticks.at(-1) < hi) ticks.push(+(ticks.at(-1) + step).toFixed(10));
  return ticks;
}

/** Rebase a series so `baseLabel` = 100. Null everywhere if the base is missing or 0. */
export function indexSeries(points, baseLabel) {
  const base = points.find((p) => p.label === baseLabel)?.value;
  const ok = base != null && base !== 0;
  return points.map((p) => ({
    label: p.label,
    value: ok && p.value != null ? (p.value / base) * 100 : null,
  }));
}

/** Competition ranking, 1 = highest value; ties share a rank, nulls stay unranked. */
export function ranks(valuesByCity) {
  const out = {};
  const present = Object.entries(valuesByCity).filter(([, v]) => v != null);
  for (const [id, v] of present) out[id] = 1 + present.filter(([, w]) => w > v).length;
  for (const id of Object.keys(valuesByCity)) if (!(id in out)) out[id] = null;
  return out;
}

/**
 * Spread labels vertically: order by y is kept, no two closer than minGap, all within
 * [top, bottom]. Returns {id: y}.
 */
export function placeLabels(items, minGap, top, bottom) {
  // Too many labels for the range: compress the gap so everything still fits.
  if (items.length > 1) minGap = Math.min(minGap, (bottom - top) / (items.length - 1));
  const sorted = items
    .map((it, i) => ({ id: it.id, y: it.y, i }))
    .sort((a, b) => a.y - b.y || a.i - b.i);
  for (let k = 0; k < 60; k++) {
    let moved = false;
    for (let i = 1; i < sorted.length; i++) {
      const d = sorted[i].y - sorted[i - 1].y;
      if (d < minGap) {
        const s = (minGap - d) / 2;
        sorted[i].y += s;
        sorted[i - 1].y -= s;
        moved = true;
      }
    }
    for (const it of sorted) it.y = Math.max(top, Math.min(bottom, it.y));
    if (!moved) break;
  }
  // Guarantee: top-down push, then bottom-up pull back inside the bounds.
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].y - sorted[i - 1].y < minGap) sorted[i].y = sorted[i - 1].y + minGap;
  }
  if (sorted.length && sorted.at(-1).y > bottom) {
    sorted.at(-1).y = bottom;
    for (let i = sorted.length - 2; i >= 0; i--) {
      if (sorted[i + 1].y - sorted[i].y < minGap) sorted[i].y = sorted[i + 1].y - minGap;
    }
  }
  return Object.fromEntries(sorted.map((it) => [it.id, it.y]));
}

/**
 * Stable colours: highlighted ids keep the colour they had, newcomers take colours that are
 * free (first in palette order). At most palette.length ids are coloured.
 */
export function assignColours(prev, highlighted, palette) {
  const out = {};
  const used = new Set();
  for (const id of highlighted) {
    if (out[id] === undefined && palette.includes(prev[id]) && !used.has(prev[id])) {
      out[id] = prev[id];
      used.add(prev[id]);
    }
  }
  const free = palette.filter((c) => !used.has(c));
  for (const id of highlighted) {
    if (out[id] === undefined && free.length) out[id] = free.shift();
  }
  // keep input order in the result
  return Object.fromEntries(highlighted.filter((id) => id in out).map((id) => [id, out[id]]));
}

/** X-axis labels; the `current` run is shown as the snapshot month ("Oct 2026"). */
export function xLabels(labels, snapshot) {
  let text = null;
  if (snapshot instanceof Date) {
    text = `${MONTHS[snapshot.getUTCMonth()]} ${snapshot.getUTCFullYear()}`;
  } else if (typeof snapshot === "string" && /^\d{4}-\d{2}/.test(snapshot)) {
    text = `${MONTHS[Number(snapshot.slice(5, 7)) - 1]} ${snapshot.slice(0, 4)}`;
  }
  return labels.map((l) => (l === "current" && text ? text : l));
}

/** Compact y-axis tick text, en-GB. */
export function tickLabel(v) {
  const a = Math.abs(v);
  if (a >= 10000) return (v / 1000).toLocaleString("en-GB", { maximumFractionDigits: 0 }) + "k";
  return v.toLocaleString("en-GB", { maximumFractionDigits: a < 10 && v % 1 ? 1 : 0 });
}

/** Exact value for tooltips: thousands separators, at most one decimal, never "12k". */
export function formatValue(v) {
  return v.toLocaleString("en-GB", { maximumFractionDigits: 1 });
}

/** Estimated rendered width of axis text, px (the axis font is small and proportional). */
export const textWidth = (text, charW = 6.2) => String(text).length * charW;

/**
 * Which x-axis labels to draw: the last one always (it is the newest run), then every `stride`-th
 * going back, with the smallest stride at which no two neighbouring labels come closer than
 * `gap` px (widths estimated from the text; `step` is the px between neighbouring points).
 * Returns ascending indices.
 */
export function tickIndices(texts, step, gap = 8) {
  const n = texts.length;
  if (n === 0) return [];
  for (let stride = 1; stride < n; stride++) {
    const idx = [];
    for (let i = n - 1; i >= 0; i -= stride) idx.unshift(i);
    const fits = idx.every(
      (i, k) =>
        k === 0 ||
        (i - idx[k - 1]) * step >= textWidth(texts[i]) / 2 + textWidth(texts[idx[k - 1]]) / 2 + gap,
    );
    if (fits) return idx;
  }
  return [n - 1];
}
