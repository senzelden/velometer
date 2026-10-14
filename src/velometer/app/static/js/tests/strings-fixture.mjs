// The JS strings of both languages as the pages get them (tests/ui_js_strings.json, generated
// from velometer.i18n.js_strings and kept equal to it by tests/test_ui_strings.py). Importing this
// module loads the English strings, as an English page's #ui-strings block does; `useLang` swaps.
import { readFileSync } from "node:fs";
import { setStrings } from "../strings.js";

export const FIXTURE = JSON.parse(
  readFileSync(new URL("../../../../../../tests/ui_js_strings.json", import.meta.url), "utf8"),
);

/** The page's strings for `lang`, English underneath (what the block holds). */
export const useLang = (lang) => setStrings(FIXTURE[lang], FIXTURE.en);

/** A document whose root element has `lang`, and a `#ui-strings` block when `strings` is given. */
export const fakeDoc = (lang, strings = null) => ({
  documentElement: { lang },
  getElementById: (id) => (id === "ui-strings" && strings ? { textContent: JSON.stringify(strings) } : null),
  querySelector: () => null,
});

useLang("en");
