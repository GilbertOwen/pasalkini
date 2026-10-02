"""The agent loop with a scripted chat model: each tool, the refusal, and the step limit."""

from datetime import date

import pytest
from test_answer_pipeline import (
    BEFORE_AND_NOW,
    CHUNKS,
    COMPENSATION,
    CONFIG,
    INDEX,
    NEW,
    OLD,
    PICKS_OLD,
    QUERY,
    SAID,
    TODAY,
    picks,
    says,
)

from pasalkini.answer.agent import MAX_STEPS, Action, Agent
from pasalkini.answer.llm import Reply
from pasalkini.answer.pipeline import OUT_OF_SCOPE
from pasalkini.answer.verify import Answer, Comparison, Selection
from pasalkini.retrieve.dense import DenseIndex


class Script:
    def __init__(self, actions, selections=(), answers=(), facts=None):
        self.actions, self.selections = list(actions), list(selections)
        self.answers, self.facts = list(answers), facts
        self.calls: list[tuple[str, list[dict]]] = []

    def __call__(self, options, messages, schema):
        self.calls.append((schema.__name__, list(messages)))
        if schema is Action:
            parsed = self.actions.pop(0)
        elif schema is Selection:
            parsed = self.selections.pop(0) if self.selections else picks()
        elif schema is Answer:
            parsed = self.answers.pop(0) if self.answers else says(SAID)
        elif schema is Comparison:
            parsed = BEFORE_AND_NOW
        else:
            parsed = schema.model_validate(self.facts)
        return Reply(parsed, parsed.model_dump_json(), 10, 5, 0.0)


@pytest.fixture(autouse=True)
def embedded_on_cpu(monkeypatch):
    """The search tool embeds its query on the CPU; here it gets a fixed vector."""
    seen = []

    def embed_query(self, text, instruction, num_ctx=4096, on_cpu=False):
        seen.append((text, on_cpu))
        return QUERY

    monkeypatch.setattr(DenseIndex, "embed_query", embed_query)
    return seen


def run(chat, question="Berapa jam lembur maksimal?", day=date(2019, 6, 1)):
    return Agent(CONFIG, CHUNKS, INDEX, None, chat=chat, today=TODAY).run(question, day, QUERY)


CITES_OLD = PICKS_OLD


def test_the_agent_searches_with_its_own_query_then_answers(embedded_on_cpu):
    chat = Script(
        [Action(aksi="cari", kueri="waktu kerja lembur"), Action(aksi="jawab")], [CITES_OLD]
    )
    outcome = run(chat)
    assert outcome.steps == ["cari"] and embedded_on_cpu == [("waktu kerja lembur", True)]
    ids = [c.source_id for c in outcome.context]
    assert OLD.source_id in ids and NEW.source_id not in ids  # only what applied in 2019
    shown_to_model = chat.calls[1][1][-1]["content"]
    assert shown_to_model.startswith("HASIL cari:") and f"[{OLD.source_id}]" in shown_to_model
    assert [c.source_id for c in outcome.citations] == [OLD.source_id]


def test_the_history_tool_shows_every_wording_and_old_ones_are_shown_as_earlier():
    chat = Script(
        [Action(aksi="riwayat", pasal="Pasal 78 UU 13/2003"), Action(aksi="jawab")], [CITES_OLD]
    )
    outcome = run(chat, "Apa yang berubah pada aturan lembur?", TODAY)
    assert [c.source_id for c in outcome.context] == [OLD.source_id, NEW.source_id]
    assert outcome.timeline.startswith("Riwayat UU 13/2003 Pasal 78:")
    assert outcome.understanding.intent == "riwayat" and not outcome.abstained
    # The old wording it quoted is compared with the one that applied, and is not a source.
    assert [c.source_id for c in outcome.citations] == [NEW.source_id]
    assert [p.source_id for p in outcome.earlier] == [OLD.source_id]


def test_a_refusal_ends_the_run_without_an_answer_call():
    chat = Script([Action(aksi="tolak")])
    outcome = run(chat, "Bagaimana cara mendaftarkan hak cipta lagu?")
    assert outcome.abstained and outcome.answer == OUT_OF_SCOPE
    assert [name for name, _ in chat.calls] == ["Action"]


def test_an_agent_that_answers_without_looking_still_gets_one_search(embedded_on_cpu):
    outcome = run(Script([Action(aksi="jawab")], [CITES_OLD]))
    assert outcome.steps == [] and OLD.source_id in [c.source_id for c in outcome.context]
    assert embedded_on_cpu == []  # the question's own vector is used


def test_the_agent_stops_after_the_step_limit():
    searches = [Action(aksi="cari", kueri=f"lembur {n}") for n in range(MAX_STEPS + 3)]
    chat = Script(searches, [CITES_OLD])
    outcome = run(chat)
    assert outcome.steps == ["cari"] * MAX_STEPS
    assert [name for name, _ in chat.calls].count("Action") == MAX_STEPS


def test_the_agent_stops_when_it_repeats_an_action():
    chat = Script([Action(aksi="cari", kueri="lembur")] * 3, [CITES_OLD])
    outcome = run(chat)
    assert outcome.steps == ["cari"] and not outcome.abstained


def test_the_calculator_tool_brings_its_articles_into_the_context():
    chat = Script(
        [Action(aksi="hitung"), Action(aksi="jawab")],
        [picks((COMPENSATION.source_id, "uang kompensasi diberikan dengan ketentuan"))],
        facts={"jenis": "kompensasi_pkwt", "lama_tahun": 0, "lama_bulan": 6, "upah_bulanan": 0},
    )
    question = "Kontrak PKWT saya 6 bulan dengan upah Rp4.000.000 berakhir. Berapa kompensasinya?"
    outcome = run(chat, question, date(2022, 3, 15))
    assert outcome.calculation.result.total == 2_000_000
    assert outcome.understanding.intent == "hitung"
    assert [c.source_id for c in outcome.context] == [COMPENSATION.source_id]
    assert outcome.answer.startswith("Menurut hitungan program, uang kompensasi PKWT-nya Rp2.000")
