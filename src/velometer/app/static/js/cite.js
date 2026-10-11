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

const bibEscape = (s) => s.replace(/[{}%&#_]/g, (c) => `\\${c}`);

export function citeBibtex(f, accessed = null, url = null) {
  const note =
    `${provenance(f)}. ${attribution(f)}.` + (accessed ? ` Accessed ${accessed}` : "");
  const fields = [
    "author = {{velometer}}",
    `title = {${bibEscape(f.title)}}`,
    `year = {${year(f)}}`,
  ];
  if (url) fields.push(`howpublished = {\\url{${url}}}`);
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

/** origin + base + path (no leading slash) + the page's query and fragment. */
export function absoluteUrl(path, loc = globalThis.location, doc = globalThis.document) {
  return loc.origin + base(doc) + path.replace(/^\/+/, "") + loc.search + loc.hash;
}
