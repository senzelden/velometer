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


def _transport(
    calls, *, authorised=False, login_status=302, expires="Sat, 03 Oct 2026 12:00:00 GMT"
):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, str(req.url)))
        url = str(req.url)
        if url.startswith(A.CONSUMER_URL) and "get_authorization_url" in url:
            return httpx.Response(
                200,
                json={
                    "authorization_url": A.OSM_HOST + "/oauth2/authorize?x=1",
                    "state": "st",
                    "redirect_uri": A.CONSUMER_URL,
                    "client_id": "cid",
                },
            )
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
    assert (
        "POST",
        A.OSM_HOST + "/oauth2/authorize?x=1",
    ) in calls  # form posted when not authorised


def test_login_skips_the_form_when_already_authorised():
    calls = []
    with httpx.Client(transport=_transport(calls, authorised=True)) as c:
        A.login("me", SECRET, client=c)
    assert not any(m == "POST" and "authorize" in u for m, u in calls)


def test_failed_login_raises_without_the_password():
    with (
        httpx.Client(transport=_transport([], login_status=200)) as c,
        pytest.raises(A.AuthError) as e,
    ):
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


def test_parse_cookie_handles_the_real_server_body_with_flag_attributes():
    body = (
        "gf_download_oauth=abc.def; expires=Sat, 03 Oct 2026 19:57:05 GMT; HttpOnly; Path=/; Secure"
    )
    c = A._parse_cookie(body, datetime(2026, 10, 1, tzinfo=UTC))
    assert c == A.Cookie(
        "gf_download_oauth", "abc.def", datetime(2026, 10, 3, 19, 57, 5, tzinfo=UTC)
    )
