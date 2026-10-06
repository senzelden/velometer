// Hand-rolled SVG charts. Layout maths lives in chart-core.js; this file only draws.
// Everything is built with createElementNS / textContent: nothing from data reaches innerHTML.
import { scaleLinear, niceTicks, placeLabels, tickLabel, formatValue, textWidth, tickIndices } from "./chart-core.js";

const NS = "http://www.w3.org/2000/svg";
export const TIER_COLOURS = { A: "#1f5fae", B: "#6fa5e6", C: "#1a9e77", D: "#eb9a54", E: "#a59fc9" };

function svgEl(tag, attrs = {}, text) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, String(v));
  if (text != null) e.textContent = text;
  return e;
}

const widthOf = (el, opts) => Math.max(220, opts?.width ?? el.clientWidth ?? 0);
const fit = (t, px) => {
  const max = Math.max(3, Math.floor(px / 6.3));
  return t.length > max ? t.slice(0, max - 1) + "…" : t;
};

// a series may carry a `short` name for an end label that has no room for the full one
const endName = (s, px) => (s.short && fit(s.name, px) !== s.name ? s.short : s.name);

function emptyNote(el, message = "No values for this selection.") {
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = message;
  el.replaceChildren(p);
}

function nameSvg(svg, label) {
  svg.setAttribute("aria-label", label);
  svg.insertBefore(svgEl("title", {}, label), svg.firstChild);
}

function makeTip(el) {
  const tip = document.createElement("div");
  tip.className = "tip";
  tip.hidden = true;
  el.appendChild(tip);
  return tip;
}

function placeTip(tip, x, y, width) {
  tip.hidden = false;
  let tx = x + 14;
  if (tx + tip.offsetWidth > width) tx = x - tip.offsetWidth - 14;
  tip.style.left = `${Math.max(0, tx)}px`;
  tip.style.top = `${Math.max(0, y - tip.offsetHeight - 10)}px`;
}

function segDist(px, py, ax, ay, bx, by) {
  const dx = bx - ax;
  const dy = by - ay;
  const l = dx * dx + dy * dy;
  const t = l ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l)) : 0;
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

/**
 * Lines. model: {labels: string[], series: [{id, name, colour?, ghost?, points: [{value, flags?}]}],
 * yTitle?}. Series with a colour are highlighted, without are grey context, ghost ones are
 * faint and unlabelled. opts: {height, width, compact, zero, invert, intTicks, yDomain,
 * tip(series, point, label) -> string, onPick(id, label)}.
 */
export function renderLines(el, model, opts = {}) {
  const W = widthOf(el, opts);
  const H = opts.height ?? 320;
  const compact = !!opts.compact;
  const narrow = W < 560;
  const labels = model.labels;
  const n = labels.length;
  const live = model.series.filter((s) => !s.ghost);
  const coloured = live.filter((s) => s.colour);
  const values = model.series
    .flatMap((s) => s.points.map((p) => p.value))
    .filter(Number.isFinite);
  if (!values.length) return emptyNote(el);

  let [lo, hi] = opts.yDomain ?? [Math.min(...values), Math.max(...values)];
  if (opts.zero && !opts.yDomain) lo = Math.min(0, lo);
  let ticks;
  if (opts.intTicks) {
    const st = Math.max(1, Math.ceil((hi - lo) / 10));
    ticks = [];
    for (let v = lo; v <= hi; v += st) ticks.push(v);
  } else {
    ticks = niceTicks(lo, hi, compact ? 3 : narrow ? 4 : 6);
    lo = ticks[0];
    hi = ticks.at(-1);
  }

  const labelled = compact ? [] : narrow && live.length > 8 ? coloured : live;
  const longest = Math.max(0, ...labelled.map((s) => s.name.length));
  const axisTexts = labels.map((l) =>
    compact && /\d{4}$/.test(l) && l.length > 4 ? l.replace(/ \d{2}(\d{2})$/, " $1") : l,
  );
  // the last x label is centred on the last point: leave room for its right half
  const lastHalf = Math.ceil(textWidth(axisTexts.at(-1) ?? "") / 2) + 2;
  const mr = Math.max(
    labelled.length ? Math.min(narrow ? 82 : 130, longest * 6.4 + 22) : compact ? 6 : 16,
    lastHalf,
  );
  const ml = compact ? 30 : 44;
  const mt = compact ? 6 : 14;
  const mb = compact ? 18 : 30;
  const iw = W - ml - mr;
  const ih = H - mt - mb;
  const step = iw / Math.max(1, n - 1);
  const x = (i) => ml + i * step;
  const yScale = scaleLinear([lo, hi], opts.invert ? [mt, mt + ih] : [mt + ih, mt]);

  const svg = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img" });
  nameSvg(svg, opts.label ?? (model.yTitle ? `Line chart: ${model.yTitle}` : "Line chart"));
  for (const t of ticks) {
    const ty = yScale(t);
    svg.appendChild(svgEl("line", { class: "gridl", x1: ml, x2: ml + iw, y1: ty, y2: ty }));
    // compact cards: the lowest y label would sit on the first x label
    if (compact && ticks.length > 1 && t === ticks[0]) continue;
    svg.appendChild(
      svgEl("text", { class: "axis-t", x: ml - 6, y: ty + 3.5, "text-anchor": "end" },
        opts.intTicks ? `#${t}` : tickLabel(t)),
    );
  }
  for (const i of tickIndices(axisTexts, step)) {
    svg.appendChild(
      svgEl("text", { class: "axis-t", x: x(i), y: H - mb + (compact ? 13 : 17),
        "text-anchor": "middle" }, axisTexts[i]),
    );
  }
  if (model.yTitle && !compact) {
    svg.appendChild(svgEl("text", { class: "ylab", x: ml, y: mt - 4 }, model.yTitle));
  }

  const order = [
    ...model.series.filter((s) => s.ghost),
    ...live.filter((s) => !s.colour),
    ...coloured,
  ];
  const geo = {};
  const groups = {};
  const endItems = [];
  for (const s of order) {
    const pts = s.points.map((p, i) => (Number.isFinite(p.value) ? [x(i), yScale(p.value)] : null));
    geo[s.id] = pts;
    let d = "";
    let pen = false;
    for (const p of pts) {
      if (!p) { pen = false; continue; }
      d += `${pen ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`;
      pen = true;
    }
    const g = svgEl("g", { class: s.ghost ? "s ghost" : s.colour ? "s" : "s gray", "data-id": s.id });
    groups[s.id] = g;
    g.appendChild(svgEl("path", { class: "line", d, fill: "none", stroke: s.colour ?? null }));
    if (!s.ghost) {
      s.points.forEach((p, i) => {
        if (!pts[i]) return;
        if (p.flags?.length) {
          g.appendChild(svgEl("circle", { class: "flag", cx: pts[i][0], cy: pts[i][1],
            r: compact ? 3 : s.colour ? 4.5 : 3.5 }));
        } else if (!s.ghost && !pts[i - 1] && !pts[i + 1]) {
          // isolated point between gaps: a line would be invisible, so draw a dot
          g.appendChild(svgEl("circle", { cx: pts[i][0], cy: pts[i][1], r: 2.4, fill: s.colour ?? "#8a8a8a" }));
        } else if (s.colour && !compact && n <= 12) {
          g.appendChild(svgEl("circle", { cx: pts[i][0], cy: pts[i][1], r: 2.2, fill: s.colour }));
        }
      });
      const last = pts.findLastIndex(Boolean);
      if (last >= 0 && labelled.includes(s)) endItems.push({ s, x0: pts[last][0], y0: pts[last][1] });
    }
    svg.appendChild(g);
  }

  const placed = placeLabels(endItems.map((it) => ({ id: it.s.id, y: it.y0 })), 12, mt + 4, mt + ih + 4);
  for (const it of endItems) {
    const y = placed[it.s.id];
    const g = groups[it.s.id];
    if (Math.abs(y - it.y0) > 2) {
      g.appendChild(svgEl("line", { class: "leader", x1: it.x0 + 2, y1: it.y0, x2: it.x0 + 7, y2: y }));
    }
    g.appendChild(
      svgEl("text", { class: "el", x: it.x0 + 8, y: y + 3.5, "text-anchor": "start",
        fill: it.s.colour ?? null }, fit(endName(it.s, mr - 10), mr - 10)),
    );
  }

  const hx = svgEl("line", { class: "hover-x", x1: 0, x2: 0, y1: mt, y2: mt + ih, visibility: "hidden" });
  const hp = svgEl("circle", { class: "hover-pt", r: 5, fill: "none", stroke: "currentColor",
    "stroke-width": 2, visibility: "hidden" });
  const hit = svgEl("rect", { class: "hit", x: ml - 10, y: 0, width: iw + 20, height: H, fill: "transparent" });
  svg.append(hx, hp, hit);
  el.replaceChildren(svg);
  const tip = makeTip(el);

  const pool = opts.hoverOnly ? live.filter((s) => s.id === opts.hoverOnly) : live;
  let cur = null;
  const clear = () => {
    svg.classList.remove("dim");
    for (const g of Object.values(groups)) g.classList.remove("on");
    tip.hidden = true;
    hx.setAttribute("visibility", "hidden");
    hp.setAttribute("visibility", "hidden");
    cur = null;
  };
  const nearest = (mx, my) => {
    let best = null;
    let bd = Infinity;
    for (const s of pool) {
      const pts = geo[s.id];
      pts.forEach((a, i) => {
        if (!a) return;
        const b = pts[i + 1];
        const d = b ? segDist(mx, my, a[0], a[1], b[0], b[1]) : Math.hypot(mx - a[0], my - a[1]);
        if (d < bd) { bd = d; best = s; }
      });
    }
    return pool.length === 1 || bd < (compact ? 40 : 26) ? best : null;
  };
  const show = (ev) => {
    const r = svg.getBoundingClientRect();
    const mx = ev.clientX - r.left;
    const s = nearest(mx, ev.clientY - r.top);
    if (!s) return clear();
    const pts = geo[s.id];
    let i = Math.max(0, Math.min(n - 1, Math.round((mx - ml) / step)));
    if (!pts[i]) {
      const have = pts.map((p, k) => (p ? k : -1)).filter((k) => k >= 0);
      if (!have.length) return;
      i = have.reduce((a, b) => (Math.abs(b - i) < Math.abs(a - i) ? b : a));
    }
    cur = { s, i };
    if (model.series.length > 1) {
      svg.classList.add("dim");
      for (const [id, g] of Object.entries(groups)) g.classList.toggle("on", id === s.id);
    }
    hx.setAttribute("x1", pts[i][0]);
    hx.setAttribute("x2", pts[i][0]);
    hx.setAttribute("visibility", "visible");
    hp.setAttribute("cx", pts[i][0]);
    hp.setAttribute("cy", pts[i][1]);
    hp.setAttribute("visibility", "visible");
    const p = s.points[i];
    tip.textContent = opts.tip ? opts.tip(s, p, labels[i]) : `${s.name} · ${labels[i]}: ${formatValue(p.value)}`;
    placeTip(tip, pts[i][0], pts[i][1], W);
  };
  hit.addEventListener("pointermove", show);
  hit.addEventListener("pointerdown", show);
  hit.addEventListener("pointerleave", clear);
  hit.addEventListener("click", (e) => {
    if (opts.hoverOnly || !cur || !opts.onPick) return;
    e.stopPropagation();
    const p = cur.s.points[cur.i];
    opts.onPick(cur.s.id, p.flags?.length ? labels[cur.i] : "");
  });
}

/**
 * Small multiples, one card per series. model as for renderLines. opts add {shared: boolean}
 * (one y scale for every card) and onPick; each card gets class "sm-card" and data-id.
 */
export function renderSmallMultiples(el, model, opts = {}) {
  const grid = document.createElement("div");
  grid.className = "sm-grid";
  el.replaceChildren(grid);
  const all = model.series.flatMap((s) => s.points.map((p) => p.value)).filter((v) => v != null);
  const yDomain = opts.shared && all.length ? [Math.min(0, ...all), Math.max(...all)] : null;
  for (const s of model.series) {
    const card = document.createElement("figure");
    card.className = "sm-card";
    card.dataset.id = s.id;
    const cap = document.createElement("figcaption");
    cap.textContent = s.name;
    const chart = document.createElement("div");
    chart.className = "sm-chart";
    card.append(cap, chart);
    grid.appendChild(card);
    if (opts.onPick) card.addEventListener("click", () => opts.onPick(s.id, ""));
    renderLines(chart, { labels: model.labels, series: [{ ...s, colour: s.colour ?? "#1f5fae" }] },
      { height: opts.height ?? 150, compact: true, zero: !yDomain, yDomain, hoverOnly: s.id,
        tip: opts.tip, label: s.name });
  }
}

/**
 * Rank per year. model: {labels, series: [{id, name, colour?, points: [{rank}]}]}, where rank
 * comes from chart-core ranks() over the selected cities. 1 is at the top.
 */
export function renderRank(el, model, opts = {}) {
  const lines = {
    labels: model.labels,
    series: model.series.map((s) => ({
      ...s,
      points: s.points.map((p) => ({ ...p, value: p.rank ?? null })),
    })),
  };
  const maxRank = Math.max(1, ...lines.series.flatMap((s) => s.points.map((p) => p.value ?? 1)));
  renderLines(el, lines, {
    ...opts,
    invert: true,
    intTicks: true,
    yDomain: [1, maxRank],
    tip: opts.tip ?? ((s, p, label) => `${s.name} · ${label}: rank ${p.value}`),
  });
}

/** A tiny axis-less line. points: [{label, value}]; nulls break the line. */
export function renderSparkline(el, points, opts = {}) {
  const W = opts.width ?? 120;
  const H = opts.height ?? 28;
  const vals = points.map((p) => p.value).filter(Number.isFinite);
  if (!vals.length) return emptyNote(el, "No data");
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const x = scaleLinear([0, Math.max(1, points.length - 1)], [2, W - 2]);
  const y = scaleLinear([lo, hi === lo ? lo + 1 : hi], [H - 3, 3]);
  let d = "";
  let pen = false;
  let last = null;
  points.forEach((p, i) => {
    if (!Number.isFinite(p.value)) { pen = false; return; }
    last = [x(i), y(p.value)];
    d += `${pen ? "L" : "M"}${last[0].toFixed(1)},${last[1].toFixed(1)}`;
    pen = true;
  });
  const svg = svgEl("svg", { class: "spark", width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img" });
  nameSvg(svg, opts.label ?? "Sparkline");
  svg.appendChild(svgEl("path", { class: "line", d, fill: "none", stroke: "currentColor", "stroke-width": 1.5 }));
  svg.appendChild(svgEl("circle", { cx: last[0], cy: last[1], r: 2.2, fill: "currentColor" }));
  el.replaceChildren(svg);
}

/**
 * Stacked tier composition. model: {labels, layers: [{key: "A".."E", name, values: number[]}]},
 * bottom to top. Mapped km, so the tooltip says so.
 */
export function renderTiers(el, model, opts = {}) {
  const W = widthOf(el, opts);
  const H = opts.height ?? 220;
  const n = model.labels.length;
  const ml = 46, mt = 10, mb = 26;
  const mr = Math.max(22, Math.ceil(textWidth(model.labels.at(-1) ?? "") / 2) + 2);
  const iw = W - ml - mr;
  const ih = H - mt - mb;
  const step = iw / Math.max(1, n - 1);
  const totals = model.labels.map((_, i) => model.layers.reduce((a, l) => a + (l.values[i] ?? 0), 0));
  const ticks = niceTicks(0, Math.max(...totals, 1), 4);
  const y = scaleLinear([0, ticks.at(-1)], [mt + ih, mt]);
  const x = (i) => ml + i * step;

  const svg = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img" });
  nameSvg(svg, opts.label ?? "Stacked area chart: mapped km by tier");
  for (const t of ticks) {
    svg.appendChild(svgEl("line", { class: "gridl", x1: ml, x2: ml + iw, y1: y(t), y2: y(t) }));
    svg.appendChild(svgEl("text", { class: "axis-t", x: ml - 6, y: y(t) + 3.5, "text-anchor": "end" }, tickLabel(t)));
  }
  for (const i of tickIndices(model.labels, step)) {
    svg.appendChild(svgEl("text", { class: "axis-t", x: x(i), y: H - 8, "text-anchor": "middle" }, model.labels[i]));
  }
  const base = model.labels.map(() => 0);
  for (const layer of model.layers) {
    const top = base.map((b, i) => b + (layer.values[i] ?? 0));
    const up = top.map((v, i) => `${x(i)},${y(v)}`).join("L");
    const down = base.map((v, i) => `${x(i)},${y(v)}`).reverse().join("L");
    svg.appendChild(svgEl("path", { class: `tier tier-${layer.key}`, d: `M${up}L${down}Z`,
      fill: TIER_COLOURS[layer.key] ?? "#999", "fill-opacity": 0.9, stroke: "#fff", "stroke-width": 0.6 }));
    top.forEach((v, i) => (base[i] = v));
  }
  const hx = svgEl("line", { class: "hover-x", x1: 0, x2: 0, y1: mt, y2: mt + ih, visibility: "hidden" });
  const hit = svgEl("rect", { class: "hit", x: ml, y: 0, width: iw, height: H, fill: "transparent" });
  svg.append(hx, hit);

  const legend = document.createElement("div");
  legend.className = "legend";
  for (const layer of [...model.layers].reverse()) {
    const chip = document.createElement("span");
    chip.className = "chip";
    const sw = document.createElement("i");
    sw.style.background = TIER_COLOURS[layer.key] ?? "#999";
    chip.append(sw, document.createTextNode(layer.name));
    legend.appendChild(chip);
  }
  el.replaceChildren(svg, legend);
  const tip = makeTip(el);
  const move = (e) => {
    const r = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(n - 1, Math.round((e.clientX - r.left - ml) / step)));
    hx.setAttribute("x1", x(i));
    hx.setAttribute("x2", x(i));
    hx.setAttribute("visibility", "visible");
    const fmt = (v) => (v ?? 0).toLocaleString("en-GB", { maximumFractionDigits: 0 });
    tip.textContent = [`${model.labels[i]} · mapped km`,
      ...[...model.layers].reverse().map((l) => `${l.key}: ${fmt(l.values[i])}`),
      `Total ${fmt(totals[i])}`].join("\n");
    tip.style.whiteSpace = "pre";
    tip.hidden = false; // measure only once visible
    placeTip(tip, x(i), mt + tip.offsetHeight + 10, W);
  };
  hit.addEventListener("pointermove", move);
  hit.addEventListener("pointerdown", move);
  hit.addEventListener("pointerleave", () => {
    tip.hidden = true;
    hx.setAttribute("visibility", "hidden");
  });
}
