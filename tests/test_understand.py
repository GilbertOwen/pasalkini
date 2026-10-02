from datetime import date

from pasalkini.answer.calculate import months_before, wages_in
from pasalkini.answer.llm import ChatOptions, Reply
from pasalkini.answer.understand import (
    decide_date,
    named_provisions,
    relative_date,
    understand,
)

TODAY = date(2026, 10, 1)


def test_a_date_in_the_question_wins_over_the_date_picker():
    assert decide_date("Saya di-PHK Maret 2019", date(2024, 1, 1), TODAY) == (
        date(2019, 3, 15),
        "pertanyaan",
    )
    assert decide_date("Berapa lama cuti?", date(2024, 1, 1), TODAY) == (
        date(2024, 1, 1),
        "pemilih_tanggal",
    )
    assert decide_date("Berapa lama cuti?", None, TODAY) == (TODAY, "hari_ini")


def test_relative_dates():
    assert relative_date("Saya di-PHK 2 tahun lalu", TODAY) == date(2024, 10, 1)
    assert relative_date("kontrak saya habis bulan lalu", TODAY) == date(2026, 9, 1)
    assert relative_date("setelah 4 tahun bekerja", TODAY) is None


def test_named_provisions():
    assert named_provisions("Apakah Pasal 59 UU 13/2003 masih berlaku?") == ["uu-13-2003/pasal-59"]
    assert named_provisions("Isi PP 35/2021 Pasal 40 ayat (2)?") == ["pp-35-2021/pasal-40"]
    assert named_provisions("Pasal 61A UU Nomor 13 Tahun 2003") == ["uu-13-2003/pasal-61a"]
    assert named_provisions("Apa isi Pasal 79 UU Ketenagakerjaan?") == ["uu-13-2003/pasal-79"]
    assert named_provisions("Berapa lama cuti tahunan?") == []


def test_an_article_named_apart_from_its_instrument_belongs_to_the_one_named():
    apart = "Pasal 90 UU Ketenagakerjaan (UU 13/2003) soal penangguhan upah, masih berlaku?"
    assert named_provisions(apart) == ["uu-13-2003/pasal-90"]
    assert named_provisions("Dalam PP 35/2021, apa isi Pasal 15?") == ["pp-35-2021/pasal-15"]
    # Two instruments and no pairing: which one the article belongs to is not guessed.
    assert named_provisions("Bandingkan UU 13/2003 dan PP 35/2021 soal Pasal 15.") == []


def test_the_year_in_a_laws_name_is_not_the_questions_date():
    long_form = "Apakah Pasal 59 Undang-Undang Nomor 13 Tahun 2003 masih berlaku?"
    assert decide_date(long_form, date(2024, 1, 1), TODAY) == (date(2024, 1, 1), "pemilih_tanggal")
    assert decide_date(long_form, None, TODAY) == (TODAY, "hari_ini")
    assert named_provisions(long_form) == ["uu-13-2003/pasal-59"]
    both = "Apa isi PP Nomor 35 Tahun 2021 tentang PKWT pada tahun 2022?"
    assert decide_date(both, None, TODAY) == (date(2022, 7, 1), "pertanyaan")


def test_invalid_model_output_falls_back_to_rules():
    def broken(options, messages, schema):
        return Reply(parsed=None, raw="{", prompt_tokens=0, output_tokens=0, seconds=0.0)

    u = understand("Apakah Pasal 64 masih berlaku?", None, TODAY, broken, ChatOptions("m"))
    assert (u.intent, u.method, u.history) == ("status", "rules", True)


def test_wages_and_months():
    assert wages_in("upah Rp6.000.000 per bulan") == [6_000_000]
    assert wages_in("gaji Rp5 juta") == [5_000_000]
    assert wages_in("tanpa angka") == []
    assert months_before(date(2023, 6, 1), 63) == date(2018, 3, 1)
    assert months_before(date(2023, 3, 31), 1) == date(2023, 2, 28)
