// Citation formats (M11 spec decision 3): readable text, BibTeX and CSL-JSON. The mirror of
// app/cite.py (cite_text); all three are tested against tests/cite_cases.json. Fields are the
// keys of CiteFields (snake_case, as `asdict` emits them).
import { base } from "./base.js";

const ATTRIBUTION = "Map data © OpenStreetMap contributors, ODbL 1.0";

function year(f) {
  if (f.osm_timestamp) return f.osm_timestamp.slice(0, 4);
  const dates = (f.snapshot_note ?? "").match(/\d{4}-\d{2}-\d{2}/g);
  return dates ? dates[dates.length - 1].slice(0, 4) : "";
}

/** The snapshot's day, for the BibTeX key when there is no accessed date. */
function snapshotDay(f) {
  if (f.osm_timestamp) return f.osm_timestamp.slice(0, 10);
  const dates = (f.snapshot_note ?? "").match(/\d{4}-\d{2}-\d{2}/g);
  return dates ? dates[dates.length - 1] : "";
}

function provenance(f) {
  const parts = [f.snapshot_note || `OSM snapshot ${f.osm_timestamp}`, `classifier ${f.classifier}`];
  if (f.run_id !== null && f.run_id !== undefined) parts.push(`run ${f.run_id}`);
  parts.push(`commit ${f.commit}`);
  return parts.join("; ");
}

const attribution = (f) => f.attribution ?? ATTRIBUTION;

export function citeText(f, accessed = null, url = null) {
  let text = `velometer (${year(f)}). ${f.title} [Data set]. ${provenance(f)}. ${attribution(f)}.`;
  if (url) text += ` ${url}` + (accessed ? ` (accessed ${accessed}).` : ".");
  return text;
}

/** `velometer_<title slug, 40 chars>_<yyyymmdd>`: the accessed day, else the snapshot's. */
function key(f, accessed) {
  const slug = f.title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40)
    .replace(/_+$/, "");
  return `velometer_${slug}_${(accessed || snapshotDay(f)).replaceAll("-", "")}`;
}

const BIB_SPECIAL = {
  "\\": "\\textbackslash{}",
  "~": "\\textasciitilde{}",
  "^": "\\textasciicircum{}",
};
// one pass, so the braces of \textbackslash{} are not escaped again
const bibEscape = (s) => s.replace(/[\\~^{}%&#_$]/g, (c) => BIB_SPECIAL[c] ?? `\\${c}`);

// A page URL goes into \url{...}: a brace or backslash would close the group and let a crafted
// link inject LaTeX, so those and spaces are percent-encoded; `%` and `#` stay (url package).
const bibUrl = (u) => u.replace(/[{}\\ ]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase().padStart(2, "0"));

export function citeBibtex(f, accessed = null, url = null) {
  const note =
    `${provenance(f)}. ${attribution(f)}.` + (accessed ? ` Accessed ${accessed}` : "");
  const fields = [
    "author = {{velometer}}",
    `title = {${bibEscape(f.title)}}`,
    `year = {${year(f)}}`,
  ];
  if (url) fields.push(`howpublished = {\\url{${bibUrl(url)}}}`);
  fields.push(`note = {${bibEscape(note)}}`);
  return `@misc{${key(f, accessed)},\n  ${fields.join(",\n  ")}\n}`;
}

export function citeCsl(f, accessed = null, url = null) {
  const item = {
    type: "dataset",
    id: key(f, accessed),
    title: f.title,
    author: [{ literal: "velometer" }],
    issued: { "date-parts": [[Number(year(f))]] },
  };
  if (accessed) item.accessed = { "date-parts": [accessed.split("-").map(Number)] };
  if (url) item.URL = url;
  item.note = `${provenance(f)}. ${attribution(f)}.`;
  item.version = f.commit;
  return item;
}

const bare = (p) => p.replace(/(^|\/)index\.html$/, "").replace(/^\/+|\/+$/g, "");

/** origin + base + path (no leading slash), plus the page's query and fragment when the path is
 * the page shown: a figure of another page (the city panel open on Compare) cites that page's own
 * address, not this page's state. */
export function absoluteUrl(path, loc = globalThis.location, doc = globalThis.document) {
  const b = base(doc);
  const own = path.replace(/^\/+/, "");
  const at = String(loc.pathname ?? "");
  const shown = at.startsWith(b) ? at.slice(b.length) : at;
  const state = bare(shown) === bare(own) ? loc.search + loc.hash : "";
  return loc.origin + b + own + state;
}

const natural = (s) => s.split(/(\d+)/).map((p, i) => (i % 2 ? Number(p) : p));
function compareNatural(a, b) {
  const x = natural(a);
  const y = natural(b);
  for (let i = 0; i < Math.min(x.length, y.length); i++) {
    if (x[i] === y[i]) continue;
    return x[i] < y[i] ? -1 : 1;
  }
  return x.length - y.length;
}

/**
 * Fields for several cities, as app/cite.py fields_for_cities, from `runs`
 * ({city: {osm_timestamp, classifier}}); cities without a run are skipped, null when none has one.
 * Compare uses it to rebuild its citation when the cities change without a reload.
 */
export function multiFields(runs, ids, title, path, commit, attr = ATTRIBUTION) {
  const rows = ids.map((id) => runs[id]).filter(Boolean);
  if (!rows.length) return null;
  const days = rows.map((r) => r.osm_timestamp.slice(0, 10)).sort();
  const [first, last] = [days[0], days[days.length - 1]];
  return {
    title,
    path,
    osm_timestamp: null,
    snapshot_note: first === last ? `OSM snapshot of ${first}` : `OSM snapshots of ${first} to ${last}`,
    classifier: [...new Set(rows.map((r) => r.classifier))].sort(compareNatural).join("/"),
    run_id: null,
    commit,
    attribution: attr,
  };
}

/** The CSL-JSON item as shown and copied: 2-space indent, each `date-parts` array on one line. */
export function cslJson(item) {
  return JSON.stringify(item, null, 2).replace(
    /"date-parts": \[\s+\[([\s\S]*?)\]\s+\]/g,
    (_, inner) => `"date-parts": [[${inner.replace(/\s+/g, " ").trim()}]]`,
  );
}
