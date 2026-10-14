// The tier-composition chart of one city and boundary, shared by the city pages and the Compare
// slide-over. el.dataset: city, kind ("lau" | "fua").
import { renderTiers } from "./chart.js";
import { TIERS, displayLabels, labelsOf, mount, pointsOn, tierName } from "./data.js";
import { t } from "./strings.js";

/** Draws it and returns the release function of its theme/resize listeners. */
export function drawTiers(el, D) {
  const id = el.dataset.city;
  const pts = D.series[`${id}/${el.dataset.kind}`] ?? [];
  const labels = labelsOf([pts]);
  const model = {
    labels: displayLabels(labels, [pts]),
    layers: TIERS.map((tier) => ({
      key: tier,
      name: tierName(tier),
      values: pointsOn(pts, labels, tier).map((p) => p.value),
    })),
  };
  const where = `${D.cities[id]?.name ?? id} ${el.dataset.kind.toUpperCase()}`;
  return mount(el, () =>
    renderTiers(el, model, { label: t("js.chart.tiers_of", { where }) }),
  );
}
