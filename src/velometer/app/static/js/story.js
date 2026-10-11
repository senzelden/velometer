// The Stories page: a sticky chart that follows the section being read. The server resolved each
// step to a Compare state (cities, highlights, metric, scale) and embedded it as #story-config;
// this file draws that state and never recomputes the selection, so the chart, the section's
// "Explore this chart" link and its table always describe the same thing. Without this file the
// page is the article with a table per step.
import { renderLines, renderSmallMultiples } from "./chart.js";
import { formatValue } from "./chart-core.js";
import { buildModel, slotPlan } from "./compare-model.js";
import { describe } from "./describe.js";
import { stepFromHash } from "./permalink.js";
import { displayLabels, failed, labelsOf, loadSeries, mount, pointsOn } from "./data.js";

const cfg = JSON.parse(document.getElementById("story-config").textContent);
const box = document.querySelector("[data-story-chart]");
const plot = box.querySelector("[data-story-plot]");
const out = {
  eyebrow: box.querySelector("[data-story-eyebrow]"),
  title: box.querySelector("[data-story-title]"),
  note: box.querySelector("[data-story-note]"),
  short: box.querySelector("[data-story-short]"),
  link: box.querySelector("[data-story-link]"),
};
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const UNIT = "per 100 km of main roads";

let D = null;
let current = null;

/** Lines for a Compare-driven step. */
function linesModel(spec) {
  const state = spec.state;
  const model = buildModel(D, state);
  const slots = slotPlan(state, {});
  const lists = model.series.map((s) => D.series[`${s.id}/${state.b}`] ?? []);
  // a step may ring only one kind of flag (jumps: the km jumps its text discusses)
  const only = (flags) => (spec.ring ? flags.filter((f) => f === spec.ring) : flags);
  const series = model.series
    .filter((s) => s.points.some((p) => p.value != null))
    .map((s) => ({
      ...s,
      slot: slots[s.id],
      points: s.points.map((p) => ({ ...p, flags: only(p.flags ?? []) })),
    }));
  const abs = state.mode === "abs";
  const tip = (s, p, label) =>
    `${s.name} · ${label}: ${abs ? "" : "index "}${formatValue(p.value)}` +
    (p.flags?.length ? ` · flagged (${p.flags.join(", ")})` : "");
  return {
    model: { labels: displayLabels(model.labels, lists), series },
    opts: { zero: abs, tip, label: `Line chart: ${spec.title}`, small: state.view === "small" },
  };
}

/** Lines of the city's Bezirke, the server's highlights in colour. */
function bezirkeModel(spec) {
  const subareas = Object.entries(D.bezirke[spec.city] ?? {});
  const lists = subareas.map(([, b]) => b.points);
  const labels = labelsOf(lists);
  const lau = D.series[`${spec.city}/lau`] ?? [];
  const series = subareas.map(([id, b]) => ({
    id,
    name: b.name,
    slot: spec.hl.includes(id) ? spec.hl.indexOf(id) : undefined,
    points: pointsOn(b.points, labels, "headline"),
  }));
  const tip = (s, p, label) => `${s.name} · ${label}: ${formatValue(p.value)} ${UNIT}`;
  return {
    model: { labels: displayLabels(labels, [lau, ...lists]), series },
    opts: { zero: true, tip, label: `Line chart: ${spec.title}` },
  };
}

function draw() {
  const spec = cfg[current];
  if (!D || !spec) return;
  try {
    const { model, opts } = spec.kind === "bezirke" ? bezirkeModel(spec) : linesModel(spec);
    if (opts.small) {
      // each city on its own y scale: the small steps are as visible as the large ones
      const narrow = window.innerWidth < 560;
      renderSmallMultiples(plot, model, { shared: false, tip: opts.tip, height: narrow ? 80 : 130 });
    } else {
      renderLines(plot, model, { ...opts, height: window.innerWidth < 560 ? 230 : 440 });
    }
  } catch (err) {
    failed(plot, err);
  }
}

function show(step) {
  const spec = cfg[step];
  box.hidden = !spec;
  if (!spec || step === current) return;
  current = step;
  const step_n = `Step ${spec.n} of ${spec.of}`;
  out.eyebrow.textContent = spec.heading ? `${step_n} · ${spec.heading}` : step_n;
  out.title.textContent = spec.title;
  out.note.textContent = spec.note;
  out.short.textContent = spec.short ?? "";
  out.link.href = spec.href;
  // the chart's data is the table in the section being read
  describe(plot, step);
  draw();
  if (reduced) return;
  plot.classList.remove("fade-in"); // restart the CSS fade
  void plot.offsetWidth;
  plot.classList.add("fade-in");
}

document.documentElement.classList.add("story-js");
for (const d of document.querySelectorAll("details.step-values")) d.open = false;

const sections = [...document.querySelectorAll("section[data-step]")];
const ids = sections.map((s) => s.dataset.step);
// permalink: the step in view is the address's #step-<id> (replaceState: Back is not flooded). The
// first step at the top of a page that came without a step hash writes nothing.
let written = stepFromHash(location.hash, ids);
const remember = (step) => {
  if (step === written || (step === ids[0] && written === null)) return;
  written = step;
  try {
    history.replaceState(history.state, "", `${location.pathname}${location.search}#step-${encodeURIComponent(step)}`);
  } catch {
    // a frame that refuses history changes: the page works without the permalink
  }
};
const mark = (step) => {
  for (const s of sections) s.classList.toggle("is-active", s.dataset.step === step);
  show(step);
  remember(step);
};
// the section that crosses a thin band a third of the way down the viewport is the one being read
const seen = new Set();
const observer = new IntersectionObserver(
  (entries) => {
    for (const e of entries) (e.isIntersecting ? seen.add(e.target) : seen.delete(e.target));
    const first = sections.find((s) => seen.has(s));
    if (first) mark(first.dataset.step);
    // above the first section (the band sits behind the pinned chart on phones): the first step
    else if (sections[0].getBoundingClientRect().top > 0) mark(sections[0].dataset.step);
  },
  { rootMargin: "-30% 0px -60% 0px" },
);
for (const s of sections) observer.observe(s);
// a permalink's step: scroll to it and mark it (an unknown step is ignored)
const wanted = stepFromHash(location.hash, ids);
if (wanted) sections.find((s) => s.dataset.step === wanted).scrollIntoView();
if (sections.length) mark(wanted ?? ids[0]);

loadSeries()
  .then((data) => {
    D = data;
    mount(plot, draw);
  })
  .catch((err) => failed(plot, err));
