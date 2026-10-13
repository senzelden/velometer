// Number and month formats of the page's language (M12 spec decision 5): en-GB or de-DE, from
// <html lang>. The mirror of velometer.i18n (number, signed, percent, month_year): German has
// `1.639,8`, `−3,2` (U+2212) and `12,3 %` (a narrow no-break space). Month names come from the
// strings block (strings.js), which velometer.i18n writes from its own tables.
import { lang } from "./base.js";
import { t } from "./strings.js";

const MINUS = "−";
const NNBSP = " ";

/** The page's locale: "de-DE" on a German page, else "en-GB" (also without a document). */
export const locale = (doc = globalThis.document) => (lang(doc) === "de" ? "de-DE" : "en-GB");

/** `v` with Intl `options` in the page's locale; German writes its minus as U+2212. */
export function format(v, options = {}, doc = globalThis.document) {
  const loc = locale(doc);
  const text = v.toLocaleString(loc, options);
  return loc === "de-DE" ? text.replace(/^-/, MINUS) : text;
}

/** `v` with exactly `decimals` decimals, grouped: "1,639.8" / "1.639,8". */
export const number = (v, decimals = 1, doc = globalThis.document) =>
  format(v, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }, doc);

/** `v` with its sign always written: "+3.2" / "−3,2"; a value that rounds to zero has none. */
export function signed(v, decimals = 1, doc = globalThis.document) {
  const n = number(Math.abs(v), decimals, doc);
  if (!/[1-9]/.test(n)) return n;
  return (v < 0 ? (locale(doc) === "de-DE" ? MINUS : "-") : "+") + n;
}

/** A percentage: "12.3%" / "12,3 %". */
export const percent = (v, decimals = 1, doc = globalThis.document) =>
  number(v, decimals, doc) + (locale(doc) === "de-DE" ? `${NNBSP}%` : "%");

/** A large value in thousands, no decimals: "12k" / "12 Tsd.". */
export const compact = (v, doc = globalThis.document) =>
  format(v / 1000, { maximumFractionDigits: 0 }, doc) + t("js.fmt.thousands");

/** A month and its year ("Oct 2026" / "Okt. 2026"; long names with `short` false) of a Date
 * (UTC) or a "YYYY-MM…" string. */
export function monthYear(date, doc = globalThis.document, short = true) {
  const [m, y] = date instanceof Date
    ? [date.getUTCMonth() + 1, date.getUTCFullYear()]
    : [Number(String(date).slice(5, 7)), String(date).slice(0, 4)];
  return `${short ? t(`js.month.short.${m}`) : t(`js.month.long.${m}`)} ${y}`;
}

// a number as the locale writes it: grouped (1.639,8) or not (1639,8), with a sign or none
const SHAPE = {
  "de-DE": /^[+\-−]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$/,
  "en-GB": /^[+\-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$/,
};

/** The machine form of a number written in `loc` ("−1.639,8" -> "-1639.8"), else null: groups
 * removed, a dot decimal, a plain minus. Null for anything that is not wholly a number. */
export function machine(text, loc = "en-GB") {
  const s = String(text ?? "").trim();
  if (!SHAPE[loc]?.test(s)) return null;
  const [group, decimal] = loc === "de-DE" ? [".", ","] : [",", "."];
  return s.replace(/^\+/, "").replace(MINUS, "-").replaceAll(group, "").replace(decimal, ".");
}

/** The inverse of `number` for the locale: a number, or null for anything that is not wholly one. */
export function parse(text, loc = "en-GB") {
  const m = machine(text, loc);
  return m === null ? null : Number(m);
}
