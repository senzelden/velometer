# Deploying the static edition

The chosen route is a Hetzner Cloud server with Caddy (§1, ADR 0009). It was run on 2026-10-28:
both sites are on the server behind a password (`docs/review/m16-deploy.md`); the go-live (the
`unlock` at the end of §1) waits for the user's go. Since M17 a deploy can also run on GitHub, from
the committed `main`, after the user approves it there (§2). The Cloudflare Pages route (§3) was
not chosen. M15 served the export locally with both routes' server software (Caddy 2.11.4 in Docker
and `wrangler pages dev` 4.147.0, 2026-10-18; §0a, `docs/review/m15-dryrun.md`). Every command below is for you to run. Replace `<dir>`,
`<datalab-dir>`, `<domain>` and `<host>` with your own values.

## 0. Make and check the export

The public site values (the site's own URL, the Datalab, its Impressum, privacy page and
accessibility statement, the public repository) are committed in `config/site.public.yaml` (M17,
R1). `export --public` merges that file over `config/site.yaml`, which stays null, so there is no
scratch copy of `config/`: export from the repo's own `config/`. Only public values belong in the
overlay (https URLs and the Datalab's name; no e-mail, no postal address).

```
git status --untracked-files=no      # must print no changes: commit first
uv run python tools/tiles.py --stamp     # once per extract: data/tiles/velometer.pmtiles.json
uv run velometer app export --out <dir> --base / --clean --public
uv run velometer app deploy-check <dir> --public
c=$(jq -r .commit_full <dir>/build.json)
git push <public remote> HEAD        # the commit the pages link must be in the public repo
git tag export-${c:0:7} $c && git push <public remote> export-${c:0:7}
```

The tag keeps the pinned commit reachable on the forge after the branch is merged (squashed or
rebased) or deleted; without it the links may lose their commit and every citation rots.
`golive-check --site <dir>` lists a commit that no tag at `repo.url` points at as open (it asks
`git ls-remote --tags repo.url`, anonymously).

`export --public` refuses to run unless the site settings name the site's own URL (`url`), the Datalab, its Impressum, its
privacy page and its accessibility statement (`accessibility_url`, R63), and the public repository (`repo.url`, the home page, and `repo.file_url`, a file's
address with `{commit}` and `{path}`; the comments in `site.yaml` give GitHub and Codeberg
examples), and records those values in `build.json`. It refuses when the database's curated
external figures differ from `config/external/figures.csv` (`velometer external check` names the
rows; `velometer external load --no-qecio --no-bikenetkit` reloads them and writes the database,
so it needs the user's go). It refuses a config directory that differs from the commit's
`config/` in any file (changed, missing or added: the pages would show numbers or values the
linked commit does not produce; export from the repo's own `config/`). It also refuses a checkout whose tracked files
have uncommitted changes (untracked files do not count): every repo path on the pages (a data
reference's file, `docs/...` in the prose, the paths in Compare's flag notes) links
`repo.file_url` at the export's commit (`build.json` `commit_full`). So the export must come from a
committed tree, and that commit must be pushed to the public repository, and the repository
publicly readable, before the site goes live, or every repo link 404s (`golive-check --site <dir>`
fetches one anonymously, §1 step 4). The methodology links `repo.url` (legal review 1.1c).
Untracked files do render: an untracked new narrative or doc shows on the pages but is not in
`commit_full`, so those pages cannot be rebuilt from the commit (its repo paths stay unlinked,
and the guard below flags any it cites). Commit what the pages show before a public export.

The export reads the basemap's sidecar, `data/tiles/velometer.pmtiles.json` (`--tiles-info`), which
`tools/tiles.py` writes beside every extract it cuts (`--stamp` writes it for one cut before): the
Protomaps build, the extract's max zoom and its sha256. It goes into `build.json` `tiles`, and
the maps' credit names the build date ("Protomaps (build 2026-08-11), …"; spec §4.3, legal review
1.7). Without the sidecar `tiles` is null, the credit has no date, and `deploy-check --public`
refuses the export.

`deploy-check` uploads nothing. It checks `build.json` and its base, `404.html`, the `_headers`
file against the pages' meta policy, a `.gz` that matches each text file of 1 KiB or more, that
no file is 25 MiB or more, that every reference resolves, and, for a public export, that every
page's footer links the Datalab, Impressum, privacy page and accessibility statement that
`build.json` records, that no page
prints a repo path in `<code>` outside a link (under `docs/`, `config/`, `src/`, `tools/`,
`content/`, `sites/`, `deploy/`, `tests/`, `scripts/`, a root file such as `HANDOVER.md`,
`LICENSE`, `CITATION.cff` or `uv.lock`, or any path-like `.py`, `.yaml`, `.md`, `.js`, `.json`,
`.toml`, `.csv`, `.sh`, `.html`, `.css`, `.geojson`, `.txt`, `.ipynb` or `.cff` name), that every
repo link carries the export's `commit_full`, and that the methodology page, English and German,
links `repo.url`. It judges the export, not today's `config/site.yaml`. A bare file name with no
directory (`retrieved.json`) is reported apart from an unlinked repo path: it is usually an error
message on a page that failed to build (the plans page when its record is unreadable), so fix the
cause and export again.
`deploy-check --public` also fails on an export made without `--public`, which would go live
without an Impressum. It exits 1 and lists the problems otherwise. Run it again after any hand
edit.

## 0a. Local dry run

Before you upload, serve the export with the same server software the host runs and probe it over
HTTP (status, compression, security headers, 404 page):

```
uv run python tools/deploy_dryrun.py --site <dir> --server caddy --datalab <datalab-dir> \
    --tiles <file.pmtiles> [--lock | --lock-default] [--debug-log]
uv run python tools/deploy_dryrun.py --site <dir> --server wrangler
```

`--server caddy` runs Caddy 2.11.4 in Docker with `deploy/Caddyfile`, the production file (§1),
serving both sites: the Datalab build (`velometer datalab build`) at `localhost`, velometer at
`velometer.localhost`, the redirect at `www.localhost`, all on one port of 127.0.0.1, without TLS.
The probes name the site in the Host header; a browser reaches the names directly (Chrome
resolves `*.localhost` to loopback). It also asks the tile file for a byte range (206) and a
malformed one (416), checks HSTS and the `www` redirect, and afterwards reads the access logs and
Caddy's own output: neither may hold the probes' address (`127.0.0.77`), a forged
`X-Forwarded-For` (`203.0.113.7`), a cookie, the password or its Authorization header, and each
access log must show the probes' address masked to /24 and keep none of those headers.
`--lock` (the password read from `$VELOMETER_PREVIEW_PASSWORD`, never typed on the command line)
locks both sites
as the server is locked until go-live (the bcrypt hash is made by `caddy hash-password` in the
container at run time and kept in a temporary file); every path of every host must then answer
401 without the password, and every locked response must carry `Cache-Control: no-store`.
`--lock-default` serves the lock the server comes up with (`respond "locked" 401`), which no
password opens. `--debug-log` raises Caddy's own log to DEBUG so that its error entries
(404, 401) are written and checked too.

`--server caddy` uses Docker host networking and so runs on Linux only. With `--network host`, the
Caddy container also binds Caddy's admin endpoint on 127.0.0.1:2019, so a Caddy already running on
the host (or a second dry run left up with `--keep-running`) makes the run fail after its 120 s
wait; stop the other one first. `--server wrangler` runs `npx wrangler pages dev` for the velometer
export alone. The tool ends with `N checks, M problems` and exits 1 on any problem. With
`--keep-running` it leaves the server up and prints its origins, so that `tools/render_pass.py
--url <origin>` can audit the pages through it (when locked it logs in as `preview` with
`$VELOMETER_PREVIEW_PASSWORD`, sending the header to that origin only; add `--lang de` for the
Datalab).

## 1. Hetzner Cloud with Caddy

The route as run on 2026-10-28 (`docs/review/m16-deploy.md`), in order. `tools/server.py` reads
`HCLOUD_TOKEN` and `VELOMETER_PREVIEW_PASSWORD` from the environment, wired by direnv + pass as in
`.envrc.example`. Every step that changes the server or costs money prints its plan and goes ahead
only after you type `yes`; a piped `yes` reaches the prompt (ssh gets no stdin).

```
uv run python tools/server.py preflight
uv run python tools/server.py create --domain <domain> --ssh-key <key name> [--type cx23] [--location nbg1|fsn1]
uv run python tools/server.py dns --domain <domain>         # enter the printed records at INWX
uv run python tools/server.py setup --host <host> --domain <domain>
uv run python tools/server.py deploy tiles data/tiles/velometer.pmtiles --host <host>
uv run python tools/server.py deploy velometer <dir> --host <host>        # the export of §0
uv run velometer datalab build --out <datalab-dir> --velometer-export <dir>
uv run python tools/server.py deploy datalab <datalab-dir> --host <host>
uv run python tools/server.py verify --domain <domain> --locked
uv run python tools/render_pass.py --site <dir> --base / --out <shots-dir>/all \
    --url https://velometer.<domain> --pages all --keyboard     # R64, before every publication
uv run python tools/render_pass.py --site <dir> --base / --out <shots-dir>/types \
    --url https://velometer.<domain> --pages types --interact --flip
uv run python tools/render_pass.py --site <datalab-dir> --base / --lang de \
    --out <shots-dir>/datalab --url https://<domain>
uv run python tools/server.py stats --host <host>
uv run python tools/server.py golive-check --datalab <datalab-dir> --site <dir> --host <host>
uv run python tools/server.py unlock --host <host> --domain <domain> --datalab <datalab-dir> --site <dir>
```

- `preflight` names the `pass insert` command for a missing secret and never prints a value.
- `create` makes a Hetzner Cloud firewall (22, 80, 443, 443/udp in) and a Debian 13 server with
  IPv4 and IPv6 from `deploy/cloud-init.yaml`: a deploy user with SSH by key only, unattended
  upgrades, UTC, Caddy at the pinned version (checked by SHA-512) not yet started, GoAccess, the
  release roots, the default lock, and journald's 14-day retention (`MaxRetentionSec=14day`:
  sshd logs the unmasked address of every SSH client to the journal; ruling R53). It refuses a location outside Germany, an unknown SSH key,
  an existing server of the same name, a deprecated type and an ARM type. The default type is
  `cx23` (Hetzner no longer offers `cx22`); the default location `nbg1` had no capacity on
  2026-10-28, and `fsn1` worked. A failed create may leave the firewall behind; the retry reuses
  it.
- `dns` prints A and AAAA for `<domain>`, `www.<domain>` and `velometer.<domain>`. Delete the
  registrar's parking records and wildcard. Let's Encrypt issues the certificates on the first
  request after `setup`.
- `render_pass.py` needs `--base /` against the live site: its default `/velometer/` 404s.
  Behind the lock it logs in as `preview` with `$VELOMETER_PREVIEW_PASSWORD` from the
  environment, so the password stands in no command line, process list or shell history, and
  it sends the Authorization header to the `--url` origin only.
- `golive-check` and `unlock` are the go-live (step 4 below); nothing before them opens the sites.
- Before every publication (the go-live, and every deploy after it) the full render pass
  (`--pages all`: every page of both editions, both themes, 1280/390/320) and the keyboard pass
  (`--keyboard`) run on the export being published, with 0 findings (ruling R64): the
  accessibility statement (`/barrierefreiheit/`) says so. Before the go-live run them against
  the locked server as above; once the sites are open, run them before uploading, against the
  local dry run of that export (§0a: `deploy_dryrun.py --server caddy --datalab <datalab-dir>
  --tiles data/tiles/velometer.pmtiles --keep-running`, then `--url` its velometer origin; the
  keyboard pass's map steps need the tiles). Set `accessibility.checked` in
  `sites/datalab/site.yaml` to the day of these passes, commit, and build and deploy the Datalab
  again (its stamp changes). The CD workflow (§2) runs the same passes on its own export and gives
  the Datalab build that day with `datalab build --checked`, without a commit. `golive-check` lists the passes as a manual confirmation and
  refuses while `accessibility.checked` is null or the Datalab build lacks the statement.

The steps in detail:

1. The server: the smallest shared x86 type in a German location. Use Caddy 2.11.4 or later:
   Caddy 2.10.2 answers a precompressed (`.gz`) file with `206 Partial Content` even when the
   browser asked for no range (found by the M15 dry run, `docs/review/m15-dryrun.md`).
2. DNS: A and AAAA records for `<domain>`, `www.<domain>` and `velometer.<domain>` pointing to the
   server, entered by hand at INWX; the INWX credentials stay off this machine.
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

   **Lock.** Every site block imports `/etc/caddy/lock.caddy` first. Until go-live it holds one
   of two texts, exactly as below; after go-live it is empty. As the server comes up (ruling P4):

   ```
   header Cache-Control "no-store"
   respond "locked" 401
   ```

   Once setup has the preview password (`<bcrypt hash>` from `caddy hash-password` on the
   server; it never enters the repository):

   ```
   header Cache-Control "no-store"
   basic_auth {
   	preview <bcrypt hash>
   }
   ```

   The Caddyfile's global `order` lines run the lock before `redir` and the tiles route, which by
   Caddy's default order would come first and answer without the password. The `header` line
   keeps every locked response out of caches, the 401, the pages behind the password and the 404
   page alike (ruling R26): it runs before the site's own headers, which set Cache-Control only
   where it is not set yet (`?Cache-Control`). A plain `header` in the lock file loses to the
   site's later one, and a deferred one misses the 401 and the 404 page (both seen with Caddy
   2.11.4). The dry run checks both texts on every host. Port 80 answers every request with
   Caddy's automatic 308 to `https://` before any site route, so before the lock too; that
   redirect names only the address that was asked for and reveals nothing of the sites.

   **Logs.** Each site writes a JSON access log, `/var/log/caddy/datalab.log` and
   `velometer.log`, with the client address masked to IPv4 /24 and IPv6 /48 before it reaches the
   disk (`remote_ip`, `client_ip`). The client port, `Cookie` and `Authorization` are dropped, and
   so are `X-Forwarded-For`, `Forwarded` and `X-Real-Ip`: no proxy stands in front of Caddy, so
   they carry only what a client chose to write (ruling R25). Of the request headers only
   `User-Agent` and `Referer` stay, the two GoAccess reads: Caddy's log filter has no allow-list
   or wildcard, so every other header a browser commonly sends is deleted by name, in Go's
   canonical spelling (`Dnt`, `Sec-Gpc`, `Te`), and so are the TLS details (`request>tls`), the
   basic-auth user (`user_id`), the duration and the response headers (ruling R52; checked with
   Caddy 2.11.4, and GoAccess 1.9.3 still reads the lines). A header not on that list, rare from
   a browser, is still written. The dry run fails on any kept header but those two.
   Retention is by time (ruling R27):
   the logs roll at 00:00 server time (`roll_at 00:00`; the server runs on UTC) and each rolled
   file is deleted once 14 days old (`roll_keep_for 336h`). Size and count must not prune first,
   and Caddy has no unlimited setting (`roll_keep 0`, or none, keeps 10 files; seen with Caddy
   2.11.4), so `roll_size 1GiB` and `roll_keep 1000` sit far above a day's log. A rolled file is
   gzipped, named like `velometer-2026-10-21T00-00-00.000-time.log.gz`. Caddy's own log (stderr,
   so journald) masks the same fields, writes no access lines, and drops the `http.stdlib`
   logger, whose messages name the client in their text (`TLS handshake error from
   <ip>:<port>`, at DEBUG) where no field filter reaches.
4. Setup, upload, statistics and go-live, with `tools/server.py deploy` and the other commands
   of the list above.

   `setup` writes `/etc/caddy/Caddyfile` (this file, checked by `caddy validate` as the `caddy`
   user before it replaces the live one), `/etc/caddy/caddy.env`, the GoAccess configuration and
   the journald drop-in (`deploy/journald-velometer.conf`; journald is restarted when it
   changes), and turns the lock the server came up with into the password lock: the password goes on stdin
   to `caddy hash-password` on the server, never on a command line. Run again, it changes
   nothing, and it leaves an unlocked server unlocked. It also compares what Caddy runs with the
   files on disk: the JSON config Caddy's admin API reports (`localhost:2019/config/`) against
   `caddy adapt` of the Caddyfile on disk, which includes the lock file. When Caddy is stopped,
   or a reload failed and Caddy still serves the previous lock, the two differ and `setup`
   reloads or starts Caddy, even when no file changed. A failed reload says what the running
   Caddy still serves.

   `deploy velometer|datalab` runs `deploy-check --public` on a velometer export first; a
   Datalab build is named after the local commit, so `deploy datalab` refuses a tree with
   uncommitted changes to tracked files and a build whose stamp is not that of the committed
   `sites/datalab/` (build it again after committing). Then it
   uploads the build with rsync into a new directory `/srv/<site>/releases/<build>/` (`<build>`
   is the export's commit and the UTC upload time, e.g. `1234abc-20261022T093005`), with
   `--link-dest` to the live release so that only changed files travel. Only after rsync exits 0
   does it write the marker `releases/<build>.complete` beside the release (outside the served
   tree, so no reader can fetch it), and only with the marker present does it switch the site: `ln -sfn releases/<build> current.new` and `mv -T current.new current`, an
   atomic rename. An upload that fails or is cut off leaves `current` on the previous complete
   release, so a reader never sees half a site. The three newest complete releases are kept;
   older ones are removed one at a time, marker first, each path first checked to be a release
   directory or its marker under `/srv/<site>/releases/`. `deploy` stops when `current` points to
   anything but a release. `deploy tiles` is no release: it uploads the file to
   `/srv/tiles/velometer.pmtiles.new` and renames it into place, as above.

   `verify` probes the live server: port 80 answers every host with a 308 to `https://`, and
   with `--locked` both sites and `www` answer 401 with `Cache-Control: no-store` and the tile
   file 401; without it the sites answer 200, `www` 308 to the apex and the tile file 206 to a
   byte range.

   Statistics (`stats --host <host>`) and the go-live (`golive-check --datalab <datalab-dir>
   --site <dir>`, then `unlock --site <dir>`) are in the tool's help. With `--site`, `golive-check`
   also fetches one file of the repository at the export's `commit_full` (`pyproject.toml`, by
   `repo.file_url`, anonymously) and lists anything but 200 as open: the commit is not pushed, or
   the repository is not publicly readable (a private repository answers 404). It also lists a
   commit that no pushed tag points at (§0). The Datalab build must carry the stamp of the
   settings and templates it is checked against (`build.json` `inputs_sha256`, written by
   `velometer datalab build`): a build made before a change to `sites/datalab/site.yaml` (say,
   the address added afterwards) is open; build it again. With `--host`, `golive-check` also
   compares what is live with what it checked: a digest of every file (path and sha256) of the
   release `/srv/velometer/current` and `/srv/datalab/current` point to, computed on the server,
   against `--site` and `--datalab`; any changed, missing or extra file is open, naming the site
   (deploy the checked directory first). `unlock` needs `--site` too and runs the same checks,
   the live comparison included, then empties the lock file and runs `verify`.

## 2. Deploy from GitHub

`.github/workflows/deploy.yml` (M17 spec §4.5) builds both sites from the server's data snapshot,
holds that exact export to the R64 passes and only then deploys it, as the server's `ci` user. It
runs only when you start it, only on `main`, one run at a time (`concurrency: production`), and
its deploy job waits in the GitHub environment `production` until you approve it there. That
approval is your go for this deploy; nothing else publishes.

The `ci` user (`setup --ci-key`, M17 Task 9) has no sudo: its key's forced command,
`deploy/ci-gate.py`, admits only what `deploy velometer|datalab` sends and rsync reads of the
snapshot and the tiles. So `setup`, `unlock`, `snapshot`, `golive-check --host`, `stats` and
`deploy tiles` stay on your machine with the `deploy` user. R35 is fixed for CI only: the
`deploy` user keeps its sudo for those (ruling R35-CI).

### Once: what you set up on GitHub

These are settings of the repository; the workflow cannot make them. Run the `gh` line from the
repo root on your machine (it reads the key from pass and sends it to GitHub on stdin; it never
lands in a file):

1. Create the environment `production` (Settings → Environments → New environment) with yourself
   as the required reviewer and no admin bypass: tick *Required reviewers* and add yourself,
   leave *Prevent self-review* off (you start the runs you approve), untick *Allow administrators
   to bypass configured protection rules*, and under *Deployment branches and tags* choose
   *Selected branches and tags* with the one rule `main`.
2. Add the CI key as that environment's secret, from pass:

   ```
   pass velometer/ci-deploy-key | gh secret set CI_DEPLOY_KEY --env production
   ```

3. Turn on branch protection for `main` (Settings → Branches, or a ruleset) requiring the `ci`
   workflow: *Require status checks to pass* with its checks `lint`, `test (1)` to `test (4)`
   and `node`.

### A deploy

Actions → deploy → *Run workflow*, branch `main`, site `velometer`, `datalab` or `both` (both
sites are built and checked either way; only the chosen ones are uploaded). The `gate` job runs
the gate (CLAUDE.md) on that commit first; then the `deploy` job asks for your approval. After
the approval it:

1. adds the `CI_DEPLOY_KEY` secret to an ssh-agent on stdin and trusts only the host key
   committed in `deploy/known_hosts` (`StrictHostKeyChecking yes`, written to the runner's
   `~/.ssh/config`; `tools/server.py` itself only sets `BatchMode`);
2. fetches `/srv/snapshot/velometer.sqlite.gz` and its `.sha256` and the tile file with rsync,
   and stops unless `sha256sum -c` passes for both. The tile file has no `.sha256` on the
   server: its sha256 is the live export's `build.json` `tiles` (the sidecar the export reads,
   `--tiles-info`). After you `deploy tiles` a new extract, that check fails until an export
   naming the new extract is live: deploy velometer once from your machine (below);
3. unzips the database and exports velometer with `--public`, runs `deploy-check --public`, and
   builds the Datalab with `--checked` set to the run's day (UTC; the statement's date for this
   build only, `site.yaml` unchanged);
4. downloads the Caddy release binary `setup` installs, at the version and SHA-512 that
   `deploy/cloud-init.yaml` pins, checks that pin against the release's official
   `caddy_<v>_checksums.txt` and the download against the pin, and serves both builds with it in
   the dry run (§0a, `--caddy-bin`, `--keep-running`); the dry run's probes must report 0
   problems;
5. runs the R64 passes against the dry run: `--pages all --keyboard`, `--pages types --interact
   --flip`, and the Datalab with `--lang de`, then `tools/pass_findings.py` reads every
   `results.json` again: any finding, or a pass that visited nothing, stops the run;
6. tags the export's commit `export-<first 7 hex>` and pushes the tag (§0; the job's token may
   write contents for this only);
7. deploys the chosen sites, `tools/server.py deploy velometer|datalab <dir> --host 2.31.133.185
   --user ci` with one `yes` piped to the prompt, then runs `verify --domain
   zaehlwerk-datalab.de` and a short live pass (velometer `--pages types`, the Datalab
   `--lang de`), held to 0 findings too;
8. writes the job summary: the pass counts, the releases switched, the export tag, the
   statement's date and the run's URL, which is the R64 evidence for this deploy.

Any failing step stops the job (bash `-eo pipefail`; nothing is allowed to fail softly). A
failure before step 7 leaves the server untouched. A failure in step 7 behaves as a local
deploy does: `current` stays on the previous complete release until a switch.

**Not yet runnable (2026-11-03).** The snapshot holds the database only, but the export also
reads `data/maps/` (the tier map PNGs, about 260 MB) and `data/plans/` (the Berlin plan data,
about 185 MB), which are git-ignored and so absent on the runner. Without them the export has no
tier maps and no plan pages and still passes `deploy-check`; the workflow therefore stops at
"The export's other inputs" until the snapshot carries both. The run also needs the dataset DOI
in place, which `deploy-check --public` asks for.

**Time.** About 2 to 3 hours: the gate about 20 minutes, the fetch a few minutes (about 3 GB
from the server), the export and Datalab a minute or two, the full pass with the keyboard pass
(about 1230 visits; about 42 minutes on the development machine) perhaps 60 to 90 minutes on the
runner, the other passes about 15 minutes, the upload a few minutes. That is well under the
6-hour job limit (the job's own limit is 330 minutes), so the passes stay in one job.

### Deploying from your machine (fallback)

When GitHub is not available, or after a new tile extract (step 2 above), deploy from your
machine as in §1 but as the `ci` user, so that every release has the one owner the next CI
deploy can prune (ruling T9-j). Load the key from pass into an agent for ten minutes:

```
eval "$(ssh-agent -s)"
pass velometer/ci-deploy-key | ssh-add -t 600 -
uv run python tools/server.py deploy velometer <dir> --host 2.31.133.185 --user ci
uv run python tools/server.py deploy datalab <datalab-dir> --host 2.31.133.185 --user ci
ssh-agent -k
```

Run the R64 passes on that export first (§1), as always. If a release ever ends up owned by
`deploy` (a deploy without `--user ci`), the next CI deploy cannot remove it when it prunes old
releases: the switch has happened, but the job fails. The repair is to run
`tools/server.py setup --host 2.31.133.185 --domain zaehlwerk-datalab.de --ci-key <ci.pub>` again
(with your go): it finds the releases `ci` does not own and hands them to `ci:releases`, owners
only.

## 3. Cloudflare Pages (not chosen, 2026-10-21)

Chosen on 2026-10-19 and dropped on 2026-10-21: the access logs would sit with a US company
(ADR 0009). Kept for reference; never deployed.

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

## 4. Datenschutz, Impressum and accessibility statement

The Impressum, the Datenschutzerklärung and the voluntary Erklärung zur Barrierefreiheit (R63)
are pages of the Datalab site (`sites/datalab/`, `/impressum/`, `/datenschutz/` and
`/barrierefreiheit/` on the apex), linked from both sites' footers. The
Datenschutzerklärung names Hetzner as the host and processor (the DPA was concluded on
2026-10-28), the masked access logs and their 14 days, the statistics, Let's Encrypt and the
supervisory authority (BlnBDI). `golive-check` refuses while a placeholder or an open legal
decision remains (`docs/review/m16-legal.md`).

Since M16 no page loads anything from another host: the map background is the self-hosted
Protomaps extract, so the OSM tile usage policy no longer applies.
