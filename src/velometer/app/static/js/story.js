// The Stories page: a sticky chart that follows the section being read. The server resolved each
// step to a Compare state (cities, highlights, metric, scale) and embedded it as #story-config;
// this file draws that state and never recomputes the selection, so the chart, the section's
// "Explore this chart" link and its table always describe the same thing. Without this file the
// page is the article with a table per step.
import { renderLines } from "./chart.js";
import { formatValue } from "./chart-core.js";
import { buildModel, colourPlan } from "./compare-model.js";
import { PALETTE, displayLabels, failed, labelsOf, loadSeries, mount, pointsOn } from "./data.js";

const cfg = JSON.parse(document.getElementById("story-config").textContent);
const box = document.querySelector("[data-story-chart]");
const plot = box.querySelector("[data-story-plot]");
const out = {
  eyebrow: box.querySelector("[data-story-eyebrow]"),
  title: box.querySelector("[data-story-title]"),
  note: box.querySelector("[data-story-note]"),
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
  const colours = colourPlan(state, {});
  const lists = model.series.map((s) => D.series[`${s.id}/${state.b}`] ?? []);
  const series = model.series
    .filter((s) => s.points.some((p) => p.value != null))
    .map((s) => ({ ...s, colour: colours[s.id] }));
  const abs = state.mode === "abs";
  const tip = (s, p, label) =>
    `${s.name} · ${label}: ${abs ? "" : "index "}${formatValue(p.value)}` +
    (p.flags?.length ? ` · flagged (${p.flags.join(", ")})` : "");
  return {
    model: { labels: displayLabels(model.labels, lists), series },
    opts: { zero: abs, tip, label: `Line chart: ${spec.title}` },
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
    colour: spec.hl.includes(id) ? PALETTE[spec.hl.indexOf(id)] : undefined,
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
    renderLines(plot, model, { ...opts, height: window.innerWidth < 560 ? 230 : 440 });
  } catch (err) {
    failed(plot, err);
  }
}

function show(step) {
  const spec = cfg[step];
  box.hidden = !spec;
  if (!spec || step === current) return;
  current = step;
  out.eyebrow.textContent = `Step ${spec.n} of ${spec.of} · ${spec.heading}`;
  out.title.textContent = spec.title;
  out.note.textContent = spec.note;
  out.link.href = spec.href;
  draw();
  if (reduced) return;
  plot.classList.remove("fade-in"); // restart the CSS fade
  void plot.offsetWidth;
  plot.classList.add("fade-in");
}

document.documentElement.classList.add("story-js");
for (const d of document.querySelectorAll("details.step-values")) d.open = false;

const sections = [...document.querySelectorAll("section[data-step]")];
const mark = (step) => {
  for (const s of sections) s.classList.toggle("is-active", s.dataset.step === step);
  show(step);
};
// the section that crosses a thin band a third of the way down the viewport is the one being read
const seen = new Set();
const observer = new IntersectionObserver(
  (entries) => {
    for (const e of entries) (e.isIntersecting ? seen.add(e.target) : seen.delete(e.target));
    const first = sections.find((s) => seen.has(s));
    if (first) mark(first.dataset.step);
  },
  { rootMargin: "-30% 0px -60% 0px" },
);
for (const s of sections) observer.observe(s);
if (sections.length) mark(sections[0].dataset.step);

loadSeries()
  .then((data) => {
    D = data;
    mount(plot, draw);
  })
  .catch((err) => failed(plot, err));
