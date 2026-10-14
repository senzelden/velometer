// Overview and Cities pages: the all-cities headline chart and the per-city sparklines, drawn
// from /data/series.json into the [data-chart] mounts the server rendered. The tables on both
// pages carry the same values without JavaScript.
import { url } from "./base.js";
import { renderLines, renderSparkline } from "./chart.js";
import { formatValue } from "./chart-core.js";
import { PILOT5 } from "./state.js";
import { displayLabels, drawAll, labelsOf, mount, pointsOn } from "./data.js";
import { t } from "./strings.js";

function overviewLines(el, D) {
  const ids = Object.keys(D.cities).sort((a, b) => D.cities[a].name.localeCompare(D.cities[b].name));
  const lists = ids.map((id) => D.series[`${id}/lau`] ?? []);
  const labels = labelsOf(lists);
  const coloured = PILOT5.filter((id) => ids.includes(id));
  const model = {
    labels: displayLabels(labels, lists),
    yTitle: t("js.unit.headline"),
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
      label: t("js.overview.chart"),
      tip: (s, p, label) =>
        `${s.name} · ${label}: ${formatValue(p.value)} ${t("js.unit.per_main_roads")}` +
        (p.flags?.length ? ` · ${t("js.chart.flagged", { flags: p.flags.join(", ") })}` : ""),
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
    ? t("js.overview.spark", { city: name, first: formatValue(vals[0]), last: formatValue(vals.at(-1)) })
    : t("js.overview.spark_none", { city: name });
  renderSparkline(el, points, { width: 140, height: 30, label });
}

drawAll({ "overview-lines": overviewLines, sparkline });
