"""The Phase 2 answer step: a short JSON answer with source IDs, no checks. The baseline and the
retrieval ablations use it; the Phase 5 pipeline is in pasalkini.answer.pipeline."""

from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, Field

from pasalkini.answer.llm import ChatOptions, chat_json
from pasalkini.corpus import Chunk

SYSTEM_PROMPT = (
    "Kamu adalah asisten informasi hukum ketenagakerjaan Indonesia. "
    "Jawab pertanyaan hanya berdasarkan kutipan peraturan di bagian KONTEKS. "
    "Tulis jawaban singkat dalam bahasa Indonesia yang mudah dipahami. "
    "Di field citations, tulis ID sumber (yang ada di dalam tanda kurung siku) dari setiap "
    "kutipan yang kamu pakai, persis seperti tertulis. "
    "Jika konteks tidak cukup untuk menjawab, katakan demikian. "
    "Ini informasi hukum, bukan nasihat hukum."
)


class BaselineAnswer(BaseModel):
    answer: str = Field(description="Jawaban singkat dalam bahasa Indonesia")
    citations: list[str] = Field(description="ID sumber dari KONTEKS yang dipakai")


@dataclass
class Generation:
    answer: BaselineAnswer | None
    raw: str
    prompt_tokens: int
    output_tokens: int
    seconds: float
    truncated_chunks: int


def build_user_message(
    question: str, as_of: date | None, chunks: list[Chunk], max_chars: int
) -> tuple[str, int]:
    """The user turn: date (when it comes from the date picker), question, then the context.

    Returns the message and how many chunks were cut to max_chars.
    """
    truncated = 0
    context = []
    for chunk in chunks:
        text = chunk.text
        if len(text) > max_chars:
            text = text[:max_chars] + " …"
            truncated += 1
        context.append(f"[{chunk.source_id}] {chunk.title}\n{text}")
    parts = []
    if as_of is not None:
        parts.append(f"Tanggal yang relevan: {as_of.isoformat()}")
    parts.append(f"Pertanyaan: {question}")
    parts.append("KONTEKS:\n\n" + "\n\n".join(context))
    return "\n\n".join(parts), truncated


def generate(
    model: str,
    question: str,
    as_of: date | None,
    chunks: list[Chunk],
    *,
    max_chars: int,
    think: bool,
    temperature: float,
    seed: int,
    num_ctx: int,
    max_tokens: int = 1024,
) -> Generation:
    user, truncated = build_user_message(question, as_of, chunks, max_chars)
    reply = chat_json(
        ChatOptions(model, temperature, seed, num_ctx, max_tokens, think),
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        BaselineAnswer,
    )
    return Generation(
        answer=reply.parsed,
        raw=reply.raw,
        prompt_tokens=reply.prompt_tokens,
        output_tokens=reply.output_tokens,
        seconds=reply.seconds,
        truncated_chunks=truncated,
    )
