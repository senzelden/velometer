// "Copy link" (M11): reveals the box of each `.copy-link` button (hidden without JavaScript) and copies the
// page's address as it is now: base path, query and hash included, so the permalink state the
// page wrote with history.replaceState is in it. Where the clipboard is refused, the address is
// shown in a <pre> and selected so Ctrl+C finishes the job.
import { copyText } from "./clipboard.js";
import { currentAddress } from "./permalink.js";

async function copy(button) {
  const text = currentAddress();
  button.parentNode.querySelector("pre.copy-link-url")?.remove();
  const pre = document.createElement("pre");
  pre.className = "copy-link-url";
  pre.textContent = text;
  button.after(pre);
  // copyText selects the <pre> holding the text when the clipboard refuses; it stays then
  if ((await copyText(text)) === "copied") pre.remove();
}

for (const button of document.querySelectorAll(".copy-link")) {
  const box = button.closest(".permalink");
  if (box) box.hidden = false;
  button.addEventListener("click", () => copy(button));
}
