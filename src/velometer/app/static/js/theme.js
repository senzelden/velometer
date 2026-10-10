// Colours come from the stylesheet's tokens (app.css), so charts and maps follow the OS theme.
// `read` is injectable for node tests; in the page it reads the root's computed style.
export const MISSING = "#808080";
const warned = new Set();

const pageRead = (name) =>
  globalThis.getComputedStyle?.(globalThis.document.documentElement).getPropertyValue(name).trim() ?? "";

/** The value of one colour token. A missing token logs one console error (the render pass fails on it). */
export function token(name, read = pageRead) {
  const v = read(name);
  if (v) return v;
  if (!warned.has(name)) {
    warned.add(name);
    console.error(`velometer: colour token ${name} is not defined`);
  }
  return MISSING;
}

/** The 8 series colours, slot 0 first. */
export const seriesColours = (read = pageRead) =>
  Array.from({ length: 8 }, (_, i) => token(`--series-${i + 1}`, read));

/** Tier letter -> colour. */
export const tierColours = (read = pageRead) =>
  Object.fromEntries([..."ABCDE"].map((t) => [t, token(`--tier-${t.toLowerCase()}`, read)]));

/** Call `fn` whenever the OS colour scheme changes; returns an unsubscribe function. */
export function onThemeChange(fn, matchMedia = globalThis.matchMedia) {
  const q = matchMedia?.("(prefers-color-scheme: dark)");
  q?.addEventListener("change", fn);
  return () => q?.removeEventListener("change", fn);
}
