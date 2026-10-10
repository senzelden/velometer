// Overview and Cities pages: the all-cities headline chart and the per-city sparklines, drawn
// from /data/series.json into the [data-chart] mounts the server rendered. The tables on both
// pages carry the same values without JavaScript.
import { url } from "./base.js";
import { renderLines, renderSparkline } from "./chart.js";
import { formatValue } from "./chart-core.js";
import { PILOT5 } from "./state.js";
import { displayLabels, drawAll, labelsOf, mount, pointsOn } from "./data.js";

function overviewLines(el, D) {
  const ids = Object.keys(D.cities).sort((a, b) => D.cities[a].name.localeCompare(D.cities[b].name));
  const lists = ids.map((id) => D.series[`${id}/lau`] ?? []);
  const labels = labelsOf(lists);
  const coloured = PILOT5.filter((id) => ids.includes(id));
  const model = {
    labels: displayLabels(labels, lists),
    yTitle: "A+B km per 100 km of main roads",
    series: ids.map((id, i) => ({
      id,
      name: D.cities[id].name,
      slot: coloured.includes(id) ? coloured.indexOf(id) : undefined,
      points: pointsOn(lists[i], labels, "headline"),
    })),
  };
  mount(el, () =>
    renderLines(el, model, {
      height: 360,
      zero: true,
      label: "Line chart: headline over time, city proper (LAU), every city",
      tip: (s, p, label) =>
        `${s.name} · ${label}: ${formatValue(p.value)} per 100 km of main roads` +
        (p.flags?.length ? ` · flagged (${p.flags.join(", ")})` : ""),
      onPick: (id) => {
        location.href = url(`/city/${encodeURIComponent(id)}`);
      },
    }),
  );
}

function sparkline(el, D) {
  const id = el.dataset.city;
  const pts = D.series[`${id}/lau`] ?? [];
  const name = D.cities[id]?.name ?? id;
  const points = pts.map((p) => ({ label: p.label, value: p.headline }));
  const vals = points.map((p) => p.value).filter(Number.isFinite);
  const label = vals.length
    ? `${name}: headline from ${formatValue(vals[0])} to ${formatValue(vals.at(-1))}`
    : `${name}: no headline series`;
  renderSparkline(el, points, { width: 140, height: 30, label });
}

drawAll({ "overview-lines": overviewLines, sparkline });
