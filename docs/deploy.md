# Deploying the static edition

M14 made the export ready for a static host; M15 served it locally with both routes' server
software (Caddy 2.11.4 in Docker and `wrangler pages dev` 4.147.0, 2026-10-18;
`docs/review/m15-dryrun.md`). Nothing has been deployed to a real host. Every command below is
for you to run. Replace `<dir>`, `<domain>` and `<host>` with your own values.

## 0. Make and check the export

```
uv run velometer app export --out <dir> --base / --clean --public
uv run velometer app deploy-check <dir> --public
```

`export --public` refuses to run unless `config/site.yaml` names the Datalab, its Impressum and
its privacy page, and records those four values in `build.json`. `deploy-check` uploads nothing.
It checks `build.json` and its base, `404.html`, the `_headers` file against the pages' meta
policy, a `.gz` that matches each text file of 1 KiB or more, that no file is 25 MiB or more, that
every reference resolves, and, for a public export, that every page's footer links the Datalab,
Impressum and privacy page that `build.json` records. It judges the export, not today's
`config/site.yaml`. `deploy-check --public` also fails on an export made without `--public`, which
would go live without an Impressum. It exits 1 and lists the problems otherwise. Run it again
after any hand edit.

## 0a. Local dry run

Before you upload, serve the export with the same server software the host runs and probe it over
HTTP (status, compression, security headers, 404 page):

```
uv run python tools/deploy_dryrun.py --site <dir> --server caddy --datalab <datalab-dir> \
    --tiles <file.pmtiles> [--lock <password> | --lock-default] [--debug-log]
uv run python tools/deploy_dryrun.py --site <dir> --server wrangler
```

`--server caddy` runs Caddy 2.11.4 in Docker with `deploy/Caddyfile`, the production file (§2),
serving both sites: the Datalab build (`velometer datalab build`) at `localhost`, velometer at
`velometer.localhost`, the redirect at `www.localhost`, all on one port of 127.0.0.1, without TLS.
The probes name the site in the Host header; a browser reaches the names directly (Chrome
resolves `*.localhost` to loopback). It also asks the tile file for a byte range (206) and a
malformed one (416), checks HSTS and the `www` redirect, and afterwards reads the access logs and
Caddy's own output: neither may hold the probes' address (`127.0.0.77`), a forged
`X-Forwarded-For` (`203.0.113.7`), a cookie, the password or its Authorization header, and each
access log must show both addresses masked to /24. `--lock <password>` locks both sites as the
server is locked until go-live (the bcrypt hash is made by `caddy hash-password` in the container
at run time and kept in a temporary file); every path of every host must then answer 401 without
the password. `--lock-default` serves the lock the server comes up with (`respond "locked" 401`),
which no password opens. `--debug-log` raises Caddy's own log to DEBUG so that its error entries
(404, 401) are written and checked too.

`--server caddy` uses Docker host networking and so runs on Linux only. With `--network host`, the
Caddy container also binds Caddy's admin endpoint on 127.0.0.1:2019, so a Caddy already running on
the host (or a second dry run left up with `--keep-running`) makes the run fail after its 120 s
wait; stop the other one first. `--server wrangler` runs `npx wrangler pages dev` for the velometer
export alone. The tool ends with `N checks, M problems` and exits 1 on any problem. With
`--keep-running` it leaves the server up and prints its origins, so that `tools/render_pass.py
--url <origin>` can audit the pages through it (add `--auth preview:<password>` when locked, and
`--lang de` for the Datalab).

## 1. Cloudflare Pages

1. Export with `--base /` (the site gets its own host name) and run `deploy-check`, as above.
2. Upload, from a machine where you are logged in to Cloudflare (no npm dependency enters this
   repository; `npx` fetches wrangler on the fly):

   ```
   npx wrangler pages deploy <dir> --project-name velometer
   ```

   Pages reads `_headers` from the site root: the Content-Security-Policy (with
   `frame-ancestors 'none'`, which only works as a header), `X-Content-Type-Options`,
   `Referrer-Policy` and `Cache-Control`. It compresses responses itself and ignores the `.gz`
   files, which count as files.
3. Custom domain, in this order (a CNAME to Pages for a domain the project does not know yet
   answers with an error):
   1. add `velometer.<domain>` as a custom domain in the Pages project;
   2. then, at the current DNS provider, add a CNAME `velometer` pointing to
      `<project>.pages.dev`, the project's host name as wrangler prints it after the first
      deploy (it carries a suffix when `velometer` is taken).
4. Limits, from Cloudflare's Pages limits page
   (https://developers.cloudflare.com/pages/platform/limits/, read 2026-10-16): 25 MiB per file;
   20,000 files per site on the Free plan. Check both against the current page before a deploy:
   limits change. `deploy-check` prints the file count (the `.gz` files are included) and refuses
   a file of 25 MiB or more.

## 2. Hetzner Cloud with Caddy

Tested locally (M15, M16: Caddy 2.11.4, Docker, plain HTTP on 127.0.0.1); not yet on a server with
TLS.

1. Create the smallest server type in a German location, with Caddy installed.
   Use Caddy 2.11.4 or later: Caddy 2.10.2 answers a precompressed (`.gz`) file with
   `206 Partial Content` even when the browser asked for no range (found by the M15 dry run,
   `docs/review/m15-dryrun.md`).
2. DNS: A and AAAA records for `<domain>`, `www.<domain>` and `velometer.<domain>` pointing to the
   server.
3. `/etc/caddy/Caddyfile` is `deploy/Caddyfile`, unchanged. It reads two environment variables
   (`deploy/caddy.env.example`): `DOMAIN`, the apex, and `SITE_ROOT`, default `/srv`. It serves:
   - the Datalab at `<domain>` from `<SITE_ROOT>/datalab/current`;
   - velometer at `velometer.<domain>` from `<SITE_ROOT>/velometer/current`, and the maps'
     basemap at `/tiles/` from `<SITE_ROOT>/tiles/`;
   - `www.<domain>`, a 308 redirect to `https://<domain>` with the path kept.

   Each site's headers equal its export's `_headers` file, plus `Strict-Transport-Security:
   max-age=31536000` (one year, without `includeSubDomains` or `preload`); a test
   (`tests/test_m16_caddyfile.py`) holds both to the exports' policies. The headers are imported in
   `handle_errors` too, so the 404 page carries them. `handle_errors 404` answers only a 404 with
   the site's `404.html`: any other error (the lock's 401) keeps its empty body. `precompressed
   gzip` serves the exports' `.gz` siblings. The error handler sets its own `root`: an error under
   `/tiles/` would otherwise look for the 404 page in the tiles' directory and send an empty body.

   The basemap (`tiles/velometer.pmtiles`, cut by `tools/tiles.py`, about 900 MB) is not part of
   the export: it lives in `<SITE_ROOT>/tiles/` and `handle_path` serves it with byte ranges
   (Caddy's file server answers `Range`; `encode` leaves its binary type alone; it has no `.gz`
   sibling and its route has no `precompressed`). Without it the maps draw without a background.
   Replace the tile file atomically: copy the new one to a temporary name in the same directory,
   then rename it into place, so a reader's open map never fetches a half-written file
   (protomaps-leaflet logs every failed tile to the console):

   ```sh
   scp velometer.pmtiles server:/srv/tiles/velometer.pmtiles.new
   ssh server mv /srv/tiles/velometer.pmtiles.new /srv/tiles/velometer.pmtiles
   ```

   **Lock.** Every site block imports `/etc/caddy/lock.caddy` first. Until go-live it holds either
   `respond "locked" 401` (as the server comes up) or a `basic_auth` block with the preview
   password's bcrypt hash; after go-live it is empty. The hash is made on the server with
   `caddy hash-password` and never enters the repository. The Caddyfile's global `order` lines run
   the lock before `redir` and the tiles route, which by Caddy's default order would come first and
   answer without the password; the dry run checks both forms on every host.

   **Logs.** Each site writes a JSON access log, `/var/log/caddy/datalab.log` and
   `velometer.log`, with the client address masked to IPv4 /24 and IPv6 /48 before it reaches the
   disk (`remote_ip`, `client_ip`, `X-Forwarded-For`), the client port, `Cookie`,
   `Authorization`, `Forwarded` and `X-Real-Ip` dropped. The logs roll at 00:00 UTC, and 14
   rolled files, at most 14 days old, are kept (`roll_at 00:00`, `roll_keep 14`,
   `roll_keep_for 336h`); a rolled file is gzipped, named like
   `velometer-2026-10-21T00-00-00.000-time.log.gz` (seen with Caddy 2.11.4). Caddy's own log (stderr, so journald) masks the same fields, writes no
   access lines, and drops the `http.stdlib` logger, whose messages name the client in their text
   (`TLS handshake error from <ip>:<port>`, at DEBUG) where no field filter reaches.
4. Upload. Dry run first, then without `--dry-run`:

   ```
   rsync -a --delete --dry-run <dir>/ <host>:/srv/velometer/current/
   rsync -a --delete <dir>/ <host>:/srv/velometer/current/
   ```

   The Datalab build goes to `/srv/datalab/current/` the same way.

## 3. Datenschutz and Impressum

The Datenschutzerklärung (the Datalab's, linked from the footer) must name:

- the host and its server logs (Cloudflare or Hetzner, including the IP addresses they log);
- Cloudflare as a US processor, if the Cloudflare Pages route is taken.

Since M16 no page loads anything from another host: the map background is the self-hosted
Protomaps extract, so the OSM tile usage policy no longer applies.
