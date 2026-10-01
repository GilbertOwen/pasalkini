"""Check an answer's citations in code before anyone sees them.

A citation passes when:
- its source ID is one of the chunks the model was given;
- the quote appears in that chunk's text (ignoring case, whitespace and quotation marks; a quote
  shortened with '…' passes when each part appears, in order);
- unless the question is about history, the chunk applied on the question's date.
An answer that does not abstain must cite at least one source.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from pasalkini.corpus import Chunk

MIN_QUOTE_CHARS = 12  # each part of a quote; shorter text verifies nothing
ELLIPSIS = re.compile(r"\s*(?:…|\.{3,})\s*")


class Citation(BaseModel):
    source_id: str = Field(description="ID sumber dari KONTEKS, persis, tanpa tanda kurung")
    quote: str = Field(description="kutipan persis dari teks sumber itu, satu kalimat atau frasa")


class Answer(BaseModel):
    answer: str = Field(description="jawaban singkat dalam bahasa Indonesia yang mudah dipahami")
    citations: list[Citation]
    confidence: Literal["tinggi", "sedang", "rendah"]
    caveats: list[str] = Field(
        default_factory=list, description="batasan atau hal yang perlu dicek"
    )
    referral: str | None = Field(default=None, description="ke mana sebaiknya bertanya jika perlu")
    abstain: bool = Field(default=False, description="true jika tidak dapat menjawab dari konteks")


@dataclass
class Verification:
    checked: list[tuple[Citation, str | None]] = field(default_factory=list)  # (citation, problem)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def valid(self) -> list[Citation]:
        return [citation for citation, problem in self.checked if problem is None]


def _normalise(text: str) -> str:
    text = re.sub(r"[\"'“”‘’]", "", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def quote_in(quote: str, text: str) -> bool:
    parts = [_normalise(part) for part in ELLIPSIS.split(quote)]
    parts = [part for part in parts if part]
    if not parts or any(len(part) < MIN_QUOTE_CHARS for part in parts):
        return False
    haystack, position = _normalise(text), 0
    for part in parts:
        found = haystack.find(part, position)
        if found < 0:
            return False
        position = found + len(part)
    return True


def clean_source_id(source_id: str) -> str:
    """Models sometimes keep the brackets the context shows around IDs: '[uu-13-2003/pasal-59]'."""
    return source_id.strip().strip("[]{}()<>").strip().lower()


def check_citation(
    citation: Citation, context: list[Chunk], as_of: date | None, history: bool
) -> str | None:
    """The problem with one citation, or None when it passes."""
    source_id = citation.source_id
    candidates = [c for c in context if c.source_id == source_id]
    if not candidates:
        return f"[{source_id}] tidak ada di KONTEKS."
    quoted = [c for c in candidates if quote_in(citation.quote, c.text)]
    if not quoted:
        return f"[{source_id}] kutipan tidak ditemukan persis di teks sumbernya."
    if as_of is not None and not history:
        if not any(not hasattr(c, "valid_on") or c.valid_on(as_of) for c in quoted):
            return f"[{source_id}] tidak berlaku pada {as_of.isoformat()}."
    return None


def verify(answer: Answer, context: list[Chunk], as_of: date | None, history: bool) -> Verification:
    result = Verification()
    if answer.abstain:
        return result
    if not answer.citations:
        result.problems.append("Jawaban tidak mencantumkan sumber.")
    for citation in answer.citations:
        cleaned = citation.model_copy(update={"source_id": clean_source_id(citation.source_id)})
        problem = check_citation(cleaned, context, as_of, history)
        result.checked.append((cleaned, problem))
        if problem:
            result.problems.append(problem)
    return result
