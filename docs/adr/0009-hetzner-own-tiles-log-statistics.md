# 0009 — Hetzner server, own tiles, masked logs and log statistics

- Status: accepted
- Date: 2026-10-28 (decided 2026-10-21; built and deployed behind a password in M16)

## Context

M15 left the host open. On 2026-10-19 the user chose Cloudflare Pages; on 2026-10-21 they moved to
a server of our own, because a site's access logs should not sit with a US company. They also
wanted basic visitor statistics without a consent banner, and no page loading anything from
another host. Until M16 the maps loaded raster tiles from `tile.openstreetmap.org`.

## Decision

- **Host:** one Hetzner Cloud server in Germany (`cx23` at `fsn1`, Debian 13), in a Hetzner
  project of its own, created from this machine through the Hetzner API by `tools/server.py` with
  a token from `pass`. A Hetzner Cloud firewall admits 22, 80, 443 and 443/udp. Hetzner is a
  processor under Art. 28 GDPR; the user concluded the DPA on 2026-10-28.
- **Two sites, one Caddyfile:** the apex `<domain>` serves the Zählwerk Berlin Datalab page,
  `velometer.<domain>` serves velometer, `www.<domain>` redirects to the apex. The domain is
  `zaehlwerk-datalab.de` (INWX; DNS records entered by hand). `deploy/Caddyfile` is the one real
  file. Caddy is pinned to 2.11.4 or later (2.10.2 answers `.gz` siblings with 206). Each site's
  headers equal its export's `_headers`, plus one year of HSTS without `includeSubDomains`.
- **Releases:** each upload goes by rsync into `releases/<build>/`; a marker beside it is written
  only after rsync exits 0, and only then does the `current` symlink switch (an atomic rename).
  Three complete releases are kept; older ones are removed one path at a time after a guard checks
  each lies under `releases/`.
- **Lock until go-live:** every site block imports `/etc/caddy/lock.caddy`. A fresh server answers
  401 to everything; `setup` replaces that with basic auth (the bcrypt hash made on the server, the
  password from `pass`). Locked responses carry `Cache-Control: no-store`. `unlock` empties the
  file, and only after `golive-check` passes.
- **Own basemap:** a Protomaps PMTiles extract (build 20260811, maxzoom 13, 898 MB), cut by
  `tools/tiles.py` with a pinned `pmtiles` CLI and served from `/srv/tiles/` with byte ranges. The
  three maps draw it with a vendored protomaps-leaflet; beyond zoom 13 they overzoom. The CSP no
  longer names `tile.openstreetmap.org`; no page loads anything from another host.
- **Logs:** Caddy writes a JSON access log per site. The client address is masked to IPv4 /24 and
  IPv6 /48 before it reaches the disk; the client port, `Cookie`, `Authorization`,
  `X-Forwarded-For`, `Forwarded` and `X-Real-Ip` are dropped. Logs roll daily and each rolled file
  is deleted when 14 days old (`roll_keep_for 336h`). Legal basis Art. 6(1)(f) GDPR.
- **Statistics:** GoAccess builds a report from the last 14 days of logs, on the server, when
  `tools/server.py stats` asks; the report is copied to `data/stats/` (not in git) and never served.
  Countries come offline from DB-IP Lite Country (CC BY 4.0), credited in the report; the HOSTS
  panel is off. No JavaScript, no cookies, nothing stored in the browser.

## Consequences

- No consent banner is needed: nothing is stored on or read from the device (§ 25 TDDDG).
- Chart downloads and Cite clicks never reach the server and are not counted.
- The server is ours to keep patched (unattended upgrades) and to pay for (EUR 6.53 a month gross,
  plus the IPv4 address).
- The deploy user has passwordless sudo, so its SSH key is root-equivalent (ruling R35).
- The basemap is coarser than OSM's own tiles beyond zoom 13. A new extract is a re-cut and an
  upload of about 900 MB.
- Cloudflare Pages (`docs/deploy.md` §1) is kept as documentation, marked not chosen.
