"""Turn parsed documents into passages ('chunks') for retrieval.

One chunk per unit that can be cited:
- an article of a regulation ('uu-13-2003/pasal-59');
- an amendment point with the articles it quotes ('perppu-2-2022/pasal-81/angka-15');
- a point of an MK ruling ('mk-168-puu-xxi-2023/amar-2').

The chunk ID is the source ID used by the evaluation labels.
"""

import hashlib
import json
from dataclasses import asdict, dataclass

from pasalkini.ingest.models import ParsedDocument
from pasalkini.paths import PROCESSED_DIR
from pasalkini.sources import Instrument, Kind, load_manifest

KIND_NAMES = {
    Kind.UU: "UU",
    Kind.PERPPU: "Perppu",
    Kind.PP: "PP",
    Kind.PERMEN: "Permenaker",
    Kind.PUTUSAN_MK: "Putusan MK",
}


@dataclass(frozen=True)
class Chunk:
    source_id: str
    instrument_id: str
    title: str  # 'UU 13/2003 Pasal 59'
    text: str
    page: int

    @property
    def text_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def short_name(instrument: Instrument) -> str:
    if instrument.kind is Kind.PUTUSAN_MK:
        return f"Putusan MK {instrument.number}"
    return f"{KIND_NAMES[instrument.kind]} {instrument.number}/{instrument.year}"


def chunks_of(doc: ParsedDocument, instrument: Instrument) -> list[Chunk]:
    name = short_name(instrument)
    chunks = []
    for article in doc.articles:
        if not article.points:
            chunks.append(
                Chunk(
                    article.source_id,
                    doc.instrument_id,
                    f"{name} {article.label}",
                    article.full_text(),
                    article.page_start,
                )
            )
            continue
        for point in article.points:
            parts = [point.instruction]
            parts += [f"{quoted.label}\n{quoted.full_text()}" for quoted in point.articles]
            chunks.append(
                Chunk(
                    point.source_id,
                    doc.instrument_id,
                    f"{name} {article.label} angka {point.number}",
                    "\n".join(p for p in parts if p),
                    point.page_start,
                )
            )
    for point in doc.amar:
        chunks.append(
            Chunk(
                f"{doc.instrument_id}/amar-{point.number}",
                doc.instrument_id,
                f"{name} amar {point.number}",
                point.text,
                0,
            )
        )
    return [c for c in chunks if c.text.strip()]


def load_corpus() -> list[Chunk]:
    """All chunks from data/processed, in manifest order."""
    chunks = []
    for instrument in load_manifest().instruments:
        path = PROCESSED_DIR / f"{instrument.id}.json"
        if instrument.status != "active" or not path.exists():
            continue
        doc = ParsedDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))
        chunks += chunks_of(doc, instrument)
    return chunks


def corpus_fingerprint(chunks: list[Chunk]) -> str:
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk.source_id.encode())
        digest.update(chunk.text_hash.encode())
    return digest.hexdigest()[:16]


def to_dicts(chunks: list[Chunk]) -> list[dict]:
    return [asdict(c) for c in chunks]
