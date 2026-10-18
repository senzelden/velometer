# M15 deploy dry run

Run on 2026-10-18 on the development machine (Linux). The export was served locally by the server
software of both hosting routes, and `tools/deploy_dryrun.py` and `tools/render_pass.py --url`
audited it over HTTP. Nothing was deployed.

## Setup

The export was made at commit `cde2aa0` with placeholder site values in a scratch copy of
`config/` (Datalab "Zählwerk Berlin Datalab", `https://datalab.example.org/`, with an Impressum and
a Datenschutz page). The repo's `config/site.yaml` stays null.

```
uv run velometer app export --out data/scratch-m15/site --base / --clean --public --config data/scratch-m15/cfg
uv run velometer app deploy-check data/scratch-m15/site --public
```

The export has 793 files and 303.1 MB (build `cde2aa0`, base `/`) and took 32.0 s. `deploy-check
--public` reported "ok: 793 files, 303.1 MB, base /, public True".

## Caddy 2.11.4 (Hetzner route)

- Server: `caddy:2.11.4-alpine` in Docker, plain HTTP on 127.0.0.1, with the Caddyfile taken from
  `docs/deploy.md` §2. `--server caddy` uses Docker host networking, so it runs on Linux only.
- Commands:

  ```
  uv run python tools/deploy_dryrun.py --site data/scratch-m15/site --server caddy
  uv run python tools/deploy_dryrun.py --site data/scratch-m15/site --server caddy --keep-running
  uv run --group dev python tools/render_pass.py --site data/scratch-m15/site --base / \
      --url <origin> --out tools/out/m15-caddy --pages types --interact --flip
  ```

- Probe, last line: `75 checks, 0 problems`.
- Render pass (both themes, 1280/390/320 px, both editions, types, `--interact`, `--flip`):
  `171 visits, 0 with findings`.

## wrangler 4.147.0 (Cloudflare Pages route)

- Server: `npx wrangler@4.147.0 pages dev`, which emulates Pages and reads `_headers`.
- Commands: the same three, with `--server wrangler` and `--out tools/out/m15-wrangler`.
- Probe, last line: `75 checks, 0 problems`.
- Render pass: `171 visits, 0 with findings`.

## Findings of the first runs

1. **Caddy 2.10.2 answered 206 for files with a `.gz` sibling.** First run (`caddy:2.10.2-alpine`):
   75 checks, 8 problems, all "status 206, expected 200", on `/`, `/city/berlin`, `/de`,
   `/data/series.json`, `/maps/amsterdam_fua.geojson`, `/static/app.css`, `/data/all.csv` and
   `/static/changemap.js`. A minimal Caddyfile (`file_server { precompressed gzip }`) with
   `Accept-Encoding: gzip` and no Range header showed it is a regression in that Caddy release,
   not a fault in the documented Caddyfile:

   | Caddy | Answer |
   |---|---|
   | 2.10.2 | 206, `Content-Range: bytes 0-47/48` |
   | 2.10.0, 2.9.1 | 200, gzip |
   | 2.11.4, 2.11.7 | 200, gzip; a real `Range` request gets 206 |

   Fix `44e9736`: the tool pins `caddy:2.11.4-alpine`, `docs/deploy.md` §2 says to use Caddy 2.11.4
   or later, and a test holds the doc to the tool's pin.
2. **The 404 probe expected a Cache-Control that wrangler does not send.** First run (wrangler
   4.147.0): 75 checks, 1 problem, `/nope-…: header cache-control is 'no-store', expected 'public,
   max-age=3600'`. Cloudflare's `_headers` documentation (developers.cloudflare.com/pages/
   configuration/headers/, read 2026-10-18) applies the rules to "static asset responses" and says
   nothing about 404s, and `wrangler pages dev` sends `no-store` on its 404. Fix `fcf2e6b`: the 404
   probe accepts any Cache-Control (`NOT_FOUND_EXEMPT`); CSP, nosniff and Referrer-Policy stay
   strict.

After both fixes the probes and render passes above are the second runs.

## Other results

- The two slow end-to-end tests (`pytest -m slow tests/test_m15_dryrun_live.py`) passed.
- No container and no wrangler or workerd process was left after any run.
- Tier maps: 226 MB raw, 29 MB gzipped; the largest, Helsinki FUA, is 20.9 MB raw and 2.8 MB
  gzipped. They are not shrunk (rulings-m15).

## Not claimed

- That a real Cloudflare Pages project or Hetzner server behaves like these local runs. wrangler
  only emulates Pages, and Caddy ran without TLS on 127.0.0.1.
- Anything about TLS, DNS or HTTP/2.
- The 404 headers that real Cloudflare Pages sends.
- That `--network host` works outside Linux (Docker Desktop on macOS or Windows).
