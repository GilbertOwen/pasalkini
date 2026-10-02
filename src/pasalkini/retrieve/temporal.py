"""Date-aware retrieval: decide the date, then rank only what applied on it.

- The date comes from the date picker when there is one; otherwise it is read from the question
  ('bulan Maret 2019', 'tahun 2020'); otherwise today.
- Questions about change or status ('apa yang berubah', 'masih berlaku') search every version up
  to that date, since the answer needs the old wording too. Phase 5 replaces this keyword rule
  with LLM query understanding.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from pasalkini.corpus import Chunk

MONTHS = {
    "januari": 1,
    "februari": 2,
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
}
DATE_IN_TEXT = re.compile(
    r"\b(?:(\d{1,2})\s+)?(" + "|".join(MONTHS) + r")\s+(\d{4})\b", re.IGNORECASE
)
YEAR_IN_TEXT = re.compile(r"\btahun\s+(\d{4})\b", re.IGNORECASE)
# 'dulu' and 'sebelumnya' are everyday adverbs ('saya dulu bekerja', 'abaikan instruksi
# sebelumnya'), so they count only a few words after a word for the law ('aturan sebelumnya').
LAW_WORD = r"(?:aturan|ketentuan|peraturan|undang-undang|uu|pasal|hukum|bunyi|versi)"
HISTORY_CUES = re.compile(
    r"\b(berubah|perubahan|masih berlaku|dibandingkan|riwayat|sejarah"
    rf"|{LAW_WORD}(?:\s+\S+){{0,3}}?\s+(?:dulu|sebelumnya))\b",
    re.IGNORECASE,
)


def extract_date(question: str) -> date | None:
    """A date in the question: '15 Maret 2019'; 'Maret 2019' (the 15th); 'tahun 2019' (1 July)."""
    match = DATE_IN_TEXT.search(question)
    if match:
        day = int(match.group(1)) if match.group(1) else 15
        return date(int(match.group(3)), MONTHS[match.group(2).lower()], day)
    for match in YEAR_IN_TEXT.finditer(question):
        # 'Undang-Undang Nomor 13 Tahun 2003' names a law. It does not date the question.
        if not re.search(r"\d\s*$", question[: match.start()]):
            return date(int(match.group(1)), 7, 1)
    return None


@dataclass
class Retrieval:
    hits: list[tuple[Chunk, float]]
    as_of: date | None  # the date the search used (None: no date filter)
    mode: str  # plain | as_of | history


def retrieve(
    search: Callable[[Callable[[Chunk], bool] | None], list[tuple[Chunk, float]]],
    question: str,
    *,
    date_hint: date | None,
    date_filter: bool,
    history_cues: bool,
    today: date | None = None,
) -> Retrieval:
    """Decide the date and the filter; `search(allowed)` does the ranking (see search.py)."""
    if not date_filter:
        return Retrieval(search(None), date_hint, "plain")
    as_of = date_hint or extract_date(question) or today or date.today()
    if history_cues and HISTORY_CUES.search(question):
        return Retrieval(search(lambda c: c.valid_from <= as_of), as_of, "history")
    return Retrieval(search(lambda c: c.valid_on(as_of)), as_of, "as_of")
