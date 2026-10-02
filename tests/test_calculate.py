"""Reading the calculator's facts from a question, and stating its result in a sentence."""

from datetime import date
from decimal import Decimal

from pasalkini.answer.calculate import (
    about_severance,
    calculate,
    facts_schema,
    may_calculate,
    said_in,
    wages_in,
)
from pasalkini.answer.llm import ChatOptions, Reply
from pasalkini.tools.pesangon import reasons_on, table_articles

OPTIONS = ChatOptions("test")


def facts(day: date, **values):
    """A chat model that returns these facts."""
    given = {"jenis": "pesangon", "lama_tahun": 0, "lama_bulan": 0, "upah_bulanan": 0, **values}

    def chat(options, messages, schema):
        parsed = schema.model_validate(given)
        return Reply(parsed, parsed.model_dump_json(), 10, 5, 0.0)

    return chat


def test_which_questions_get_the_calculator_without_asking_for_a_calculation():
    asks = "Kalau saya di-PHK karena efisiensi, berapa kali ketentuan uang pesangon?"
    rights = "Saya di-PHK bulan Maret 2019 setelah 4 tahun bekerja. Apa saja hak saya?"
    resigned = "Apa saja hak pekerja yang mengundurkan diri atas kemauan sendiri?"
    contract = "Kontrak PKWT saya 12 bulan berakhir. Apakah saya berhak uang kompensasi?"
    assert all(map(may_calculate, [asks, rights, resigned, contract]))
    # About severance, so the articles with the tables are added, but no dismissal to compute.
    table = "Apakah besaran uang pesangon dalam tabel merupakan jumlah minimal?"
    assert about_severance(table) and not may_calculate(table)
    for other in [
        "Apakah pekerja yang terkena PHK mendapat Jaminan Kehilangan Pekerjaan?",
        "Apakah pekerja kontrak berhak mendapat uang kompensasi ketika kontraknya berakhir?",
        "Berapa hari cuti tahunan minimal?",
    ]:
        assert not may_calculate(other)


def test_the_reason_must_be_in_the_questions_own_words():
    question = "Saya di-PHK karena Perusahaan  melakukan efisiensi."
    assert said_in("perusahaan melakukan efisiensi", question) == "Perusahaan  melakukan efisiensi"
    assert said_in('"karena perusahaan melakukan efisiensi."', question)
    assert said_in("perusahaan pailit", question) is None
    assert said_in(None, question) is None and said_in("...", question) is None


def test_with_only_a_reason_the_result_is_the_multipliers():
    day = date(2022, 6, 1)
    question = "Kalau saya di-PHK karena efisiensi karena rugi, berapa kali ketentuan pesangon?"
    chat = facts(day, bukti_alasan="efisiensi karena rugi", alasan="efisiensi_karena_rugi")
    calculation = calculate(question, day, chat, OPTIONS, strict=False)
    assert calculation.wage is None and calculation.months is None
    assert calculation.sources == ["pp-35-2021/pasal-43", "pp-35-2021/pasal-40"]
    assert calculation.summary() == (
        "Menurut hitungan program untuk PHK dengan alasan “efisiensi karena perusahaan mengalami "
        "kerugian”: uang pesangon 0,5 kali ketentuan dan uang penghargaan masa kerja 1 kali "
        "ketentuan, ditambah uang penggantian hak. Untuk alasan lain dalam pasal yang sama: "
        "efisiensi untuk mencegah kerugian: uang pesangon 1 x, UPMK 1 x ketentuan."
    )
    text = calculation.text()
    assert "Upah sebulan: tidak disebut; masa kerja: tidak disebut" in text
    assert "- Uang pesangon: 0,5 x ketentuan tabel masa kerja (dasar:" in text


def test_with_the_length_of_service_the_result_is_months_of_wage():
    day = date(2019, 3, 15)
    question = "Saya di-PHK setelah 4 tahun bekerja karena perusahaan efisiensi. Apa hak saya?"
    chat = facts(day, lama_tahun=4, bukti_alasan="perusahaan efisiensi", alasan="tutup_efisiensi")
    calculation = calculate(question, day, chat, OPTIONS, strict=False)
    assert calculation.result.total_months == Decimal("13.8") and calculation.result.minimum
    assert calculation.summary().endswith(
        "paling sedikit 13,8 bulan upah (uang pesangon 10 bulan upah, uang penghargaan masa "
        "kerja 2 bulan upah, penggantian perumahan serta pengobatan dan perawatan 1,8 bulan "
        "upah), belum termasuk uang penggantian hak lain yang tidak dapat dihitung dari "
        "pertanyaan."
    )


def test_a_reason_without_severance_says_so():
    day = date(2020, 1, 15)
    question = "Saya mengundurkan diri setelah 3 tahun bekerja. Apa saja hak saya?"
    chat = facts(day, lama_tahun=3, bukti_alasan="mengundurkan diri", alasan="mengundurkan_diri")
    calculation = calculate(question, day, chat, OPTIONS, strict=False)
    assert calculation.summary() == (
        "Menurut hitungan program untuk PHK dengan alasan “pekerja mengundurkan diri atas "
        "kemauan sendiri”: tidak ada uang pesangon dan uang penghargaan masa kerja; yang menjadi "
        "hak adalah uang penggantian hak dan uang pisah."
    )
    text = calculation.text()
    assert "- Uang pesangon dan uang penghargaan masa kerja: tidak ada untuk alasan ini" in text
    assert "15%" not in text  # the housing and medical share is a share of nothing


def test_an_unsupported_reason_is_dropped_unless_a_calculation_was_asked_for():
    day = date(2022, 6, 1)
    question = "Apakah perusahaan boleh tidak membayar pesangon kepada pekerja yang di-PHK?"
    chat = facts(day, bukti_alasan="karena pailit", alasan="pailit")
    assert calculate(question, day, chat, OPTIONS, strict=False).error == (
        "alasan PHK tidak terbaca dari pertanyaan."
    )
    asked = calculate(question, day, chat, OPTIONS, strict=True)
    assert asked.error is None and asked.evidence is None and asked.result.reason_label


def test_the_schema_asks_for_the_evidence_before_the_reason_code():
    fields = list(facts_schema(sorted(reasons_on(date(2022, 6, 1)))).model_fields)
    assert fields.index("bukti_alasan") < fields.index("alasan")


def test_the_articles_with_the_severance_tables_on_a_date():
    assert table_articles(date(2019, 6, 1)) == ["uu-13-2003/pasal-156"]
    assert table_articles(date(2022, 6, 1)) == ["uu-13-2003/pasal-156", "pp-35-2021/pasal-40"]
    assert table_articles(date(2020, 12, 1)) == ["uu-13-2003/pasal-156"]  # between the two


def test_one_stated_amount_is_the_wage():
    assert wages_in("upah Rp6.000.000 per bulan") == [6_000_000]
    assert wages_in("gaji Rp 4,5 juta dan THR Rp4.500.000,00") == [4_500_000]
    assert wages_in("upah Rp750 ribu seminggu, lalu Rp3 juta sebulan") == [750_000, 3_000_000]


def test_rights_after_a_dismissal_are_asked_about_in_more_than_one_way():
    from pasalkini.answer.calculate import may_calculate

    assert may_calculate("Apa saja hak pekerja yang mengundurkan diri atas kemauan sendiri?")
    assert may_calculate("Kalau saya resign atas keinginan sendiri, saya dapat apa saja?")
    assert may_calculate("Karyawan yang di-PHK menerima apa saja dari perusahaan?")
    assert not may_calculate("Kalau saya resign, apakah saya dapat bekerja di perusahaan pesaing?")
