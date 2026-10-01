from datetime import date

from pasalkini.answer.verify import Answer, Citation, quote_in, verify
from pasalkini.temporal.corpus import DatedChunk

OLD = DatedChunk(
    source_id="uu-13-2003/pasal-78",
    instrument_id="uu-13-2003",
    title="UU 13/2003 Pasal 78",
    text="b. waktu kerja lembur hanya dapat dilakukan paling banyak 3 (tiga) jam sehari",
    page=0,
    provision_id="uu-13-2003/pasal-78",
    status="in_force",
    valid_from=date(2003, 3, 25),
    valid_to=date(2020, 11, 2),
)
NEW = DatedChunk(
    source_id="uu-11-2020/pasal-81/angka-22",
    instrument_id="uu-13-2003",
    title="UU 13/2003 Pasal 78",
    text="b. waktu kerja lembur hanya dapat dilakukan paling lama 4 (empat) jam sehari",
    page=0,
    provision_id="uu-13-2003/pasal-78",
    status="in_force",
    valid_from=date(2020, 11, 2),
    valid_to=None,
)


def answer(*citations: tuple[str, str], abstain: bool = False) -> Answer:
    return Answer(
        answer="…",
        citations=[Citation(source_id=s, quote=q) for s, q in citations],
        confidence="tinggi",
        abstain=abstain,
    )


def test_quote_matching_ignores_case_and_whitespace_but_needs_some_length():
    assert quote_in("Paling  banyak 3 (tiga) JAM", OLD.text)
    assert not quote_in("3 jam", OLD.text)  # too short to verify anything
    assert not quote_in("paling banyak 5 (lima) jam", OLD.text)


def test_a_shortened_quote_passes_when_each_part_is_there_in_order():
    assert quote_in("waktu kerja lembur … paling banyak 3 (tiga) jam", OLD.text)
    assert not quote_in("paling banyak 3 (tiga) jam … waktu kerja lembur", OLD.text)
    assert not quote_in("waktu kerja lembur … jam", OLD.text)  # each part needs some length


def test_brackets_around_a_cited_id_are_tolerated():
    ok = verify(
        answer(("[uu-13-2003/pasal-78]", "paling banyak 3 (tiga) jam")),
        [OLD],
        date(2019, 6, 1),
        False,
    )
    assert ok.ok and ok.valid[0].source_id == "uu-13-2003/pasal-78"


def test_a_correct_citation_passes():
    ok = verify(
        answer((OLD.source_id, "paling banyak 3 (tiga) jam")), [OLD], date(2019, 6, 1), False
    )
    assert ok.ok


def test_invented_source_misquote_and_wrong_date_are_caught():
    checks = verify(
        answer(
            ("pp-35-2021/pasal-26", "paling lama 4 (empat) jam"),  # not in context
            (OLD.source_id, "paling lama 4 (empat) jam"),  # not what that text says
            (NEW.source_id, "paling lama 4 (empat) jam"),  # did not apply in 2019
        ),
        [OLD, NEW],
        date(2019, 6, 1),
        False,
    )
    assert len(checks.problems) == 3


def test_history_questions_may_cite_old_versions():
    ok = verify(
        answer((OLD.source_id, "paling banyak 3 (tiga) jam")), [OLD, NEW], date(2025, 1, 1), True
    )
    assert ok.ok


def test_an_answer_must_cite_something_unless_it_abstains():
    assert not verify(answer(), [OLD], date(2019, 6, 1), False).ok
    assert verify(answer(abstain=True), [OLD], date(2019, 6, 1), False).ok
