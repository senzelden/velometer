import hashlib

import httpx
import pytest

from velometer.sources import geofabrik
from velometer.sources.download import DownloadError, fetch, user_agent

BODY = b"x" * 10_000
MD5 = hashlib.md5(BODY).hexdigest()


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_writes_file_and_verifies_md5(tmp_path):
    c = _client(lambda r: httpx.Response(200, content=BODY))
    out = fetch("https://h/f.pbf", tmp_path / "f.pbf", md5=MD5, client=c, backoff_s=0)
    assert out.read_bytes() == BODY


def test_fetch_md5_mismatch_raises_and_leaves_no_file(tmp_path):
    c = _client(lambda r: httpx.Response(200, content=b"corrupt"))
    with pytest.raises(DownloadError, match="md5"):
        fetch("https://h/f.pbf", tmp_path / "f.pbf", md5=MD5, client=c, backoff_s=0)
    assert list(tmp_path.iterdir()) == []


def test_existing_file_with_right_md5_is_not_refetched(tmp_path):
    (tmp_path / "f.pbf").write_bytes(BODY)
    c = _client(lambda r: pytest.fail("network used"))
    fetch("https://h/f.pbf", tmp_path / "f.pbf", md5=MD5, client=c)


def test_existing_file_with_wrong_md5_is_refetched(tmp_path):
    (tmp_path / "f.pbf").write_bytes(b"stale")
    c = _client(lambda r: httpx.Response(200, content=BODY))
    fetch("https://h/f.pbf", tmp_path / "f.pbf", md5=MD5, client=c, backoff_s=0)
    assert (tmp_path / "f.pbf").read_bytes() == BODY


def test_fetch_retries_then_succeeds(tmp_path):
    calls = []

    def handler(r):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, content=BODY)

    fetch("https://h/f.pbf", tmp_path / "f.pbf", md5=MD5, client=_client(handler), backoff_s=0)
    assert len(calls) == 3


def test_user_agent_has_contact_only_when_set(monkeypatch):
    monkeypatch.delenv("VELOMETER_CONTACT", raising=False)
    assert user_agent().startswith("velometer/") and ";" not in user_agent()
    monkeypatch.setenv("VELOMETER_CONTACT", "https://example.org/velometer")
    assert user_agent().endswith("; https://example.org/velometer")


def test_resolve_dated_follows_latest_redirect():
    def handler(r):
        assert r.method == "HEAD"
        return httpx.Response(307, headers={"location": "berlin-260930.osm.pbf"})

    url = geofabrik.resolve_dated("europe/germany/berlin", _client(handler))
    assert url == "https://download.geofabrik.de/europe/germany/berlin-260930.osm.pbf"


def test_fetch_region_reads_md5_and_header_timestamp(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    def handler(r):
        if r.method == "HEAD":
            return httpx.Response(307, headers={"location": "berlin-260930.osm.pbf"})
        if r.url.path.endswith(".md5"):
            return httpx.Response(200, text=f"{MD5}  berlin-260930.osm.pbf\n")
        return httpx.Response(200, content=BODY)

    ts = datetime(2026, 9, 30, 20, 22, 42, tzinfo=UTC)
    monkeypatch.setattr(geofabrik, "fileinfo_timestamp", lambda p: ts)
    rf = geofabrik.fetch_region("europe/germany/berlin", tmp_path, client=_client(handler))
    assert rf.md5 == MD5 and rf.osm_timestamp == ts
    assert rf.path == tmp_path / "raw" / "berlin-260930.osm.pbf"


def test_non_transient_4xx_is_not_retried(tmp_path):
    calls = []

    def handler(r):
        calls.append(1)
        return httpx.Response(404)

    with pytest.raises(DownloadError):
        fetch("https://h/f.pbf", tmp_path / "f.pbf", client=_client(handler), backoff_s=0)
    assert len(calls) == 1


def test_429_is_retried(tmp_path):
    calls = []

    def handler(r):
        calls.append(1)
        return httpx.Response(429) if len(calls) < 2 else httpx.Response(200, content=BODY)

    fetch("https://h/f.pbf", tmp_path / "f.pbf", client=_client(handler), backoff_s=0)
    assert len(calls) == 2


def test_midstream_oserror_propagates_and_leaves_no_part(tmp_path):
    class Boom(httpx.SyncByteStream):
        def __iter__(self):
            yield b"abc"
            raise OSError("disk gone")

    c = _client(lambda r: httpx.Response(200, stream=Boom()))
    with pytest.raises(OSError, match="disk gone"):
        fetch("https://h/f.pbf", tmp_path / "f.pbf", client=c, backoff_s=0)
    assert list(tmp_path.iterdir()) == []


def test_retries_must_be_positive(tmp_path):
    with pytest.raises(ValueError):
        fetch("https://h/f.pbf", tmp_path / "f.pbf", retries=0)


def test_redirect_without_location_raises_download_error():
    with pytest.raises(DownloadError, match="location"):
        geofabrik.resolve_dated("r", _client(lambda r: httpx.Response(307)))


def test_resolve_dated_accepts_absolute_location():
    h = {"location": "https://other.example/x/berlin-260930.osm.pbf"}
    url = geofabrik.resolve_dated("r", _client(lambda r: httpx.Response(302, headers=h)))
    assert url == "https://other.example/x/berlin-260930.osm.pbf"


def test_empty_md5_body_raises_download_error(tmp_path):
    def handler(r):
        if r.method == "HEAD":
            return httpx.Response(307, headers={"location": "b-1.osm.pbf"})
        return httpx.Response(200, text="\n")

    with pytest.raises(DownloadError, match="md5"):
        geofabrik.fetch_region("r", tmp_path, client=_client(handler))


def test_resolve_dated_retries_a_trailing_slash_redirect():
    # Geofabrik's mirror intermittently answers 301 -> "<file>.osm.pbf/" (seen 2026-10-01);
    # that is not a dated file, and appending ".md5" to it gives ".../.md5" (404/502).
    answers = iter(
        [
            httpx.Response(301, headers={"location": "berlin-latest.osm.pbf/"}),
            httpx.Response(307, headers={"location": "berlin-260930.osm.pbf"}),
        ]
    )
    url = geofabrik.resolve_dated(
        "europe/germany/berlin", _client(lambda r: next(answers)), backoff_s=0
    )
    assert url == "https://download.geofabrik.de/europe/germany/berlin-260930.osm.pbf"


def test_resolve_dated_gives_up_on_a_persistent_trailing_slash_redirect():
    h = {"location": "berlin-latest.osm.pbf/"}
    with pytest.raises(DownloadError, match="trailing slash"):
        geofabrik.resolve_dated(
            "r", _client(lambda r: httpx.Response(301, headers=h)), retries=2, backoff_s=0
        )


def test_resolve_dated_retries_a_transient_5xx():
    answers = iter(
        [httpx.Response(502), httpx.Response(307, headers={"location": "b-260930.osm.pbf"})]
    )
    url = geofabrik.resolve_dated("r", _client(lambda r: next(answers)), backoff_s=0)
    assert url.endswith("/b-260930.osm.pbf")


def test_fetch_region_retries_a_transient_md5_error(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    md5_calls = []

    def handler(r):
        if r.method == "HEAD":
            return httpx.Response(307, headers={"location": "b-260930.osm.pbf"})
        if r.url.path.endswith(".md5"):
            md5_calls.append(1)
            if len(md5_calls) == 1:
                return httpx.Response(502)
            return httpx.Response(200, text=f"{MD5}  b-260930.osm.pbf\n")
        return httpx.Response(200, content=BODY)

    monkeypatch.setattr(
        geofabrik, "fileinfo_timestamp", lambda p: datetime(2026, 9, 30, tzinfo=UTC)
    )
    rf = geofabrik.fetch_region("r", tmp_path, client=_client(handler), backoff_s=0)
    assert rf.md5 == MD5 and len(md5_calls) == 2
