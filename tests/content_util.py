"""The synthetic content tree of the content-check tests, and `fake_translate`, which writes a
stamped German twin of any English content file (no shipped prose involved)."""

import re
from pathlib import Path

import yaml

from velometer import i18n
from velometer.content.check import _NUMBER_TOKEN, NOT_STATED, NOT_STATED_DE
from velometer.content.facts import FactError, evaluate, parse_printed
from velometer.content.models import STORY_STEPS

EXPR = "series.berlin.lau.current.ab_km"

SOURCES = {
    "sources": [
        {
            "id": "src",
            "publisher": "Senat",
            "title": "Radverkehr",
            "url": "https://example.org/radverkehr",
            "accessed": "2026-10-01",
            "language": "de",
            "kind": "official",
            "excerpts": [
                {
                    "id": "e1",
                    "text": "Das Netz ist 78,2 km lang.",
                    "gloss_en": "The network is 78.2 km long.",
                    "locator": "p. 3",
                }
            ],
        }
    ]
}


def _write(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")


def _berlin(value: float) -> dict:
    return {
        "city_id": "berlin",
        "title": "Berlin",
        "dek": "A dek.",
        "sections": [
            {"heading": "Story", "paragraphs": [f"Berlin has {value:.1f} km [#r1] [@src]."]},
            {"role": "figures", "paragraphs": ["Figures."]},
        ],
        "quotes": [{"excerpt": "src/e1", "after": 0}],
        "facts": [{"id": "ab", "expr": EXPR, "printed": f"{value:.1f}"}],
        "data_refs": [{"id": "r1", "label": "Report", "route": "/"}],
        "literals": ["5 m"],
    }


def _combined() -> dict:
    return {
        "city_id": "combined",
        "title": "All",
        "dek": "Dek.",
        "sections": [{"step": s, "paragraphs": [f"Step {s}."]} for s in STORY_STEPS],
    }


def build_tree(fixture_db, tmp_path):
    """(content dir, ReportData, docs dir): berlin, paris and combined narratives, an explainer
    and a one-source registry, valid against the report fixture. The fixture config's
    differences.yaml is removed: these trees own their dimension list."""
    _db, _cfg, _conn, data = fixture_db
    value = evaluate(EXPR, data, tmp_path)
    root = tmp_path / "content"
    _write(root / "sources" / "all.yaml", SOURCES)
    _write(root / "narratives" / "berlin.yaml", _berlin(value))
    _write(root / "narratives" / "paris.yaml", {**_berlin(value), "city_id": "paris"})
    _write(root / "narratives" / "combined.yaml", _combined())
    _write(root / "explainer.yaml", {"title": "Explainer", "intro": ["Intro."], "sections": []})
    (_cfg / "differences.yaml").unlink(missing_ok=True)
    return root, data, tmp_path


# markers, code spans and quotations keep their bytes in a translation
_KEPT = re.compile(
    r"\[[@#][^\]]*\]|`[^`]*`|<q\b[^>]*>.*?</q>|<blockquote\b[^>]*>.*?</blockquote>", re.S
)


def _german_number(raw: str) -> str:
    """An English number token as the German edition prints it, at its printed precision."""
    squeezed = re.sub(r"[   ]", "", raw)
    try:
        value, decimals = parse_printed(squeezed)
    except FactError:
        return raw
    grouped = "," in squeezed or squeezed != raw
    out = i18n.fmt(abs(value), f"{',' if grouped else ''}.{decimals}f", "de")
    sign = "+" if raw.startswith("+") else i18n.MINUS if raw[:1] in "−-" else ""
    return f"{sign}{out}{i18n.NNBSP}%" if raw.endswith("%") else f"{sign}{out}"


def _numbers_de(text: str) -> str:
    def numbers(part: str) -> str:
        def one(m: re.Match) -> str:
            raw = m.group(0)
            core = raw.rstrip(",")
            return _german_number(core) + raw[len(core) :]

        return _NUMBER_TOKEN.sub(one, part)

    out, last = [], 0
    for m in _KEPT.finditer(text):
        out += [numbers(text[last : m.start()]), m.group(0)]
        last = m.end()
    return "".join([*out, numbers(text[last:])])


def german_text(text: str) -> str:
    """The fake translation of one English string."""
    if " ".join(text.split()) == NOT_STATED:
        return NOT_STATED_DE
    return "Übersetzt: " + _numbers_de(text)


def fake_translate(en_file: Path, de_file: Path, drop: frozenset[str] = frozenset()) -> None:
    """Write a stamped German twin of `en_file`: every translatable string is "Übersetzt: " and
    the English with its numbers in German format (markers and quotations byte for byte), each
    literal translated the same way, and the `drop` walk paths left out (a list item becomes
    null, so the other items keep their places)."""
    from velometer.content import translate as tr

    en = tr.load_english(en_file)
    texts = {path: german_text(text) for path, text in tr.walk(en) if path not in drop}
    doc = tr.skeleton(en, texts, [_numbers_de(lit) for lit in en.literals])
    de_file.parent.mkdir(parents=True, exist_ok=True)
    tr.dump(de_file, doc)
    tr.stamp(de_file, en)
