// A polite live region (#live, in base.html) for changes a screen-reader user cannot see:
// the Compare redraw and the city panel loading. A page without #live announces nothing.

const nextFrame = (f) => (globalThis.requestAnimationFrame ?? ((g) => setTimeout(g, 0)))(f);
let latest = 0;

/** Say `text`. Clearing first and setting in the next frame makes an identical repeat read again. */
export function announce(text, doc = globalThis.document) {
  const live = doc?.getElementById?.("live");
  if (!live) return;
  const mine = ++latest;
  live.textContent = "";
  nextFrame(() => {
    if (mine === latest) live.textContent = text;
  });
}
