"""Spans: what each stage of answering a question did, and how long it took.

`with span("retrieve"):` records a span when it runs under `with tracing(...)`, and does nothing
otherwise, so the pipeline, the evaluation runner and the tests run the same with or without it.
The app uses the spans for two things:

- to tell a waiting user which stage is running (`on_start`);
- to show a question's path through the pipeline in Arize Phoenix, or any OpenTelemetry
  collector, when PASALKINI_TRACE_ENDPOINT is set (`Exporter`). Every text is redacted before it
  leaves the process.
"""

import functools
import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from pasalkini.privacy.redact import redact

# The span kinds Phoenix draws differently (OpenInference).
CHAIN, LLM, RETRIEVER, TOOL, EMBEDDING = "CHAIN", "LLM", "RETRIEVER", "TOOL", "EMBEDDING"
PROJECT = "pasalkini"
MAX_ATTRIBUTE_CHARS = 20_000  # a prompt with seven articles is about 15,000 characters


@dataclass
class Span:
    name: str
    kind: str = CHAIN
    attributes: dict[str, object] = field(default_factory=dict)
    started: float = 0.0  # seconds since the epoch
    ended: float | None = None
    error: str | None = None
    children: list["Span"] = field(default_factory=list)

    @property
    def seconds(self) -> float:
        return (self.ended if self.ended is not None else time.time()) - self.started

    def walk(self) -> Iterator["Span"]:
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass
class Trace:
    on_start: Callable[[Span, int], None] | None = None  # called with the span and its depth
    root: Span | None = None
    open: list[Span] = field(default_factory=list)  # the spans not yet closed, outermost first


_TRACE: ContextVar[Trace | None] = ContextVar("pasalkini_trace", default=None)


@contextmanager
def span(name: str, kind: str = CHAIN, **attributes: object) -> Iterator[Span]:
    current = Span(name, kind, dict(attributes), started=time.time())
    trace = _TRACE.get()
    if trace is not None:
        if trace.open:
            trace.open[-1].children.append(current)
        trace.open.append(current)
        if trace.on_start is not None:
            trace.on_start(current, len(trace.open) - 1)
    try:
        yield current
    except BaseException as error:
        current.error = repr(error)
        raise
    finally:
        current.ended = time.time()
        if trace is not None:
            trace.open.pop()


@contextmanager
def tracing(
    name: str, on_start: Callable[[Span, int], None] | None = None, **attributes: object
) -> Iterator[Trace]:
    """Record every span opened inside, under one root span."""
    trace = Trace(on_start)
    token = _TRACE.set(trace)
    try:
        with span(name, **attributes) as root:
            trace.root = root
            yield trace
    finally:
        _TRACE.reset(token)


def note(**attributes: object) -> None:
    """Add to the innermost open span, if one is being recorded."""
    trace = _TRACE.get()
    if trace is not None and trace.open:
        trace.open[-1].attributes.update(attributes)


def traced(name: str, kind: str = CHAIN) -> Callable:
    """Decorator: the function's calls are spans."""

    def wrap(function: Callable) -> Callable:
        @functools.wraps(function)
        def inner(*args, **kwargs):
            with span(name, kind):
                return function(*args, **kwargs)

        return inner

    return wrap


def scrub(value: object) -> str | int | float | bool:
    """A span attribute as OpenTelemetry accepts it: a scalar, with text redacted and capped."""
    if isinstance(value, bool | int | float):
        return value
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = redact(text).text
    return text if len(text) <= MAX_ATTRIBUTE_CHARS else text[:MAX_ATTRIBUTE_CHARS] + " …"


def open_inference(recorded: Span) -> dict[str, str | int | float | bool]:
    """The span's attributes under the names Phoenix reads (OpenInference conventions). What has
    no such name is kept as 'pasalkini.<name>'."""
    out: dict[str, str | int | float | bool] = {"openinference.span.kind": recorded.kind}
    names = {
        "input": "input.value",
        "output": "output.value",
        "prompt_tokens": "llm.token_count.prompt",
        "output_tokens": "llm.token_count.completion",
    }
    for key, value in recorded.attributes.items():
        if value is None:
            continue
        if key == "messages":  # what the model was sent
            for i, message in enumerate(value):
                out[f"llm.input_messages.{i}.message.role"] = message["role"]
                out[f"llm.input_messages.{i}.message.content"] = scrub(message["content"])
        elif key == "documents":  # what a search returned: (ID, title)
            for i, (source_id, title) in enumerate(value):
                out[f"retrieval.documents.{i}.document.id"] = source_id
                out[f"retrieval.documents.{i}.document.content"] = scrub(title)
        elif key == "model":
            prefix = "embedding" if recorded.kind == EMBEDDING else "llm"
            out[f"{prefix}.model_name"] = scrub(value)
        elif key == "output" and recorded.kind == LLM:
            out["output.value"] = scrub(value)
            out["llm.output_messages.0.message.role"] = "assistant"
            out["llm.output_messages.0.message.content"] = scrub(value)
        else:
            out[names.get(key, f"pasalkini.{key}")] = scrub(value)
    return out


class Exporter:
    """Sends finished traces to an OpenTelemetry collector over OTLP/HTTP. Phoenix listens at
    http://localhost:6006/v1/traces. Needs the 'tracing' extra (`uv sync --extra tracing`)."""

    def __init__(self, endpoint: str, processor=None) -> None:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        if processor is None:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        resource = Resource.create({"service.name": PROJECT, "openinference.project.name": PROJECT})
        self.endpoint = endpoint
        self.provider = TracerProvider(resource=resource)
        self.provider.add_span_processor(processor)
        self.tracer = self.provider.get_tracer(PROJECT)

    def export(self, trace: Trace) -> None:
        if trace.root is not None:
            self._emit(trace.root, None)

    def _emit(self, recorded: Span, parent) -> None:
        from opentelemetry.trace import Status, StatusCode, set_span_in_context

        sent = self.tracer.start_span(
            recorded.name,
            context=parent,
            attributes=open_inference(recorded),
            start_time=int(recorded.started * 1e9),
        )
        if recorded.error:
            sent.set_status(Status(StatusCode.ERROR, recorded.error))
        else:
            sent.set_status(Status(StatusCode.OK))
        context = set_span_in_context(sent)
        for child in recorded.children:
            self._emit(child, context)
        sent.end(end_time=int((recorded.ended or time.time()) * 1e9))

    def shutdown(self) -> None:
        self.provider.shutdown()
