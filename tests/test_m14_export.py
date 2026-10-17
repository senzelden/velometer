"""M14 export, part 2: `.gz` siblings, the size guard and `_headers`."""

import gzip
import re
from pathlib import Path

import pytest

from tests.test_app_base import rich  # noqa: F401  (`rich` is a fixture)
from tests.test_export import _export, _files
from velometer.app import export
from velometer.app.main import CSP, csp_meta


def _meta_csp(out: Path) -> str:
    html = (out / "index.html").read_text()
    m = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)"', html)
    assert m, "no CSP meta in index.html"
    return m.group(1).replace("&#39;", "'")


def test_gz_siblings_for_big_text_files(rich, tmp_path):  # noqa: F811
    out = tmp_path / "out"
    _export(rich, out)
    files = _files(out)
    eligible = [
        p for p in files if p.suffix in export.GZ_TYPES and p.stat().st_size >= export.GZ_MIN_BYTES
    ]
    assert eligible
    for p in eligible:
        gz = p.with_name(p.name + ".gz")
        assert gz.is_file(), p
        assert gzip.decompress(gz.read_bytes()) == p.read_bytes()
    # no .gz for a small file, another type, or a .gz itself
    for p in files:
        if p.suffix == ".gz":
            origin = p.with_name(p.name.removesuffix(".gz"))
            assert origin in eligible
            assert not p.with_name(p.name + ".gz").exists()
        elif p not in eligible:
            assert not p.with_name(p.name + ".gz").exists(), p
    assert any(p.suffix == ".png" for p in files)


def test_gz_is_reproducible(rich, tmp_path):  # noqa: F811
    a, b = tmp_path / "a", tmp_path / "b"
    _export(rich, a)
    _export(rich, b)
    gzs = [p for p in _files(a) if p.suffix == ".gz"]
    assert gzs
    compared = 0
    for p in gzs:
        origin = p.with_name(p.name.removesuffix(".gz"))
        if origin.read_bytes() != (b / origin.relative_to(a)).read_bytes():
            continue  # the source differs (the CSVs and build.json carry a build time)
        compared += 1
        assert p.read_bytes() == (b / p.relative_to(a)).read_bytes(), p
    assert compared > 10


def test_write_gz_counts_and_stores_no_name(tmp_path):
    (tmp_path / "big.json").write_bytes(b"x" * export.GZ_MIN_BYTES)
    (tmp_path / "small.json").write_bytes(b"x" * (export.GZ_MIN_BYTES - 1))
    (tmp_path / "big.png").write_bytes(b"x" * 5000)
    assert export.write_gz(tmp_path) == 1
    raw = (tmp_path / "big.json.gz").read_bytes()
    assert raw[4:8] == b"\0\0\0\0"  # mtime 0
    assert raw[3] == 0  # no FNAME flag: no file name stored
    assert not (tmp_path / "small.json.gz").exists()
    assert not (tmp_path / "big.png.gz").exists()


def test_oversized_boundary(tmp_path):
    limit = 100
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "at.bin").write_bytes(b"x" * limit)
    (tmp_path / "under.bin").write_bytes(b"x" * (limit - 1))
    assert export.oversized(tmp_path, limit) == ["sub/at.bin"]


def test_max_file_bytes_is_25_mib():
    assert export.MAX_FILE_BYTES == 25 * 1024 * 1024


def test_export_refuses_an_oversized_file(rich, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(export, "MAX_FILE_BYTES", 5000)
    out = tmp_path / "out"
    with pytest.raises(export.ExportError) as e:
        _export(rich, out)
    assert "index.html" in str(e.value) or "static/" in str(e.value)
    assert not out.exists()


def test_oversized_sees_gz_and_headers(tmp_path):
    (tmp_path / "a.json.gz").write_bytes(b"x" * 10)
    (tmp_path / export.HEADERS_FILE).write_text("x" * 10)
    assert export.oversized(tmp_path, 10) == ["_headers", "a.json.gz"]


def test_headers_file(rich, tmp_path):  # noqa: F811
    out = tmp_path / "out"
    _export(rich, out)
    text = (out / export.HEADERS_FILE).read_text()
    lines = text.splitlines()
    assert lines[0] == "/*"
    fields = [ln.strip() for ln in lines[1:] if ln.strip()]
    assert f"Content-Security-Policy: {_meta_csp(out)}; frame-ancestors 'none'" in fields
    assert "X-Content-Type-Options: nosniff" in fields
    assert "Referrer-Policy: strict-origin-when-cross-origin" in fields
    assert "Cache-Control: public, max-age=3600" in fields
    assert all(ln.startswith("  ") for ln in lines[1:] if ln)


def test_headers_path_pattern_follows_base(rich, tmp_path):  # noqa: F811
    out = tmp_path / "out"
    _export(rich, out, base="/velometer/")
    assert (out / export.HEADERS_FILE).read_text().splitlines()[0] == "/velometer/*"


def test_headers_text_uses_the_given_policy():
    text = export.headers_text("/", csp_meta(CSP))
    assert f"Content-Security-Policy: {csp_meta(CSP)}; frame-ancestors 'none'" in text


def test_scan_ignores_gz_and_headers(rich, tmp_path):  # noqa: F811
    out = tmp_path / "out"
    _export(rich, out)
    (out / "evil.html.gz").write_bytes(b"/nowhere/at/all.js")
    (out / export.HEADERS_FILE).write_text("/missing/ref.js\n")
    assert export.scan_references(out, "/") == []
