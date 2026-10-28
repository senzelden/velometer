# M16 live deployment behind the lock

Run on 2026-10-28 (plan Task 9) from the development machine, each outward step with the user's go.
Both sites are on a Hetzner server of our own and answer 401 without the preview password; nothing
is public. Go-live is Task 12.

## Prerequisites

- Domain `zaehlwerk-datalab.de`, registered by the user at INWX (NS `ns.inwx.de`, `ns2.inwx.de`,
  `ns3.inwx.eu`).
- A Hetzner Cloud project of its own for velometer (not shared with other projects: the token
  controls every server in its project, and the deploy key is root-equivalent, ruling R35). The
  token is in pass `velometer/hcloud-token`, the preview password in `velometer/preview-password`,
  both loaded by `.envrc` (`.envrc.example`). SSH key at Hetzner: `dennis-ws` (ED25519, the
  fingerprint matches the local public key).
- `tools/server.py preflight`: both secrets set.

## Server

```
uv run python tools/server.py create --domain zaehlwerk-datalab.de --ssh-key dennis-ws --type cx23 --location fsn1
```

- `cx22`, the tool's default, is no longer offered by Hetzner; `cx23` (2 shared x86 vCPU, 4 GB,
  40 GB disk, EUR 6.53 a month gross plus the IPv4 address) is its successor at the same price
  (ruling R40).
- The first attempt at `nbg1` failed with `412 error during placement` (no capacity). It had
  created the firewall `velometer-web` (id 11914638) before the server; the retry reused it. The
  server was created at `fsn1`, the spec's other German location (ruling R41).
- Server `velometer`, id 173078765: `2.31.133.185`, `2a01:4f8:c016:7b61::1`, Debian 13.
  cloud-init finished (`status: done`), Caddy v2.11.4 installed and not started (no Caddyfile yet),
  time zone `Etc/UTC` (ruling R30).

## DNS

`dns --domain zaehlwerk-datalab.de` printed A and AAAA for the apex, `www` and `velometer`. INWX had
created parking records (`*`, `www` and the apex, A `185.181.104.242`): the user changed the apex
and `www` to the server, deleted the wildcard and added the other four. `dig` at `ns.inwx.de` and
at `1.1.1.1` answered all six; `foo.zaehlwerk-datalab.de` answers nothing. The development
machine's router had cached an NXDOMAIN for the apex from before the registration (DENIC's
negative TTL, 7200 s), so local probes of the apex waited for it to expire; public resolvers were
not affected.

## Setup

```
uv run python tools/server.py setup --host 2.31.133.185 --domain zaehlwerk-datalab.de
```

- Uploaded the Caddyfile, `caddy.env` and the GoAccess configuration, wrote the password lock and
  started Caddy. Let's Encrypt issued certificates for the three names within seconds.
- Run again: "running Caddy serves the password lock", "nothing to change" (the item Task 8 left
  for the server).
- Found: the confirmation cannot be fed from a pipe with one `yes`, because `Target.ssh` runs `ssh`
  with the inherited stdin, which swallows it before the prompt; the run said "Aborted." and
  changed nothing. Fed with `yes yes |` it went through. Fix in Task 11 (`stdin=DEVNULL` when there
  is no input).

## Builds and deploys

The velometer export was made at `d04de95` with the Datalab values in a scratch copy of `config/`
(name "Zählwerk Berlin Datalab", `lang: de`, `https://zaehlwerk-datalab.de/`, its `/impressum/` and
`/datenschutz/`); the repo's `config/site.yaml` stays null until Task 12. Run in the Bash sandbox,
the export was stamped `d04de95-dirty` (the sandbox shows stub files in the working tree); run
outside it, `d04de95`.

```
uv run velometer app export --public --clean --config-dir <scratch>/config --out <scratch>/velometer
uv run velometer app deploy-check <scratch>/velometer --public
uv run velometer datalab build --out <scratch>/datalab --velometer-export <scratch>/velometer
uv run python tools/server.py deploy tiles data/tiles/velometer.pmtiles --host 2.31.133.185
uv run python tools/server.py deploy velometer <scratch>/velometer --host 2.31.133.185
uv run python tools/server.py deploy datalab <scratch>/datalab --host 2.31.133.185
```

- velometer: 798 files, 303.5 MB; `deploy-check --public` ok. Release
  `d04de95-20261028T132851`, then (see below) `d04de95-20261028T145723`.
- Datalab: 20 files, 184 KB, release `d04de95-20261028T133138`; 10 placeholders left (operator
  values the user has not given yet), which `golive-check` refuses.
- Tiles: 898,070,870 bytes in 5 min 30 s; SHA-256 on the server equals the local file's
  (`1bca035e…0197`).

## Live probes

- `verify --domain zaehlwerk-datalab.de --locked`: 0 problems (port 80 answers 308 to https on
  every host; both sites 401 with `Cache-Control: no-store`).
- By hand: TLS verifies on all three names, HTTP/2; IPv6 answers 401; with the password `www`
  answers 308 to the apex and the tile file 206 to `Range: bytes=0-1023` (1024 bytes, HTTP/2);
  without it 401.
- Access log (`sudo tail -1 /var/log/caddy/velometer.log`): `remote_ip` and `client_ip`
  `2604:a880:400::` (masked to /48), no `remote_port`, no `Authorization` or `Cookie`. Both logs
  are `0600 caddy`.
- `render_pass.py --site <scratch>/velometer --base / --url https://velometer.zaehlwerk-datalab.de
  --auth preview:… --pages types --interact --flip` (both themes, 1280/390/320, both editions).
  `--base` must be given: it defaults to `/velometer/`, which 404s on the live site.

### Finding: stale external figures

The first live render pass reported 171 visits, 3 with findings: `/de/city/berlin/figures` had 12
elements marked `data-fallback`. Cause: `config/external/figures.csv` was changed by the press
rewordings (`90c23d6`), but `velometer.sqlite` was not reloaded, so 7 rows (Berlin ×6, Vienna ×1)
still carried the old notes and values (e.g. 140 km for 140.1, 2,400 km for 2,398.3, 5.8 % for
5.84 %, the dpa text as source instead of the Senate's Fahrrad-Fortschrittsbericht). Their German
notes are looked up by the new English text, so the German page fell back to English. The
local M16 render passes had not covered the German figures page with the new CSV.

Fixed with the user's go: `velometer external load --no-qecio --no-bikenetkit` (the curated CSV
only; the QECIO and BikeNetKit rows unchanged, 191 rows in all); afterwards all 65 CSV rows match
the database. `velometer.sqlite` md5 now `bc7225af0cc4b50753c1d73fe19298be`. Re-exported (0 pages
with `data-fallback`), `deploy-check --public` ok, redeployed as `d04de95-20261028T145723`.
Second live render pass: 171 visits, 0 with findings. A guard that fails an export whose database
figures differ from `figures.csv` follows in Task 11.

## Statistics

`stats --host 2.31.133.185` wrote `data/stats/2026-10-28.html` (not in git). It was looked at:
17,689 requests and 40 visitors on the first day, almost all from the render passes; the rest are
scanners (`/.git`, `/api`, `robots.txt`), all answered 401. The one 404 URL, `/velometer/`, is the
first render pass with the wrong base. The report names DB-IP (CC BY 4.0) as required.

## Not claimed

- That `roll_keep_for 336h` deletes rolled logs after 14 days: check on the server after
  2026-11-12.
- Anything about the sites unlocked: `verify` without `--locked`, the go-live render pass and the
  public 404 headers come with Task 12.
- The Datalab pages' legal text with real operator values (placeholders until the user gives them).
