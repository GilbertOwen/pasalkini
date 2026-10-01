"""Constitutional Court ruling points: shorter citations, and what the fixed formulas mean."""

from pasalkini.temporal.rulings import (
    abbreviate,
    ayat_of,
    meaning_of,
    reading,
    struck,
    without,
)

LAW = (
    "Undang-Undang Nomor 6 Tahun 2023 tentang Penetapan Peraturan Pemerintah Pengganti "
    "Undang-Undang Nomor 2 Tahun 2022 tentang Cipta Kerja Menjadi Undang-Undang (Lembaran Negara "
    "Republik Indonesia Tahun 2023 Nomor 41, Tambahan Lembaran Negara Republik Indonesia Nomor "
    "6856)"
)
UNCONSTITUTIONAL = (
    "bertentangan dengan Undang-Undang Dasar Negara Republik Indonesia Tahun 1945 dan tidak "
    "memiliki kekuatan hukum mengikat"
)
MK168 = "Putusan MK 168/PUU-XXI/2023"
WEEKLY_REST = (
    f"Menyatakan Pasal 79 ayat (2) huruf b dalam Pasal 81 angka 25 Lampiran {LAW} yang "
    "menyatakan, “istirahat mingguan 1 (satu) hari untuk 6 (enam) hari kerja dalam 1 (satu) "
    f"minggu”, {UNCONSTITUTIONAL}, sepanjang tidak dimaknai mencakup frasa, “atau 2 (dua) hari "
    "untuk 5 (lima) hari kerja dalam 1 (satu) minggu”;"
)
MINIMUM = (
    "Menyatakan frasa “diberikan dengan ketentuan sebagai berikut” dalam Pasal 156 ayat (2) "
    f"dalam Pasal 81 angka 47 Lampiran {LAW}, {UNCONSTITUTIONAL} sepanjang tidak dimaknai, "
    "“paling sedikit”;"
)
WORD_STRUCK = (
    f"Menyatakan kata “dapat” dalam Pasal 79 ayat (5) dalam Pasal 81 angka 25 Lampiran {LAW} "
    f"{UNCONSTITUTIONAL};"
)


def test_citations_are_shortened_and_the_decision_is_left_alone():
    short = abbreviate(WEEKLY_REST)
    assert len(short) < 400 < len(WEEKLY_REST)
    assert "Lampiran UU 6/2023 yang menyatakan" in short and "UUD 1945" in short
    assert "sepanjang tidak dimaknai mencakup frasa, “atau 2 (dua) hari" in short
    labor_law = (
        "Pasal 164 ayat (3) Undang-Undang Nomor 13 Tahun 2003 tentang Ketenagakerjaan "
        "(Lembaran Negara Republik Indonesia Tahun 2003 Nomor 39, Tambahan Lembaran Negara "
        "Republik Indonesia Nomor 4279) bertentangan"
    )
    assert abbreviate(labor_law) == "Pasal 164 ayat (3) UU 13/2003 bertentangan"


def test_a_conditional_ruling_leaves_the_provision_in_force_with_the_courts_reading():
    assert reading(WEEKLY_REST, MK168) == (
        "Menurut Putusan MK 168/PUU-XXI/2023, Pasal 79 ayat (2) huruf b yang menyatakan, "
        "“istirahat mingguan 1 (satu) hari untuk 6 (enam) hari kerja dalam 1 (satu) minggu” hanya "
        "berlaku jika dimaknai mencakup frasa “atau 2 (dua) hari untuk 5 (lima) hari kerja dalam "
        "1 (satu) minggu”."
    )
    assert reading(MINIMUM, MK168) == (
        "Menurut Putusan MK 168/PUU-XXI/2023, frasa “diberikan dengan ketentuan sebagai berikut” "
        "dalam Pasal 156 ayat (2) hanya berlaku jika dimaknai “paling sedikit”."
    )
    assert meaning_of(MINIMUM) == "“paling sedikit”" and ayat_of(MINIMUM) == "2"


def test_a_ruling_without_a_condition_strikes_the_words():
    assert reading(WORD_STRUCK, MK168) == (
        "Menurut Putusan MK 168/PUU-XXI/2023, kata “dapat” dalam Pasal 79 ayat (5) tidak berlaku "
        "lagi (tidak mempunyai kekuatan hukum mengikat): baca ketentuan itu tanpa kata-kata "
        "tersebut."
    )
    assert meaning_of(WORD_STRUCK) is None and ayat_of(WORD_STRUCK) == "5"


def test_the_phrase_named_after_sepanjang_is_what_gets_the_reading():
    closed = (
        "Menyatakan Pasal 164 ayat (3) Undang-Undang Nomor 13 Tahun 2003 tentang Ketenagakerjaan "
        "(Lembaran Negara Republik Indonesia Tahun 2003 Nomor 39, Tambahan Lembaran Negara "
        "Republik Indonesia Nomor 4279) bertentangan dengan Undang-Undang Dasar Negara Republik "
        "Indonesia Tahun 1945 sepanjang frasa “perusahaan tutup” tidak dimaknai “perusahaan tutup "
        "permanen atau perusahaan tutup tidak untuk sementara waktu”;"
    )
    assert reading(closed, "Putusan MK 19/PUU-IX/2011") == (
        "Menurut Putusan MK 19/PUU-IX/2011, frasa “perusahaan tutup” dalam Pasal 164 ayat (3) UU "
        "13/2003 hanya berlaku jika dimaknai “perusahaan tutup permanen atau perusahaan tutup "
        "tidak untuk sementara waktu”."
    )


def test_a_sentence_outside_the_formulas_is_shortened_but_not_interpreted():
    # MK 91/PUU-XVIII/2020: the making of the law is unconstitutional unless repaired in time.
    making = (
        "Menyatakan pembentukan Undang-Undang Nomor 11 Tahun 2020 tentang Cipta Kerja (Lembaran "
        "Negara Republik Indonesia Tahun 2020 Nomor 245, Tambahan Lembaran Negara Republik "
        "Indonesia Nomor 6573) bertentangan dengan Undang-Undang Dasar Negara Republik Indonesia "
        "Tahun 1945 dan tidak mempunyai kekuatan hukum mengikat secara bersyarat sepanjang tidak "
        "dimaknai “tidak dilakukan perbaikan dalam waktu 2 (dua) tahun sejak putusan ini "
        "diucapkan”;"
    )
    court = "Putusan MK 91/PUU-XVIII/2020"
    assert reading(making, court).startswith(f"{court}: Menyatakan pembentukan UU 11/2020 ")
    assert reading("Menolak permohonan para Pemohon untuk selain dan selebihnya.", court) == (
        f"{court}: Menolak permohonan para Pemohon untuk selain dan selebihnya."
    )


def test_only_a_ruling_that_strikes_words_is_written_into_the_text():
    assert struck(WORD_STRUCK) == ("5", "dapat")
    assert struck(MINIMUM) is None and struck(WEEKLY_REST) is None  # the Court set a reading
    line = "(5) Perusahaan tertentu dapat memberikan istirahat panjang."
    assert without(line, "dapat") == "(5) Perusahaan tertentu memberikan istirahat panjang."
    assert without("dapat diberikan dan dapat dicabut", "dapat") is None  # which of the two?
    assert without("pendapatan pekerja", "dapat") is None  # inside another word
