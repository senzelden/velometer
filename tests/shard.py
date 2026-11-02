"""Splits the suite into CI shards by test file (`VELOMETER_TEST_SHARD=k/n`, k in 1..n).

By file, not by test, so a module-scoped fixture is built in one shard only. The hash is
crc32 of the file's repo-relative path, stable across runs and machines (`hash()` is salted).
"""

import zlib


def parse_shard(spec: str) -> tuple[int, int]:
    """`"k/n"` as (k, n); raises ValueError unless 1 <= k <= n."""
    k, sep, n = spec.partition("/")
    if not sep or not k.isdigit() or not n.isdigit() or not 1 <= int(k) <= int(n):
        raise ValueError(f"VELOMETER_TEST_SHARD={spec!r}: expected k/n with 1 <= k <= n")
    return int(k), int(n)


def shard_index(path: str, total: int) -> int:
    """The 1-based shard of the test file at `path` (repo-relative, forward slashes)."""
    return zlib.crc32(path.encode("utf-8")) % total + 1
