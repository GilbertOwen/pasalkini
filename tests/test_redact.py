"""Redaction: personal data goes, the facts a labor-law question is about stay."""

import pytest

from pasalkini.privacy.redact import redact


@pytest.mark.parametrize(
    ("text", "expected", "found"),
    [
        (
            "NIK saya 3201234567890001, bisa cek status BPJS?",
            "NIK saya [NIK], bisa cek status BPJS?",
            {"nik": 1},
        ),
        ("KTP 3201 2345 6789 0001 atas PHK", "KTP [NIK] atas PHK", {"nik": 1}),
        ("NPWP 12.345.678.9-012.345 dipotong", "NPWP [NPWP] dipotong", {"npwp": 1}),
        ("NPWP 123456789012345 dipotong", "NPWP [NPWP] dipotong", {"npwp": 1}),
        ("NIP 198501012010011001", "NIP [NOMOR]", {"nomor": 1}),
        ("Hubungi saya di 0812-3456-7890 ya", "Hubungi saya di [TELEPON] ya", {"telepon": 1}),
        ("WA +62 812 3456 7890", "WA [TELEPON]", {"telepon": 1}),
        ("WA 6281234567890.", "WA [TELEPON].", {"telepon": 1}),
        ("telepon kantor (021) 555-1234", "telepon kantor [TELEPON]", {"telepon": 1}),
        ("kirim ke budi.s+kerja@mail.co.id segera", "kirim ke [EMAIL] segera", {"email": 1}),
        (
            "Nama saya Budi Santoso, saya di-PHK kemarin",
            "Nama saya [NAMA], saya di-PHK kemarin",
            {"nama": 1},
        ),
        (
            "surat atas nama Siti Aminah dan email siti@contoh.id, HP 081234567890",
            "surat atas nama [NAMA] dan email [EMAIL], HP [TELEPON]",
            {"nama": 1, "email": 1, "telepon": 1},
        ),
    ],
)
def test_personal_data_is_replaced_by_what_it_was(text, expected, found):
    redacted = redact(text)
    assert redacted.text == expected
    assert redacted.found == found and not redacted.clean


@pytest.mark.parametrize(
    "text",
    [
        "Saya bekerja 7 tahun dengan gaji Rp5.000.000 lalu di-PHK. Berapa pesangon saya?",
        "Upah saya Rp 10.812.345.678 setahun",  # '0.812.345.678' is not a phone number
        "Gaji 4500000 sebulan, PHK tanggal 08-12-2021 pukul 10.00",
        "Apakah Pasal 59 UU 13/2003 masih berlaku pada 2021-03-15?",
        "Kontrak 0,5 tahun sejak 01-02-2021 sampai 31-07-2021",
        "Putusan MK 168/PUU-XXI/2023 dan PP 35/2021 Pasal 40 ayat (2)",
        "Lembaran Negara Republik Indonesia Tahun 2003 Nomor 39, Tambahan Nomor 4279",
        "nama saya tidak tercantum di daftar penerima THR",
        "Uang pesangon 628.000.000 atau Rp 62.500.000?",
    ],
)
def test_amounts_dates_and_article_numbers_survive(text):
    redacted = redact(text)
    assert redacted.text == text
    assert redacted.clean and redacted.found == {}


def test_every_find_is_counted():
    redacted = redact("HP 081234567890 atau 0857-1111-2222")
    assert redacted.text == "HP [TELEPON] atau [TELEPON]"
    assert redacted.found == {"telepon": 2}
