# velometer M15: Deploy dry run (design)

Status: draft for user review, 2026-10-18. M14 ended with "Next: not yet decided". The user asked
for the suggested next milestone, export size plus a deploy dry run, and narrowed it in one round
of questions (§2).

## 1. Purpose

Show, before going live, that the export and `docs/deploy.md` work when real server software
serves them. Both documented routes are covered, and everything runs on this machine. So far only
`deploy-check` has looked at an export, and it reads the files on disk. It has never seen:
- response headers;
- the `.gz` siblings being served;
- a 404 response;
- directory URLs.

The Caddyfile in `docs/deploy.md` has never been run.

Nothing is uploaded and no host is chosen. No stored number, OSM run, classifier version or
database write is involved. No reader-visible change is planned; the only exception is a fix that
the dry run itself shows is needed (§4.3).

## 2. User decisions (2026-10-18)

- **Tier maps are not shrunk.** The 43 tier-map GeoJSON files total 226 MB on disk but 29 MB
  gzipped, and both hosts serve them compressed. The largest file is Helsinki FUA: 20.9 MB raw,
  2.8 MB gzipped. No file comes near the 25 MiB per-file limit. Simplifying at 1 m was measured
  and not chosen: Helsinki FUA's compressed geometry would drop from 2.07 to 1.17 MB. This closes
  the HANDOVER "hosting size follow-up".
- **Dry run:** both routes, locally:
  - Caddy, from the official Docker image, with the Caddyfile from `docs/deploy.md`;
  - Cloudflare Pages, emulated by `wrangler pages dev`, which `npx` fetches at run time. No npm
    dependency enters the repo.
- **site.yaml:** the real values don't exist yet. The dry run exports with `example.org`
  placeholders passed through `--config` from a scratch copy of `config/`, as M14 did. The
  repo's `config/site.yaml` stays all null.
- **Host:** stays host-neutral. Neither route is picked. Basemap tiles stay the recorded
  follow-up (OSM tile usage policy), not part of M15.

## 3. Facts this design rests on (survey of 2026-10-18)

- **Caddy and Docker:** Docker is installed; caddy and wrangler are not. `npx` comes from
  node v24.
- **What the export ships:** `_headers` (CSP with `frame-ancestors 'none'`, nosniff, a
  Referrer-Policy and cache rules), a `.gz` sibling for each text file of 1 KiB or more, and
  `404.html`.
- **What is already tested:** `tests/test_m14_deploy_doc.py` holds the Caddyfile's `header` lines
  to the same policy as `_headers`. Nothing serves an export through either server.
- **How the render pass serves:** `tools/render_pass.py` always serves the export with
  `python -m http.server`, which sends no CSP header. The pass has therefore only ever met the CSP
  as a meta tag.
- **The maps:** `static/map.js` already draws with Leaflet's canvas renderer.

## 4. Design

### 4.1 `tools/deploy_dryrun.py`

This is a developer tool, like `render_pass.py`; it is not a `velometer` CLI command.

```
uv run python tools/deploy_dryrun.py --site <dir> --server caddy|wrangler [--keep-running]
```

The tool starts the server, probes it, stops it, and prints a report. It exits 1 when any probe
fails.

**Servers.** Both bind to `127.0.0.1` on a free port, and both are pinned to an exact version at
least two weeks old. The versions are named in the tool and in `docs/deploy.md`.
- **caddy:**
  - It runs `docker run --rm` with the `caddy:<version>` image.
  - The export is mounted read-only at `/srv/velometer`.
  - The Caddyfile is the fenced block under "Hetzner Cloud with Caddy" in `docs/deploy.md`,
    extracted at run time. Only its site address `velometer.<domain>` is replaced, with
    `http://127.0.0.1:<port>` (so no automatic HTTPS).
  - If the block cannot be found, or the address is missing, the tool fails rather than falling
    back to a Caddyfile of its own.
  - The container is removed on exit, Ctrl-C included.
- **wrangler:** `npx --yes wrangler@<version> pages dev <dir> --ip 127.0.0.1 --port <port>`. The
  tool kills the whole process group on exit.

**Probes.** Each is a pure function from a response, or a pair of responses, to a list of
problems, so it can be tested without a server.
1. **Headers:** every header that `_headers` sets for a path matches on:
   - `/` and the Berlin city page;
   - a `/de/` page;
   - `/data/series.json`;
   - one tier-map GeoJSON;
   - `/static/app.css`.

   The expected values are read from the export's own `_headers`; the probe has no copy of the
   policy.
2. **404:** `/nope-<random>` answers status 404, its body is `404.html`, and it carries the
   headers from (1).
3. **Compression:** a request with `Accept-Encoding: gzip` for a file that has a `.gz` sibling
   must decode to the original bytes.
   - Caddy: the response must be `Content-Encoding: gzip`.
   - wrangler: compression is the host's business, so only byte equality is required.
4. **Directory URLs:** the Berlin city page, in the form the exported pages link it, serves
   `city/berlin/index.html`. The other form, with or without the trailing slash, ends at the same
   page too, either by a redirect within the site or by direct service.
5. **Content types:**
   - `.html` → `text/html`;
   - `.json` → `application/json`;
   - `.geojson` → `application/geo+json` or `application/json`;
   - `.csv` → `text/csv`;
   - `.css` → `text/css`;
   - `.js` → a JavaScript type.

   Each may carry a charset parameter.
6. **Base and links:** each `href` and `src` on `/` that points within the site answers 2xx.

The report lists each problem with the path, the expected value and the value found.

### 4.2 Render pass through a running server

`tools/render_pass.py` gains `--url <origin>`. With it, the pass audits a server that is already
running instead of starting `http.server`. Without it, behaviour is unchanged.
- `--url` and `--site` are both still given: `--site` is where the pass reads the page list.
- `deploy_dryrun.py --keep-running` prints the origin and waits, so the render pass can run
  against it.

The pass runs against both servers with `--pages types --interact --flip`, both themes and both
editions. Through these servers the browser meets the CSP as a header, and the pass's existing CSP
and console checks apply to it.

### 4.3 Fixing what the dry run finds

If a probe or the render pass fails, the fix goes where the fault is:
- the Caddyfile or the route's text in `docs/deploy.md`;
- `_headers`, in `app/export.py`;
- an export file.

Each fix gets a failing test first, in `test_m14_deploy_doc.py`, `test_m14_deploy_check.py` or the
export tests. A fix that would change a reader-visible page stops for the user before it lands.
Each fix and its reason is recorded in `docs/superpowers/rulings-m15.md`.

### 4.4 Tests

- **Default gate (no network, no Docker):**
  - every probe, against hand-made responses. Correct input passes, and each kind of break fails:
    a missing header, a wrong CSP value, a 200 for the 404, a gzip body that decodes to other
    bytes, a wrong content type, a broken link. Each is red-proofed by breaking the rule.
  - extraction of the Caddyfile from `docs/deploy.md`: it finds the block, replaces only the site
    address, and fails on a document without the block or without the address.
  - `render_pass --url` does not start `http.server`. This is tested by stubbing the server
    starter.
- **Slow (`@pytest.mark.slow`, deselected by default):**
  - one end-to-end run per server against a small fixture export built by the existing export
    tests' helper;
  - each run skips with a reason when Docker or `npx` is missing.

### 4.5 Records

- **Evidence:** `docs/review/m15-dryrun.md` records, for each server:
  - its version, the command and the date;
  - the probe report and the render-pass result;
  - every fix made.
- **`docs/deploy.md`:**
  - "Nothing here has been run" becomes "tested locally with Caddy <v> and wrangler <v> on
    <date>; never on a real host".
  - It gains a short "Dry run" section with the commands.
- **`HANDOVER.md`:** a new M15 paragraph. The "hosting size follow-up" closes with the measured
  figures. The §8 commands list gains `tools/deploy_dryrun.py`.
- **`CLAUDE.md`:** the latest delivered milestone becomes M15.

## 5. Out of scope

- Uploading anything, DNS, picking a host, real site.yaml values.
- Simplifying or splitting the tier maps (§2).
- Basemap tiles.
- The remaining accessibility and endonym items.
- §12 Q1.

## 6. Execution order

1. Probes and Caddyfile extraction, with their unit tests.
2. `deploy_dryrun.py` with both servers, and its slow tests.
3. `render_pass.py --url`.
4. The live dry run, on both servers, against a `--public` export of the head with placeholder
   values. Fixes per §4.3.
5. Records (§4.5).
6. Final whole-branch review.

Work goes on a branch, `m15`, merged into main locally only. There is no push.

## 7. Accept

- The gate is green, including the node tests, and the six checks exit 0.
- `velometer.sqlite` is unchanged (md5).
- `deploy_dryrun.py` exits 0 on a `--public` export of the head for both `--server caddy` and
  `--server wrangler`.
- `render_pass.py --url --pages types --interact --flip` exits 0 against both servers, in both
  themes, at 1280/390/320, in both editions.
- The two slow end-to-end tests pass on this machine.
- `docs/review/m15-dryrun.md` records the versions, reports and fixes.

**Not claimed:**
- that a real Cloudflare Pages project or Hetzner server behaves like these local runs (wrangler
  only emulates Pages, and Caddy runs without TLS here);
- anything about TLS, DNS or HTTP/2.
