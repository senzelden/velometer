"""M16 Task 4: the PMTiles extract tool (`tools/tiles.py`); no network except the slow test."""

import hashlib
import io
import json
import math
import struct
import tarfile
from pathlib import Path

import pytest

from tests.helpers import ROOT, load_script

tiles = load_script("tools/tiles.py")

CITIES = """
cities:
  - id: alpha
  - id: beta
"""


def _boundary(ring):
    return {
        "type": "FeatureCollection",
        "boundary": {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        },
        "features": [],
    }


@pytest.fixture
def two_cities(tmp_path):
    cities = tmp_path / "cities.yaml"
    cities.write_text(CITIES)
    maps = tmp_path / "maps"
    maps.mkdir()
    rings = {
        "alpha": [[13.0, 52.0], [13.5, 52.0], [13.5, 52.4], [13.1, 52.45], [13.0, 52.0]],
        "beta": [[2.0, 48.5], [2.6, 48.5], [2.6, 49.0], [2.0, 48.5]],
    }
    for city, ring in rings.items():
        (maps / f"{city}_fua.geojson").write_text(json.dumps(_boundary(ring)))
    return cities, maps, rings


def test_city_bboxes_are_padded_and_contain_every_vertex(two_cities):
    cities, maps, rings = two_cities
    boxes = tiles.city_bboxes(cities, maps)
    assert set(boxes) == {"alpha", "beta"}
    for city, (w, s, e, n) in boxes.items():
        for lon, lat in rings[city]:
            assert w < lon < e and s < lat < n
        lats = [p[1] for p in rings[city]]
        lons = [p[0] for p in rings[city]]
        # 2 km of padding: about 0.018 degrees of latitude, wider in longitude.
        assert min(lats) - s == pytest.approx(2 / 111.32, rel=0.05)
        assert n - max(lats) == pytest.approx(2 / 111.32, rel=0.05)
        coslat = math.cos(math.radians(max(abs(la) for la in (s, n))))
        assert min(lons) - w == pytest.approx(2 / (111.32 * coslat), rel=0.05)


def test_a_missing_boundary_names_the_city(two_cities):
    cities, maps, _ = two_cities
    (maps / "beta_fua.geojson").unlink()
    with pytest.raises(FileNotFoundError, match="beta"):
        tiles.city_bboxes(cities, maps)


def _tarball(payload: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo("pmtiles")
        info.size = len(payload)
        info.mode = 0o755
        tar.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


def test_the_pinned_binary_is_checked_against_its_sha256(tmp_path):
    data = _tarball(b"#!/bin/sh\necho fake\n")
    good = hashlib.sha256(data).hexdigest()
    binary = tiles.ensure_pmtiles(tmp_path / "bin", fetch=lambda url: data, sha256=good)
    assert binary.read_bytes().startswith(b"#!/bin/sh")
    assert binary.stat().st_mode & 0o111


def test_a_tampered_cached_binary_is_restored_and_never_trusted(tmp_path):
    data = _tarball(b"#!/bin/sh\necho real\n")
    good = hashlib.sha256(data).hexdigest()
    calls = []

    def fetch(url):
        calls.append(url)
        return data

    binary = tiles.ensure_pmtiles(tmp_path, fetch=fetch, sha256=good)
    binary.write_bytes(b"#!/bin/sh\necho evil\n")
    assert tiles.ensure_pmtiles(tmp_path, fetch=fetch, sha256=good) == binary
    assert b"real" in binary.read_bytes()
    assert len(calls) == 1  # restored from the verified cached tarball


def test_a_tampered_cached_tarball_is_downloaded_again_or_refused(tmp_path):
    data = _tarball(b"real")
    good = hashlib.sha256(data).hexdigest()
    tiles.ensure_pmtiles(tmp_path, fetch=lambda url: data, sha256=good)
    (tmp_path / f"pmtiles-{tiles.PMTILES_VERSION}.tar.gz").write_bytes(b"junk")
    tiles.ensure_pmtiles(tmp_path, fetch=lambda url: data, sha256=good)
    (tmp_path / f"pmtiles-{tiles.PMTILES_VERSION}.tar.gz").write_bytes(b"junk")
    with pytest.raises(ValueError, match="sha256"):
        tiles.ensure_pmtiles(tmp_path, fetch=lambda url: b"also junk", sha256=good)


def test_a_checksum_mismatch_refuses_and_leaves_no_binary(tmp_path):
    data = _tarball(b"tampered")
    with pytest.raises(ValueError, match="sha256"):
        tiles.ensure_pmtiles(tmp_path / "bin", fetch=lambda url: data, sha256="0" * 64)
    assert not (tmp_path / "bin" / f"pmtiles-{tiles.PMTILES_VERSION}").exists()


def test_the_pinned_constants_are_exact():
    assert tiles.PMTILES_VERSION.count(".") == 2
    assert len(tiles.PMTILES_SHA256) == 64
    assert tiles.PROTOMAPS_BUILD.isdigit() and len(tiles.PROTOMAPS_BUILD) == 8
    assert tiles.PMTILES_URL.endswith(f"go-pmtiles_{tiles.PMTILES_VERSION}_Linux_x86_64.tar.gz")


def test_extract_builds_the_argv_with_a_region_of_the_union(tmp_path):
    boxes = {"alpha": (13.0, 52.0, 13.5, 52.4), "beta": (2.0, 48.5, 2.6, 49.0)}
    seen = {}

    def run(argv):
        seen["argv"] = argv
        region = json.loads(Path(argv[argv.index("--region") + 1]).read_text())
        seen["region"] = region
        Path(argv[-1]).write_bytes(b"x" * 123)

    out = tmp_path / "o" / "v.pmtiles"
    size = tiles.extract(
        "https://build.protomaps.com/20260811.pmtiles",
        boxes,
        14,
        out,
        binary=Path("/bin/pmtiles"),
        run=run,
    )
    argv = seen["argv"]
    assert argv[:2] == ["/bin/pmtiles", "extract"]
    assert argv[2] == "https://build.protomaps.com/20260811.pmtiles"
    assert argv[argv.index("--maxzoom") + 1] == "14"
    assert "--bbox" not in argv
    assert argv[-1].endswith(".pmtiles") and size == 123 and out.stat().st_size == 123
    geometry = seen["region"]["geometry"] if "geometry" in seen["region"] else seen["region"]
    assert geometry["type"] == "MultiPolygon"
    assert len(geometry["coordinates"]) == 2
    corners = {tuple(p) for poly in geometry["coordinates"] for p in poly[0]}
    assert (13.0, 52.0) in corners and (2.6, 49.0) in corners


def test_extract_does_not_leave_a_partial_output_when_the_tool_fails(tmp_path):
    def run(argv):
        Path(argv[-1]).write_bytes(b"partial")
        raise RuntimeError("boom")

    out = tmp_path / "v.pmtiles"
    with pytest.raises(RuntimeError):
        tiles.extract("u", {"a": (0, 0, 1, 1)}, 14, out, binary=Path("pmtiles"), run=run)
    assert not out.exists()


def test_measure_reads_the_predicted_archive_size_and_keeps_nothing(tmp_path):
    seen = []

    def capture(argv):
        seen.append(argv)
        return "x: Extract transferred 1.8 GB (overfetch 0.05) for an archive size of 1.7 GB\n"

    got = tiles.measure("u", {"a": (0, 0, 1, 1)}, 14, binary=Path("pmtiles"), capture=capture)
    assert got == "1.7 GB"
    assert "--dry-run" in seen[0] and seen[0][seen[0].index("--maxzoom") + 1] == "14"
    with pytest.raises(RuntimeError, match="no archive size"):
        tiles.measure("u", {}, 14, binary=Path("pmtiles"), capture=lambda argv: "nothing")


def test_the_tile_directory_is_git_ignored():
    import subprocess

    r = subprocess.run(
        ["git", "check-ignore", "data/tiles/velometer.pmtiles"], cwd=ROOT, capture_output=True
    )
    assert r.returncode == 0


FIXTURE = ROOT / "tests" / "fixtures" / "tiles" / "berlin-z0-8.pmtiles"


def test_the_fixture_is_a_small_berlin_archive_for_zoom_0_to_8_with_its_attribution():
    head = FIXTURE.read_bytes()[:127]
    assert head[:7] == b"PMTiles" and head[7] == 3
    assert (head[100], head[101]) == (0, 8)  # min and max zoom
    west, south, east, north = (
        struct.unpack_from("<i", head, off)[0] / 1e7 for off in (102, 106, 110, 114)
    )
    assert 13.0 <= west < east <= 13.9 and 52.3 <= south < north <= 52.7
    assert FIXTURE.stat().st_size < 2_000_000
    text = (FIXTURE.parent / "ATTRIBUTION.txt").read_text()
    assert "OpenStreetMap contributors" in text and "ODbL" in text and "Protomaps" in text
    assert FIXTURE.name in text


# --- the sidecar: the build the extract was cut from (final review I3) --------------------------

FIXTURE = ROOT / "tests" / "fixtures" / "tiles" / "berlin-z0-8.pmtiles"


def test_the_sidecar_records_build_maxzoom_and_checksum(tmp_path):
    out = tmp_path / "velometer.pmtiles"
    out.write_bytes(FIXTURE.read_bytes())
    info = tiles.write_sidecar(out, "https://build.protomaps.com/20260811.pmtiles")
    on_disk = json.loads((tmp_path / "velometer.pmtiles.json").read_text(encoding="utf-8"))
    assert on_disk == info
    assert info["protomaps_build"] == "2026-08-11"
    assert info["maxzoom"] == 8  # read from the file, not from an argument
    assert info["sha256"] == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()


def test_the_sidecar_refuses_an_undated_build_or_a_file_that_is_no_pmtiles(tmp_path):
    out = tmp_path / "v.pmtiles"
    out.write_bytes(FIXTURE.read_bytes())
    with pytest.raises(ValueError, match="dated"):
        tiles.write_sidecar(out, "https://build.protomaps.com/latest.pmtiles")
    out.write_bytes(b"not a tile archive" * 10)
    with pytest.raises(ValueError, match="PMTiles"):
        tiles.write_sidecar(out, "https://build.protomaps.com/20260811.pmtiles")


def test_every_cut_writes_its_sidecar(tmp_path, two_cities, monkeypatch):
    cities, maps, _ = two_cities
    site = tmp_path / "site"
    site.mkdir()
    (site / "maps").symlink_to(maps)
    out = tmp_path / "o" / "velometer.pmtiles"

    def fake_extract(build_url, boxes, maxzoom, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(FIXTURE.read_bytes())
        return out_path.stat().st_size

    monkeypatch.setattr(tiles, "extract", fake_extract)
    args = ["--site", str(site), "--cities", str(cities), "--out", str(out)]
    assert tiles.main(args) == 0
    info = json.loads(tiles.sidecar_path(out).read_text(encoding="utf-8"))
    assert info["protomaps_build"] == tiles.build_date(tiles.BUILD_URL)
    (tmp_path / "o" / "velometer.pmtiles.json").unlink()
    assert tiles.main(["--stamp", "--out", str(out)]) == 0
    assert json.loads(tiles.sidecar_path(out).read_text(encoding="utf-8")) == info
