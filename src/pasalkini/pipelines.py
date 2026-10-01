"""Named pipeline configurations. Every evaluation run records the full configuration it used."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from pasalkini.corpus import Chunk


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    # documents: one chunk per article or amendment point, as published (Phase 2)
    # versions: one chunk per article version with its validity dates (Phase 3)
    corpus: Literal["documents", "versions"] = "documents"
    date_filter: bool = False  # keep only chunks that applied on the question's date
    history_cues: bool = False  # 'apa yang berubah', 'masih berlaku': search all versions to date
    retriever: Literal["dense", "bm25", "hybrid"] = "dense"  # hybrid: RRF of dense and BM25
    rewrite_query: bool = False  # add legal terms for everyday words (sources/topics.yaml)
    chunk_headers: bool = False  # embed 'title + text' instead of the text alone
    embed_model: str = "qwen3-embedding:0.6b"
    chat_model: str = "qwen3.5:4b"
    top_k: int = 5
    query_instruction: bool = False  # Qwen3-Embedding's recommended query prefix
    think: bool = False
    temperature: float = 0.0
    seed: int = 42
    num_ctx: int = 8192  # chat model context
    embed_num_ctx: int = 4096  # the longest chunk is about 2,000 tokens
    max_chars_per_chunk: int = 2500  # longer chunks are cut in the prompt, never in the index
    # Caps runaway generations: under enforced JSON a small model can loop until its context is
    # full, at about 10 tokens/s. A capped answer is invalid JSON and is counted as such.
    max_answer_tokens: int = 1024
    # baseline: the Phase 2 answer step (short JSON with source IDs, nothing checked)
    # verified: the Phase 5 pipeline (pasalkini.answer.pipeline): question classified, articles
    #   the question names added, quotes checked in code, calculator for amounts
    # agent: the model chooses what to look up with tools (pasalkini.answer.agent), then the
    #   same answer step and checks
    answer_mode: Literal["baseline", "verified", "agent"] = "baseline"


CONFIGS: dict[str, PipelineConfig] = {
    c.name: c
    for c in [
        PipelineConfig(
            name="baseline",
            description=(
                "Plain RAG: dense search over every version of every article with dates "
                "ignored; qwen3.5:4b answers from the top 5 chunks."
            ),
        ),
        PipelineConfig(
            name="baseline-instruct",
            description="As baseline, with the Qwen3-Embedding query instruction.",
            query_instruction=True,
        ),
        PipelineConfig(
            name="versions",
            description=(
                "Ablation: one chunk per article version with its validity in the title, "
                "but no date filter."
            ),
            corpus="versions",
        ),
        PipelineConfig(
            name="temporal",
            description=(
                "Date-aware RAG: one chunk per article version; only versions that applied on "
                "the question's date are ranked (all versions up to it for questions about "
                "change or status)."
            ),
            corpus="versions",
            date_filter=True,
            history_cues=True,
        ),
        *[
            PipelineConfig(
                name=f"temporal-{suffix}",
                description=f"Ablation: temporal with {what}.",
                corpus="versions",
                date_filter=True,
                history_cues=True,
                **options,
            )
            for suffix, what, options in [
                ("bm25", "BM25 instead of dense search", {"retriever": "bm25"}),
                ("hybrid", "dense + BM25 fused by RRF", {"retriever": "hybrid"}),
                ("rewrite", "query rewriting", {"rewrite_query": True}),
                ("headers", "titles embedded with the text", {"chunk_headers": True}),
                (
                    "hybrid-rewrite",
                    "hybrid search and query rewriting",
                    {"retriever": "hybrid", "rewrite_query": True},
                ),
                (
                    "hybrid-headers",
                    "hybrid search and embedded titles",
                    {"retriever": "hybrid", "chunk_headers": True},
                ),
                (
                    "hybrid-headers-rewrite",
                    "hybrid search, embedded titles and query rewriting",
                    {"retriever": "hybrid", "chunk_headers": True, "rewrite_query": True},
                ),
            ]
        ],
        PipelineConfig(
            name="pasalkini",
            description=(
                "Phase 5 pipeline: the model classifies the question and rules read its date; "
                "date-aware hybrid search plus the articles the question names; the answer "
                "quotes its sources word for word and code checks every citation (one repair, "
                "then abstain); severance and PKWT compensation are computed in code."
            ),
            corpus="versions",
            date_filter=True,
            retriever="hybrid",
            answer_mode="verified",
        ),
        PipelineConfig(
            name="pasalkini-agent",
            description=(
                "Agent: rules read the date; the model picks one tool per step (search with "
                "its own query, an article's history, the calculator), at most four steps, "
                "then the same answer step and citation check as pasalkini."
            ),
            corpus="versions",
            date_filter=True,
            retriever="hybrid",
            answer_mode="agent",
        ),
    ]
}


def load_chunks(config: PipelineConfig) -> list[Chunk]:
    if config.corpus == "versions":
        from pasalkini.temporal.corpus import load_dated_corpus

        return load_dated_corpus()
    from pasalkini.corpus import load_corpus

    return load_corpus()
