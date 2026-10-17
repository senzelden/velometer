# M14 rulings

M14 makes velometer ready to host and closes a batch of follow-ups. Nothing was deployed.
- Spec: `docs/superpowers/specs/2026-10-16-velometer-m14-design.md`.
- Plan: `docs/superpowers/plans/2026-10-16-velometer-m14.md`.
- SDD ledger, briefs, reports and reviews: `.superpowers/sdd/2026-10-16-velometer-m14/` (git-ignored
  scratch).

The committed evidence:
- `docs/deploy.md`, the host-neutral deploy guide;
- `docs/review/m14-screen-reader.md`, Orca under a German locale.

Each ruling reads: Ruling — why — cost.

## User rulings

Before the spec (2026-10-16):
- **Host:** host-neutral. Cloudflare Pages and Hetzner + Caddy are both documented; none is picked.
- **Address:** velometer gets its own subdomain of the coming Zählwerk Berlin Datalab, with a link
  back. Impressum and Datenschutz link to the Datalab's pages.
- **Deployment:** nothing is deployed in M14. There is no server, no DNS change and no upload.
- **Follow-ups in scope:** an accessibility pass, the small fixes, and OCR for scanned PDFs.
- **OCR engine:** the Mistral OCR API (`mistral-ocr-latest`). The key is the existing pass entry
  `api/mistral`, loaded by direnv as `MISTRAL_API_KEY` (`use_pass_optional`). Tests never call it.
- "No rm rf commands." No recursive force delete was run, and the SDD workspace stays in place.

## Plan and process

- The T7 fallback test pins today's output as literal expected lines. The old function cannot be
  called once it has been replaced — the cost is a test that encodes current numbers, for the
  fallback path only.
- Task 10 (docs only, 15 lines) was reviewed by the controller directly, with every citation
  spot-checked. A reviewer seat adds nothing to a citation check — the cost is a missed wording
  issue, which the final review would catch.
- The final review's two Important findings, eight of its nine Minors and five deferred task minors
  were fixed in one wave. The ninth Minor, M9, went into the docs commit. The fixes were cheap, and
  two of them (M5 and M8) affect real users — the cost is a larger wave.
- Task 12 also ran the city-name and table checkers over both real exports, because the fixtures
  had missed both Important findings — the cost is a scratch script
  (`data/scratch-m14/final/real_checks.py`, not committed).

## Hosting (T1–T3)

- **Datalab settings:** a Datalab block whose name and url are both null counts as unset. The
  shipped `config/site.yaml` lists every key as null — no cost.
- **Header CSP:** the `_headers` CSP is `csp_meta(CSP)` plus `frame-ancestors 'none'`. The meta
  policy cannot carry `frame-ancestors`, and the header must — the cost is one string join.
- **`.gz` reproducibility:** checked only where the sources are byte-equal. The CSV files and
  `build.json` embed the build time — the cost is a narrower test.
- **Cloudflare limits:** 25 MiB per file and 20,000 files (Free plan), fetched 2026-10-16. The
  Caddyfile is documented and was never run — the cost is an untested Caddy route; a test ties
  its header lines to `headers_text`.
- **`deploy-check`:** it judges the export (its `build.json` and page footers), not today's
  `site.yaml`, and `--public` fails a non-public export (final review M5). It skips HTML fragments
  without a `<footer>` and always checks `index.html` — the cost is that a page which lost its whole
  footer is not flagged.

## Accessibility (T4–T6, T11)

- **Original terms:** the mark is required wherever the term is HTML text. Plain text is used only
  in `<title>`, attributes, CSV, Markdown sources, JS strings and citations, which spec §4.3 lists
  — the cost is a `label_html` variant.
- **City names:**
  - English pages mark the city's own name where it differs from the English form (København,
    Wien, Warszawa, Kraków, Praha). German pages show the German form, which needs no mark.
  - Barcelona's language is `ca` and Oslo's is `nb`.
  - Citations stay plain.
- **JS-drawn labels:** chart labels and search options built by JS leave endonyms unmarked. The JS
  has no city language data — the cost is Orca reading those labels in the page voice (follow-up).
- **Prose:** narrative prose, NUTS3 labels and organisation names containing a city
  (Mobilitätsagentur Wien, IPR Praha) are not marked. They are outside the rule for a city's
  configured name. On the real export, 0 standalone city names are unmarked; the 66 remaining hits
  are all of these kinds (follow-up).
- **Markdown marks:** the `md` filter lets through exactly `<span lang="TAG">text</span>` and
  `<i lang="TAG">text</i>`, with TAG a valid language tag and plain text inside, and escapes
  everything else. Post-processing table cells would miss the methodology's bullets and prose —
  the cost is that a hand-edited doc can carry a mark nobody reviewed, which is harmless. The final
  re-review tried about 38 crafted inputs; none got through.
- **Table names:** data tables are named with `aria-labelledby` on their existing headings, not
  with captions — no visual change. 19 older tests that matched literal tags were loosened.
- **Datalab name:** its `lang` goes on a `<span>` inside the footer link, so "Part of" keeps the
  page voice — no cost found.
- **Orca:** Orca under `de_DE.UTF-8` spoke all seven M13 labels in the German voice, where the
  control run spoke six in English. Each condition ran once. Orca's own role words ("link",
  "heading") stayed English in both runs, and a reader with an English locale was not tested.

## Small fixes (T7, T8)

- Download key chips use the page's key-font measure only when the page supplies one; otherwise
  they use the chip average as before.
- **Per-test GC is opt-in** (`VELOMETER_GC_EACH_TEST=1`). The default run still fails on any leak,
  at session end, and naming the test makes a run 26.6 min instead of 10.7 — the cost is that a
  leak is reported without its test name until someone re-runs with the variable (CLAUDE.md).

## OCR (T9)

- Mistral's own docs do not show the base64 `data:application/pdf` form of `document_url`. Only
  third-party guides do, so the Task 12 live call settles it.
- OCR text is mapped to pages by position in the response, because the docs contradict each other
  on page indexing.
- The cap is 20 pages actually sent per run, across all PDFs (final review M1). Cached pages do not
  count. Raised to 100 on 2026-10-17 at the user's choice, after the live run spent 20 on the
  first PDF and left 52 empty pages in 7 PDFs: one run now reaches all 72.
- `MISTRAL_API_KEY` is removed at `pytest_configure` and again by an autouse fixture, so no test or
  fixture of any scope can make a billed call. A subprocess guard test proves it.
- A short answer (fewer pages than sent) is not cached. The temporary cut PDFs live in a `.cut-*`
  directory inside the cache directory and are removed on every path.

## Found in acceptance

- **Empty city links on `/plans`:** the render pass found the plans table's city links empty in
  both editions (axe link-name). Task 5 had passed the table's row dicts to `city_name`, which reads
  by attribute.
  - Fixed in `6cf381a`: the rows go through `city_row_name`, `city_name` refuses a dict, and a
    whole-site test asserts every link has a name.
  - No earlier test read the link text.

## Acceptance

At head `7e22088`, with the live OCR run on 2026-10-17:
- **Tests:** the gate is green (3014 pytest, 311 node), the six checks exit 0, and `velometer.sqlite`
  is unchanged (md5 `d9fd513e…`).
- **Exports:** `site-velometer` (`--base /velometer/`) and `site-root` (`--base / --public`, with
  placeholder site values) have 793 files each, about 303 MB. Both pass `deploy-check`.
  `site-velometer` checked with `--public` exits 1, as it should.
- **Render passes:** the full pass (1230 visits) and the types pass (173 visits) exit 0 with 0
  findings on both exports. The first round found the `/plans` links (see above).
- **Real-export checkers:** 0 unnamed data tables in 248 HTML files, and 0 standalone city names
  unmarked on 103 English pages.
- **Live OCR:**
  - Mistral accepted the base64 `data:application/pdf` form.
  - 20 pages of the Fortschrittsbericht 2025 were sent and 20 cache files written, all with text.
  - The online misses went from 14 to 11. Three of that report's six were found. Still missing:
    its other three (not checked whether they sit on skipped pages), the one in the
    Fortschrittsbericht 2023 (not sent), and the seven PDF-layout cases from M13.
  - The cap was spent on the first scanned PDF, so 52 empty pages in 7 PDFs were skipped. A later
    run sends the next 20 and leaves the cached pages alone.
- **Screenshots looked at:**
  - The footer, at 1280 in both themes and both editions. The 390-wide full-page shots end before
    the footer; the HTML is the same.
  - A downloaded PNG and SVG. Their title is short, so a long title was not seen wrapping.
- **Follow-ups:**
  - Spend the OCR cap first on PDFs that have a missing excerpt.
  - Mark endonyms in JS-drawn labels.
  - Find out why Orca's role words stay English.
  - Repo name and location (§12 Q1).
