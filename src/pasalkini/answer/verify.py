"""Check an answer's citations in code before anyone sees them.

A citation passes when:
- its source ID is one of the chunks the model was given;
- the quote appears in that chunk's text (ignoring case and whitespace);
- unless the question is about history, the chunk applied on the question's date.
An answer that does not abstain must cite at least one source.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from pasalkini.corpus import Chunk

MIN_QUOTE_CHARS = 12


class Citation(BaseModel):
    source_id: str = Field(description="ID sumber dari KONTEKS, persis, tanpa tanda kurung")
    quote: str = Field(description="kutipan persis dari teks sumber itu, 1-2 kalimat")


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
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _normalise(text: str) -> str:
    text = text.lower().replace("…", " ").replace("...", " ")
    text = re.sub(r"[\"'“”‘’]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def quote_in(quote: str, text: str) -> bool:
    quote_n = _normalise(quote)
    return len(quote_n) >= MIN_QUOTE_CHARS and quote_n in _normalise(text)


def verify(answer: Answer, context: list[Chunk], as_of: date | None, history: bool) -> Verification:
    result = Verification()
    if answer.abstain:
        return result
    if not answer.citations:
        result.problems.append("Jawaban tidak mencantumkan sumber.")
    for citation in answer.citations:
        candidates = [c for c in context if c.source_id == citation.source_id]
        if not candidates:
            result.problems.append(f"[{citation.source_id}] tidak ada di KONTEKS.")
            continue
        if not any(quote_in(citation.quote, c.text) for c in candidates):
            result.problems.append(
                f"[{citation.source_id}] kutipan tidak ditemukan persis di teks sumbernya."
            )
            continue
        if as_of is not None and not history:
            valid = [c for c in candidates if not hasattr(c, "valid_on") or c.valid_on(as_of)]
            if not valid:
                result.problems.append(
                    f"[{citation.source_id}] tidak berlaku pada {as_of.isoformat()}."
                )
    return result
