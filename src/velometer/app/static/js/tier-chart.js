// The tier-composition chart of one city and boundary, shared by the city pages and the Compare
// slide-over. el.dataset: city, kind ("lau" | "fua").
import { renderTiers } from "./chart.js";
import { TIER_NAMES, displayLabels, labelsOf, mount, pointsOn } from "./data.js";

/** Draws it and returns the release function of its theme/resize listeners. */
export function drawTiers(el, D) {
  const id = el.dataset.city;
  const pts = D.series[`${id}/${el.dataset.kind}`] ?? [];
  const labels = labelsOf([pts]);
  const model = {
    labels: displayLabels(labels, [pts]),
    layers: Object.keys(TIER_NAMES).map((t) => ({
      key: t,
      name: TIER_NAMES[t],
      values: pointsOn(pts, labels, t).map((p) => p.value),
    })),
  };
  const where = `${D.cities[id]?.name ?? id} ${el.dataset.kind.toUpperCase()}`;
  return mount(el, () =>
    renderTiers(el, model, { label: `Stacked area chart: mapped km by tier, ${where}` }),
  );
}
