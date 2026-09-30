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
    ]
}


def load_chunks(config: PipelineConfig) -> list[Chunk]:
    if config.corpus == "versions":
        from pasalkini.temporal.corpus import load_dated_corpus

        return load_dated_corpus()
    from pasalkini.corpus import load_corpus

    return load_corpus()
