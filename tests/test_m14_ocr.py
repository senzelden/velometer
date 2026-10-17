"""Task 9 (M14 section 4.5): scanned PDF pages are OCRed through Mistral OCR.

Every HTTP call goes through httpx.MockTransport shaped like the API documented at
https://docs.mistral.ai/api/endpoint/ocr (checked 2026-10-16): POST with a Bearer key,
{"model", "document": {"type": "document_url", "document_url": "data:application/pdf;base64,..."}},
answered by {"pages": [{"index", "markdown"}], "model"}. No test reaches the network.
"""

import base64
import copy
import json
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

from tests.content_util import SOURCES
from tests.test_content_check import load_sources_from
from velometer.content import ocr
from velometer.content.check import check_online

HERE = Path(__file__).parent
SCANNED = HERE / "fixtures/ocr/five-pages-p3-scanned.pdf"  # page 3 is an image, 1/2/4/5 are text
TEXT_PDF = HERE / "fixtures/content_online/excerpt.pdf"
KEY = "test-key-not-real"
NO_KEY_NOTE = (
    "OCR not available: set MISTRAL_API_KEY (use_pass_optional MISTRAL_API_KEY api/mistral in "
    ".envrc)"
)

pytestmark = pytest.mark.skipif(
    shutil.which("pdftotext") is None or shutil.which("pdfunite") is None, reason="no poppler"
)


class Api:
    """A mocked Mistral OCR endpoint that records the requests it gets."""

    def __init__(self, handler=None):
        self.requests: list[httpx.Request] = []
        self.handler = handler or self.ok

    def ok(self, request: httpx.Request) -> httpx.Response:
        n = _sent_pages(request)
        pages = [{"index": i, "markdown": f"# Scan {i}\n\nVerkehrs-\nwende"} for i in range(n)]
        return httpx.Response(200, json={"model": "mistral-ocr-test", "pages": pages})

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def _body(request: httpx.Request) -> dict:
    return json.loads(request.content)


def _sent_pdf(request: httpx.Request) -> bytes:
    doc = _body(request)["document"]
    assert doc["type"] == "document_url"
    prefix = "data:application/pdf;base64,"
    assert doc["document_url"].startswith(prefix)
    return base64.b64decode(doc["document_url"][len(prefix) :])


def _sent_pages(request: httpx.Request) -> int:
    out = subprocess.run(["pdfinfo", "-"], input=_sent_pdf(request), capture_output=True)
    return int(next(x for x in out.stdout.decode().splitlines() if x.startswith("Pages:"))[6:])


@pytest.fixture
def api():
    return Api()


def _ocr(api, pdf=None, pages=(3,), tmp=None, **kw):
    with api.client() as c:
        return ocr.ocr_pages(
            pdf or SCANNED.read_bytes(), list(pages), client=c, cache_dir=tmp, key=KEY, **kw
        )


def test_only_the_empty_page_is_found_and_sent(api, tmp_path):
    pdf = SCANNED.read_bytes()
    assert ocr.empty_pages(pdf) == [3]
    result = _ocr(api, pdf, tmp=tmp_path)
    assert len(api.requests) == 1
    assert _sent_pages(api.requests[0]) == 1
    req = api.requests[0]
    assert req.url == httpx.URL(ocr.OCR_URL)
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert _body(req)["model"] == ocr.OCR_MODEL
    assert list(result.texts) == [3]
    assert result.texts[3] == "Scan 0 Verkehrswende"
    assert result.notes == [] and result.skipped == []


def test_check_online_finds_an_excerpt_only_the_ocr_text_holds(tmp_path):
    def handler(request):
        return httpx.Response(
            200,
            json={"model": "m", "pages": [{"index": 0, "markdown": "Das **Radnetz** misst 5 km"}]},
        )

    api = Api(handler)
    doc = copy.deepcopy(SOURCES)
    doc["sources"][0]["excerpts"][0]["text"] = "Das Radnetz misst 5 km"
    sources = load_sources_from(doc)
    with api.client() as c:
        ocr_call = lambda pdf, pages, limit: ocr.ocr_pages(  # noqa: E731
            pdf, pages, limit, client=c, cache_dir=tmp_path, key=KEY
        )
        problems, notes = check_online(sources, fetch=lambda u: SCANNED.read_bytes(), ocr=ocr_call)
    assert (problems, notes) == ([], [])
    assert len(api.requests) == 1 and _sent_pages(api.requests[0]) == 1
    # without OCR the same excerpt is not on the page
    problems, _ = check_online(sources, fetch=lambda u: SCANNED.read_bytes(), ocr=None)
    assert problems == ["sources/src: excerpt not found online: e1"]


def test_a_text_only_pdf_never_reaches_the_api(api, tmp_path):
    assert ocr.empty_pages(TEXT_PDF.read_bytes()) == []
    with api.client() as c:
        ocr_call = lambda pdf, pages, limit: ocr.ocr_pages(  # noqa: E731
            pdf, pages, limit, client=c, cache_dir=tmp_path, key=KEY
        )
        assert check_online(
            load_sources_from(SOURCES), fetch=lambda u: TEXT_PDF.read_bytes(), ocr=ocr_call
        ) == ([], [])
    assert api.requests == []


def test_markdown_to_text():
    md = (
        "# Title\n\n**bold** and *em* and _u_\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n---\n\n"
        "![img-0.jpeg](img-0.jpeg)\n\nVerkehrs-\nwende"
    )
    text = ocr.markdown_to_text(md)
    for mark in ("#", "*", "|", "---", "img-0", "!["):
        assert mark not in text
    for word in ("Title", "bold", "em", "1", "2"):
        assert word in text.split()
    assert "Verkehrswende" in text


def test_the_cache_answers_a_second_call_and_never_names_the_key(api, tmp_path):
    first = _ocr(api, tmp=tmp_path)
    assert len(api.requests) == 1
    again = _ocr(api, tmp=tmp_path)
    assert len(api.requests) == 1
    assert again.texts == first.texts
    files = list(tmp_path.iterdir())
    sha = __import__("hashlib").sha256(SCANNED.read_bytes()).hexdigest()
    assert [f.name for f in files] == [f"{sha}-p3.json"]
    stored = json.loads(files[0].read_text(encoding="utf-8"))
    assert stored == {"model": "mistral-ocr-test", "text": first.texts[3]}
    assert KEY not in files[0].name + files[0].read_text(encoding="utf-8")
    # a different PDF is OCRed again
    _ocr(api, pdf=TEXT_PDF.read_bytes(), pages=[1], tmp=tmp_path)
    assert len(api.requests) == 2


def test_no_key_makes_no_request_and_one_note(api, tmp_path, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with api.client() as c:
        result = ocr.ocr_pages(SCANNED.read_bytes(), [3], client=c, cache_dir=tmp_path)
    assert api.requests == []
    assert result.texts == {} and result.notes == [NO_KEY_NOTE]


def test_the_key_defaults_to_the_environment(api, tmp_path, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", KEY)
    with api.client() as c:
        ocr.ocr_pages(SCANNED.read_bytes(), [3], client=c, cache_dir=tmp_path)
    assert api.requests[0].headers["authorization"] == f"Bearer {KEY}"


@pytest.mark.parametrize("status", [401, 500])
def test_an_api_error_is_a_note_with_status_and_message_but_not_the_key(tmp_path, status):
    api = Api(lambda r: httpx.Response(status, json={"message": f"Unauthorized {KEY}"}))
    result = _ocr(api, tmp=tmp_path)
    assert result.texts == {}
    assert len(result.notes) == 1
    assert str(status) in result.notes[0] and "Unauthorized" in result.notes[0]
    assert KEY not in result.notes[0]
    assert len(api.requests) == (2 if status >= 500 else 1)


def test_a_timeout_is_retried_once_then_succeeds(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"model": "m", "pages": [{"index": 0, "markdown": "ok"}]})

    api = Api(handler)
    result = _ocr(api, tmp=tmp_path)
    assert len(api.requests) == 2 and result.texts == {3: "ok"}


def test_a_timeout_twice_is_a_note(tmp_path):
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    api = Api(handler)
    result = _ocr(api, tmp=tmp_path)
    assert len(api.requests) == 2
    assert result.texts == {} and len(result.notes) == 1 and "timed out" in result.notes[0]


def test_over_the_cap_the_rest_is_skipped_with_a_note(tmp_path, monkeypatch):
    sent: list[list[int]] = []

    def cut(pdf, selected, work):
        sent.append(list(selected))
        return b"%PDF-1.4 stand-in"

    def handler(request):
        pages = [{"index": i, "markdown": f"t{i}"} for i in range(len(sent[-1]))]
        return httpx.Response(200, json={"model": "m", "pages": pages})

    monkeypatch.setattr(ocr, "_cut_pages", cut)
    api = Api(handler)
    result = _ocr(api, pages=range(1, 26), tmp=tmp_path)
    assert sent == [list(range(1, 21))] and len(api.requests) == 1
    assert result.skipped == [21, 22, 23, 24, 25]
    assert sorted(result.texts) == list(range(1, 21))
    assert any("5 pages" in n and "skipped" in n for n in result.notes)


def test_the_ocr_text_of_each_sent_page_goes_to_its_own_page_number(tmp_path):
    def handler(request):
        pages = [{"index": i, "markdown": f"text {i}"} for i in range(2)]
        return httpx.Response(200, json={"model": "m", "pages": pages})

    api = Api(handler)
    result = _ocr(api, pdf=SCANNED.read_bytes(), pages=[3, 5], tmp=tmp_path)
    assert result.texts == {3: "text 0", 5: "text 1"}


@pytest.fixture(scope="session")
def _key_at_session_setup():
    """Whether a session fixture, set up before any test's own fixtures, sees the key."""
    import os

    return "MISTRAL_API_KEY" in os.environ


def test_the_suite_has_no_mistral_key(_key_at_session_setup):
    """Run by the guard below with a key in the process environment."""
    import os

    assert "MISTRAL_API_KEY" not in os.environ
    assert not _key_at_session_setup


def test_a_key_in_the_environment_never_reaches_a_test():
    """Guard: pytest run inside direnv has a real MISTRAL_API_KEY. tests/conftest.py must drop it
    for every test, or check_online's default OCR would make a billed call."""
    import os
    import sys

    env = {**os.environ, "MISTRAL_API_KEY": "dummy-not-real"}
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header",
         f"{__file__}::test_the_suite_has_no_mistral_key"],
        env=env, capture_output=True, text=True, cwd=HERE.parent,
    )  # fmt: skip
    assert out.returncode == 0, out.stdout[-800:]


def test_check_online_without_a_key_sends_nothing_by_default(monkeypatch):
    reached: list[httpx.Request] = []

    def boom(request):
        reached.append(request)
        raise AssertionError("a live OCR request left the test")

    real = httpx.Client
    monkeypatch.setattr(
        ocr.httpx, "Client", lambda *a, **k: real(transport=httpx.MockTransport(boom))
    )
    doc = copy.deepcopy(SOURCES)
    doc["sources"][0]["excerpts"][0]["text"] = "nothing on any page"
    problems, notes = check_online(load_sources_from(doc), fetch=lambda u: SCANNED.read_bytes())
    assert reached == []
    assert notes == [NO_KEY_NOTE]
    assert problems == ["sources/src: excerpt not found online: e1"]


def test_a_cache_write_leaves_no_partial_file_and_an_oserror_is_a_note(api, tmp_path, monkeypatch):
    def broken_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(ocr.os, "replace", broken_replace)
    result = _ocr(api, tmp=tmp_path)
    assert result.texts[3]  # the text is still returned
    assert len(result.notes) == 1 and "cache" in result.notes[0]
    assert list(tmp_path.iterdir()) == []  # no half-written file left behind


def test_an_unwritable_scratch_dir_is_a_note_not_an_exception(api, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    result = _ocr(api, tmp=blocker / "sub")  # the cut's scratch directory is in the cache
    assert api.requests == [] and result.texts == {}
    assert len(result.notes) == 1 and "OCR failed" in result.notes[0]


def test_a_short_answer_is_not_cached(tmp_path):
    api = Api(
        lambda r: httpx.Response(200, json={"model": "m", "pages": [{"index": 0, "markdown": "a"}]})
    )
    result = _ocr(api, pages=[3, 5], tmp=tmp_path)
    assert any("1 pages answered for 2 sent" in n for n in result.notes)
    assert list(tmp_path.iterdir()) == []


def test_a_missing_pdfinfo_is_a_note_when_ocr_would_apply(monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None if name == "pdfinfo" else "/x")
    pdf = SCANNED.read_bytes()
    notes: list[str] = []
    ocr.empty_pages(pdf, notes)
    assert notes == []  # no key: OCR would not apply, so no note on every PDF
    monkeypatch.setenv("MISTRAL_API_KEY", KEY)
    ocr.empty_pages(pdf, notes)
    assert notes == [ocr.PDFINFO_NOTE]
    assert KEY not in notes[0]


def test_the_cap_is_for_the_whole_run_not_each_pdf(tmp_path, monkeypatch):
    # final review M1: two PDFs of 15 scanned pages each send 20 pages in all, not 30
    from velometer.content import check

    sent: list[list[int]] = []

    def cut(pdf, selected, work):
        sent.append(list(selected))
        return b"%PDF-1.4 stand-in"

    def handler(request):
        pages = [{"index": i, "markdown": f"t{i}"} for i in range(len(sent[-1]))]
        return httpx.Response(200, json={"model": "m", "pages": pages})

    monkeypatch.setattr(ocr, "_cut_pages", cut)
    monkeypatch.setattr(check, "empty_pages", lambda pdf, notes=None: list(range(1, 16)))
    doc = copy.deepcopy(SOURCES)
    second = copy.deepcopy(doc["sources"][0])
    second.update(id="src2", url="https://example.org/other")
    doc["sources"].append(second)
    bodies = {s["url"]: SCANNED.read_bytes() + s["id"].encode() for s in doc["sources"]}
    api = Api(handler)
    with api.client() as c:
        ocr_call = lambda pdf, pages, limit: ocr.ocr_pages(  # noqa: E731
            pdf, pages, limit, client=c, cache_dir=tmp_path, key=KEY
        )
        _problems, notes = check_online(load_sources_from(doc), fetch=bodies.get, ocr=ocr_call)
    assert sum(map(len, sent)) == ocr.MAX_OCR_PAGES == 20
    assert sent == [list(range(1, 16)), list(range(1, 6))]
    assert any("10 pages skipped" in n for n in notes), notes


def test_a_run_with_no_pages_left_sends_nothing(api, tmp_path):
    result = _ocr(api, tmp=tmp_path, limit=0)
    assert api.requests == [] and result.texts == {} and result.sent == 0
    assert result.skipped == [3] and any("skipped" in n for n in result.notes)


def test_the_cut_works_in_the_cache_dir_not_a_milestone_scratch_dir(api, tmp_path, monkeypatch):
    # final review M2: no scratch path of this machine in shipped code
    seen: list[Path] = []
    real = ocr._cut_pages

    def cut(pdf, selected, work):
        seen.append(work)
        return real(pdf, selected, work)

    monkeypatch.setattr(ocr, "_cut_pages", cut)
    _ocr(api, tmp=tmp_path)
    assert seen and seen[0].parent == tmp_path
    assert "scratch-m" not in Path(ocr.__file__).read_text(encoding="utf-8")


def test_any_http_error_is_a_note_with_its_type_only(tmp_path):
    # final review M3: an httpx error that is not a transport error is a note, never raised
    def handler(request):
        raise httpx.DecodingError(f"bad body for {KEY}")

    result = _ocr(Api(handler), tmp=tmp_path)
    assert result.notes == ["OCR failed: DecodingError"] and result.texts == {}


def test_the_empty_pages_take_one_pdftotext_run(monkeypatch):
    # final review M4: one pdftotext over the PDF, not one per page; the page numbers stay
    calls: list[str] = []
    real = ocr._poppler

    def counted(name, *args, **kw):
        calls.append(name)
        return real(name, *args, **kw)

    monkeypatch.setattr(ocr, "_poppler", counted)
    assert ocr.empty_pages(SCANNED.read_bytes()) == [3]
    assert calls.count("pdftotext") == 1
