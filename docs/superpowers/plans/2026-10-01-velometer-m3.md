# velometer M3 (history 2018–2026) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a yearly (1 January 2018–2026) time series of every M2 metric for the 5 pilot cities, with mapping-activity and tag-drift diagnostics, flagged years with enforced explanations, and FUA runs for Berlin and Paris.

**Architecture:**
1. Log in to Geofabrik's internal server with the user's OSM account (credentials from the environment only).
2. Fetch the per-region `.osh.pbf` history and merge regions where a boundary needs several.
3. Clip the history once per city and boundary, then `osmium time-filter` one snapshot per date.
4. Feed each snapshot through the unchanged M2 pipeline as a run with `source='history'`.
5. Activity aggregates are computed from the same clipped history. Flags and the time-series report are pure functions over runs plus activity.

**Tech Stack:** Python 3.14, uv, httpx, pyosmium, osmium-tool 1.19 (`merge`, `extract --with-history`, `time-filter`), shapely, SQLite (schema v5), Typer, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-velometer-m3-design.md`. Also read `docs/superpowers/rulings-m2.md` and `docs/adr/0005-annual-snapshots-versioned-classifier.md`.

## Global Constraints

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest`. Ruff line length is 100.
- Network tests are `@pytest.mark.slow` and deselected by default. Default tests never touch the network or spend money.
- Lengths are computed only in the city's projected EPSG.
- Never type OSM ids from memory; query them.
- Credentials:
  - They come only from `VELOMETER_OSM_USER` and `VELOMETER_OSM_PASSWORD`, wired by direnv `use_pass` from `pass` entries `velometer/osm-username` and `velometer/osm-password`.
  - Never write them to a file, log, exception message or test fixture.
  - The cookie file `data/auth/geofabrik_cookie.json` is mode 0600 and holds no password.
- Mapper data is aggregated only. OSM uids and user names never reach the DB, files or logs.
- Population for every history year is the 2024 value, labelled "population 2024 held constant".
- Classifier `v1` is frozen. Never edit `config/classifier/v1.yaml`.
- Snapshot dates are `YYYY-01-01T00:00:00Z` for 2018 to 2026. History runs store `osm_timestamp` in exactly that form.
- Never commit `data/` or `velometer.sqlite`. Stage explicit paths only; never `git add -A`.
- Each commit ends with exactly one trailer line, `Assisted-by: Claude:<model-id>`, where the model id is that of the agent that wrote the commit.
- No email address appears in any file or header. `VELOMETER_CONTACT` stays unset.

## Review Focus

1. **An expired or rejected cookie mid-download.** `fetch_history` must log in again once and retry. It must not loop or keep a half file. Test: Task 3, `test_fetch_history_relogs_once_on_403`.
2. **A way that left the boundary after 2018.** The clipped history must keep its old versions, so the 2018 snapshot counts it. Test: Task 4, `test_city_history_keeps_way_that_left_boundary`.
3. **A rerun after a newer history download.** A different history-set md5 must give new runs, never reuse the old ones, and never mix two history sets in one series. Test: Task 7, `test_new_history_set_makes_new_runs_and_series_uses_one_set`.
4. **Current runs and history runs side by side.** `latest_done_run` (M2 reports) must still return the current run, never a history run. Test: Task 2, `test_latest_done_run_ignores_history_runs`.
5. **A city with zero cycling edits in a year.** Activity must store zeros, not skip the year, and `top_mapper_share` must be 0.0, not a division error. Test: Task 5, `test_year_without_edits_stores_zeros`.

---

### Task 1: Geofabrik OAuth login and `auth check`

**Files:**
- Create: `src/velometer/sources/geofabrik_auth.py`
- Create: `.envrc.example`
- Modify: `src/velometer/cli.py` (add an `auth` sub-app with `check`)
- Test: `tests/test_geofabrik_auth.py`

**Interfaces:**
- Produces:
  - `AuthError(RuntimeError)`
  - `Cookie(name: str, value: str, expires: datetime)`, a frozen dataclass with `.header() -> str` returning `name=value`
  - `CONSUMER_URL = "https://osm-internal.download.geofabrik.de/get_cookie"`
  - `OSM_HOST = "https://www.openstreetmap.org"`
  - `login(user: str, password: str, *, client: httpx.Client) -> Cookie`
  - `cookie_path(data_dir: Path) -> Path`
  - `save_cookie(c: Cookie, data_dir: Path) -> None`
  - `load_cookie(data_dir: Path, *, now: datetime) -> Cookie | None`
  - `load_or_login(data_dir: Path, *, client: httpx.Client, now: datetime | None = None, force: bool = False) -> Cookie`, which reads the credentials from the env
  - `credentials_from_env() -> tuple[str, str]`

The flow mirrors Geofabrik's documented `oauth_cookie_client.py`, re-implemented in httpx rather than vendored:
1. `POST CONSUMER_URL?action=get_authorization_url` returns JSON with `authorization_url`, `state`, `redirect_uri` and `client_id`.
2. `GET OSM_HOST/login?cookie_test=true` returns a page holding `authenticity_token`.
3. `POST OSM_HOST/login` with username, password, `referer=/`, `commit=Login` and the token must answer 302.
4. `GET authorization_url` without following redirects. A 302 means already authorised. A 200 means the form must be posted: `client_id`, `redirect_uri`, `authenticity_token`, `state`, `response_type=code`, `scope=read_prefs`, empty `nonce`, `code_challenge` and `code_challenge_method`, and `commit=Authorize`. That post must answer 302.
5. The `location` of the 302 must contain `?`.
6. `GET OSM_HOST/logout`.
7. `GET <location>&format=http` returns a body like `gf_download_oauth=<value>; expires=<RFC 1123 date>; ...`. Parse the `name=value` up to the first `;` and `expires=` if present. If `expires` is missing, use now + 24 h.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_geofabrik_auth.py
import json
import os
import stat
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from velometer.sources import geofabrik_auth as A

LOGIN_PAGE = '<form><input name="authenticity_token" value="tok123" type="hidden"></form>'
AUTHZ_PAGE = '<form><input type="hidden" name="authenticity_token" value="tok456"></form>'
SECRET = "s3cr3t-pw"


def _transport(calls, *, authorised=False, login_status=302, expires="Sat, 03 Oct 2026 12:00:00 GMT"):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, str(req.url)))
        url = str(req.url)
        if url.startswith(A.CONSUMER_URL) and "get_authorization_url" in url:
            return httpx.Response(200, json={
                "authorization_url": A.OSM_HOST + "/oauth2/authorize?x=1",
                "state": "st", "redirect_uri": A.CONSUMER_URL, "client_id": "cid"})
        if url.startswith(A.OSM_HOST + "/login") and req.method == "GET":
            return httpx.Response(200, text=LOGIN_PAGE)
        if url == A.OSM_HOST + "/login" and req.method == "POST":
            body = req.content.decode()
            assert "tok123" in body
            return httpx.Response(login_status, headers={"location": A.OSM_HOST + "/"})
        if url.startswith(A.OSM_HOST + "/oauth2/authorize"):
            loc = {"location": A.CONSUMER_URL + "?code=c&state=st"}
            if authorised or req.method == "POST":
                if req.method == "POST":
                    assert "tok456" in req.content.decode()
                return httpx.Response(302, headers=loc)
            return httpx.Response(200, text=AUTHZ_PAGE)
        if url.startswith(A.OSM_HOST + "/logout"):
            return httpx.Response(302, headers={"location": A.OSM_HOST + "/"})
        if url.startswith(A.CONSUMER_URL + "?code="):
            assert "format=http" in url
            return httpx.Response(200, text=f"gf_download_oauth=abc.def; expires={expires}; Path=/")
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def test_login_runs_the_oauth_flow_and_parses_the_cookie():
    calls = []
    with httpx.Client(transport=_transport(calls)) as c:
        cookie = A.login("me", SECRET, client=c)
    assert cookie.name == "gf_download_oauth" and cookie.value == "abc.def"
    assert cookie.expires == datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
    assert cookie.header() == "gf_download_oauth=abc.def"
    assert ("POST", A.OSM_HOST + "/oauth2/authorize?x=1") in calls  # form posted when not authorised


def test_login_skips_the_form_when_already_authorised():
    calls = []
    with httpx.Client(transport=_transport(calls, authorised=True)) as c:
        A.login("me", SECRET, client=c)
    assert not any(m == "POST" and "authorize" in u for m, u in calls)


def test_failed_login_raises_without_the_password():
    with httpx.Client(transport=_transport([], login_status=200)) as c:
        with pytest.raises(A.AuthError) as e:
            A.login("me", SECRET, client=c)
    assert SECRET not in str(e.value) and SECRET not in repr(e.value)


def test_missing_expiry_defaults_to_24h():
    with httpx.Client(transport=_transport([], expires="")) as c:
        before = datetime.now(UTC)
        cookie = A.login("me", SECRET, client=c)
    assert before + timedelta(hours=23) < cookie.expires < before + timedelta(hours=25)


def test_cookie_file_is_private_and_has_no_password(tmp_path):
    c = A.Cookie("gf_download_oauth", "v", datetime(2030, 1, 1, tzinfo=UTC))
    A.save_cookie(c, tmp_path)
    p = A.cookie_path(tmp_path)
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600
    assert set(json.loads(p.read_text())) == {"name", "value", "expires"}
    assert A.load_cookie(tmp_path, now=datetime(2029, 1, 1, tzinfo=UTC)) == c


def test_expired_cookie_triggers_relogin(tmp_path, monkeypatch):
    A.save_cookie(A.Cookie("gf_download_oauth", "old", datetime(2020, 1, 1, tzinfo=UTC)), tmp_path)
    monkeypatch.setenv("VELOMETER_OSM_USER", "me")
    monkeypatch.setenv("VELOMETER_OSM_PASSWORD", SECRET)
    with httpx.Client(transport=_transport([])) as c:
        cookie = A.load_or_login(tmp_path, client=c, now=datetime(2026, 10, 1, tzinfo=UTC))
    assert cookie.value == "abc.def"
    assert A.load_cookie(tmp_path, now=datetime(2026, 10, 1, tzinfo=UTC)).value == "abc.def"


def test_missing_env_credentials_raise_clearly(tmp_path, monkeypatch):
    monkeypatch.delenv("VELOMETER_OSM_USER", raising=False)
    monkeypatch.delenv("VELOMETER_OSM_PASSWORD", raising=False)
    with pytest.raises(A.AuthError, match="VELOMETER_OSM_USER"):
        A.credentials_from_env()


@pytest.mark.slow
def test_real_login(tmp_path):
    with A.new_auth_client() as c:
        cookie = A.load_or_login(tmp_path, client=c, force=True)
    assert cookie.name == "gf_download_oauth" and cookie.value
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest tests/test_geofabrik_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: velometer.sources.geofabrik_auth`.

- [ ] **Step 3: Implement**

```python
# src/velometer/sources/geofabrik_auth.py
"""Log in to Geofabrik's internal download server with an OSM account (OAuth cookie flow).

Mirrors Geofabrik's oauth_cookie_client.py, re-implemented with httpx. Credentials come only from
the environment (VELOMETER_OSM_USER / VELOMETER_OSM_PASSWORD via direnv + pass) and are never
written, logged or put into exception messages.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx

from velometer.sources.download import user_agent

CONSUMER_URL = "https://osm-internal.download.geofabrik.de/get_cookie"
OSM_HOST = "https://www.openstreetmap.org"
_TOKEN = re.compile(r'name="authenticity_token"[^>]*value="([^"]+)"|value="([^"]+)"[^>]*name="authenticity_token"')


class AuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class Cookie:
    name: str
    value: str
    expires: datetime

    def header(self) -> str:
        return f"{self.name}={self.value}"


def new_auth_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": user_agent()}, timeout=60, follow_redirects=False)


def _token(html: str, step: str) -> str:
    m = _TOKEN.search(html)
    if not m:
        raise AuthError(f"{step}: no authenticity_token in the page")
    return m.group(1) or m.group(2)


def _expect(resp: httpx.Response, codes: tuple[int, ...], step: str) -> httpx.Response:
    if resp.status_code not in codes:
        raise AuthError(f"{step}: HTTP {resp.status_code}, expected {' or '.join(map(str, codes))}")
    return resp


def _parse_cookie(text: str, now: datetime) -> Cookie:
    parts = [p.strip() for p in text.strip().split(";")]
    name, sep, value = parts[0].partition("=")
    if not sep or not value:
        raise AuthError("cookie response did not contain name=value")
    expires = now + timedelta(hours=24)
    for p in parts[1:]:
        k, _, v = p.partition("=")
        if k.lower() == "expires" and v:
            expires = parsedate_to_datetime(v).astimezone(UTC)
    return Cookie(name, value.strip('"'), expires)


def login(user: str, password: str, *, client: httpx.Client) -> Cookie:
    r = _expect(client.post(f"{CONSUMER_URL}?action=get_authorization_url"), (200,), "consumer")
    try:
        j = r.json()
        authz, state, redirect, cid = (
            j["authorization_url"], j["state"], j["redirect_uri"], j["client_id"])
    except (ValueError, KeyError) as e:
        raise AuthError("consumer: unexpected authorisation response") from e
    r = _expect(client.get(f"{OSM_HOST}/login?cookie_test=true"), (200,), "osm login page")
    r = client.post(
        f"{OSM_HOST}/login",
        data={"username": user, "password": password, "referer": "/", "commit": "Login",
              "authenticity_token": _token(r.text, "osm login page")},
    )
    _expect(r, (302,), "osm login (wrong user name or password?)")
    r = client.get(authz)
    if r.status_code != 302:
        _expect(r, (200,), "authorise")
        r = client.post(authz, data={
            "client_id": cid, "redirect_uri": redirect, "state": state,
            "authenticity_token": _token(r.text, "authorise"), "response_type": "code",
            "scope": "read_prefs", "nonce": "", "code_challenge": "",
            "code_challenge_method": "", "commit": "Authorize"})
        _expect(r, (302,), "authorise form")
    location = r.headers.get("location", "")
    if "?" not in location:
        raise AuthError("authorise: redirect without a query string")
    client.get(f"{OSM_HOST}/logout")
    r = _expect(client.get(f"{location}&{urlencode({'format': 'http'})}"), (200,), "cookie")
    return _parse_cookie(r.text, datetime.now(UTC))


def cookie_path(data_dir: Path) -> Path:
    return data_dir / "auth" / "geofabrik_cookie.json"


def save_cookie(c: Cookie, data_dir: Path) -> None:
    p = cookie_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    part = p.with_suffix(".part")
    fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"name": c.name, "value": c.value, "expires": c.expires.isoformat()}, f)
    part.replace(p)


def load_cookie(data_dir: Path, *, now: datetime) -> Cookie | None:
    p = cookie_path(data_dir)
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    c = Cookie(d["name"], d["value"], datetime.fromisoformat(d["expires"]))
    return c if c.expires - timedelta(minutes=10) > now else None


def credentials_from_env() -> tuple[str, str]:
    user, password = os.environ.get("VELOMETER_OSM_USER"), os.environ.get("VELOMETER_OSM_PASSWORD")
    if not user or not password:
        raise AuthError(
            "set VELOMETER_OSM_USER and VELOMETER_OSM_PASSWORD (direnv + pass, see .envrc.example)")
    return user, password


def load_or_login(
    data_dir: Path, *, client: httpx.Client, now: datetime | None = None, force: bool = False
) -> Cookie:
    now = now or datetime.now(UTC)
    if not force and (c := load_cookie(data_dir, now=now)) is not None:
        return c
    c = login(*credentials_from_env(), client=client)
    save_cookie(c, data_dir)
    return c
```

`.envrc.example` is a template for direnv. The user copies it to `.envrc` and runs `direnv allow`. `.envrc` is not yet gitignored, so Step 4 adds it to `.gitignore`.

```bash
# velometer: OSM account for Geofabrik's internal server (M3). Values live in pass, never here.
use_pass VELOMETER_OSM_USER velometer/osm-username
use_pass VELOMETER_OSM_PASSWORD velometer/osm-password
```

In `cli.py`, add an `auth` Typer sub-app:

```python
auth_app = typer.Typer(no_args_is_help=True, help="Geofabrik internal-server login.")
app.add_typer(auth_app, name="auth")


@auth_app.command("check")
def auth_check(data: Path = DATA_OPT) -> None:
    """Log in with VELOMETER_OSM_USER/PASSWORD and store the cookie; prints only ok or the error."""
    from velometer.sources.geofabrik_auth import AuthError, load_or_login, new_auth_client

    try:
        with new_auth_client() as c:
            cookie = load_or_login(data, client=c, force=True)
    except (AuthError, httpx.HTTPError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(f"ok: cookie valid until {cookie.expires:%Y-%m-%d %H:%M} UTC")
```

Add a CLI test with a monkeypatched `load_or_login` that raises `AuthError`: the exit code is 1 and the password does not appear in the output.

- [ ] **Step 4: Add `.envrc` to `.gitignore`.** Run the tests and the gate. Expected: all pass, and the slow test is deselected.

- [ ] **Step 5: Commit**

```bash
git add src/velometer/sources/geofabrik_auth.py src/velometer/cli.py tests/test_geofabrik_auth.py tests/test_cli.py .envrc.example .gitignore
git commit -m "feat: Geofabrik internal-server login from env credentials, auth check command"
```

---

### Task 2: Schema v5 (run source, activity, diagnostics)

**Files:**
- Modify: `src/velometer/db.py`, `src/velometer/models.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces:
  - `SCHEMA_VERSION = 5`.
  - `RunKey.source: str = "current"` as the last field, with a default so M2 callers are unchanged.
  - `find_done_run` matches `source`.
  - The unique index `runs_done_key` gains `source`.
  - `latest_done_run(...)` adds `AND source='current'`.
  - `ActivityYear` (in `models.py`): `city_id, boundary_kind, year, history_set_md5, n_edits, n_changesets, n_mappers, top_mapper_share, n_ways_created_cycling, n_ways_deleted_cycling`.
  - `replace_activity(conn, city_id, boundary_kind, history_set_md5, rows: list[ActivityYear]) -> None`, atomic.
  - `fetch_activity(conn, city_id, boundary_kind, history_set_md5) -> list[ActivityYear]`.
  - `complete_run(..., diagnostics: dict[str, float] | None = None)` writes `diagnostics(run_id, key, value)` in the same transaction.
  - `fetch_diagnostics(conn, run_id) -> dict[str, float]`.
  - `history_runs(conn, city_id, boundary_kind, *, classifier_version, classifier_parameters, config_sha256, history_set_md5) -> dict[str, int]` maps `osm_timestamp` to run_id for done `source='history'` runs.

- [ ] **Step 1: Write failing tests** in `tests/test_db.py`:

```python
def test_migration_4_to_5_keeps_runs_and_marks_them_current(tmp_path):
    # build a v4 DB with one done run via the current code path at v4, then reopen at v5
    ...  # use the existing v3->v4 migration test helper pattern in this file
    # assert: runs.source == 'current' for the old row; activity and diagnostics tables exist


def test_history_and_current_runs_with_same_key_fields_are_distinct(tmp_path):
    with open_db(tmp_path / "v.sqlite") as conn:
        create_schema(conn); upsert_cities(conn, CITIES)
        k_cur = _key(osm_timestamp="2026-01-01T00:00:00Z")
        k_his = replace(k_cur, source="history")
        a = start_run(conn, k_cur, git_commit="g", region_md5="m")
        complete_run(conn, a, "berlin", EMPTY_RESULT, [])
        assert find_done_run(conn, k_his) is None
        b = start_run(conn, k_his, git_commit="g", region_md5="m")
        complete_run(conn, b, "berlin", EMPTY_RESULT, [])  # unique index must allow both
        assert find_done_run(conn, k_his) == b


def test_latest_done_run_ignores_history_runs(tmp_path):
    # a history run with a LATER osm_timestamp than the current run must not be returned
    ...
    assert latest_done_run(conn, "berlin", "lau", config_sha256=SHA) == current_id


def test_replace_activity_is_atomic_and_round_trips(tmp_path):
    rows = [ActivityYear(city_id="berlin", boundary_kind="lau", year=2019, history_set_md5="h",
                         n_edits=3, n_changesets=2, n_mappers=2, top_mapper_share=0.67,
                         n_ways_created_cycling=1, n_ways_deleted_cycling=0)]
    replace_activity(conn, "berlin", "lau", "h", rows)
    replace_activity(conn, "berlin", "lau", "h", rows)  # replace, not duplicate
    assert fetch_activity(conn, "berlin", "lau", "h") == rows


def test_activity_table_has_no_user_columns(tmp_path):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(activity)")}
    assert not cols & {"uid", "user", "user_id", "username", "mapper"}


def test_diagnostics_written_with_the_run_and_rolled_back_with_it(tmp_path):
    ...  # complete_run(..., diagnostics={"legacy_km": 1.5}) -> fetch_diagnostics == {...};
    # a failing complete_run (duplicate metric rows) leaves no diagnostics rows
```

The implementer completes the `...` bodies using the fixtures already in `tests/test_db.py`: `_key`, `CITIES`, the empty `MeasureResult` builder, and the v3→v4 migration test. The assertions in the comments are the requirements.

- [ ] **Step 2: Run and confirm failure.** `uv run pytest tests/test_db.py -v`. The new tests fail.

- [ ] **Step 3: Implement**
  - Add to `_SCHEMA`:
    ```sql
    CREATE TABLE IF NOT EXISTS activity (
      city_id TEXT NOT NULL REFERENCES cities(id), boundary_kind TEXT NOT NULL,
      year INTEGER NOT NULL, history_set_md5 TEXT NOT NULL,
      n_edits INTEGER NOT NULL, n_changesets INTEGER NOT NULL, n_mappers INTEGER NOT NULL,
      top_mapper_share REAL NOT NULL, n_ways_created_cycling INTEGER NOT NULL,
      n_ways_deleted_cycling INTEGER NOT NULL,
      PRIMARY KEY (city_id, boundary_kind, year, history_set_md5)
    );
    CREATE TABLE IF NOT EXISTS diagnostics (
      run_id INTEGER NOT NULL REFERENCES runs(id), key TEXT NOT NULL, value REAL NOT NULL,
      PRIMARY KEY (run_id, key)
    );
    ```
  - Add `source TEXT NOT NULL DEFAULT 'current' CHECK (source IN ('current','history'))` to the `runs` columns and to `runs_done_key`.
  - `_migrate_4_to_5`: `ALTER TABLE runs ADD COLUMN source TEXT NOT NULL DEFAULT 'current'` if missing, then `DROP INDEX IF EXISTS runs_done_key`. `_SCHEMA` recreates the index. Add `"activity"` and `"diagnostics"` to `_RESULT_TABLES`.
  - In `start_run`, insert `key.source`. In `find_done_run`, add `AND source=?`. In `latest_done_run`, add `AND source='current'`.
  - `complete_run` gains `diagnostics` and inserts its rows inside the existing `with conn:` block.
  - Write `replace_activity` (DELETE plus INSERT in one `with conn:`), `fetch_activity`, `fetch_diagnostics` and `history_runs`.

- [ ] **Step 4: Run the tests and the gate.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/velometer/db.py src/velometer/models.py tests/test_db.py
git commit -m "feat: schema v5 with run source, activity aggregates and run diagnostics"
```

---

### Task 3: History sources (index snapshot, region selection, authenticated fetch)

**Files:**
- Modify: `src/velometer/sources/geofabrik.py`
- Test: `tests/test_geofabrik_history.py`
- Fixture: `tests/fixtures/geofabrik/index_small.json`, a synthetic FeatureCollection with 4 square regions and a parent, `urls.history` set

**Interfaces:**
- Consumes:
  - `Cookie` and `load_or_login` (Task 1)
  - `download.fetch` and `md5_of` (M2)
- Produces:
  - `INDEX_URL = "https://download.geofabrik.de/index-v1.json"`.
  - `fetch_index(data_dir, *, client=None, today: date | None = None) -> Path`. It writes `data/external/geofabrik/index-v1-YYYYMMDD.json`, trusting the dated name, and returns the path.
  - `load_index(path) -> dict[str, dict]`, mapping id to `{"geometry": shapely geom (WGS84), "parent": str | None, "history": str | None}`.
  - `regions_for(polygon_wgs84, index, *, buffer_m=1000) -> list[str]`.
    - It works on leaf regions only, meaning regions with no child in the index and a non-null `history`.
    - It buffers the polygon by `buffer_m` in EPSG:3035.
    - It keeps the leaves that intersect the buffered polygon. It then drops any leaf whose removal leaves the polygon still covered: greedily, smallest intersection area first, and only if the union of the rest still contains the buffered polygon.
    - It returns the ids sorted.
  - `HistoryFile(region: str, path: Path, md5: str, md5_source: Literal["published","computed"], fetched_at: date)`.
  - `fetch_history(region, data_dir, index, *, client=None, cookie_loader=load_or_login, today=None) -> HistoryFile`. The URL comes from `index[region]["history"].`
    1. Try `GET url + ".md5"` with the cookie. On 200 with a 32-hex first word, the md5 is "published".
    2. Download to `data/history/<region-slug>_<YYYYMMDD>.osh.pbf` with `fetch(..., md5=published or None)`, sending the cookie header. If the md5 was not published, compute it after the download.
    3. A 401 or 403 calls `cookie_loader(force=True)` once and retries once. A second 401 or 403 raises `DownloadError`.
    4. Final name: `<region-slug>_<YYYYMMDD>_<md5[:8]>.osh.pbf`, renamed after the md5 is known.
  - `history_set_md5(files: list[HistoryFile]) -> str` is `md5("\n".join(sorted(f"{f.region}:{f.md5}")))`.

`download.fetch` needs a way to pass headers. Add a keyword `headers: dict[str, str] | None = None`, forwarded to `client.stream(..., headers=headers)`, and a test that the header is sent.

- [ ] **Step 1: Write failing tests** (offline, `httpx.MockTransport`):

```python
def test_regions_for_covers_polygon_with_no_redundant_region():
    idx = load_index(FIX / "index_small.json")
    poly = box(0.5, 0.5, 1.5, 0.9)  # spans leaves a and b
    got = regions_for(poly, idx, buffer_m=0)
    assert got == ["a", "b"]
    union = unary_union([idx[r]["geometry"] for r in got])
    assert union.contains(poly)
    for r in got:  # rule: dropping any chosen region uncovers the polygon
        rest = unary_union([idx[o]["geometry"] for o in got if o != r])
        assert not rest.contains(poly)


def test_regions_for_never_returns_a_parent_region(): ...
def test_regions_for_raises_when_index_cannot_cover(): ...  # polygon outside all leaves


def test_fetch_history_sends_cookie_and_uses_published_md5(tmp_path): ...
def test_fetch_history_computes_md5_when_none_published(tmp_path): ...  # md5_source == "computed"
def test_fetch_history_relogs_once_on_403(tmp_path):
    # first GET 403, cookie_loader(force=True) called once, second GET 200 -> file present, no .part
    ...
def test_fetch_history_gives_up_after_second_403(tmp_path): ...  # DownloadError, no file, no .part
def test_history_set_md5_is_order_independent(): ...
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement** to the interface above. Retry policy: reuse `_with_retries` for transient errors. Authentication failures are handled only by the one-relogin rule.
- [ ] **Step 4: Run the tests and the gate.**
- [ ] **Step 5: Verify against the real server.** This needs the user's gpg unlocked, so skip it if `auth check` fails and say so in the report.
  - Run `uv run velometer auth check`.
  - `curl -sI -b "<cookie header>" <berlin history url>.md5` and `<berlin history url>`. Use the cookie from `data/auth/geofabrik_cookie.json`, read with python, and never echo it.
  - Record in the report whether a `.md5` is published and the `Content-Length` of the berlin history.
- [ ] **Step 6: Commit**

```bash
git add src/velometer/sources/geofabrik.py src/velometer/sources/download.py tests/test_geofabrik_history.py tests/test_download.py tests/fixtures/geofabrik/index_small.json
git commit -m "feat: Geofabrik index snapshot, region selection and authenticated history fetch"
```

---

### Task 4: osmium history wrappers and per-city history and snapshots

**Files:**
- Modify: `src/velometer/osmium.py`
- Create: `src/velometer/pipeline/history.py`
- Test: `tests/test_history.py`
- Fixture: `tests/fixtures/history/mini.osh`, hand-written OSM XML with `version`, `timestamp`, `uid`, `changeset` and `visible` attributes

The fixture is all in WGS84 near (13.40, 52.52), with a boundary square of 0.01° side centred there. It contains:
- way 1: a cycleway inside the square; v1 in 2017-06, v2 in 2019-03 (adds `segregated=yes`)
- way 2: inside in 2017; v2 in 2020-05 moves all its nodes outside the square (node versions)
- way 3: created in 2021-02 inside the square, deleted in 2022-08 (`visible="false"`)
- way 4: always outside the square, with versions in 2018 and 2019
- each node carries a location history to match

**Interfaces:**
- Produces:
  - `osmium.merge_history(srcs: list[Path], dst: Path) -> Path`, which runs `osmium merge --with-history`.
  - `osmium.extract_history(src, polygon_geojson, dst) -> Path`, which runs `osmium extract --with-history -s complete_ways`.
  - `osmium.time_filter(src, ts: datetime, dst) -> Path`, which runs `osmium time-filter src <ts:%Y-%m-%dT%H:%M:%SZ>`.
  - All three write a `.part` file, then replace atomically.
  - `history.city_history(city_id, kind, files: list[HistoryFile], set_md5, boundary_geojson, boundary_sha256, data_dir) -> Path`. It is cached at `data/history/city/<city>_<kind>_<set_md5[:8]>_<bsha[:8]>.osh.pbf`, merging first when `len(files) > 1`.
  - `history.snapshot_at(city_history: Path, ts: datetime, data_dir) -> Path`. It is cached at `data/snapshots/<city_history stem>_<YYYYMMDD>.osm.pbf`.
  - `history.SNAPSHOT_DATES(years: range) -> list[datetime]` gives 1 January 00:00 UTC for each year.

- [ ] **Step 1: Write failing tests** (they need osmium; skip with a clear reason if it is missing, as `test_osmium.py` does):

```python
def test_time_filter_shows_each_way_as_it_was(tmp_path):
    src = FIX / "mini.osh"
    s2018 = time_filter(src, datetime(2018, 1, 1, tzinfo=UTC), tmp_path / "a.osm.pbf")
    s2020 = time_filter(src, datetime(2020, 1, 1, tzinfo=UTC), tmp_path / "b.osm.pbf")
    w18 = {w.id: w for w in read_ways(s2018).ways}
    w20 = {w.id: w for w in read_ways(s2020).ways}
    assert 1 in w18 and "segregated" not in w18[1].tags
    assert w20[1].tags["segregated"] == "yes"
    assert 3 not in w18 and 3 not in w20


def test_city_history_keeps_way_that_left_boundary(tmp_path):
    hist = city_history("t", "lau", [HF], "set", POLY, "b" * 64, tmp_path)
    snap = snapshot_at(hist, datetime(2018, 1, 1, tzinfo=UTC), tmp_path)
    assert 2 in {w.id for w in read_ways(snap).ways}   # inside in 2018, outside later
    assert 4 not in {w.id for w in read_ways(snap).ways}


def test_deleted_way_absent_after_deletion(tmp_path):
    ...  # 2022-01-01 has way 3, 2023-01-01 does not


def test_city_history_and_snapshots_are_cached(tmp_path, monkeypatch):
    ...  # second call does not invoke osmium (monkeypatch velometer.osmium._run to count)


def test_merge_history_dedups_identical_versions(tmp_path):
    ...  # merging mini.osh with itself equals mini.osh object/version set


def test_failed_osmium_leaves_no_part_file(tmp_path): ...
```

- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.** Mirror `osmium.extract` and `pipeline/extract.snapshot` (the `.part` naming must keep the `.osh.pbf` / `.osm.pbf` suffix so osmium can infer the format).
- [ ] **Step 4: Run the tests and the gate.**
- [ ] **Step 5: Commit**

```bash
git add src/velometer/osmium.py src/velometer/pipeline/history.py tests/test_history.py tests/fixtures/history/mini.osh
git commit -m "feat: history-aware osmium merge/extract/time-filter and cached city histories"
```

---

### Task 5: Activity aggregates from a city history

**Files:**
- Create: `config/activity.yaml`
- Create: `src/velometer/pipeline/activity.py`
- Modify: `src/velometer/config.py` (`ActivityConfig`, `load_activity`)
- Test: `tests/test_activity.py` (reuses `tests/fixtures/history/mini.osh` and adds `tests/fixtures/history/edits.osh`)

`config/activity.yaml`:

```yaml
# Mapping-activity diagnostics and flag rules (M3 spec §2.12–2.14). Thresholds are data.
cycling_keys:
  exact: [segregated, bicycle_road, cyclestreet, oneway:bicycle]
  prefixes: ["cycleway", "bicycle", "sidewalk:left:bicycle", "sidewalk:right:bicycle",
             "sidewalk:both:bicycle", "sidewalk:bicycle"]
  highway_values: [cycleway, path, footway, pedestrian, living_street]
legacy:
  rules: [B_sidewalk_designated, X_sidewalk_bicycle_permitted]
  value_prefixes: {cycleway: opposite}
flags:
  km_jump_pct: 10
  km_jump_min_km: 25
  activity_spike_factor: 2.0
  single_mapper_share: 0.5
  tag_drift_pct: 50
```

**Interfaces:**
- Produces:
  - `ActivityConfig` (pydantic, strict) and `load_activity(path) -> ActivityConfig`.
  - `cycling_tags(tags: Mapping[str,str], cfg) -> dict[str,str]`, the cycling-relevant subset. `highway` counts only when its value is in `highway_values`.
  - `activity(city_history: Path, years: range, cfg, *, city_id, boundary_kind, history_set_md5) -> list[ActivityYear]`. There is exactly one row per year in `years`, and zeros are allowed.
  - The window for year Y is `[Y-1-01-01, Y-01-01)` UTC.
  - A way version counts when `cycling_tags(v) != cycling_tags(previous version)`, where the previous version of v1 is `{}` and a deleted version (`visible=false`) has `{}`. Created means previous `{}` and current non-empty; deleted means previous non-empty and current `{}`.
  - uids are collected per year in a local set and dropped. `top_mapper_share = max count / n_edits`, or 0.0 when `n_edits == 0`. Anonymous edits (uid 0) count as one mapper bucket.

Implementation: a `osmium.SimpleHandler` subclass with `way(self, w)`. Iterate the history file (`osmium.io.Reader` with history; the `apply_file` default reads all versions). Keep `prev: dict[int, dict]` per way id, relying on sorted id/version order. Copy tags with `{t.k: t.v for t in w.tags}`, because pyosmium objects are only valid inside the callback.

- [ ] **Step 1: Write failing tests**

```python
def test_counts_per_year_follow_the_window_rule():
    rows = {r.year: r for r in activity(FIX / "mini.osh", range(2018, 2024), CFG,
                                        city_id="t", boundary_kind="lau", history_set_md5="h")}
    assert rows[2018].n_edits == 1          # way 1 v1 (2017) created with cycling tags
    assert rows[2020].n_edits == 1          # way 1 v2 (2019) adds segregated
    assert rows[2022].n_ways_created_cycling == 1  # way 3 created 2021
    assert rows[2023].n_ways_deleted_cycling == 1  # way 3 deleted 2022


def test_non_cycling_tag_change_is_not_an_edit(): ...      # edits.osh: name change only
def test_top_mapper_share_and_mapper_count(): ...         # edits.osh: uid 7 makes 3 of 4 edits
def test_year_without_edits_stores_zeros():
    rows = activity(FIX / "mini.osh", range(2030, 2031), CFG, city_id="t", boundary_kind="lau",
                    history_set_md5="h")
    assert rows == [ActivityYear(city_id="t", boundary_kind="lau", year=2030,
                                 history_set_md5="h", n_edits=0, n_changesets=0, n_mappers=0,
                                 top_mapper_share=0.0, n_ways_created_cycling=0,
                                 n_ways_deleted_cycling=0)]
def test_no_uid_leaves_the_function():
    rows = activity(...)
    assert all("uid" not in r.model_dump() for r in rows)
def test_cycling_tags_highway_only_for_listed_values(): ...
def test_activity_config_rejects_unknown_keys(): ...
```

- [ ] **Steps 2–4:** confirm the tests fail, implement, then run the tests and the gate.
- [ ] **Step 5: Commit**

```bash
git add config/activity.yaml src/velometer/config.py src/velometer/pipeline/activity.py tests/test_activity.py tests/fixtures/history/edits.osh
git commit -m "feat: per-year mapping-activity aggregates from a city history (no user ids kept)"
```

---

### Task 6: Tag-drift diagnostics per run

**Files:**
- Modify: `src/velometer/pipeline/measure.py` (`MeasureResult.way_lengths: dict[int, float]`, default empty, filled by `measure`)
- Create: `src/velometer/pipeline/drift.py`
- Test: `tests/test_drift.py`

**Interfaces:**
- Consumes: `ActivityConfig` (Task 5) and `MeasureResult.classified` / `.way_lengths`.
- Produces: `drift_diagnostics(result: MeasureResult, ways: list[WayRecord], cfg: ActivityConfig) -> dict[str, float]` with keys `legacy_km` and `unrecognised_cycling_km`. Both are per_side km, clipped (from `way_lengths`).
  - A side is **legacy** when its `rule_id` is in `cfg.legacy.rules`, or when its source way has a key from `cfg.legacy.value_prefixes` whose value starts with the given prefix (e.g. `cycleway=opposite_track`). Only sides with a tier (A–E or excluded) count.
  - A side is **unrecognised cycling** when its `tier is None` and the source way has non-empty `cycling_tags`.

- [ ] **Step 1: Write failing tests** using the existing M1 case fixtures (`tests/fixtures/cases/*.osm`). Pick `opposite_track`, `sidewalk_right_designated` and one unknown value case by grepping `tests/fixtures/expected.yaml`. Assert:
  - each legacy case gives `legacy_km` > 0;
  - a modern `cycleway:right=track` case gives `legacy_km == 0`;
  - the unknown-value case gives `unrecognised_cycling_km > 0`;
  - km wholly outside a given boundary contribute 0.
- [ ] **Steps 2–4:** confirm the tests fail, implement, then run the tests and the gate. Check that `measure`'s existing outputs are unchanged: the full suite must still pass.
- [ ] **Step 5: Commit**

```bash
git add src/velometer/pipeline/measure.py src/velometer/pipeline/drift.py tests/test_drift.py
git commit -m "feat: legacy-tag and unrecognised-cycling km diagnostics per run"
```

---

### Task 7: History runs (`run_city_year`, `run_history`) and CLI

**Files:**
- Modify: `src/velometer/run.py`, `src/velometer/cli.py`
- Test: `tests/test_run_history.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes:
  - Tasks 1–6.
  - `city_boundary`, `measure`, `compute_metrics`, `with_per_100k`, `config_sha256`, `git_commit` (M2).
- Produces:
  - `HistoryDeps`, a frozen dataclass of callables with real defaults: `fetch_index`, `load_index`, `fetch_history`, `city_boundary`, `city_history`, `snapshot_at`, `read_ways`, `activity`.
  - `run_history(conn, city, years: range, *, data_dir, config_dir, boundary_kind="lau", classifier="v1", deps=None, force=False) -> list[RunOutcome]`, one outcome per year. Its steps:
    1. Get the boundary (as M2; the population comes from it and is held constant).
    2. Load the index and compute `regions_for(boundary WGS84)`.
    3. `fetch_history` for each region, then compute `set_md5`.
    4. Build the `city_history`.
    5. For each year, do the same as `run_city` but with `key.osm_timestamp = f"{Y}-01-01T00:00:00Z"`, `source="history"` and `region_md5=set_md5`.
       - Make the snapshot with `snapshot_at`.
       - Pass `diagnostics=drift_diagnostics(...)` to `complete_run`.
       - A failure in one year records a failed run and continues with the next year.
    6. Run `replace_activity` once per (city, kind, set_md5), with `years = range(first, last + 1)` plus the current-point window. The window is stored as year `last + 1`, covering `[last-01-01, now)` where now is the latest current run's `osm_timestamp`; skip it when no current run exists.
    - Failures before the first year (auth, index, download, boundary) return a single `RunOutcome(city.id, "failed", None, error)`, as M2 R5 does.
  - CLI:
    - `run --years 2018-2026` (parsed into `range`; invalid input exits 2) calls `run_history` for each city. Without `--years`, the M2 behaviour is unchanged.
    - `osm fetch-history --region R` or `--city C [--boundary lau|fua]` prints the region, path, md5, md5_source and size.

- [ ] **Step 1: Write failing tests** with fake `HistoryDeps`. The fakes return `tests/fixtures/measure/mini_city.osm` as every snapshot, and a fixed list from `activity`.

```python
def test_run_history_makes_one_history_run_per_year(tmp_path): ...
    # outcomes all done; runs rows have source='history', osm_timestamp YYYY-01-01T00:00:00Z,
    # region_md5 == set md5; population_year == 2024 on every row; diagnostics rows present

def test_rerun_skips_done_years(tmp_path): ...            # second call: all "skipped"
def test_new_history_set_makes_new_runs_and_series_uses_one_set(tmp_path): ...
    # change fake fetch_history md5 -> all years run again; history_runs(..., set_md5=new) has
    # exactly the new ids and history_runs(..., set_md5=old) the old ones
def test_one_failing_year_does_not_stop_the_others(tmp_path): ...  # snapshot_at raises for 2020
def test_pre_run_failure_returns_one_failed_outcome(tmp_path): ...  # fetch_history raises
def test_activity_written_once_per_city_kind_set(tmp_path): ...
def test_current_run_unaffected_by_history_runs(tmp_path): ...  # M2 run_city still skipped/done
def test_cli_years_parse_and_reject(tmp_path, monkeypatch): ...  # "2018-2026" ok; "2026-2018", "x" exit 2
```

- [ ] **Steps 2–4:** confirm the tests fail, implement, then run the tests and the gate.
- [ ] **Step 5: Slow test** (`@pytest.mark.slow`) in `tests/test_run_history.py`:
  - Run Berlin LAU for `range(2018, 2019)` against the real server into `tmp_path` (DB and data).
  - Assert:
    - the status is done;
    - `osm_timestamp == "2018-01-01T00:00:00Z"`;
    - the headline is not None and every tier km is ≥ 0;
    - **pitfall 7:** `fetch_diagnostics(run)["legacy_km"] > 0`, and the legacy-tagged ways in that snapshot (any way with `cycleway=opposite_*` or `sidewalk:*:bicycle=*`) all classify to a tier, so `unrecognised_cycling_km` does not include them.
  - Run it once and report the result. If gpg is locked, report it as not run.
- [ ] **Step 6: Commit**

```bash
git add src/velometer/run.py src/velometer/cli.py tests/test_run_history.py tests/test_cli.py
git commit -m "feat: resumable yearly history runs with activity and drift diagnostics"
```

---

### Task 8: Time series, flags, report block and `--check`

**Files:**
- Create: `src/velometer/timeseries.py`
- Create: `docs/review/m3_timeseries.md` (preamble plus markers plus `## Explanations`)
- Modify: `src/velometer/cli.py` (`timeseries` command)
- Test: `tests/test_timeseries.py`

**Interfaces:**
- Consumes: `history_runs`, `latest_done_run`, `fetch_run_results`, `fetch_activity`, `fetch_diagnostics` (Task 2); `ActivityConfig` (Task 5); `select_metric` and the presets config (M2).
- Produces:
  - `YearPoint(label: str, run_id: int, osm_timestamp: str, headline: float | None, ab_km: float, tiers_km: dict[str, float], activity: ActivityYear | None, legacy_km: float, unrecognised_km: float)`. `label` is `"2018"`…`"2026"` or `"current"`.
  - `series(conn, city_id, kind, selector, history_set_md5) -> list[YearPoint]`, in label order.
  - `Flag(city_id, kind, label, rules: tuple[str, ...], detail: str)`.
  - `flags(points: list[YearPoint], cfg: ActivityConfig, *, current_fraction: float) -> list[Flag]`. It implements spec §2.13 exactly:
    - `km_jump`: `abs(ab_km - prev.ab_km) >= max(pct/100 * prev.ab_km, min_km * scale)`. Here `scale` is 1.0 for full years and `current_fraction` for the current point.
    - `activity_spike`: `n_edits >= factor * median(n_edits over the 2018–2026 points) * scale`.
    - `campaign_suspected` = jump and spike; `single_mapper` = jump and `top_mapper_share >= share`.
    - `tag_drift`: `legacy_km` or `unrecognised_km` changes by ≥ pct% versus prev, when prev > 0.
    - The first point gets no rule that needs a previous point.
  - `render_block(points_by_city_kind, flags) -> str` renders one table per city and kind: columns label, headline %, A+B km, tiers A–E km, edits, mappers, top-mapper share, legacy km, unrecognised km and flags. It also prints a per-city provenance line (run ids, history_set_md5[:8], classifier and config sha[:12], "population 2024 held constant").
  - `write_report(path, block)` replaces the text between `<!-- timeseries:begin -->` and `<!-- timeseries:end -->`. Missing markers raise `ValueError`.
  - `missing_explanations(path, flags) -> list[str]` uses headings `### <city>/<kind>/<label>`.
  - `stale_explanations(path, flags) -> list[str]`.
  - The explained-against marker is `<!-- explained-against: berlin/lau=<history_set_md5[:8]> ... -->`. `--check` fails when it differs from the current sets.
- CLI: `timeseries [--city ...] [--boundary lau|fua] [--write] [--check]`.
  - It prints the tables.
  - `--write` renders every city with history runs.
  - `--check` exits 1 with a message for each of: a missing explanation, a stale marker, a city without history runs, and missing markers or file. It warns on stale headings.

- [ ] **Step 1: Write failing tests.** These are pure tests over hand-built `YearPoint` lists: each flag rule at the threshold and just below, `current_fraction` scaling, first-point rules, a zero `prev`. CLI tests build a DB through the Task 7 fakes.

```python
def test_km_jump_at_threshold_flags_and_just_below_does_not(): ...
def test_campaign_needs_both_jump_and_spike(): ...
def test_single_mapper_needs_a_jump(): ...
def test_current_point_thresholds_scale_with_window(): ...
def test_first_point_never_flagged_by_change_rules(): ...
def test_tag_drift_ignores_zero_previous(): ...
def test_check_requires_explanation_per_flag_and_fresh_marker(tmp_path, monkeypatch): ...
def test_write_keeps_text_outside_markers_and_is_idempotent(tmp_path): ...
```

- [ ] **Steps 2–4:** confirm the tests fail, implement, then run the tests and the gate. Red-proof each flag rule by breaking it.
- [ ] **Step 5: Commit**

```bash
git add src/velometer/timeseries.py src/velometer/cli.py docs/review/m3_timeseries.md tests/test_timeseries.py
git commit -m "feat: yearly time series with activity flags and an enforced explanations check"
```

---

### Task 9: Execute M3 (real downloads, runs, chart, explanations)

Run this on the most capable model, with the controller watching.

**Files:**
- Create: `scripts/render_m3_timeseries.py`, `docs/review/m3_timeseries.png`
- Modify: `docs/review/m3_timeseries.md` (generated block plus explanations)
- Modify: `docs/adr/0005-annual-snapshots-versioned-classifier.md` (append `## Notes (M3 as run)`: download sizes, timings, region sets per boundary)

- [ ] **Step 1: Login.** Run `uv run velometer auth check`. It needs the user's gpg agent unlocked so direnv can run `pass`. If it fails, stop and report.
- [ ] **Step 2: Fetch and run.** Time each step.
  ```bash
  uv run velometer osm fetch-history --city berlin --boundary fua   # also covers berlin lau
  uv run velometer run --cities all --years 2018-2026
  uv run velometer run --cities berlin,paris --years 2018-2026 --boundary fua
  ```
  The `--cities` parsing of a comma list must match the existing CLI; check `--help`. Expected: every year is done. A failed year is investigated and fixed through a tested code change, never by retrying blindly.
- [ ] **Step 3: Write `scripts/render_m3_timeseries.py`** (matplotlib Agg; it reads the DB via `timeseries.series`). It draws three panels:
  - (a) headline % over time per city on LAU, with flagged points marked;
  - (b) small multiples of stacked A–E per_side km per year, one per city;
  - (c) LAU vs FUA headline for Berlin and Paris.

  The title is built from the run rows. The footer carries the ODbL attribution plus "OSM mapped km, not built km (ADR 0006); population 2024 held constant". Run it, view the PNG with the Read tool, and fix any rendering problem.
- [ ] **Step 4: Explain.** Run `uv run velometer timeseries --write`. For each flagged key, write a `### <city>/<kind>/<label>` explanation of 2–6 sentences, using evidence from:
  - activity numbers;
  - per-tier deltas;
  - the legacy and unrecognised km;
  - where useful, a few example way ids with their tag change, taken from the city history with `osmium getid -H`.

  Name the cause: **campaign**, **import**, **construction**, **tag drift** or **classifier gap**. Classifier gaps go into a list for the user; rules are not changed. Then set the marker. `timeseries --check` and `reconcile --check` must both exit 0.
- [ ] **Step 5: Gate and commit** (no data files).

```bash
git add scripts/render_m3_timeseries.py docs/review/m3_timeseries.md docs/review/m3_timeseries.png docs/adr/0005-annual-snapshots-versioned-classifier.md
git commit -m "docs: M3 time series 2018-2026 for 5 cities with FUA runs and flag explanations"
```

---

## Self-review notes (writer)

**Spec coverage:**

| Spec | Task |
|---|---|
| §2.1 FUA all years | 7, 9 |
| §2.2 population held | 7 (population_year 2024 assert), 8 (provenance line) |
| §2.3 aggregates only | 2 (no user columns), 5 |
| §2.4 credentials | 1 |
| §2.6 regions_for | 3 |
| §2.7 clip once, filter per date | 4, 7 |
| §2.8 dates/current | 4, 7, 8 |
| §2.9 boundaries 2024 | 7 (city_boundary reused) |
| §2.10 frozen v1 | Global Constraints |
| §2.11 run key/source | 2, 7 |
| §2.12 activity | 5 |
| §2.13 flags | 8 |
| §2.14 drift | 6 |
| §2.15 performance | 9 (timings into ADR 0005) |
| §3 CLI | 1, 7, 8 |
| §4 testing incl. pitfall 7 slow test | 1, 3, 4, 5, 7 |
| §5 execution | 9 |

**Type consistency:**
- `HistoryFile` (Task 3) is used by `city_history` (Task 4) and `run_history` (Task 7).
- `ActivityYear` (Task 2 `models.py`) is produced by Task 5 and consumed by Task 8.
- `ActivityConfig` (Task 5) is used by Tasks 6 and 8.
- `RunKey.source` (Task 2) is used by Task 7.
- `complete_run(diagnostics=)` (Task 2) is used by Task 7.

**Known plan risk:** Task 2's test bodies are given as requirements plus helper pointers rather than full code, because they depend on the fixture helpers in `tests/test_db.py`. The assertions are spelled out and must not be weakened.
