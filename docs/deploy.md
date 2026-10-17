# Deploying the static edition

Nothing here has been run. M14 makes the export ready for a static host and checks it with
`velometer app deploy-check`; it deploys nothing. Every command below is for you to run. Replace
`<dir>`, `<domain>` and `<host>` with your own values.

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

Not run in M14. The Caddyfile below is an example and has not been tested on a server.

1. Create the smallest server type in a German location, with Caddy installed.
2. DNS: an A record (and AAAA, if the server has IPv6) for `velometer.<domain>` pointing to the
   server.
3. `/etc/caddy/Caddyfile`:

   ```
   (security_headers) {
       header {
           Content-Security-Policy "default-src 'self'; img-src 'self' data: https://tile.openstreetmap.org; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
           X-Content-Type-Options nosniff
           Referrer-Policy strict-origin-when-cross-origin
           Cache-Control "public, max-age=3600"
       }
   }

   velometer.<domain> {
       root * /srv/velometer
       encode gzip
       import security_headers
       file_server {
           precompressed gzip
       }
       handle_errors {
           import security_headers
           rewrite * /404.html
           file_server
       }
   }
   ```

   The `header` lines must equal the `_headers` file in the export; `deploy-check` checks that
   file, not the Caddyfile, and a test (`tests/test_m14_deploy_doc.py`) holds these lines to the
   same policy. The snippet is imported in `handle_errors` too, so the 404 page carries the
   headers whether or not Caddy keeps the site route's headers on an error response.
   `precompressed gzip` serves the export's `.gz` siblings. This block is for `--base /`.
4. Upload. Dry run first, then without `--dry-run`:

   ```
   rsync -a --delete --dry-run <dir>/ <host>:/srv/velometer/
   rsync -a --delete <dir>/ <host>:/srv/velometer/
   ```

## 3. Datenschutz and Impressum

The Datenschutzerklärung (the Datalab's, linked from the footer) must name:

- the host and its server logs (Cloudflare or Hetzner, including the IP addresses they log);
- `tile.openstreetmap.org`: when a tier map loads, the browser asks the OpenStreetMap Foundation's
  tile server, which receives the visitor's IP address;
- Cloudflare as a US processor, if the Cloudflare Pages route is taken.

The OSM tile usage policy forbids heavy use of `tile.openstreetmap.org`. A site with real traffic
needs its own tiles or a commercial provider; that is a recorded follow-up, not built in M14.
