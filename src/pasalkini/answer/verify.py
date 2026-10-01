"""Check an answer's citations in code before anyone sees them.

A citation passes when:
- its source ID is one of the chunks the model was given, or a ruling named in the notes of one
  of them (it is then shown under that chunk's ID);
- the quote's words and numbers appear in that chunk's title or text, in order (case and
  punctuation do not count; a quote shortened with '…', or stitched after a colon, passes when
  each part appears, in order);
- unless the question is about history, the chunk applied on the question's date.
An answer that does not abstain must cite at least one source.

What this does not check: the answer's own sentences. A verified citation shows the source says
what is quoted, not that the answer drew the right conclusion from it.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from pasalkini.corpus import Chunk

MIN_QUOTE_CHARS = 12  # a shorter quote, or part of one, verifies nothing
# Where a quote may skip text: an ellipsis, or a colon ('… sebagai berikut: f. masa kerja 5 …'
# quotes a table's opening line and one of its rows).
GAP = re.compile(r"\s*(?:…|\.{3,}|:)\s*")
# A note inside a version's text starts with the ID of the ruling or clause it comes from.
NOTE_ID = re.compile(r"^\[([^\]\s]+)\]", re.MULTILINE)


class Citation(BaseModel):
    source_id: str = Field(description="ID sumber dari KONTEKS, persis, tanpa tanda kurung")
    quote: str = Field(
        description="kutipan persis dari teks sumber itu: satu kalimat atau frasa, paling "
        "banyak 30 kata"
    )


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
    """Lower-case words and numbers with single spaces between them. Punctuation, quotation
    marks, bracket style and line breaks do not count: models add a closing full stop, and
    legal texts end clauses with ';'."""
    return " ".join(re.findall(r"\w+", text.lower()))


def quote_in(quote: str, text: str) -> bool:
    """Every word and number of the quote appears in the text, in order and as whole words. A
    part shorter than MIN_QUOTE_CHARS is a marker ('(2) …'), not evidence: it is skipped, and a
    quote with no longer part fails."""
    parts = [_normalise(part) for part in GAP.split(quote)]
    parts = [part for part in parts if len(part) >= MIN_QUOTE_CHARS]
    if not parts:
        return False
    haystack, position = f" {_normalise(text)} ", 0
    for part in parts:
        found = haystack.find(f" {part} ", position)
        if found < 0:
            return False
        position = found + len(part) + 1
    return True


def clean_source_id(source_id: str) -> str:
    """Models sometimes keep the brackets the context shows around IDs: '[uu-13-2003/pasal-59]'."""
    return source_id.strip().strip("[]{}()<>").strip().lower()


def cites_note(chunk: Chunk, source_id: str) -> bool:
    """The chunk's notes name this ruling: '[mk-168-puu-xxi-2023/amar-7] …' for that ID or for
    'mk-168-puu-xxi-2023'."""
    return any(
        note == source_id or note.startswith(source_id + "/")
        for note in NOTE_ID.findall(chunk.text)
    )


def check_citation(
    citation: Citation, context: list[Chunk], as_of: date | None, history: bool
) -> tuple[str | None, str]:
    """(the problem with one citation or None, the source ID to show it under).

    Models cite the ruling that conditions an article by the ID in the article's notes. The
    ruling is real and the chunk shows it, so the citation counts when the quote is in that
    chunk, and it is shown under the chunk's own ID.
    """
    source_id = citation.source_id
    candidates = [c for c in context if c.source_id == source_id]
    if not candidates:
        candidates = [c for c in context if cites_note(c, source_id)]
    if not candidates:
        return f"[{source_id}] tidak ada di KONTEKS.", source_id
    # The title counts: for a status question the evidence is the validity it states.
    quoted = [c for c in candidates if quote_in(citation.quote, c.title + "\n" + c.text)]
    if not quoted:
        return f"[{source_id}] kutipan tidak ditemukan persis di teks sumbernya.", source_id
    if as_of is not None and not history:
        quoted = [c for c in quoted if not hasattr(c, "valid_on") or c.valid_on(as_of)]
        if not quoted:
            return f"[{source_id}] tidak berlaku pada {as_of.isoformat()}.", source_id
    return None, quoted[0].source_id


def verify(answer: Answer, context: list[Chunk], as_of: date | None, history: bool) -> Verification:
    result = Verification()
    if answer.abstain:
        return result
    if not answer.citations:
        result.problems.append("Jawaban tidak mencantumkan sumber.")
    for citation in answer.citations:
        cleaned = citation.model_copy(update={"source_id": clean_source_id(citation.source_id)})
        problem, shown_as = check_citation(cleaned, context, as_of, history)
        result.checked.append((cleaned.model_copy(update={"source_id": shown_as}), problem))
        if problem:
            result.problems.append(problem)
    return result
