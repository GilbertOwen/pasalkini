"""Dense retrieval with an Ollama embedding model and brute-force cosine similarity.

The corpus is a few hundred chunks, so a NumPy matrix product is instant and needs no vector
database. Vectors are cached by (model, text hash) in data/processed/index/, so only new or
changed chunks are embedded again.
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import ollama

from pasalkini.corpus import Chunk, corpus_fingerprint
from pasalkini.paths import PROCESSED_DIR

INDEX_DIR = PROCESSED_DIR / "index"
BATCH_SIZE = 16

# Qwen3-Embedding expects an instruction on queries (not on documents); see its model card.
QUERY_INSTRUCTION = (
    "Instruct: Given a question about Indonesian labor law, retrieve the legal provisions "
    "that answer it\nQuery: "
)


def _slug(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def _normalise(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


def embed_texts(model: str, texts: list[str], num_ctx: int, unload: bool = False) -> np.ndarray:
    """Embed in batches. unload=True frees the model's memory after the last batch, so the chat
    model has the GPU to itself (6 GB is not enough for both)."""
    vectors = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        last = start + BATCH_SIZE >= len(texts)
        response = ollama.embed(
            model=model,
            input=batch,
            truncate=True,
            options={"num_ctx": num_ctx},
            keep_alive=0 if unload and last else None,
        )
        vectors += response.embeddings
    return _normalise(np.asarray(vectors, dtype=np.float32))


class EmbeddingCache:
    """Vectors keyed by text hash, one file per embedding model."""

    def __init__(self, model: str) -> None:
        self.model = model
        self.path = INDEX_DIR / f"{_slug(model)}.cache.npz"
        self.vectors: dict[str, np.ndarray] = {}
        if self.path.exists():
            data = np.load(self.path)
            self.vectors = dict(zip(data["hashes"].tolist(), data["vectors"], strict=True))

    def vectors_for(self, chunks: list[Chunk], num_ctx: int) -> tuple[np.ndarray, int]:
        """Vectors in chunk order, and how many had to be embedded now."""
        missing = [c for c in chunks if c.text_hash not in self.vectors]
        if missing:
            fresh = embed_texts(self.model, [c.text for c in missing], num_ctx)
            for chunk, vector in zip(missing, fresh, strict=True):
                self.vectors[chunk.text_hash] = vector
            self.save()
        return np.stack([self.vectors[c.text_hash] for c in chunks]), len(missing)

    def save(self) -> None:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        hashes = list(self.vectors)
        np.savez(
            self.path, hashes=np.array(hashes), vectors=np.stack([self.vectors[h] for h in hashes])
        )


@dataclass
class DenseIndex:
    model: str
    chunks: list[Chunk]
    vectors: np.ndarray  # (n_chunks, dims), L2-normalised
    fingerprint: str
    newly_embedded: int = 0

    @classmethod
    def build(cls, model: str, chunks: list[Chunk], num_ctx: int = 4096) -> "DenseIndex":
        vectors, new = EmbeddingCache(model).vectors_for(chunks, num_ctx)
        return cls(model, chunks, vectors, corpus_fingerprint(chunks), new)

    def embed_query(self, text: str, instruction: bool, num_ctx: int = 4096) -> np.ndarray:
        return self.embed_queries([text], instruction, num_ctx)[0]

    def embed_queries(
        self, texts: list[str], instruction: bool, num_ctx: int = 4096, unload: bool = False
    ) -> np.ndarray:
        queries = [QUERY_INSTRUCTION + t if instruction else t for t in texts]
        return embed_texts(self.model, queries, num_ctx, unload=unload)

    def search(
        self,
        query_vector: np.ndarray,
        k: int,
        allowed: Callable[[Chunk], bool] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Top-k chunks by cosine similarity. `allowed` filters chunks before ranking."""
        scores = self.vectors @ query_vector
        if allowed is not None:
            mask = np.array([allowed(c) for c in self.chunks])
            scores = np.where(mask, scores, -np.inf)
        order = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in order if np.isfinite(scores[i])]
