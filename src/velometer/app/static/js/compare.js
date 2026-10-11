// The Compare page: filters, the Lines / Small multiples / Rank / Table views, the URL state and
// the city slide-over. The server renders the form and the Table for the requested URL (it works
// without this file); this file keeps the URL in sync with the filters via history.replaceState
// and redraws from /data/series.json without a reload.
import { url } from "./base.js";
import { renderLines, renderRank, renderSmallMultiples } from "./chart.js";
import { formatValue } from "./chart-core.js";
import { displayLabels, failed, loadSeries } from "./data.js";
import { onThemeChange, seriesColours, token } from "./theme.js";
import {
  buildModel, compareSummary, slotPlan, colouredIds, compareUrl, footnote, nextSort, orderCities, plainText, popPlan,
  queryOf, rankSeries, sortRows,
} from "./compare-model.js";
import { COUNTER_CONTEXT, counterTitle } from "./counter-model.js";
import { createPanel } from "./panel.js";
import { announce } from "./live.js";
import { labelCells } from "./table.js";
import { DEFAULTS, MAX_HIGHLIGHTED, QUICK_SETS, droppedMetric, parseState, serializeState } from "./state.js";

const FUA_NOTE =
  "A+B km per 100k residents exists for the city proper (LAU) only; showing the headline for the metro area (FUA).";
const BOUNDARY = { lau: "City proper (LAU)", fua: "Metro area (FUA)" };

const $ = (sel, root = document) => root.querySelector(sel);
const form = $("#compare-filters");
const out = {
  title: $("[data-compare-title]"),
  notes: $("[data-compare-notes]"),
  chips: $("[data-compare-chips]"),
  chart: $("[data-compare-chart]"),
  flag: $("[data-flag-note]"),
  table: $("[data-compare-table]"),
  foot: $("[data-compare-foot]"),
};
const cfg = JSON.parse($("#compare-config").textContent);
const known = { cities: cfg.cities, metrics: cfg.metric_order };

let state = parseState(location.search, known);
let dropped = droppedMetric(location.search, state);
let D = null;
let slots = {}; // {cityId: slot}: kept across selection and theme changes
let sort = null;
let sharedScale = true;
let sheetOpen = false;
document.documentElement.classList.add("compare-js");
out.chart.tabIndex = -1; // the last resort for focus: the chart itself
const cityEl = (id) =>
  [...document.querySelectorAll(`[data-city="${CSS.escape(id)}"]`)].find((e) => e.offsetParent) ?? out.chart;
const panel = createPanel($("#city-panel"), {
  fallbackFocus: cityEl,
  nameOf: (id) => D?.cities[id]?.name ?? cfg.cities?.[id]?.name,
});

const el = (tag, attrs = {}, text) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
};

// ---- state <-> URL <-> form ----

function commit() {
  const qs = serializeState(state);
  history.replaceState(history.state, "", compareUrl(qs));
}

function apply(search) {
  state = parseState(search, known);
  dropped = droppedMetric(search, state);
  commit();
  render();
}

/** Every field of the form as a query string (plus the view and highlights it does not show). */
function formSearch() {
  const q = new URLSearchParams();
  const data = new FormData(form);
  q.set("c", orderCities(state.c, data.getAll("c")).join(","));
  for (const k of ["m", "b", "mode"]) q.set(k, data.get(k));
  q.set("view", state.view);
  const hl = state.hl.filter((id) => data.getAll("c").includes(id));
  if (hl.length) q.set("hl", hl.join(","));
  return q.toString();
}

function syncForm() {
  for (const box of form.querySelectorAll('input[name="c"]')) box.checked = state.c.includes(box.value);
  form.elements.m.value = dropped ?? state.m; // the page says so: see the note
  for (const r of form.elements.b) r.checked = r.value === state.b;
  for (const r of form.elements.mode) r.checked = r.value === state.mode;
  form.elements.view.value = state.view;
  const hl = form.elements.hl;
  if (hl) hl.value = state.hl.join(",");
  for (const a of document.querySelectorAll(".view-tabs a")) {
    if (a.dataset.view === state.view) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  const n = state.c.length;
  $("[data-filters-summary]").textContent =
    state.m === "counter_index"
      ? `${counterTitle(cfg.metrics[state.m].label)} · ${n} cit${n === 1 ? "y" : "ies"}`
      : `${cfg.metrics[state.m].label} · ${state.b.toUpperCase()} · ${n} cit${n === 1 ? "y" : "ies"} · ${state.mode === "index" ? "indexed" : "absolute"}`;
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  apply(formSearch());
});
form.addEventListener("change", () => apply(formSearch()));

for (const a of document.querySelectorAll(".view-tabs a")) {
  a.addEventListener("click", (e) => {
    e.preventDefault();
    apply(`${serializeState({ ...state, view: a.dataset.view })}`);
  });
}

for (const a of form.querySelectorAll("a[data-quick]")) {
  a.addEventListener("click", (e) => {
    e.preventDefault();
    const ids = QUICK_SETS[a.dataset.quick] ?? known.cities;
    const c = ids.filter((id) => known.cities.includes(id));
    apply(serializeState({ ...state, c: c.length ? c : DEFAULTS.c, hl: [] }) || "c=");
  });
}

// Back / Forward: the panel opens or closes, the URL always says what the page shows
window.addEventListener("popstate", (e) => {
  const plan = popPlan({
    popState: e.state,
    panelOpen: panel.isOpen,
    shownQuery: serializeState(state),
    urlQuery: queryOf(location.search, known),
  });
  if (plan.panel) panel.show(plan.panel);
  else if (panel.isOpen) panel.hide();
  if (plan.restore !== null) {
    history.replaceState(e.state, "", compareUrl(plan.restore));
  }
  if (plan.rerender) {
    state = parseState(location.search, known);
    dropped = droppedMetric(location.search, state);
    sort = null;
    render();
  }
});

// the filter sheet on phones: collapsed behind a button
const toggle = $(".filters-toggle");
toggle.hidden = false; // aria-expanded=false is how the template renders it, and the sheet starts closed
const setSheet = (open) => {
  sheetOpen = open;
  form.classList.toggle("open", open);
  toggle.setAttribute("aria-expanded", String(open));
};
toggle.addEventListener("click", () => setSheet(!sheetOpen));

// ---- drawing ----

const unitOf = () => cfg.metrics[state.m].unit;
const tipFor = (model) => (s, p, label) => {
  if (model.counter) return `${s.name} · ${label}: index ${formatValue(p.value)}`;
  const idx = state.mode === "index" ? "index " : "";
  const flag = p.flags?.length ? ` · flagged (${p.flags.join(", ")})` : "";
  return `${s.name} · ${label}: ${idx}${formatValue(p.value)}${state.mode === "index" ? "" : ` ${unitOf()}`}${flag}`;
};

function showFlag(id, label, rawLabel) {
  const key = `${id}/${state.b}/${rawLabel}`;
  const raw = D.explanations?.timeseries?.[key];
  const text = raw ? plainText(raw) : null;
  const box = out.flag;
  box.replaceChildren();
  const head = el("h3", { tabindex: "-1" }, `${D.cities[id].name} · ${label} · flagged year`);
  const close = el("button", { type: "button", class: "flag-close", "aria-label": "Dismiss" }, "×");
  close.addEventListener("click", () => (box.hidden = true));
  box.append(close, head);
  if (text) {
    for (const para of text.split(/\n{2,}/)) box.append(el("p", {}, para.trim()));
  } else {
    box.append(el("p", { class: "note" }, "No explanation recorded for this flag."));
  }
  const more = el("p");
  more.append(el("a", { href: url(`/city/${encodeURIComponent(id)}/time`) }, "Over time tab →"));
  box.append(more);
  box.hidden = false;
  box.scrollIntoView({ block: "nearest" });
  head.focus({ preventScroll: true });
}

function drawChips(model) {
  slots = slotPlan(state, slots);
  const palette = seriesColours();
  out.chips.replaceChildren();
  const coloured = new Set(colouredIds(state));
  const many = state.c.length > MAX_HIGHLIGHTED;
  if (many) {
    out.chips.append(el("span", { class: "chips-label" }, `Highlight (max ${MAX_HIGHLIGHTED}):`));
  }
  for (const s of model.series) {
    const b = el("button", { type: "button", class: "chip", "data-city": s.id, "aria-pressed": many ? String(state.hl.includes(s.id)) : "false" });
    const dot = el("i");
    dot.style.background = coloured.has(s.id) ? (palette[slots[s.id]] ?? "") : "";
    dot.className = coloured.has(s.id) ? "dot-on" : "dot-off";
    b.append(dot, document.createTextNode(s.name));
    b.title = many ? "Highlight this city" : "Open the city panel";
    b.addEventListener("click", () => {
      if (!many) return panel.open(s.id, b);
      const on = state.hl.includes(s.id);
      const hl = on ? state.hl.filter((i) => i !== s.id) : [...state.hl, s.id].slice(-MAX_HIGHLIGHTED);
      apply(serializeState({ ...state, hl }) || "");
    });
    out.chips.append(b);
  }
  out.chips.hidden = !state.c.length;
}

function drawChart(model) {
  slots = slotPlan(state, slots);
  const context = token("--ctx"); // grey cities in small multiples, as their chips
  const present = model.series.filter((s) => s.points.some((p) => p.value != null));
  // the axis names the snapshot month of the first list that has a current run
  const lists = model.series.map((s) => D.series[`${s.id}/${state.b}`] ?? []);
  const axis = displayLabels(model.labels, lists);
  const series = present.map((s) => ({
    ...s,
    slot: slots[s.id],
    colour: s.id in slots || state.view !== "small" ? undefined : context,
  }));
  const onPick = (id, flagLabel) => {
    if (flagLabel) {
      const i = axis.indexOf(flagLabel);
      return showFlag(id, flagLabel, model.labels[i]);
    }
    panel.open(id);
  };
  const base = { labels: axis, series };
  const size = { height: window.innerWidth < 560 ? 340 : 440, marks: model.marks };
  const tip = tipFor(model);
  if (!present.length) {
    out.chart.replaceChildren(el("p", { class: "empty" }, "No values for this selection."));
  } else if (state.view === "small") {
    renderSmallMultiples(out.chart, base, { shared: sharedScale, tip, onPick, height: 150, marks: model.marks });
  } else if (state.view === "rank") {
    renderRank(out.chart, { labels: axis, series: rankSeries(series, model.labels) }, {
      ...size, onPick, label: "Line chart: rank per year among the selected cities",
    });
  } else {
    renderLines(out.chart, base, {
      ...size, zero: state.mode === "abs" && !model.counter, tip, onPick,
      label: `Line chart: ${model.counter ? counterTitle(cfg.metrics[state.m].label) : `${cfg.metrics[state.m].label}, ${BOUNDARY[state.b]}`}`,
    });
    out.chart.dataset.series = String(series.length);
  }
}

// "Sort by" is on screen only where the header is a bar of buttons (a phone), so the table is
// described by it only there; it follows the layout when the window crosses the breakpoint
const PHONE = matchMedia("(max-width: 600px)");
function describeSort(table) {
  if (PHONE.matches) table.setAttribute("aria-describedby", table.dataset.sortCaption);
  else table.removeAttribute("aria-describedby");
}
PHONE.addEventListener("change", () => {
  const table = out.table.querySelector("table");
  if (table) describeSort(table);
});

function drawTable(model) {
  const marked = new Map(model.marks.map((m) => [m.label, m.text]));
  const axis = model.counter
    ? model.labels.map((l) => (marked.has(l) ? `${l} (${marked.get(l)})` : l))
    : displayLabels(model.labels, model.series.map((s) => D.series[`${s.id}/${state.b}`] ?? []));
  const rows = sortRows(model.series, model.labels, sort);
  const table = el("table", { class: "compare-table stack" });
  table.append(el("caption", { class: "sr-only", id: "compare-caption" }, `${cfg.metrics[state.m].label} per city and snapshot`));
  const head = el("tr");
  const th = (key, text, cls) => {
    const h = el("th", { scope: "col", ...(cls ? { class: cls } : {}) });
    const b = el("button", { type: "button", class: "sort", "data-key": key }, text);
    h.setAttribute("aria-sort", sort?.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none");
    if (sort?.key === key) b.textContent = `${text} ${sort.dir === 1 ? "↑" : "↓"}`;
    b.addEventListener("click", () => {
      sort = nextSort(sort, key);
      render();
      // the table was rebuilt: put keyboard focus back on the header that was pressed
      [...out.table.querySelectorAll("button.sort")].find((x) => x.dataset.key === key)?.focus();
    });
    h.append(b);
    return h;
  };
  head.append(th("name", "City"), ...model.labels.map((l, i) => th(l, axis[i], "num")));
  const thead = el("thead");
  thead.append(head);
  table.append(thead);
  const tbody = el("tbody");
  for (const r of rows) {
    const tr = el("tr");
    const name = el("th", { scope: "row" });
    const a = el("a", { href: url(`/city/${encodeURIComponent(r.id)}`), "data-city": r.id }, r.name);
    a.addEventListener("click", (e) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
      e.preventDefault();
      panel.open(r.id, a);
    });
    name.append(a);
    tr.append(name);
    for (const p of r.points) {
      const td = el("td", { class: "num" }, p.value == null ? "n/a" : p.value.toLocaleString("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
      if (p.flags.length) {
        td.append(el("span", { class: "flagmark", title: "flagged year" }, " ⚑"), el("span", { class: "sr-only" }, " (flagged)"));
      }
      tr.append(td);
    }
    tbody.append(tr);
  }
  table.append(tbody);
  labelCells(table);
  // on a phone the header is a bar of sort buttons: the caption says what the bar is for
  const caption = el("p", { class: "sort-caption", id: "compare-sort-caption" }, "Sort by");
  table.dataset.sortCaption = caption.id;
  describeSort(table);
  out.table.replaceChildren(caption, table);
}

function drawTitle(model) {
  const m = cfg.metrics[state.m];
  out.title.replaceChildren(
    model.counter
      ? el("h2", {}, counterTitle(m.label))
      : el("h2", {}, `${m.label} · ${BOUNDARY[state.b]}${state.mode === "index" ? " · index, first year = 100" : ""}`),
    el("p", { class: "meta" }, model.counter ? `${model.unit}. ${COUNTER_CONTEXT}` : `${m.unit}. Mapped km in OpenStreetMap, not built km.`),
  );
  out.foot.textContent = footnote(state.m, cfg.headline_unit);
  const notes = [...(dropped ? [FUA_NOTE] : []), ...model.notes];
  out.notes.replaceChildren(...notes.map((n) => el("p", { class: "note" }, n)));
  if (state.view === "rank") {
    out.notes.append(el("p", { class: "note" }, "Rank 1 is the highest value among the selected cities; ranks change with the selection."));
  }
}

function extras() {
  // small multiples: shared or own y scale
  let box = $(".sm-controls");
  if (state.view !== "small") return box?.remove();
  if (!box) {
    box = el("p", { class: "sm-controls" });
    const label = el("label");
    const input = el("input", { type: "checkbox" });
    input.checked = sharedScale;
    input.addEventListener("change", () => {
      sharedScale = input.checked;
      render();
    });
    label.append(input, document.createTextNode(" Same y scale for every city"));
    box.append(label);
    out.chart.before(box);
  }
}

let lastSummary = "";
/** Tell a screen reader what the redraw shows, unless it is the same as the last time. */
function announceOnce(model) {
  const text = compareSummary({ ...state, c: model.series.map((s) => s.id) }, cfg.metrics);
  const first = lastSummary === "";
  if (text === lastSummary) return;
  lastSummary = text;
  if (!first) announce(text); // the first draw is the page loading, not a change
}

function render(keepFlag = false) {
  syncForm();
  if (!D) return;
  try {
    const model = buildModel(D, state);
    drawTitle(model);
    if (!keepFlag) announceOnce(model);
    const table = state.view === "table";
    out.table.hidden = !table;
    out.chart.hidden = table;
    out.chips.hidden = table;
    if (!keepFlag) out.flag.hidden = true;
    extras();
    if (table) {
      drawTable(model);
    } else {
      drawChips(model);
      drawChart(model);
    }
  } catch (err) {
    failed(out.chart, err);
    out.chart.hidden = false;
    out.table.hidden = false;
  }
}

// charts size to their box: redraw when its width changes
let lastWidth = 0;
let timer = null;
new ResizeObserver(() => {
  const w = out.chart.clientWidth;
  if (!w || w === lastWidth) return;
  lastWidth = w;
  clearTimeout(timer);
  timer = setTimeout(() => render(true), 120);
}).observe(out.chart);

// the OS theme changed: redraw the same state (colours are read at draw time, slots are kept)
onThemeChange(() => render(true));

loadSeries()
  .then((data) => {
    D = data;
    render();
  })
  .catch((err) => {
    failed(out.chart, err);
    out.chart.hidden = false;
  });
