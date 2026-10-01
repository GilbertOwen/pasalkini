"""Combine rankings, and rewrite everyday words into the legal terms the texts use."""

import re

from pasalkini.corpus import Chunk
from pasalkini.sources import Topics


def reciprocal_rank_fusion(
    rankings: list[list[tuple[Chunk, float]]], k: int, constant: int = 60
) -> list[tuple[Chunk, float]]:
    """Reciprocal Rank Fusion: score = sum of 1 / (constant + rank) over the rankings.

    Ranks, not raw scores, are combined, so cosine similarities and BM25 scores need no scaling.
    Chunks are identified by position in the corpus (id()), since several versions can share a
    source ID.
    """
    scores: dict[int, float] = {}
    by_key: dict[int, Chunk] = {}
    for ranking in rankings:
        for rank, (chunk, _) in enumerate(ranking, start=1):
            key = id(chunk)
            by_key[key] = chunk
            scores[key] = scores.get(key, 0.0) + 1.0 / (constant + rank)
    ordered = sorted(scores.items(), key=lambda item: -item[1])[:k]
    return [(by_key[key], score) for key, score in ordered]


def expand_query(question: str, topics: Topics) -> str:
    """Append the legal name of every topic whose everyday words appear in the question.

    'Saya dipecat, apa hak saya?' gains 'Pemutusan hubungan kerja (PHK)', which is how the
    regulations say it.
    """
    lowered = question.lower()
    extra = []
    for topic in topics.topics:
        if any(re.search(rf"\b{re.escape(s)}\b", lowered) for s in topic.synonyms):
            extra.append(topic.name)
    return question if not extra else f"{question}\n{'; '.join(extra)}"
