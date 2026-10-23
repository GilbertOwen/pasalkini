"""Gemini as the chat model, with a fake client: no key, no network, no cost."""

from types import SimpleNamespace

import pytest
from google.genai import errors, types
from test_answer_pipeline import CHUNKS, INDEX
from test_service import IN_2019, QUESTION, make_service

from pasalkini.answer import llm
from pasalkini.answer.llm import ChatOptions, GeminiUnavailable, gemini_contents, gemini_json
from pasalkini.answer.pipeline import Pipeline
from pasalkini.answer.understand import Classification
from pasalkini.pipelines import CONFIGS
from pasalkini.service import ModelUnavailable

GEMINI = CONFIGS["pasalkini-gemini"]
OPTIONS = ChatOptions("gemini-3.5-flash-lite", 0.0, 42, 8192, 200)
MESSAGES = [
    {"role": "system", "content": "Pilih satu intent."},
    {"role": "user", "content": "Contoh?"},
    {"role": "assistant", "content": '{"intent": "jelaskan"}'},
    {"role": "user", "content": "Berapa jam lembur?"},
]


class FakeGemini:
    def __init__(self, text='{"intent": "jelaskan"}', error=None):
        self.text, self.error, self.calls = text, error, []
        self.models = self

    def generate_content(self, *, model, contents, config):
        self.calls.append((model, contents, config))
        if self.error is not None:
            raise self.error
        usage = SimpleNamespace(prompt_token_count=40, candidates_token_count=6)
        return SimpleNamespace(text=self.text, usage_metadata=usage)


def test_the_conversation_is_sent_in_geminis_form():
    system, contents = gemini_contents(MESSAGES)
    assert system == "Pilih satu intent."
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    assert contents[-1]["parts"] == [{"text": "Berapa jam lembur?"}]


def test_a_reply_is_held_to_the_same_schema_as_the_local_models():
    fake = FakeGemini()
    reply = gemini_json(OPTIONS, MESSAGES, Classification, client=fake)
    assert reply.parsed == Classification(intent="jelaskan")
    assert (reply.prompt_tokens, reply.output_tokens) == (40, 6)
    model, _, config = fake.calls[0]
    assert model == "gemini-3.5-flash-lite"
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == Classification.model_json_schema()
    assert config.system_instruction == "Pilih satu intent."
    assert config.temperature == 0.0 and config.max_output_tokens == 200
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    # A reply outside the schema is counted as invalid, as with the local model.
    assert gemini_json(OPTIONS, MESSAGES, Classification, FakeGemini("tidak")).parsed is None


def test_a_refused_call_or_a_missing_key_is_a_model_that_cannot_be_reached(monkeypatch):
    refused = errors.APIError(403, {"error": {"message": "API key not valid"}})
    with pytest.raises(GeminiUnavailable, match="API key not valid"):
        gemini_json(OPTIONS, MESSAGES, Classification, FakeGemini(error=refused))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(llm, "_gemini_client", None)
    with pytest.raises(GeminiUnavailable, match="GEMINI_API_KEY"):
        gemini_json(OPTIONS, MESSAGES, Classification)
    assert issubclass(GeminiUnavailable, ConnectionError)


def test_a_gemini_model_name_goes_to_gemini_and_nothing_is_unloaded(monkeypatch):
    sent = []
    monkeypatch.setattr(llm, "gemini_json", lambda o, m, s: sent.append(o.model) or "reply")
    assert llm.chat_json(OPTIONS, MESSAGES, Classification) == "reply"
    assert sent == ["gemini-3.5-flash-lite"]
    llm.unload("gemini-3.5-flash-lite")  # would fail if it reached Ollama: nothing runs here


def test_the_gemini_configuration_changes_only_the_chat_model():
    local = CONFIGS["pasalkini"].model_dump(exclude={"name", "description", "chat_model"})
    assert GEMINI.model_dump(exclude={"name", "description", "chat_model"}) == local
    assert GEMINI.chat_model.startswith("gemini") and GEMINI.embed_model == "qwen3-embedding:0.6b"


def test_the_app_says_which_model_wrote_the_answer_and_why_gemini_failed(tmp_path):
    def no_key(options, messages, schema):
        raise GeminiUnavailable("GEMINI_API_KEY belum diisi")

    service = make_service(tmp_path, no_key)
    service.pipeline = Pipeline(GEMINI, CHUNKS, INDEX, None, chat=no_key)
    service.config = GEMINI
    with pytest.raises(ModelUnavailable, match="Periksa GEMINI_API_KEY"):
        service.ask(QUESTION, IN_2019)
    assert service.answered_by == "Gemini (gemini-3.5-flash-lite, lewat internet)"
    local = make_service(tmp_path / "local")
    assert local.ask(QUESTION, IN_2019)["answered_by"] == "qwen3.5:4b (lokal)"
