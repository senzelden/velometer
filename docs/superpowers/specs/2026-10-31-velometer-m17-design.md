# velometer M17: findable, citable, and published from GitHub

Status: design, 2026-10-31. Follows M16 (live since 2026-10-30). Rulings go to
`docs/superpowers/rulings-m17.md`, evidence to `docs/review/m17-*.md`.

## 1. Purpose

velometer and the Zählwerk Berlin Datalab are public, but nothing points to them: there's no
`robots.txt`, no sitemap, no description in any page head, and no DOI. In the first day the only
non-us traffic was scanners. M17 makes both sites easy for search engines and AI answer engines
(ChatGPT search, Perplexity, Claude, Google AI Overviews, Copilot) to find, understand and cite.
It gives the code and the data citable DOIs, and moves checks and publishing onto GitHub so that
the public repo is protected and a deploy no longer needs the user's machine.

Who searches (user, 2026-10-31): people looking for an overview of cycling infrastructure and
how each city is doing. Queries like "how good is Berlin's bike infrastructure", "which European
city has the best cycling infrastructure", "Radinfrastruktur Berlin Bezirke". Landing pages: the
home ranking, `/cities`, and each city's story page.

## 2. User decisions (2026-10-31)

1. **Indexing:** every public page, Datalab legal pages included. Downloads (`/data/*`, CSV,
   PNG, GeoJSON), `/tiles/`, `build.json`, `/city/<id>/panel` fragments stay out of the index.
2. **Languages:** the sitemap lists both editions, each URL with `xhtml:link` alternates for
   en, de and x-default (= en).
3. **Generated, not hand-written:** the public export and `datalab build` write their own
   `robots.txt` and `sitemap.xml` from their page lists. `deploy-check --public` (and the Datalab
   equivalent) refuses a sitemap that names a page the build lacks or misses one it has.
4. **AI crawlers welcome,** training crawlers included (GPTBot, ClaudeBot, CCBot,
   Google-Extended, Applebot-Extended), like any other visitor.
5. **GEO is part of it** (generative engine optimisation), and so is a **Zenodo DOI**.
6. **CI and CD on GitHub, both:** checks on every push and PR, *and* publishing without the
   user's machine.
7. **No additional costs: the priority.** No paid service, storage or runner. GitHub Actions
   (free for public repos), Zenodo, Search Console and Bing Webmaster Tools are free. The data
   snapshot lives on the existing Hetzner server (33 GB of 38 GB free on 2026-10-31).
8. **Data stays local:** the user rebuilds `velometer.sqlite` on their machine as now and
   uploads it with one command; GitHub builds from that snapshot and never downloads OSM.

## 3. Facts this design rests on

- **Research 2026-10-31:**
  - Google says AI Overviews need no more than normal indexing, and no special schema or "AI
    files".
  - The only peer-reviewed GEO study (Aggarwal et al., KDD 2024) found that statistics,
    quotations and cited sources in the text raise visibility.
  - `llms.txt` (llmstxt.org) is almost never fetched by AI crawlers: 97% of files got no AI
    request in a 2026 sample. It costs about 20 lines, so we add it, but claim no effect.
  - Google's Dataset guidance asks for `name` and a 50–5000-character `description`, plus
    `license`, `creator`, `identifier` (DOI), `distribution`, `spatialCoverage`,
    `temporalCoverage`, `isBasedOn` and `isAccessibleForFree`. Markup must match visible text.
  - In sitemaps, hreflang alternates must be reciprocal. `lastmod` is used only if accurate;
    `changefreq` and `priority` are ignored.
  - Zenodo: a GitHub release of an enabled repo gives a version DOI plus a concept DOI. If
    `.zenodo.json` exists it overrides `CITATION.cff`; otherwise a valid `CITATION.cff` is used.
- **Repo recon 2026-10-31:**
  - The export's page list is `PAGES` plus `export_urls` (`app/export.py:69`, `:235`). Every
    HTML page has a German twin via `urls.with_lang`.
  - `base.html` already emits hreflang alternates, but as base-relative paths. No meta
    description, OpenGraph tags, canonical (except legacy `/methodology/de`), robots meta or
    JSON-LD exist. The CSP and the export's reference scan already allow `application/ld+json`.
  - No velometer public origin is configured: `config/site.yaml` has no `url`. The domain exists
    only in `sites/datalab/site.yaml`, and `CITATION.cff` hard-codes the velometer URL.
  - Each city story page opens with a plain-text result sentence (the narrative dek,
    `content/narratives/<city>.yaml` and `de/`, for all 21 cities). The home page has a ranking
    table in HTML text.
  - `CITATION.cff`: type software, MIT, version 0.1.0, no DOI. There is no `.zenodo.json` and no
    `.github/`.
  - `velometer.sqlite` is 2.1 GB and `data/tiles` is 857 MB, neither in git. The local gate runs
    about 13 minutes (3585 tests).
  - The server's `deploy` user has passwordless sudo (R35: root-equivalent).

## 4. Design

### 4.1 Crawl files (both sites)

- **`robots.txt` per host** (velometer and apex; `www` already 308s):
  - `User-agent: *`, then `Allow: /`, then `Disallow` lines for the non-index paths of §2.1.
  - A `Sitemap:` line with the absolute URL.
  - No per-bot groups: an unnamed bot is allowed already. A comment line says AI crawlers are
    welcome on purpose.
- **`sitemap.xml` per host:**
  - Every indexable HTML page once per edition, with absolute URLs and reciprocal `xhtml:link`
    alternates (en, de, x-default→en). The Datalab is German-only, so its entries have no
    alternates.
  - `lastmod` = the date the page's content last changed, never the build date.
    - Velometer city pages: that city's OSM snapshot date from `build.json` `osm_timestamps`.
    - Other pages: the date of the last commit touching their template, content or data
      sources. The builder may simplify this, as long as the date is never later than the real
      change and never moves on a no-change rebuild.
- **`llms.txt` on both hosts,** following llmstxt.org:
  - An H1, then a blockquote saying what velometer measures, for which 21 cities, from which
    sources and under which licences.
  - Link lists to the cities, the methodology, the downloads, the repo and the DOIs.
  - English only, with a pointer to `/de/`. No `llms-full.txt`.
- **Gzip:** `.txt` and `.xml` join the export's `GZ_TYPES` (and the Datalab's) so they're
  served precompressed.

### 4.2 Page heads (GEO and SEO)

- **A new required setting `url` in `config/site.yaml`:** the velometer public origin.
  - `export --public` refuses without it, and `build.json` records it.
  - A test checks that `CITATION.cff` `url` equals it (no second source of truth).
- **Absolute URLs:** the hreflang alternates and a `<link rel="canonical">` on every page become
  absolute in public exports. Preview and local builds stay relative.
- **Meta description on every indexable page:**
  - City story: the narrative dek.
  - City tabs: one template sentence per tab with the city's headline figure.
  - Other pages: a sentence per page from `content/ui/{en,de}.yaml`.
  - New reader-facing sentences ship only after the user reviewed them (standing rule); the
    same applies to `llms.txt` and §4.3 text.
- **OpenGraph and Twitter tags:** `og:title`, `og:description`, `og:url`, `og:locale` (+
  alternate), `og:site_name`, `twitter:card=summary`.
  - No `og:image` unless an existing light PNG of that page fits (builder's call). No new image
    generation.
- **JSON-LD** (must match visible text, Google's rule):
  - Home: `WebSite` + one `Dataset` for the whole collection, with:
    - `name`, `description`, `creator` (Person Dennis Senzel), `license` (ODbL 1.0 URL)
    - `isAccessibleForFree`, `spatialCoverage` (the 21 cities), `temporalCoverage` (first
      snapshot to latest)
    - `distribution` (`/data/all.csv`, text/csv)
    - `isBasedOn` (OpenStreetMap, GISCO, Eurostat/INSEE/INE)
    - `identifier` = dataset concept DOI (§4.4)
    - `hasPart` → the city datasets
  - City story page: a `Dataset` per city (its CSV as distribution), `isPartOf` the collection.
  - Methodology: `TechArticle`.
  - Datalab home: `Organization`/`WebSite` naming velometer as its project.
- **Citable text:** the GEO lever with evidence behind it.
  - Every city story page states its headline result in a plain sentence with the figure,
    source and date. The dek mostly does this already; the builder audits all 21 × 2 and
    reports gaps rather than rewriting (rewrites need the user's review).
  - The home page gets one plain sentence naming the current top and bottom city by the
    headline measure.
  - No other prose changes.

### 4.3 Zenodo: two records, two DOIs

- **Software record:** the GitHub–Zenodo integration archives each GitHub release.
  - Metadata comes from `CITATION.cff` only, with no `.zenodo.json`. CI validates it with
    `cffconvert --validate`.
  - The concept DOI goes into `CITATION.cff` `identifiers`, a README badge and the site's cite
    box.
- **Dataset record** (resource type dataset, licence ODbL 1.0), one version per data snapshot:
  - Contents: the public CSV downloads (`all.csv`, per-city and subarea CSVs) plus a data
    README with sources, notices (ADR 0008 texts verbatim) and the classifier version.
  - Related identifiers link it to the software record ("is derived from"/"is supplemented by").
  - Its concept DOI is the JSON-LD `identifier` and appears in the cite box and the download
    page's citation text.
- **The GISCO condition:** it is non-commercial (ADR 0008), and the record must state it.
  - The builder checks that no GISCO geometry goes into the deposit; only numbers do.
  - The builder flags anything that would put a geometry in rather than deciding.
- **Steps only the user can do:**
  - Log in to Zenodo with GitHub and enable the repo.
  - Make the first GitHub release (a go).
  - Create a Zenodo token (`pass insert velometer/zenodo-token`) if the dataset upload is
    scripted.
- **Chicken-and-egg:** a DOI is known only after the first deposit. The dataset record can
  reserve its DOI before publishing. The software concept DOI is added after the first release,
  so the second release carries it, or the record is edited on Zenodo.

### 4.4 CI on GitHub (`.github/workflows/`)

- **`ci.yml`** on push and PR:
  - Runs the gate: ruff format/check, pytest, node tests. Jobs may be split in parallel to stay
    well under the 13-minute local time.
  - Tests that need `velometer.sqlite` or `data/` must skip with a reason, or use small
    committed fixtures.
  - The builder lists which tests are affected. No test may silently pass without its data.
  - `cffconvert --validate` runs too.
- **Pinned actions** (commit SHAs), least-privilege `permissions:`, no secrets in `ci.yml`.
  PRs from forks get no secrets (GitHub's default; don't use `pull_request_target`).
- **Branch protection on `main`** (requires CI green): a GitHub setting the user enables.

### 4.5 CD on GitHub (`deploy.yml`)

- **Trigger:** `workflow_dispatch` (manual) for the default branch, with inputs site
  (velometer|datalab|both).
- **Environment `production`** with the user as required reviewer.
  - The deploy waits until the user approves in GitHub. That click is the user's go and replaces
    the typed go for deploys only.
  - `setup` and `unlock` stay local-only. CI never holds a key that can do them.
- **Steps:**
  1. Gate.
  2. Fetch the data snapshot and verify its sha256.
  3. `export --public` with the public site values, plus `datalab build`.
  4. `deploy-check --public`.
  5. The R64 passes on that exact export, locally in the runner via `tools/deploy_dryrun.py`
     with Caddy 2.11.4 pinned by checksum: full render pass `--pages all` (both themes, 3
     widths) and `--keyboard`.
  6. The `--interact --flip` pass.
  7. Any finding stops the deploy.
  8. Push tag `export-<sha>`.
  9. Upload with `tools/server.py deploy`.
  10. `verify` (unlocked), and a short live render pass.
  11. A job summary with the counts.
- **Public site values in the repo:** a committed `config/site.public.yaml` holds what today's
  scratch config holds. These values are public anyway.
  - The export takes it as an overlay, and the config guard (R58) is extended to accept exactly
    that overlay.
  - This retires the hand-made scratch config. Locally, `export --public` uses the same file.
- **The accessibility statement's date** (`sites/datalab/site.yaml` `accessibility.checked`)
  must stay true (R64).
  - The workflow sets it to the run's date in the build only, not in git, after the passes
    succeed.
  - It also records the run URL in the job summary as evidence. The builder may instead commit
    the date back; that's their call, stated.
- **Deploy key without root (fixes R35 for CI):**
  - A new server user `ci` with its own SSH key, no sudo, and `restrict` options in
    `authorized_keys`.
  - It owns `/srv/{velometer,datalab}/releases` and the `current` symlinks. `deploy` already
    needs only rsync plus an atomic symlink switch; no sudo for that path.
  - `setup` creates the user and ownership; that is one local `setup` run, with the user's go.
  - The private key goes into the `production` environment secret, created from `pass`
    (`velometer/ci-deploy-key`). It is never written to a file.
  - The pinned server host key is a committed `known_hosts` line, not trust-on-first-use.
- **Snapshot:**
  - A new `tools/server.py snapshot --host`, run locally after a data rebuild, uploads
    `velometer.sqlite` (gzip) and its sha256 to `/srv/snapshot/` on the server.
  - That directory is outside every Caddy root and must never be served; a test asserts the
    Caddyfile doesn't. The `ci` user may read it.
  - The tiles stay on the server, and the workflow checks their sha256 against `build.json`
    `tiles`.
- **Concurrency:** one deploy at a time (`concurrency: production`).

### 4.6 Search registration (user steps, free)

- **Google Search Console and Bing Webmaster Tools:** verify and submit both sitemaps.
  - Verification by a DNS TXT record at INWX, where the user manages DNS (see `server.py dns`).
    No meta tag or file in the build, so no code depends on it.
  - One Search Console *domain* property for `zaehlwerk-datalab.de` covers the apex, `www` and
    `velometer.`, so there is one TXT record. Bing can import it from Search Console.
- **IndexNow:** not in M17. It's optional, and Bing finds the sitemap.

### 4.7 Settled after the builder check (2026-10-31)

Answers from the conversation or the repo, or my calls (marked).

1. **Origin values.**
   - `site.url` = `https://velometer.zaehlwerk-datalab.de/`; the Datalab is the apex.
   - `CITATION.cff` is correct; the new test only keeps them equal.
2. **What `site.public.yaml` holds:** exactly today's scratch `site.yaml` values.
   - Keys: Datalab name and URL, the Impressum, Datenschutz and Barrierefreiheit URLs, the repo
     URL and file URL, plus the new `url`.
   - All of them are visible on the live pages. Operator data lives in
     `sites/datalab/site.yaml`, already committed.
   - Nothing private moves into git. R58 is extended from "site.yaml aside" to "site.yaml or the
     committed public overlay".
3. **Render passes on the runner** *(my call).*
   - The deploy job fetches the data snapshot *and* the tiles from the server over the `ci` key
     (both sha256-checked). That traffic is free within Hetzner's 20 TB.
   - A runner has ~14 GB of free disk and a 6 h job limit. The full pass plus keyboard, about 1250
     visits, fits; Playwright's Chromium and Caddy are installed per run, Caddy pinned by checksum.
   - If a single job can't finish, the builder splits passes across parallel jobs on the same
     export artifact. The pass never moves back to the user's machine.
4. **What `ci` may do** *(my call).*
   - Only `deploy velometer|datalab` (rsync with `--link-dest`, then an atomic symlink switch,
     with no sudo) and reading `/srv/snapshot/` and `/srv/tiles/`.
   - `verify` probes over HTTP only and needs no key.
   - Everything that reads the lock or Caddy (`setup`, `golive-check --host`, `stats`, `unlock`,
     `deploy tiles`) stays local with the `deploy` user. The builder adds a no-sudo deploy path,
     not a no-sudo `server.py`.
   - Restriction: `restrict` in `authorized_keys`, plus a forced-command wrapper that permits
     only the rsync and `ln`/`mv` forms deploy uses. The builder may choose the wrapper's form.
5. **Ownership migration:**
   - The one `setup` run creates group `releases`, adds `ci` and `deploy` to it and makes
     `/srv/*/releases` group-writable (setgid). Files must stay readable by `caddy`, same modes
     as today's `RSYNC_CHMOD`.
   - It touches no file content and doesn't switch `current`, so the live site stays up.
   - `deploy` keeps working, which is the fallback from the user's machine.
   - Proof: a test of the setup script, and a dry run under the existing `deploy_dryrun`
     harness.
6. **Tests in `ci.yml`.** The existing synthetic fixtures (`tests/report_fixture.py`) are the
   CI data.
   - All new robots, sitemap, canonical, JSON-LD and llms tests use them and run on every PR.
   - Tests that need the real `velometer.sqlite` skip with a named reason. The builder lists
     them in the evidence, and a guard test fails if a skip appears without a reason.
   - The real export runs only in `deploy.yml`.
7. **Dataset deposit** *(my call: manual, no token).*
   - A new `velometer dataset bundle` writes the zip (CSVs plus data README with the ADR 0008
     notices) and the Zenodo metadata as a text sheet.
   - The user uploads it on Zenodo by hand, once per data snapshot (rare). The first deposit
     reserves the DOI.
   - No Zenodo token and no new secret. Scripting it can come later.
8. **Licence of the CSVs:**
   - ODbL 1.0, as ADR 0008 already records for derived data, with the other credits in each
     CSV preamble.
   - The record's description repeats the GISCO non-commercial condition and the
     Eurostat/INSEE/INE credits verbatim. JSON-LD `license` = the ODbL URL.
   - Any doubt is reported, not decided.
9. **`accessibility.checked`:** each deploy run executes the *full* R64 passes, so the run date
   is a true "Stand".
10. **`lastmod`:**
    - From git history, with `fetch-depth: 0` in the deploy job.
    - Locally the same function runs on the full clone.

## 5. Out of scope / non-goals

- **Anti-goals:**
  - Any paid service.
  - Anything that publishes without the user's approval.
  - Any change to figures or methodology.
  - Rewriting city narratives without review.
- **Non-goals:**
  - Data refresh on GitHub.
  - `llms-full.txt`.
  - Per-bot robots groups.
  - New images.
  - IndexNow.
  - Analytics beyond M16's GoAccess.

## 6. Execution order

1. `site.url`, and absolute canonical and hreflang.
2. robots, sitemap and llms, with deploy-check.
3. Meta descriptions and OpenGraph: drafts to the user for review.
4. JSON-LD, with a DOI placeholder that fails closed in `--public` until set.
5. CI workflow plus test data handling.
6. Server `ci` user and snapshot (local `setup`, user's go).
7. `deploy.yml` plus the `production` environment.
8. Zenodo (user's login and first release), then DOIs into `CITATION.cff`, README, cite box and
   JSON-LD.
9. First deploy through GitHub.
10. Search Console and Bing registration.

## 7. Accept

- Gate green locally and on GitHub.
- For both sites:
  - The live `robots.txt`, `sitemap.xml` and `llms.txt` answer 200.
  - Every sitemap URL answers 200, and every alternate pair is reciprocal (a test on the build,
    a probe live).
- Google's Rich Results test shows valid `Dataset` markup on the home and a city page.
- Both DOIs resolve, and the dataset DOI's record holds the CSVs and notices.
- One deploy ran end to end on GitHub after the user's approval click:
  - the R64 passes had 0 findings;
  - `verify` had 0 problems.
- The `ci` key cannot run `sudo` (tested on the server).
- No new monthly cost.
