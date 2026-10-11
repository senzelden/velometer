// Copy text to the clipboard, falling back to selecting it (M11). Shared by the citations and
// the permalink button. Where the clipboard is refused (an insecure origin, a denied permission,
// no API) the text is selected in the matching <pre> so Ctrl+C finishes the job.
import { announce as say } from "./live.js";

/**
 * Resolve "copied" after `nav.clipboard.writeText`, or "selected" after selecting the `<pre>`
 * that holds `text` and announcing how to finish. Both outcomes are announced.
 */
export async function copyText(text, { nav = globalThis.navigator, doc = globalThis.document, announce = say } = {}) {
  try {
    await nav.clipboard.writeText(text);
    announce("Copied");
    return "copied";
  } catch {
    const pre = [...(doc?.querySelectorAll?.("pre") ?? [])].find((p) => p.textContent === text);
    if (pre) {
      const sel = doc.getSelection();
      const range = doc.createRange();
      range.selectNodeContents(pre);
      sel.removeAllRanges();
      sel.addRange(range);
    }
    announce("Press Ctrl+C to copy");
    return "selected";
  }
}
