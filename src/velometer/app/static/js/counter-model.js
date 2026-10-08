// The counter index as chart models (Counts tab, Compare's counter_index metric), from the
// `counters` block of /data/series.json. Pure (no DOM). Counters are context: counts recorded at
// counter sites, never cycling in a city. A year without an index value is a gap (null), never 0.
// A city listed under `none:` in config/counters.yaml gets its note from `counters.none`.
// app/compare.py: counter_lines computes the Compare table the same way for the no-JS page.

export const COUNTER_METRIC = "counter_index";
export const NO_COUNTERS = "no open counter data";
export const NO_COUNTER_LINE = "no counter index line (an index value for one year only; see its Counts tab)";
// config/counters.yaml unreadable (`counters.config_error`): the no-data notes are missing
export const COUNTER_CONFIG_ERROR = "counter configuration unreadable (config/counters.yaml; see the server log): cities without open counter data are not named as such";
export const AVG_DAILY = "index of average daily intensity (monthly values), not of counts";
export const COVID_TEXT = "COVID year";
// the attribution note of each city whose counter index is drawn (ADR 0008, M8 note)
export const COUNTER_DATA = "Counter data";
export const NOT_RECORDED = "not recorded";
// Compare's counter metric: title, unit and footnote (app/compare.py has the same strings; a test
// asserts it). The unit's base year comes from the drawn cities (counterUnit).
export const COUNTER_TITLE = "counter sites"; // the counter index is the same for both boundaries
export const COUNTER_CONTEXT = "Counters are context: they record the bicycles passing the sites where they stand, not those elsewhere in the city.";
export const COUNTER_FOOT = "Counter index: each city's base year = 100, never rebased. Counters are context: counts recorded at counter sites, not cycling in the whole city. Ranks in the Rank view depend on the cities selected.";
export const COUNTER_OF = "index of counts recorded at counter sites (or of their average daily intensity)";
export const ANY_BASE = "each city's base year = 100"; // no city drawn: no year to name

const range = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => String(a + i));

/** The COVID-year mark of a counter chart, if the year is on the axis. */
export function covidMarks(D, labels) {
  const y = String(D.counters?.covid_year ?? "");
  return labels.includes(y) ? [{ label: y, text: COVID_TEXT }] : [];
}

/** The counter metric's chart and table title. */
export const counterTitle = (label) => `${label} · ${COUNTER_TITLE}`;

/**
 * The counter index unit for `ids`, naming the base year (= 100) of the cities drawn as a line:
 * the base year of most of them (a tie: the earliest), then each other base year with its cities,
 * "2019 = 100 (2020 = 100 for Madrid)"; no city drawn: each city's base year.
 */
export function counterUnit(D, ids) {
  const counters = D.counters?.cities ?? {};
  const byBase = new Map();
  for (const id of ids) {
    if (!counters[id]?.line) continue;
    const y = counters[id].base_year;
    if (!byBase.has(y)) byBase.set(y, []);
    byBase.get(y).push(D.cities[id].name);
  }
  let base = ANY_BASE;
  if (byBase.size) {
    const years = [...byBase.keys()].sort((a, b) => a - b);
    const lead = years.reduce((best, y) => (byBase.get(y).length > byBase.get(best).length ? y : best));
    const others = years.filter((y) => y !== lead).map((y) => `${y} = 100 for ${byBase.get(y).join(", ")}`).join("; ");
    base = `${lead} = 100${others ? ` (${others})` : ""}`;
  }
  const covid = D.counters?.covid_year;
  return `${COUNTER_OF}, ${base}${covid != null ? `; ${covid} is the COVID year` : ""}`;
}

/**
 * Compare's counter index for `ids`: {labels, series: [{id, name, points: [{label, value,
 * flags}]}], notes, marks, unit}. Labels are the calendar years from the first to the last with a value
 * for any drawn city; a city without counter data, or whose index is not a line, has no values
 * and a note. Each drawn city gets an attribution note, after the others: "Counter data, <city>:
 * <publisher>, licence <licence>" (ADR 0008). An unreadable config/counters.yaml is a note before
 * all others.
 */
export function counterLines(D, ids) {
  const counters = D.counters?.cities ?? {};
  const drawn = ids.filter((id) => counters[id]?.line);
  const years = drawn.flatMap((id) => counters[id].points.filter((p) => p.idx != null).map((p) => p.year));
  const labels = years.length ? range(Math.min(...years), Math.max(...years)) : [];
  const notes = D.counters?.config_error ? [COUNTER_CONFIG_ERROR] : [];
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
  for (const id of drawn) {
    const c = counters[id];
    notes.push(`${COUNTER_DATA}, ${D.cities[id].name}: ${c.source || `source ${NOT_RECORDED}`}, licence ${c.licence || NOT_RECORDED}`);
  }
  return { labels, series, notes, marks: covidMarks(D, labels), unit: counterUnit(D, ids) };
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
