import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from velometer.sources.download import DownloadError
from velometer.sources.geofabrik import (
    INDEX_URL,
    HistoryFile,
    fetch_history,
    fetch_index,
    history_set_md5,
    load_index,
    regions_for,
)
from velometer.sources.geofabrik_auth import Cookie

FIX = Path(__file__).parent / "fixtures" / "geofabrik"
BODY = b"history-bytes" * 500
MD5 = hashlib.md5(BODY).hexdigest()
TODAY = date(2026, 10, 1)
URL = "https://osm-internal.download.geofabrik.de/a-internal.osh.pbf"
IDX = {"a": {"geometry": None, "parent": None, "history": URL}}


def _cookie(value="v1"):
    return Cookie("gf_download_oauth", value, datetime.now(UTC) + timedelta(hours=24))


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_regions_for_covers_polygon_with_no_redundant_region():
    idx = load_index(FIX / "index_small.json")
    poly = box(0.5, 0.5, 1.5, 0.9)  # spans leaves a and b
    got = regions_for(poly, idx)
    assert got.regions == ["a", "b"]
    assert got.uncovered_km2 < 1e-6
    union = unary_union([idx[r]["geometry"] for r in got.regions])
    assert union.contains(poly)
    for r in got.regions:  # rule: dropping any chosen region uncovers the polygon
        rest = unary_union([idx[o]["geometry"] for o in got.regions if o != r])
        assert not rest.contains(poly)


def test_regions_for_never_returns_a_parent_region():
    idx = load_index(FIX / "index_small.json")
    assert idx["a"]["parent"] == "world"
    assert regions_for(box(0.2, 0.2, 0.4, 0.4), idx).regions == ["a"]
    assert "world" not in regions_for(box(0.2, 0.2, 1.8, 1.8), idx).regions


def test_regions_for_sliver_below_tolerance_pulls_in_no_neighbour():
    idx = load_index(FIX / "index_small.json")
    got = regions_for(box(0.5, 0.5, 1.0003, 0.9), idx)  # ~1.5 km2 sticks into b
    assert got.regions == ["a"]
    assert 0.5 < got.uncovered_km2 < 2.4


def test_regions_for_overlap_above_tolerance_pulls_in_the_neighbour():
    idx = load_index(FIX / "index_small.json")
    got = regions_for(box(0.5, 0.5, 1.05, 0.9), idx)  # ~240 km2 in b
    assert got.regions == ["a", "b"]


def test_regions_for_tolerance_is_adjustable():
    idx = load_index(FIX / "index_small.json")
    poly = box(0.5, 0.5, 1.0003, 0.9)
    assert regions_for(poly, idx, tolerance_km2=0.1, tolerance_frac=0).regions == ["a", "b"]


def test_regions_for_single_containing_leaf_beats_a_two_leaf_set():
    idx = load_index(FIX / "index_small.json")
    idx["e"] = {"geometry": box(0, 0, 1.2, 1), "parent": "world", "history": "https://h/e"}
    assert regions_for(box(0.5, 0.2, 1.1, 0.4), idx).regions == ["e"]


def test_regions_for_single_covering_leaf_with_smallest_area_wins():
    idx = load_index(FIX / "index_small.json")
    idx["big"] = {"geometry": box(-5, -5, 5, 5), "parent": "world", "history": "https://h/big"}
    assert regions_for(box(0.2, 0.2, 0.4, 0.4), idx).regions == ["a"]


def test_regions_for_specific_leaves_beat_an_overlapping_aggregate():
    idx = load_index(FIX / "index_small.json")
    idx["agg"] = {"geometry": box(0, 0, 2, 1.2), "parent": "europe", "history": "https://h/agg"}
    got = regions_for(box(0.5, 0.5, 1.5, 1.5), idx)  # needs all four squares; agg is redundant
    assert got.regions == ["a", "b", "c", "d"]


def test_regions_for_buffer_pulls_in_a_neighbour():
    idx = load_index(FIX / "index_small.json")
    poly = box(0.2, 0.2, 0.999, 0.4)  # inside a, ~100 m from b's border
    assert regions_for(poly, idx).regions == ["a"]
    assert "b" in regions_for(poly, idx, buffer_m=5000).regions


def test_regions_for_raises_when_index_cannot_cover():
    idx = load_index(FIX / "index_small.json")
    with pytest.raises(ValueError, match="cover"):
        regions_for(box(5, 5, 6, 6), idx)


def test_load_index_maps_history_and_parent():
    idx = load_index(FIX / "index_small.json")
    assert idx["world"]["parent"] is None
    assert idx["a"]["history"].endswith("a-internal.osh.pbf")


def test_fetch_index_writes_dated_snapshot_and_trusts_it(tmp_path):
    calls = []

    def handler(r):
        calls.append(str(r.url))
        return httpx.Response(200, content=b'{"features": []}')

    c = _client(handler)
    p = fetch_index(tmp_path, client=c, today=TODAY)
    assert p == tmp_path / "external" / "geofabrik" / "index-v1-20261001.json"
    assert json.loads(p.read_text()) == {"features": []}
    assert fetch_index(tmp_path, client=c, today=TODAY) == p
    assert calls == [INDEX_URL]


def _history_handler(seen, *, md5_body=None, statuses=None):
    statuses = list(statuses or [])

    def handler(r):
        seen.append((str(r.url), r.headers.get("cookie")))
        if str(r.url).endswith(".md5"):
            if md5_body is None:
                return httpx.Response(404)
            return httpx.Response(200, text=md5_body)
        if statuses:
            code = statuses.pop(0)
            if code != 200:
                return httpx.Response(code)
        return httpx.Response(200, content=BODY)

    return handler


def test_fetch_history_sends_cookie_and_uses_published_md5(tmp_path):
    seen = []
    c = _client(_history_handler(seen, md5_body=f"{MD5}  a-internal.osh.pbf\n"))
    hf = fetch_history(
        "a", tmp_path, IDX, client=c, cookie_loader=lambda force=False: _cookie(), today=TODAY
    )
    assert hf.md5 == MD5 and hf.md5_source == "published" and hf.fetched_at == TODAY
    assert hf.path == tmp_path / "history" / f"a_20261001_{MD5[:8]}.osh.pbf"
    assert hf.path.read_bytes() == BODY
    assert [u for u, _ in seen] == [URL + ".md5", URL]
    assert all(ck == "gf_download_oauth=v1" for _, ck in seen)
    assert sorted(p.name for p in (tmp_path / "history").iterdir()) == [hf.path.name]


def test_fetch_history_computes_md5_when_none_published(tmp_path):
    c = _client(_history_handler([]))
    hf = fetch_history(
        "a", tmp_path, IDX, client=c, cookie_loader=lambda force=False: _cookie(), today=TODAY
    )
    assert hf.md5 == MD5 and hf.md5_source == "computed"
    assert hf.path.name == f"a_20261001_{MD5[:8]}.osh.pbf" and hf.path.exists()


def test_fetch_history_ignores_a_200_that_is_no_md5(tmp_path):
    c = _client(_history_handler([], md5_body="<html>please log in</html>"))
    hf = fetch_history(
        "a", tmp_path, IDX, client=c, cookie_loader=lambda force=False: _cookie(), today=TODAY
    )
    assert hf.md5_source == "computed"


def test_fetch_history_slug_of_a_path_style_region(tmp_path):
    idx = {"europe/germany/berlin": {"geometry": None, "parent": None, "history": URL}}
    c = _client(_history_handler([]))
    hf = fetch_history(
        "europe/germany/berlin",
        tmp_path,
        idx,
        client=c,
        cookie_loader=lambda force=False: _cookie(),
        today=TODAY,
    )
    assert hf.path.parent == tmp_path / "history" and "/" not in hf.path.name


def test_fetch_history_relogs_once_on_403(tmp_path):
    seen, forced = [], []

    def loader(force=False):
        forced.append(force)
        return _cookie("v2" if force else "v1")

    c = _client(_history_handler(seen, statuses=[403, 200]))
    hf = fetch_history("a", tmp_path, IDX, client=c, cookie_loader=loader, today=TODAY)
    assert forced == [False, True]
    assert hf.path.exists()
    assert seen[-1][1] == "gf_download_oauth=v2"
    assert not list((tmp_path / "history").glob("*.part"))


def test_fetch_history_relogs_when_the_md5_request_is_refused(tmp_path):
    forced = []

    def handler(r):
        if r.headers.get("cookie") == "gf_download_oauth=v1":
            return httpx.Response(401)
        return httpx.Response(200, content=BODY)

    def loader(force=False):
        forced.append(force)
        return _cookie("v2" if force else "v1")

    hf = fetch_history("a", tmp_path, IDX, client=_client(handler), cookie_loader=loader)
    assert forced == [False, True] and hf.path.exists()


def test_fetch_history_gives_up_after_second_403(tmp_path):
    forced = []

    def loader(force=False):
        forced.append(force)
        return _cookie()

    c = _client(_history_handler([], statuses=[403, 403]))
    with pytest.raises(DownloadError):
        fetch_history("a", tmp_path, IDX, client=c, cookie_loader=loader, today=TODAY)
    assert forced == [False, True]
    assert not (tmp_path / "history").exists() or list((tmp_path / "history").iterdir()) == []


def test_fetch_history_does_not_retry_other_client_errors(tmp_path):
    forced = []
    c = _client(_history_handler([], statuses=[404]))
    with pytest.raises(DownloadError):
        fetch_history(
            "a",
            tmp_path,
            IDX,
            client=c,
            cookie_loader=lambda force=False: forced.append(force) or _cookie(),
            today=TODAY,
        )
    assert forced == [False]


def test_fetch_history_skips_download_when_file_with_published_md5_exists(tmp_path):
    dst = tmp_path / "history" / f"a_20261001_{MD5[:8]}.osh.pbf"
    dst.parent.mkdir(parents=True)
    dst.write_bytes(BODY)

    def handler(r):
        if str(r.url).endswith(".md5"):
            return httpx.Response(200, text=f"{MD5}  x\n")
        pytest.fail("history downloaded again")

    hf = fetch_history(
        "a",
        tmp_path,
        IDX,
        client=_client(handler),
        cookie_loader=lambda force=False: _cookie(),
        today=TODAY,
    )
    assert hf.path == dst


def test_history_set_md5_is_order_independent():
    a = HistoryFile("a", Path("a"), "1" * 32, "published", TODAY)
    b = HistoryFile("b", Path("b"), "2" * 32, "computed", TODAY)
    want = hashlib.md5(f"a:{'1' * 32}\nb:{'2' * 32}".encode()).hexdigest()
    assert history_set_md5([a, b]) == history_set_md5([b, a]) == want
    c = HistoryFile("b", Path("b"), "3" * 32, "computed", TODAY)
    assert history_set_md5([a, c]) != want
