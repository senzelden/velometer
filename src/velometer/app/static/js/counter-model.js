// The counter index as chart models (Counts tab, Compare's counter_index metric), from the
// `counters` block of /data/series.json. Pure (no DOM). Counters are context: counts recorded at
// counter sites, never cycling in a city. A year without an index value is a gap (null), never 0.
// A city listed under `none:` in config/counters.yaml gets its note from `counters.none`.
// app/compare.py: counter_lines computes the Compare table the same way for the no-JS page.

import { t } from "./strings.js";

export const COUNTER_METRIC = "counter_index";
// The texts are the `js.counts.*` strings of the page's language, the twins of the `counts.*`
// keys app/compare.py uses (a pytest runs counterLines, counterTitle and footnote against the
// Python in both languages). The unit's base year comes from the drawn cities (counterUnit).

/** Compare's line under the counter metric's title: what a counter records. */
export const counterContext = () => t("js.counts.context");
/** Compare's footnote for the counter metric. */
export const counterFoot = () => t("js.counts.foot");

const range = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => String(a + i));

/** The COVID-year mark of a counter chart, if the year is on the axis. */
export function covidMarks(D, labels) {
  const y = String(D.counters?.covid_year ?? "");
  return labels.includes(y) ? [{ label: y, text: t("js.counts.covid_year") }] : [];
}

/** The counter metric's chart and table title (the index is the same for both boundaries). */
export const counterTitle = (label) => `${label} · ${t("js.counts.title")}`;

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
  let base = t("js.counts.any_base"); // no city drawn: no year to name
  if (byBase.size) {
    const years = [...byBase.keys()].sort((a, b) => a - b);
    const lead = years.reduce((best, y) => (byBase.get(y).length > byBase.get(best).length ? y : best));
    const others = years
      .filter((y) => y !== lead)
      .map((y) => t("js.counts.base_for", { year: y, cities: byBase.get(y).join(", ") }))
      .join("; ");
    base = `${lead} = 100${others ? ` (${others})` : ""}`;
  }
  const covid = D.counters?.covid_year;
  const covidNote = covid != null ? `; ${t("js.counts.covid_is", { year: covid })}` : "";
  return `${t("js.counts.of")}, ${base}${covidNote}`;
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
  // config/counters.yaml unreadable (`counters.config_error`): the no-data notes are missing
  const notes = D.counters?.config_error ? [t("js.counts.config_error")] : [];
  const series = ids.map((id) => {
    const c = counters[id];
    const name = D.cities[id].name;
    if (!c) notes.push(`${name}: ${D.counters?.none?.[id] ?? t("js.counts.no_counters")}`);
    else if (!c.line) notes.push(`${name}: ${t("js.counts.no_line")}`);
    else if (c.series === "avg_daily_intensity") notes.push(`${name}: ${t("js.counts.avg_daily")}`);
    const by = new Map(c?.line ? c.points.map((p) => [String(p.year), p.idx]) : []);
    const points = labels.map((label) => {
      const v = by.get(label);
      return { label, value: Number.isFinite(v) ? v : null, flags: [] };
    });
    return { id, name, points };
  });
  for (const id of drawn) {
    const c = counters[id];
    notes.push(t("js.counts.attribution", {
      city: D.cities[id].name,
      source: c.source || t("js.counts.source_not_recorded"),
      licence: c.licence || t("js.counts.not_recorded"),
    }));
  }
  return { labels, series, notes, marks: covidMarks(D, labels), unit: counterUnit(D, ids) };
}

/**
 * The Counts tab chart of one city: the counter index and the A+B mapped-km index of the city
 * proper (1 January snapshots), both base year = 100 (the counter index's base year). Years run
 * from the first to the last with either value. No counter line: no chart (the tab mounts one
 * only for a city with a line and shows a note otherwise). No km for the base year: the counter
 * line alone. `names`: {counter, km, counterShort, kmShort}, the short ones for end labels at
 * phone width.
 */
export function countsChart(D, id, names = {}) {
  const c = D.counters?.cities?.[id];
  if (!c?.line) return null;
  const base = c.base_year;
  const counter = new Map(c.points.filter((p) => p.idx != null).map((p) => [p.year, p.idx]));
  const km = new Map();
  const snaps = (D.series?.[`${id}/lau`] ?? []).filter((p) => p.label !== "current");
  const b = snaps.find((p) => Number(p.label) === base)?.ab_km;
  if (Number.isFinite(b) && b !== 0) {
    for (const p of snaps) if (Number.isFinite(p.ab_km)) km.set(Number(p.label), (p.ab_km / b) * 100);
  }
  const years = [...counter.keys(), ...km.keys()];
  const labels = range(Math.min(...years), Math.max(...years));
  const line = (map, sid, name, short) => ({
    id: sid,
    name,
    short, // the end label when the full name has no room; the key under the chart names it
    points: labels.map((l) => ({ label: l, value: map.has(Number(l)) ? map.get(Number(l)) : null, flags: [] })),
  });
  const series = [line(counter, "counter", names.counter ?? t("js.counts.index"), names.counterShort ?? t("js.counts.short_counts"))];
  if (km.size) {
    series.push(line(km, "km", names.km ?? t("js.counts.km_index"), names.kmShort ?? t("js.counts.short_km")));
  }
  return { labels, series, marks: covidMarks(D, labels), base };
}
