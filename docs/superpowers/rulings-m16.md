# M16 rulings

M16 puts velometer and the Zählwerk Berlin Datalab page on a Hetzner server of our own, behind a
password, with a self-hosted basemap, masked access logs, log-based statistics and a legal review.
Go-live is a separate step (plan Task 12) with the user's go.
- Spec: `docs/superpowers/specs/2026-10-21-velometer-m16-design.md`.
- Plan: `docs/superpowers/plans/2026-10-21-velometer-m16.md`.
- SDD ledger, briefs, reports and reviews: `.superpowers/sdd/2026-10-21-velometer-m16/`
  (git-ignored scratch).

The committed evidence:
- `docs/review/m16-legal.md`, the legal review with a verdict per topic;
- `docs/review/m16-press.md`, the press-law table, every row reviewed;
- `docs/review/m16-deploy.md`, the live deployment behind the lock;
- `docs/deploy.md`, the Hetzner route as run;
- ADR 0009 (`docs/adr/0009-hetzner-own-tiles-log-statistics.md`) and ADR 0008 (licences, extended).

Each execution ruling reads: Ruling — why — cost if wrong.

## User decisions

- **2026-10-19:** Cloudflare Pages as the host (superseded two days later).
- **2026-10-21 (spec §2):**
  - Host: Hetzner Cloud with Caddy, not Cloudflare, because access logs must not go to a US
    company. DNS stays at INWX.
  - Hostnames: the apex serves the Datalab page, `velometer.<domain>` serves velometer, one server,
    one Caddyfile; the domain `zaehlwerk-datalab.de`.
  - The server is created from this machine through the Hetzner API with a token in `pass`.
  - Map tiles: self-hosted Protomaps PMTiles drawn by a vendored protomaps-leaflet.
  - Operator undecided; the review covers all three forms.
  - Datalab page: draft A ("Zählwerk") of the spike, version 2.
  - Visitor statistics: basic, from the logs (spec §4.4).
- **2026-10-22/23 (Task 10):** all 32 press rewordings accepted, 64 rows kept, claim 47 at printed
  precision. Legal 1.1c: publish the repository and link it from the methodology (the lede stays);
  1.2b: non-commercial; 4.1: the operator is a private person; 4.4: e-mail contact only.
- **2026-10-24:** the credit strings (R8, R15), the German 404 wording (R29), the Impressum and the
  Datenschutzerklärung approved; the second German ECF sentence smoothed; supervisory authority
  BlnBDI. The postal address is left off the pages entirely until it is set (R39).
- **2026-10-28:**
  - Domain registered at INWX; `pass` entries and `.envrc` in place; Hetzner key `dennis-ws`, own
    project. Server created as `cx23` at `fsn1` (R40, R41); DNS entered by the user; setup, deploys
    behind the lock (Task 9).
  - The database write: `velometer external load --no-qecio --no-bikenetkit`, to bring
    `external_figures` in line with the reviewed `figures.csv` (md5 now
    `bc7225af0cc4b50753c1d73fe19298be`).
  - Contact `zaehlwerk-datalab@posteo.com`, mail host Posteo e.K.; Verantwortlicher Dennis Senzel
    (legal 4.2).
  - Repo paths on the pages link the public repository (R42).
  - **First go-live without a postal address (R43).** This contradicts R39's go-live clause; the
    user was asked and confirmed it, and knowingly accepts the risk under § 18 MStV and § 5 DDG.
    Recorded in `m16-legal.md` 4.3 as a waiver that `golive-check` reads.
  - Git remote `origin` = https://github.com/senzelden/velometer, private for now; `main` and `m16`
    pushed after a history scan (one author, no secrets, no blob over 5 MB). Links resolve only once
    the repository is public.
  - A README (English, one German line to the Datalab), drafted for the user's review, with
    `CITATION.cff` naming Dennis Senzel.
  - Hetzner DPA (AVV) concluded (legal 5.6; log data, website visitors).
  - Go: after the review fixes and Task 11, a fresh public export and a redeploy of both sites,
    behind the lock; no unlock.
  - The German methodology's repository sentence reads "Der Code ist mit den Klassifikationsregeln
    und dieser Dokumentation im velometer-Repository veröffentlicht." (the user's word
    "Klassifikationsregeln", as in the document's heading).
- 2026-10-29 (final review fix round):
  - Map credit with the tile build date, as drafted: "Protomaps (build 2026-08-11), ESA WorldCover
    (CC BY 4.0)" / "Protomaps (Stand 2026-08-11), ESA WorldCover (CC BY 4.0)".
  - Datenschutzerklärung §3 gains two sentences, the user's wording: "Weitere technische Angaben aus
    dem Kopf der Anfrage: Die üblichen (etwa bevorzugte Sprache oder Angaben zu Browser und Gerät)
    löscht der Server vor dem Schreiben; nur selten gesendete können im Protokoll stehen." and
    "Unabhängig von der Website protokolliert der Server Anmeldeversuche über den
    Fernwartungszugang (SSH) mit der vollständigen IP-Adresse; diese Einträge löscht er nach 14
    Tagen."
  - Go to run `setup` during the redeploy (new log filter, journald limit), lock kept.
- 2026-10-29 (accessibility statement):
  - A voluntary Erklärung zur Barrierefreiheit on the Datalab (`/barrierefreiheit/`), linked from
    both sites' footers, in the user's approved wording; after the claim check the user re-worded
    the map and zoom bullets and chose to make "Vor jeder Veröffentlichung … jede Seite …
    Tastaturtest" true through the deploy procedure (R64) rather than reword it.
  - On English pages the three legal footer links (Impressum, Privacy, Accessibility) carry
    `hreflang="de"`; the `<i lang="de">` mark on "Impressum" stays.

## Pre-flight rulings

- **P1.** The EuroGeographics credit on the tier map is added with
  `map.attributionControl.addAttribution(...)`, independent of the tile layer — the tile layer was
  replaced in Task 5 — cost: one credit line moved twice.
- **P2.** `docs/review/m16-press.md` ends with a `Status` column, `open` or `reviewed`;
  `golive-check` counts rows not `reviewed` — a machine-readable marker — cost: a column rename.
- **P3.** A legal verdict line reads `**Verdict:** decision for the user` and, once decided, gets
  ` (decided YYYY-MM-DD: …)` appended — same — cost: a regex.
- **P4.** The cloud-init lock answers every request with `respond "locked" 401` until `setup`
  writes the basic-auth block — a fresh server must never be open and has no password yet — cost:
  none.
- **P5.** The SDD workspace is not deleted with `rm -rf` (user rule); it is git-ignored — cost: a
  few KB.
- **P6.** Work on branch `m16` in the main checkout without a worktree — as M14 and M15 did —
  cost: none.

## Execution rulings

- **R1.** The German boundary credit is GISCO's prescribed "© EuroGeographics bezüglich der
  Verwaltungsgrenzen", not the plan's "für die" — the licensor's text wins — cost: a string.
- **R2.** The CSV preamble names each population source as recorded per city (Eurostat, INSEE,
  INE) — five cities use national offices — cost: a preamble line.
- **R3.** Logs roll daily with `roll_keep_for 336h`; GoAccess ignores the HOSTS panel and credits
  DB-IP — 14-day retention must hold and reports must not keep addresses — cost: config lines.
- **R4.** IPv6 stays masked to /48 as the spec says; the lawyer question stands — cost: one filter
  value if a lawyer wants /56 or no address.
- **R5.** Subagents run the full pytest in the background or with a 600000 ms timeout — it exceeds
  10 minutes — cost: none.
- **R6.** Task 2 covers review rows F1-F5 and ADR entries for F6, F7, F8 and F15; the review's
  notice texts override the plan's — the review read the licences — cost: a broader diff.
- **R7.** The tier-map PNGs and GeoJSON are regenerated before the first deploy — credits changed —
  cost: one redraw.
- **R8.** The new credit strings go to the user with the press table — reader-facing wording needs
  review — cost: none (approved 2026-10-24).
- **R9.** The press CLI's candidate list is raw output; the reviewed table is hand-edited and the
  CLI never overwrites it by default — re-running must not destroy the review — cost: none.
- **R10.** The tile fixture is `tests/fixtures/tiles/berlin-z0-8.pmtiles`, named after its content
  — a name that lies about its zoom range misleads — cost: a rename.
- **R11.** The extract keeps the landcover layer (the CLI cannot drop it); the maps never draw it,
  and the credit adds ESA WorldCover anyway — the file is downloadable, so its data is distributed
  — cost: one credit line.
- **R12.** Maxzoom 13 (898 MB); the maps overzoom beyond it — spec §4.9 item 4 — cost: a re-cut at
  z14 (1.7 GB) if too coarse.
- **R13.** With no tile file, the browser's single 404 line for the probe is the designed degraded
  state; "zero console messages" is asserted with tiles present — the browser logs failed requests
  whatever the script does — cost: a JSON manifest probe instead.
- **R14.** Map colours are `--map-*` CSS tokens read by `basemap.js` — one source for both themes
  — cost: none.
- **R15.** `js.map.basemap_credit` joins the R8 list — cost: none (approved).
- **R16.** The Caddyfile sets `root * /srv/velometer` inside `handle_errors` — a 404 under
  `/tiles/` otherwise has no body — cost: one line.
- **R17.** With `operator_form` null the legal pages render all three variants with visible
  `[[…]]` placeholders; the Datalab has its own strict CSP — the operator was undecided — cost: a
  re-render.
- **R18.** Operator keys `mail_host`, `representative`, `authority` are accepted additions; phone
  and VAT optional — legal 4.1 and 5.1 require them — cost: golive-check counts them.
- **R19.** The lede "Offen, mit dem Code, der jede Zahl erzeugt" went to the user with legal 1.1c
  — true only if the code is published — cost: one sentence.
- **R20.** The Hetzner DPA is a user step before go-live — cost: none (done 2026-10-28).
- **R21.** The Datalab gets its own 404 page — its build had none — cost: one template.
- **R22.** The velometer link on the Datalab page is always rendered; the lock hides both hosts
  until go-live — spec §4.5 is met by the lock — cost: none.
- **R23.** The Datalab favicon came with its 404 page — a console 404 — cost: one file.
- **R24.** The German tier-SVG download must not wrap the ADR 0006 phrase at 390 px; fixed apart
  after Task 7 — a render-pass finding, older than M16 — cost: one fix.
- **R25.** `X-Forwarded-For`, `Forwarded` and `X-Real-Ip` are dropped from the logs — no proxy
  stands in front, so they carry only what a client wrote — cost: none.
- **R26.** The lock file sets `header Cache-Control "no-store"` in both forms — locked responses
  must not be cached — cost: none.
- **R27.** Retention is by time: `roll_keep_for 336h` binds, `roll_size` and `roll_keep` sit far
  above a day — Caddy has no unlimited count — cost: none.
- **R28.** The dry-run lock password may come from `VELOMETER_PREVIEW_PASSWORD` — cost: none.
- **R29.** The German 404 wording went to the user — cost: none (approved).
- **R30.** The server runs on UTC; uploads go to `releases/<build>` with a symlink switch; `verify`
  checks port 80 answers 308 — cost: lines in Task 8.
- **R31.** `golive-check` fails on automatable items and prints the manual confirmations — some
  facts no file shows — cost: none.
- **R32.** Site releases use `rsync -rlpD --checksum --link-dest` — an export writes every file
  anew, so times never match — cost: checksum CPU.
- **R33.** The `.complete` marker lies beside the release, not inside — inside it would be served
  — cost: none.
- **R34.** The monthly DB-IP download has no checksum — data, CC BY, over HTTPS — cost: none.
- **R35.** The deploy user keeps passwordless sudo in M16 — any allow-list covering setup and stats
  is root-equivalent — cost: the deploy key is root until fixed-argument helper scripts exist.
- **R36.** Caddy's checksum is SHA-512 from the official checksums file — stronger than SHA-256 —
  cost: none.
- **R37.** Datalab release names use the local HEAD commit — its build has no `build.json` — cost:
  none.
- **R38.** `figures.csv` lines 62-64 keep `length_basis` `unknown` — data, not reviewed prose —
  cost: a basis shown as unknown that Table 2 could support.
- **R39.** `DEFERRED = ("address",)` hides the address on the pages until set, and golive-check
  lists it as open — the law requires it at go-live — cost: none. Its go-live clause is superseded
  by R43.
- **R40.** Hetzner no longer offers `cx22`; the server is `cx23` (2 vCPU, 4 GB, 40 GB, EUR 6.53
  gross), and Task 11 made it the default — cost: none.
- **R41.** `create` at `nbg1` failed with 412 (no capacity); retried at `fsn1`, the spec's other
  German location, same price — cost: none.
- **R42.** `config/site.yaml` gets `repo: {url, file_url}`; a public export refuses without it;
  links pin to `commit_full`; heading locators get a GitHub/Forgejo anchor; code spans that are
  repo paths link too; the methodology links `repo.url` (1.1c); deploy-check refuses an unlinked
  repo path — about 168 citations on 60 pages named internal paths — cost: a forge change means new
  `file_url` and anchor checks.
- **R43.** The first go-live may go without the postal address, but only with the recorded waiver
  line `**Go-live without:** operator.<key> (decided DATE: …)` for a deferred key; golive-check
  prints it as waived — the user's decision of 2026-10-28, no silent drop — cost: the legal risk the
  user accepted.
- **R44.** Repo paths that the browser renders (Compare's flag notes) are linked through a
  per-explanation `{path: url}` map in `series.json`; `js.counts.config_error` stays out of scope —
  cost: none.
- **R45.** Repo links, fix round 2: `unlock` needs `--site` and runs the repo probe; the probe and
  the manual line say "pushed and publicly readable at repo.url"; the export commit gets a pushed
  tag, and `golive-check --site` asks the remote for it; the plan's Task 12 follows the
  scratch-config workflow; the guard covers `LICENSE`, `CITATION.cff`, `uv.lock`,
  `.python-version`, `scripts/` and `.csv/.sh/.html/.css/.geojson/.txt/.ipynb/.cff`; it reports a
  bare file name apart from an unlinked path; deploy-check wants both methodology pages to link
  `repo.url` — the review's I1, I2, M1, M2, M4, M5, M8 — cost: none.
- **R46.** `golive-check --site` checks the tag itself: `git ls-remote --tags repo.url`,
  anonymously (`GIT_TERMINAL_PROMPT=0`), must list a tag on `commit_full`; a failed listing or no
  such tag is open — cheap and exact, so no manual line — cost: one `git` call per check; a forge
  that hides tags from anonymous clients would need the tag confirmed by hand.
- **R47.** `tools/server.py` gives every command without input `/dev/null` as stdin, rsync
  included, not only ssh — no step reads the operator's terminal except the typed `yes` — cost:
  none.
- **R48.** The figures guard compares every curated source (all but `qecio_v2_10` and
  `bikenetkit_v1`) field by field as `external load` stores it, so a source dropped from the CSV
  is caught too. A config without `external/figures.csv` has nothing to compare (the app treats
  the file as optional); `velometer external check` refuses a missing file — cost: an export from
  a config that lost the file passes the guard.
- **R49.** The export runs the figures guard only with `--public` (the brief's rule). Tests whose
  fixture database holds synthetic figures switch it off by monkeypatch, as they do for the clean
  commit; the guard has its own tests — cost: none.
- **R50.** Task 11 does not merge `m16` into `main` (the plan's Step 4): the brief says no merge;
  the merge waits for the final review and the user — cost: none.
- **R51.** Final-review fix round: I1-I4, M1-M8 and M10 are fixed; M9 gets the 14-day journald
  retention and is recorded (R53). Each `fix in M16` topic of the legal review names its commits
  — the review found the gate blind to a missing fix — cost: one round.
- **R52.** Caddy's log filter cannot keep a list of headers (2.11.4: no allow-list module, and
  `request>headers>* delete` deletes nothing), so both log filters delete by name every header a
  browser commonly sends but `User-Agent` and `Referer`, in Go's canonical spelling (`Dnt`,
  `Sec-Gpc`, `Te`), plus `request>tls`, `user_id`, `duration` and `resp_headers`; GoAccess 1.9.3
  reads the lines without them. A header not on the list is still written, so the
  Datenschutzerklärung needs a sentence for "further technical headers", which goes to the user
  (R8) — the alternative, `log_append` fields and a custom GoAccess format, changes the stats
  pipeline — cost: the list must grow if browsers add headers; the dry run fails on any kept one.
- **R53.** journald keeps 14 days (`MaxRetentionSec=14day`, by cloud-init and `setup`). sshd logs
  the unmasked address of every SSH client (scanners on port 22 included) to the journal, for up
  to 14 days, outside the masked web logs and the statistics; the Datenschutzerklärung's wording
  for it is the user's — personal data kept without a stated period otherwise — cost: older
  journal lines for debugging are gone after 14 days.
  Checked on the server 2026-10-29: `/var/log/btmp` is empty (this Debian image's sshd writes
  no failed logins there), there is no rsyslog and no `auth.log`; `wtmp` holds only the
  operator's own logins. The journal is the only place SSH client addresses are kept.
- **R54.** Go-live judges what is live: `unlock` and `golive-check --host` compare a digest of every
  file (path and sha256) of the release `current` points to, computed on the server over the
  guarded release path, with `--site` and `--datalab`; `--host` without `--site` is open. The
  Datalab build stamps `build.json` `inputs_sha256` over its settings, templates, static files and
  the shared credit strings; a missing or stale stamp is open. `unlock` reads the server before it
  refuses — cost: an ssh round trip per site on every unlock attempt.
- **R55.** The Protomaps build date reaches the credit from data: `tools/tiles.py` writes
  `velometer.pmtiles.json` (build, maxzoom read from the PMTiles header, sha256; `--stamp` for an
  extract cut before), the export records it in `build.json` `tiles` and passes the date to the
  maps' configs (`tiles_build`). Without a sidecar the credit stays undated and a public
  deploy-check refuses the export. The sidecar of the existing extract was written locally
  (`data/` is git-ignored) — cost: the deployed tile file's sha256 is not compared with
  `build.json` (a manual check).
- **R56.** `render_pass.py` and `readme_shots.py` log in as `preview` with
  `$VELOMETER_PREVIEW_PASSWORD` whenever `--url` is given and the variable is set; `--auth` still
  overrides. The header reaches only the `--url` origin (`Fetch.enable` with that origin's pattern;
  checked in Chrome against a second origin) — cost: an audit of an open site sends a harmless
  header to it.
- **R57.** A legal fix is closed only by ` (fixed <sha>[, <sha>…])` on its verdict line, each
  commit known to git (`git cat-file -e`); 5.1 names the log-field fix (533da34) beside the page
  — cost: none.
- **R58.** The config guard (M6) compares `--config-dir` with HEAD's `config/` by git blob id,
  `site.yaml` aside; tests whose fixture config is no copy switch it off (as R49) — cost: none.
- **R59.** `--host` takes an IP address or a host name, single labels included (an ssh alias);
  `--user` is checked too — cost: none.
- **R60.** `deploy datalab` wants the stamp of the committed `sites/datalab/`, not only a stamp, so
  the release named after HEAD is what HEAD builds — cost: a rebuild after every commit there.

- **R61.** The log filters also delete Alt-Used, Save-Data, Via, X-Forwarded-Host and
  X-Forwarded-Proto (final re-review N1) — headers Firefox over HTTP/3, data-saver modes and
  proxies send — cost if wrong: a rarely sent header stays in the log, which the
  Datenschutzerklärung now says.

- **R62.** The tag check really is anonymous: `git ls-remote` runs with no askpass program
  (`GIT_ASKPASS=`, `SSH_ASKPASS=`), no global or system git config and from `/`, so no credential
  helper applies. Found on the redeploy of 2026-10-29: VS Code's `GIT_ASKPASS` and the per-host gh
  helper logged in silently, and the check passed on the private repository — cost if wrong: the
  tag check would pass before the repository is public (the repo-link probe still caught it).

- **R63.** The accessibility statement is a Datalab page like the legal pages: the hosts from
  `domain`, the e-mail the Impressum's (`operator.email`, as a mailto link), the "Stand:" date
  `accessibility.checked` (an ISO day, null until go-live, a visible placeholder meanwhile);
  `golive-check` refuses while the date is null or the build lacks the page. velometer links it by
  `accessibility_url`, independent of the Impressum pair, required by `export --public`, recorded
  in `build.json` and checked by `deploy-check --public` like the other footer links. English
  terms carry `lang="en"`: the guideline title as `<i lang="en">`, the names and the loanword
  (WCAG, axe-core, Orca, Screenreader) as `<span lang="en">`, not italic — cost if wrong: a
  styling difference only.
- **R64.** The statement's "Vor jeder Veröffentlichung … jede Seite … Tastaturtest" is made true:
  `docs/deploy.md` §1 runs `render_pass.py --pages all --keyboard` (and the Datalab pass) on the
  export being published, before the go-live against the locked server and afterwards against
  the local dry run before uploading; `golive-check` prints it as a manual confirmation, and
  `accessibility.checked` is the day of those passes — cost: a full pass over every page
  before every publication.

## Known limits (recorded, not fixed)

- **M3, slug divergences.** `heading_slug` differs from github-slugger for numbers of category No
  (`²`), connector punctuation other than `_`, headings with inline markup or HTML (we slug the raw
  text, GitHub the rendered), generated suffixes that collide (`x, x, x-1`), setext and indented
  headings, `#` lines in indented code or HTML comments, and unclosed fences. No heading a page
  links hits any of them today.
- **M6, anchor cache.** `file_anchor` is cached per process, so a long-running dev server keeps old
  anchors after a heading is edited. Exports start fresh.
- **M7, untracked content renders.** An untracked narrative or doc shows on a public export but is
  not in `commit_full`; its paths stay unlinked and the guard flags any it cites. `docs/deploy.md`
  §0 says to commit first.
