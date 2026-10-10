"""Pydantic models for narratives, the explainer, organisation profiles and the external-source
registry."""

import re
from datetime import date
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

STORY_STEPS = ("all", "leaders", "tail", "growth", "jumps", "bezirke")
INTERNAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}
MAX_EXCERPT_WORDS = 60
# a BCP 47 language tag, as far as content needs one: "de", "pt-BR", "zh-Hant". It is what the
# page writes into `lang` attributes (a quote's language), so it is also what content may write
LANG_TAG = re.compile(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*")


class ContentError(Exception):
    """A content file is missing or invalid; the message names the file."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _external_url(v: str | None, what: str = "source url") -> str | None:
    """`v` unchanged when it is an external http(s) URL; ValueError naming `what` otherwise."""
    if v is None:
        return v
    u = urlparse(v)
    if u.scheme not in ("http", "https") or not u.hostname or u.hostname in INTERNAL_HOSTS:
        raise ValueError(f"{what} must be an external http(s) URL, not {v!r}")
    return v


class Excerpt(_Strict):
    id: str
    text: str
    gloss_en: str | None = None
    locator: str


class Source(_Strict):
    id: str
    publisher: str
    title: str
    url: str
    published: date | None = None
    accessed: date
    language: str
    kind: Literal["official", "parliament", "ngo", "index", "press", "research"]
    archive_url: str | None = None
    excerpts: list[Excerpt]

    @field_validator("language")
    @classmethod
    def _language_tag(cls, v: str) -> str:
        if not LANG_TAG.fullmatch(v):
            raise ValueError(f"language must be a BCP 47 language tag such as 'de', not {v!r}")
        return v

    @field_validator("url", "archive_url")
    @classmethod
    def _external(cls, v: str | None) -> str | None:
        return _external_url(v)

    @model_validator(mode="after")
    def _excerpts(self) -> "Source":
        ids = [e.id for e in self.excerpts]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate excerpt id in {self.id}")
        for e in self.excerpts:
            if len(e.text.split()) > MAX_EXCERPT_WORDS:
                raise ValueError(f"excerpt {self.id}/{e.id} has more than 60 words")
            if self.language != "en" and not e.gloss_en:
                raise ValueError(
                    f"excerpt {self.id}/{e.id} needs gloss_en (language {self.language})"
                )
        return self


class Quote(_Strict):
    excerpt: str  # "<source_id>/<excerpt_id>"
    after: int


class Fact(_Strict):
    id: str
    expr: str
    printed: str


class DataRef(_Strict):
    id: str
    label: str
    file: str | None = None
    locator: str | None = None
    route: str | None = None


class Section(_Strict):
    heading: str | None = None
    step: str | None = None
    role: Literal["story", "figures"] = "story"
    paragraphs: list[str]

    @field_validator("step")
    @classmethod
    def _known_step(cls, v: str | None) -> str | None:
        if v is not None and v not in STORY_STEPS:
            raise ValueError(f"unknown step {v!r}; expected one of {STORY_STEPS}")
        return v


class ExplainerSection(_Strict):
    dimension: str
    heading: str
    paragraphs: list[str]


def _unique(kind: str, ids: list[str]) -> None:
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {kind} id")


class Narrative(_Strict):
    city_id: str
    title: str
    dek: str
    sections: list[Section]
    quotes: list[Quote] = []
    facts: list[Fact] = []
    data_refs: list[DataRef] = []
    literals: list[str] = []

    @property
    def paragraphs(self) -> list[str]:
        return [p for s in self.sections for p in s.paragraphs]

    @model_validator(mode="after")
    def _consistent(self) -> "Narrative":
        n = len(self.paragraphs)
        for q in self.quotes:
            if not 0 <= q.after < n:
                raise ValueError(f"quote {q.excerpt}: after={q.after} must index one of {n}")
        _unique("fact", [f.id for f in self.facts])
        _unique("data_ref", [d.id for d in self.data_refs])
        return self


class Explainer(_Strict):
    title: str
    intro: list[str]
    sections: list[ExplainerSection]
    quotes: list[Quote] = []
    facts: list[Fact] = []
    data_refs: list[DataRef] = []
    literals: list[str] = []

    @model_validator(mode="after")
    def _consistent(self) -> "Explainer":
        _unique("fact", [f.id for f in self.facts])
        _unique("data_ref", [d.id for d in self.data_refs])
        return self


class OrgSection(_Strict):
    heading: str
    paragraphs: list[str]
    dimensions: dict[str, str] | None = None  # keys ⊆ differences.yaml dimension ids


class Organisation(_Strict):
    """`content/organisations/<id>.yaml`: a profile of a body behind our external figures."""

    id: str
    name: str
    kind: Literal["official", "ngo", "index", "research", "parliament", "agency"]
    url: str
    sections: list[OrgSection]
    quotes: list[Quote] = []
    facts: list[Fact] = []
    data_refs: list[DataRef] = []
    literals: list[str] = []

    @field_validator("url")
    @classmethod
    def _external(cls, v: str) -> str:
        _external_url(v, "organisation url")
        return v

    @property
    def prose(self) -> list[str]:
        out = [self.name]
        for sec in self.sections:
            out += [sec.heading, *sec.paragraphs, *(sec.dimensions or {}).values()]
        return out

    @model_validator(mode="after")
    def _consistent(self) -> "Organisation":
        n = sum(len(s.paragraphs) for s in self.sections)
        for q in self.quotes:
            if not 0 <= q.after < n:
                raise ValueError(f"quote {q.excerpt}: after={q.after} must index one of {n}")
        _unique("fact", [f.id for f in self.facts])
        _unique("data_ref", [d.id for d in self.data_refs])
        return self


class OrgMapping(_Strict):
    """One entry of `config/organisations.yaml`: the body behind a source (in one city or all)."""

    city: str  # a city id or "*"
    source: str
    organisation: str
