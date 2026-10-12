// Search and jump (M11): a WAI-ARIA 1.2 combobox in the nav over /data/search.json. The pure
// part (fold, rank, move) is tested under node; the DOM part runs only in a page. Without this
// file the nav keeps its "Find a city" link to /cities.
import { url } from "./base.js";
import { announce } from "./live.js";

// Letters NFD does not take apart: a keyboard without them must still find the city.
const LETTERS = { ł: "l", ø: "o", đ: "d", ð: "d", æ: "ae", œ: "oe", ß: "ss", þ: "th", ı: "i" };

/** NFD, combining marks stripped, special letters mapped, lower case, spaces collapsed, trimmed. */
export function fold(s) {
  return String(s)
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[łøđðæœßþı]/g, (c) => LETTERS[c])
    .replace(/\s+/g, " ")
    .trim();
}

const KIND_ORDER = ["city", "country", "page", "story", "organisation"];

function score(words, entry) {
  const terms = [entry.label, ...(entry.terms ?? [])].map(fold);
  const pieces = terms.flatMap((t) => t.split(/[^\p{L}\p{N}]+/u).filter(Boolean));
  if (words.every((w) => pieces.some((p) => p.startsWith(w)))) return 0;
  if (words.every((w) => terms.some((t) => t.includes(w)))) return 1;
  return -1;
}

/** The entries matching `query`, best first, at most `cap`; none for an empty query. */
export function rank(entries, query, cap = 8) {
  const words = fold(query).split(" ").filter(Boolean);
  if (!words.length) return [];
  return entries
    .map((entry) => ({ entry, s: score(words, entry) }))
    .filter((r) => r.s >= 0)
    .sort(
      (a, b) =>
        a.s - b.s ||
        KIND_ORDER.indexOf(a.entry.kind) - KIND_ORDER.indexOf(b.entry.kind) ||
        a.entry.label.localeCompare(b.entry.label),
    )
    .slice(0, cap)
    .map((r) => r.entry);
}

/** The active index after Down (`dir` 1) or Up (-1) over `count` options, wrapping; -1 for none. */
export function move(active, dir, count) {
  if (!count) return -1;
  if (active < 0) return dir > 0 ? 0 : count - 1;
  return (active + dir + count) % count;
}

/** What a key does to the list: move to an option, pick one, or nothing (null) — e.g. with no match. */
export function keyAction({ active, count }, key) {
  if (!count) return null;
  if (key === "ArrowDown" || key === "ArrowUp") {
    return { type: "move", to: move(active, key === "ArrowDown" ? 1 : -1, count) };
  }
  if (key === "Enter") return { type: "pick", index: active >= 0 ? active : 0 };
  return null;
}

function mount(doc) {
  const box = doc.querySelector(".search");
  const input = box?.querySelector("input");
  const list = box?.querySelector("[role=listbox]");
  const fallback = doc.querySelector(".search-fallback");
  if (!box || !input || !list) return;
  box.hidden = false;
  if (fallback) fallback.hidden = true;

  let index = null;
  let loading = null;
  let shown = [];
  let active = -1;

  const load = () => {
    loading ??= fetch(url("/data/search.json"))
      .then((r) => {
        if (!r.ok) throw new Error(`search.json: ${r.status}`);
        return r.json();
      })
      .then((data) => {
        index = data;
        if (input.value) update();
      })
      .catch((err) => {
        console.error("search index could not be loaded", err);
        box.hidden = true;
        if (fallback) fallback.hidden = false;
      });
    return loading;
  };

  const setActive = (i) => {
    active = i;
    for (const [n, li] of [...list.children].entries()) {
      li.setAttribute("aria-selected", String(n === i));
    }
    if (i >= 0) {
      input.setAttribute("aria-activedescendant", list.children[i].id);
      list.children[i].scrollIntoView?.({ block: "nearest" });
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  };

  const close = () => {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    setActive(-1);
  };

  function update() {
    if (!index) return;
    shown = rank(index, input.value);
    list.replaceChildren();
    if (!input.value.trim()) return close();
    shown.forEach((entry, n) => {
      const li = doc.createElement("li");
      li.id = `site-search-opt-${n}`;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", "false");
      const label = doc.createElement("span");
      label.textContent = entry.label;
      const kind = doc.createElement("span");
      kind.className = "kind";
      kind.textContent = entry.kind;
      li.append(label, kind);
      li.addEventListener("mousedown", (e) => e.preventDefault()); // keep focus in the input
      li.addEventListener("click", () => go(entry));
      list.append(li);
    });
    if (!shown.length) {
      const li = doc.createElement("li");
      li.className = "none";
      li.setAttribute("role", "option"); // a listbox owns only options
      li.setAttribute("aria-disabled", "true");
      li.textContent = "No match";
      list.append(li);
    }
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    setActive(-1);
    announce(shown.length ? `${shown.length} ${shown.length === 1 ? "result" : "results"}` : "No match");
  }

  const go = (entry) => {
    // the index holds paths without the base; the literal lead keeps the rule of base.test.mjs
    globalThis.location.href = url(`/${entry.url.replace(/^\/+/, "")}`);
  };

  input.addEventListener("focus", load, { once: true });
  input.addEventListener("input", () => {
    load().then(update);
    update();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (list.hidden) update();
      const a = keyAction({ active, count: shown.length }, e.key);
      if (!a) return;
      e.preventDefault();
      setActive(a.to);
    } else if (e.key === "Enter") {
      const a = list.hidden ? null : keyAction({ active, count: shown.length }, e.key);
      if (a) {
        e.preventDefault();
        go(shown[a.index]);
      }
    } else if (e.key === "Escape") {
      e.stopPropagation(); // the phone menu stays open (nav.js)
      e.preventDefault(); // a search field would clear itself on the first Escape
      if (!list.hidden) close();
      else input.value = "";
    }
  });
  doc.addEventListener("click", (e) => {
    if (!box.contains(e.target)) close();
  });
  input.addEventListener("blur", () => setTimeout(() => !box.contains(doc.activeElement) && close(), 0));
}

if (globalThis.document) mount(globalThis.document);
