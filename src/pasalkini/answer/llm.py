"""Chat calls to the local model: one client with a timeout, output constrained to a JSON schema
and checked against the same Pydantic model."""

import time
from dataclasses import dataclass

import ollama
from pydantic import BaseModel, ValidationError

# Answers take under a minute; a request still open after this has hung (for example across a
# laptop sleep), and the caller can retry.
CLIENT = ollama.Client(timeout=300)


@dataclass(frozen=True)
class ChatOptions:
    model: str
    temperature: float = 0.0
    seed: int = 42
    num_ctx: int = 8192
    max_tokens: int = 1024
    think: bool = False


@dataclass
class Reply[T: BaseModel]:
    parsed: T | None  # None when the output does not validate against the schema
    raw: str
    prompt_tokens: int
    output_tokens: int
    seconds: float


def chat_json[T: BaseModel](
    options: ChatOptions, messages: list[dict], schema: type[T]
) -> Reply[T]:
    started = time.perf_counter()
    response = CLIENT.chat(
        model=options.model,
        messages=messages,
        format=schema.model_json_schema(),
        think=options.think,
        options={
            "temperature": options.temperature,
            "seed": options.seed,
            "num_ctx": options.num_ctx,
            "num_predict": options.max_tokens,
        },
    )
    raw = response.message.content
    try:
        parsed = schema.model_validate_json(raw)
    except ValidationError:
        parsed = None
    return Reply(
        parsed=parsed,
        raw=raw,
        prompt_tokens=response.prompt_eval_count or 0,
        output_tokens=response.eval_count or 0,
        seconds=time.perf_counter() - started,
    )
