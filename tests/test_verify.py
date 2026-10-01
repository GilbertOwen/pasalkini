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
    assert quote_in("b. ... waktu kerja lembur hanya dapat dilakukan", OLD.text)  # 'b.' is a marker
    assert not quote_in("b. ... sehari", OLD.text)  # nothing long enough to check


def test_punctuation_does_not_fail_a_quote_but_words_and_numbers_do():
    ruling = "tidak dimaknai, “dibuat tidak melebihi paling lama 5 (lima) tahun”;"
    assert quote_in("dibuat tidak melebihi paling lama 5 (lima) tahun.", ruling)
    assert not quote_in("dibuat tidak melebihi paling lama 15 (lima) tahun", ruling)
    twelve = "masa kerja 12 (dua belas) tahun atau lebih"
    assert not quote_in("2 (dua belas) tahun atau lebih", twelve)  # whole numbers only


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


RULED = DatedChunk(
    source_id="perppu-2-2022/pasal-81/angka-25",
    instrument_id="uu-13-2003",
    title="UU 13/2003 Pasal 79 (berlaku sejak 30 Desember 2022; bersyarat sejak 31 Oktober 2024)",
    text=(
        "(2) Waktu istirahat wajib diberikan kepada pekerja/buruh paling sedikit meliputi:\n"
        "b. istirahat mingguan 1 (satu) hari untuk 6 (enam) hari kerja dalam 1 (satu) minggu.\n\n"
        "Catatan:\n"
        "[mk-168-puu-xxi-2023/amar-7] tidak dimaknai mencakup frasa atau 2 (dua) hari untuk "
        "5 (lima) hari kerja dalam 1 (satu) minggu"
    ),
    page=0,
    provision_id="uu-13-2003/pasal-79",
    status="conditional",
    valid_from=date(2022, 12, 30),
    valid_to=None,
)


def test_a_ruling_named_in_a_chunks_notes_is_shown_under_that_chunk():
    quote = "2 (dua) hari untuk 5 (lima) hari kerja dalam 1 (satu) minggu"
    for cited in ("mk-168-puu-xxi-2023/amar-7", "mk-168-puu-xxi-2023"):
        check = verify(answer((cited, quote)), [RULED], date(2025, 6, 1), False)
        assert check.ok and check.valid[0].source_id == RULED.source_id
    # The ruling's ID does not vouch for words the chunk does not contain.
    assert not verify(
        answer(("mk-168-puu-xxi-2023", "3 (tiga) hari untuk 4 (empat) hari kerja")),
        [RULED],
        date(2025, 6, 1),
        False,
    ).ok
    assert not verify(answer(("mk-91-puu-xviii-2020", quote)), [RULED], date(2025, 6, 1), False).ok


def test_a_quote_may_join_a_lists_opening_line_and_one_of_its_rows():
    quote = "Waktu istirahat wajib diberikan paling sedikit meliputi: b. istirahat mingguan 1 hari"
    assert not quote_in(quote, RULED.text)  # 'wajib diberikan paling sedikit' skips words
    stitched = (
        "Waktu istirahat wajib diberikan kepada pekerja/buruh paling sedikit meliputi: "
        "5 (lima) hari kerja dalam 1 (satu) minggu"
    )
    assert quote_in(stitched, RULED.text)
