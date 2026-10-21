"""Press-law candidate sentences (M16 Task 3): every reader-facing sentence, in both editions,
that names a person, party, administration or organisation, or states a cause or a judgement
about one (spec §4.1 item 3, §4.9 item 8).

    uv run python tools/press_review.py --out FILE [PATH ...]

Without PATHs it reads `default_paths()`: the English and German content files (not
`content/sources/`, whose excerpts are verbatim, attributed quotations), the UI catalogues, the
flagged-year explanations, `config/limitations.yaml` and the config directory itself, whose
reader prose is what `velometer.config.reader_prose` lists. A YAML file is walked string by
string (ids, expressions, stamps, URLs, `facts`, `data_refs`, `literals` and `quotes` skipped);
a `.md` file is read as `### key` entries.

The list is a net, not a verdict: a reader cuts it down and judges each kept sentence in
`docs/review/m16-press.md`. Names come from data where the repo has them: the organisations of
`config/organisations.yaml` (named in `content/organisations/`) and the source publishers of
`content/sources/`. Generic offices, parties and the reviewed `PERSONS` are lists here.

A sentence is a candidate when it names an actor, when it uses an actor-implying verb
(`ACTOR_VERBS`: "rolled back", "zurückgebaut", "underspent" …), or when it states a cause or a
judgement in a paragraph that names an actor.
"""

import argparse
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REASONS = (
    "names-person",
    "names-party",
    "names-administration",
    "names-organisation",
    "causal-claim",
    "judgement",
)

# Named individuals in reader prose (reviewed 2026-10-21: none; the content names offices, not
# office holders). A title followed by a capitalised name is caught by PERSON_TITLE as well.
PERSONS: tuple[str, ...] = ()
PERSON_TITLE = re.compile(
    r"\b(?:Mayor|Senator|Minister|Councillor|Dr\.|Prof\.|Bürgermeister(?:in)?|Senatorin|"
    r"Ministerin|Stadträtin|Stadtrat)\s+[A-ZÄÖÜ][\w-]+"
)
# an office held by one identifiable person names that person, even without the name
OFFICE_HOLDER = re.compile(
    r"\b(?:[Cc]ycling commissioner|\w*[Rr]adverkehrsbeauftragte[rn]?|\w*[Ff]ahrradbeauftragte[rn]?|"
    r"[Gg]overning [Mm]ayor|Regierende[nr]? Bürgermeister(?:in)?)\b"
)
PARTIES = re.compile(
    r"\b(?:CDU|CSU|SPD|FDP|AfD|BSW|Bündnis 90|Die Grünen|Grünen|Greens?|Die Linke|Linken?|"
    r"ÖVP|SPÖ|NEOS|FPÖ|PiS|Fidesz|Volt|Parti socialiste|Les Républicains|PSOE|Partido Popular|"
    r"Vox|Podemos|GroenLinks|VVD|D66|Moderaterna|Socialdemokraterna|Høyre|Arbeiderpartiet|"
    r"coalition|Koalition|party|Partei(?:en)?|red-green|rot-grün\w*|green-red|grün-rot\w*)\b"
)
# offices and bodies by their generic name (a profiled or publishing body is found by its own)
ADMINISTRATION = re.compile(
    r"\b(?:Senate(?:'s)?|Senat(?:s|es)?|\w*[Vv]erwaltung(?:en)?|[Aa]dministrations?|"
    r"[Cc]ity (?:council|hall|government)|[Cc]ouncil|Bezirksämter|Bezirksamt\w*|Magistrat\w*|"
    r"[Mm]inistr(?:y|ies)|Ministeri\w+|[Gg]overnments?|\w*[Rr]egierung\w*|[Mm]ayors?|"
    r"\w*[Bb]ürgermeister\w*|[Aa]uthorit(?:y|ies)|\w*[Bb]ehörde\w*|[Pp]arliament\w*|"
    r"Parlament\w*|Abgeordnetenhaus\w*|[Cc]ommittee|\w*[Aa]usschuss\w*|[Aa]genc(?:y|ies)|"
    r"[Dd]epartments?|City of [A-Z]\w+)\b"
)
ORGANISATION = re.compile(r"\b(?:NGOs?|Verein\w*|Verband|Verbände\w*|[Aa]ssociation)\b")
# verbs that say an actor did something to the network or the money: always a candidate
ACTOR_VERBS = re.compile(
    r"\b(?:roll(?:ed|s)? back|rollbacks?|underspen\w*|unspent|scrapp\w*|cancell?ed|"
    r"abandon\w*|fell short|failed to|stop|stops|stopped|stopping|halt|halts|halted|paus\w*|"
    r"zurückgebaut|Rückbau\w*|gestrichen|stopp\w*|gestoppt|gekürzt|"
    r"Kürzung\w*|nicht abgerufen|aufgegeben|verfehlt\w*)\b"
)
CAUSAL = re.compile(
    r"\b(?:because|due to|owing to|caus(?:e|ed|es|ing)|led to|leads? to|result(?:ed|s)? "
    r"(?:in|from)|as a result|thanks to|driven by|so that|weil|wegen|aufgrund|auf Grund|"
    r"infolge|führ(?:t|te|ten) zu|verursach\w*|Ursache\w*|Folge|deshalb|daher|darum|"
    r"zurückzuführen|removed|remov(?:al|es)|cut|cuts|delay(?:ed|s)?|blocked|"
    r"entfernt|verzögert\w*|blockiert\w*)\b",
)
JUDGEMENT = re.compile(
    r"\b(?:(?:not |un|ir)?reproducib\w*|wrong\w*|incorrect\w*|mislead\w*|overstat\w*|"
    r"understat\w*|inflat\w*|exaggerat\w*|inaccura\w*|(?:un)?reliab\w*|flaw\w*|bias\w*|"
    r"errors?|mistak\w*|suspect|doubt\w*|questionab\w*|credib\w*|fail\w*|success\w*|"
    r"ambitio\w*|unrealistic|poor\w*|best|worst|better|worse|good|bad|lag\w*|leaders?|"
    r"leading|behind|ahead|contest\w*|disput\w*|disagree\w*|contradict\w*|inconsisten\w*|"
    r"supports?|unclear|opaque|claims?|claimed|(?:nicht )?reproduzierbar\w*|"
    r"nachvollziehbar\w*|nachprüfbar\w*|falsch\w*|fehlerhaft\w*|irreführend\w*|überhöht\w*|"
    r"übertrieben\w*|ungenau\w*|(?:un)?zuverlässig\w*|verzerrt\w*|Fehler\w*|verdächtig\w*|"
    r"zweifelhaft\w*|Zweifel\w*|fragwürdig\w*|glaubwürdig\w*|scheiter\w*|Erfolg\w*|"
    r"erfolgreich\w*|ehrgeizig\w*|unrealistisch\w*|schlecht\w*|beste[nmrs]?|besser\w*|gut|"
    r"gute[nmrs]?|Vorreiter\w*|hinterher|rückständig\w*|bestreit\w*|bestritten|"
    r"widersprech\w*|widersprüchlich\w*|Widerspruch|stützt|unklar\w*|intransparent\w*|"
    r"behaupt\w*|lediglich|merely|(?:below|short of|missed|behind) (?:\w+ ){0,3}targets?|"
    r"unter (?:\w+ ){0,3}Ziel\w*|Ziel\w* (?:\w+ ){0,2}verfehlt)\b"
)

# YAML keys that are never reader prose, and subtrees that are data, not prose
SKIP_KEYS = {
    "id", "city_id", "src", "url", "expr", "printed", "file", "locator", "route", "accessed",
    "kind", "lang", "language", "excerpt", "after", "dimension", "role", "step", "name",
    "source", "organisation", "city", "metric", "preset", "scope",
}  # fmt: skip
SKIP_TREES = {"facts", "data_refs", "literals", "quotes"}
# org kinds of content/organisations/ that are public bodies
PUBLIC_KINDS = {"official", "parliament", "agency"}
# publisher words that mark a public body
PUBLIC_WORDS = re.compile(
    r"Ville|Stadt|Kommune|Gemeente|Ayuntamiento|Ajuntament|Senatsverwaltung|Urząd|Zarząd|"
    r"Magistrat|stad|Mestna občina|Métropole|Abgeordnetenhaus|Commission|Statens|Diputació|"
    r"Rekenkamer|Chambre|Agencia|Statistiska|Insee|Technická správa|kommun|Kommune|Senat|"
    r"Mobilitätsagentur|infraVelo|Eurostat|INE\b|ZDM|ZTP|TSK"
)
# names too generic or not an actor in the prose (OpenStreetMap is the data, not a claimant)
NOT_NAMES = {"OpenStreetMap", "OpenStreetMap Wiki", "Zenodo", "GitHub", "GISRUK 2026"}
# reviewed aliases of profiled organisations (their content/organisations name is matched too)
ALIASES = {
    "infravelo": ("infraVelo",),
    "senmvku": ("SenMVKU", "Senate Department for Mobility"),
    "ecf": ("ECF", "QECIO"),
    "copenhagen_kommune": ("City of Copenhagen", "Københavns Kommune"),
    "bikenetkit": ("BikeNetKit",),
}
_SUFFIX = re.compile(r"\s+(?:Campaign|e\.V\.|GmbH|a\.s\.)$")


@dataclass(frozen=True)
class Candidate:
    file: str
    key: str
    lang: str
    sentence: str
    reasons: tuple[str, ...]


# --- names ---------------------------------------------------------------------------------


def _variants(name: str) -> set[str]:
    """A body's name, without its parenthesis, the abbreviation in it and a legal suffix."""
    out = {name}
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", name)
    if m:
        base, inner = m.group(1).strip(), m.group(2).strip()
        out.add(base)
        for part in re.split(r"[;,]\s*", inner):
            if part and len(part.split()) <= 3:
                out.add(part)
    for v in list(out):
        out.add(_SUFFIX.sub("", v))
    for v in list(out):  # "Ville de Paris, Paris Data" -> "Ville de Paris"
        out.add(re.split(r",\s|\s–\s", v)[0].strip())
    return {v for v in out if len(v) >= 3 and v not in NOT_NAMES}


@cache
def load_names(root: Path = ROOT) -> dict[str, str]:
    """name -> `names-administration` or `names-organisation`: the bodies of
    config/organisations.yaml (by their content/organisations name and kind) and the source
    publishers of content/sources/."""
    names: dict[str, str] = {}
    entries = yaml.safe_load((root / "config" / "organisations.yaml").read_text("utf-8")) or []
    for org_id in sorted({e["organisation"] for e in entries} | set(ALIASES)):
        path = root / "content" / "organisations" / f"{org_id}.yaml"
        if not path.is_file():
            continue
        org = yaml.safe_load(path.read_text(encoding="utf-8"))
        reason = "names-administration" if org.get("kind") in PUBLIC_KINDS else "names-organisation"
        for v in _variants(org["name"]) | set(ALIASES.get(org_id, ())):
            names[v] = reason
    for path in sorted((root / "content" / "sources").glob("*.yaml")):
        for s in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("sources", []):
            for field in ("publisher", "publisher_de"):
                if not s.get(field):
                    continue
                for v in _variants(s[field]):
                    public = PUBLIC_WORDS.search(v)
                    names.setdefault(v, "names-administration" if public else "names-organisation")
    return names


@cache
def _names_pattern(root: Path) -> list[tuple[re.Pattern, str]]:
    names = load_names(root)
    return [
        (re.compile(rf"(?<!\w){re.escape(n)}(?!\w)"), r)
        for n, r in sorted(names.items(), key=lambda x: -len(x[0]))
    ]


# --- text ----------------------------------------------------------------------------------

_MARKUP = re.compile(r"\[[@#][^\]]*\]|<[^>]+>|\*\*|`")
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ„\"(\d])")
_ABBREV = re.compile(
    r"(?:(?:^|[\s(])(?:z|u|o|d|s|v|p|pp|S|bzw|vgl|Nr|ca|St|Dr|Prof|vs|etc|Abs|Ä|B|h|Jan|Feb|Mar|"
    r"Apr|Jun|Jul|Aug|Sep|Sept|Oct|Okt|Nov|Dec|Dez)\.|"
    r"\b[eE]\.g\.|\b[iI]\.e\.|(?:^|\s)[A-Z]\.)$"
)
_ORDINAL = re.compile(r"(?:^|[\s(])\d{1,2}\.$")
_MONTH = re.compile(
    r"(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\b"
)


def clean(text: str) -> str:
    """Prose without citation marks, HTML tags, emphasis and code ticks, on one line."""
    return re.sub(r"\s+([,.;:])", r"\1", re.sub(r"\s+", " ", _MARKUP.sub("", text))).strip()


def split_sentences(text: str) -> list[str]:
    """The sentences of a paragraph; no break after an abbreviation, an initial or a German
    ordinal ("am 2. Oktober")."""
    out: list[str] = []
    for piece in _SPLIT.split(text.strip()):
        if out and (_ABBREV.search(out[-1]) or (_ORDINAL.search(out[-1]) and _MONTH.match(piece))):
            out[-1] = f"{out[-1]} {piece}"
        else:
            out.append(piece)
    return [s for s in out if s]


def _words(sentence: str) -> str:
    return re.sub(r"\S+=\S+", "", sentence)


def reasons(sentence: str, persons=PERSONS, root: Path = ROOT) -> tuple[str, ...]:
    """The REASONS a sentence gives; OSM tags (`railway=abandoned`) are not words."""
    sentence = _words(sentence)
    found = set()
    if (
        PERSON_TITLE.search(sentence)
        or OFFICE_HOLDER.search(sentence)
        or any(re.search(rf"(?<!\w){re.escape(p)}(?!\w)", sentence) for p in persons)
    ):
        found.add("names-person")
    if PARTIES.search(sentence):
        found.add("names-party")
    if ADMINISTRATION.search(sentence):
        found.add("names-administration")
    if ORGANISATION.search(sentence):
        found.add("names-organisation")
    for pat, reason in _names_pattern(root):
        if pat.search(sentence):
            found.add(reason)
    if CAUSAL.search(sentence) or ACTOR_VERBS.search(sentence):
        found.add("causal-claim")
    if JUDGEMENT.search(sentence):
        found.add("judgement")
    return tuple(r for r in REASONS if r in found)


# --- files ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Unit:
    """One paragraph of reader prose."""

    file: str
    key: str
    lang: str
    text: str


def _rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _file_lang(path: Path) -> str:
    p = Path(path)
    return (
        "de"
        if "de" in p.parent.parts[-1:] or p.stem == "de" or p.suffixes[-2:-1] == [".de"]
        else "en"
    )


def _key_lang(key: str, default: str) -> str:
    """The language a key names (`de`, `note_de`, `paragraphs_de.0`), the nearest segment first."""
    for seg in reversed(key.split(".")):
        if seg == "de" or seg.endswith("_de"):
            return "de"
        if seg == "en" or seg.endswith("_en"):
            return "en"
    return default


def _walk(node, path: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(node, dict):
        for k, v in node.items():
            k = str(k)
            if k in SKIP_KEYS or k in SKIP_TREES:
                continue
            yield from _walk(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}.{i}" if path else str(i))
    elif isinstance(node, str):
        yield path, node


def _yaml_units(path: Path) -> list[Unit]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    lang = _file_lang(path)
    return [
        Unit(_rel(path), key.removesuffix(".text"), _key_lang(key, lang), text)
        for key, text in _walk(data)
    ]


def _md_units(path: Path) -> list[Unit]:
    """`### key` entries of an explanations file, one unit per paragraph."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    out = []
    for m in re.finditer(r"^### (\S+)\s*\n(.*?)(?=^#{1,3} |\Z)", text, re.M | re.S):
        for para in re.split(r"\n\s*\n", m.group(2).strip()):
            if para.strip():
                out.append(Unit(_rel(path), m.group(1), _file_lang(path), para))
    return out


_CONFIG_FILES = {"figures.csv": "external/figures.csv", "plans.yaml": "plans/plans.yaml"}


def _config_units(config_dir: Path) -> list[Unit]:
    """The config's reader prose (`velometer.config.reader_prose`), English and German."""
    from velometer.config import reader_prose

    out = []
    for where, en, de in reader_prose(config_dir):
        name, _, key = where.partition(" ")
        file = _rel(Path(config_dir) / _CONFIG_FILES.get(name, name))
        out.append(Unit(file, key, "en", en))
        if de:
            out.append(Unit(file, key, "de", de))
    return out


def units(path: Path) -> list[Unit]:
    path = Path(path)
    if path.is_dir():
        return _config_units(path)
    if path.suffix == ".md":
        return _md_units(path)
    return _yaml_units(path)


def twin(unit_or_candidate) -> tuple[str, str]:
    """The (file, key) an English unit and its German twin share."""
    file = re.sub(r"/de/", "/", unit_or_candidate.file)
    file = re.sub(r"(?:^|/)de\.yaml$", lambda m: m.group(0).replace("de.yaml", "en.yaml"), file)
    file = file.replace(".de.md", ".md")
    key = re.sub(r"(?:_de|_en)(?=\.|$)", "", unit_or_candidate.key)
    key = re.sub(r"\.(?:de|en)$", "", key)
    return file, key


def candidates(paths: list[Path], persons=PERSONS, root: Path = ROOT) -> list[Candidate]:
    """The candidate sentences of the files (and config dirs), English and German twins
    adjacent (English first), in file and key order."""
    found: list[tuple[tuple, Candidate]] = []
    order: dict[tuple[str, str], int] = {}
    for path in paths:
        for u in units(path):
            sentences = [(s, reasons(s, persons, root)) for s in split_sentences(clean(u.text))]
            actor = any(r.startswith("names-") for _, rs in sentences for r in rs)
            for i, (s, rs) in enumerate(sentences):
                named = any(r.startswith("names-") for r in rs)
                if not (named or ACTOR_VERBS.search(_words(s)) or (rs and actor)):
                    continue
                t = twin(u)
                if u.lang == "en" or t not in order:
                    order.setdefault(t, len(order))
                found.append(((t, u.lang != "en", i), Candidate(u.file, u.key, u.lang, s, rs)))
    found.sort(key=lambda x: (order[x[0][0]], x[0][1], x[0][2]))
    return [c for _, c in found]


def default_paths(root: Path = ROOT) -> list[Path]:
    content = root / "content"
    paths = [
        p for p in sorted(content.rglob("*.yaml")) if "sources" not in p.relative_to(content).parts
    ]
    report = root / "docs" / "review" / "m3_timeseries.md"
    paths += [report, report.with_name("m3_timeseries.de.md")]
    paths += [root / "config" / "limitations.yaml", root / "config"]
    return paths


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def table(cands: list[Candidate]) -> str:
    lines = [
        "| # | File | Key | Lang | Sentence | Reasons | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for n, c in enumerate(cands, 1):
        lines.append(
            f"| {n} | {c.file} | {_cell(c.key)} | {c.lang} | {_cell(c.sentence)} | "
            f"{', '.join(c.reasons)} | open |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("paths", nargs="*", type=Path)
    a = ap.parse_args(argv)
    cands = candidates(a.paths or default_paths())
    by_reason = {r: sum(r in c.reasons for c in cands) for r in REASONS}
    head = (
        f"# Press-law candidates (raw)\n\n{len(cands)} candidate sentences "
        f"({sum(c.lang == 'en' for c in cands)} en, {sum(c.lang == 'de' for c in cands)} de). "
        + ", ".join(f"{r}: {n}" for r, n in by_reason.items())
        + ".\n\n"
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(head + table(cands), encoding="utf-8")
    print(f"{len(cands)} candidates -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
