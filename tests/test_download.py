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
