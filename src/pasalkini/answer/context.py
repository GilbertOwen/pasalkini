"""Choose the chunks the model sees.

- Articles the question names come first: the version that applied on the date, or for status
  and history questions every version up to it, with the MK rulings attached to them.
- Then the articles the calculator used, then the search results.
- For status and history questions, consecutive periods of the same wording (split only by a
  status change, such as a conditional ruling) are shown as one chunk over the whole span.
"""

from collections import defaultdict
from datetime import date, timedelta

from pasalkini.corpus import Chunk
from pasalkini.temporal.corpus import DatedChunk
from pasalkini.temporal.query import format_date

MAX_CONTEXT = 7  # about 5,000 prompt tokens at 2,500 characters a chunk
STATUS_WORDS = {"in_force": "berlaku", "conditional": "bersyarat", "repealed": "dihapus"}


def key(chunk: DatedChunk) -> tuple[str, str]:
    """One wording of one article. A source ID alone is not enough: one Perppu point can insert
    several articles."""
    return chunk.provision_id, chunk.source_id


def label(chunk: DatedChunk) -> str:
    """'UU 13/2003 Pasal 59' from 'UU 13/2003 Pasal 59 (berlaku …)'."""
    return chunk.title.split(" (")[0]


class Library:
    """The dated corpus, indexed for lookups by article and by source ID."""

    def __init__(self, chunks: list[DatedChunk]) -> None:
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

    chosen: dict[tuple[str, str], DatedChunk] = {}
    for chunk in first + [h for h in hits if isinstance(h, DatedChunk)]:
        chosen.setdefault(key(chunk), chunk)
    limit = min(MAX_CONTEXT, top_k + len({key(c) for c in first}))
    picked = list(chosen.values())[:limit]
    if history:
        picked = [merge_periods(library.periods(c, as_of)) for c in picked]
    return picked
