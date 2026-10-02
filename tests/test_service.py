"""The service behind the API and the UI, with a scripted chat model and a five-chunk corpus."""

from datetime import date

import pytest
from test_answer_pipeline import (
    CHUNKS,
    COMPENSATION,
    CONFIG,
    FOUR,
    INDEX,
    NEW,
    OLD,
    PICKS_OLD,
    QUERY,
    SAID,
    THREE,
    TODAY,
    ScriptedChat,
)

from pasalkini.answer.pipeline import OUT_OF_SCOPE, Pipeline
from pasalkini.cache import AnswerCache
from pasalkini.privacy.log import QuestionLog
from pasalkini.service import MAX_QUESTION_CHARS, ModelUnavailable, Service
from pasalkini.sources import load_manifest
from pasalkini.temporal.model import Version
from pasalkini.tools.pesangon import CalculatorError, hitung_pesangon

QUESTION = "Berapa jam lembur maksimal?"
IN_2019 = date(2019, 6, 1)
VERSIONS = [
    Version(
        version_id=f"{chunk.provision_id}@{chunk.valid_from}",
        provision_id=chunk.provision_id,
        label="Pasal " + chunk.provision_id.rsplit("-", 1)[-1],
        source_id=chunk.source_id,
        text=chunk.text,
        valid_from=chunk.valid_from,
        valid_to=chunk.valid_to,
        status=chunk.status,
    )
    for chunk in CHUNKS
]


def make_service(tmp_path, chat=None, today=TODAY, **parts) -> Service:
    chat = chat if chat is not None else ScriptedChat(selections=[PICKS_OLD])
    pipeline = Pipeline(CONFIG, CHUNKS, INDEX, None, chat=chat, today=today)
    parts.setdefault("cache", AnswerCache(tmp_path / "answers.db"))
    parts.setdefault("log", QuestionLog(tmp_path / "logs"))
    return Service(
        pipeline,
        VERSIONS,
        load_manifest(),
        embed=lambda question: QUERY,
        today=lambda: today,
        **parts,
    )


def logged(service: Service) -> list[dict]:
    return [entry for path in sorted(service.log.directory.glob("*.jsonl")) for entry in read(path)]


def read(path) -> list[dict]:
    import json

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_an_answer_comes_back_as_the_answer_contract(tmp_path):
    payload = make_service(tmp_path).ask(QUESTION, IN_2019)
    assert payload["as_of"] == "2019-06-01" and payload["as_of_source"] == "date_picker"
    assert payload["as_of_text"] == "1 Juni 2019 (tanggal dari pemilih tanggal)"
    assert payload["intent"] == "explain" and payload["answer"] == SAID
    assert not payload["abstained"] and payload["confidence"] == "high"
    assert payload["citations"] == [
        {
            "source_id": OLD.source_id,
            "provision_id": "uu-13-2003/pasal-78",
            "title": OLD.title,
            "quote": "paling banyak 3 (tiga) jam",
            "valid_from": "2003-03-25",
            "valid_to": "2020-11-02",
        }
    ]
    assert payload["nearest"] == [] and payload["later"] == [] and payload["earlier"] == []
    assert "diubah sejak 2 November 2020" in payload["changed_since"][0]
    assert payload["looked_up"] and not payload["cached"] and payload["calculation"] is None
    assert set(payload["seconds"]) == {"understand", "retrieve", "select", "answer", "total"}


def test_the_same_question_about_the_same_date_is_answered_once(tmp_path):
    chat = ScriptedChat(selections=[PICKS_OLD, PICKS_OLD])
    service = make_service(tmp_path, chat)
    first = service.ask(QUESTION, IN_2019)
    calls = len(chat.calls)
    again = service.ask("  berapa jam lembur   MAKSIMAL? ", IN_2019)
    assert again["cached"] and again["answer"] == first["answer"]
    assert again["citations"] == first["citations"] and len(chat.calls) == calls
    other_date = service.ask(QUESTION, date(2019, 7, 1))
    assert not other_date["cached"] and len(chat.calls) > calls
    assert [entry["cached"] for entry in logged(service)] == [False, True, False]


def test_a_date_in_the_question_wins_over_the_date_picker(tmp_path):
    payload = make_service(tmp_path).ask("Berapa jam lembur maksimal pada 1 Juni 2019?", TODAY)
    assert payload["as_of"] == "2019-06-01" and payload["as_of_source"] == "question"


def test_a_question_with_personal_data_is_not_cached_and_is_logged_redacted(tmp_path):
    chat = ScriptedChat(selections=[PICKS_OLD, PICKS_OLD])
    service = make_service(tmp_path, chat)
    question = "Nama saya Budi Santoso, HP 081234567890. Berapa jam lembur maksimal?"
    first = service.ask(question, IN_2019)
    calls = len(chat.calls)
    second = service.ask(question, IN_2019)
    assert not first["cached"] and not second["cached"] and len(chat.calls) == 2 * calls
    assert len(service.cache) == 0
    # The model and the search get the redacted question too: nothing downstream sees the rest.
    redacted = "Nama saya [NAMA], HP [TELEPON]. Berapa jam lembur maksimal?"
    assert f"PERTANYAAN: {redacted}" in chat.named("Selection")[0][-1]["content"]
    sent = str(chat.calls)
    assert "Budi" not in sent and "081234567890" not in sent
    entry = logged(service)[0]
    assert entry["question"] == redacted
    assert entry["personal_data"] == {"nama": 1, "telepon": 1}
    kept = "".join(path.read_text(encoding="utf-8") for path in service.log.directory.iterdir())
    assert "Budi" not in kept and "081234567890" not in kept


def test_the_log_keeps_what_happened_and_not_what_was_answered(tmp_path):
    service = make_service(tmp_path)
    service.ask(QUESTION, IN_2019)
    (entry,) = logged(service)
    assert entry["question"] == QUESTION and entry["personal_data"] == {}
    assert entry["date_picker"] == "2019-06-01" and entry["as_of"] == "2019-06-01"
    assert entry["as_of_source"] == "date_picker" and entry["intent"] == "explain"
    assert entry["citations"] == [OLD.source_id] and not entry["abstained"]
    assert entry["error"] is None and "answer" not in entry and SAID not in str(entry)


def test_a_refusal_is_an_answer_too(tmp_path):
    service = make_service(tmp_path, ScriptedChat(intent="di_luar_cakupan"))
    payload = service.ask("Bagaimana pembagian harta gono-gini?")
    assert payload["abstained"] and payload["answer"] == OUT_OF_SCOPE
    assert payload["intent"] == "out_of_scope" and payload["as_of_source"] == "today"
    assert not payload["looked_up"] and payload["citations"] == [] and payload["referral"]


def test_stages_are_reported_as_they_start(tmp_path):
    events = list(make_service(tmp_path).ask_events(QUESTION, IN_2019))
    stages = [data["stage"] for kind, data in events if kind == "stage"]
    assert stages == ["understand", "retrieve", "select", "answer"]
    assert events[0] == ("stage", {"stage": "understand", "label": "Memahami pertanyaan"})
    kind, payload = events[-1]
    assert kind == "answer" and payload["answer"] == SAID
    assert [kind for kind, _ in events].count("answer") == 1


def test_a_cached_answer_has_no_stages(tmp_path):
    service = make_service(tmp_path)
    service.ask(QUESTION, IN_2019)
    events = list(service.ask_events(QUESTION, IN_2019))
    assert [kind for kind, _ in events] == ["answer"] and events[0][1]["cached"]


def test_a_model_server_that_does_not_answer_is_reported_as_such(tmp_path):
    def down(options, messages, schema):
        raise ConnectionError("Failed to connect to Ollama")

    service = make_service(tmp_path, down)
    with pytest.raises(ModelUnavailable, match="Ollama"):
        service.ask(QUESTION, IN_2019)
    (entry,) = logged(service)
    assert entry["error"] == "ConnectionError" and entry["question"] == QUESTION
    assert len(service.cache) == 0
    events = list(service.ask_events(QUESTION, IN_2019))
    assert events[-1][0] == "error" and events[-1][1]["status"] == 503
    assert not service.lock.locked()  # the next question can be asked


def test_an_empty_or_overlong_question_is_refused_before_any_work(tmp_path):
    chat = ScriptedChat()
    service = make_service(tmp_path, chat)
    with pytest.raises(ValueError, match="kosong"):
        service.ask("   ")
    with pytest.raises(ValueError, match="terlalu panjang"):
        service.ask("a" * (MAX_QUESTION_CHARS + 1))
    assert not chat.calls and logged(service) == []
    events = list(service.ask_events(" "))
    assert events == [("error", {"status": 422, "detail": "Pertanyaan kosong."})]


def test_an_answer_cut_short_by_the_model_is_not_cached(tmp_path):
    from pasalkini.answer.llm import Reply
    from pasalkini.answer.verify import Answer

    scripted = ScriptedChat(selections=[PICKS_OLD, PICKS_OLD])

    def cut(options, messages, schema):
        if schema is Answer:
            return Reply(None, '{"dasar": "paling', 10, 400, 0.0)
        return scripted(options, messages, schema)

    service = make_service(tmp_path, cut)
    service.ask(QUESTION, IN_2019)
    assert len(service.cache) == 0


def test_the_cache_is_left_when_a_new_wording_takes_effect(tmp_path):
    cache, chat = AnswerCache(tmp_path / "answers.db"), ScriptedChat(selections=[PICKS_OLD] * 2)
    before = make_service(tmp_path, chat, today=date(2020, 11, 1), cache=cache)
    after = make_service(tmp_path, chat, today=date(2020, 11, 2), cache=cache)
    assert before.law_as_of(date(2020, 11, 1)) == date(2003, 3, 25)
    assert after.law_as_of(date(2020, 11, 2)) == date(2020, 11, 2)
    assert before.ask(QUESTION, IN_2019)["changed_since"] == []
    assert not after.ask(QUESTION, IN_2019)["cached"]
    assert before.ask(QUESTION, IN_2019)["cached"]


def test_an_article_is_shown_as_it_stood_on_the_date(tmp_path):
    service = make_service(tmp_path)
    old = service.provision("uu-13-2003/pasal-78", IN_2019)
    assert old["exists_on_date"] and old["text"] == THREE and old["status"] == "in_force"
    assert old["source_id"] == OLD.source_id and old["valid_to"] == "2020-11-02"
    assert old["published_in"] == "UU 13/2003" and old["label"] == "UU 13/2003 Pasal 78"
    new = service.provision("uu-13-2003/pasal-78", date(2022, 1, 1))
    assert new["text"] == FOUR and new["source_id"] == NEW.source_id
    assert new["status"] == "conditional" and new["status_text"] == "berlaku bersyarat"
    # Both periods of the wording as one span, with the day its status changed.
    assert new["valid_from"] == "2020-11-02" and "bersyarat sejak 25 November 2021" in new["title"]


def test_an_article_that_did_not_exist_yet_says_when_it_began(tmp_path):
    service = make_service(tmp_path)
    early = service.provision(COMPENSATION.provision_id, IN_2019)
    assert not early["exists_on_date"] and early["first_valid_from"] == "2021-02-02"
    assert "belum berlaku pada 1 Juni 2019" in early["message"]
    assert service.provision("uu-13-2003/pasal-999", IN_2019) is None


def test_an_articles_history_carries_the_word_level_changes(tmp_path):
    found = make_service(tmp_path).history("uu-13-2003/pasal-78")
    assert found["label"] == "UU 13/2003 Pasal 78"
    assert found["timeline"].startswith("Riwayat UU 13/2003 Pasal 78:")
    first, second, third = found["versions"]
    assert first["diff"] is None and not first["same_text_as_previous"]
    assert first["validity"] == "berlaku 25 Maret 2003 s.d. 1 November 2020"
    assert second["published_in"] == "UU 11/2020"
    assert ("banyak 3 (tiga)", "-") in second["diff"] and ("lama 4 (empat)", "+") in second["diff"]
    assert third["same_text_as_previous"] and third["diff"] is None
    assert third["status"] == "conditional"
    assert make_service(tmp_path).history("uu-13-2003/pasal-999") is None


def test_a_law_is_shown_as_it_stood_on_the_date(tmp_path):
    service = make_service(tmp_path)
    law = service.law("uu-13-2003", IN_2019)
    assert law["name"] == "UU 13/2003" and law["as_of"] == "2019-06-01"
    assert [a["label"] for a in law["articles"]] == ["Pasal 78", "Pasal 79"]
    assert law["articles"][0]["text"] == THREE and not law["articles"][0]["amended"]
    later = service.law("uu-13-2003", date(2021, 1, 1), only=["78"])
    assert [a["text"] for a in later["articles"]] == [FOUR] and later["articles"][0]["amended"]
    assert service.law("pp-35-2021", IN_2019)["articles"] == []  # not yet in force
    assert service.law("uu-99-1999", IN_2019) is None


def test_the_laws_that_can_be_browsed_are_listed_with_their_articles(tmp_path):
    service = make_service(tmp_path)
    listed = service.instruments()
    assert [(i["id"], i["name"], i["articles"]) for i in listed] == [
        ("uu-13-2003", "UU 13/2003", 2),
        ("pp-35-2021", "PP 35/2021", 1),
    ]
    assert listed[0]["official_urls"] and listed[0]["title"]
    assert service.articles("uu-13-2003") == [
        {"provision_id": "uu-13-2003/pasal-78", "label": "Pasal 78"},
        {"provision_id": "uu-13-2003/pasal-79", "label": "Pasal 79"},
    ]


def test_the_calculator_gives_each_line_with_the_articles_it_rests_on(tmp_path):
    service = make_service(tmp_path)
    end = date(2024, 3, 1)
    reasons = service.reasons(end)
    reason = next(iter(reasons))
    result = service.severance(date(2018, 3, 1), end, 5_000_000, reason, leave_days=4)
    direct = hitung_pesangon(date(2018, 3, 1), end, 5_000_000, reason, sisa_cuti_hari=4)
    assert result["total"] == direct.total and result["service"] == "6 tahun 0 bulan"
    assert [line["amount"] for line in result["lines"]] == [line.amount for line in direct.lines]
    assert all(line["basis"] for line in result["lines"])
    assert result["as_of"] == "2024-03-01" and result["reason"].startswith(reasons[reason])
    cited = {source["source_id"] for source in result["sources"]}
    assert cited == {basis for line in result["lines"] for basis in line["basis"]}
    with pytest.raises(CalculatorError, match="tidak dikenal"):
        service.severance(date(2018, 3, 1), end, 5_000_000, "alasan-yang-tidak-ada")


def test_contract_compensation_cites_the_article_as_titled_in_the_corpus(tmp_path):
    result = make_service(tmp_path).pkwt_compensation(date(2022, 1, 1), date(2023, 7, 1), 6_000_000)
    assert result["total"] == 9_000_000 and result["lines"][0]["months_of_wage"] == 1.5
    titles = {source["source_id"]: source["title"] for source in result["sources"]}
    assert titles["pp-35-2021/pasal-16"] == "PP 35/2021 Pasal 16"
    assert titles["pp-35-2021/pasal-15"] == "pp-35-2021/pasal-15"  # not in this small corpus


def test_health_says_whether_questions_can_be_answered(tmp_path, monkeypatch):
    import ollama

    service = make_service(tmp_path)

    class Down:
        def __init__(self, timeout):
            pass

        def list(self):
            raise ConnectionError("Failed to connect to Ollama")

    monkeypatch.setattr(ollama, "Client", Down)
    health = service.health()
    assert health["status"] == "degraded" and health["model"]["reachable"] is False
    assert health["corpus"]["chunks"] == 5 and health["corpus"]["article_versions"] == 5
    assert health["corpus"]["law_as_of"] == "2021-11-25" and health["today"] == "2026-10-01"

    class Model:
        def __init__(self, name):
            self.model = name

    class Up(Down):
        def list(self):
            class Listed:
                models = [Model(CONFIG.chat_model), Model(CONFIG.embed_model)]

            return Listed()

    monkeypatch.setattr(ollama, "Client", Up)
    health = service.health()
    assert health["status"] == "ok" and health["model"]["chat"]["installed"]

    class Half(Down):
        def list(self):
            class Listed:
                models = [Model(CONFIG.chat_model)]

            return Listed()

    monkeypatch.setattr(ollama, "Client", Half)
    health = service.health()
    assert health["status"] == "degraded" and not health["model"]["embedding"]["installed"]


def test_a_question_is_traced_once_with_the_stages_under_it(tmp_path):
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from pasalkini.trace import Exporter

    memory = InMemorySpanExporter()
    service = make_service(tmp_path, exporter=Exporter("memory", SimpleSpanProcessor(memory)))
    service.ask("HP 081234567890. Berapa jam lembur maksimal?", IN_2019)
    sent = {s.name: s for s in memory.get_finished_spans()}
    assert set(sent) == {"ask", "understand", "retrieve", "select", "answer"}
    ask = sent["ask"]
    assert ask.attributes["input.value"] == "HP [TELEPON]. Berapa jam lembur maksimal?"
    assert ask.attributes["output.value"] == SAID
    assert ask.attributes["pasalkini.as_of"] == "2019-06-01"
    assert all(s.parent.span_id == ask.context.span_id for s in sent.values() if s is not ask)
    found = sent["retrieve"].attributes
    documents = {found[f"retrieval.documents.{n}.document.id"] for n in range(2)}
    assert documents == {OLD.source_id, "uu-13-2003/pasal-79"}
    assert sent["select"].attributes["pasalkini.passages"] == f'["{OLD.source_id}"]'
