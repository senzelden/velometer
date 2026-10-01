"""Log in to Geofabrik's internal download server with an OSM account (OAuth cookie flow).

Mirrors Geofabrik's oauth_cookie_client.py, re-implemented with httpx. Credentials come only from
the environment (VELOMETER_OSM_USER / VELOMETER_OSM_PASSWORD via direnv + pass) and are never
written, logged or put into exception messages.
"""

import json
import os
import re
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx

from velometer.sources.download import user_agent

CONSUMER_URL = "https://osm-internal.download.geofabrik.de/get_cookie"
OSM_HOST = "https://www.openstreetmap.org"
_TOKEN = re.compile(
    r'name="authenticity_token"[^>]*value="([^"]+)"'
    r'|value="([^"]+)"[^>]*name="authenticity_token"'
)


class AuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class Cookie:
    name: str
    value: str = field(repr=False)
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
            with suppress(TypeError, ValueError):  # malformed date: keep the 24 h default
                expires = parsedate_to_datetime(v).astimezone(UTC)
    return Cookie(name, value.strip('"'), expires)


def login(user: str, password: str, *, client: httpx.Client) -> Cookie:
    r = _expect(client.post(f"{CONSUMER_URL}?action=get_authorization_url"), (200,), "consumer")
    try:
        j = r.json()
        authz, state, redirect, cid = (
            j["authorization_url"],
            j["state"],
            j["redirect_uri"],
            j["client_id"],
        )
    except (ValueError, KeyError) as e:
        raise AuthError("consumer: unexpected authorisation response") from e
    r = _expect(client.get(f"{OSM_HOST}/login?cookie_test=true"), (200,), "osm login page")
    r = client.post(
        f"{OSM_HOST}/login",
        data={
            "username": user,
            "password": password,
            "referer": "/",
            "commit": "Login",
            "authenticity_token": _token(r.text, "osm login page"),
        },
    )
    _expect(r, (302,), "osm login (wrong user name or password?)")
    r = client.get(authz)
    if r.status_code != 302:
        _expect(r, (200,), "authorise")
        r = client.post(
            authz,
            data={
                "client_id": cid,
                "redirect_uri": redirect,
                "state": state,
                "authenticity_token": _token(r.text, "authorise"),
                "response_type": "code",
                "scope": "read_prefs",
                "nonce": "",
                "code_challenge": "",
                "code_challenge_method": "",
                "commit": "Authorize",
            },
        )
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
    part.unlink(missing_ok=True)  # a stale file would keep its old mode through O_TRUNC
    try:
        fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"name": c.name, "value": c.value, "expires": c.expires.isoformat()}, f)
        part.replace(p)
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def load_cookie(data_dir: Path, *, now: datetime) -> Cookie | None:
    p = cookie_path(data_dir)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
        c = Cookie(d["name"], d["value"], datetime.fromisoformat(d["expires"]))
        return c if c.expires - timedelta(minutes=10) > now else None
    except (ValueError, KeyError, TypeError):
        return None  # corrupt or hand-edited file: treat as a miss and log in afresh


def credentials_from_env() -> tuple[str, str]:
    user, password = os.environ.get("VELOMETER_OSM_USER"), os.environ.get("VELOMETER_OSM_PASSWORD")
    if not user or not password:
        raise AuthError(
            "set VELOMETER_OSM_USER and VELOMETER_OSM_PASSWORD (direnv + pass, see .envrc.example)"
        )
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
