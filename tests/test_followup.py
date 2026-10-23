"""Conversation memory: a follow-up becomes a question of its own before the pipeline sees it."""

from datetime import date

from fastapi.testclient import TestClient
from test_answer_pipeline import PICKS_OLD, ScriptedChat
from test_service import IN_2019, QUESTION, make_service

from pasalkini.answer.followup import FollowUp, Turn, read_follow_up
from pasalkini.answer.llm import ChatOptions, Reply
from pasalkini.api.main import create_app
from pasalkini.service import turn_of
from pasalkini.ui.render import conversation_html

TODAY = date(2026, 10, 1)
OPTIONS = ChatOptions("qwen3.5:4b")
EARLIER = Turn(
    "Berapa jam lembur maksimal?", "Paling banyak 3 jam sehari.", IN_2019, "pemilih_tanggal"
)


class Rewriter:
    """Answers the follow-up call with `reply`; anything else goes to `rest`."""

    def __init__(self, reply: FollowUp | None, rest=None):
        self.reply, self.rest, self.seen = reply, rest, []

    def __call__(self, options, messages, schema):
        if schema is FollowUp:
            self.seen.append(messages[-1]["content"])
            raw = self.reply.model_dump_json() if self.reply else "bukan JSON"
            return Reply(self.reply, raw, 10, 5, 0.0)
        return self.rest(options, messages, schema)


def test_without_a_conversation_the_question_is_not_touched():
    chat = Rewriter(FollowUp(lanjutan=True, pertanyaan="lain"))
    read = read_follow_up("Berapa jam lembur?", [], None, TODAY, chat, OPTIONS)
    assert read.question == "Berapa jam lembur?" and not read.rewritten and chat.seen == []


def test_a_follow_up_is_rewritten_and_keeps_the_date_of_the_turn_before():
    chat = Rewriter(FollowUp(lanjutan=True, pertanyaan="Berapa jam lembur maksimal seminggu?"))
    read = read_follow_up("seminggunya?", [EARLIER], None, TODAY, chat, OPTIONS)
    assert read.rewritten
    # The rewrite names no date: the turn before was about 1 June 2019, so this one is too.
    assert read.question == "Berapa jam lembur maksimal seminggu pada 1 Juni 2019?"
    assert "1. Tanya (1 Juni 2019): Berapa jam lembur maksimal?" in chat.seen[0]
    assert chat.seen[0].endswith("PERTANYAAN BARU: seminggunya?")


def test_a_follow_up_that_names_its_own_year_keeps_it():
    rewrite = "Berapa jam lembur maksimal dalam sehari pada tahun 2022?"
    chat = Rewriter(FollowUp(lanjutan=True, pertanyaan=rewrite))
    read = read_follow_up("kalau tahun 2022?", [EARLIER], None, TODAY, chat, OPTIONS)
    assert read.question == rewrite


def test_a_complete_question_or_an_unusable_reply_is_asked_as_typed():
    complete = Rewriter(FollowUp(lanjutan=False, pertanyaan="Berapa lama cuti melahirkan?"))
    read = read_follow_up("Berapa lama cuti melahirkan?", [EARLIER], None, TODAY, complete, OPTIONS)
    assert read.question == "Berapa lama cuti melahirkan?" and not read.rewritten
    broken = read_follow_up("seminggunya?", [EARLIER], None, TODAY, Rewriter(None), OPTIONS)
    assert broken.question == "seminggunya?" and not broken.rewritten


def test_the_app_answers_the_rewrite_and_says_how_it_read_the_follow_up(tmp_path):
    rest = ScriptedChat(selections=[PICKS_OLD])
    rewrite = "Berapa jam lembur maksimal seminggu?"
    service = make_service(tmp_path, Rewriter(FollowUp(lanjutan=True, pertanyaan=rewrite), rest))
    events = list(service.ask_events("seminggunya?", None, [EARLIER]))
    assert events[0] == ("stage", {"stage": "follow-up", "label": "Membaca pertanyaan lanjutan"})
    kind, payload = events[-1]
    assert kind == "answer"
    assert payload["asked_as"] == "Berapa jam lembur maksimal seminggu pada 1 Juni 2019?"
    assert payload["as_of"] == "2019-06-01"
    # The pipeline was asked the rewrite, never the bare follow-up.
    asked = [m[-1]["content"] for name, m in rest.calls if name == "Classification"]
    assert asked == [payload["asked_as"]]


def test_a_turn_keeps_no_personal_data_from_what_was_typed(tmp_path):
    payload = make_service(tmp_path).ask(QUESTION, IN_2019)
    turn = turn_of("Nama saya Budi Santoso. Berapa jam lembur maksimal?", payload)
    assert "Budi" not in turn.question and turn.as_of == IN_2019
    assert turn.as_of_source == "pemilih_tanggal"


def test_the_api_takes_the_conversation_so_far(tmp_path):
    rest = ScriptedChat(selections=[PICKS_OLD])
    rewrite = "Berapa jam lembur maksimal seminggu?"
    service = make_service(tmp_path, Rewriter(FollowUp(lanjutan=True, pertanyaan=rewrite), rest))
    client = TestClient(create_app(service, ui=False))
    earlier = {
        "question": "Berapa jam lembur maksimal?",
        "answer": "Paling banyak 3 jam sehari.",
        "as_of": "2019-06-01",
        "as_of_source": "date_picker",
    }
    body = client.post("/ask/json", json={"question": "seminggunya?", "history": [earlier]}).json()
    assert body["asked_as"].endswith("pada 1 Juni 2019?")


def test_earlier_turns_are_shown_in_short_and_escaped(tmp_path):
    payload = make_service(tmp_path).ask(QUESTION, IN_2019)
    shown = conversation_html([{"typed": "<b>lembur?</b>", "payload": payload}])
    assert '<div class="pk-you">&lt;b&gt;lembur?&lt;/b&gt;</div>' in shown
    assert "Menurut hukum pada 1 Juni 2019" in shown and "Sumber" not in shown
