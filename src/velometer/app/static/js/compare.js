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
  buildModel, compareSummary, slotPlan, colouredIds, compareUrl, footnote, nextSort, orderCities, flagParagraphs, paragraphNode, popPlan,
  queryOf, rankSeries, sortRows,
} from "./compare-model.js";
import { counterContext, counterTip, counterTitle } from "./counter-model.js";
import { createPanel } from "./panel.js";
import { announce } from "./live.js";
import { multiFields } from "./cite.js";
import { fieldsOf, setFields } from "./cite-ui.js";
import { labelCells } from "./table.js";
import { setParam } from "./permalink.js";
import { DEFAULTS, MAX_HIGHLIGHTED, QUICK_SETS, droppedMetric, panelOf, parseState, serializeState } from "./state.js";
import { number } from "./fmt.js";
import { t } from "./strings.js";

const boundary = (b) => (b === "fua" ? t("js.unit.fua") : t("js.unit.lau"));
const flagged = (p) => (p.flags?.length ? ` · ${t("js.chart.flagged", { flags: p.flags.join(", ") })}` : "");

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

// the open panel travels in the query (`panel=<city id>`), after the compare state
const withPanel = (qs) => {
  const q = setParam(qs ? `?${qs}` : "", "panel", panel.isOpen ? panel.current : null);
  return q.replace(/^\?/, "");
};

function commit() {
  const qs = serializeState(state);
  history.replaceState(history.state, "", compareUrl(withPanel(qs)));
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
  const cities = t("js.compare.n_cities", { count: state.c.length });
  const scale = state.mode === "index" ? t("js.compare.indexed") : t("js.compare.absolute");
  $("[data-filters-summary]").textContent =
    state.m === "counter_index"
      ? `${counterTitle(cfg.metrics[state.m].label)} · ${cities}`
      : `${cfg.metrics[state.m].label} · ${state.b.toUpperCase()} · ${cities} · ${scale}`;
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
    history.replaceState(e.state, "", compareUrl(withPanel(plan.restore)));
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
  const index = t("js.chart.index_value", { value: formatValue(p.value) });
  if (model.counter) return counterTip(D, s.id, p.value, label);
  const value = state.mode === "index" ? index : `${formatValue(p.value)} ${unitOf()}`;
  return `${s.name} · ${label}: ${value}${flagged(p)}`;
};

function showFlag(id, label, rawLabel) {
  const key = `${id}/${state.b}/${rawLabel}`;
  const paragraphs = flagParagraphs(D, key);
  const box = out.flag;
  box.replaceChildren();
  const head = el("h3", { tabindex: "-1" }, t("js.compare.flag_head", { city: D.cities[id].name, label }));
  const close = el("button", { type: "button", class: "flag-close", "aria-label": t("js.compare.dismiss") }, "×");
  close.addEventListener("click", () => (box.hidden = true));
  box.append(close, head);
  if (paragraphs.length) {
    for (const p of paragraphs) box.append(paragraphNode(p));
  } else {
    box.append(el("p", { class: "note" }, t("js.compare.no_explanation")));
  }
  const more = el("p");
  more.append(el("a", { href: url(`/city/${encodeURIComponent(id)}/time`) }, t("js.compare.over_time_link")));
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
    out.chips.append(el("span", { class: "chips-label" }, t("js.compare.highlight_max", { max: MAX_HIGHLIGHTED })));
  }
  for (const s of model.series) {
    const b = el("button", { type: "button", class: "chip", "data-city": s.id, "aria-pressed": many ? String(state.hl.includes(s.id)) : "false" });
    const dot = el("i");
    dot.style.background = coloured.has(s.id) ? (palette[slots[s.id]] ?? "") : "";
    dot.className = coloured.has(s.id) ? "dot-on" : "dot-off";
    b.append(dot, document.createTextNode(s.name));
    b.title = many ? t("js.compare.highlight_city") : t("js.compare.open_panel");
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
    out.chart.replaceChildren(el("p", { class: "empty" }, t("js.chart.no_values")));
  } else if (state.view === "small") {
    renderSmallMultiples(out.chart, base, { shared: sharedScale, tip, onPick, height: 150, marks: model.marks });
  } else if (state.view === "rank") {
    renderRank(out.chart, { labels: axis, series: rankSeries(series, model.labels) }, {
      ...size, onPick, label: t("js.compare.rank_chart"),
    });
  } else {
    renderLines(out.chart, base, {
      ...size, zero: state.mode === "abs" && !model.counter, tip, onPick,
      label: t("js.chart.line_of", {
        title: model.counter ? counterTitle(cfg.metrics[state.m].label) : `${cfg.metrics[state.m].label}, ${boundary(state.b)}`,
      }),
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
  table.append(el("caption", { class: "sr-only", id: "compare-caption" }, t("js.compare.caption", { metric: cfg.metrics[state.m].label })));
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
  head.append(th("name", t("js.compare.city")), ...model.labels.map((l, i) => th(l, axis[i], "num")));
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
      const td = el("td", { class: "num" }, p.value == null ? t("js.fmt.na") : number(p.value, 1));
      if (p.flags.length) {
        td.append(
          el("span", { class: "flagmark", title: t("js.compare.flagged_year") }, " ⚑"),
          el("span", { class: "sr-only" }, ` ${t("js.compare.flagged")}`),
        );
      }
      tr.append(td);
    }
    tbody.append(tr);
  }
  table.append(tbody);
  labelCells(table);
  // on a phone the header is a bar of sort buttons: the caption says what the bar is for
  const caption = el("p", { class: "sort-caption", id: "compare-sort-caption" }, t("js.compare.sort_by"));
  table.dataset.sortCaption = caption.id;
  describeSort(table);
  out.table.replaceChildren(caption, table);
}

function drawTitle(model) {
  const m = cfg.metrics[state.m];
  out.title.replaceChildren(
    model.counter
      ? el("h2", {}, counterTitle(m.label))
      : el("h2", {}, `${m.label} · ${boundary(state.b)}${state.mode === "index" ? ` · ${t("js.compare.index_heading")}` : ""}`),
    el("p", { class: "meta" }, `${model.counter ? model.unit : m.unit}. ${model.counter ? counterContext() : t("js.compare.mapped_not_built")}`),
  );
  out.foot.textContent = footnote(state.m, cfg.headline_unit);
  const notes = [...(dropped ? [t("js.compare.fua_note")] : []), ...model.notes];
  out.notes.replaceChildren(...notes.map((n) => el("p", { class: "note" }, n)));
  if (state.view === "rank") {
    out.notes.append(el("p", { class: "note" }, t("js.compare.rank_note")));
  }
}

let citeKey = null;
/** Rebuild the Cite for what the page now shows. It is rebuilt (and closed) only when the title
 * or the cities change, not on a resize or a theme redraw. The date and address are taken when
 * the disclosure opens, so the URL state the page keeps is in them. */
function updateCite(model) {
  const details = $(".compare-out details.cite");
  if (!details) return; // no run for the cities the page was rendered with: no Cite
  const title = t("js.compare.cite_title", {
    heading: out.title.querySelector("h2").textContent,
    cities: model.series.map((s) => s.name).join(", "),
  });
  const ids = model.series.map((s) => s.id);
  const key = `${title}|${ids.join(",")}`;
  if (key === citeKey) return;
  citeKey = key;
  const f0 = fieldsOf(details);
  // the runs of the boundary shown: a metro-area chart cites the FUA runs
  const fields = multiFields(cfg.cite_runs?.[state.b] ?? {}, ids, title, f0.path, f0.commit);
  if (fields) setFields(details, fields);
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
    label.append(input, document.createTextNode(` ${t("js.compare.same_scale")}`));
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
    updateCite(model);
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

// a permalink with `panel=<city>` reopens that city's panel (an unknown city is ignored)
const wantedPanel = panelOf(location.search, known);
if (wantedPanel) panel.show(wantedPanel);

loadSeries()
  .then((data) => {
    D = data;
    render();
  })
  .catch((err) => {
    failed(out.chart, err);
    out.chart.hidden = false;
  });
