// Cite this figure (M11): upgrades each `details.cite` on its first open into three labelled
// blocks (Text, BibTeX, CSL-JSON), each a <pre> with a Copy button. The fields come from the
// `.cite-data` JSON the server wrote. The access date and the absolute address (base path, query
// and fragment included) are taken when the disclosure opens, so a permalink state is in them.
// Compare rebuilds its citation by calling `setFields` on the details and closing it.
import { absoluteUrl, citeBibtex, citeCsl, citeText } from "./cite.js";
import { copyText } from "./clipboard.js";

const FORMATS = [
  ["Text", (f, a, u) => citeText(f, a, u)],
  ["BibTeX", (f, a, u) => citeBibtex(f, a, u)],
  ["CSL-JSON", (f, a, u) => JSON.stringify(citeCsl(f, a, u), null, 2)],
];

let serial = 0;
const today = () => new Date().toISOString().slice(0, 10);

function el(tag, attrs = {}, text) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}

/** The fields the details currently holds. */
export const fieldsOf = (details) => JSON.parse(details.querySelector(".cite-data").textContent);

/** Replace the details' fields (the JSON blob, its screen-reader name) and close it. */
export function setFields(details, fields) {
  details.querySelector(".cite-data").textContent = JSON.stringify(fields);
  const name = details.querySelector("summary .visually-hidden");
  if (name) name.textContent = ` ${fields.title}`;
  details.open = false;
}

/** Fill the details' blocks from its fields, the date and the address of this moment (a reopen
 * redoes it, replacing the blocks). */
function render(details) {
  const f = fieldsOf(details);
  const accessed = today();
  const url = absoluteUrl(f.path);
  details.querySelector(".cite-text")?.remove();
  details.querySelector(".cite-blocks")?.remove();
  const blocks = el("div", { class: "cite-blocks" });
  FORMATS.forEach(([label, make]) => {
    const text = make(f, accessed, url);
    const id = `cite-${++serial}`;
    const block = el("div", { class: "cite-block" });
    const head = el("div", { class: "cite-head" });
    head.append(el("h4", { id: `${id}-h` }, label));
    const button = el("button", { type: "button", class: "cite-copy" }, "Copy");
    button.setAttribute("aria-label", `Copy ${label}`);
    button.addEventListener("click", () => copyText(text));
    head.append(button);
    const scroll = el("div", { class: "scroll", tabindex: "0", role: "region" });
    scroll.setAttribute("aria-labelledby", `${id}-h`);
    scroll.append(el("pre", {}, text));
    block.append(head, scroll);
    blocks.append(block);
  });
  details.append(blocks);
}

/** Render on every open: the date and the address are those of the moment (a permalink state). */
function upgrade(details) {
  if (details.dataset.citeBound !== undefined) return;
  details.dataset.citeBound = "";
  details.addEventListener("toggle", () => {
    if (details.open) render(details);
  });
}

for (const d of document.querySelectorAll("details.cite")) upgrade(d);

// the city panel is fetched after load: upgrade the cites it brings
new MutationObserver((records) => {
  for (const r of records)
    for (const n of r.addedNodes)
      if (n.nodeType === 1)
        for (const d of n.matches("details.cite") ? [n] : n.querySelectorAll("details.cite")) upgrade(d);
}).observe(document.body, { childList: true, subtree: true });
