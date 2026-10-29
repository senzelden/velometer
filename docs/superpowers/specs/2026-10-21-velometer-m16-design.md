# velometer M16: Hetzner deployment, own tiles, visitor statistics, legal review (design)

Status: draft for user review, 2026-10-21. M15 ended with "Next: not yet decided". On 2026-10-19
the user chose Cloudflare Pages. On 2026-10-21 they moved to Hetzner, because access logs must not
go to a US company, and asked for basic visitor statistics and a thorough legal review. One round
of questions settled the rest (§2).

## 1. Purpose

Put velometer and the Zählwerk Berlin Datalab main page on a server of our own in Germany, ready to
open to the public. Nothing a visitor loads should come from another host. Visitor statistics must
need no consent banner. The legal position is checked topic by topic and fixed where the repo can
fix it.

The milestone ends with both sites live on their real hostnames, **behind a password** (§4.6).
Opening them to the public is a separate step at the end. It needs the operator decision, the real
Impressum and Datenschutz values and a contact mailbox, and the user's explicit go (§4.7).

No stored number, OSM run, classifier version or database write is involved.

## 2. User decisions (2026-10-21)

- **Host:** Hetzner Cloud with Caddy (`docs/deploy.md` §2), not Cloudflare. Reason: no access logs
  at a US company. DNS stays at INWX.
- **Hostnames:** the apex `<domain>` serves the Datalab main page; `velometer.<domain>` serves
  velometer. Both run on one server, as two sites in one Caddyfile. The domain will be
  `zaehlwerk-datalab.de`. The user registers it at INWX; on 2026-10-21 it was not registered yet.
  The tools still take the domain as a parameter, and step 5 of §6 waits for the registration.
- **Server creation:** a Hetzner Cloud API token in `pass`, wired by direnv. The server is created
  from this machine, not by hand in the console.
- **Map tiles:** self-hosted vector tiles (Protomaps PMTiles), drawn in Leaflet by a vendored
  protomaps-leaflet. `tile.openstreetmap.org` is no longer used.
- **Operator:** not decided (private person, e.V. or company). The legal review covers all three;
  go-live waits for the choice.
- **Datalab main page:** draft A ("Zählwerk") of the spike artifact
  (https://claude.ai/artifact/ShbSKY4oQRnTnVUHroVUpm, version 2): no "Das Datalab" section, and the
  contact in the footer.
- **Visitor statistics:** wanted, "basic information". The approach in §4.4 was recommended in chat
  and not objected to; it is recorded here as the design's choice.

## 3. Facts this design rests on

- The export is 793 files and 303.1 MB (M15), and its own `deploy-check` passes. M15 ran the
  documented Caddyfile under Caddy 2.11.4 locally with 0 problems. Caddy 2.10.2 answers `.gz`
  siblings with 206 and must not be used.
- Three maps load raster tiles from `OSM_TILES` (`src/velometer/app/main.py`, used at about lines
  1041, 1470 and 1619): the tier map (`static/map.js`), the change map (`static/changemap.js`) and the
  counter map (`static/countermap.js`). The CSP admits `https://tile.openstreetmap.org` in
  `img-src`, and that is the only outside host a page loads.
- The tier maps include GISCO boundary outlines (the `boundary` member of each map's GeoJSON). The
  exported site credits OpenStreetMap only. "© EuroGeographics for the administrative boundaries"
  appears nowhere in the export (checked 2026-10-21); it is only in `docs/review/m2_results.md:91`.
  ADR 0008 does not mention GISCO or Eurostat.
- Caddy writes no access log unless a `log` directive asks for one.
- The spike page loads Google Fonts (Martian Mono, Public Sans) and has inline script and style.
  velometer's CSP forbids both.

## 4. Design

### 4.1 Legal review (first, because its findings feed the rest)

Output: `docs/review/m16-legal.md`, in English, with the German legal terms in the original. Every
topic gets:
- the rule, quoted from the primary source as read on a stated date (gesetze-im-internet.de,
  EUR-Lex, the licence texts, the providers' terms);
- what velometer and the Datalab page do today, with file references;
- a verdict: ok / fix in M16 / decision for the user / question for a lawyer;
- the fix, if any, with its commit.

Topics:
1. **Data licences, source by source.** OSM (ODbL: attribution, share-alike, the produced work vs
   the derivative database, offering the database); GISCO boundaries and Eurostat population
   (EuroGeographics credit, the terms on commercial use); every counter dataset in
   `config/counters.yaml` (dl-de-zero, ODbL, CC BY 4.0, NLOD); the Berlin WFS layers; BikeNetKit;
   the Protomaps basemap (ODbL data, the build's terms); protomaps-leaflet and Leaflet (code
   licences); the fonts of the Datalab page (OFL); a GeoIP database if §4.4 uses one.
2. **Comparison numbers and quotations.** Clean Cities, Copenhagenize, ECF/QECIO and the official
   figures: copyright and the EU database right (sui generis) for single figures; § 51 UrhG for the
   excerpts in `content/sources/*.yaml` (purpose of the quotation, length, attribution); plan
   documents cited, not redistributed.
3. **Statements of fact (press law).** Every reader-facing sentence, in both editions, that names a
   person, a party, an administration or an organisation, or that states a cause ("rollback",
   "underspend", a ranking "is not reproducible"), is listed in a table: sentence, file, source
   behind it, fact or opinion, risk. Risky sentences get a proposed rewording. **No reworded
   sentence ships without the user's review** (as in M13). This includes the "mapped km, not built
   km" discipline (ADR 0006).
4. **Impressum.** § 5 DDG and § 18 MStV for journalistic-editorial content (V.i.S.d.P.); what each
   operator form (private person, e.V., company) must state; the address question, including a c/o
   service; where the Impressum lives (on the apex, linked from both sites).
5. **Datenschutz.** GDPR Art. 13; the legal basis for logs and statistics (Art. 6(1)(f)); § 25
   TDDDG (nothing stored on or read from the device); Hetzner as processor (AVV); Let's Encrypt
   (sees the domain only); log retention; the rights and the Berlin supervisory authority (BlnBDI);
   a check that no page loads anything from another host after §4.3.
6. **Other duties to check off:** accessibility law (BFSG: does it apply?), the OSM tile usage
   policy (moot after §4.3, stated as such), trademark or name use of the organisations quoted,
   and image rights on the Datalab page.

Deliverables beside the review:
- German **Impressum** and **Datenschutzerklärung** texts as pages of the Datalab site
  (`/impressum`, `/datenschutz`), written for the chosen setup, with one marked variant block per
  operator form and placeholders for name, address and contact. Placeholders are visible and
  refused by a go-live check (§4.7).
- A short **questions for a lawyer** list at the end of the review.
- The review says plainly that it is not legal advice.
- Fixes the repo can make go in M16: at least the EuroGeographics credit wherever the map credit
  appears (pages, downloads, CSV preamble where boundaries are involved), and ADR 0008 extended with
  GISCO, Eurostat, Protomaps and the fonts. Each fix has a test that fails without it.

### 4.2 Server and Caddy

- **Creation:** a tool (`tools/server.py`, subcommands as the builder sees fit) creates the server
  through the Hetzner Cloud API with a token from `pass` (`use_pass HCLOUD_TOKEN velometer/hcloud-token`
  in `.envrc.example`; the user runs `pass insert`). The smallest shared x86 type, a German location
  (`nbg1` or `fsn1`), Debian 13, IPv4 and IPv6, a Hetzner Cloud firewall (22, 80, 443 in; 443/udp
  for HTTP/3). Creating, resizing and deleting are confirmed with the user each time: they cost
  money. The API is called with the existing dev dependencies or the official `hcloud` CLI pinned to
  an exact release with a checksum; no new runtime dependency.
- **SSH:** the user's public key is uploaded to Hetzner and named in the creation call. Which key is
  confirmed with the user at that step. No private key is written anywhere.
- **Setup:** cloud-init user data checked in under `deploy/`, so a fresh server comes up the same
  way: a deploy user, SSH by key only, unattended security upgrades, Caddy at an exact version
  ≥ 2.11.4, GoAccess. Setup is repeatable: running it twice changes nothing.
- **Caddyfile:** one real file, `deploy/Caddyfile`, taking over from the copy in `docs/deploy.md`
  (the doc points to it; `tests/test_m14_deploy_doc.py` moves its assertions to the file). Two
  site blocks, `<domain>` and `velometer.<domain>`, with the hostnames as Caddy placeholders or an
  env file, not hard-coded. Security headers stay equal to the export's `_headers` (the test holds
  that), plus `Strict-Transport-Security` for one year, without `includeSubDomains` or `preload`.
  `www.<domain>` redirects to the apex. Range requests must work on `.pmtiles` (protomaps-leaflet
  reads byte ranges); `.pmtiles` gets no `.gz` sibling.
- **Deploy:** each upload goes to `releases/<build>/` and a symlink `current` is switched once the
  upload is complete, so a reader never sees half a site. The last three releases are kept;
  removing older ones never uses `rm -rf` on a computed path without a guard that it lies under
  `releases/`. Tiles live outside the releases (`/srv/tiles/`), because they change rarely.
- **DNS:** the user enters A and AAAA records for `<domain>`, `www.<domain>` and
  `velometer.<domain>` at INWX by hand. The tool prints the values. INWX credentials stay off this
  machine.

### 4.3 Self-hosted vector tiles

- A tool cuts one PMTiles extract from a dated Protomaps daily build with the `pmtiles` CLI
  (pinned release, checksum), covering the bounding boxes of all 21 cities' largest boundary (FUA),
  up to a maxzoom chosen by measured size (target: the whole extract under 1 GB; the builder
  measures z14 and z15 and records both). The build date goes into `build.json` and the map credit.
- protomaps-leaflet is vendored into `static/vendor/` beside Leaflet, with its licence and an entry
  in `VERSIONS`, pinned to an exact release at least two weeks old. No npm dependency enters the
  repo.
- The three maps switch from `L.tileLayer` to the vector layer, with a muted light flavour and a
  dark flavour that follow the page theme. Labels are drawn with fonts the page already has; no
  glyph or sprite host. Beyond the extract's maxzoom the layer overzooms.
- The CSP loses `https://tile.openstreetmap.org`. `connect-src 'self'` covers the range requests.
  `OSM_TILES` and the foreign-host allowance in the render pass go.
- The local export (`app serve`, the render pass, the dry run) needs tiles too. The builder chooses
  how: a small dev extract, the full one, or a configured tile URL. A missing tile file must give a
  map without a basemap and a clear console-free state, not a broken page.
- The map credit names OpenStreetMap contributors, Protomaps and (tier maps) EuroGeographics.

### 4.4 Visitor statistics

- Caddy writes a JSON access log per site, with the client IP masked (IPv4 /24, IPv6 /48) by Caddy's
  log filters before it reaches the disk. Cookie and Authorization headers are dropped from the
  log. The log rolls daily and is kept for 14 days.
- GoAccess turns the logs into a report: page views, approximate unique visitors, pages, referrers,
  countries, browsers and operating systems, 404s, file downloads (CSV, PNG, GeoJSON). Countries
  come from a local GeoIP database file if its licence allows it (the review checks this), never
  from an online lookup.
- The report is not served on the web. A tool command builds it on the server and copies it to
  this machine (`data/stats/`, git-ignored), keeping one HTML file per run.
- No JavaScript, no cookies, nothing stored in the browser. Chart downloads and Cite clicks, which
  never reach the server, are not counted (an accepted gap; an on-site counter is out of scope).

### 4.5 The Datalab main page

- Lives in this repo under `sites/datalab/`, as static files: HTML, one CSS file, one JS file, the
  fonts as self-hosted woff2 with their OFL licence files. No inline script or style; the same CSP
  as velometer.
- Content: draft A as of version 2, in German. The Berlin counter's figures are read from the
  velometer export (`data/all.csv`) when the Datalab site is built, so they cannot drift from
  velometer. The Impressum and Datenschutz pages of §4.1 live here. The velometer link goes live
  only with the go-live.
- velometer's `config/site.yaml` points `impressum_url` and `privacy_url` at these pages.

### 4.6 Password until go-live

Both sites answer only with HTTP basic auth until the go-live. The password is in `pass`
(`velometer/preview-password`); the bcrypt hash is written to a file on the server that the
Caddyfile imports, never into the repo. Search engines see `401` and nothing else. The checks of
§6 run through the lock with the password.

### 4.7 Go-live (the last step, confirmed separately)

A check (`tools/server.py golive-check`, or as the builder names it) refuses while any of these is
open: the operator is undecided; a placeholder remains in the Impressum or Datenschutz; the contact
mailbox is not given; a "decision for the user" from the review is open; a press-law sentence is
unreviewed. When it passes and the user says go, the lock is removed. If the user's answers are not
in by the end of M16, M16 ends at the locked state and the go-live is a follow-up.

### 4.8 Records

- `docs/review/m16-legal.md` (§4.1), `docs/review/m16-deploy.md` (versions, commands, the live
  probe and render-pass reports, the tile extract's size and maxzoom, a sample of a masked log
  line, a first GoAccess report looked at).
- `docs/deploy.md` rewritten around the Hetzner route. The Cloudflare section is kept but marked
  as not chosen.
- ADR 0009: hosting at Hetzner with own tiles and log-based statistics, and why.
- Rulings in `docs/superpowers/rulings-m16.md`; HANDOVER and CLAUDE.md updated.

### 4.9 Builder's calls (settled after the builder check, 2026-10-21)

1. **IP masking.** Every Caddy log that can carry a client address goes through the masking filter
   or does not record HTTP requests at all: the access logs, and the default logger, whose
   `http.log.error` entries carry `remote_ip`. stdout/journald get no unmasked address. A /24 mask
   is treated as pseudonymous, not anonymous, so the legal basis is Art. 6(1)(f) with 14-day
   retention. The review judges whether that holds. If it doesn't, the fallback is to drop the IP
   entirely; GoAccess then counts visitors less accurately.
2. **Without the domain.** Everything up to step 4 of §6 needs no domain. If it is still not given
   when step 5 is reached, M16 ends with the live items of §7 marked open, not claimed.
3. **Operator variants.** The Impressum and Datenschutz pages hold one complete variant block per
   operator form (private person, e.V., company). A config field (`sites/datalab/site.yaml`
   `operator_form`, null until chosen) selects one; the build renders only that one. The go-live
   check refuses null.
4. **Disk and maxzoom.** 1 GB is a target, not a hard limit; the smallest current shared type has
   more than enough disk. If z14 already exceeds it, a lower maxzoom with overzoom is acceptable,
   and the screenshots show what that looks like.
5. **Transport.** `rsync` over SSH into a fresh `releases/<build>/`, with `--link-dest` to the
   previous release so only changed files travel. The symlink is switched only after rsync exits 0
   and a marker file written last is present.
6. **GeoIP.** DB-IP Lite Country (CC BY 4.0, no account). Countries are dropped if the review finds
   any doubt. No MaxMind account.
7. **Datalab build input.** The Datalab site is built from a finished velometer export
   (`--velometer-export DIR`); the tests use a small checked-in fixture CSV. The Datalab site gets
   its own releases under its own root.
8. **Press-law scope.** Not every sentence: only those that name a person, party, administration
   or organisation, or that state a cause or a judgement about one. They are found by a script that
   lists candidate sentences from the content and config files, and a reading that cuts the list
   down.
9. **Secrets preflight.** Every tool step that needs `HCLOUD_TOKEN` or the preview password checks
   for it first. If it is missing, the step stops and names the `pass insert` command; no step
   assumes the entry exists.

## 5. Out of scope

- A mailbox for the domain (the user sets it up; the go-live needs its address).
- JavaScript analytics (Umami, Plausible, GoatCounter).
- English pages for the Datalab site.
- Changing any number, classifier or run.
- B and C of the spike.

## 6. Execution order

1. Legal review, research part (§4.1). Fixes that need no user input go in straight away.
2. Self-hosted tiles (§4.3), with the local setup, CSP change and render pass.
3. The Datalab site (§4.5), with Impressum and Datenschutz drafts.
4. Caddyfile, cloud-init and the server tool (§4.2, §4.4, §4.6), tested locally first (the M15 dry
   run gains the two sites, the lock, the log format and Range on `.pmtiles`).
5. Server creation (confirmed), DNS (user), first deploy behind the lock, live checks.
6. Press-law table to the user for review; their changes applied.
7. Records; final whole-branch review.
8. Go-live, only if §4.7 passes and the user confirms.

Work goes on branch `m16`. Merges are local; there is no push to a remote unless the user asks.

## 7. Accept

- The gate is green, including the node tests; the six checks exit 0; `velometer.sqlite` is
  unchanged (md5).
- No exported page of velometer or the Datalab site loads anything from another host (render pass
  foreign-host audit, both editions, both themes).
- Locally and live: the probe reports 0 problems on both hostnames, including TLS, the HTTP→HTTPS
  redirect, HTTP/2, the security headers, the 404 page, Range on a `.pmtiles` file and the `401`
  without the password.
- Live: `render_pass.py --url --pages types --interact --flip` reports 0 findings on velometer,
  and the Datalab pages are audited the same way.
- A live access log line shows a masked IP; a GoAccess report was produced and looked at.
- Screenshots of the three maps with the new tiles (both themes) and of the Datalab page (1280 and
  390, both themes) were looked at.
- `docs/review/m16-legal.md` covers every topic in §4.1 with a verdict.

**Not claimed:** that the review is legal advice; anything about mail; the go-live, unless §4.7
passed and the user confirmed it.
