// The base path the site is served under (M9 spec decision 3), from the page's
// <meta name="velometer-base">, and url(): every internal URL a script fetches, links or puts in
// history goes through it. The mirror of app/urls.py (normalise_base, make_u); both are tested
// against tests/url_cases.json. The live app runs with base `/`, where url() is the identity.
// URLs a script reads from a page's JSON config already carry the base: never pass them here.
// M12: on a German page (<html lang="de">) url() puts `de/` after the base for a page path, as
// make_u(base, "de") does; data, map and static paths are shared by both editions and never get
// it (JS has no data_u: url() is its single rule).

/** `b` with exactly one leading and one trailing `/` ("" and "/" are `/`). */
function normalise(b) {
  const inner = String(b).replace(/^\/+|\/+$/g, "");
  return inner ? `/${inner}/` : "/";
}

/** A scheme (`https:`, `mailto:`) or a protocol-relative `//host`: not ours to prefix. */
function isExternal(u) {
  if (u.startsWith("//")) return true;
  const colon = u.indexOf(":");
  return colon > 0 && /^\p{L}+$/u.test(u.slice(0, colon));
}

/** Data, map and static paths: one file for both languages. */
const DATA_PATH = /^\/(?:data|maps|static)(?=[/?#]|$)/;
/** A path already under the German prefix. */
const UNDER_DE = /^\/de(?=[/?#]|$)/;

/** The page's language from its root element: `de` for a German page, else `en`. */
export function lang(doc = globalThis.document) {
  return String(doc?.documentElement?.lang ?? "").toLowerCase().startsWith("de") ? "de" : "en";
}

/** The page's base path, normalised; `/` when there is no document or no meta tag. */
export function base(doc = globalThis.document) {
  const content = doc?.querySelector('meta[name="velometer-base"]')?.getAttribute("content");
  return normalise(content ?? "/");
}

/**
 * `url("/city/berlin")` is `<base>city/berlin` (query and fragment kept), `<base>de/city/berlin`
 * on a German page. Data, map and static paths and paths already under the German prefix get
 * no language prefix. External URLs and a fragment-only `#x` come back unchanged; any other path must start
 * with `/`, else it throws.
 */
export function url(path, doc = globalThis.document) {
  if (path.startsWith("#") || isExternal(path)) return path;
  if (!path.startsWith("/")) throw new Error(`an internal URL must start with '/': ${JSON.stringify(path)}`);
  const page = lang(doc) === "de" && !DATA_PATH.test(path) && !UNDER_DE.test(path);
  return base(doc) + (page ? `de${path}` : path.slice(1));
}
