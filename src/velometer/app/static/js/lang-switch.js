// The nav's language switch (M12 spec decision 1): a plain link to the same page in the other
// language, which works without JS. With JS the link also carries the current query and hash, so
// a permalink (Compare's selection, a chart anchor) survives the switch. The twin's path is the
// server's (`data-href`, already based); the query and hash are this page's.

/** `href` with the location's query and hash, unless `href` already has a query or hash. */
export function switchHref(href, loc) {
  if (/[?#]/.test(href)) return href;
  return href + (loc.search || "") + (loc.hash || "");
}

function wire(doc) {
  for (const a of doc.querySelectorAll("a.lang-switch[data-href]")) {
    const update = () => {
      a.href = switchHref(a.dataset.href, globalThis.location);
    };
    for (const type of ["focus", "pointerenter", "click"]) a.addEventListener(type, update);
  }
}

if (globalThis.document) wire(globalThis.document);
