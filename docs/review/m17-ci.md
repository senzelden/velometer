# M17 CI on GitHub (`ci.yml`)

Plan Task 8, spec section 4.4. `.github/workflows/ci.yml` runs the gate on every push and pull
request from a fresh checkout. Guarded by `tests/test_m17_workflows.py`.

## The workflow

- Triggers `push` and `pull_request`; no `pull_request_target`, so PRs from forks get no secrets.
- `permissions: contents: read` for the whole workflow; `ci.yml` uses no secrets.
- Every action is pinned to the commit of its release tag, resolved with `git ls-remote` on
  2026-11-02 (tags are lightweight, so no peeled `^{}` line):

  | Action | Tag | Commit |
  |---|---|---|
  | `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
  | `astral-sh/setup-uv` | v10.3.3 | `68559e99cc807c1eb7e9238fd43a15bba460eec2` |
  | `actions/setup-node` | v7.1.0 | `949feb2413d6458794dcd2491c4babbbce0c15c1` |

- Every checkout has `fetch-depth: 0`: sitemap `lastmod` comes from git history and raises on a
  shallow clone (ruling T3a). `persist-credentials: false`, since no job pushes.
- Jobs, all on `ubuntu-24.04`:
  - `lint`: `uv run ruff format --check .`, `uv run ruff check .`,
    `uvx cffconvert==2.0.0 --validate` (`CITATION.cff`).
  - `test`: `uv run pytest` in four shards (matrix `shard: [1, 2, 3, 4]`,
    `VELOMETER_TEST_SHARD=k/4`). `pytest-xdist` is not a dev dependency, so `tests/conftest.py`
    keeps the test files whose crc32 of the repo-relative path falls in shard k
    (`tests/shard.py`). Sharding by file keeps module-scoped fixtures in one shard. The serial
    suite takes about 14.5 minutes locally.
  - `node`: `node --test "src/velometer/app/static/js/tests/*.test.mjs"`.
- Python comes from `.python-version` (3.14) through uv, Node is 24 (the local version; the repo
  pins none). The `test` job installs `osmium-tool` and `poppler-utils` so the tests that call
  them run instead of skipping; Chrome, Docker, git and npx are on the runner image already.

## What a fresh checkout lacks

`velometer.sqlite`, `data/` (boundaries, extracts, stats, tiles), `reports/`, `research_notes/`,
`tools/out/`, `.superpowers/`, `.envrc` and any `dist/` or export output. All tests build what they
need from committed fixtures (`tests/report_fixture.py`, `tests/fixtures/`) in `tmp_path`.

## Tests that skip without velometer.sqlite

None. No test reads the real database; the suite in a fresh clone (no database, no `data/`)
passes with only the one skip below. A test that needs the database later takes
`@pytest.mark.skipif(not DB.exists(), reason="needs velometer.sqlite (not in git)")` and is listed
here as `` - `tests/<file>.py::<test>` ``; `test_skips_have_reasons` fails until the list and the
marks agree, and refuses a runtime `pytest.skip` that names the database.

## Other skips in CI

- `tests/test_epsg_stored.py::test_stored_admin_boundaries_pass_the_epsg_check`: "no
  data/boundaries in this checkout". It reads the stored boundaries, which are gitignored; it
  runs on the development machine.

Tests that skip without a tool (osmium, poppler, Chrome, node, Docker, npx) all name the tool.
Slow tests (`@pytest.mark.slow`, network or Docker) are deselected by default, as locally.

## Local runs

- **Fresh clone, the way CI sees it** (2026-11-02): `git clone` of the repo into a scratch
  directory (full history; no `velometer.sqlite`, no `data/`, no untracked files), the Task 8
  files copied in, `uv sync --frozen`. Lint (`ruff format --check`, `ruff check`,
  `cffconvert==2.0.0 --validate`) green; node 0 skipped, all pass; pytest in the four shards
  side by side:

  | Shard | Passed | Skipped | Time |
  |---|---|---|---|
  | 1/4 | 973 | 0 | 2:29 |
  | 2/4 | 1137 | 0 | 7:04 |
  | 3/4 | 801 | 1 (`test_epsg_stored`, no `data/boundaries`) | 1:51 |
  | 4/4 | 925 | 0 | 3:05 |

  3837 tests in all, each in exactly one shard: the serial run of the clone before this task
  ran 3824 (3823 passed, the same 1 skipped), plus this task's 13. Shard 2 is the long one; the four ran on one machine at once.
- **Development checkout with the database and `data/`** (2026-11-02): the full gate green,
  pytest 3837 passed, 0 skipped (13:31 serial), node 335 passed; `velometer.sqlite` md5
  unchanged.

## GitHub run

**TODO (after the user's go to push `m17`):** run URL and duration.

- Run URL: _pending_
- Duration: _pending_
