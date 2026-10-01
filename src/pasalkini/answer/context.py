"""Choose the chunks the model sees.

- Articles the question names come first: the version that applied on the date, or for status
  and history questions every version up to it, with the MK rulings attached to them.
- Then the articles the calculator used, then the search results.
- Consecutive periods of the same wording (split only by a status change, such as a conditional
  ruling) are shown as one chunk over the whole span.
- For status and history questions, each article found is shown with all its wordings, and
  code states the facts the temporal model holds: the timeline of an article (history_of) and
  whether it applied on the date (status_sentence). The model explains the content.
- A version's notes reach the answer step as plain readings of the rulings (rulings_read).
"""

import re
from collections import defaultdict
from datetime import date, timedelta

from pasalkini.corpus import Chunk
from pasalkini.temporal.corpus import NOTES_HEADING, DatedChunk
from pasalkini.temporal.query import format_date
from pasalkini.temporal.rulings import ayat_of, meaning_of, reading, struck, without

MAX_CONTEXT = 7  # about 5,000 prompt tokens at 2,500 characters a chunk
STATUS_WORDS = {"in_force": "berlaku", "conditional": "bersyarat", "repealed": "dihapus"}
NOTE = re.compile(r"^\[([^\]\s]+)\]\s*(.*)$")


def key(chunk: DatedChunk) -> tuple[str, str]:
    """One wording of one article. A source ID alone is not enough: one Perppu point can insert
    several articles."""
    return chunk.provision_id, chunk.source_id


def label(chunk: DatedChunk) -> str:
    """'UU 13/2003 Pasal 59' from 'UU 13/2003 Pasal 59 (berlaku …)'."""
    return chunk.title.split(" (")[0]


class Library:
    """The dated corpus, indexed for lookups by article and by source ID.

    `enacted` maps an instrument to the law that later enacted it unchanged and the date
    that law took effect: {'perppu-2-2022': ('uu-6-2023', date(2023, 3, 31))}.
    """

    def __init__(
        self, chunks: list[DatedChunk], enacted: dict[str, tuple[str, date]] | None = None
    ) -> None:
        self.enacted = enacted or {}
        self.by_provision: dict[str, list[DatedChunk]] = defaultdict(list)
        self.by_source: dict[str, list[DatedChunk]] = defaultdict(list)
        for chunk in sorted(chunks, key=lambda c: c.valid_from):
            self.by_provision[chunk.provision_id].append(chunk)
            self.by_source[chunk.source_id].append(chunk)

    def versions(self, provision_id: str, as_of: date, history: bool) -> list[DatedChunk]:
        mine = self.by_provision.get(provision_id, [])
        if history:
            return [c for c in mine if c.valid_from <= as_of]
        return [c for c in mine if c.valid_on(as_of)]

    def source_on(self, source_id: str, as_of: date) -> DatedChunk | None:
        """The chunk published at source_id that applied on the date."""
        return next((c for c in self.by_source.get(source_id, []) if c.valid_on(as_of)), None)

    def rulings_of(self, chunk: DatedChunk, as_of: date) -> list[DatedChunk]:
        return [
            ruling
            for ruling_id in chunk.rulings
            for ruling in self.by_source.get(ruling_id, [])
            if ruling.valid_from <= as_of
        ]

    def next_version(self, chunk: DatedChunk) -> DatedChunk | None:
        if chunk.valid_to is None:
            return None
        mine = self.by_provision.get(chunk.provision_id, [])
        return next((c for c in mine if c.valid_from == chunk.valid_to), None)

    def instrument(self, source_id: str, as_of: date) -> str:
        """'UU 11/2020'; 'Perppu 2/2022 (ditetapkan menjadi UU 6/2023)' once that law was
        in force on the date."""
        head = source_id.split("/")[0]
        name = instrument_label(head)
        if head in self.enacted and self.enacted[head][1] <= as_of:
            name += f" (ditetapkan menjadi {instrument_label(self.enacted[head][0])})"
        return name

    def periods(self, chunk: DatedChunk, as_of: date) -> list[DatedChunk]:
        """The unbroken run of periods of this chunk's wording that contains it, up to the date.
        A wording revived after a gap (a revoked amendment) is a separate run."""
        runs: list[list[DatedChunk]] = []
        for c in self.by_provision.get(chunk.provision_id, []):
            if key(c) != key(chunk) or c.valid_from > as_of:
                continue
            if runs and runs[-1][-1].valid_to == c.valid_from:
                runs[-1].append(c)
            else:
                runs.append([c])
        return next(
            (run for run in runs if chunk.valid_from in [c.valid_from for c in run]), [chunk]
        )


def merge_periods(periods: list[DatedChunk]) -> DatedChunk:
    """One chunk for consecutive periods of the same wording, titled with the whole span and
    each status change: 'UU 13/2003 Pasal 156 (berlaku 2 November 2020 s.d. 29 Desember 2022;
    bersyarat sejak 25 November 2021)'."""
    if len(periods) == 1:
        return periods[0]
    first, last = periods[0], periods[-1]
    start = format_date(first.valid_from)
    if last.valid_to is None:
        span = f"berlaku sejak {start}"
    else:
        span = f"berlaku {start} s.d. {format_date(last.valid_to - timedelta(days=1))}"
    notes = [span] if first.status == "in_force" else [span, STATUS_WORDS[first.status]]
    notes += [
        f"{STATUS_WORDS[c.status]} sejak {format_date(c.valid_from)}"
        for previous, c in zip(periods, periods[1:], strict=False)
        if c.status != previous.status
    ]
    return DatedChunk(
        source_id=last.source_id,
        instrument_id=last.instrument_id,
        title=f"{label(first)} ({'; '.join(notes)})",
        text=last.text,  # the latest period carries every note so far
        page=0,
        provision_id=last.provision_id,
        status=last.status,
        valid_from=first.valid_from,
        valid_to=last.valid_to,
        rulings=tuple(dict.fromkeys(r for c in periods for r in c.rulings)),
    )


def gather(
    library: Library,
    hits: list[Chunk],
    provisions: list[str],
    calculator_sources: list[str],
    as_of: date,
    history: bool,
    top_k: int,
) -> list[Chunk]:
    first: list[DatedChunk] = []
    for provision_id in provisions:
        for version in library.versions(provision_id, as_of, history):
            first += [version, *library.rulings_of(version, as_of)]
    for source_id in calculator_sources:
        chunk = library.source_on(source_id, as_of)
        if chunk is not None:
            first.append(chunk)

    # Each wording once, titled with its whole span: a version's own period can start at a
    # status change ('berlaku sejak 30 Desember 2022; bersyarat'), which reads as if the
    # regulation itself began that day.
    chosen: dict[tuple, DatedChunk] = {}

    def add(chunk: DatedChunk) -> None:
        run = library.periods(chunk, as_of)
        chosen.setdefault((key(chunk), run[0].valid_from), merge_periods(run))

    for chunk in first:
        add(chunk)
    limit = min(MAX_CONTEXT, top_k + len(chosen))
    for chunk in hits:
        if not isinstance(chunk, DatedChunk):
            continue
        if history:
            # A question about change needs wordings to compare: every wording of the
            # article this hit belongs to, oldest first.
            for version in library.versions(chunk.provision_id, as_of, history=True):
                add(version)
        else:
            add(chunk)
    return list(chosen.values())[:limit]


def changed_provisions(
    library: Library, context: list[Chunk], as_of: date, limit: int = 2
) -> list[str]:
    """Articles in the context that had more than one wording by the date, in context order."""
    found: list[str] = []
    for chunk in context:
        if not isinstance(chunk, DatedChunk) or chunk.provision_id in found:
            continue
        versions = library.versions(chunk.provision_id, as_of, history=True)
        if len({key(v) for v in versions}) > 1:
            found.append(chunk.provision_id)
    return found[:limit]


KIND_WORDS = {"uu": "UU", "pp": "PP", "perppu": "Perppu", "permenaker": "Permenaker"}


def instrument_label(source_id: str) -> str:
    """'UU 11/2020' from 'uu-11-2020/pasal-81/angka-15'; 'Putusan MK 168/PUU-XXI/2023'."""
    head = source_id.split("/")[0]
    match = re.fullmatch(r"([a-z]+)-(\d+)-(\d{4})", head)
    if match and match.group(1) in KIND_WORDS:
        return f"{KIND_WORDS[match.group(1)]} {match.group(2)}/{match.group(3)}"
    match = re.fullmatch(r"mk-(\d+)-puu-([a-z]+)-(\d{4})", head)
    if match:
        return f"Putusan MK {match.group(1)}/PUU-{match.group(2).upper()}/{match.group(3)}"
    return head


def is_original(chunk: DatedChunk) -> bool:
    """The wording was published by the article's own instrument, not by an amendment."""
    return chunk.source_id.split("/")[0] == chunk.provision_id.split("/")[0]


def timeline_line(library: Library, run: list[DatedChunk], as_of: date) -> str:
    first, last = run[0], run[-1]
    start = format_date(first.valid_from)
    if last.valid_to is None:
        span = f"sejak {start}"
    else:
        span = f"{start} s.d. {format_date(last.valid_to - timedelta(days=1))}"
    if first.status == "repealed":
        what = f"dihapus oleh {library.instrument(first.source_id, as_of)}"
    elif is_original(first):
        what = "bunyi asli"
    else:
        what = f"bunyi dari {library.instrument(first.source_id, as_of)}"
    line = f"- {span}: {what} [{first.source_id}]"
    if first.status == "conditional":
        line += "; bersyarat"
    for previous, c in zip(run, run[1:], strict=False):
        if c.status != previous.status:
            new = [r for r in c.rulings if r not in previous.rulings]
            by = ", ".join(dict.fromkeys(instrument_label(r) for r in new))
            line += f"; {STATUS_WORDS[c.status]} sejak {format_date(c.valid_from)}"
            line += f" ({by})" if by else ""
    return line


def first_deletion(library: Library, deleted: DatedChunk, as_of: date) -> DatedChunk:
    """An article deleted by one law and deleted again by its replacement (UU 11/2020, then
    Perppu 2/2022) has been gone since the first deletion, not since the latest one."""
    first = deleted
    for version in reversed(library.versions(deleted.provision_id, as_of, history=True)):
        if version.status == "repealed" and version.valid_to == first.valid_from:
            first = version
    return first


def history_of(library: Library, provision_id: str, as_of: date) -> str | None:
    """The article's timeline up to the date and its status on it, stated by code from the
    temporal model. None when the article is not in the model."""
    runs: dict[tuple, list[DatedChunk]] = {}
    for chunk in library.versions(provision_id, as_of, history=True):
        run = library.periods(chunk, as_of)
        runs.setdefault((key(chunk), run[0].valid_from), run)
    if not runs:
        return None
    name = label(next(iter(runs.values()))[0])
    lines = [f"Riwayat {name}:"]
    lines += [timeline_line(library, run, as_of) for run in runs.values()]
    current = library.versions(provision_id, as_of, history=False)
    day = format_date(as_of)
    if not current:
        lines.append(f"Pada {day}: tidak ada versi yang berlaku.")
    elif current[0].status == "repealed":
        since = first_deletion(library, current[0], as_of).valid_from
        by = library.instrument(current[0].source_id, as_of)
        lines.append(
            f"Pada {day}: sudah dihapus. Dihapus sejak {format_date(since)}; dasarnya sekarang "
            f"{by} [{current[0].source_id}]."
        )
    else:
        now = current[0]
        how = "berlaku bersyarat" if now.status == "conditional" else "berlaku"
        if is_original(now):
            lines.append(f"Pada {day}: {how} dengan bunyi aslinya [{now.source_id}].")
        else:
            by = library.instrument(now.source_id, as_of)
            lines.append(
                f"Pada {day}: {how} dengan bunyi dari {by} [{now.source_id}], bukan bunyi aslinya."
            )
    return "\n".join(lines)


def status_sentence(library: Library, provision_id: str, as_of: date) -> str | None:
    """Whether the article applied on the date and in which wording, as the sentence an answer
    opens with. Stated by code: the model got these dates wrong. None when the article is not
    in the model."""
    versions = library.versions(provision_id, as_of, history=True)
    if not versions:
        return None
    name, day = label(versions[0]), format_date(as_of)
    current = library.versions(provision_id, as_of, history=False)
    if not current:
        return f"Pada {day} tidak ada versi {name} yang berlaku."
    now = current[0]
    if now.status == "repealed":
        first = first_deletion(library, now, as_of)
        sentence = (
            f"{name} sudah tidak berlaku pada {day}: pasal ini dihapus sejak "
            f"{format_date(first.valid_from)} oleh {library.instrument(first.source_id, as_of)}"
        )
        if first.source_id.split("/")[0] != now.source_id.split("/")[0]:
            sentence += f", dan tetap dihapus dalam {library.instrument(now.source_id, as_of)}"
        return sentence + "."
    how = "berlaku bersyarat" if now.status == "conditional" else "berlaku"
    if is_original(now):
        return f"{name} masih {how} pada {day} dengan bunyi aslinya."
    since = format_date(library.periods(now, as_of)[0].valid_from)
    sentence = (
        f"{name} masih {how} pada {day}, tetapi tidak lagi dengan bunyi aslinya: yang berlaku "
        f"adalah bunyi dari {library.instrument(now.source_id, as_of)}, sejak {since}."
    )
    changed = next(v for v in versions if not is_original(v))
    if changed.source_id.split("/")[0] != now.source_id.split("/")[0]:
        what = "dihapus" if changed.status == "repealed" else "diubah"
        sentence += (
            f" Bunyi aslinya pertama kali {what} oleh "
            f"{library.instrument(changed.source_id, as_of)} sejak "
            f"{format_date(changed.valid_from)}."
        )
    return sentence


def notes_of(chunk: Chunk) -> list[tuple[str, str]]:
    """The notes under a version's text, as (ID of the ruling or clause, what it says)."""
    notes = chunk.text.partition(NOTES_HEADING)[2]
    return [match.groups() for match in map(NOTE.match, notes.split("\n")) if match]


def rulings_read(library: Library, chunk: Chunk, ayat: set[str]) -> list[str]:
    """Plain readings of the MK ruling points noted on this version, from the rulings' full
    text. A point that names an ayat is left out when the quoted lines are in other ayat; with
    no ayat given, every point is read."""
    found, meanings = [], set()
    for note_id, text in notes_of(chunk):
        if "/amar-" not in note_id:
            continue
        ruling = library.by_source.get(note_id)
        full = ruling[0].text if ruling else text
        about = ayat_of(full)
        if ayat and about and about not in ayat:
            continue
        meaning = meaning_of(full)
        if meaning in meanings:  # MK 19/PUU-IX/2011 sets the same reading in two points
            continue
        if meaning:
            meanings.add(meaning)
        found.append(reading(full, instrument_label(note_id)))
    return found


def as_ruled(library: Library, chunk: Chunk, text: str) -> str:
    """The quoted lines as they read after a ruling that strikes words from them, with a mark
    saying so. Told only beside the text that 'dapat' no longer applies, the model went on
    reading 'dapat memberikan' as optional. Rulings that set a reading are not written into the
    text: they are read out beside it (rulings_read)."""
    lines = text.split("\n")
    for note_id, note in notes_of(chunk):
        if "/amar-" not in note_id:
            continue
        ruling = library.by_source.get(note_id)
        target = struck(ruling[0].text if ruling else note)
        if target is None:
            continue
        ayat, words = target
        for i, line in enumerate(lines):
            changed = without(line, words) if line.startswith(f"({ayat})") else None
            if changed:
                by = instrument_label(note_id)
                effect = ": bukan lagi pilihan" if words == "dapat" else ""
                lines[i] = f"{changed} [kata “{words}” dihapus oleh {by}{effect}]"
    return "\n".join(lines)


def standing_notes(chunk: Chunk) -> list[str]:
    """Notes about the whole instrument, as written: UU 11/2020 conditionally unconstitutional,
    or a regulation that applies only as far as it fits the Perppu."""
    return [text for note_id, text in notes_of(chunk) if "/amar-" not in note_id]
