from datetime import date

from pasalkini.answer.verify import (
    Citation,
    Selection,
    body_of,
    check_selection,
    dates_in,
    expand,
    find_spans,
    locate,
    numbers_in,
    quote_in,
    ungrounded,
)
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


def chosen(*citations: tuple[str, str]) -> Selection:
    return Selection(kutipan=[Citation(source_id=s, quote=q) for s, q in citations])


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
    ok = check_selection(
        chosen(("[uu-13-2003/pasal-78]", "paling banyak 3 (tiga) jam")),
        [OLD],
        date(2019, 6, 1),
        False,
    )
    assert ok.ok and ok.passages[0].source_id == "uu-13-2003/pasal-78"


def test_a_correct_quote_passes_and_is_shown_in_the_sources_words():
    ok = check_selection(
        chosen((OLD.source_id, "Paling banyak 3 (tiga) jam.")), [OLD], date(2019, 6, 1), False
    )
    assert ok.ok and ok.passages[0].quote == "paling banyak 3 (tiga) jam"


def test_invented_source_misquote_and_wrong_date_are_caught():
    checks = check_selection(
        chosen(
            ("pp-35-2021/pasal-26", "paling lama 5 (lima) jam"),  # nowhere in the context
            (OLD.source_id, "paling lama 6 (enam) jam"),  # not what any text says
            (NEW.source_id, "paling lama 4 (empat) jam"),  # did not apply in 2019
        ),
        [OLD, NEW],
        date(2019, 6, 1),
        False,
    )
    assert len(checks.problems) == 3 and not checks.passages
    assert checks.failed == ["pp-35-2021/pasal-26", OLD.source_id, NEW.source_id]


def test_history_questions_may_quote_old_versions():
    ok = check_selection(
        chosen((OLD.source_id, "paling banyak 3 (tiga) jam")), [OLD, NEW], date(2025, 1, 1), True
    )
    assert ok.ok


def test_selecting_nothing_is_not_a_problem_and_the_same_passage_counts_once():
    assert check_selection(chosen(), [OLD], date(2019, 6, 1), False).ok
    twice = chosen(
        (OLD.source_id, "paling banyak 3 (tiga) jam"), (OLD.source_id, "Paling banyak 3 (tiga) jam")
    )
    assert len(check_selection(twice, [OLD], date(2019, 6, 1), False).passages) == 1


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
        check = check_selection(chosen((cited, quote)), [RULED], date(2025, 6, 1), False)
        assert check.ok and check.passages[0].source_id == RULED.source_id
        assert check.passages[0].spans == []  # in the notes, not in the article's own text
    # The ruling's ID does not vouch for words the chunk does not contain.
    assert not check_selection(
        chosen(("mk-168-puu-xxi-2023", "3 (tiga) hari untuk 4 (empat) hari kerja")),
        [RULED],
        date(2025, 6, 1),
        False,
    ).ok


def test_a_right_quote_under_a_wrong_id_is_shown_under_the_chunk_that_has_it():
    quote = "istirahat mingguan 1 (satu) hari untuk 6 (enam) hari kerja"
    check = check_selection(
        chosen(("uu-13-2003/pasal-81", quote)), [OLD, RULED], date(2025, 6, 1), False
    )
    assert check.ok and check.passages[0].source_id == RULED.source_id
    # ... but not when the only chunk that has it did not apply on the date.
    late = check_selection(
        chosen(("pp-35-2021/pasal-26", "paling lama 4 (empat) jam")),
        [OLD, NEW],
        date(2019, 6, 1),
        False,
    )
    assert late.problems == ["[pp-35-2021/pasal-26] tidak berlaku pada 2019-06-01."]


def test_a_quote_may_join_a_lists_opening_line_and_one_of_its_rows():
    quote = "Waktu istirahat wajib diberikan paling sedikit meliputi: b. istirahat mingguan 1 hari"
    # The quote leaves out 'kepada pekerja/buruh' and '(satu)'; the user sees the text's words.
    assert locate(quote, RULED.text) == (
        "Waktu istirahat wajib diberikan kepada pekerja/buruh paling sedikit meliputi: "
        "b. istirahat mingguan 1 (satu) hari"
    )
    stitched = (
        "Waktu istirahat wajib diberikan kepada pekerja/buruh paling sedikit meliputi: "
        "5 (lima) hari kerja dalam 1 (satu) minggu"
    )
    assert quote_in(stitched, RULED.text)


def test_ocr_digit_confusions_do_not_fail_a_correctly_read_quote():
    scanned = "b. istirahat mingguan I (satu) hari untuk 6 (enam) hari kerja dalam 1 (satu) minggu"
    assert quote_in("istirahat mingguan 1 (satu) hari untuk 6 (enam) hari kerja", scanned)
    assert quote_in(
        "dimaksud dalam Pasal 80 ayat (1)", "sebagaimana dimaksud dalam Pasal 8O ayat (l)"
    )
    assert not quote_in("istirahat mingguan 2 (satu) hari untuk 6 (enam) hari kerja", scanned)


def test_a_tidied_quote_is_found_and_shown_in_the_sources_words():
    source = (
        "(3) Pekerja/buruh yang mengundurkan diri sebagaimana dimaksud dalam ayat (1) harus "
        "memenuhi syarat : a. mengajukan permohonan pengunduran diri secara tertulis "
        "selambat-lambatnya 30 (tiga puluh) hari sebelum tanggal mulai pengunduran diri; "
        "b. tidak terikat dalam ikatan dinas"
    )
    tidied = (
        "Pekerja/buruh yang mengundurkan diri atas kemauan sendiri harus memenuhi syarat: "
        "mengajukan permohonan pengunduran diri secara tertulis selambat-lambatnya 30 (tiga "
        "puluh) hari sebelum tanggal mulai pengunduran diri."
    )
    shown = locate(tidied, source)
    assert shown.startswith("Pekerja/buruh yang mengundurkan diri sebagaimana dimaksud dalam")
    assert shown.endswith("30 (tiga puluh) hari sebelum tanggal mulai pengunduran diri")
    # A word the PDF broke at a line end is the same word.
    broken = (
        "uang penghargaan masa kerja ditetapkan sebagai be-rikut : a. masa kerja 3 (tiga) tahun"
    )
    assert quote_in("uang penghargaan masa kerja ditetapkan sebagai berikut", broken)
    # A changed number is never a near match, in digits or in words.
    assert not quote_in(tidied.replace("30 (tiga puluh)", "14 (empat belas)"), source)
    assert not quote_in(tidied.replace("30 (tiga puluh)", "30 (dua puluh)"), source)
    # Words from all over the article are not a passage.
    assert not quote_in(
        "pekerja yang terikat dalam permohonan dinas harus mengundurkan diri", source
    )


def test_a_quote_is_found_where_its_words_are_together_not_where_one_phrase_repeats():
    article = (
        "(2) Perjanjian kerja untuk waktu tertentu sebagaimana dimaksud pada ayat (1) didasarkan "
        "atas: a. jangka waktu; atau b. selesainya suatu pekerjaan tertentu. "
        "(3) Jangka waktu atau selesainya suatu pekerjaan tertentu sebagaimana dimaksud pada "
        "ayat (2) ditentukan berdasarkan perjanjian kerja."
    )
    quote = (
        "Perjanjian kerja untuk waktu tertentu didasarkan atas jangka waktu atau selesainya "
        "suatu pekerjaan tertentu."
    )
    assert locate(quote, article).startswith("Perjanjian kerja untuk waktu tertentu sebagaimana")


def test_the_shown_passage_keeps_the_brackets_around_its_first_and_last_words():
    text = "(1) Perusahaan dapat menyerahkan sebagian pekerjaan. (2) Pemerintah menetapkan."
    opening = "(1) Perusahaan dapat menyerahkan sebagian"
    assert locate(opening, text) == opening
    closing = "menyerahkan sebagian pekerjaan. (2)"
    assert locate(closing, text) == closing


REST = (
    "(1) Pengusaha wajib memberi waktu istirahat dan cuti kepada pekerja/buruh.\n"
    "(2) Waktu istirahat dan cuti sebagaimana dimaksud dalam ayat (1), meliputi :\n"
    "a. istirahat antara jam kerja, sekurang kurangnya setengah jam;\n"
    "b. istirahat mingguan 1 (satu) hari untuk 6 (enam) hari kerja dalam 1 (satu) minggu;\n"
    "c. cuti tahunan, sekurang kurangnya 12 (dua belas) hari kerja; dan\n"
    "d. istirahat panjang sekurang-kurangnya 2 (dua) bulan bagi pekerja/buruh yang telah "
    "bekerja selama 6 (enam) tahun.\n"
    "(3) Pelaksanaan waktu istirahat tahunan sebagaimana dimaksud dalam ayat (2) huruf c diatur "
    "dalam perjanjian kerja.\n"
    "(4) Hak istirahat panjang sebagaimana dimaksud dalam ayat (2) huruf d hanya berlaku bagi "
    "pekerja/buruh yang bekerja pada perusahaan tertentu.\n"
    "(5) Perusahaan tertentu sebagaimana dimaksud dalam ayat (4) diatur dengan Keputusan Menteri."
)


def passage(quote: str, body: str = REST) -> tuple[str, set[str]]:
    return expand(body, find_spans(quote, body))


def test_a_quoted_item_is_read_with_its_ayat_and_with_the_line_that_limits_it():
    text, ayat = passage("istirahat panjang sekurang-kurangnya 2 (dua) bulan")
    assert ayat == {"2"}
    assert text.splitlines() == [
        "(2) Waktu istirahat dan cuti sebagaimana dimaksud dalam ayat (1), meliputi :",
        "…",
        "d. istirahat panjang sekurang-kurangnya 2 (dua) bulan bagi pekerja/buruh yang telah "
        "bekerja selama 6 (enam) tahun.",
        "…",
        # Ayat (4) refers back to item d; ayat (3) is about item c and stays out.
        "(4) Hak istirahat panjang sebagaimana dimaksud dalam ayat (2) huruf d hanya berlaku bagi "
        "pekerja/buruh yang bekerja pada perusahaan tertentu.",
    ]


def test_a_quoted_opening_line_brings_the_items_under_it_unless_one_is_quoted():
    opening = "Waktu istirahat dan cuti sebagaimana dimaksud dalam ayat (1), meliputi"
    text, _ = passage(opening)
    lines = text.splitlines()
    assert lines[0].startswith("(2) Waktu istirahat") and lines[4].startswith("d. istirahat")
    assert not any(line.startswith("(1)") for line in lines)
    text, _ = passage(opening + ": b. istirahat mingguan 1 (satu) hari untuk 6 (enam) hari kerja")
    assert [line[:2] for line in text.splitlines()] == ["(2", "…", "b."]


def test_a_bracket_scanned_as_a_letter_does_not_fail_a_reference_to_an_ayat():
    scanned = "sebagaimana dimaksud pada ayat (1), ayat (2l., dan ayat (3), Perusahaan tertentu"
    assert quote_in("dimaksud pada ayat (1), ayat (2), dan ayat (3), Perusahaan tertentu", scanned)
    # Only after 'ayat': elsewhere a digit and a letter may be a number the scan garbled.
    assert not quote_in("paling lama 2 (dua) tahun bekerja", "paling lama 2l (dua) tahun bekerja")


def test_a_long_passage_is_cut():
    body = "(1) Daftar berikut:\n" + "\n".join(f"a. butir nomor {n} " + "x" * 80 for n in range(40))
    text, _ = passage("Daftar berikut", body)
    assert len(text) <= 1210 and text.endswith(" …")


def test_the_articles_own_text_ends_where_its_notes_begin():
    assert body_of(RULED).endswith("dalam 1 (satu) minggu.") and "Catatan" not in body_of(RULED)


GIVEN = (
    "PERTANYAAN: Saya lembur 4 jam sehari dengan upah Rp4.500.000.\n"
    "1. PP 35/2021 Pasal 40 (berlaku sejak 2 Februari 2021)\n"
    "(2) Uang pesangon diberikan paling banyak 3 (tiga) jam, I (satu) hari, setengah bulan upah "
    "atau 0,5 kali, sebagaimana dimaksud dalam Pasal 156."
)
ARTICLES = {"pp-35-2021/pasal-40"}


def test_an_answer_may_only_mention_numbers_and_articles_it_was_given():
    fine = "Menurut PP 35/2021 Pasal 40 ayat (2), paling banyak 3 jam; 4 jam melebihi batas itu."
    assert ungrounded(fine, GIVEN, ARTICLES) == []
    assert ungrounded("Batasnya 14 jam seminggu.", GIVEN, ARTICLES) == ["angka 14"]
    # The right article under the wrong law, and an article that appears nowhere.
    assert ungrounded("Lihat Pasal 40 UU No. 13 Tahun 2003.", GIVEN, ARTICLES) == [
        "Pasal 40 UU 13/2003",
        "angka 13",
        "angka 2003",
    ]
    assert ungrounded("Lihat Pasal 41.", GIVEN, ARTICLES) == ["Pasal 41"]
    assert ungrounded("Lihat juga Pasal 156.", GIVEN, ARTICLES) == []  # the passage mentions it


def test_numbers_are_compared_by_value_not_by_spelling():
    assert ungrounded("Upahnya Rp4,5 juta atau Rp 4.500.000,00.", GIVEN, ARTICLES) == []
    assert ungrounded("Satu hari, yaitu 1 hari, dan 0.5 kali.", GIVEN, ARTICLES) == []
    assert numbers_in("18.000.000 dan 1,80 serta 2 juta") == ["18000000", "1,8", "2000000"]


def test_dates_in_an_answer_are_found():
    answer = "Pasal itu dihapus sejak 2 November 2020 dan diganti pada 2022 oleh UU 13/2003."
    assert dates_in(answer) == ["2 November 2020", "pada 2022"]
    assert dates_in("Batasnya 4 jam sehari menurut PP 35/2021.") == []
