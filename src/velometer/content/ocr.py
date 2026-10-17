"""OCR for the scanned pages of a PDF source, through the Mistral OCR API (M14 section 4.5).

`content --check --online` reads a PDF with `pdftotext`; a scanned page has no text layer. Only
those empty pages are cut out (`pdfseparate`), joined (`pdfunite`) and sent, so only they are
billed. The text is cached by the PDF's SHA-256 and the page number.

API shape, read from Mistral's documentation on 2026-10-16
(https://docs.mistral.ai/api/endpoint/ocr and https://docs.mistral.ai/capabilities/document_ai/basic_ocr/):

- `POST https://api.mistral.ai/v1/ocr`, header `Authorization: Bearer <key>`;
- body `{"model": "mistral-ocr-latest", "document": {"type": "document_url", "document_url": ...}}`;
  the reference page only shows a public URL for `document_url`. The base64 form
  `data:application/pdf;base64,<data>` is the one third-party integration guides (LiteLLM,
  Codesota) use with the same field; the first live call (Task 12) confirms it;
- optional `pages` (0-based list or "0,2-4" string); this module sends no `pages`, it cuts the
  pages out itself;
- there is no language parameter, so none is taken;
- the 200 response is `{"pages": [{"index", "markdown", ...}], "model", "usage_info"}`. The docs'
  sample shows a first `index` of 1 while `pages` is documented as 0-based, so a page is matched
  to the one sent by its position in `pages`, never by `index` arithmetic.

The key is read from `MISTRAL_API_KEY` and never printed, logged or written.
"""

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx

OCR_MODEL = "mistral-ocr-latest"
OCR_URL = "https://api.mistral.ai/v1/ocr"
MAX_OCR_PAGES = 20
CACHE_DIR = Path("data/cache/ocr")  # also holds the scratch directory of a cut (git-ignored)
POPPLER_TIMEOUT = 60
REQUEST_TIMEOUT = 60.0
PDFINFO_NOTE = "OCR skipped: pdfinfo unavailable or could not count the PDF's pages"
NO_KEY_NOTE = (
    "OCR not available: set MISTRAL_API_KEY (use_pass_optional MISTRAL_API_KEY api/mistral in "
    ".envrc)"
)


@dataclass
class OcrResult:
    texts: dict[int, str] = field(default_factory=dict)  # 1-based original page -> text
    notes: list[str] = field(default_factory=list)
    skipped: list[int] = field(default_factory=list)  # pages over the run's limit
    sent: int = 0  # pages sent to the API (cached pages are not): the run's limit counts these


def _poppler(name: str, *args: str, input: bytes | None = None) -> bytes | None:
    """stdout of a poppler tool, or None when it is missing or fails."""
    exe = shutil.which(name)
    if exe is None:
        return None
    try:
        return subprocess.run(
            [exe, *args], input=input, capture_output=True, check=True, timeout=POPPLER_TIMEOUT
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def page_count(pdf: bytes) -> int:
    out = _poppler("pdfinfo", "-", input=pdf)
    m = re.search(rb"^Pages:\s+(\d+)", out or b"", re.M)
    return int(m.group(1)) if m else 0


def empty_pages(pdf: bytes, notes: list[str] | None = None) -> list[int]:
    """The 1-based pages of `pdf` for which `pdftotext` yields nothing but whitespace: one
    `pdftotext` run over the whole PDF, its output split at the form feed that ends each page.
    When `pdfinfo` cannot count the pages and a key is set (so OCR would apply), `notes` gets a
    note."""
    count = page_count(pdf)
    if count == 0:
        if notes is not None and os.environ.get("MISTRAL_API_KEY"):
            notes.append(PDFINFO_NOTE)
        return []
    out = _poppler("pdftotext", "-q", "-", "-", input=pdf)
    if out is None:
        return []
    texts = out.split(b"\f")
    return [n for n in range(1, count + 1) if n <= len(texts) and not texts[n - 1].strip()]


def _cut_pages(pdf: bytes, selected: list[int], work: Path) -> bytes | None:
    """A PDF of only the `selected` pages of `pdf`, in page order, or None if poppler fails."""
    src = work / "src.pdf"
    src.write_bytes(pdf)
    parts = []
    for n in selected:
        part = work / f"p{n}.pdf"
        if _poppler("pdfseparate", "-f", str(n), "-l", str(n), str(src), str(part)) is None:
            return None
        parts.append(str(part))
    if len(parts) == 1:
        return Path(parts[0]).read_bytes()
    joined = work / "joined.pdf"
    if _poppler("pdfunite", *parts, str(joined)) is None:
        return None
    return joined.read_bytes()


def markdown_to_text(md: str) -> str:
    """Plain text of OCR Markdown: image references, rules, table pipes, heading and emphasis
    marks dropped, a line-end hyphen joined to the next line."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)
    text = re.sub(
        r"^\s*(?:[-*_]{3,}|\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?)\s*$", " ", text, flags=re.M
    )
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"(?<=\w)-\n\s*(?=\w)", "", text)
    text = re.sub(r"[*_`|]+", " ", text)
    return " ".join(text.split())


def _cache_file(cache_dir: Path, sha: str, page: int) -> Path:
    return cache_dir / f"{sha}-p{page}.json"


def _error_message(resp: httpx.Response, key: str) -> str:
    try:
        body = resp.json()
        msg = body.get("message") or body.get("detail") or body
    except ValueError:
        msg = resp.text
    return str(msg).replace(key, "***")[:300]


def _post(client: httpx.Client, payload: dict, key: str) -> httpx.Response | str:
    """The response, or a note about why there is none. A timeout or a 5xx is retried once."""
    last: httpx.Response | str = "no answer"
    for _attempt in range(2):
        try:
            resp = client.post(
                OCR_URL,
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.TimeoutException:
            last = f"OCR failed: request timed out after {REQUEST_TIMEOUT:.0f} s"
            continue
        except httpx.HTTPError as e:  # any other failure of the request: its type only
            return f"OCR failed: {type(e).__name__}"
        if resp.status_code >= 500:
            last = resp
            continue
        return resp
    return last


def ocr_pages(
    pdf: bytes,
    pages: list[int],
    limit: int = MAX_OCR_PAGES,
    *,
    client: httpx.Client | None = None,
    cache_dir: Path = CACHE_DIR,
    key: str | None = None,
) -> OcrResult:
    """OCR the 1-based `pages` of `pdf` (those without a text layer). Cached pages cost nothing;
    at most `limit` others are sent in one request (`check_online` passes what is left of the
    run's MAX_OCR_PAGES), the rest are `skipped`. Without a key or on an API error `texts` lacks
    the pages and `notes` says why; this never raises."""
    result = OcrResult()
    sha = hashlib.sha256(pdf).hexdigest()
    todo = []
    for n in sorted(set(pages)):
        f = _cache_file(cache_dir, sha, n)
        try:
            result.texts[n] = json.loads(f.read_text(encoding="utf-8"))["text"]
        except (OSError, ValueError, KeyError):
            todo.append(n)
    if not todo:
        return result
    key = key if key is not None else os.environ.get("MISTRAL_API_KEY")
    if not key:
        result.notes.append(NO_KEY_NOTE)
        return result
    limit = max(limit, 0)
    if len(todo) > limit:
        result.skipped = todo[limit:]
        todo = todo[:limit]
        result.notes.append(
            f"OCR: {len(result.skipped)} pages skipped (at most {MAX_OCR_PAGES} per run): "
            + ", ".join(map(str, result.skipped))
        )
    if not todo:
        return result
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache_dir, prefix=".cut-") as tmp:
            cut = _cut_pages(pdf, todo, Path(tmp))
    except OSError as e:
        result.notes.append(f"OCR failed: {type(e).__name__} cutting the scanned pages out")
        return result
    if cut is None:
        result.notes.append("OCR failed: poppler could not cut the scanned pages out")
        return result
    payload = {
        "model": OCR_MODEL,
        "document": {
            "type": "document_url",
            "document_url": "data:application/pdf;base64," + base64.b64encode(cut).decode("ascii"),
        },
    }
    result.sent = len(todo)  # billed or not, these count against the run's limit
    own = client is None
    http = client or httpx.Client()
    try:
        resp = _post(http, payload, key)
    finally:
        if own:
            http.close()
    if isinstance(resp, str):
        result.notes.append(resp)
        return result
    if resp.status_code != 200:
        msg = _error_message(resp, key)
        result.notes.append(f"OCR failed: HTTP {resp.status_code}: {msg}")
        return result
    try:
        body = resp.json()
        answered = body["pages"]
        model = body.get("model", OCR_MODEL)
        texts = [markdown_to_text(p["markdown"]) for p in answered]
    except (ValueError, KeyError, TypeError):
        result.notes.append("OCR failed: unexpected response shape")
        return result
    if len(texts) != len(todo):
        # an answer for fewer pages than were sent cannot be trusted to line up: use what came,
        # cache none of it
        result.notes.append(f"OCR: {len(texts)} pages answered for {len(todo)} sent")
        result.texts.update(zip(todo, texts, strict=False))
        return result
    result.texts.update(zip(todo, texts, strict=True))
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        for n, text in zip(todo, texts, strict=True):
            _write_cache(_cache_file(cache_dir, sha, n), model, text)
    except OSError as e:
        result.notes.append(f"OCR: could not write the cache: {type(e).__name__}")
    return result


def _write_cache(f: Path, model: str, text: str) -> None:
    """Write the cache file whole or not at all: a temp file in the same directory, then rename."""
    tmp = f.with_name(f"{f.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps({"model": model, "text": text}, ensure_ascii=False), "utf-8")
        os.replace(tmp, f)
    finally:
        tmp.unlink(missing_ok=True)
