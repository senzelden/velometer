// The Berlin plan page's charts: per plan item, the yearly target (steps) against the reported
// figures (one marker per document: the current figure filled, revisions hollow, suspect figures
// ringed), the infraVelo completed projects per year and our mapped-on-the-network change since
// 1 January of the plan's first target year (a line, one point per OSM snapshot).
// Data: the page's <script type="application/json" id="plan-config">; every value is also in the
// tables under each chart. Built with createElementNS / textContent only.
import { niceTicks, scaleLinear, tickLabel, formatValue, textWidth } from "./chart-core.js";
import { mount, failed } from "./data.js";
import { t } from "./strings.js";

const NS = "http://www.w3.org/2000/svg";

/** A target above this many times the largest figure is capped at the chart's top edge. */
export const OFFSCALE_FACTOR = 3;
// target kinds whose steps are km per year, the quantity of every charted figure
const PER_YEAR = new Set(["km_per_year", "none"]);
/** A target kind's word on the y label ("cumulative"); a kind without one is named by its id. */
const quantityText = (q) =>
  ({ km_cumulative: () => t("js.plan.cumulative"), km_total: () => t("js.plan.total"), share: () => t("js.plan.share") })[q]?.() ?? q;
const LINE = 12; // one line of axis text, px

/**
 * The chart series of one plan item. targets: {year: value} (empty or null: no target line);
 * reports: [{year, value, doc, quantity, current, suspect, note, ...}] (only figures for the
 * year itself are charted: cumulative and other quantities live in the tables); overlay:
 * [{date, ab_km}] snapshots of A+B mapped km on the network; projects: [{year, km}].
 * opts.mappedFrom: the baseline year of the mapped series (the plan's first target year).
 * mapped: per snapshot from 1 January of that year on, the change in A+B mapped km since the
 * 1 January snapshot (spec §4.4: "change since 2022-01-01"); `at` is the snapshot's position in
 * years (2026-10-03 -> 2026.75). No baseline snapshot: no series.
 */
export function planSeries(targets, reports, overlay, projects, opts = {}) {
  const target = Object.entries(targets ?? {})
    .map(([y, v]) => ({ year: Number(y), value: v }))
    .sort((a, b) => a.year - b.year);
  const reported = (reports ?? [])
    .filter((r) => (r.quantity ?? "implemented_in_year") === "implemented_in_year")
    .map((r) => ({
      year: r.year,
      value: r.value,
      doc: r.doc,
      docType: r.doc_type,
      docDate: r.doc_date,
      current: !!r.current,
      suspect: !!r.suspect,
      note: r.note ?? null,
      noteFallback: !!r.note_fallback,
    }))
    // revisions first, so the current marker is drawn on top
    .sort((a, b) => a.year - b.year || a.current - b.current || String(a.docDate).localeCompare(String(b.docDate)));
  const proj = (projects ?? [])
    .map((p) => ({ year: p.year, value: p.km }))
    .sort((a, b) => a.year - b.year);
  const snaps = [...(overlay ?? [])].sort((a, b) => a.date.localeCompare(b.date));
  const from = opts.mappedFrom ?? (snaps.length ? Number(snaps[0].date.slice(0, 4)) : null);
  const baseline = snaps.find((p) => p.date === `${from}-01-01`);
  const mapped = baseline
    ? snaps
        .filter((p) => p.date >= baseline.date)
        .map((p) => ({ date: p.date, year: Number(p.date.slice(0, 4)), at: yearPosition(p.date), value: p.ab_km - baseline.ab_km }))
    : [];
  return { target, reported, projects: proj, mapped, mappedFrom: baseline ? from : null };
}

/** A date's position in years: 1 January of Y is Y, 1 July about Y.5. */
export function yearPosition(date) {
  const y = Number(date.slice(0, 4));
  const start = Date.UTC(y, 0, 1);
  const days = (Date.UTC(y + 1, 0, 1) - start) / 864e5;
  return y + (Date.parse(`${date}T00:00:00Z`) - start) / 864e5 / days;
}

/**
 * The y domain: the step comes from the positive span (niceTicks over [0, max]); a negative
 * minimum only adds the room it needs (5 % of the span below it), never a whole negative step.
 * Ticks are those inside [lo, hi], 0 always among them. All values negative: niceTicks as is.
 * opts.headroom: the top tick lies at least one step above the largest value (with caps on the
 * top edge, no value drawn on scale shares their line).
 */
export function yDomain(values, count = 5, opts = {}) {
  const max = Math.max(0, ...values);
  const min = Math.min(0, ...values);
  if (max <= 0) {
    const ticks = niceTicks(min, 0, count);
    return { lo: ticks[0], hi: ticks.at(-1), ticks };
  }
  const up = niceTicks(0, max, count);
  const step = up[1] - up[0];
  if (opts.headroom && up.at(-1) - max < step - 1e-9) up.push(+(up.at(-1) + step).toFixed(10));
  const hi = up.at(-1);
  const lo = min < 0 ? min - 0.05 * (hi - min) : 0;
  const ticks = [];
  for (let v = -step; v >= lo; v -= step) ticks.unshift(+v.toFixed(10));
  return { lo, hi, ticks: [...ticks, ...up] };
}

/**
 * Which target steps the y axis holds. A step above OFFSCALE_FACTOR x the largest figure
 * (reported, completed or mapped) is off scale: the axis is set by the figures and the nearer
 * steps, and the far ones are drawn as caps on the top edge. No figure above 0: all on scale.
 */
export function targetScale(steps, figures) {
  const top = Math.max(0, ...figures);
  if (!(top > 0)) return { onScale: [...steps], offScale: [] };
  const off = (p) => p.value > OFFSCALE_FACTOR * top;
  return { onScale: steps.filter((p) => !off(p)), offScale: steps.filter(off) };
}

/**
 * The y domain and the targets it holds, agreeing: with caps the domain keeps a step of
 * headroom (yDomain), and that can lift its top past an off-scale target. Such a target is
 * drawn on the scale and the domain is set again, until every cap lies above the top.
 * Returns {steps (on scale, by year), offScale, dom}.
 */
export function settleScale({ onScale, offScale }, figures, count = 5) {
  let steps = [...onScale];
  let off = [...offScale];
  for (;;) {
    const values = [...steps.map((p) => p.value), ...figures];
    const dom = yDomain(values, count, { headroom: off.length > 0 });
    const inside = off.filter((p) => p.value <= dom.hi);
    if (!inside.length) return { steps, offScale: off, dom };
    steps = [...steps, ...inside].sort((a, b) => a.year - b.year);
    off = off.filter((p) => p.value > dom.hi);
  }
}

function el(tag, attrs = {}, text) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, String(v));
  if (text != null) e.textContent = text;
  return e;
}

const titled = (node, text, fallback = false) => {
  // a note still in English on a German page is marked, as the table row marks it
  node.appendChild(el("title", fallback ? { lang: "en", "data-fallback": "" } : {}, text));
  return node;
};

/**
 * Where the date label of the last snapshot goes: above-left of the point (x, y), else above-right,
 * below-left, below-right, the first whose box (width w, 10px text) crosses no target step and
 * stays inside the plot [left, right, top, bottom]; none fits: above-left. Returns text attributes.
 */
export function labelSpot(x, y, w, segments, [left, right, top, bottom]) {
  const spots = [
    { x: x - 4, y: y - 7, "text-anchor": "end" },
    { x: x + 4, y: y - 7, "text-anchor": "start" },
    { x: x - 4, y: y + 13, "text-anchor": "end" },
    { x: x + 4, y: y + 13, "text-anchor": "start" },
  ];
  const fits = (s) => {
    const [x1, x2] = s["text-anchor"] === "end" ? [s.x - w, s.x] : [s.x, s.x + w];
    const [y1, y2] = [s.y - 9, s.y + 2]; // cap height to below the baseline
    if (x1 < left || x2 > right || y1 < top || y2 > bottom) return false;
    return !segments.some((g) => g.x1 < x2 && g.x2 > x1 && g.y >= y1 && g.y <= y2);
  };
  return spots.find(fits) ?? spots[0];
}

/**
 * Draw `series` (planSeries) into `host`: one band per year (opts.years, else every year with a
 * value), target steps across each band, completed-project bars beside the reported markers and
 * the mapped line (positioned by snapshot date, its last point labelled with the date).
 * opts: {label, years, unit, quantity, width, height}; quantity is the item's target_kind, and
 * the y label says it. The charted figures are per year: a cumulative or total target is not
 * drawn against them (a note under the chart says so; the table lists it), only on its own.
 * Off-scale targets (targetScale, then settleScale) are caps on the top edge, their values labelled. Margins
 * follow the labels: every text lies inside the svg. No values: a note instead of an svg.
 */
export function renderPlanChart(host, series, opts = {}) {
  const unit = opts.unit ?? "km";
  const quantity = opts.quantity ?? "km_per_year";
  const all = [
    ...series.target.map((p) => p.year),
    ...series.reported.map((p) => p.year),
  ];
  let years = opts.years?.length ? [...opts.years] : [...new Set(all)];
  years.sort((a, b) => a - b);
  const inRange = (p) => years.includes(p.year);
  const mapped = series.mapped.filter(inRange);
  const figures = [
    ...series.reported.filter(inRange),
    ...series.projects.filter(inRange),
    ...mapped,
  ].map((p) => p.value);
  const perYear = PER_YEAR.has(quantity);
  const drawTarget = perYear || !figures.length;
  const scaled = drawTarget
    ? targetScale(series.target.filter(inRange), figures)
    : { onScale: [], offScale: [] };
  const values = [...scaled.onScale.map((p) => p.value), ...figures];
  if (!years.length || !values.length) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = t("js.plan.no_figures");
    host.replaceChildren(p);
    return;
  }
  const W = Math.max(280, opts.width ?? host.clientWidth ?? 0);
  const H = opts.height ?? 240;
  const { steps, offScale, dom } = settleScale(scaled, figures, W < 480 ? 4 : 5);
  const ticks = dom.ticks;
  // left: the widest tick label and its 6 px gap, 4 px to spare; right: the last band's edge
  const ml = Math.ceil(Math.max(...ticks.map((tick) => textWidth(tickLabel(tick))))) + 10;
  const mr = 10;
  const axis = perYear || !drawTarget ? t("js.plan.per_year", { unit }) : `${unit}, ${quantityText(quantity)}`;
  const line = mapped.length ? t("js.plan.line", { year: series.mappedFrom }) : null;
  const oneLine = line ? `${axis} · ${line}` : axis;
  const ylines = !line || textWidth(oneLine) <= W - ml - mr ? [oneLine] : [axis, line];
  // the y label's lines, then a row for the off-scale caps' values, then the plot
  const mt = 14 + (ylines.length - 1) * LINE + (offScale.length ? LINE : 0);
  const mb = 26;
  const y = scaleLinear([dom.lo, dom.hi], [H - mb, mt]);
  const band = (W - ml - mr) / years.length;
  const x0 = (yr) => ml + years.indexOf(yr) * band;
  const mid = (yr) => x0(yr) + band / 2;
  const barW = Math.max(3, Math.min(14, band / 6));

  const svg = el("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", class: "plan-svg" });
  const label = opts.label ? t("js.plan.chart_of", { label: opts.label }) : t("js.plan.chart");
  svg.setAttribute("aria-label", label);
  svg.appendChild(el("title", {}, label));
  for (const tick of ticks) {
    svg.appendChild(el("line", { class: tick === 0 ? "gridl zero" : "gridl", x1: ml, x2: W - mr, y1: y(tick), y2: y(tick) }));
    svg.appendChild(el("text", { class: "axis-t", x: ml - 6, y: y(tick) + 3.5, "text-anchor": "end" }, tickLabel(tick)));
  }
  const every = band < 34 ? 2 : 1;
  years.forEach((yr, i) => {
    if ((years.length - 1 - i) % every) return;
    svg.appendChild(el("text", { class: "axis-t", x: mid(yr), y: H - mb + 16, "text-anchor": "middle" }, String(yr)));
  });
  ylines.forEach((text, i) => svg.appendChild(el("text", { class: "ylab", x: ml, y: 10 + i * LINE }, text)));

  const bars = (points, cls, dx, what) => {
    const g = el("g", { class: cls });
    for (const p of points.filter(inRange)) {
      const top = y(Math.max(0, p.value));
      const h = Math.abs(y(p.value) - y(0));
      const text = `${what}, ${p.year}: ${formatValue(p.value)} ${unit}`;
      g.appendChild(titled(el("rect", { class: "bar", x: mid(p.year) + dx - barW / 2, y: top, width: barW, height: Math.max(1, h) }), text));
    }
    svg.appendChild(g);
  };
  bars(series.projects, "projects", -barW * 1.6, t("js.plan.completed"));
  const segments = steps.map((p) => ({ x1: x0(p.year) + 2, x2: x0(p.year) + band - 2, y: y(p.value) }));

  if (mapped.length) {
    // a snapshot sits at its date: 1 January of Y on the left edge of Y's band
    const xAt = (p) => x0(p.year) + (p.at - p.year) * band;
    const g = el("g", { class: "mapped" });
    const d = mapped.map((p, i) => `${i ? "L" : "M"}${xAt(p).toFixed(1)},${y(p.value).toFixed(1)}`).join("");
    g.appendChild(el("path", { class: "mapped-line", d }));
    for (const p of mapped) {
      const sign = p.value > 0 ? "+" : "";
      const text = t("js.plan.mapped_point", { date: p.date, value: `${sign}${formatValue(p.value)}`, year: series.mappedFrom });
      g.appendChild(titled(el("circle", { class: "mapped-pt", cx: xAt(p), cy: y(p.value), r: 3 }), text));
    }
    const last = mapped.at(-1);
    const spot = labelSpot(xAt(last), y(last.value), textWidth(last.date), segments, [ml, W - mr, mt, H - mb]);
    g.appendChild(el("text", { class: "mapped-label", ...spot }, last.date));
    svg.appendChild(g);
  }

  if (steps.length) {
    const g = el("g", { class: "target" });
    let d = "";
    for (const p of steps) {
      const yy = y(p.value).toFixed(1);
      d += `M${(x0(p.year) + 2).toFixed(1)},${yy}H${(x0(p.year) + band - 2).toFixed(1)}`;
    }
    const list = steps.map((p) => `${p.year} ${formatValue(p.value)} ${unit}`).join(", ");
    g.appendChild(titled(el("path", { class: "target-step", d }), t("js.plan.target", { steps: list })));
    svg.appendChild(g);
  }
  if (offScale.length) {
    // off the scale: a cap on the top edge of the band, the value above it (every target is
    // also in the table under the chart)
    const g = el("g", { class: "target offscale" });
    for (const p of offScale) {
      const d = `M${(x0(p.year) + 2).toFixed(1)},${mt}H${(x0(p.year) + band - 2).toFixed(1)}`;
      const text = t("js.plan.target_cap", { year: p.year, value: formatValue(p.value), unit });
      g.appendChild(titled(el("path", { class: "target-cap", d }), text));
      const wide = `↑ ${formatValue(p.value)}`;
      const value = textWidth(wide) <= band ? wide : `↑${formatValue(p.value)}`;
      g.appendChild(el("text", { class: "target-cap-label", x: mid(p.year), y: mt - 3, "text-anchor": "middle" }, value));
    }
    svg.appendChild(g);
  }

  const g = el("g", { class: "reported" });
  const offsets = {};
  for (const p of series.reported.filter(inRange)) {
    // documents agreeing on a value would hide one another: spread them a little
    const key = `${p.year}`;
    const k = (offsets[key] = (offsets[key] ?? -1) + 1);
    const cx = mid(p.year) + (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 3;
    const cls = ["rep", p.current ? "rep-current" : "rep-revision", p.suspect ? "rep-suspect" : null]
      .filter(Boolean)
      .join(" ");
    const which = p.current ? t("js.plan.current") : t("js.plan.revision");
    const suspect = p.suspect ? `, ${p.note ? t("js.plan.suspect_note", { note: p.note }) : t("js.plan.suspect")}` : "";
    const text = `${t("js.plan.reported", { year: p.year, value: formatValue(p.value), unit, doc: p.doc })} ${which}${suspect}`;
    g.appendChild(titled(el("circle", { class: cls, cx, cy: y(p.value), r: p.suspect ? 5.5 : 4.5 }), text, p.suspect && !!p.note && p.noteFallback));
  }
  svg.appendChild(g);
  if (drawTarget || !series.target.some(inRange)) {
    host.replaceChildren(svg);
    return;
  }
  const note = document.createElement("p");
  note.className = "meta plan-chart-note";
  note.textContent = t("js.plan.not_drawn", { unit, quantity: quantityText(quantity) });
  host.replaceChildren(svg, note);
}

function boot() {
  const node = document.getElementById("plan-config");
  if (!node) return;
  let config;
  try {
    config = JSON.parse(node.textContent);
  } catch (err) {
    document.querySelectorAll("[data-plan-item]").forEach((m) => failed(m, err));
    return;
  }
  const items = Object.fromEntries(config.items.map((i) => [i.id, i]));
  for (const m of document.querySelectorAll("[data-plan-item]")) {
    const item = items[m.dataset.planItem];
    if (!item) continue;
    try {
      const series = planSeries(item.targets, item.reports, item.overlay, item.projects, {
        mappedFrom: config.mapped_from,
      });
      // every year from the first to the last target or reported figure, gaps included
      const ys = [...series.target, ...series.reported].map((p) => p.year);
      const years = ys.length
        ? Array.from({ length: Math.max(...ys) - Math.min(...ys) + 1 }, (_, i) => Math.min(...ys) + i)
        : [];
      mount(m, () =>
        renderPlanChart(m, series, { label: item.label, years, unit: item.unit, quantity: item.target_kind }),
      );
    } catch (err) {
      failed(m, err);
    }
  }
}

if (typeof document !== "undefined" && typeof document.getElementById === "function") boot();
