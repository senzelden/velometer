// City page charts (Story, Over time, Tiers, Counts and Bezirke tabs): headline over time (LAU
// and FUA), tier composition per boundary, the counter index beside the mapped-km index and the
// Bezirk small multiples, drawn from /data/series.json into the server-rendered [data-chart]
// mounts. Every value is also in a table on the page.
import { renderLines, renderSmallMultiples } from "./chart.js";
import { drawTiers } from "./tier-chart.js";
import { formatValue } from "./chart-core.js";
import { displayLabels, drawAll, labelsOf, mount, pointsOn } from "./data.js";
import { countsChart } from "./counter-model.js";
import { t } from "./strings.js";

const BOUNDARY = { lau: () => t("js.unit.lau"), fua: () => t("js.unit.fua") };
// end labels of narrow charts
const BOUNDARY_SHORT = { lau: () => t("js.city.lau_short"), fua: () => t("js.city.fua_short") };
const flagged = (p) => (p.flags?.length ? ` · ${t("js.chart.flagged", { flags: p.flags.join(", ") })}` : "");

function headline(el, D) {
  const id = el.dataset.city;
  const kinds = ["lau", "fua"].filter((k) => (D.series[`${id}/${k}`] ?? []).length);
  const lists = kinds.map((k) => D.series[`${id}/${k}`]);
  const labels = labelsOf(lists);
  const model = {
    labels: displayLabels(labels, lists),
    yTitle: t("js.unit.headline"),
    series: kinds.map((k, i) => ({
      id: k,
      name: BOUNDARY[k](),
      short: BOUNDARY_SHORT[k](),
      slot: i,
      points: pointsOn(lists[i], labels, "headline"),
    })),
  };
  mount(el, () =>
    renderLines(el, model, {
      height: Number(el.dataset.height) || 300,
      zero: true,
      label: t("js.city.headline_chart", { city: D.cities[id]?.name ?? id }),
      tip: (s, p, label) =>
        `${s.name} · ${label}: ${formatValue(p.value)} ${t("js.unit.per_main_roads")}${flagged(p)}`,
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
      tip: (s, p, label) => `${s.name} · ${label}: ${formatValue(p.value)} ${t("js.unit.per_main_roads")}`,
    }),
  );
}

function counts(el, D) {
  const id = el.dataset.city;
  const avg = D.counters?.cities?.[id]?.series === "avg_daily_intensity";
  const model = countsChart(D, id, {
    counter: avg ? t("js.counts.avg_at_sites") : t("js.counts.at_sites"),
    counterShort: el.dataset.counterShort, // the server's short names, as in the key
    km: t("js.counts.km_jan"),
    kmShort: el.dataset.kmShort,
  });
  if (!model) throw new Error(t("js.city.no_counter_data", { city: id }));
  const lines = {
    labels: model.labels,
    yTitle: t("js.city.index_axis", { base: model.base }),
    series: model.series.map((s, i) => ({ ...s, slot: i })),
  };
  mount(el, () =>
    renderLines(el, lines, {
      height: Number(el.dataset.height) || 300,
      marks: model.marks,
      label: t("js.city.counts_chart", { city: D.cities[id]?.name ?? id, base: model.base }),
      tip: (s, p, label) => `${s.name} · ${label}: ${t("js.chart.index_value", { value: formatValue(p.value) })}`,
    }),
  );
}

drawAll({ "city-headline": headline, "city-tiers": drawTiers, "city-counts": counts, bezirke });
