// City page charts (Story, Over time, Tiers, Counts and Bezirke tabs): headline over time (LAU
// and FUA), tier composition per boundary, the counter index beside the mapped-km index and the
// Bezirk small multiples, drawn from /data/series.json into the server-rendered [data-chart]
// mounts. Every value is also in a table on the page.
import { renderLines, renderSmallMultiples } from "./chart.js";
import { drawTiers } from "./tier-chart.js";
import { formatValue } from "./chart-core.js";
import { displayLabels, drawAll, labelsOf, mount, pointsOn } from "./data.js";
import { countsChart } from "./counter-model.js";

const BOUNDARY = { lau: "City proper (LAU)", fua: "Metro area (FUA)" };
const BOUNDARY_SHORT = { lau: "City proper", fua: "Metro area" }; // end labels of narrow charts
const UNIT = "per 100 km of main roads";

function headline(el, D) {
  const id = el.dataset.city;
  const kinds = ["lau", "fua"].filter((k) => (D.series[`${id}/${k}`] ?? []).length);
  const lists = kinds.map((k) => D.series[`${id}/${k}`]);
  const labels = labelsOf(lists);
  const model = {
    labels: displayLabels(labels, lists),
    yTitle: "A+B km per 100 km of main roads",
    series: kinds.map((k, i) => ({
      id: k,
      name: BOUNDARY[k],
      short: BOUNDARY_SHORT[k],
      slot: i,
      points: pointsOn(lists[i], labels, "headline"),
    })),
  };
  mount(el, () =>
    renderLines(el, model, {
      height: Number(el.dataset.height) || 300,
      zero: true,
      label: `Line chart: headline over time, ${D.cities[id]?.name ?? id}, LAU and FUA`,
      tip: (s, p, label) =>
        `${s.name} · ${label}: ${formatValue(p.value)} ${UNIT}` +
        (p.flags?.length ? ` · flagged (${p.flags.join(", ")})` : ""),
    }),
  );
}

function bezirke(el, D) {
  const id = el.dataset.city;
  const subareas = Object.values(D.bezirke[id] ?? {}).sort((a, b) => a.name.localeCompare(b.name));
  const lists = subareas.map((b) => b.points);
  const labels = labelsOf(lists);
  const model = {
    labels: displayLabels(labels, [D.series[`${id}/lau`] ?? [], ...lists]),
    series: subareas.map((b, i) => ({
      id: `b${i}`,
      name: b.name,
      slot: 0,
      points: pointsOn(b.points, labels, "headline"),
    })),
  };
  mount(el, () =>
    renderSmallMultiples(el, model, {
      shared: true,
      tip: (s, p, label) => `${s.name} · ${label}: ${formatValue(p.value)} ${UNIT}`,
    }),
  );
}

function counts(el, D) {
  const id = el.dataset.city;
  const avg = D.counters?.cities?.[id]?.series === "avg_daily_intensity";
  const model = countsChart(D, id, {
    counter: avg ? "Average daily intensity at counter sites" : "Counts at counter sites",
    counterShort: el.dataset.counterShort, // the server's short names, as in the key
    km: "A+B mapped km (1 Jan)",
    kmShort: el.dataset.kmShort,
  });
  if (!model) throw new Error(`no counter data for ${id}`);
  const lines = {
    labels: model.labels,
    yTitle: `Index, ${model.base} = 100`,
    series: model.series.map((s, i) => ({ ...s, slot: i })),
  };
  mount(el, () =>
    renderLines(el, lines, {
      height: Number(el.dataset.height) || 300,
      marks: model.marks,
      label: `Line chart: counter index and A+B mapped-km index, ${D.cities[id]?.name ?? id}, ${model.base} = 100`,
      tip: (s, p, label) => `${s.name} · ${label}: index ${formatValue(p.value)}`,
    }),
  );
}

drawAll({ "city-headline": headline, "city-tiers": drawTiers, "city-counts": counts, bezirke });
