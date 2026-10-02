"""The answer pipeline with a scripted chat model: every path without a GPU."""

from dataclasses import replace
from datetime import date

import numpy as np

from pasalkini.answer.context import Library, history_of, merge_periods, status_sentence
from pasalkini.answer.llm import Reply
from pasalkini.answer.pipeline import (
    DISPUTE_REFERRAL,
    LATER_PROMPT,
    NO_BASIS,
    NO_VERIFIED_SOURCE,
    NOT_FOUND,
    OUT_OF_SCOPE,
    OUT_OF_SCOPE_REFERRAL,
    Pipeline,
    shown_passages,
)
from pasalkini.answer.understand import Classification
from pasalkini.answer.verify import Answer, Citation, Comparison, Selection, check_selection
from pasalkini.pipelines import CONFIGS
from pasalkini.retrieve.dense import DenseIndex
from pasalkini.sources import Topics
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
SAID = "Paling banyak 3 jam sehari."


class ScriptedChat:
    """Replies in order: the question's kind, the facts for the calculator, the quotes picked
    (none once the script runs out, as when later law is searched), and the answer written (the
    same short answer unless the test scripts others)."""

    def __init__(self, intent="jelaskan", selections=(), answers=(), facts=None, comparisons=()):
        self.intent, self.facts = intent, facts
        self.selections, self.answers = list(selections), list(answers)
        self.comparisons = list(comparisons)
        self.calls: list[tuple[str, list[dict]]] = []

    def __call__(self, options, messages, schema):
        self.calls.append((schema.__name__, list(messages)))
        if schema is Classification:
            parsed = Classification(intent=self.intent)
        elif schema is Selection:
            parsed = self.selections.pop(0) if self.selections else picks()
        elif schema is Answer:
            parsed = self.answers.pop(0) if self.answers else says(SAID)
        elif schema is Comparison:
            parsed = self.comparisons.pop(0) if self.comparisons else BEFORE_AND_NOW
        else:
            parsed = schema.model_validate(self.facts)
        return Reply(parsed, parsed.model_dump_json(), 10, 5, 0.0)

    def named(self, schema: str) -> list[list[dict]]:
        return [messages for name, messages in self.calls if name == schema]


def picks(*citations: tuple[str, str]) -> Selection:
    return Selection(kutipan=[Citation(source_id=s, quote=q) for s, q in citations])


def says(text: str, **fields) -> Answer:
    return Answer(**{"dasar": None, "batasan": None, "answer": text, **fields})


BEFORE_AND_NOW = Comparison(
    lama="Lembur paling banyak 3 jam sehari", sekarang="Lembur paling lama 4 jam sehari."
)
COMPARED = (
    "Bunyi lama: Lembur paling banyak 3 jam sehari. Bunyi yang berlaku pada 1 Oktober 2026: "
    "Lembur paling lama 4 jam sehari."
)
PICKS_OLD = picks((OLD.source_id, "paling banyak 3 (tiga) jam"))
PICKS_NEW = picks((NEW.source_id, "paling lama 4 (empat) jam"))


def run(chat, question="Berapa jam lembur maksimal?", day=date(2019, 6, 1)):
    return Pipeline(CONFIG, CHUNKS, INDEX, None, chat=chat, today=TODAY).run(question, day, QUERY)


def test_a_verified_answer_is_shown_with_what_changed_later():
    chat = ScriptedChat(selections=[PICKS_OLD])
    outcome = run(chat)
    assert not outcome.abstained and not outcome.retried and not outcome.rewritten
    assert outcome.answer == SAID
    assert [c.source_id for c in outcome.citations] == [OLD.source_id]
    assert NEW.source_id not in [c.source_id for c in outcome.context]  # did not apply in 2019
    assert "diubah sejak 2 November 2020" in outcome.changed_since[0]
    shown = outcome.display()
    assert shown.startswith("Menurut hukum yang berlaku pada 1 Juni 2019 (tanggal dari pemilih")
    assert '[uu-13-2003/pasal-78]: "paling banyak 3 (tiga) jam"' in shown


def test_the_answer_is_written_from_the_selected_passages_alone():
    chat = ScriptedChat(selections=[PICKS_OLD])
    run(chat)
    selecting, answering = chat.named("Selection")[0], chat.named("Answer")[0]
    assert "istirahat mingguan" in selecting[-1]["content"]  # the whole context
    given = answering[-1]["content"]
    assert THREE in given and "istirahat mingguan" not in given
    assert "KUTIPAN:\n\n1. UU 13/2003 Pasal 78" in given


def test_abbreviations_in_a_question_are_spelled_out_for_the_model():
    topics = Topics(topics=[], abbreviations={"PKWTT": "perjanjian kerja waktu tidak tertentu"})
    chat = ScriptedChat(selections=[PICKS_OLD])
    pipeline = Pipeline(CONFIG, CHUNKS, INDEX, None, topics, chat=chat, today=TODAY)
    pipeline.run("Berapa jam lembur maksimal untuk PKWTT?", date(2019, 6, 1), QUERY)
    spelled = "ISTILAH: PKWTT = perjanjian kerja waktu tidak tertentu"
    assert spelled in chat.named("Selection")[0][-1]["content"]
    assert spelled in chat.named("Answer")[0][-1]["content"]
    assert topics.spelled_out("Berapa lama kontrak PKWT?") is None  # another abbreviation


def test_a_misquote_is_repaired_once():
    wrong = picks((OLD.source_id, "paling banyak 5 (lima) jam sehari"))  # the text says 3
    chat = ScriptedChat(selections=[wrong, PICKS_OLD])
    outcome = run(chat)
    assert outcome.retried and outcome.first_problems and not outcome.abstained
    repair = chat.named("Selection")[-1][-1]["content"]
    assert "kutipan tidak ditemukan" in repair


def test_a_selection_with_nothing_verifiable_abstains_without_an_answer_call():
    wrong = picks((NEW.source_id, "paling lama 4 (empat) jam"))  # not in the 2019 context
    chat = ScriptedChat(selections=[wrong, wrong])
    outcome = run(chat)
    assert outcome.abstained and outcome.answer == NO_VERIFIED_SOURCE
    assert outcome.dropped == [NEW.source_id] and not chat.named("Answer")


def test_selecting_nothing_is_not_repaired_and_later_law_is_searched_before_abstaining():
    chat = ScriptedChat(selections=[picks()])
    outcome = run(chat)
    assert outcome.abstained and outcome.answer == NOT_FOUND
    asked = [messages[0]["content"] for messages in chat.named("Selection")]
    assert len(asked) == 2 and asked[1] == LATER_PROMPT and not chat.named("Answer")
    # Later law: articles that did not exist on the date, not later wordings of ones that did.
    later = chat.named("Selection")[1][-1]["content"]
    assert "[pp-35-2021/pasal-16]" in later and NEW.source_id not in later


def test_a_rule_that_began_after_the_date_is_reported_as_not_yet_in_force():
    began_later = picks((COMPENSATION.source_id, "uang kompensasi diberikan dengan ketentuan"))
    chat = ScriptedChat(selections=[picks(), began_later])
    outcome = run(chat, "Apakah pekerja kontrak berhak uang kompensasi saat kontrak berakhir?")
    assert not outcome.abstained and not outcome.citations
    assert outcome.answer == (
        "Saya tidak menemukan ketentuan tentang hal ini di antara peraturan yang berlaku pada "
        "1 Juni 2019. Ketentuan yang mengaturnya dalam sumber PasalKini, PP 35/2021 Pasal 16, "
        "baru berlaku sejak 2 Februari 2021, jadi belum berlaku pada tanggal itu."
    )
    shown = outcome.display()
    assert 'Aturan yang berlaku kemudian:\n- PP 35/2021 Pasal 16 [pp-35-2021/pasal-16]: "' in shown
    assert "sumber PasalKini, yang tidak memuat semua peraturan" in shown
    assert "Sumber:" not in shown and outcome.confidence == "sedang"


def test_a_repair_that_verifies_nothing_keeps_what_the_first_selection_verified():
    mixed = picks(
        (OLD.source_id, "paling banyak 3 (tiga) jam"), (OLD.source_id, "paling lama 9 jam sehari")
    )
    wrong = picks((OLD.source_id, "paling lama 9 jam sehari"))
    outcome = run(ScriptedChat(selections=[mixed, wrong]))
    assert not outcome.abstained and [c.source_id for c in outcome.citations] == [OLD.source_id]
    assert outcome.dropped == [OLD.source_id]


def test_out_of_scope_is_refused_without_searching():
    chat = ScriptedChat(intent="di_luar_cakupan")
    outcome = run(chat, "Bagaimana pembagian harta gono-gini?")
    assert outcome.abstained and outcome.answer == OUT_OF_SCOPE
    assert outcome.referral == OUT_OF_SCOPE_REFERRAL
    assert [name for name, _ in chat.calls] == ["Classification"]
    assert outcome.display().startswith(OUT_OF_SCOPE)


def test_a_named_article_comes_before_the_search_results():
    outcome = run(ScriptedChat(selections=[PICKS_OLD]), "Apa isi Pasal 78 UU 13/2003?")
    assert outcome.context[0].source_id == OLD.source_id
    assert outcome.context[1].source_id == REST.source_id
    assert outcome.lead is None  # not a question about the article's status


def test_an_answer_that_mentions_what_it_was_not_given_is_rewritten_once():
    invented = says("Paling banyak 3 jam sehari dan 14 jam seminggu menurut Pasal 99.")
    chat = ScriptedChat(selections=[PICKS_OLD], answers=[invented, says(SAID)])
    outcome = run(chat)
    assert outcome.rewritten and outcome.answer_problems == ["Pasal 99", "angka 14"]
    assert outcome.answer == SAID and not outcome.ungrounded and not outcome.caveats
    asked = chat.named("Answer")[-1][-1]["content"]
    assert "tidak tertulis di KUTIPAN: Pasal 99, angka 14" in asked


def test_an_answer_that_stays_ungrounded_is_shown_with_a_note():
    invented = says("Paling banyak 3 jam sehari dan 14 jam seminggu.")
    outcome = run(ScriptedChat(selections=[PICKS_OLD], answers=[invented, invented]))
    assert outcome.ungrounded == ["angka 14"] and outcome.confidence == "rendah"
    assert "menyebut angka 14, yang tidak ada di sumber" in outcome.caveats[-1]


def test_the_words_an_answer_says_it_rests_on_must_be_in_its_passages():
    made_up = says(SAID, dasar="paling banyak 9 (sembilan) jam dalam 1 (satu) hari")
    copied = says(SAID, dasar="paling banyak 3 (tiga) jam dalam 1 (satu) hari")
    chat = ScriptedChat(selections=[PICKS_OLD], answers=[made_up, copied])
    outcome = run(chat)
    assert outcome.answer_problems == [NO_BASIS] and outcome.rewritten
    assert not outcome.ungrounded and outcome.confidence == "tinggi"
    assert "salin persis dari KUTIPAN" in chat.named("Answer")[-1][-1]["content"]


PICKS_REST = picks((REST.source_id, "istirahat mingguan 1 hari"))


def test_when_the_passages_hold_no_answer_the_model_picks_again_once():
    nothing = says("Kutipan tidak menyebut batas lembur.", abstain=True)
    chat = ScriptedChat(selections=[PICKS_REST, PICKS_OLD], answers=[nothing, says(SAID)])
    outcome = run(chat)
    assert outcome.reselected and not outcome.abstained and outcome.answer == SAID
    assert [c.source_id for c in outcome.citations] == [OLD.source_id]
    again = chat.named("Selection")[1]
    assert again[-2]["role"] == "assistant" and "istirahat mingguan" in again[-2]["content"]
    assert again[-1]["content"].startswith(
        "Kutipan itu tidak memuat jawabannya. Kutipan tidak menyebut batas lembur. Pilih kutipan"
    )


def test_picking_the_same_passage_again_gets_a_context_without_its_article():
    nothing = says("Kutipan tidak menyebut batas lembur.", abstain=True)
    chat = ScriptedChat(
        selections=[PICKS_REST, PICKS_REST, PICKS_OLD], answers=[nothing, says(SAID)]
    )
    outcome = run(chat)
    assert not outcome.abstained and outcome.answer == SAID and not outcome.retried
    first, again, without = [messages[-1]["content"] for messages in chat.named("Selection")]
    assert f"[{REST.source_id}]" in first and again.startswith("Kutipan itu tidak memuat")
    assert f"[{REST.source_id}]" not in without and f"[{OLD.source_id}]" in without


def test_an_answer_that_finds_nothing_in_its_passages_abstains():
    nothing = says("Kutipan tidak menyebut batas lembur.", abstain=True)
    # Picking the same passage twice more is not a second chance.
    chat = ScriptedChat(selections=[PICKS_OLD, PICKS_OLD, PICKS_OLD], answers=[nothing])
    outcome = run(chat)
    assert outcome.abstained and outcome.answer == "Kutipan tidak menyebut batas lembur."
    assert not outcome.citations and len(chat.named("Answer")) == 1
    # What was found is still shown, as found and not as the basis of an answer.
    assert "Kutipan terdekat yang ditemukan:\n- UU 13/2003 Pasal 78" in outcome.display()


PASAL_59 = dated(
    "uu-13-2003/pasal-59",
    "uu-13-2003/pasal-59",
    "(1) Perjanjian kerja untuk waktu tertentu hanya dapat dibuat untuk pekerjaan tertentu.\n"
    "(2) Perjanjian kerja untuk waktu tertentu tidak dapat diadakan untuk pekerjaan tetap.\n"
    "(3) Perjanjian kerja untuk waktu tertentu dapat diperpanjang atau diperbaharui.\n"
    "(4) Perjanjian kerja waktu tertentu yang didasarkan atas jangka waktu tertentu dapat "
    "diadakan untuk paling lama 2 (dua) tahun dan hanya boleh diperpanjang 1 (satu) kali untuk "
    "jangka waktu paling lama 1 (satu) tahun.",
    "2003-03-25",
    title="UU 13/2003 Pasal 59 (berlaku sejak 25 Maret 2003)",
)
PICKS_EXTENSION = picks((PASAL_59.source_id, "dapat diperpanjang atau diperbaharui"))
NO_LIMIT = "Tidak ada batas maksimal lama kontrak dalam peraturan yang berlaku."
TWO_PLUS_ONE = "Paling lama 2 tahun, dan hanya boleh diperpanjang 1 kali untuk paling lama 1 tahun."


def run_contract(chat):
    index = DenseIndex("test", [PASAL_59], np.array([[1.0, 0.0]], np.float32), "test")
    pipeline = Pipeline(CONFIG, [PASAL_59], index, None, chat=chat, today=TODAY)
    return pipeline.run("Berapa lama maksimal kontrak kerja?", date(2019, 6, 1), QUERY)


def test_an_answer_that_no_rule_exists_gets_a_second_look_at_the_whole_article():
    # The quoted line cannot carry "there is no limit": the limit is in the next ayat.
    basis = "(4) Perjanjian kerja waktu tertentu yang didasarkan atas jangka waktu tertentu"
    chat = ScriptedChat(
        selections=[PICKS_EXTENSION], answers=[says(NO_LIMIT), says(TWO_PLUS_ONE, dasar=basis)]
    )
    outcome = run_contract(chat)
    assert outcome.reread and not outcome.abstained and not outcome.reselected
    assert outcome.answer == TWO_PLUS_ONE and not outcome.ungrounded
    first, second = [messages[-1]["content"] for messages in chat.named("Answer")]
    assert "dapat diperpanjang atau diperbaharui" in first and "paling lama 2 (dua)" not in first
    assert "paling lama 2 (dua) tahun" in second and "(1) Perjanjian kerja" in second
    assert "TUGAS: KUTIPAN di bawah memuat bunyi lengkap pasal yang dikutip" in second
    # The source shown is the line the answer now rests on, not the line first quoted.
    (cited,) = outcome.citations
    assert cited.source_id == PASAL_59.source_id and cited.quote.startswith("(4) Perjanjian")
    assert len(chat.named("Selection")) == 1


def test_a_second_look_that_still_finds_no_rule_is_the_answer():
    # 'There is no duty' can be the right reading of 'dapat'. It is not withheld.
    still = "Tidak ada ketentuan yang membatasi lamanya, menurut seluruh pasal itu."
    chat = ScriptedChat(selections=[PICKS_EXTENSION], answers=[says(NO_LIMIT), says(still)])
    outcome = run_contract(chat)
    assert outcome.reread and not outcome.abstained and outcome.answer == still
    assert len(chat.named("Answer")) == 2
    assert outcome.citations[0].quote == "dapat diperpanjang atau diperbaharui"


def test_with_nothing_more_to_read_there_is_no_second_look():
    # The article is one line, and the answer step has already read all of it.
    outcome = run(chat := ScriptedChat(selections=[PICKS_OLD], answers=[says(NO_LIMIT)]))
    assert not outcome.reread and outcome.answer == NO_LIMIT
    assert len(chat.named("Answer")) == 1


def test_a_cut_off_selection_is_read_from_the_start_of_its_quotes():
    scripted = ScriptedChat()
    cut = (
        '{"kutipan": [{"source_id": "[uu-13-2003/pasal-78]", "quote": "waktu kerja lembur hanya '
        "dapat dilakukan paling banyak 3 (tiga) jam dalam 1 (sat"
    )

    def chat(options, messages, schema):
        if schema is Selection:
            scripted.calls.append((schema.__name__, list(messages)))
            return Reply(None, cut, 10, 500, 0.0)
        return scripted(options, messages, schema)

    outcome = run(chat)
    assert outcome.salvaged and not outcome.retried and not outcome.abstained
    assert outcome.answer == SAID and outcome.json_ok
    assert [c.source_id for c in outcome.citations] == [OLD.source_id]
    assert outcome.citations[0].quote.endswith("3 (tiga) jam dalam 1")
    assert len(scripted.named("Selection")) == 1  # not asked again


def test_a_dispute_gets_the_fixed_referral():
    outcome = run(ScriptedChat(selections=[PICKS_OLD], answers=[says(SAID, perselisihan=True)]))
    assert outcome.referral.startswith("mediator hubungan industrial")


def test_history_questions_see_each_wording_once_over_its_whole_span():
    chat = ScriptedChat(intent="riwayat", selections=[PICKS_OLD])
    outcome = run(chat, "Apa yang berubah pada Pasal 78 UU 13/2003?", TODAY)
    ids = [c.source_id for c in outcome.context]
    assert ids.count(NEW.source_id) == 1 and OLD.source_id in ids
    merged = next(c for c in outcome.context if c.source_id == NEW.source_id)
    assert merged.valid_from == date(2020, 11, 2) and merged.status == "conditional"
    assert outcome.changed_since == []  # a history answer already covers the changes
    # Code states the article's timeline and its status on the date.
    assert outcome.timeline.splitlines() == [
        "Riwayat UU 13/2003 Pasal 78:",
        "- 25 Maret 2003 s.d. 1 November 2020: bunyi asli [uu-13-2003/pasal-78]",
        "- sejak 2 November 2020: bunyi dari UU 11/2020 [uu-11-2020/pasal-81/angka-22]; "
        "bersyarat sejak 25 November 2021",
        "Pada 1 Oktober 2026: berlaku bersyarat dengan bunyi dari UU 11/2020 "
        "[uu-11-2020/pasal-81/angka-22], bukan bunyi aslinya.",
    ]
    given = chat.named("Answer")[0][-1]["content"]
    assert "RIWAYAT PASAL" in given and "TUGAS: Jelaskan apa yang berubah" in given


OPENING = (
    "UU 13/2003 Pasal 78 masih berlaku bersyarat pada 1 Oktober 2026, tetapi tidak lagi dengan "
    "bunyi aslinya: yang berlaku adalah bunyi dari UU 11/2020, sejak 2 November 2020."
)


def test_whether_a_named_article_still_applies_is_answered_by_code_alone():
    chat = ScriptedChat(intent="status")
    outcome = run(chat, "Apakah Pasal 78 UU 13/2003 masih berlaku?", TODAY)
    assert [name for name, _ in chat.calls] == ["Classification"]
    assert outcome.answer == OPENING and not outcome.abstained
    # Sources: the wording that applies, then the original, each by its first line.
    assert [(c.source_id, c.quote) for c in outcome.citations] == [
        (NEW.source_id, FOUR),
        (OLD.source_id, THREE),
    ]
    assert outcome.timeline.startswith("Riwayat UU 13/2003 Pasal 78:")
    assert outcome.confidence == "sedang"  # the wording applies conditionally


def test_a_status_question_about_an_article_not_in_the_model_goes_to_the_model():
    chat = ScriptedChat(intent="status", selections=[PICKS_OLD])
    outcome = run(chat, "Apakah Pasal 999 UU 13/2003 masih berlaku?", TODAY)
    assert outcome.lead is None and chat.named("Answer")


def test_a_question_about_change_is_answered_as_the_old_wording_and_the_current_one():
    chat = ScriptedChat(intent="riwayat", selections=[PICKS_NEW])
    outcome = run(chat, "Apa yang berubah pada Pasal 78 UU 13/2003?", TODAY)
    # The model quoted only the wording that applies; code adds the original, in front.
    assert [c.source_id for c in outcome.citations] == [OLD.source_id, NEW.source_id]
    given = chat.named("Comparison")[0][-1]["content"]
    assert (
        "1. BUNYI LAMA: UU 13/2003 Pasal 78" in given and "2. BUNYI SEKARANG: UU 13/2003" in given
    )
    assert given.index(THREE) < given.index(FOUR) and "TUGAS" not in given
    # Code opens with the article's status and labels the two summaries.
    assert outcome.lead == OPENING and outcome.answer == f"{OPENING} {COMPARED}"
    assert not chat.named("Answer")


def test_a_summary_that_repeats_its_label_is_shown_without_it():
    labelled = Comparison(
        lama="Bunyi lama mengatur bahwa lembur paling banyak 3 jam sehari",
        sekarang="bunyi sekarang: lembur paling lama 4 jam sehari.",
    )
    chat = ScriptedChat(intent="riwayat", selections=[PICKS_NEW], comparisons=[labelled])
    outcome = run(chat, "Apa yang berubah soal lembur setelah Cipta Kerja?", TODAY)
    assert outcome.answer == COMPARED


def test_each_summary_may_only_use_its_own_wording_and_neither_may_state_dates():
    swapped = Comparison(lama="Lembur paling lama 4 jam.", sekarang="Lembur paling banyak 3 jam.")
    chat = ScriptedChat(intent="riwayat", selections=[PICKS_NEW], comparisons=[swapped])
    outcome = run(chat, "Apa yang berubah soal lembur setelah Cipta Kerja?", TODAY)
    assert outcome.answer_problems == [
        "angka 4 (tidak ada di bunyi lama)",
        "angka 3 (tidak ada di bunyi sekarang)",
    ]
    assert outcome.rewritten and outcome.answer == COMPARED and not outcome.ungrounded
    dated_summary = Comparison(lama="Sejak 25 Maret 2003 paling banyak 3 jam.", sekarang="4 jam.")
    chat = ScriptedChat(intent="riwayat", selections=[PICKS_NEW], comparisons=[dated_summary])
    outcome = run(chat, "Apa yang berubah soal lembur setelah Cipta Kerja?", TODAY)
    assert outcome.answer_problems == ["tanggal 25 Maret 2003"]


def test_without_an_old_wording_a_question_about_change_goes_to_the_usual_answer():
    both = picks((OLD.source_id, "paling banyak 3 (tiga) jam"), (NEW.source_id, "paling lama 4"))
    chat = ScriptedChat(intent="riwayat", selections=[both])
    outcome = run(chat, "Apa yang berubah?", TODAY)
    assert [c.source_id for c in outcome.citations] == [OLD.source_id, NEW.source_id]
    assert outcome.answer == COMPARED  # the model quoted both itself: nothing was added
    only_old = ScriptedChat(intent="riwayat", selections=[PICKS_OLD])
    outcome = run(only_old, "Apa yang berubah pada aturan lembur sampai 2019?", date(2019, 6, 1))
    assert not only_old.named("Comparison") and outcome.answer == SAID


def test_merge_periods_names_the_status_change():
    merged = merge_periods([NEW, NEW_RULED])
    assert merged.title == (
        "UU 13/2003 Pasal 78 (berlaku sejak 2 November 2020; bersyarat sejak 25 November 2021)"
    )


CONTRACT = "Kontrak PKWT saya 6 bulan dengan upah Rp4.000.000 berakhir. Berapa kompensasinya?"
CONTRACT_FACTS = {"jenis": "kompensasi_pkwt", "lama_tahun": 0, "lama_bulan": 6, "upah_bulanan": 0}
AMOUNT = "Menurut hitungan program, uang kompensasi PKWT-nya Rp2.000.000 (6/12 x 1 bulan upah)."


def test_an_amount_that_was_asked_for_is_stated_and_sourced_by_code():
    chat = ScriptedChat(intent="hitung", facts=CONTRACT_FACTS)
    outcome = run(chat, CONTRACT, date(2022, 3, 15))
    assert outcome.calculation.result.total == 2_000_000
    # After reading the facts the model has nothing left to do.
    assert [name for name, _ in chat.calls] == ["Classification", "FaktaHitungan"]
    assert outcome.answer == AMOUNT and not outcome.abstained
    assert [(c.source_id, c.quote) for c in outcome.citations] == [
        (COMPENSATION.source_id, "uang kompensasi diberikan dengan ketentuan sebagai berikut")
    ]
    assert "Hitungan (oleh program):" in outcome.display() and outcome.referral is None


def test_an_enacted_perppu_is_named_with_its_law_once_that_law_applied():
    library = Library([], {"perppu-2-2022": ("uu-6-2023", date(2023, 3, 31))})
    point = "perppu-2-2022/pasal-81/angka-15"
    assert library.instrument(point, date(2023, 1, 15)) == "Perppu 2/2022"
    assert library.instrument(point, date(2024, 1, 1)) == (
        "Perppu 2/2022 (ditetapkan menjadi UU 6/2023)"
    )
    ruling = "mk-168-puu-xxi-2023/amar-7"
    assert library.instrument(ruling, date(2025, 1, 1)) == "Putusan MK 168/PUU-XXI/2023"


def test_a_history_question_without_a_named_article_gets_the_timeline_of_what_it_quotes():
    chat = ScriptedChat(intent="riwayat", selections=[PICKS_OLD])
    outcome = run(chat, "Apa yang berubah soal lembur setelah Cipta Kerja?", TODAY)
    ids = [c.source_id for c in outcome.context]
    # The search ranks the rest-day article first, but it never changed. What changed can only
    # be read from an article that did: both wordings of the overtime article come first, oldest
    # first.
    assert ids[:3] == [OLD.source_id, NEW.source_id, REST.source_id]
    assert outcome.timeline.startswith("Riwayat UU 13/2003 Pasal 78:")
    assert outcome.lead is None and outcome.answer == SAID


def test_a_rule_the_model_finds_absent_is_reported_with_when_it_began():
    # Read in full, the article of the date has no such rule. One began later: code says when.
    none = "Tidak ada ketentuan tentang uang kompensasi dalam pasal ini."
    later = picks((COMPENSATION.source_id, "uang kompensasi diberikan dengan ketentuan"))
    chat = ScriptedChat(selections=[PICKS_OLD, later], answers=[says(none)])
    outcome = run(chat, "Apakah pekerja kontrak berhak uang kompensasi saat kontrak berakhir?")
    assert outcome.absent and not outcome.abstained
    assert outcome.answer == (
        f"{none} Ketentuan yang mengaturnya dalam sumber PasalKini, PP 35/2021 Pasal 16, baru "
        "berlaku sejak 2 Februari 2021, jadi belum berlaku pada tanggal itu."
    )
    assert outcome.confidence == "sedang"
    assert "sumber PasalKini, yang tidak memuat semua peraturan" in outcome.display()
    assert "Aturan yang berlaku kemudian:\n- PP 35/2021 Pasal 16" in outcome.display()


EFFICIENCY = "Kalau saya di-PHK karena perusahaan efisiensi, berapa kali ketentuan uang pesangon?"


def efficiency_facts(evidence):
    return {
        "jenis": "pesangon",
        "lama_tahun": 0,
        "lama_bulan": 0,
        "upah_bulanan": 0,
        "bukti_alasan": evidence,
        "alasan": "tutup_efisiensi",
    }


def test_a_severance_question_without_a_wage_gets_the_multipliers_from_the_calculator():
    chat = ScriptedChat(
        facts=efficiency_facts("perusahaan efisiensi"),
        selections=[PICKS_OLD],
        answers=[says("Dasarnya ketentuan tentang pemutusan hubungan kerja.")],
    )
    outcome = run(chat, EFFICIENCY)
    assert outcome.understanding.intent == "jelaskan" and outcome.calculation is not None
    assert outcome.answer.startswith(
        "Menurut hitungan program untuk PHK dengan alasan “perusahaan tutup bukan karena rugi "
        "atau keadaan memaksa, tetapi karena efisiensi”: uang pesangon 2 kali ketentuan dan uang "
        "penghargaan masa kerja 1 kali ketentuan, ditambah uang penggantian hak."
    )
    assert 'dibaca dari "perusahaan efisiensi"' in outcome.calculation.text()


def test_after_a_calculation_the_models_sentences_about_amounts_are_not_shown():
    opening = "Menurut hitungan program untuk PHK dengan alasan"
    restated = says(
        "Anda berhak atas uang pesangon sebesar 2 kali upah per bulan kerja. Uang penghargaan "
        "masa kerja mengikuti tabel Pasal 156 ayat (3). Hak ini timbul karena perusahaan tutup."
    )
    facts = efficiency_facts("perusahaan efisiensi")
    outcome = run(ScriptedChat(facts=facts, selections=[PICKS_OLD], answers=[restated]), EFFICIENCY)
    assert outcome.answer.startswith(opening)
    assert outcome.answer.endswith("ketentuan. Hak ini timbul karena perusahaan tutup.")
    assert "upah per bulan kerja" not in outcome.answer and "Pasal 156" not in outcome.answer
    # Nothing but amounts: the opening stands alone.
    only_amounts = says("Uang pesangon dihitung 2 kali ketentuan.")
    outcome = run(
        ScriptedChat(facts=facts, selections=[PICKS_OLD], answers=[only_amounts]), EFFICIENCY
    )
    assert outcome.answer.startswith(opening) and outcome.answer.endswith("x ketentuan.")


def test_after_an_opening_the_models_sentences_are_shown_only_if_they_pass_the_checks():
    invented = says("Batasnya naik menjadi 9 jam sehari.")
    chat = ScriptedChat(intent="riwayat", selections=[PICKS_OLD], answers=[invented, invented])
    outcome = run(chat, "Apa yang berubah pada Pasal 78 UU 13/2003 sampai 2019?", date(2019, 6, 1))
    # Named article, one wording only: the usual answer call, after the status sentence by code.
    assert outcome.lead and outcome.trimmed and outcome.answer == outcome.lead
    assert not outcome.caveats and not outcome.ungrounded


def test_a_reason_the_question_does_not_state_is_not_calculated_with():
    chat = ScriptedChat(facts=efficiency_facts("perusahaan bangkrut"), selections=[PICKS_OLD])
    outcome = run(chat, EFFICIENCY)
    assert chat.named("FaktaHitungan") and outcome.calculation is None
    assert outcome.answer == SAID and "Hitungan" not in outcome.display()


def test_the_calculator_is_not_asked_about_questions_on_other_things():
    chat = ScriptedChat(selections=[PICKS_OLD])
    run(chat, "Apakah pekerja yang terkena PHK mendapat Jaminan Kehilangan Pekerjaan?")
    assert not chat.named("FaktaHitungan")


def test_the_calculator_prompt_lists_the_reasons_in_force_and_shows_the_one_used():
    chat = ScriptedChat(
        intent="hitung",
        facts={
            "jenis": "pesangon",
            "lama_tahun": 5,
            "lama_bulan": 3,
            "upah_bulanan": 6000000,
            "alasan": "tutup_rugi_2_tahun",
        },
        selections=[picks((COMPENSATION.source_id, "uang kompensasi diberikan dengan ketentuan"))],
        answers=[says("Dasarnya ketentuan tentang pemutusan hubungan kerja.")],
    )
    question = "Saya bekerja 5 tahun 3 bulan, upah Rp6.000.000, perusahaan tutup karena rugi."
    outcome = run(chat, question, date(2023, 6, 1))
    facts_prompt = chat.named("FaktaHitungan")[0][0]["content"]
    assert "- tutup_rugi_2_tahun: perusahaan tutup karena rugi selama 2 tahun" in facts_prompt
    assert "- pensiun: pekerja memasuki usia pensiun" in facts_prompt
    text = outcome.calculation.text()
    # The question asks for a calculation, so the reason is used though no evidence came with it.
    assert outcome.calculation.result.total == 30_000_000
    assert "Alasan PHK yang dipakai: perusahaan tutup karena rugi selama 2 tahun" in text
    assert outcome.answer == (
        "Menurut hitungan program untuk PHK dengan alasan “perusahaan tutup karena rugi selama 2 "
        "tahun, terus-menerus atau tidak”: Rp30.000.000 (uang pesangon Rp18.000.000, uang "
        "penghargaan masa kerja Rp12.000.000), belum termasuk uang penggantian hak lain yang "
        "tidak dapat dihitung dari pertanyaan."
    )
    assert outcome.referral == DISPUTE_REFERRAL  # a severance sum is asked about a dismissal


def test_an_article_deleted_twice_is_reported_as_deleted_since_the_first_deletion():
    pid, title = "uu-13-2003/pasal-90", "UU 13/2003 Pasal 90 (x)"
    chunks = [
        dated(
            pid, pid, "Pengusaha dilarang membayar upah lebih rendah", "2003-03-25", "2020-11-02"
        ),
        dated(
            "uu-11-2020/pasal-81/angka-27", pid, "Dihapus.", "2020-11-02", "2022-12-30", "repealed"
        ),
        dated("perppu-2-2022/pasal-81/angka-30", pid, "Dihapus.", "2022-12-30", None, "repealed"),
    ]
    chunks = [replace(c, title=title) for c in chunks]
    library = Library(chunks, {"perppu-2-2022": ("uu-6-2023", date(2023, 3, 31))})
    perppu = "Perppu 2/2022 (ditetapkan menjadi UU 6/2023)"
    assert history_of(library, pid, TODAY).splitlines() == [
        "Riwayat UU 13/2003 Pasal 90:",
        "- 25 Maret 2003 s.d. 1 November 2020: bunyi asli [uu-13-2003/pasal-90]",
        "- 2 November 2020 s.d. 29 Desember 2022: dihapus oleh UU 11/2020 "
        "[uu-11-2020/pasal-81/angka-27]",
        f"- sejak 30 Desember 2022: dihapus oleh {perppu} [perppu-2-2022/pasal-81/angka-30]",
        f"Pada 1 Oktober 2026: sudah dihapus. Dihapus sejak 2 November 2020; dasarnya sekarang "
        f"{perppu} [perppu-2-2022/pasal-81/angka-30].",
    ]
    assert status_sentence(library, pid, TODAY) == (
        "UU 13/2003 Pasal 90 sudah tidak berlaku pada 1 Oktober 2026: pasal ini dihapus sejak "
        f"2 November 2020 oleh UU 11/2020, dan tetap dihapus dalam {perppu}."
    )
    assert status_sentence(library, pid, date(2019, 6, 1)) == (
        "UU 13/2003 Pasal 90 masih berlaku pada 1 Juni 2019 dengan bunyi aslinya."
    )
    assert status_sentence(library, "uu-13-2003/pasal-999", TODAY) is None


WORD_STRUCK = (
    "Menyatakan kata “dapat” dalam Pasal 79 ayat (5) dalam Pasal 81 angka 25 Lampiran "
    "Undang-Undang Nomor 6 Tahun 2023 tentang Penetapan Peraturan Pemerintah Pengganti "
    "Undang-Undang Nomor 2 Tahun 2022 tentang Cipta Kerja Menjadi Undang-Undang (Lembaran Negara "
    "Republik Indonesia Tahun 2023 Nomor 41, Tambahan Lembaran Negara Republik Indonesia Nomor "
    "6856) bertentangan dengan Undang-Undang Dasar Negara Republik Indonesia Tahun 1945 dan "
    "tidak memiliki kekuatan hukum mengikat;"
)
LEAVE = dated(
    "perppu-2-2022/pasal-81/angka-25",
    "uu-13-2003/pasal-79",
    "(3) Cuti tahunan paling sedikit 12 (dua belas) hari kerja.\n"
    "(5) Perusahaan tertentu dapat memberikan istirahat panjang.\n\n"
    "Catatan:\n"
    "[mk-168-puu-xxi-2023/amar-8] Menyatakan kata “dapat” dalam Pasal 79 ayat (5) …\n"
    "[perppu-2-2022/pasal-184] Perppu 2/2022 Pasal 184: tetap berlaku sepanjang tidak "
    "bertentangan.",
    "2024-10-31",
    status="conditional",
    title="UU 13/2003 Pasal 79 (berlaku sejak 31 Oktober 2024; bersyarat)",
)
RULING = dated(
    "mk-168-puu-xxi-2023/amar-8",
    "mk-168-puu-xxi-2023/amar-8",
    WORD_STRUCK,
    "2024-10-31",
    title="Putusan MK 168/PUU-XXI/2023 amar 8",
)


def test_a_quoted_ayat_is_read_with_what_the_court_ruled_about_it():
    library = Library([LEAVE, RULING])
    day = date(2025, 6, 1)
    struck = (
        "Putusan MK: Menurut Putusan MK 168/PUU-XXI/2023, kata “dapat” dalam Pasal 79 ayat (5) "
        "tidak berlaku lagi (tidak mempunyai kekuatan hukum mengikat): baca ketentuan itu tanpa "
        "kata-kata tersebut, sehingga hal yang diaturnya bukan lagi pilihan."
    )
    quoted = picks((LEAVE.source_id, "Perusahaan tertentu dapat memberikan istirahat panjang"))
    passages = check_selection(quoted, [LEAVE], day, False).passages
    [(_, ayat, block)] = shown_passages(library, passages)
    assert ayat == {"5"} and block.splitlines() == [
        LEAVE.title,
        # The word the Court struck is taken out of what the model reads, and marked.
        "(5) Perusahaan tertentu memberikan istirahat panjang. [kata “dapat” dihapus oleh "
        "Putusan MK 168/PUU-XXI/2023: bukan lagi pilihan]",
        struck,  # from the ruling's full text, not from the note cut short under the article
    ]
    # The user is still shown the source's own words.
    assert passages[0].quote == "Perusahaan tertentu dapat memberikan istirahat panjang"
    # A ruling about ayat (5) says nothing about a passage from ayat (3).
    other = picks((LEAVE.source_id, "Cuti tahunan paling sedikit 12 (dua belas) hari kerja"))
    passages = check_selection(other, [LEAVE], day, False).passages
    assert "Putusan MK" not in shown_passages(library, passages)[0][2]


def test_a_regulation_quoted_beside_a_ruled_law_is_marked_as_the_lower_rule():
    regulation = dated(
        "pp-35-2021/pasal-35",
        "pp-35-2021/pasal-35",
        "(1) Perusahaan tertentu dapat memberikan istirahat panjang.",
        "2021-02-02",
        title="PP 35/2021 Pasal 35",
    )
    library = Library([LEAVE, RULING, regulation])
    both = picks(
        (LEAVE.source_id, "Perusahaan tertentu dapat memberikan istirahat panjang"),
        (regulation.source_id, "Perusahaan tertentu dapat memberikan istirahat panjang"),
    )
    passages = check_selection(both, [LEAVE, regulation], date(2025, 6, 1), False).passages
    law, lower = [block for _, _, block in shown_passages(library, passages)]
    assert "Putusan MK:" in law and "Catatan program" not in law
    assert lower.splitlines()[-1].startswith("Catatan program: ini peraturan pelaksana.")
    # Without a ruling in play, a regulation is quoted as it is.
    alone = shown_passages(library, passages[1:])[0][2]
    assert "Catatan program" not in alone


def test_rulings_and_standing_notes_on_a_cited_article_are_shown_by_code():
    chunks = [*CHUNKS, LEAVE, RULING]
    vectors = np.vstack([INDEX.vectors, [[1.0, 0.0], [0.0, 1.0]]]).astype(np.float32)
    index = DenseIndex(model="test", chunks=chunks, vectors=vectors, fingerprint="test")
    chat = ScriptedChat(
        selections=[picks((LEAVE.source_id, "Perusahaan tertentu dapat memberikan istirahat"))],
        answers=[says("Perusahaan tertentu wajib memberikan istirahat panjang.")],
    )
    pipeline = Pipeline(CONFIG, chunks, index, None, chat=chat, today=TODAY)
    outcome = pipeline.run("Apakah istirahat panjang wajib?", date(2025, 6, 1), QUERY)
    assert outcome.caveats[0].startswith("Menurut Putusan MK 168/PUU-XXI/2023, kata “dapat”")
    assert outcome.caveats[1].startswith("Perppu 2/2022 Pasal 184")
    assert outcome.confidence == "sedang"  # the article applies conditionally
    given = chat.named("Answer")[0][-1]["content"]
    assert "Putusan MK: Menurut Putusan MK 168" in given and "Pasal 184" not in given
