"""The judge: how a verdict on the key's points becomes a grade, and how agreement is counted."""

from datetime import date

from pasalkini.answer.llm import ChatOptions, Reply
from pasalkini.evals.judge import (
    Ban,
    Point,
    Verdict,
    agreement,
    grade_of,
    judge_item,
    judge_message,
    kappa,
    split_key,
)
from pasalkini.evals.metrics import ItemResult
from pasalkini.evals.schema import EvalItem

OPTIONS = ChatOptions("test")


def item(points, should_abstain=False):
    return EvalItem(
        id="lembur-001",
        pair_id="lembur",
        question="Berapa jam lembur paling banyak dalam sehari?",
        as_of=date(2019, 6, 1),
        category="should_abstain" if should_abstain else "temporal_trap",
        topic="lembur",
        expected_points=points,
        should_abstain=should_abstain,
        source="draft",
        split="dev",
        review="needed",
    )


def result(answer="Paling banyak 3 jam sehari.", abstained=False):
    return ItemResult(
        id="lembur-001",
        category="temporal_trap",
        split="dev",
        as_of=date(2019, 6, 1),
        question="Berapa jam lembur paling banyak dalam sehari?",
        retrieved=[],
        context_ids=[],
        retrieval_ms=0.0,
        answer=answer,
        abstained=abstained,
    )


KEY = [
    "Paling banyak 3 jam sehari dan 14 jam seminggu (UU 13/2003 Pasal 78)",
    "Tidak berlaku bagi sektor usaha atau pekerjaan tertentu",
    "Tidak memakai batas 4 jam dari UU Cipta Kerja",
    "Catatan: aturan ini berubah pada 2 November 2020",
]


def verdict(*statuses, bans=(), wrong=None):
    return Verdict(
        poin=[Point(nomor=n, status=s) for n, s in enumerate(statuses, start=1)],
        larangan=[Ban(nomor=n, dilanggar=b) for n, b in enumerate(bans, start=1)],
        keliru=wrong,
    )


def says(parsed):
    """A chat model that returns this verdict and records what it was shown."""
    seen = []

    def chat(options, messages, schema):
        seen.append(messages[-1]["content"])
        return Reply(parsed, parsed.model_dump_json(), 10, 5, 0.0)

    chat.seen = seen
    return chat


def test_the_key_is_split_into_points_to_state_and_things_not_to_do():
    points, bans = split_key(item(KEY))
    # A point whose content is a 'no' stays a point; the note for the key's reader is dropped.
    assert points == KEY[:2] and bans == [KEY[2]]
    shown = judge_message(item(KEY), "Paling banyak 3 jam.")
    assert "POIN KUNCI:\n1. Paling banyak 3 jam" in shown and "LARANGAN:\n1. Tidak memakai" in shown
    assert "TANGGAL: 1 Juni 2019" in shown and "Catatan" not in shown


def test_a_verdict_becomes_a_grade_by_the_main_point_and_by_what_goes_against_the_key():
    assert grade_of(verdict("ada", "tidak_disebut")) == ("correct", "")
    assert grade_of(verdict("ada", "bertentangan"))[0] == "partly"
    assert grade_of(verdict("ada", "ada", bans=[True])) == ("partly", "larangan 1 dilanggar")
    assert grade_of(verdict("ada", wrong="Menurut Pasal 99."))[0] == "partly"
    assert grade_of(verdict("bertentangan", "ada"))[0] == "wrong"
    assert grade_of(verdict("tidak_disebut", "ada")) == ("partly", "poin utama tidak disebut")
    assert grade_of(verdict("tidak_disebut", "tidak_disebut"))[0] == "wrong"


def test_refusals_are_graded_by_code_and_answers_by_the_model():
    refused = judge_item(item(KEY, should_abstain=True), result(abstained=True), None, OPTIONS)
    assert (refused.grade, refused.by) == ("correct", "code")
    declined = judge_item(item(KEY), result(abstained=True), None, OPTIONS)
    assert (declined.grade, declined.by) == ("wrong", "code")  # should have answered
    chat = says(verdict("ada", "tidak_disebut", bans=[False]))
    answered = judge_item(item(KEY), result(), chat, OPTIONS)
    assert (answered.grade, answered.by) == ("correct", "model")
    assert "JAWABAN:\nPaling banyak 3 jam sehari." in chat.seen[0]


def test_plain_rag_cannot_abstain_so_the_model_reads_its_answer_to_a_question_to_refuse():
    plain = result("Pasal 372 KUHP.", abstained=None)
    key = ["Menyatakan pertanyaan pidana di luar cakupan", "Menyarankan menghubungi advokat"]
    judged = judge_item(
        item(key, should_abstain=True), plain, says(verdict("tidak_disebut")), OPTIONS
    )
    assert (judged.grade, judged.by) == ("wrong", "model")


def test_agreement_counts_same_grades_and_corrects_for_chance():
    reference = {"a": "correct", "b": "correct", "c": "partly", "d": "wrong", "e": "wrong"}
    judged = {
        "a": "correct",
        "b": "partly",
        "c": "partly",
        "d": "wrong",
        "e": "correct",
        "f": "wrong",
    }
    lines = agreement(reference, judged)
    assert lines[:3] == [
        "- Answers graded by both: 5",
        "- Same grade: 60% (3/5)",
        "- Same on correct or not: 60% (3/5)",
    ]
    assert lines[3].startswith("- Cohen's kappa: 0.4")
    assert "| correct | 1 | 1 | 0 |" in lines
    same = [("correct", "correct"), ("wrong", "wrong")]
    assert kappa(same) == 1.0 and kappa([]) is None
    assert kappa([("correct", "correct")] * 3) is None  # one grade only: chance explains it all
