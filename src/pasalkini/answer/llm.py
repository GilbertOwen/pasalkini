"""Chat calls: output constrained to a JSON schema and checked against the same Pydantic model.

The local model (Ollama) by default. A model whose name starts with 'gemini' goes to Google's
Gemini API instead, with the key from the GEMINI_API_KEY environment variable. Everything the
pipeline checks is checked the same way whichever model answers.
"""

import os
import time
from dataclasses import dataclass

import ollama
from pydantic import BaseModel, ValidationError

from pasalkini.trace import LLM, span

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


def is_gemini(model: str) -> bool:
    return model.startswith("gemini")


def unload(model: str) -> None:
    """Free the model, so that the next call loads it afresh. At temperature 0 the same prompt
    can still get a different answer from a server that has been running for a while (seen on
    2026-10-01: one refusal became a calculation between two runs of the same code, and came
    back after a reload). An evaluation run therefore starts from a fresh load."""
    if is_gemini(model):
        return  # nothing is loaded on this machine
    CLIENT.generate(model=model, keep_alive=0)


def chat_json[T: BaseModel](
    options: ChatOptions, messages: list[dict], schema: type[T]
) -> Reply[T]:
    if is_gemini(options.model):
        return gemini_json(options, messages, schema)
    started = time.perf_counter()
    with span(f"chat: {schema.__name__}", LLM, model=options.model, messages=messages) as call:
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
        call.attributes.update(
            output=raw,
            prompt_tokens=response.prompt_eval_count or 0,
            output_tokens=response.eval_count or 0,
            valid_json=parsed is not None,
        )
    return Reply(
        parsed=parsed,
        raw=raw,
        prompt_tokens=response.prompt_eval_count or 0,
        output_tokens=response.eval_count or 0,
        seconds=time.perf_counter() - started,
    )


class GeminiUnavailable(ConnectionError):
    """No key, or the Gemini API refused or failed the call. A ConnectionError, so the app
    reports it as a model that cannot be reached."""


_gemini_client = None


def gemini_client():
    global _gemini_client
    if _gemini_client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise GeminiUnavailable("GEMINI_API_KEY belum diisi")
        from google import genai

        _gemini_client = genai.Client(api_key=key)
    return _gemini_client


def gemini_contents(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Ollama-style messages as Gemini's: the system prompt apart, 'assistant' as 'model'."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system") or None
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
        if m["role"] != "system"
    ]
    return system, contents


def gemini_json[T: BaseModel](
    options: ChatOptions, messages: list[dict], schema: type[T], client=None
) -> Reply[T]:
    from google.genai import errors, types

    started = time.perf_counter()
    system, contents = gemini_contents(messages)
    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=options.temperature,
        seed=options.seed,
        max_output_tokens=options.max_tokens,
        response_mime_type="application/json",
        response_json_schema=schema.model_json_schema(),
        # The lowest level the fast models allow: the checks, not the model's thinking, are
        # what keeps an answer to its sources.
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
    )
    with span(f"chat: {schema.__name__}", LLM, model=options.model, messages=messages) as call:
        try:
            response = (client or gemini_client()).models.generate_content(
                model=options.model, contents=contents, config=config
            )
        except errors.APIError as error:
            raise GeminiUnavailable(f"Gemini: {error}") from error
        raw = response.text or ""
        try:
            parsed = schema.model_validate_json(raw)
        except ValidationError:
            parsed = None
        usage = response.usage_metadata
        prompt_tokens = (usage.prompt_token_count or 0) if usage else 0
        output_tokens = (usage.candidates_token_count or 0) if usage else 0
        call.attributes.update(
            output=raw,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            valid_json=parsed is not None,
        )
    return Reply(
        parsed=parsed,
        raw=raw,
        prompt_tokens=prompt_tokens,
        output_tokens=output_tokens,
        seconds=time.perf_counter() - started,
    )
