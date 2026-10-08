// The counter index as chart models (Counts tab, Compare's counter_index metric), from the
// `counters` block of /data/series.json. Pure (no DOM). Counters are context: counts recorded at
// counter sites, never cycling in a city. A year without an index value is a gap (null), never 0.
// A city listed under `none:` in config/counters.yaml gets its note from `counters.none`.
// app/compare.py: counter_lines computes the Compare table the same way for the no-JS page.

export const COUNTER_METRIC = "counter_index";
export const NO_COUNTERS = "no open counter data";
export const NO_COUNTER_LINE = "no counter index line (an index value for one year only; see its Counts tab)";
export const AVG_DAILY = "index of average daily intensity (monthly values), not of counts";
export const COVID_TEXT = "COVID year";

const range = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => String(a + i));

/** The COVID-year mark of a counter chart, if the year is on the axis. */
export function covidMarks(D, labels) {
  const y = String(D.counters?.covid_year ?? "");
  return labels.includes(y) ? [{ label: y, text: COVID_TEXT }] : [];
}

/**
 * Compare's counter index for `ids`: {labels, series: [{id, name, points: [{label, value,
 * flags}]}], notes, marks}. Labels are the calendar years from the first to the last with a value
 * for any drawn city; a city without counter data, or whose index is not a line, has no values
 * and a note.
 */
export function counterLines(D, ids) {
  const counters = D.counters?.cities ?? {};
  const drawn = ids.filter((id) => counters[id]?.line);
  const years = drawn.flatMap((id) => counters[id].points.filter((p) => p.idx != null).map((p) => p.year));
  const labels = years.length ? range(Math.min(...years), Math.max(...years)) : [];
  const notes = [];
  const series = ids.map((id) => {
    const c = counters[id];
    const name = D.cities[id].name;
    if (!c) notes.push(`${name}: ${D.counters?.none?.[id] ?? NO_COUNTERS}`);
    else if (!c.line) notes.push(`${name}: ${NO_COUNTER_LINE}`);
    else if (c.series === "avg_daily_intensity") notes.push(`${name}: ${AVG_DAILY}`);
    const by = new Map(c?.line ? c.points.map((p) => [String(p.year), p.idx]) : []);
    const points = labels.map((label) => {
      const v = by.get(label);
      return { label, value: Number.isFinite(v) ? v : null, flags: [] };
    });
    return { id, name, points };
  });
  return { labels, series, notes, marks: covidMarks(D, labels) };
}

/**
 * The Counts tab chart of one city: the counter index and the A+B mapped-km index of the city
 * proper (1 January snapshots), both base year = 100 (the counter index's base year). Years run
 * from the first to the last with either value. No counter line (one year only): the km line
 * alone. No km for the base year: the counter line alone. `names`: {counter, km, counterShort,
 * kmShort}, the short ones for end labels at phone width.
 */
export function countsChart(D, id, names = {}) {
  const c = D.counters?.cities?.[id];
  if (!c) return null;
  const base = c.base_year;
  const counter = new Map(c.line ? c.points.filter((p) => p.idx != null).map((p) => [p.year, p.idx]) : []);
  const km = new Map();
  const snaps = (D.series?.[`${id}/lau`] ?? []).filter((p) => p.label !== "current");
  const b = snaps.find((p) => Number(p.label) === base)?.ab_km;
  if (Number.isFinite(b) && b !== 0) {
    for (const p of snaps) if (Number.isFinite(p.ab_km)) km.set(Number(p.label), (p.ab_km / b) * 100);
  }
  const years = [...counter.keys(), ...km.keys()];
  if (!years.length) return null;
  const labels = range(Math.min(...years), Math.max(...years));
  const line = (map, sid, name, short) => ({
    id: sid,
    name,
    short, // the end label when the full name has no room; the key under the chart names it
    points: labels.map((l) => ({ label: l, value: map.has(Number(l)) ? map.get(Number(l)) : null, flags: [] })),
  });
  const series = [];
  if (counter.size) {
    series.push(line(counter, "counter", names.counter ?? "Counter index", names.counterShort ?? "Counts"));
  }
  if (km.size) series.push(line(km, "km", names.km ?? "A+B mapped km index", names.kmShort ?? "Mapped km"));
  return { labels, series, marks: covidMarks(D, labels), base };
}
