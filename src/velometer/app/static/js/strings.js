// The page's UI strings (M12 spec decision 2): the `js.*` catalogue keys of content/ui/<lang>.yaml
// and the month names, in the page's language with English underneath, from the
// <script type="application/json" id="ui-strings"> block base.html writes
// (velometer.i18n.js_strings). Every user-facing word a script writes goes through t().

let strings = null; // the page's language, read from the block on first use
let english = {}; // what a key missing in `strings` falls back to

/** Use `obj` as the strings and `fallback` (English) under them (tests; loadStrings). */
export function setStrings(obj, fallback = obj) {
  strings = obj ?? {};
  english = fallback ?? {};
}

/** Read the page's #ui-strings block; false (and the strings unchanged) when there is none. */
export function loadStrings(doc = globalThis.document) {
  const node = doc?.getElementById?.("ui-strings");
  if (!node) return false;
  try {
    const obj = JSON.parse(node.textContent);
    setStrings(obj, obj); // the block already has English under the page's language
    return true;
  } catch (err) {
    console.error("velometer: the #ui-strings block is not JSON", err);
    return false;
  }
}

/**
 * The string of `key` with its `{name}` placeholders filled from `vars`; a plural ({one, other})
 * picks by `vars.count`. A key the strings lack gives its English value. Only a key in neither
 * (a bug the node and pytest key tests catch) gives the key itself.
 */
export function t(key, vars = {}) {
  if (strings === null) loadStrings();
  let value = strings?.[key] ?? english[key];
  if (value === undefined) {
    console.error(`velometer: no UI string ${key}`);
    return key;
  }
  if (typeof value === "object") value = vars.count === 1 ? value.one : value.other;
  return value.replace(/\{(\w+)\}/g, (all, name) => (name in vars ? String(vars[name]) : all));
}
