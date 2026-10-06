// City page charts (Story, Over time, Tiers and Bezirke tabs): headline over time (LAU and FUA),
// tier composition per boundary and the Bezirk small multiples, drawn from /data/series.json into the server-rendered [data-chart]
// mounts. Every value is also in a table on the page.
import { renderLines, renderSmallMultiples } from "./chart.js";
import { drawTiers } from "./tier-chart.js";
import { formatValue } from "./chart-core.js";
import { PALETTE, displayLabels, drawAll, labelsOf, mount, pointsOn } from "./data.js";

const BOUNDARY = { lau: "City proper (LAU)", fua: "Metro area (FUA)" };
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
      colour: PALETTE[i],
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
      colour: PALETTE[0],
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

drawAll({ "city-headline": headline, "city-tiers": drawTiers, bezirke });
