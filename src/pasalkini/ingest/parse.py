"""Clean lines → articles, ayat, amendment points, penjelasan and MK rulings.

The parser relies on *numbering order* rather than on line shape alone:

- A document's own articles run 1, 2, 3 … (or I, II in amending regulations). A 'Pasal 59'
  heading inside Pasal 81 of the Cipta Kerja law is not an article of that law; it is the new
  wording of UU 13/2003 Pasal 59 quoted inside an amendment point.
- Ayat run (1), (2), (3) … with inserted ayat such as (1a). Knowing which number comes next lets
  the parser repair OCR errors: '(21 PKWT …' after ayat (1) is ayat (2).
- Amendment points ('angka') run 1, 2, 3 … and start with a standard instruction such as
  'Ketentuan Pasal 59 diubah sehingga berbunyi sebagai berikut:'.
"""

import re
from dataclasses import dataclass, field

from pasalkini.ingest.extract import Line
from pasalkini.ingest.models import (
    AmarPoint,
    AmendmentPoint,
    Article,
    Ayat,
    EmbeddedArticle,
)

# ---------------------------------------------------------------- patterns

# OCR puts letters in numbers ('Pasal 8O') and junk after them ('Pasal 88E}'); both are tolerated
# here and normalised in parse_pasal_heading.
PASAL_HEADING = re.compile(r"^Pasa[l1I]\s*((?:[\dOoIl]\s?){1,4}[A-Z]?|[IVXLl]{1,6})\s*[}'’\]]?$")
BAB_HEADING = re.compile(r"^BAB\s+([IVXLCl]+[A-Z]?)$")
BAGIAN_HEADING = re.compile(r"^Bagian\s+(Ke[a-z]+|Pertama)(\s+[A-Z])?$")
PARAGRAF_HEADING = re.compile(r"^Paragraf\s+(\d+[A-Z]?)$")

# '(1) text', '(1a) text', and OCR variants '(21 text', '(4l', '(2]', '( 1)'
AYAT_MARKER = re.compile(r"^\(\s*([0-9Il]{1,3})([a-z])?\s*([)\]}|])?\s*(.*)$")
LIST_ITEM = re.compile(r"^([a-z]|\d{1,2})\s?[.)](\s|$)")
# Point numbers as OCR reads them: '17.', 'L7.', '3O.'; see point_number()
POINT_MARKER = re.compile(r"^([\dOoIlL]{1,3})\s?\.\s*(.*)$")
INSTRUCTION = re.compile(
    r"^(Ketentuan\s+(ayat|Pasa[l1I]|huruf|angka|Penjelasan|BAB|Bab|Bagian|Paragraf|Lampiran|judul)"
    r"|Di\s*antara|Pasa[l1I]\s*[\dOoIl]+[A-Z]?\s*dihapus|Penjelasan\s+(ayat|Pasa[l1I]|umum)|Judul"
    r"|Menambahkan|Menyisipkan|Setelah\s+(ayat|Pasa[l1I]|Bagian|Bab|BAB|Paragraf|huruf|angka))"
    # Case-sensitive on purpose: an instruction starts a sentence. A lowercase 'ketentuan Pasal …'
    # at the start of a line is the continuation of the previous instruction.
)
# OCR sometimes merges two points onto one line: 'Pasal 89 dihapus. 3O. Pasal 90dihapus.'
MERGED_POINT = re.compile(
    r"(?<=[.;:])\s+(?=[\dOoIlL]{1,3}\s?\.\s+(Pasa[l1I]|Ketentuan|Di\s*antara))"
)


def point_number(token: str) -> int | None:
    if not re.search(r"\d", token):
        return None
    return int(token.translate(str.maketrans("OoIlL", "00111")))


def split_merged_lines(lines: list[Line]) -> list[Line]:
    out = []
    for line in lines:
        parts = MERGED_POINT.split(line.text)
        # re.split also returns the captured keyword group; keep only the text pieces
        pieces = [p for k, p in enumerate(parts) if k % 2 == 0]
        out += [Line(line.page, p.strip()) for p in pieces if p.strip()]
    return out


# Searched anywhere in the line: OCR sometimes breaks 'Agar setiap' onto the previous line.
CLOSING = re.compile(r"^Agar\s+setiap\s+orang\s+mengetahui|mengetahuinya,?\s*memerintah", re.I)
PENJELASAN_START = re.compile(r"^PENJELASAN$")
PENJELASAN_OCR = re.compile(r"^PENJ\S{3,8}$")  # e.g. 'PENJET,ASAN'; only with 'ATAS' next
UMUM = re.compile(r"^(I\s*\.?\s*)?UMUM$")
PASAL_DEMI_PASAL = re.compile(r"^(II\s*\.?\s*)?PASAL\s+DEMI\s+PASAL$")
MENGADILI = re.compile(r"^M\s*E\s*N\s*G\s*A\s*D\s*I\s*L\s*I\s*[:,]?$", re.IGNORECASE)
DEMIKIAN = re.compile(r"^Demikian\s+diputus", re.IGNORECASE)
OPINION = re.compile(r"^\d+\.\s*(PENDAPAT|ALASAN)\s+BERBEDA", re.IGNORECASE)

ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman_to_int(numeral: str) -> int:
    total, previous = 0, 0
    for char in reversed(numeral):
        value = ROMAN_VALUES[char]
        total = total - value if value < previous else total + value
        previous = max(previous, value)
    return total


# ---------------------------------------------------------------- headings


@dataclass(frozen=True)
class HeadingNumber:
    label: str  # normalised: '59', '61A', 'II'
    value: int
    suffix: str
    roman: bool


def parse_pasal_heading(text: str, roman_allowed: bool) -> HeadingNumber | None:
    match = PASAL_HEADING.match(text)
    if not match:
        return None
    token = match.group(1).replace(" ", "")
    if roman_allowed and re.fullmatch(r"[IVXLl]+", token):
        numeral = token.replace("l", "I")
        return HeadingNumber(numeral, roman_to_int(numeral), "", roman=True)
    if not re.search(r"\d", token):
        return None  # letters only, in a document numbered in arabic: not a heading
    number_part = re.match(r"[\dOoIl]+", token).group()
    suffix = token[len(number_part) :]
    number = number_part.translate(str.maketrans("OoIl", "0011"))
    return HeadingNumber(number + suffix, int(number), suffix, roman=False)


# ---------------------------------------------------------------- text helpers


def join_lines(lines: list[str]) -> str:
    """Join wrapped lines into paragraphs; list items ('a.', '1.', '1)') start a new line."""
    out: list[str] = []
    for text in lines:
        if out and not LIST_ITEM.match(text):
            out[-1] = out[-1] + text if out[-1].endswith("-") else f"{out[-1]} {text}"
        else:
            out.append(text)
    return "\n".join(out)


def parse_ayat(lines: list[Line], first_must_be_one: bool, where: str, warnings: list[str]):
    """Split an article's lines into intro text and ayat, repairing OCR'd markers by order."""
    intro: list[str] = []
    ayat: list[tuple[str, list[str]]] = []
    last_number, last_suffix = 0, ""

    for line in lines:
        chosen = None
        match = AYAT_MARKER.match(line.text)
        # A real marker is followed by nothing or by the start of a sentence. '(4), maka …' or
        # '(1) huruf a …' at the start of a line is a wrapped reference, not a marker.
        if match and match.group(4) and not re.match(r"^[A-Z0-9“\"'(]", match.group(4)):
            match = None
        if match:
            digits = match.group(1).replace("I", "1").replace("l", "1")
            suffix, close, rest = match.group(2) or "", match.group(3), match.group(4)
            candidates = []  # (number, suffix, clean)
            if close:
                candidates.append((int(digits), suffix, True))
            elif not suffix:
                candidates.append((int(digits), "", False))
                if len(digits) > 1 and digits.endswith("1"):
                    candidates.append((int(digits[:-1]), "", False))  # ')' read as '1'
            for number, suf, clean in candidates:
                if not ayat:
                    if (number == 1 and not suf) or (not first_must_be_one and clean):
                        chosen = (number, suf)
                elif not suf and number == last_number + 1:
                    chosen = (number, suf)
                elif suf and clean and number == last_number and suf > last_suffix:
                    chosen = (number, suf)
                elif not suf and clean and number == last_number + 2:
                    warnings.append(
                        f"{where}: ayat ({last_number + 1}) missing; jumped to ({number})"
                    )
                    chosen = (number, suf)
                if chosen:
                    break
        if chosen:
            last_number, last_suffix = chosen
            ayat.append((f"{chosen[0]}{chosen[1]}", [rest] if rest else []))
        elif ayat:
            ayat[-1][1].append(line.text)
        else:
            intro.append(line.text)

    return join_lines(intro), [Ayat(number=n, text=join_lines(t)) for n, t in ayat]


# ---------------------------------------------------------------- segmentation


@dataclass
class EmbeddedBlock:
    heading: HeadingNumber
    lines: list[Line] = field(default_factory=list)


@dataclass
class PointBlock:
    number: int
    inferred: bool
    first_line: Line
    lines: list[Line] = field(default_factory=list)
    embedded: list[EmbeddedBlock] = field(default_factory=list)

    def last_page(self) -> int:
        pages = [ln.page for ln in self.lines] + [ln.page for e in self.embedded for ln in e.lines]
        return max(pages, default=self.first_line.page)


@dataclass
class ArticleBlock:
    heading: HeadingNumber
    context: dict[str, str]
    first_line: Line
    lines: list[Line] = field(default_factory=list)
    points: list[PointBlock] = field(default_factory=list)

    def last_page(self) -> int:
        pages = [ln.page for ln in self.lines] + [p.last_page() for p in self.points]
        return max(pages, default=self.first_line.page)

    def text_so_far(self) -> str:
        return " ".join(ln.text for ln in self.lines)


def ends_sentence(text: str) -> bool:
    return text.rstrip().endswith((".", ";", ":"))


def instruction_strength(lines: list[Line], i: int) -> str | None:
    """How sure we are that an unnumbered line starts an amendment point (OCR lost the number).

    'strong': the standard wording of an amendment ('… diubah sehingga berbunyi', 'disisipkan',
    'dihapus') follows within a few lines. 'weak': only 'sebagai berikut'.
    """
    if not INSTRUCTION.match(lines[i].text):
        return None
    window = " ".join(ln.text for ln in lines[i : i + 4])
    if re.search(r"sehingga\s+(ber|men)bunyi|disisipkan|ditambahkan|dihapus", window):
        return "strong"
    return "weak" if "berikut" in window else None


def segment(
    lines: list[Line], roman: bool, first_any: bool, where: str, warnings: list[str]
) -> list[ArticleBlock]:
    """Group lines into own articles, their amendment points, and embedded articles."""
    lines = split_merged_lines(lines)
    blocks: list[ArticleBlock] = []
    context: dict[str, str] = {}
    expected: int | None = None
    previous = ":"  # last content line; ':' means 'a heading or the start'
    i = 0

    def is_own(h: HeadingNumber, current: ArticleBlock | None, in_points: bool, nxt: str) -> bool:
        if h.suffix:
            return False
        if expected is None:
            return first_any or h.value == 1
        if roman and not h.roman:
            return False
        if h.value != expected and not (h.value == expected + 1 and not in_points):
            return False
        if in_points and previous.rstrip().endswith("berikut:"):
            return False  # the instruction just introduced this heading: it's embedded
        # A heading follows a finished sentence, or is followed by the start of an article.
        # 'Pasal 64' wrapped mid-sentence is followed by lowercase text such as 'ayat (1) …'.
        starts_article = bool(re.match(r"^(\(\s*[0-9Il]|[A-Z])", nxt))
        return ends_sentence(previous) or current is None or starts_article

    while i < len(lines):
        line = lines[i]
        text = line.text
        current = blocks[-1] if blocks else None
        in_points = bool(current and current.points)
        point = current.points[-1] if in_points else None

        if not in_points:
            bab = BAB_HEADING.match(text)
            if bab:
                context = {"bab": f"BAB {bab.group(1).replace('l', 'I')}"}
                title = []
                while (
                    i + 1 < len(lines)
                    and lines[i + 1].text.isupper()
                    and not (
                        PASAL_HEADING.match(lines[i + 1].text)
                        or BAB_HEADING.match(lines[i + 1].text)
                    )
                ):
                    i += 1
                    title.append(lines[i].text)
                context["bab_title"] = " ".join(title)
                previous = ":"
                i += 1
                continue
            key = "bagian" if BAGIAN_HEADING.match(text) else None
            key = key or ("paragraf" if PARAGRAF_HEADING.match(text) else None)
            if key:
                if key == "bagian":
                    context = {k: v for k, v in context.items() if k.startswith("bab")}
                context = {k: v for k, v in context.items() if not k.startswith("paragraf")}
                context[key] = text
                if i + 1 < len(lines) and not PASAL_HEADING.match(lines[i + 1].text):
                    i += 1
                    context[f"{key}_title"] = lines[i].text
                previous = ":"
                i += 1
                continue

        heading = parse_pasal_heading(text, roman_allowed=roman)
        if heading:
            nxt = lines[i + 1].text if i + 1 < len(lines) else ""
            if is_own(heading, current, in_points, nxt):
                if expected is not None and heading.value == expected + 1:
                    warnings.append(f"{where}: Pasal {expected} heading not found (OCR?)")
                blocks.append(ArticleBlock(heading, dict(context), line))
                expected = heading.value + 1
                previous = ":"
                i += 1
                continue
            if point is not None:
                point.embedded.append(EmbeddedBlock(heading, []))
                previous = ":"
                i += 1
                continue
            if current is not None and expected is not None and heading.value == expected:
                warnings.append(
                    f"{where}: 'Pasal {heading.label}' on page {line.page} not taken as a heading "
                    f"(previous line: '{previous[-40:]}')"
                )

        if current is None:  # preamble before the first article
            i += 1
            continue

        next_point = point.number + 1 if point else 1
        marker = POINT_MARKER.match(text)
        marker_number = point_number(marker.group(1)) if marker else None
        # A number followed by an instruction is strong evidence, so allow it to skip up to three
        # points whose numbers OCR lost ('17.' missing, then '18. Ketentuan Pasal 64 …').
        if marker_number is not None and next_point <= marker_number <= next_point + 3:
            rest = marker.group(2)
            probe = rest if rest else (lines[i + 1].text if i + 1 < len(lines) else "")
            if INSTRUCTION.match(probe):
                number = marker_number
                if number != next_point:
                    warnings.append(
                        f"{where}: amendment points {next_point}–{number - 1} not found before "
                        f"point {number} (page {line.page})"
                    )
                new_point = PointBlock(number, False, line)
                if rest:
                    new_point.lines.append(Line(line.page, rest))
                    i += 1
                else:  # number alone on its line: the instruction is the next line
                    new_point.lines.append(lines[i + 1])
                    i += 2
                current.points.append(new_point)
                previous = new_point.lines[-1].text
                continue
        can_infer = in_points or current.text_so_far().rstrip().endswith("berikut:")
        strength = instruction_strength(lines, i) if can_infer else None
        if strength == "strong" or (strength == "weak" and ends_sentence(previous)):
            warnings.append(f"{where}: amendment point {next_point} has no number (OCR?); inferred")
            current.points.append(PointBlock(next_point, True, line, [line]))
            previous = text
            i += 1
            continue

        if point is not None and point.embedded:
            point.embedded[-1].lines.append(line)
        elif point is not None:
            point.lines.append(line)
        else:
            current.lines.append(line)
        previous = text
        i += 1

    return blocks


# ---------------------------------------------------------------- document parts


def is_penjelasan_start(lines: list[Line], i: int) -> bool:
    text = lines[i].text
    if PENJELASAN_START.match(text):
        return True
    return bool(PENJELASAN_OCR.match(text)) and i + 1 < len(lines) and lines[i + 1].text == "ATAS"


def starts_closing(lines: list[Line], i: int) -> bool:
    """'Agar setiap orang mengetahuinya, memerintahkan …' starts here.

    Justified typeset text can put one word per line, so the phrase is matched over a window
    of lines that starts at line i.
    """
    if CLOSING.search(lines[i].text):
        return True
    if not lines[i].text.startswith("Agar"):
        return False
    window = " ".join(ln.text for ln in lines[i : i + 6])
    return bool(CLOSING.match(window))


def split_parts(lines: list[Line]) -> tuple[list[Line], list[Line], list[Line]]:
    """body (up to 'Agar setiap orang mengetahuinya'), closing, penjelasan."""
    end = next((i for i in range(len(lines)) if starts_closing(lines, i)), None)
    search_from = end if end is not None else 0
    start_pj = next(
        (i for i in range(search_from, len(lines)) if is_penjelasan_start(lines, i)), len(lines)
    )
    if end is None:
        end = start_pj
    return lines[:end], lines[end:start_pj], lines[start_pj:]


def cut_scope(lines: list[Line], start: str, end: str, where: str, warnings: list[str]):
    starts = [i for i, ln in enumerate(lines) if ln.text == start]
    if not starts:
        warnings.append(f"{where}: scope start '{start}' not found; parsing everything")
        return lines
    if len(starts) > 1:
        warnings.append(f"{where}: '{start}' appears {len(starts)} times; using the first")
    s = starts[0]
    e = next((i for i in range(s + 1, len(lines)) if lines[i].text == end), None)
    if e is None:
        warnings.append(f"{where}: scope end '{end}' not found after '{start}'")
        return lines[s:]
    return lines[s:e]


def repair_inserted_labels(
    instruction: str, embedded: list[EmbeddedArticle], where: str, warnings: list[str]
) -> None:
    """Use the instruction's own list of inserted articles to fix OCR'd labels.

    'disisipkan 6 (enam) pasal, yakni Pasal 88A, Pasal 88B, …' tells us the labels; OCR may have
    read the heading 'Pasal 88B' as 'Pasal 88E' or 'Pasal 61A' as 'Pasal 614'.
    """
    if "disisipkan" not in instruction or "yakni" not in instruction:
        return
    # Only the list after 'yakni'; 'Di antara Pasal 9O dan …' before it names neighbours.
    listed = re.findall(r"Pasa[l1I]\s*(\d{1,3}[A-Z])\b", instruction.split("yakni", 1)[1])
    if len(listed) != len(embedded):
        return
    for article, label in zip(embedded, listed, strict=True):
        if article.number != label:
            warnings.append(f"{where}: quoted 'Pasal {article.number}' relabelled 'Pasal {label}'")
            article.number, article.label = label, f"Pasal {label}"


def check_named_in_instruction(
    instruction: str, embedded: list[EmbeddedArticle], where: str, warnings: list[str]
) -> None:
    """Every quoted article should be named in its point's instruction; flag the ones that aren't.

    Usually a sign that OCR lost the next point's instruction and its article landed here.
    """
    # Inserting a whole Bab, Bagian or Paragraf names the section, not the articles inside it.
    if re.search(
        r"(disisipkan|ditambahkan)\s+\d+\s*\(\w+\)\s*(bab|bagian|paragraf)", instruction, re.I
    ):
        return
    named = set()
    for token in re.findall(r"Pasa[l1I]\s*([\dOoIl]{1,4}[A-Z]?)", instruction):
        digits = re.match(r"[\dOoIl]+", token).group()
        named.add(digits.translate(str.maketrans("OoIl", "0011")) + token[len(digits) :])
    for article in embedded:
        if article.number not in named:
            warnings.append(f"{where}: quoted Pasal {article.number} not named in the instruction")


def build_articles(
    instrument_id: str, blocks: list[ArticleBlock], where: str, warnings: list[str]
) -> list[Article]:
    articles = []
    for block in blocks:
        label = f"Pasal {block.heading.label}"
        source_id = f"{instrument_id}/pasal-{block.heading.label.lower()}"
        intro, ayat = parse_ayat(block.lines, True, f"{where} {label}", warnings)
        points = []
        for p in block.points:
            embedded = []
            for e in p.embedded:
                e_label = f"Pasal {e.heading.label}"
                e_where = f"{where} {label} angka {p.number} {e_label}"
                e_intro, e_ayat = parse_ayat(e.lines, False, e_where, warnings)
                pages = [ln.page for ln in e.lines] or [p.first_line.page]
                embedded.append(
                    EmbeddedArticle(
                        label=e_label,
                        number=e.heading.label,
                        intro=e_intro,
                        ayat=e_ayat,
                        page_start=min(pages),
                        page_end=max(pages),
                    )
                )
            instruction = join_lines([ln.text for ln in p.lines])
            p_where = f"{where} {label} angka {p.number}"
            repair_inserted_labels(instruction, embedded, p_where, warnings)
            check_named_in_instruction(instruction, embedded, p_where, warnings)
            points.append(
                AmendmentPoint(
                    source_id=f"{source_id}/angka-{p.number}",
                    number=p.number,
                    number_inferred=p.inferred,
                    instruction=instruction,
                    articles=embedded,
                    page_start=p.first_line.page,
                    page_end=p.last_page(),
                )
            )
        if not intro and not ayat and not points:
            warnings.append(f"{where}: {label} has no text")
        articles.append(
            Article(
                source_id=source_id,
                label=label,
                number=block.heading.label,
                context=block.context,
                intro=intro,
                ayat=ayat,
                points=points,
                page_start=block.first_line.page,
                page_end=block.last_page(),
            )
        )
    return articles


def parse_penjelasan(
    lines: list[Line], roman: bool, where: str, warnings: list[str]
) -> tuple[str | None, dict[str, str]]:
    """General explanation and per-article explanations keyed by article label number."""
    umum_at = next((i for i, ln in enumerate(lines) if UMUM.match(ln.text)), None)
    pdp_at = next((i for i, ln in enumerate(lines) if PASAL_DEMI_PASAL.match(ln.text)), None)
    if pdp_at is None:
        warnings.append(f"{where}: 'PASAL DEMI PASAL' not found in penjelasan")
        return None, {}
    umum = None
    if umum_at is not None and umum_at < pdp_at:
        umum = join_lines([ln.text for ln in lines[umum_at + 1 : pdp_at]])

    per_article: dict[str, list[str]] = {}
    expected = 1
    current: str | None = None
    previous = ":"
    for line in lines[pdp_at + 1 :]:
        heading = parse_pasal_heading(line.text, roman_allowed=roman)
        is_own = (
            heading is not None
            and not heading.suffix
            and heading.value in (expected, expected + 1)
            and (heading.roman or not roman)
            and not previous.startswith("Angka")
            and not previous.rstrip().endswith("berikut:")
            and (heading.value == expected or ends_sentence(previous))
        )
        if is_own:
            if heading.value == expected + 1:
                warnings.append(f"{where}: penjelasan of Pasal {expected} not found (OCR?)")
            current = heading.label
            per_article[current] = []
            expected = heading.value + 1
            previous = ":"
            continue
        if current is not None:
            text = line.text
            if re.match(r"^(Ayat|Huruf|Angka|Pasal)\s", text) and per_article[current]:
                per_article[current].append("\n" + text)
            else:
                per_article[current].append(text)
        previous = line.text
    explained = {k: join_lines(v).replace(" \n", "\n").strip() for k, v in per_article.items() if v}
    return umum, explained


def parse_amar(lines: list[Line], where: str, warnings: list[str]):
    """The operative part of an MK decision: numbered points after the last 'Mengadili'."""
    starts = [i for i, ln in enumerate(lines) if MENGADILI.match(ln.text)]
    if not starts:
        warnings.append(f"{where}: 'Mengadili' not found")
        return [], ""
    start = starts[-1]
    end = next((i for i in range(start, len(lines)) if DEMIKIAN.match(lines[i].text)), len(lines))
    # A dissenting or concurring opinion can sit between the ruling and 'Demikian diputus'.
    stop = next((i for i in range(start, end) if OPINION.match(lines[i].text)), end)
    points: list[tuple[int, list[str]]] = []
    for line in lines[start + 1 : stop]:
        if re.fullmatch(r"-{3,}", line.text):
            continue
        marker = POINT_MARKER.match(line.text)
        bullet = re.match(r"^[•●▪\-–]\s*(.*)$", line.text)  # older decisions use bullets
        expected = points[-1][0] + 1 if points else 1
        if marker and point_number(marker.group(1)) == expected:
            points.append((expected, [marker.group(2)] if marker.group(2) else []))
        elif bullet and bullet.group(1)[:1].isupper():
            points.append((expected, [bullet.group(1)]))
        elif points:
            points[-1][1].append(line.text)
    amar = [AmarPoint(number=n, text=re.sub(r"\s*-{3,}\s*$", "", join_lines(t))) for n, t in points]
    closing = join_lines([ln.text for ln in lines[end : end + 30]])
    return amar, closing
