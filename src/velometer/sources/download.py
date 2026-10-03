"""HTTP downloads: streamed to .part, md5-verified, atomically renamed, bounded retries."""

import hashlib
import os
import time
from importlib.metadata import version
from pathlib import Path

import httpx


class DownloadError(RuntimeError):
    pass


def user_agent() -> str:
    base = f"velometer/{version('velometer')}"
    contact = os.environ.get("VELOMETER_CONTACT")
    return f"{base}; {contact}" if contact else base


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def new_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": user_agent()}, timeout=120, follow_redirects=True)


def is_transient(e: httpx.HTTPError) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        return code >= 500 or code in (408, 429)
    return True


def fetch(
    url: str,
    dst: Path,
    *,
    md5: str | None = None,
    verify_length: bool = False,
    client: httpx.Client | None = None,
    retries: int = 3,
    backoff_s: float = 5.0,
) -> Path:
    """Download url to dst via a .part file, verify md5, rename atomically.

    An existing dst is trusted when md5 is None, so callers without a published md5 must use
    versioned file names (e.g. GISCO's names carry the year). Only transient failures are
    retried (transport errors, 5xx, 408, 429); other HTTP errors raise DownloadError at once.
    With verify_length, a response that carried a Content-Length must deliver exactly that many
    bytes (a truncated body raises DownloadError); meant for downloads accepted without an md5.
    Non-HTTP errors (e.g. OSError while writing) propagate unwrapped. No .part survives a failure.
    """
    if retries < 1:
        raise ValueError(f"retries must be >= 1, got {retries}")
    if dst.exists() and (md5 is None or md5_of(dst) == md5):
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    own = client is None
    client = client or new_client()
    try:
        for attempt in range(1, retries + 1):
            try:
                with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    written = 0
                    with part.open("wb") as f:
                        for chunk in resp.iter_bytes(1 << 20):
                            written += f.write(chunk)
                    declared = resp.headers.get("Content-Length")
                    # a Content-Encoding makes the declared length that of the encoded body
                    plain = "Content-Encoding" not in resp.headers
                    if (
                        verify_length
                        and plain
                        and declared is not None
                        and declared.isdigit()
                        and written != int(declared)
                    ):
                        raise DownloadError(
                            f"{url}: got {written} bytes, Content-Length said {declared}"
                        )
                if md5 is not None and md5_of(part) != md5:
                    raise DownloadError(f"{url}: md5 mismatch (expected {md5})")
                part.replace(dst)
                return dst
            except httpx.HTTPError as e:
                part.unlink(missing_ok=True)
                if attempt == retries or not is_transient(e):
                    raise DownloadError(f"{url}: {e}") from e
                time.sleep(backoff_s * attempt)
        raise AssertionError("unreachable")  # pragma: no cover
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    finally:
        if own:
            client.close()
