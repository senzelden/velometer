# velometer M14: Ready to host, plus follow-ups (design)

Status: draft for user review, 2026-10-16. M13 ended with "Next: not yet decided". The user asked
to plan the M13 follow-ups and to think about hosting. They named Hetzner, and a subdomain of their
coming Zählwerk Berlin Datalab.

## 1. Purpose

Make the static edition ready to serve from `velometer.<datalab-domain>`, on any static host,
without deploying it. In the same milestone, close three groups of M13 follow-ups: accessibility,
small fixes, and OCR for the scanned excerpts.

No stored number changes, and no OSM run, classifier version or database write is involved. The
reader-visible changes are:
- the footer link line;
- `lang` attributes;
- table captions;
- hidden link context on Sources;
- the wrapping of downloaded chart titles.

## 2. User decisions (2026-10-16)

- **Host:** keep it host-neutral. M14 produces a folder that any static host serves correctly. It
  documents two routes, Cloudflare Pages and Hetzner Cloud with Caddy, and picks neither. The user
  picks at deploy time, once the Datalab's own hosting is known.
  - Cloudflare Pages can serve one subdomain through a CNAME on the user's current DNS.
  - Cloudflare Workers custom domains would need the whole zone on Cloudflare, so Workers is not a
    documented route.
- **Datalab:** velometer gets its own subdomain and keeps its own look. It links back to the
  Datalab, and its Impressum and Datenschutz links point to the Datalab's pages. Shared branding is
  later work.
- **Going public:** nothing is deployed in M14. There is no server, no DNS change and no upload.
  That answers HANDOVER §12 Q4 for now: not public until a later deploy step.
- **Follow-ups in scope:** the accessibility pass, the small fixes, and OCR for the scanned PDF
  pages.
- **OCR engine:** the Mistral OCR API. It gives the best quality on scanned German pages and
  needs neither an install nor `sudo`. The cost is negligible: 7 pages, cached after the first run.
  The other options were rejected:
  - Docling: several GB of PyTorch for 7 pages;
  - tesseract: needs a system install and is weaker on poor scans.
- **Out:** the Straßburg exonym and full-text search (§6).

## 3. Facts this design rests on (survey of 2026-10-16)

- **Export size:** the M13 export (`data/scratch-m13/final/site`) is 262 MB. 236 MB of it are 43
  tier-map GeoJSON files under `maps/`:
  - the largest is `helsinki_fua.geojson` at 20,932,619 bytes, and `berlin_fua.geojson` is
    19,122,135;
  - gzip -9 takes Berlin to 1,864,172 bytes (10.3×);
  - coordinates already have 5 decimals (about 1 m);
  - each feature's `tags` (OSM tags) are 36 % of the bytes and its geometry 32 %. The tier-map
    popup shows the tags (`map.js`, `tierPopup`), so they stay.
- **`velometer app export`:**
  - it takes `--base` (default `/`) and `--clean`;
  - it renders every page through the app, writes `404.html` and `build.json`, and fails closed on
    any reference it cannot resolve (`scan_references`);
  - the CSP is a `<meta http-equiv>` with `img-src 'self' data: https://tile.openstreetmap.org`;
  - no `Referrer-Policy` is set, so the browser default (`strict-origin-when-cross-origin`) sends
    the tile servers the origin, which the OSM tile usage policy expects.
- **Repo and site:** the repo has no git remote and no CI, and the database is local and
  git-ignored. A deploy is therefore an export on this machine followed by an upload.
- **Footer (`templates/base.html`):** it carries the OSM attribution, mapped km, methodology, the
  full CSV, run and build. There is no Impressum or Datenschutz link.
- **UI strings:** `content/ui/{en,de}.yaml` are plain strings. Original terms in labels (for
  example `figure.scope.cykelsti: cykelsti (kerbed cycle track)`) carry no `lang`, because a UI
  string cannot hold the content mark `<i lang="xx">…</i>` (`narrative.TERM_MARK`).
- **Orca:** the M13 run (`tools/orca_pass.py`, `docs/review/m13-screen-reader.md` R1) heard German
  landmark labels and table names in the English voice. The run's process locale was
  `en_US.UTF-8`, and Chrome ran with `--lang=en-US`.
  - No `de_DE` locale is installed (`locale -a`).
  - `localedef` is available, so a German locale can be built into a scratch directory and used
    through `LOCPATH` without root.
- **OCR:** the 7 excerpts that need OCR are on scanned pages of Berlin's Fortschrittsbericht, in
  German.
  - `content --check --online` reads PDFs with `pdftotext` (M13-l); `pdfinfo` and `pdfseparate`
    from the same poppler tools are installed.
  - `httpx` is already a dependency.
  - Secrets are wired through a tracked `.envrc.example` with `use_pass` lines (the Geofabrik login,
    M3). The real `.envrc` is git-ignored.
- **Downloaded titles:** chart downloads wrap titles by average glyph width
  (`static/js/download.js`, `wrap(text, perChar, room)`). A line of wide glyphs can overrun by a
  few px (rulings-m13, Follow-ups).
- **City names:** `config/cities.yaml` holds each city's own `name` (for example `København`). The
  English edition shows it in places such as the Figures heading, without `lang` (M13 Orca R2).

## 4. Design

### 4.1 Ready to host (host-neutral)

- **Base `/`:** the hosting export uses `--base /`. Nothing changes in the code for this, since
  M9 made the export base-agnostic. What M14 adds is the proof:
  - the full render pass and the type pass run on a `/` export as well as on `/velometer/`;
  - `tools/render_pass.py` already takes `--base`.
- **Precompressed copies:** the export writes a `.gz` sibling (gzip level 9, Python's `gzip`
  module, no new dependency) for each exported text file of at least 1 KiB:
  - text means HTML, CSS, JS, JSON, GeoJSON, CSV and SVG;
  - the `.gz` has the same content and a fixed mtime, so it is reproducible;
  - Caddy serves these through `file_server { precompressed gzip }`, and Cloudflare ignores them
    and compresses on its own;
  - `scan_references` does not treat `.gz` files as pages.
- **Size guard:** no exported file may be 25 MiB (26,214,400 bytes) or larger, which is
  Cloudflare Pages' per-file limit.
  - The export fails with the file's name if one is.
  - The test sets the limit low on a fixture to prove the guard fires.
  - The maps keep their content (§3); no simplification.
- **`_headers`:** the export writes `_headers` at the site root, in the Cloudflare Pages / Netlify
  format. Paths are relative to the base. It sets:
  - `Content-Security-Policy`: the meta policy plus `frame-ancestors 'none'`, which only works as a
    header. The meta tag stays, so a host that ignores `_headers` keeps the policy.
  - `X-Content-Type-Options: nosniff`.
  - `Referrer-Policy: strict-origin-when-cross-origin`, the browser default written down.
  - `Cache-Control`: `public, max-age=3600` everywhere. File names carry no content hash, so nothing
    is marked immutable.
  The reference scan ignores `_headers`.
- **`docs/deploy.md`:** a new guide with three parts.
  - **Cloudflare Pages:** create the project; `wrangler pages deploy <dir>` (noting the Pages
    file-count and file-size limits); add a CNAME `velometer` → `<project>.pages.dev` at the
    current DNS provider.
  - **Hetzner Cloud with Caddy:** the smallest server type in a German location; an A or AAAA
    record; a complete example `Caddyfile`, which:
    - turns `_headers` into `header` directives;
    - uses `precompressed gzip`;
    - sets `handle_errors` to `404.html`.
    Then `rsync -a --delete <dir>/ host:/srv/velometer/`, after a `--dry-run`.
  - **What the Datenschutzerklärung must name:**
    - the host, with its server logs;
    - `tile.openstreetmap.org` (the OSMF receives visitors' IP addresses when a tier map loads);
    - Cloudflare as a US processor, if that route is taken.
  It also notes that the OSM tile usage policy forbids heavy use. A site with real traffic needs
  its own tiles or a commercial provider. That is recorded as a follow-up, not built.
- **`velometer app deploy-check DIR [--base /]`:** a new command that verifies a finished export
  and uploads nothing. Exit 1 lists the problems. It checks:
  - `build.json` and its base;
  - `404.html`;
  - `_headers` and its CSP, against the pages' meta CSP;
  - a `.gz` for every text file of at least 1 KiB, decompressing to the same bytes;
  - no file of 25 MiB or more;
  - `scan_references` clean;
  - for a public export, the site settings of §4.2.
  This is the M14 deploy dry run.

### 4.2 Link to the Datalab

- **`config/site.yaml`** (new, Pydantic-validated). Every value may be null, and all of them are
  in the shipped file:
  ```yaml
  datalab:
    name: null        # e.g. "Zählwerk Berlin Datalab"
    url: null         # https URL of the Datalab
  impressum_url: null # https URL (the Datalab's Impressum)
  privacy_url: null   # https URL (the Datalab's Datenschutzerklärung)
  ```
  URLs must be `https://`.
- **Footer:**
  - When `datalab.name` and `datalab.url` are set, both editions show a new first footer line:
    "Part of {name}" / "Teil von {name}", linked to the Datalab.
  - When `impressum_url` and `privacy_url` are set, the line also carries "Impressum" and "Privacy"
    / "Datenschutz". "Impressum" is not translated: it is a German legal term, marked
    `lang="de"` in the English edition.
  - Unset values leave the line out, so today's local exports look as before.
- **`velometer app export --public`:** refuses to run unless all four values are set. A public
  export without legal links cannot be made by mistake. `build.json` records `"public": true|false`,
  and `deploy-check` reads it.
- **CSP and reference scan:** both unchanged. The links are plain `<a href>` to an external https
  URL, which the scan already allows as non-loaded references.

### 4.3 Accessibility pass

- **Orca under German.** Re-run `tools/orca_pass.py` on the German sample pages with a German
  process locale:
  - `localedef -i de_DE -f UTF-8` into a scratch directory under `data/scratch-m14/`;
  - `LOCPATH` pointing there and `LANG=LC_ALL=de_DE.UTF-8` for Chrome and Orca;
  - Chrome with `--lang=de`.
  The driver gets a `--locale` option, so the run is repeatable. The result goes into
  `docs/review/m14-screen-reader.md`, comparing which utterances took which voice language with the
  M13 run9.
  - If the German labels still come out in the English voice, that is a recorded finding with its
    cause, not a site change.
  - If `localedef` fails, the run stops and the user is asked to run `sudo locale-gen de_DE.UTF-8`.
  The same isolation as M13 applies: a private `dbus-run-session`, headless Chrome, no audio, and a
  private `HOME`. Nothing touches the user's desktop, session bus or speakers.
- **`lang` in UI strings:**
  - A UI string may carry the content mark `<i lang="xx">term</i>`, validated by the same rules as
    content prose (`content --check` malformed marks).
  - `t()` renders the mark as markup in HTML text.
  - It renders plain text, without the mark, wherever text is needed: attribute values
    (`aria-label`, `title`), the `#ui-strings` JS block, CSV headers, downloads and citations.
  - Every original term in `content/ui/{en,de}.yaml` gets the mark, starting with `figure.scope.*`
    and `figure.basis.*` and covering the rest of `docs/review/m13-terms.md` that appears in UI
    strings.
  - A test checks that no UI string contains a term from the M13 term list without its mark.
- **`lang` on data:**
  - The Vienna and Lyon plan titles and Oslo's source get `bracket_lang` (or `name_lang`) where
    their lead and bracket differ in language.
  - Every place a city's own `name` is shown in the English edition carries the city's language. A
    new `lang` per city in `config/cities.yaml` holds it: a BCP 47 tag, `fi` for Helsinki whose
    LAU name is "Helsinki / Helsingfors".
  - A test renders every page of the fixture app and checks that each city name differing from its
    English form sits inside an element with that city's `lang`.
- **Captions:** every data table outside prose (`.prose table` is exempt) gets a `<caption>`, or an
  accessible name through `aria-labelledby` on a visible heading. A test over every exported page
  of the fixture app asserts this.
- **Sources links:** the 15 "source" links get visually hidden context ("source: <source title>"),
  so the accessible name is unique and meets WCAG 2.4.9. The visible text stays "source". A test
  asserts that the link names on the Sources page are unique.

### 4.4 Small fixes

- **Download title wrap:**
  - `download.js` wraps titles (and key labels) by measuring each candidate line with the same text
    measure it uses for the line's font, so a wrapped line never exceeds `room`.
  - A node test uses a title of wide glyphs ("WWWW…" and "ÄÖÜ…"), and a measure stub that charges
    each glyph its real width, then asserts every line ≤ room. The test fails on today's
    average-width wrap.
- **ResourceWarnings:**
  - Fix the unclosed files, connections and clients in the test suite (`sqlite3` connections,
    `TestClient`s and file handles opened without `with`).
  - Add `filterwarnings = ["error::ResourceWarning"]` to the pytest config, so a new one fails the
    gate.
  - That config line is the rule test: it is red-proofed by a deliberately leaky test, run once and
    then removed.
- **HANDOVER §12:** each open question gets its status:
  - answered, with where it was decided (ADR, rulings line, memory note), or still open;
  - verified against the record, not from memory;
  - Q4 records the M14 decision, and Q5 records the Geofabrik credentials set up in M3.
  Answered questions move to a short "Answered" list, so §12 lists only what is open.

### 4.5 OCR for scanned PDF pages (Mistral OCR)

- **When it applies:** in `content --check --online`, when `pdftotext` yields no text for a PDF
  page (empty after whitespace is stripped), that page is OCRed. Pages with a text layer never go
  to the API.
- **The call:**
  - `POST https://api.mistral.ai/v1/ocr` with `model: mistral-ocr-latest`;
  - the document is sent as a base64 `data:application/pdf` URL of only the scanned pages, cut out
    with `pdfseparate` and joined back with `pdfunite` (poppler), so only those pages are billed;
  - the response's per-page `markdown` is the OCR text;
  - `httpx` is used, with the check's existing 60 s timeout and one retry on a timeout or 5xx;
  - the request and response shapes are checked against Mistral's current API documentation when
    the task is implemented, not taken from this spec.
- **Matching:** the OCR text is reduced to plain text: Markdown marks (`#`, `*`, `_`, `|`, table
  rules) and image references are dropped. It is then compared the way M13-l compares
  `pdftotext -raw` text (all whitespace removed), after joining a line-end hyphen that a newline
  follows.
- **Cache:** the OCR text is stored per source document and page under the git-ignored
  `data/cache/ocr/`, keyed by the PDF's SHA-256 and the page number, together with the model name
  the response reports.
  - A later run reads the cache and does not call the API.
  - A changed PDF has a new hash and is OCRed again.
- **Key:** `MISTRAL_API_KEY`, through direnv and `pass`. It reuses the user's existing general
  entry `api/mistral`, the one `denckring-bench` already reads.
  - `.envrc.example` gets `use_pass_optional MISTRAL_API_KEY api/mistral`. The global direnv helper
    makes a missing entry a warning, which fits an optional key.
  - The user adds the same line to their git-ignored `.envrc`; no new `pass` entry is needed.
  - No key value is written into any file, log or report.
  - The key is never printed. An error from the API is reported with its status and message only.
- **No key:** the check prints one note, `OCR not available: set MISTRAL_API_KEY
  (use_pass_optional MISTRAL_API_KEY api/mistral in .envrc)`, and treats those pages as before. It never fails because OCR is
  unavailable. With a key but an API error, the note names the status, and the pages count as
  unread, as today.
- **Cost guard:** a run OCRs at most 20 pages; the rest are reported as skipped. That is far above
  the 7 needed, and keeps a source with a large scanned PDF from running up a bill.
- **Tests never call the API:**
  - an `httpx` mock transport returns a recorded-shape response, and the tests assert that only
    the empty pages are sent and that the excerpt is found;
  - a cache hit makes no request;
  - a missing key gives the note;
  - an API error is reported without the key;
  - the 20-page cap holds.
  No slow test calls the real API.
- **The one real call** is the acceptance run of `content --check --online` (§8), on the 7 pages.
  The user chose Mistral OCR knowing it is a paid API (2026-10-16).
- **Acceptance:** the expected result is about 7 missed excerpts instead of 14. Whatever the run
  gives is recorded.

## 5. User review stop

None for prose: M14 adds no narrative text. The two new footer strings and the hidden link texts
are UI strings, reviewed in the final whole-branch review.

The user is asked:
- once, at the start of the OCR task, to add `use_pass_optional MISTRAL_API_KEY api/mistral` to
  their `.envrc` and run `direnv allow` (§4.5);
- for `sudo locale-gen`, only if `localedef` fails (§4.3).

## 6. Out of scope

- Deploying: no server, no DNS change, no upload, no Cloudflare or Hetzner account step.
- Shared Datalab branding.
- Own map tiles.
- Simplifying or dropping GeoJSON content.
- The Straßburg exonym.
- Full-text search (M11-9).

## 7. Execution order

1. `config/site.yaml`, footer, `--public`.
2. Export: `.gz`, size guard, `_headers`.
3. `deploy-check`.
4. `docs/deploy.md`.
5. UI-string `lang` marks.
6. `lang` on data (cities, plan titles, Oslo).
7. Captions.
8. Sources link context.
9. Download title wrap.
10. ResourceWarnings.
11. OCR fallback.
12. HANDOVER §12.
13. Orca under German.
14. Final verification: both exports, render passes, `deploy-check`, online check; then the docs
    (HANDOVER M14 paragraph, rulings-m14, CLAUDE.md).

## 8. Accept

- The gate is green, including the node tests; the six checks exit 0; `velometer.sqlite` is
  unchanged.
- Two exports, at `--base /velometer/` and at `--base /` (the latter with test values in a scratch
  copy of `site.yaml` and `--public`), each:
  - pass the full render pass (`--pages all`, both themes, 1280/390/320, both editions) and
    `--pages types --interact --keyboard --flip`, exit 0;
  - pass `velometer app deploy-check`, exit 0.
- `content --check --online` is run with the Mistral key (the one real API call, 7 pages), and the
  remaining misses are recorded.
- `docs/review/m14-screen-reader.md` records the German-locale Orca run.
- Screenshots were checked in both themes, at 1280 and 390, in both editions:
  - the footer with the Datalab line;
  - the Sources links;
  - a Figures table with captions;
  - a downloaded chart with a long title.
- Not claimed:
  - anything about a real host's behaviour (nothing is deployed);
  - that the Caddyfile was run (only shown);
  - that `_headers` was read by Cloudflare.
