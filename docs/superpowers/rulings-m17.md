# M17 rulings

M17 makes velometer findable, citable and published from GitHub.
- Spec: `docs/superpowers/specs/2026-10-31-velometer-m17-design.md`.
- Plan: `docs/superpowers/plans/2026-10-31-velometer-m17.md`.
- SDD ledger, briefs, reports and reviews: `.superpowers/sdd/2026-10-31-velometer-m17/`
  (git-ignored scratch).

The committed evidence:
- `docs/review/m17-text.md`, every new or changed reader-facing text, as the user approved it;
- `docs/review/m17-ci.md`, the CI workflow's first runs on GitHub;
- `docs/deploy.md` §2, the CD route and the fallback deploy.

Each execution ruling reads: Ruling — why — cost if wrong. `tests/test_m17_rulings.py` holds every
ruling ID that the code, tests and docs cite to an entry here (or in `rulings-m16.md` for M16
IDs).

## User decisions

- **2026-10-31:** the spec approved ("Do so"); the decisions of spec §2 (indexing, both
  languages, generated crawl files, AI crawlers welcome, GEO and a Zenodo DOI, CI and CD on
  GitHub, no additional costs, data stays local).
- **2026-11-01:** spec §4.8 approved (home lead, terms registry and glossary, own SVG tier
  diagrams, the city story page as one scroll on phones); execution order 1-4, 13-16, 5-12.
- **2026-11-02:**
  - "Yes, fix the small items": yes to T13b, yes to X1 (fix the URLs, not the server), the
    deferred minors fixed now (U1).
  - Push of `m17` for the first CI run.
  - The open points of the review batch: (1) long deks get ≤160-character descriptions, drafted
    with their caveats; (2) Zenodo licence `odbl-1.0` with the GISCO condition in the description
    and README; (3) ECF joins the glossary; (4) tier letters marked at the first use per section
    only; (5) the llms.txt wording "(one per year since 2018, plus the current state)", the CSV
    link kept; (6) captions "typically" (A) and "such as" (C); (7) "Radwegtypen" kept; (8) the
    home lead tightened; (9) the phone "over time" section is the tier mix (T16a confirmed);
    (10/11) the methodology correction approved, German "alle Radfahr- und Schutzstreifen als eine
    Klasse"; the rest of `m17-text.md` approved.
- **2026-11-03:**
  - Home lead, ECF entry and the 14 cities' descriptions approved; Copenhagen (de) "Knick"
    replaced (CPH-1).
  - The ban on `rm -rf` lifted.
  - The CI key made by the user (`pass velometer/ci-deploy-key`); `setup --ci-key` and
    `snapshot` run by the user; GitHub environment, secret and branch ruleset set by the user.
  - Push of `m17` at bd61b88; draft PR #1 into `main`.
  - **M3-robots** (below): keep `Disallow: /data/`, open the chart and search JSON.

## Pre-flight rulings

- **P1.** Task 1 takes the site values from the live `build.json` `site` block (the plan's
  stated fallback): the old scratch config no longer exists — cost: a stale value, which
  deploy-check and golive-check catch.
- **P2.** The terms wrapper (Task 13) never touches `<head>`, `<script>`, `<style>` or `<svg>`,
  so later JSON-LD and meta tags cannot be altered — cost: none expected.
- **P3.** Task 6 drops its duplicate home-sentence test (Task 15 owns the rule) and asserts only
  JSON-LD consistency — the rule stays tested once — cost: none.
- **P4.** The Task 5 review batch goes to the user with the Task 8 push request, as one stop;
  Tasks 6-7 run before it, since nothing merges before the review — cost: rework of Task 6-7
  strings if the user changes the lead or the terms.

## Execution rulings

- **R1.** (Extends M16 R58.) The public site values, `url` included, are committed in
  `config/site.public.yaml`; `load_site(config_dir, public=True)` merges it over `site.yaml` key by
  key, and only `export --public` asks for it. The config guard therefore exempts no file: the
  scratch copy of `config/` is retired, and a config directory must equal HEAD's `config/`
  — cost: the overlay holds public values only (tested), so a private value must never go in it.
- **T1.** The Datalab name in the overlay test comes from `sites/datalab/templates/base.html`
  (`site.yaml` `name` is the operator's person name) — cost: the test follows a template string.
- **T3a.** A public export raises `ConfigError` when `lastmod` cannot come from git (a shallow
  clone, no git, no history for a page's sources) instead of falling back; the CI and deploy
  workflows check out with `fetch-depth: 0` — a fallback date would be later than the real
  change — cost: a CI export fails loudly until the checkout depth is fixed.
- **T4a.** The Datalab's sitemap entries carry no `<lastmod>`: four static legal pages, with no
  per-page change date and no git dependency — cost: crawlers get no recency hint there.
- **T5a.** No mechanical cutting of deks. A dek of ≤160 characters is the description; a longer
  one falls back to the `meta.city` sentence; `m17-text.md` lists each such city so the user can
  shorten its dek — "description = dek" and "50-160" cannot both hold for long deks, and a cut
  can drop a caveat (ADR 0006) — cost: those pages get the generic sentence until shortened.
- **T13a.** Tier letters are marked only after "tier(s)" / "Stufe(n)" (table headers "A km…E km"
  unmarked; "A+B km" marked) — avoids false hits such as "A city" — cost: the user asks for
  header marks.
- **T13b.** The stale tier-B sentence in the generated methodology is live prose outside §4.8,
  not changed without the user's go; raised to the user (who said yes on 2026-11-02, Task 2c)
  — cost: none after the go.
- **T16a.** The phone section "over time" shows the tier composition over time, not the headline
  chart, which sits directly above in the aside — cost: the user asks for the headline chart
  (the user confirmed the tier mix on 2026-11-02).
- **X1.** Every absolute URL M17 emits uses the form the server answers 200 for: a page exported
  as `<dir>/index.html` gets a trailing `/` (`/` and `/de/` unchanged; files unchanged), decided
  by one helper (`urls.absolute_url`) and tested over the whole fixture export. Internal relative
  links (308 on click) stay out of scope — Caddy's file server redirects the slashless form —
  cost: one more rework if the user prefers to change the server.
- **U1.** Task 2b gets two companions before Task 8: Task 2c (the methodology's tier-B sentence)
  and Task 2d (the code and test minors of the ledger). Minors that are wording choices stay for
  the review batch, not changed silently — cost: the user asks for them after the batch.
- **2d-a.** The 9 English descriptions that were verbatim copies of the dek are dropped: an absent
  English description means the dek, and the German description's stamp source is the English
  description when present, else the dek — removes the duplicate rather than guarding it — cost:
  one stamp-model change in translate/check.
- **CPH-1.** Copenhagen (de): "Knick" became "…der Rückgang bei Geh- und Radwegen 2025: neu
  getaggt." (159 characters; "war eine Tag-Änderung" was 168), the nearest wording that fits;
  the user was told — cost: one string.
- **T9-a.** The gate (`deploy/ci-gate.py`) is also `ci`'s login shell: sshd runs a forced command
  through the login shell, so `nologin` would break it, and even a key added without `command=`
  lands in the gate; no sshd `Match` drop-in, which could lock out `deploy` — cost: none known,
  proved in the container.
- **T9-b.** Existing releases and `current` are handed to `ci:releases`, owners only; modes stay
  `RSYNC_CHMOD`. Release directories are 0755, so only their owner can prune them; `/srv/<site>`
  stays deploy-owned but `releases` 2775, for the `mv -T` of the switch — cost: without the
  hand-over the first CI prune fails.
- **T9-c.** `authorized_keys` and `~/.ssh` of `ci` are root-owned: `ci` cannot change its own
  key — cost: none.
- **T9-d.** The snapshot goes up as `deploy` (via sudo): through deploy's home, then
  `sudo install` 0640 root:ci and an atomic `mv`, the sha256 written last and checked on the
  server; a CI fetch racing an upload sees a mismatch and fails closed — cost: none known.
- **T9-e.** `setup --ci-key` does not reload Caddy when only `ci` things change — cost: none.
- **T9-f.** The gate refuses `rm` of the release `current` points to (defence in depth) — cost:
  none.
- **T9-g.** rsync option letters are allowlisted: the workflow fetches with plain options (none,
  `-t`, `-a`, `-av`, `--checksum`, `--partial`), never `-s`/`--protect-args`, `-L`, `-R` or
  filters — cost: a workflow change that needs another option is refused until the gate admits it.
- **T9-h.** `deploy/known_hosts` holds one ed25519 line for exactly the host CD connects to
  (`deploy.yml` `HOST`); the tests hold the two files equal, not to a literal address (final
  review M2) — cost: none; a server move changes both files.
- **T9-i.** The receiver flag set drops `l` and `D` (the sender keeps them), `RSYNC_SITE` is
  `-rp`, `deploy_site` refuses an export holding any symlink or non-regular file, and the gate
  appends `--munge-links` on receive; `/home/ci` is `root:root` — a stolen CI key could otherwise
  plant symlinks Caddy follows (TLS keys, logs) or a FIFO — cost: none known, an export has no
  symlinks.
- **T9-j.** Fallback deploys from the user's machine run as `--user ci` with the pass key in an
  agent, so every release has one owner; re-running `setup --ci-key` is the documented repair
  (`docs/deploy.md` §2); group-writable modes are rejected (spec: same modes) — cost: a release
  owned by `deploy` makes the next CI prune fail until repaired.
- **R35-CI.** M16's R35 (deploy needs sudo) is fixed for CI only: `ci` has no sudo, and the
  `deploy` user keeps its sudo for `setup`, `unlock`, `snapshot`, `stats`, `golive-check --host`
  and `deploy tiles` — those need root and run with the user's go — cost: the local route stays
  root-equivalent, as in M16.
- **T10-a.** The gate is its own job before the approval, read-only with no secret; the approval
  request appears only for a commit that passed it — cost: about 20 minutes more per deploy than
  sharding.
- **T10-b.** `printf 'yes\n' |`, not `yes yes |`: under `-o pipefail`, `yes` ends with SIGPIPE
  once the prompt has read its line and fails a deploy that succeeded — cost: none.
- **T10-c.** The ssh trust goes into the runner's `~/.ssh/config` with a copy of
  `deploy/known_hosts`; `server.py` is unchanged and the checkout stays clean for `deploy
  datalab`'s dirty-tree check — cost: none.
- **T10-d.** The tiles' sha256 comes from the live `build.json` (spec §4.5); after `deploy tiles`
  of a new extract, CD fails the tile check until one velometer deploy from the user's machine
  names it — cost: that one local deploy per extract.
- **T10-e.** The Caddy pin (version, SHA-512) is read from `deploy/cloud-init.yaml`, checked
  against the official checksums file, and the verified binary is mounted into the pinned image
  (`--caddy-bin`) — one source of the pin — cost: none.
- **T10-f.** Both sites are always built and checked; the `site` input picks only what is
  uploaded; the live pass covers the deployed sites — cost: a few minutes per run.
- **T10-g.** `tools/pass_findings.py` is a small committed tool, not inline YAML, so the
  0-findings rule is tested — cost: none.
- **T10-h.** Environment step 1 adds "Prevent self-review" off (the sole reviewer approves their
  own runs) and the deployment-branch rule `main`; step 3 names the `ci` jobs' check names —
  GitHub requires job checks — cost: none.
- **T10-i.** `render_pass` resolves a public export's alternates on the server it audits (F1),
  as a separate commit; without it no R64 pass of a public M17 export passes the dry run — cost:
  none.
- **T10-B1.** `server.py snapshot` also publishes a data archive (`data/maps` + `data/plans`)
  with its `.sha256`, the gate reads it, the workflow fetches and verifies it, and `export
  --public` refuses empty maps or plans — "CD publishes the same site" needs these inputs and the
  snapshot held only the DB — cost: about 230 MB more per snapshot upload.
- **T10-N1.** The data archive's listings are captured (`tar -tvzf`, `tar -tzf`) before any check
  reads them, two captures rather than one parsed listing — a tar error inside a pipe or an `if`
  failed open, and splitting `-tv` columns breaks on names with spaces — cost: one more read of
  the archive.
- **FINAL-1.** The final whole-branch review runs before the merge, since the merge is what goes
  public; Tasks 11 and 12 follow as small task-reviewed commits on the PR — cost: one extra
  review of the Task 11/12 diff.

## Final review fix wave (2026-11-03)

- **M3-robots.** The user's decision: robots.txt keeps `Disallow: /data/` (the downloads stay
  out of the index, spec §2.1) and allows exactly the JSON the page scripts fetch to draw the
  charts and the search (`/data/series.json`, `/data/search.json`, `/de/data/search.json`), so
  Googlebot renders the pages as a reader sees them; the Allow lines come first for first-match
  crawlers, and a test derives the paths from the scripts — cost: those JSON files may be crawled
  (and, rarely, listed); the tier-map GeoJSON under `/maps/` stays disallowed.
- **FIX-1.** Nested JSON-LD objects are never incomplete `Dataset`s: `hasPart` and `isPartOf`
  are page URLs (Google accepts a URL or a full `Dataset`; its own example uses a URL), and the
  `isBasedOn` sources are `CreativeWork`s — Google validates every `Dataset` in the graph and
  requires `name` and `description` — cost: the graph links the collection and the cities by page
  URL, not by `@id`.
- **FIX-2.** A `Dataset`'s `description` is text the page shows (spec §3): the home lead's first
  sentences (`page.index.lead.what`) and a city's dek (50-5000 characters, else the page's meta
  description); the meta descriptions stay as they are — cost: a dek over 5000 characters, or
  under 50, falls back to the meta description.
- **FIX-3.** A page's `lastmod` sources are its templates with every template they extend,
  include or import (found by parsing them), the UI catalogue (every page shows its strings) and
  the page's own content; the shared registries every page reads (all narratives, sources and
  organisations for the citation numbering, the series payload) count only for their own pages
  — listing them everywhere would date every page by any narrative edit — cost: a page whose
  cited-source numbering changes with another page's edit keeps an earlier date.
- **FIX-4.** `build.json` `site` records both DOIs; llms.txt names the configured ones, and
  `deploy-check --public` holds the home page's JSON-LD identifier and llms.txt to the build's
  dataset DOI (a Zenodo DOI) — the check judges the export, not today's config — cost: an export
  made before this change has no DOI in `build.json` and must be made again.
- **FIX-5.** `docs/deploy.md` defines its values once as shell variables (`DOMAIN`, `SERVER`,
  `EXPORT`, `DATALAB`, `SHOTS`; `SERVER`, not `HOST`, which zsh sets itself), so every shell
  block runs as written; the Caddy lock texts are tagged `caddy` — cost: a reader in a new shell
  sets the variables again.
