"""Every ruling the code, tests and docs cite is recorded (M17 final review I1).

A citation reads "ruling <ID>" (or "Ruling", "rulings <ID>, <ID> and <ID>"). An ID of M17's own
shapes (`T3a`, `T9-i`, `T10-B1`, `X1`, `U1`, `2d-a`, `R35-CI`, `FINAL-1`, `M3-robots`, ...)
must be an entry of `docs/superpowers/rulings-m17.md`; a plain `R<n>` or `P<n>`, the shape M16
also used, an entry of that file or of `rulings-m16.md`. An entry is a list item opening with the
bold ID and a full stop (`- **T9-i.**`). The rulings files themselves and the older milestones'
specs and plans (`docs/superpowers/`) cite their own milestone's IDs and are not read.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULINGS = ROOT / "docs" / "superpowers"
SCANNED = ("docs/", "deploy/", "tools/", "src/", "tests/", ".github/")
ID = r"(?:[A-Z]+\d+[a-z]?(?:-[A-Za-z0-9]+)?|[A-Z]+-\d+|\d[a-z]-[a-z])"
CITATION = re.compile(rf"\b[Rr]ulings? ({ID}(?:(?:, | and | to ){ID})*)\b")
SHARED = re.compile(r"^[RP]\d+$")  # the shape M16's rulings also have
ENTRY = re.compile(rf"^\s*- \*\*({ID})\.\*\*", re.MULTILINE)


def defined(name: str) -> set[str]:
    return set(ENTRY.findall((RULINGS / name).read_text(encoding="utf-8")))


def cited_ids(text: str) -> set[str]:
    return {i for group in CITATION.findall(text) for i in re.findall(ID, group)}


def _tracked() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", *SCANNED], cwd=ROOT, capture_output=True, check=True
    ).stdout.decode()
    paths = [ROOT / p for p in out.split("\0") if p]
    return [p for p in paths if not p.is_relative_to(RULINGS) and p.is_file()]


def _citations() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in _tracked():
        if path == Path(__file__):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # a binary file
        for i in cited_ids(text):
            found.setdefault(i, set()).add(path.relative_to(ROOT).as_posix())
    return found


def test_every_cited_ruling_is_recorded():
    m17, m16 = defined("rulings-m17.md"), defined("rulings-m16.md")
    cited = _citations()
    assert {"T3a", "T9-i", "T9-j", "R35-CI"} <= set(cited)  # the scan finds the known ones
    missing = {
        i: sorted(where)
        for i, where in cited.items()
        if i not in m17 and not (SHARED.match(i) and i in m16)
    }
    assert not missing, missing


def test_the_named_m17_rulings_are_recorded():
    """The ledger's named rulings, each an entry of rulings-m17.md."""
    names = [
        "P1", "P2", "P3", "P4", "R1", "T1", "T3a", "T4a", "T5a", "T13a", "T13b", "T16a", "X1",
        "U1", "2d-a", "R35-CI", "T10-B1", "FINAL-1", "M3-robots",
        *(f"T9-{c}" for c in "abcdefghij"), *(f"T10-{c}" for c in "abcdefghi"),
    ]  # fmt: skip
    m17 = defined("rulings-m17.md")
    assert not [n for n in names if n not in m17]


def test_citation_reader_finds_lists_and_skips_dates():
    """Red-proof of the scan: lists of IDs are read, dates and bare numbers are no IDs."""
    text = (
        "(ruling T9-i) Ruling 2d-a; rulings R21, R24 and P3; ruling FINAL-1; ruling M3-robots;"
        " ruling 2026-10-07; ruling 2."
    )
    assert cited_ids(text) == {"T9-i", "2d-a", "R21", "R24", "P3", "FINAL-1", "M3-robots"}
    assert "Z9-q" not in defined("rulings-m17.md")
    assert cited_ids("see ruling Z9-q") == {"Z9-q"}  # an unrecorded ID is caught
