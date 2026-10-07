// The Berlin plan page's charts: per plan item, the yearly target (steps) against the reported
// figures (one marker per document: the current figure filled, revisions hollow, suspect figures
// ringed), the infraVelo completed projects and our mapped-on-the-network change per year.
// Data: the page's <script type="application/json" id="plan-config">; every value is also in the
// tables under each chart. Built with createElementNS / textContent only.
import { niceTicks, scaleLinear, tickLabel, formatValue } from "./chart-core.js";
import { mount, failed } from "./data.js";

const NS = "http://www.w3.org/2000/svg";

/**
 * The chart series of one plan item. targets: {year: value} (empty or null: no target line);
 * reports: [{year, value, doc, quantity, current, suspect, note, ...}] (only figures for the
 * year itself are charted: cumulative and other quantities live in the tables); overlay:
 * [{date, ab_km}] snapshots of A+B mapped km on the network; projects: [{year, km}].
 * opts.mappedFrom: the first year of the mapped series (the plan's first target year).
 * mapped: the change in each year, from a 1 January snapshot to the next snapshot if that is the
 * following 1 January, or to a later snapshot within the same year (partial, the current run).
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
    }))
    // revisions first, so the current marker is drawn on top
    .sort((a, b) => a.year - b.year || a.current - b.current || String(a.docDate).localeCompare(String(b.docDate)));
  const proj = (projects ?? [])
    .map((p) => ({ year: p.year, value: p.km }))
    .sort((a, b) => a.year - b.year);
  const snaps = [...(overlay ?? [])].sort((a, b) => a.date.localeCompare(b.date));
  const from = opts.mappedFrom ?? -Infinity;
  const mapped = [];
  for (let i = 0; i + 1 < snaps.length; i++) {
    const a = snaps[i];
    const b = snaps[i + 1];
    const year = Number(a.date.slice(0, 4));
    if (a.date.slice(5) !== "01-01" || year < from) continue;
    const full = b.date === `${year + 1}-01-01`;
    if (!full && Number(b.date.slice(0, 4)) !== year) continue;
    mapped.push({ year, value: b.ab_km - a.ab_km, to: b.date, partial: !full });
  }
  return { target, reported, projects: proj, mapped };
}

function el(tag, attrs = {}, text) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, String(v));
  if (text != null) e.textContent = text;
  return e;
}

const titled = (node, text) => {
  node.appendChild(el("title", {}, text));
  return node;
};

/**
 * Draw `series` (planSeries) into `host`: one band per year (opts.years, else every year with a
 * value), target steps across each band, project and mapped bars either side of the reported
 * markers. opts: {label, years, unit, width, height}. No values: a note instead of an svg.
 */
export function renderPlanChart(host, series, opts = {}) {
  const unit = opts.unit ?? "km";
  const all = [
    ...series.target.map((p) => p.year),
    ...series.reported.map((p) => p.year),
  ];
  let years = opts.years?.length ? [...opts.years] : [...new Set(all)];
  years.sort((a, b) => a - b);
  const inRange = (p) => years.includes(p.year);
  const values = [
    ...series.target.filter(inRange),
    ...series.reported.filter(inRange),
    ...series.projects.filter(inRange),
    ...series.mapped.filter(inRange),
  ].map((p) => p.value);
  if (!years.length || !values.length) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = "No figures to chart for this item; the tables list what is recorded.";
    host.replaceChildren(p);
    return;
  }
  const W = Math.max(280, opts.width ?? host.clientWidth ?? 0);
  const H = opts.height ?? 240;
  const ml = 44;
  const mr = 10;
  const mt = 14;
  const mb = 26;
  const ticks = niceTicks(Math.min(0, ...values), Math.max(0, ...values), W < 480 ? 4 : 5);
  const y = scaleLinear([ticks[0], ticks.at(-1)], [H - mb, mt]);
  const band = (W - ml - mr) / years.length;
  const x0 = (yr) => ml + years.indexOf(yr) * band;
  const mid = (yr) => x0(yr) + band / 2;
  const barW = Math.max(3, Math.min(14, band / 6));

  const svg = el("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", class: "plan-svg" });
  const label = opts.label ? `Chart: ${opts.label}, target and figures by year` : "Plan chart";
  svg.setAttribute("aria-label", label);
  svg.appendChild(el("title", {}, label));
  for (const t of ticks) {
    svg.appendChild(el("line", { class: t === 0 ? "gridl zero" : "gridl", x1: ml, x2: W - mr, y1: y(t), y2: y(t) }));
    svg.appendChild(el("text", { class: "axis-t", x: ml - 6, y: y(t) + 3.5, "text-anchor": "end" }, tickLabel(t)));
  }
  const every = band < 34 ? 2 : 1;
  years.forEach((yr, i) => {
    if ((years.length - 1 - i) % every) return;
    svg.appendChild(el("text", { class: "axis-t", x: mid(yr), y: H - mb + 16, "text-anchor": "middle" }, String(yr)));
  });
  svg.appendChild(el("text", { class: "ylab", x: ml, y: mt - 4 }, `${unit} per year`));

  const bars = (points, cls, dx, what) => {
    const g = el("g", { class: cls });
    for (const p of points.filter(inRange)) {
      const top = y(Math.max(0, p.value));
      const h = Math.abs(y(p.value) - y(0));
      const text = `${what}, ${p.year}${p.partial ? ` (to ${p.to})` : ""}: ${formatValue(p.value)} ${unit}`;
      g.appendChild(titled(el("rect", { class: p.partial ? "bar partial" : "bar", x: mid(p.year) + dx - barW / 2, y: top, width: barW, height: Math.max(1, h) }), text));
    }
    svg.appendChild(g);
  };
  bars(series.projects, "projects", -barW * 1.6, "Completed projects");
  bars(series.mapped, "mapped", barW * 1.6, "Mapped on the network, change in the year");

  const steps = series.target.filter(inRange);
  if (steps.length) {
    const g = el("g", { class: "target" });
    let d = "";
    for (const p of steps) {
      const yy = y(p.value).toFixed(1);
      d += `M${(x0(p.year) + 2).toFixed(1)},${yy}H${(x0(p.year) + band - 2).toFixed(1)}`;
    }
    g.appendChild(titled(el("path", { class: "target-step", d }), `Target: ${steps.map((p) => `${p.year} ${formatValue(p.value)} ${unit}`).join(", ")}`));
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
    const text = `Reported ${p.year}: ${formatValue(p.value)} ${unit}, ${p.doc}` +
      `${p.current ? " (current)" : " (revision)"}${p.suspect ? `, suspect${p.note ? `: ${p.note}` : ""}` : ""}`;
    g.appendChild(titled(el("circle", { class: cls, cx, cy: y(p.value), r: p.suspect ? 5.5 : 4.5 }), text));
  }
  svg.appendChild(g);
  host.replaceChildren(svg);
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
      mount(m, () => renderPlanChart(m, series, { label: item.label, years, unit: item.unit }));
    } catch (err) {
      failed(m, err);
    }
  }
}

if (typeof document !== "undefined" && typeof document.getElementById === "function") boot();
