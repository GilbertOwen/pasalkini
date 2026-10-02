"""Build the search function a pipeline configuration asks for: dense, BM25, or both fused."""

from collections.abc import Callable

import numpy as np

from pasalkini.corpus import Chunk
from pasalkini.retrieve.dense import DenseIndex
from pasalkini.retrieve.hybrid import reciprocal_rank_fusion
from pasalkini.retrieve.lexical import BM25Index

Hits = list[tuple[Chunk, float]]
Search = Callable[[Callable[[Chunk], bool] | None], Hits]

# Candidates taken from each ranking before fusion. A question in everyday words ('kontrak saya
# habis', 'gaji sesuai UMR') ranks the right article well in one ranking and far down the other;
# with 20 candidates it then counted in one only, and lost to articles that were mediocre in
# both. On the reworded development questions 20 finds an expected source in the top 5 for 30 of
# 37 questions, 50 for 32; the original questions are unchanged at 34 of 37.
FUSION_POOL = 50


def make_search(
    retriever: str,
    k: int,
    dense: DenseIndex,
    query_vector: np.ndarray,
    lexical: BM25Index | None = None,
    query_text: str = "",
) -> Search:
    """A function of the date filter ('allowed') that returns the top-k chunks."""

    def search(allowed: Callable[[Chunk], bool] | None) -> Hits:
        if retriever == "dense":
            return dense.search(query_vector, k, allowed)
        if lexical is None:
            raise ValueError(f"retriever '{retriever}' needs a BM25 index")
        if retriever == "bm25":
            return lexical.search(query_text, k, allowed)
        pool = max(k, FUSION_POOL)
        return reciprocal_rank_fusion(
            [dense.search(query_vector, pool, allowed), lexical.search(query_text, pool, allowed)],
            k,
        )

    return search
