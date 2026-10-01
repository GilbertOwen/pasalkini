"""The Phase 5 pipeline with a scripted chat model: every path without a GPU."""

from datetime import date

import numpy as np

from pasalkini.answer.context import merge_periods
from pasalkini.answer.llm import Reply
from pasalkini.answer.pipeline import NO_VERIFIED_SOURCE, OUT_OF_SCOPE, Pipeline
from pasalkini.answer.understand import Classification
from pasalkini.answer.verify import Answer, Citation
from pasalkini.pipelines import CONFIGS
from pasalkini.retrieve.dense import DenseIndex
from pasalkini.temporal.corpus import DatedChunk

TODAY = date(2026, 10, 1)


def dated(source_id, provision_id, text, start, end=None, status="in_force", title=""):
    return DatedChunk(
        source_id=source_id,
        instrument_id=provision_id.split("/")[0],
        title=title or f"UU 13/2003 Pasal 78 ({start})",
        text=text,
        page=0,
        provision_id=provision_id,
        status=status,
        valid_from=date.fromisoformat(start),
        valid_to=date.fromisoformat(end) if end else None,
    )


THREE = "waktu kerja lembur hanya dapat dilakukan paling banyak 3 (tiga) jam dalam 1 (satu) hari"
FOUR = "waktu kerja lembur hanya dapat dilakukan paling lama 4 (empat) jam dalam 1 (satu) hari"
OLD = dated("uu-13-2003/pasal-78", "uu-13-2003/pasal-78", THREE, "2003-03-25", "2020-11-02")
NEW = dated("uu-11-2020/pasal-81/angka-22", "uu-13-2003/pasal-78", FOUR, "2020-11-02", "2021-11-25")
NEW_RULED = dated(
    "uu-11-2020/pasal-81/angka-22",
    "uu-13-2003/pasal-78",
    FOUR,
    "2021-11-25",
    status="conditional",
)
REST = dated(
    "uu-13-2003/pasal-79", "uu-13-2003/pasal-79", "istirahat mingguan 1 hari", "2003-03-25"
)
COMPENSATION = dated(
    "pp-35-2021/pasal-16",
    "pp-35-2021/pasal-16",
    "uang kompensasi diberikan dengan ketentuan sebagai berikut",
    "2021-02-02",
    title="PP 35/2021 Pasal 16",
)
CHUNKS = [OLD, NEW, NEW_RULED, REST, COMPENSATION]
# The search ranks the rest-day article first, so a named article must be put ahead of it.
INDEX = DenseIndex(
    model="test",
    chunks=CHUNKS,
    vectors=np.array([[0.8, 0.2], [0.8, 0.2], [0.8, 0.2], [1.0, 0.0], [0.1, 0.9]], np.float32),
    fingerprint="test",
)
QUERY = np.array([1.0, 0.0], dtype=np.float32)
CONFIG = CONFIGS["pasalkini"].model_copy(update={"retriever": "dense"})


class ScriptedChat:
    def __init__(self, intent="jelaskan", answers=(), facts=None):
        self.intent, self.answers, self.facts = intent, list(answers), facts
        self.calls: list[tuple[str, list[dict]]] = []

    def __call__(self, options, messages, schema):
        self.calls.append((schema.__name__, messages))
        if schema is Classification:
            parsed = Classification(intent=self.intent, rujukan="LBH")
        elif schema is Answer:
            parsed = self.answers.pop(0)
        else:
            parsed = schema.model_validate(self.facts)
        return Reply(parsed, parsed.model_dump_json(), 10, 5, 0.0)


def says(*citations: tuple[str, str], abstain=False) -> Answer:
    return Answer(
        answer="Paling banyak 3 jam sehari.",
        citations=[Citation(source_id=s, quote=q) for s, q in citations],
        confidence="tinggi",
        abstain=abstain,
    )


def run(chat, question="Berapa jam lembur maksimal?", day=date(2019, 6, 1)):
    return Pipeline(CONFIG, CHUNKS, INDEX, None, chat=chat, today=TODAY).run(question, day, QUERY)


def test_a_verified_answer_is_shown_with_what_changed_later():
    chat = ScriptedChat(answers=[says((OLD.source_id, "paling banyak 3 (tiga) jam"))])
    outcome = run(chat)
    assert not outcome.abstained and not outcome.retried
    assert [c.source_id for c in outcome.citations] == [OLD.source_id]
    assert NEW.source_id not in [c.source_id for c in outcome.context]  # did not apply in 2019
    assert "diubah sejak 2 November 2020" in outcome.changed_since[0]


def test_a_misquote_is_repaired_once():
    chat = ScriptedChat(
        answers=[
            says((OLD.source_id, "paling banyak 3 jam sehari")),  # not the text's words
            says((OLD.source_id, "paling banyak 3 (tiga) jam")),
        ]
    )
    outcome = run(chat)
    assert outcome.retried and outcome.first_problems and not outcome.abstained
    repair = chat.calls[-1][1][-1]["content"]
    assert "kutipan tidak ditemukan" in repair


def test_an_answer_without_a_verifiable_citation_abstains():
    wrong = says((NEW.source_id, "paling lama 4 (empat) jam"))  # not in the 2019 context
    outcome = run(ScriptedChat(answers=[wrong, wrong]))
    assert outcome.abstained and outcome.answer == NO_VERIFIED_SOURCE
    assert outcome.dropped == [NEW.source_id]


def test_out_of_scope_is_refused_without_searching():
    chat = ScriptedChat(intent="di_luar_cakupan")
    outcome = run(chat, "Bagaimana pembagian harta gono-gini?")
    assert outcome.abstained and outcome.answer == OUT_OF_SCOPE and outcome.referral == "LBH"
    assert [name for name, _ in chat.calls] == ["Classification"]


def test_a_named_article_comes_before_the_search_results():
    chat = ScriptedChat(answers=[says((OLD.source_id, "paling banyak 3 (tiga) jam"))])
    outcome = run(chat, "Apa isi Pasal 78 UU 13/2003?")
    assert outcome.context[0].source_id == OLD.source_id
    assert outcome.context[1].source_id == REST.source_id


def test_history_questions_see_each_wording_once_over_its_whole_span():
    chat = ScriptedChat(
        intent="riwayat", answers=[says((OLD.source_id, "paling banyak 3 (tiga) jam"))]
    )
    outcome = run(chat, "Apa yang berubah pada Pasal 78 UU 13/2003?", TODAY)
    ids = [c.source_id for c in outcome.context]
    assert ids.count(NEW.source_id) == 1 and OLD.source_id in ids
    merged = next(c for c in outcome.context if c.source_id == NEW.source_id)
    assert merged.valid_from == date(2020, 11, 2) and merged.status == "conditional"
    assert outcome.changed_since == []  # a history answer already covers the changes


def test_merge_periods_names_the_status_change():
    merged = merge_periods([NEW, NEW_RULED])
    assert merged.title == (
        "UU 13/2003 Pasal 78 (berlaku sejak 2 November 2020; bersyarat sejak 25 November 2021)"
    )


def test_the_calculator_supplies_the_amount_and_its_article():
    chat = ScriptedChat(
        intent="hitung",
        facts={"jenis": "kompensasi_pkwt", "lama_tahun": 0, "lama_bulan": 6, "upah_bulanan": 0},
        answers=[says((COMPENSATION.source_id, "uang kompensasi diberikan dengan ketentuan"))],
    )
    question = "Kontrak PKWT saya 6 bulan dengan upah Rp4.000.000 berakhir. Berapa kompensasinya?"
    outcome = run(chat, question, date(2022, 3, 15))
    assert outcome.calculation.result.total == 2_000_000
    assert COMPENSATION.source_id in [c.source_id for c in outcome.context]
    prompt = chat.calls[-1][1][-1]["content"]
    assert "HASIL HITUNGAN" in prompt and "Rp2.000.000" in prompt
