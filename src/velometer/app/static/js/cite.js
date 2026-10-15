// Citation formats (M11 spec decision 3): readable text, BibTeX and CSL-JSON. The mirror of
// app/cite.py (cite_text); all three are tested against tests/cite_cases.json, which has cases per
// language (M12). The words are the page's `js.cite.*` strings (the twins of `cite.*`); `lang`
// adds the language field to BibTeX and CSL-JSON. Fields are the keys of CiteFields (snake_case,
// as `asdict` emits them).
import { base } from "./base.js";
import { t } from "./strings.js";

// the language field of a German citation: BibTeX (babel name) and CSL-JSON
const BIBTEX_LANGUAGE = { de: "german" };

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
  const parts = [
    f.snapshot_note || t("js.cite.snapshot", { timestamp: f.osm_timestamp }),
    t("js.cite.classifier", { version: f.classifier }),
  ];
  if (f.run_id !== null && f.run_id !== undefined) parts.push(t("js.cite.run", { run: f.run_id }));
  parts.push(t("js.cite.commit", { commit: f.commit }));
  return parts.join("; ");
}

const attribution = (f) => f.attribution ?? t("js.cite.attribution");

/** The readable citation (app/cite.py: cite_text). Its words are the page's strings, so it takes
 * no language (citeBibtex and citeCsl do). */
export function citeText(f, accessed = null, url = null) {
  let text = t("js.cite.text", { year: year(f), title: f.title, provenance: provenance(f), attribution: attribution(f) });
  if (url) text += " " + (accessed ? t("js.cite.accessed", { url, accessed }) : `${url}.`);
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

export function citeBibtex(f, accessed = null, url = null, lang = "en") {
  const note =
    `${provenance(f)}. ${attribution(f)}.` + (accessed ? ` ${t("js.cite.accessed_note", { accessed })}` : "");
  const fields = [
    "author = {{velometer}}",
    `title = {${bibEscape(f.title)}}`,
    `year = {${year(f)}}`,
  ];
  if (url) fields.push(`howpublished = {\\url{${bibUrl(url)}}}`);
  if (BIBTEX_LANGUAGE[lang]) fields.push(`language = {${BIBTEX_LANGUAGE[lang]}}`);
  fields.push(`note = {${bibEscape(note)}}`);
  return `@misc{${key(f, accessed)},\n  ${fields.join(",\n  ")}\n}`;
}

export function citeCsl(f, accessed = null, url = null, lang = "en") {
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
  if (lang !== "en") item.language = lang;
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
 * Compare uses it to rebuild its citation when the cities change without a reload. The snapshot
 * note and the attribution are the page's strings.
 */
export function multiFields(runs, ids, title, path, commit, attr = t("js.cite.attribution")) {
  const rows = ids.map((id) => runs[id]).filter(Boolean);
  if (!rows.length) return null;
  const days = rows.map((r) => r.osm_timestamp.slice(0, 10)).sort();
  const [first, last] = [days[0], days[days.length - 1]];
  return {
    title,
    path,
    osm_timestamp: null,
    snapshot_note: first === last
      ? t("js.cite.snapshot_one", { day: first })
      : t("js.cite.snapshot_range", { first, last }),
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
