// The JS literal guard of strings.test.mjs (M12 spec decision 2): the string and template literals
// of a script, and those of them that read as English text. A literal is text when it has two or
// more words of two or more letters outside the allowlist. Not text: a t("…") key, an import
// path or a page path, a CSS selector (a querySelector/closest/matches/matchMedia argument, or
// one with an attribute selector), a console message, a class or rel token list, and a few
// named exceptions.

/** [{text, line, before}] for every string and template literal (a template's `${…}` parts are
 * NUL); comments and regular expression literals are skipped. */
export function literals(src) {
  const out = [];
  const n = src.length;
  let i = 0;
  let line = 1;
  let prev = ""; // the last significant character of code
  const regexCanStart = () =>
    !prev || /[(,=:[!&|?{};+\-*%<>~^]/.test(prev) ||
    /\b(?:return|typeof|case|in|of|delete|void|throw|new|else|do)$/.test(src.slice(Math.max(0, i - 8), i).trimEnd());
  const push = (kind, text, l, at) => out.push({ kind, text, line: l, before: src.slice(Math.max(0, at - 120), at) });

  function code(untilBrace) {
    let depth = 0;
    while (i < n) {
      const c = src[i];
      if (c === "\n") { line++; i++; continue; }
      if (c === "/" && src[i + 1] === "/") { while (i < n && src[i] !== "\n") i++; continue; }
      if (c === "/" && src[i + 1] === "*") {
        const end = src.indexOf("*/", i + 2);
        for (let k = i; k < end; k++) if (src[k] === "\n") line++;
        i = end + 2;
        continue;
      }
      if (c === '"' || c === "'") {
        const at = i;
        const l = line;
        let s = "";
        for (i++; i < n && src[i] !== c; i++) {
          if (src[i] === "\\") s += src[++i];
          else s += src[i];
        }
        i++;
        push("str", s, l, at);
        prev = "a";
        continue;
      }
      if (c === "`") { template(); prev = "a"; continue; }
      if (c === "/" && regexCanStart()) {
        let cls = false;
        for (i++; i < n; i++) {
          const d = src[i];
          if (d === "\\") { i++; continue; }
          if (d === "[") cls = true;
          else if (d === "]") cls = false;
          else if (d === "/" && !cls) break;
        }
        i++;
        while (/[a-z]/.test(src[i] ?? "")) i++;
        prev = "a";
        continue;
      }
      if (untilBrace) {
        if (c === "{") depth++;
        if (c === "}") {
          if (depth === 0) { i++; return; }
          depth--;
        }
      }
      if (!/\s/.test(c)) prev = c;
      i++;
    }
  }

  function template() {
    const at = i;
    const l = line;
    let s = "";
    for (i++; i < n && src[i] !== "`"; ) {
      if (src[i] === "\\") { s += src[i + 1]; i += 2; continue; }
      if (src[i] === "$" && src[i + 1] === "{") {
        i += 2;
        prev = "(";
        code(true);
        s += "\0";
        continue;
      }
      if (src[i] === "\n") line++;
      s += src[i++];
    }
    i++;
    push("tpl", s, l, at);
  }

  code(false);
  return out;
}

// the brand, unit symbols and abbreviations, and the BibTeX/CSL field names cite.js writes
const ALLOWED = new Set([
  "velometer", "km", "OSM", "LAU", "FUA", "CSV", "SVG", "PNG", "JSON", "HTTP", "ODbL", "BibTeX",
  "CSL", "author", "title", "year", "howpublished", "note", "url", "misc", "language",
  "dataset", "literal", "issued", "accessed", "version", "type",
]); // fmt: skip

/** The words of a literal: whitespace-separated tokens that are letters only once their
 * punctuation and markup are stripped (a token with a digit, `0px`, is none), of two or more
 * letters, outside ALLOWED. */
export function words(text) {
  return text
    .replace(/<[^>]*>/g, " ")
    .split(/[\s\0]+/)
    .map((w) => w.replace(/^[^\p{L}\d]+|[^\p{L}\d]+$/gu, ""))
    .filter((w) => /^\p{L}[\p{L}'’]+$/u.test(w) && !ALLOWED.has(w));
}

const SELECTOR_CALL = /\b(?:querySelector|querySelectorAll|closest|matches|matchMedia)\(\s*$/;
const ATTRIBUTE_SELECTOR = /\[[a-z][\w-]*(?:[~|^$*]?=[^\]]*)?\]/;
const NOT_TEXT = [
  /\bt\(\s*$/, // a catalogue key
  /\bconsole\.\w+\(\s*$/, // a console message
  /(?:\bimport|\bfrom)\s*\(?\s*$/, // an import path
  /\b(?:class|className|rel)\s*[:=][^,;{}()]*$/, // class and rel token lists
  /\bsetAttribute\(\s*["'](?:class|rel)["']\s*,\s*$/,
];
// named exceptions: the English CSV preamble (spec 4.5) and a developer's assertion
const EXCEPTIONS = [
  { file: "download.js", before: /\b(?:ATTRIBUTION|CSV_NOTE)\s*=\s*$/ },
  { file: "base.js", text: /^an internal URL must start with/ },
];

/** The literals of `src` (a file named `file`) that read as English text. */
export function offenders(src, file) {
  return literals(src)
    .filter((l) => l.text !== "use strict" && !l.text.startsWith("/")) // a directive, a path
    .filter((l) => !SELECTOR_CALL.test(l.before) && !ATTRIBUTE_SELECTOR.test(l.text))
    .filter((l) => !NOT_TEXT.some((re) => re.test(l.before)))
    .filter((l) => !EXCEPTIONS.some((e) => e.file === file && (e.before?.test(l.before) || e.text?.test(l.text))))
    .filter((l) => words(l.text).length >= 2)
    .map((l) => ({ file, line: l.line, text: l.text }));
}
