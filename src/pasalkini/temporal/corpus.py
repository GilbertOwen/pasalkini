"""Chunks for date-aware retrieval: one per article version, plus one per MK ruling point.

Each chunk carries the dates it applied, so retrieval can keep only what applied on a date.
The chunk's source_id is where its wording was published, the same IDs the evaluation labels use.
"""

import json
import re
from dataclasses import dataclass
from datetime import date

from pasalkini.corpus import Chunk, short_name
from pasalkini.ingest.models import ParsedDocument
from pasalkini.paths import PROCESSED_DIR
from pasalkini.sources import Kind, load_manifest
from pasalkini.temporal.model import Version
from pasalkini.temporal.query import format_date, validity
from pasalkini.temporal.rulings import abbreviate
from pasalkini.temporal.store import load_versions

MAX_NOTE_CHARS = 700  # the longest ruling point is 630 characters once its citations are short
NOTES_HEADING = "\n\nCatatan:\n"  # between a version's text and its notes


@dataclass(frozen=True)
class DatedChunk(Chunk):
    provision_id: str
    status: str  # in_force | conditional | repealed
    valid_from: date
    valid_to: date | None  # exclusive; None: still applies
    rulings: tuple[str, ...] = ()  # MK ruling points that condition this version

    def valid_on(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day < self.valid_to)


def instrument_name(instrument_id: str, names: dict[str, str]) -> str:
    """'UU 13/2003'; laws outside the manifest (e.g. uu-40-2004) are named from their id."""
    if instrument_id in names:
        return names[instrument_id]
    match = re.fullmatch(r"(uu|pp)-(\d+)-(\d{4})", instrument_id)
    return f"{match.group(1).upper()} {match.group(2)}/{match.group(3)}" if match else instrument_id


def version_chunk(version: Version, names: dict[str, str]) -> DatedChunk:
    status = {"conditional": "; bersyarat", "repealed": "; dihapus"}.get(version.status, "")
    name = instrument_name(version.instrument_id, names)
    title = f"{name} {version.label} ({validity(version)}{status})"
    # Rulings and status changes are shown with the text; deletion instructions are not needed.
    # A ruling point is mostly citation (the law's full title and gazette numbers); written out,
    # the part that says what the Court decided fell past the length limit.
    notes = [abbreviate(n) if "/amar-" in n else n for n in version.notes if n.startswith("[")]
    text = version.text
    if notes:
        shown = [n if len(n) <= MAX_NOTE_CHARS else n[:MAX_NOTE_CHARS] + " …" for n in notes]
        text += NOTES_HEADING + "\n".join(shown)
    return DatedChunk(
        source_id=version.source_id,
        instrument_id=version.instrument_id,
        title=title,
        text=text,
        page=0,
        provision_id=version.provision_id,
        status=version.status,
        valid_from=version.valid_from,
        valid_to=version.valid_to,
        rulings=tuple(version.rulings),
    )


def ruling_chunks(names: dict[str, str]) -> list[DatedChunk]:
    chunks = []
    for instrument in load_manifest().instruments:
        path = PROCESSED_DIR / f"{instrument.id}.json"
        if instrument.kind is not Kind.PUTUSAN_MK or instrument.in_force_on is None:
            continue
        if not path.exists():
            continue
        doc = ParsedDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for point in doc.amar:
            source_id = f"{instrument.id}/amar-{point.number}"
            spoken = format_date(instrument.in_force_on)
            title = f"{names[instrument.id]} amar {point.number} (diucapkan {spoken})"
            chunks.append(
                DatedChunk(
                    source_id=source_id,
                    instrument_id=instrument.id,
                    title=title,
                    text=point.text,
                    page=0,
                    provision_id=source_id,
                    status="in_force",
                    valid_from=instrument.in_force_on,
                    valid_to=None,
                )
            )
    return chunks


def load_dated_corpus() -> list[DatedChunk]:
    names = {i.id: short_name(i) for i in load_manifest().instruments if i.number}
    return [version_chunk(v, names) for v in load_versions()] + ruling_chunks(names)
