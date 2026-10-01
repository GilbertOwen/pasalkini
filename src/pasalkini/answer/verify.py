"""Check in code what the model selects and what it writes, before anyone sees it.

The answer is made in two model calls, and each is checked.

1. The model picks quotes from the context. A quote is used to find the passage; the user is
   shown the source's own words. A quote passes when it is found in a chunk the model was given:
   - word for word, or nearly: at least MIN_COVERAGE of the quote's words (80%), in order and
     close together, including every number and number word. Small models tidy what they copy:
     they resolve a cross-reference ('sebagaimana dimaksud dalam ayat (1)' becomes 'atas kemauan
     sendiri'), drop list markers, or repair a word the PDF broke ('be-rikut'). A changed number
     is never tolerated;
   - a quote shortened with '…', or stitched after a colon, passes when each part is found, in
     order;
   - in the chunk it names, or a chunk whose notes name that ruling, or failing that any other
     chunk in the context (a right quote under a wrong ID is shown under the right one);
   - unless the question is about history, the chunk applied on the question's date.
2. The model answers from those passages alone: the quoted lines with what a reader needs beside
   them (expand). Its sentences are then checked for what code can check: every number and every
   article it mentions must be in what it was given (ungrounded).

What this does not check: whether the answer draws the right conclusion from its passages.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from pasalkini.answer.understand import ARTICLE, provision_pairs
from pasalkini.corpus import Chunk
from pasalkini.temporal.corpus import NOTES_HEADING

MIN_QUOTE_CHARS = 12  # a shorter quote, or part of one, verifies nothing
MIN_COVERAGE = 0.8  # share of a quote's words that must be found for a near match
MIN_PART_COVERAGE = 0.6  # ... and of each part of a quote split by '…' or ':'
MIN_NEAR_WORDS = 5  # shorter parts must match word for word
MIN_RUN = 3  # a near match needs this many words in a row
MAX_PASSAGE_CHARS = 1200
MAX_BACK_REFERENCES = 2
# Where a quote may skip text: an ellipsis, or a colon ('… sebagai berikut: f. masa kerja 5 …'
# quotes a table's opening line and one of its rows).
GAP = re.compile(r"\s*(?:…|\.{3,}|:)\s*")
WORD = re.compile(r"\w+")
SCANNED_BRACKET = re.compile(r"\d+[il]")
# A note inside a version's text starts with the ID of the ruling or clause it comes from.
NOTE_ID = re.compile(r"^\[([^\]\s]+)\]", re.MULTILINE)
AYAT = re.compile(r"^\((\d+[a-z]?)\)")
ITEM = re.compile(r"^([a-z])[.\-]\s")
NUMBER_WORDS = frozenset(
    "nol satu dua tiga empat lima enam tujuh delapan sembilan sepuluh sebelas seratus seribu "
    "belas puluh ratus ribu juta setengah koma".split()
)
UNITS = dict(
    zip("nol satu dua tiga empat lima enam tujuh delapan sembilan".split(), range(10), strict=True)
)
TEENS = {"sepuluh": "10", "sebelas": "11", "seratus": "100", "seribu": "1000"}
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
SCALED = re.compile(r"(\d+(?:,\d+)?)\s*(ribu|juta|miliar)\b", re.IGNORECASE)
SCALES = {"ribu": 1_000, "juta": 1_000_000, "miliar": 1_000_000_000}
MONTHS = "Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember"
DATE = re.compile(
    rf"\b(?:\d{{1,2}} )?(?:{MONTHS}) \d{{4}}\b"
    r"|\b(?:tahun|pada|sejak|sebelum|setelah|sesudah|hingga|sampai) (?:19|20)\d{2}\b",
    re.IGNORECASE,
)


class Citation(BaseModel):
    source_id: str = Field(description="ID sumber dari KONTEKS, persis, tanpa tanda kurung")
    quote: str = Field(
        description="kutipan persis dari teks sumber itu: satu kalimat atau butir, paling "
        "banyak 40 kata"
    )


class Selection(BaseModel):
    """First call: the passages that answer the question."""

    kutipan: list[Citation]


class Answer(BaseModel):
    """Second call: the answer, written from the selected passages. The model first copies the
    words it answers from and any limit on them, then answers: a 4B model that answers straight
    away takes the first number it sees ('1 hari untuk 6 hari kerja atau 2 hari untuk 5 hari
    kerja' for someone who works 5 days) and skips the limiting sentence."""

    dasar: str | None = Field(description="bagian kutipan yang menjawab, disalin persis")
    batasan: str | None = Field(description="batas, syarat, pengecualian atau putusan MK")
    answer: str = Field(description="jawaban singkat, 1 sampai 3 kalimat")
    abstain: bool = Field(default=False, description="true jika kutipan tidak memuat jawabannya")
    perselisihan: bool = Field(
        default=False, description="true jika penanya sedang menghadapi PHK atau perselisihan"
    )


@dataclass
class Passage:
    """A verified quote: where it is, the source's own words, and the lines around it."""

    chunk: Chunk
    quote: str  # shown to the user
    # Where the quote is in the article's own text. Empty when it is in the title or the notes.
    spans: list[tuple[int, int]] = field(default_factory=list)

    @property
    def source_id(self) -> str:
        return self.chunk.source_id


def body_of(chunk: Chunk) -> str:
    """The article's own text, without the notes under it."""
    return chunk.text.partition(NOTES_HEADING)[0]


@dataclass
class Checked:
    passages: list[Passage] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)  # source IDs of quotes that did not pass

    @property
    def ok(self) -> bool:
        return not self.problems


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
    found, previous = [], ""
    for match in WORD.finditer(text):
        token = match.group().lower()
        # A scan reads the closing bracket of 'ayat (2)' as a letter: 'ayat (2l.,'.
        if previous == "ayat" and SCANNED_BRACKET.fullmatch(token):
            token = token[:-1]
        previous = token
        found.append((_fold(token), match.start(), match.end()))
    return found


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


def find_spans(quote: str, text: str) -> list[tuple[int, int]] | None:
    """Where the quote is in the text, as character ranges, or None when it is not there."""
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
    ranges = []
    for first, last in spans:
        start, end = source[first][1], source[last - 1][2]
        # Words carry no punctuation, so '(1) Perusahaan' would be cut to '1) Perusahaan'. Take
        # a bracket or quotation mark at either end when that balances the piece.
        piece = text[start:end]
        for opening, closing in ("()", "[]"):
            if start > 0 and text[start - 1] == opening:
                if piece.count(closing) > piece.count(opening):
                    start -= 1
            if end < len(text) and text[end] == closing:
                if piece.count(opening) > piece.count(closing):
                    end += 1
        if 0 < start and end < len(text) and text[start - 1] in '“"' and text[end] in '”"':
            start, end = start - 1, end + 1
        ranges.append((start, end))
    return ranges


def shown(text: str, spans: list[tuple[int, int]]) -> str:
    """The text at the ranges, on one line, with '…' between ranges."""
    return " … ".join(" ".join(text[start:end].split()) for start, end in spans)


def locate(quote: str, text: str) -> str | None:
    """The source's own words for the quote, or None when the quote is not there."""
    spans = find_spans(quote, text)
    return None if spans is None else shown(text, spans)


def quote_in(quote: str, text: str) -> bool:
    return find_spans(quote, text) is not None


class _Layout:
    """An article's text as lines: where each starts, the ayat it belongs to, the line that
    opens that ayat, and the letter of a list item ('b' for 'b. istirahat mingguan …')."""

    def __init__(self, body: str) -> None:
        self.lines = body.split("\n")
        self.starts: list[int] = []
        self.ayat: list[str | None] = []
        self.opener: list[int | None] = []
        position, current, current_line = 0, None, None
        for i, line in enumerate(self.lines):
            self.starts.append(position)
            position += len(line) + 1
            match = AYAT.match(line)
            if match:
                current, current_line = match.group(1), i
            self.ayat.append(current)
            self.opener.append(current_line)

    def item(self, i: int) -> str | None:
        match = ITEM.match(self.lines[i])
        return match.group(1) if match else None

    def touched(self, spans: list[tuple[int, int]]) -> list[int]:
        """The lines the character ranges touch."""

        def line_at(offset: int) -> int:
            return max(i for i, start in enumerate(self.starts) if start <= offset)

        found: set[int] = set()
        for start, end in spans:
            found.update(range(line_at(start), line_at(max(start, end - 1)) + 1))
        return sorted(found)

    def span(self, i: int) -> tuple[int, int]:
        return self.starts[i], self.starts[i] + len(self.lines[i])


def places(body: str, spans: list[tuple[int, int]]) -> list[tuple[str | None, str | None]]:
    """Where the spans are in the article: the (ayat, item letter) of each line they touch."""
    layout = _Layout(body)
    return [(layout.ayat[i], layout.item(i)) for i in layout.touched(spans)]


def same_places(body: str, wanted: list[tuple[str | None, str | None]]) -> list[tuple[int, int]]:
    """The same ayat and items in another wording of the article, as character ranges: the item
    when that wording has it, otherwise the line that opens the ayat. Empty when the wording
    has none of them."""
    layout = _Layout(body)
    found: list[int] = []
    for ayat, letter in wanted:
        in_ayat = [i for i, a in enumerate(layout.ayat) if a == ayat]
        items = [i for i in in_ayat if letter and layout.item(i) == letter]
        if items:
            found.append(items[0])
        elif ayat is not None and in_ayat:
            found.append(in_ayat[0])
    return [layout.span(i) for i in sorted(set(found))]


def opening(body: str) -> list[tuple[int, int]]:
    """The article's first line, as a character range."""
    return [(0, len(body.split("\n", 1)[0]))]


def expand(body: str, spans: list[tuple[int, int]]) -> tuple[str, set[str]]:
    """The whole lines the spans touch, with what a reader needs beside them:
    - the opening line of the ayat a list item belongs to ('(2) Waktu istirahat … meliputi:');
    - the items under a quoted line that ends with a colon, unless one of them is quoted;
    - other lines of the article that refer back to what was quoted ('… sebagaimana dimaksud
      dalam ayat (2) huruf d hanya berlaku bagi …'), at most MAX_BACK_REFERENCES of them.
    Returns the text and the ayat of the quoted lines."""
    layout = _Layout(body)
    lines, ayat_of, opener = layout.lines, layout.ayat, layout.opener
    quoted = layout.touched(spans)
    keep = set(quoted) | {opener[i] for i in quoted if opener[i] is not None}
    for i in quoted:
        if lines[i].rstrip().endswith(":"):
            items = []
            while i + 1 < len(lines) and not AYAT.match(lines[i + 1]):
                i += 1
                items.append(i)
            if not set(items) & set(quoted):  # the quote does not already say which item
                keep.update(items)

    wanted = []
    for i in quoted:
        if ayat_of[i] is None:
            continue
        about = rf"ayat \({ayat_of[i]}\)"
        wanted.append(about + r"(?!,? huruf)")  # the ayat as a whole
        if layout.item(i):
            wanted.append(about + rf",? huruf {layout.item(i)}\b")
    references = 0
    for j, line in enumerate(lines):
        if j in keep or references == MAX_BACK_REFERENCES:
            continue
        if any(re.search(pattern, line) for pattern in wanted):
            keep.add(j)
            references += 1

    out, previous = [], None
    for i in sorted(keep):
        if previous is not None and i > previous + 1:
            out.append("…")
        out.append(lines[i])
        previous = i
    text = "\n".join(out)
    if len(text) > MAX_PASSAGE_CHARS:
        text = text[:MAX_PASSAGE_CHARS] + " …"
    return text, {ayat_of[i] for i in quoted if ayat_of[i] is not None}


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
) -> tuple[Passage | None, str | None]:
    """(the passage, None) when the quote passes; otherwise (None, the problem)."""
    source_id = citation.source_id
    named = [c for c in context if c.source_id == source_id]
    # Models cite the ruling that conditions an article by the ID in the article's notes.
    named = named or [c for c in context if cites_note(c, source_id)]
    stale = False
    # The chunk the model named first; a right quote under a wrong ID is still a right quote.
    for chunk in named + [c for c in context if c not in named]:
        # The title counts: for a status question the evidence is the validity it states.
        whole = chunk.title + "\n" + chunk.text
        spans = find_spans(citation.quote, whole)
        if spans is None:
            continue
        applies = history or as_of is None or not hasattr(chunk, "valid_on")
        if not applies and not chunk.valid_on(as_of):
            stale = True
            continue
        # The answer step reads the lines around the quote in the article's own text. A quote
        # from the title or the notes has none: notes reach it as readings of the rulings.
        offset, body = len(chunk.title) + 1, body_of(chunk)
        in_body = [
            (start - offset, end - offset)
            for start, end in spans
            if offset <= start < offset + len(body)
        ]
        return Passage(chunk, shown(whole, spans), in_body), None
    if stale:
        return None, f"[{source_id}] tidak berlaku pada {as_of.isoformat()}."
    if not named:
        return None, f"[{source_id}] tidak ada di KONTEKS."
    return None, f"[{source_id}] kutipan tidak ditemukan di teks sumbernya."


def check_selection(
    selection: Selection, context: list[Chunk], as_of: date | None, history: bool
) -> Checked:
    """Verify each selected quote. Two quotes that land on the same passage count once."""
    result = Checked()
    seen: set[tuple[str, str]] = set()
    for citation in selection.kutipan:
        cleaned = citation.model_copy(update={"source_id": clean_source_id(citation.source_id)})
        passage, problem = check_citation(cleaned, context, as_of, history)
        if passage is None:
            result.problems.append(problem)
            result.failed.append(cleaned.source_id)
        elif (passage.source_id, passage.quote) not in seen:
            seen.add((passage.source_id, passage.quote))
            result.passages.append(passage)
    return result


def _normal(raw: str) -> str:
    """One spelling for a number: '18.000.000' and '18000000', '1.8' and '1,8', '2,0' and '2'."""
    whole, _, fraction = raw.partition(",")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", whole):
        whole = whole.replace(".", "")
    elif "." in whole and not fraction:
        whole, _, fraction = whole.partition(".")
    fraction = fraction.rstrip("0")
    return f"{whole},{fraction}" if fraction else whole


def _scaled(match: re.Match) -> str:
    value = float(match.group(1).replace(",", ".")) * SCALES[match.group(2).lower()]
    return str(round(value))


def numbers_in(text: str, scaled: bool = True) -> list[str]:
    """Every number written in digits, in order. '4,5 juta' counts as 4500000, or with
    scaled=False as 4,5."""
    if scaled:
        text = SCALED.sub(_scaled, text)
    return list(dict.fromkeys(_normal(match.group()) for match in NUMBER.finditer(text)))


def spelled_numbers(text: str) -> set[str]:
    """Numbers written in words ('tiga puluh', 'dua belas'), as digits. Legal texts give both
    forms, and a scan sometimes garbles the digits ('I (satu) hari')."""
    words = re.findall(r"[a-z]+", text.lower())
    found = set()
    for i, word in enumerate(words):
        following = [*words[i + 1 : i + 3], "", ""]
        if word in TEENS:
            found.add(TEENS[word])
        elif word == "setengah":
            found.add("0,5")
        elif word in UNITS:
            n = UNITS[word]
            found.add(str(n))
            if following[0] == "belas":
                found.add(str(10 + n))
            elif following[0] == "ratus":
                found.add(str(100 * n))
            elif following[0] == "puluh":
                found.add(str(10 * n))
                if following[1] in UNITS:
                    found.add(str(10 * n + UNITS[following[1]]))
    return found


def provisions_of(chunk: Chunk) -> set[str]:
    """The articles a chunk can be called by: the article it is a version of, and the point of
    the amending law that published its wording ('uu-11-2020/pasal-81')."""
    found = {getattr(chunk, "provision_id", chunk.source_id)}
    parts = chunk.source_id.split("/")
    if len(parts) > 1 and parts[1].startswith("pasal-"):
        found.add("/".join(parts[:2]))
    return found


def _name(provision_id: str) -> str:
    instrument, _, article = provision_id.partition("/pasal-")
    kind, number, year = instrument.split("-")
    kind = "Perppu" if kind == "perppu" else kind.upper()
    return f"Pasal {article.upper()} {kind} {number}/{year}"


def ungrounded(answer: str, material: str, provisions: set[str]) -> list[str]:
    """What the answer mentions that it was not given: an article attributed to an instrument
    none of its passages come from, an article number, or a number. `material` is everything
    the answer step saw; `provisions` are the articles its passages belong to."""
    known = provisions | set(provision_pairs(material))
    problems = [_name(pair) for pair in provision_pairs(answer) if pair not in known]
    articles = {a.upper() for a in re.findall(ARTICLE, material, re.IGNORECASE)}
    articles |= {p.partition("/pasal-")[2].upper() for p in known}
    unknown = [a.upper() for a in re.findall(ARTICLE, answer, re.IGNORECASE)]
    unknown = [a for a in dict.fromkeys(unknown) if a not in articles]
    problems += [f"Pasal {article}" for article in unknown]
    numbers = {*numbers_in(material), *numbers_in(material, scaled=False)}
    numbers |= spelled_numbers(material)
    for number in numbers_in(answer):
        if number not in numbers and number not in unknown:
            problems.append(f"angka {number}")
    return list(dict.fromkeys(problems))


def dates_in(answer: str) -> list[str]:
    """Dates and years the answer states: '2 November 2020', 'Maret 2019', 'sejak 2020'."""
    return list(dict.fromkeys(match.group() for match in DATE.finditer(answer)))
