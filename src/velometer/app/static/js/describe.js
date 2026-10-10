// A chart's data is the table in the section being read: point the chart at it, or at nothing
// when that step has no table (a stale reference to the previous step's table would be wrong).
export function describe(plot, step, doc = document) {
  const id = `step-values-${step}`;
  if (doc.getElementById(id)) plot.setAttribute("aria-describedby", id);
  else plot.removeAttribute("aria-describedby");
}
