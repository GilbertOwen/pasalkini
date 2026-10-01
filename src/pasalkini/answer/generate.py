"""Generate an answer from retrieved chunks with a local Ollama model (structured JSON output)."""

import time
from dataclasses import dataclass
from datetime import date

import ollama
from pydantic import BaseModel, Field, ValidationError

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
    started = time.perf_counter()
    response = ollama.chat(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        format=BaselineAnswer.model_json_schema(),
        think=think,
        options={
            "temperature": temperature,
            "seed": seed,
            "num_ctx": num_ctx,
            "num_predict": max_tokens,
        },
    )
    seconds = time.perf_counter() - started
    raw = response.message.content
    try:
        answer = BaselineAnswer.model_validate_json(raw)
    except ValidationError:
        answer = None
    return Generation(
        answer=answer,
        raw=raw,
        prompt_tokens=response.prompt_eval_count or 0,
        output_tokens=response.eval_count or 0,
        seconds=seconds,
        truncated_chunks=truncated,
    )
