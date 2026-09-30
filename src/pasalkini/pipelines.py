"""Named pipeline configurations. Every evaluation run records the full configuration it used."""

from pydantic import BaseModel, ConfigDict


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    description: str
    embed_model: str = "qwen3-embedding:0.6b"
    chat_model: str = "qwen3.5:4b"
    top_k: int = 5
    query_instruction: bool = False  # Qwen3-Embedding's recommended query prefix
    think: bool = False
    temperature: float = 0.0
    seed: int = 42
    num_ctx: int = 8192
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
    ]
}
