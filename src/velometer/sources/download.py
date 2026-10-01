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


def fetch(
    url: str,
    dst: Path,
    *,
    md5: str | None = None,
    client: httpx.Client | None = None,
    retries: int = 3,
    backoff_s: float = 5.0,
) -> Path:
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
                    with part.open("wb") as f:
                        for chunk in resp.iter_bytes(1 << 20):
                            f.write(chunk)
                break
            except httpx.HTTPError as e:
                part.unlink(missing_ok=True)
                if attempt == retries:
                    raise DownloadError(f"{url}: {e}") from e
                time.sleep(backoff_s * attempt)
        if md5 is not None and md5_of(part) != md5:
            part.unlink()
            raise DownloadError(f"{url}: md5 mismatch (expected {md5})")
        part.replace(dst)
        return dst
    finally:
        if own:
            client.close()
