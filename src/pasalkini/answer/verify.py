"""Check an answer's citations in code before anyone sees them.

The model's quote is used to find the passage; the user is shown the source's own words.

A citation passes when its quote is found in a chunk the model was given:
- word for word, or nearly: at least MIN_COVERAGE of the quote's words (80%), in order and
  close together, including every number and number word. Small models tidy what they copy: they
  resolve a cross-reference ('sebagaimana dimaksud dalam ayat (1)' becomes 'atas kemauan
  sendiri'), drop list markers, or repair a word the PDF broke ('be-rikut'). A changed number
  is never tolerated;
- a quote shortened with '…', or stitched after a colon, passes when each part is found, in
  order;
- in the chunk it names, or a chunk whose notes name that ruling, or failing that any other
  chunk in the context (a right quote under a wrong ID is shown under the right one);
- unless the question is about history, the chunk applied on the question's date.
An answer that does not abstain must cite at least one source.

What this does not check: the answer's own sentences. A verified citation shows what the source
says, not that the answer drew the right conclusion from it.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from pasalkini.corpus import Chunk

MIN_QUOTE_CHARS = 12  # a shorter quote, or part of one, verifies nothing
MIN_COVERAGE = 0.8  # share of a quote's words that must be found for a near match
MIN_PART_COVERAGE = 0.6  # ... and of each part of a quote split by '…' or ':'
MIN_NEAR_WORDS = 5  # shorter parts must match word for word
MIN_RUN = 3  # a near match needs this many words in a row
# Where a quote may skip text: an ellipsis, or a colon ('… sebagai berikut: f. masa kerja 5 …'
# quotes a table's opening line and one of its rows).
GAP = re.compile(r"\s*(?:…|\.{3,}|:)\s*")
WORD = re.compile(r"\w+")
# A note inside a version's text starts with the ID of the ruling or clause it comes from.
NOTE_ID = re.compile(r"^\[([^\]\s]+)\]", re.MULTILINE)
NUMBER_WORDS = frozenset(
    "nol satu dua tiga empat lima enam tujuh delapan sembilan sepuluh sebelas seratus seribu "
    "belas puluh ratus ribu juta setengah koma".split()
)


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
    # (citation, problem). A citation that passed carries the chunk's ID and the source's words.
    checked: list[tuple[Citation, str | None]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def valid(self) -> list[Citation]:
        return [citation for citation, problem in self.checked if problem is None]


def _fold(token: str) -> str:
    """OCR reads 1 as I or l and 0 as O ('istirahat mingguan I (satu) hari', 'Pasal 8O'). Folding
    them the same way in the quote and in the text lets a model that read the number correctly
    still match."""
    if token in ("i", "l"):
        return "1"
    if token == "o":
        return "0"
    if any(ch.isdigit() for ch in token):
        return token.replace("o", "0").replace("l", "1").replace("i", "1")
    return token


def _words(text: str) -> list[tuple[str, int, int]]:
    """Lower-case words and numbers with their positions. Punctuation, quotation marks and line
    breaks do not count: models add a closing full stop, and legal texts end clauses with ';'."""
    return [(_fold(m.group().lower()), m.start(), m.end()) for m in WORD.finditer(text)]


def _is_number(token: str) -> bool:
    return token in NUMBER_WORDS or any(ch.isdigit() for ch in token)


def _find(part: list[str], words: list[str], begin: int) -> tuple[int, int, int] | None:
    """Where the part's words are in `words` from `begin` on: (first, one past last, how many
    of the part's words were found)."""
    n = len(part)
    for i in range(begin, len(words) - n + 1):
        if words[i : i + n] == part:
            return i, i + n, n
    if n < MIN_NEAR_WORDS:
        return None
    matcher = SequenceMatcher(None, part, words[begin:], autojunk=False)
    blocks = [b for b in matcher.get_matching_blocks() if b.size]
    # The words must lie close together: within a stretch of the source about twice the part's
    # length. Matches outside it (a stray 'yang' elsewhere in the article) are dropped from the
    # ends, smallest first.
    while blocks and blocks[-1].b + blocks[-1].size - blocks[0].b > 2 * n + 12:
        blocks.pop(0 if blocks[0].size <= blocks[-1].size else -1)
    if not blocks or max(b.size for b in blocks) < MIN_RUN:
        return None
    matched = {i for b in blocks for i in range(b.a, b.a + b.size)}
    numbers = {i for i, token in enumerate(part) if _is_number(token)}
    if len(matched) < MIN_PART_COVERAGE * n or not numbers <= matched:
        return None
    return begin + blocks[0].b, begin + blocks[-1].b + blocks[-1].size, len(matched)


def locate(quote: str, text: str) -> str | None:
    """The source's own words for the quote, or None when the quote is not there."""
    source = _words(text)
    words = [word for word, _, _ in source]
    begin, spans, total, found = 0, [], 0, 0
    for piece in GAP.split(quote):
        part = [word for word, _, _ in _words(piece)]
        if len(" ".join(part)) < MIN_QUOTE_CHARS:
            continue  # a marker such as '(2) …', not evidence
        span = _find(part, words, begin)
        if span is None:
            return None
        first, last, matched = span
        if spans and first - spans[-1][1] <= 2:  # only a list marker in between
            spans[-1] = (spans[-1][0], last)
        else:
            spans.append((first, last))
        begin, total, found = last, total + len(part), found + matched
    if not spans or found < MIN_COVERAGE * total:
        return None
    shown = [text[source[first][1] : source[last - 1][2]] for first, last in spans]
    return " … ".join(" ".join(piece.split()) for piece in shown)


def quote_in(quote: str, text: str) -> bool:
    return locate(quote, text) is not None


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
) -> tuple[Citation, str | None]:
    """(the citation to show, None) when it passes: the chunk's ID and the source's words.
    Otherwise (the citation as given, the problem)."""
    source_id = citation.source_id
    named = [c for c in context if c.source_id == source_id]
    # Models cite the ruling that conditions an article by the ID in the article's notes.
    named = named or [c for c in context if cites_note(c, source_id)]
    stale = False
    # The chunk the model named first; a right quote under a wrong ID is still a right quote.
    for chunk in named + [c for c in context if c not in named]:
        # The title counts: for a status question the evidence is the validity it states.
        shown = locate(citation.quote, chunk.title + "\n" + chunk.text)
        if shown is None:
            continue
        applies = history or as_of is None or not hasattr(chunk, "valid_on")
        if applies or chunk.valid_on(as_of):
            return Citation(source_id=chunk.source_id, quote=shown), None
        stale = True
    if stale:
        return citation, f"[{source_id}] tidak berlaku pada {as_of.isoformat()}."
    if not named:
        return citation, f"[{source_id}] tidak ada di KONTEKS."
    return citation, f"[{source_id}] kutipan tidak ditemukan di teks sumbernya."


def verify(answer: Answer, context: list[Chunk], as_of: date | None, history: bool) -> Verification:
    result = Verification()
    if answer.abstain:
        return result
    if not answer.citations:
        result.problems.append("Jawaban tidak mencantumkan sumber.")
    for citation in answer.citations:
        cleaned = citation.model_copy(update={"source_id": clean_source_id(citation.source_id)})
        shown, problem = check_citation(cleaned, context, as_of, history)
        result.checked.append((shown, problem))
        if problem:
            result.problems.append(problem)
    return result
