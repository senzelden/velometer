// The base path the site is served under (M9 spec decision 3), from the page's
// <meta name="velometer-base">, and url(): every internal URL a script fetches, links or puts in
// history goes through it. The mirror of app/urls.py (normalise_base, make_u); both are tested
// against tests/url_cases.json. The live app runs with base `/`, where url() is the identity.
// URLs a script reads from a page's JSON config already carry the base: never pass them here.

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

/** The page's base path, normalised; `/` when there is no document or no meta tag. */
export function base(doc = globalThis.document) {
  const content = doc?.querySelector('meta[name="velometer-base"]')?.getAttribute("content");
  return normalise(content ?? "/");
}

/**
 * `url("/city/berlin")` is `<base>city/berlin` (query and fragment kept). External URLs and a
 * fragment-only `#x` come back unchanged; any other path must start with `/`, else it throws.
 */
export function url(path, doc = globalThis.document) {
  if (path.startsWith("#") || isExternal(path)) return path;
  if (!path.startsWith("/")) throw new Error(`an internal URL must start with '/': ${JSON.stringify(path)}`);
  return base(doc) + path.slice(1);
}
