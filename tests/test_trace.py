"""Spans: recorded only under `tracing`, nested as they were opened, redacted when exported."""

import pytest

from pasalkini.trace import (
    LLM,
    RETRIEVER,
    Exporter,
    note,
    open_inference,
    scrub,
    span,
    traced,
    tracing,
)


def test_spans_nest_as_they_were_opened():
    started = []
    with tracing("ask", lambda s, depth: started.append((s.name, depth)), input="q") as trace:
        with span("understand"):
            with span("chat: Classification", LLM, model="m"):
                note(output="{}")
            note(intent="jelaskan")
        with span("retrieve", RETRIEVER):
            pass
    root = trace.root
    assert root.name == "ask" and root.attributes == {"input": "q"}
    assert [child.name for child in root.children] == ["understand", "retrieve"]
    understand = root.children[0]
    assert understand.attributes == {"intent": "jelaskan"}
    assert understand.children[0].attributes == {"model": "m", "output": "{}"}
    assert started == [("ask", 0), ("understand", 1), ("chat: Classification", 2), ("retrieve", 1)]
    assert [s.name for s in root.walk()] == [
        "ask",
        "understand",
        "chat: Classification",
        "retrieve",
    ]
    assert all(s.ended is not None and s.seconds >= 0 for s in root.walk())


def test_without_tracing_a_span_is_not_kept_and_a_note_goes_nowhere():
    with span("select") as alone:
        note(passages=["x"])
    assert alone.attributes == {} and alone.children == []


def test_a_failing_span_keeps_the_error_and_the_trace_is_closed():
    with pytest.raises(ConnectionError):
        with tracing("ask") as trace:
            with span("understand"):
                raise ConnectionError("Ollama is not running")
    assert "Ollama is not running" in trace.root.children[0].error
    assert "Ollama is not running" in trace.root.error
    with span("later") as alone:  # the trace is no longer current
        pass
    assert alone not in trace.root.children


def test_a_traced_function_is_a_span():
    @traced("select")
    def select(n):
        note(picked=n)
        return n + 1

    with tracing("ask") as trace:
        assert select(2) == 3
    assert trace.root.children[0].name == "select"
    assert trace.root.children[0].attributes == {"picked": 2}


def test_text_is_redacted_and_capped_before_it_leaves():
    assert scrub("HP saya 081234567890") == "HP saya [TELEPON]"
    assert scrub(3) == 3 and scrub(True) is True
    assert scrub(["uu-13-2003/pasal-78"]) == '["uu-13-2003/pasal-78"]'
    assert len(scrub("a" * 30_000)) == 20_002


def test_attributes_take_the_names_phoenix_reads():
    with tracing("ask", input="NIK 3201234567890001, berapa pesangon?") as trace:
        messages = [{"role": "system", "content": "Kamu ..."}, {"role": "user", "content": "q"}]
        with span("chat: Answer", LLM, model="qwen3.5:4b", messages=messages) as call:
            call.attributes.update(output='{"answer": "x"}', prompt_tokens=10, output_tokens=5)
        with span("retrieve", RETRIEVER):
            note(documents=[("uu-13-2003/pasal-78", "UU 13/2003 Pasal 78")], skipped=None)
    root, llm, retrieve = trace.root.walk()
    assert open_inference(root) == {
        "openinference.span.kind": "CHAIN",
        "input.value": "NIK [NIK], berapa pesangon?",
    }
    assert open_inference(llm) == {
        "openinference.span.kind": "LLM",
        "llm.model_name": "qwen3.5:4b",
        "llm.input_messages.0.message.role": "system",
        "llm.input_messages.0.message.content": "Kamu ...",
        "llm.input_messages.1.message.role": "user",
        "llm.input_messages.1.message.content": "q",
        "output.value": '{"answer": "x"}',
        "llm.output_messages.0.message.role": "assistant",
        "llm.output_messages.0.message.content": '{"answer": "x"}',
        "llm.token_count.prompt": 10,
        "llm.token_count.completion": 5,
    }
    assert open_inference(retrieve) == {
        "openinference.span.kind": "RETRIEVER",
        "retrieval.documents.0.document.id": "uu-13-2003/pasal-78",
        "retrieval.documents.0.document.content": "UU 13/2003 Pasal 78",
    }


def test_a_trace_is_exported_as_one_tree_with_its_own_times():
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    memory = InMemorySpanExporter()
    exporter = Exporter("memory", SimpleSpanProcessor(memory))
    with tracing("ask", input="HP 081234567890") as trace:
        with span("understand"):
            with span("chat: Classification", LLM, model="m"):
                pass
        with pytest.raises(ValueError):
            with span("retrieve", RETRIEVER):
                raise ValueError("no index")
    exporter.export(trace)
    sent = {s.name: s for s in memory.get_finished_spans()}
    assert set(sent) == {"ask", "understand", "chat: Classification", "retrieve"}
    ask, understand, chat = sent["ask"], sent["understand"], sent["chat: Classification"]
    assert ask.parent is None
    assert understand.parent.span_id == ask.context.span_id
    assert chat.parent.span_id == understand.context.span_id
    assert len({s.context.trace_id for s in sent.values()}) == 1
    assert ask.attributes["input.value"] == "HP [TELEPON]"
    assert ask.resource.attributes["openinference.project.name"] == "pasalkini"
    assert ask.start_time == int(trace.root.started * 1e9)
    assert ask.end_time == int(trace.root.ended * 1e9)
    assert sent["retrieve"].status.status_code.name == "ERROR"
    assert ask.status.status_code.name == "OK"
    exporter.shutdown()
