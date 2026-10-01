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
