"""Unit tests for the parser rules, on small hand-made snippets (no PDFs needed)."""

import pytest

from pasalkini.ingest.extract import Line
from pasalkini.ingest.models import EmbeddedArticle
from pasalkini.ingest.parse import (
    build_articles,
    parse_amar,
    parse_ayat,
    parse_pasal_heading,
    repair_inserted_labels,
    segment,
    split_parts,
)


def lines(text: str, page: int = 1) -> list[Line]:
    return [Line(page, t.strip()) for t in text.strip().splitlines() if t.strip()]


def parse(text: str, roman: bool = False, first_any: bool = False, instrument: str = "x"):
    warnings: list[str] = []
    blocks = segment(lines(text), roman, first_any, "test", warnings)
    return build_articles(instrument, blocks, "test", warnings), warnings


# ---------------------------------------------------------------- headings


@pytest.mark.parametrize(
    ("text", "label", "value"),
    [
        ("Pasal 59", "59", 59),
        ("Pasal26", "26", 26),
        ("Pasal 8O", "80", 80),  # letter O read for zero
        ("Pasal 1 1", "11", 11),  # OCR split the digits
        ("Pasal 61A", "61A", 61),
        ("Pasa1 167", "167", 167),
        ("Pasal 88E}", "88E", 88),  # junk after the number
    ],
)
def test_pasal_heading_arabic(text, label, value):
    heading = parse_pasal_heading(text, roman_allowed=False)
    assert (heading.label, heading.value) == (label, value)


def test_pasal_heading_roman_only_when_allowed():
    assert parse_pasal_heading("Pasal II", roman_allowed=True).value == 2
    assert parse_pasal_heading("Pasal II", roman_allowed=False) is None


@pytest.mark.parametrize("text", ["Pasal 59 ayat (1)", "Pasal-pasal", "Pasal ini"])
def test_not_a_heading(text):
    assert parse_pasal_heading(text, roman_allowed=False) is None


# ---------------------------------------------------------------- ayat


def test_ayat_ocr_markers_repaired_by_order():
    body = lines("(1) PKWT dapat dibuat.\n(21 PKWT sebagaimana dimaksud.\n(3) Perjanjian harian.")
    intro, ayat = parse_ayat(body, True, "t", [])
    assert [a.number for a in ayat] == ["1", "2", "3"]
    assert ayat[1].text == "PKWT sebagaimana dimaksud."


def test_wrapped_reference_is_not_an_ayat():
    body = lines(
        "(1) Pengusaha membayar pesangon sesuai Pasal 156 ayat\n"
        "(4), maka selisihnya dibayar oleh pengusaha.\n"
        "(2) Dalam hal lain."
    )
    _, ayat = parse_ayat(body, True, "t", [])
    assert [a.number for a in ayat] == ["1", "2"]
    assert "(4), maka" in ayat[0].text


def test_inserted_ayat_and_list_items():
    body = lines("(1) Upah minimum.\n(1a) Pekerja tertentu:\na.\nsatu;\nb. dua.\n(2) Upah lain.")
    _, ayat = parse_ayat(body, True, "t", [])
    assert [a.number for a in ayat] == ["1", "1a", "2"]
    assert ayat[1].text == "Pekerja tertentu:\na. satu;\nb. dua."


def test_embedded_article_may_start_at_a_later_ayat():
    _, ayat = parse_ayat(lines("(3) Indeks tertentu.\n(4) Lainnya."), False, "t", [])
    assert [a.number for a in ayat] == ["3", "4"]


def test_article_without_ayat_keeps_intro():
    intro, ayat = parse_ayat(lines("Segala biaya ditanggung\npengusaha."), True, "t", [])
    assert ayat == [] and intro == "Segala biaya ditanggung pengusaha."


# ---------------------------------------------------------------- articles


def test_base_law_articles_and_context():
    articles, warnings = parse(
        """
        BAB I
        KETENTUAN UMUM
        Pasal 1
        Dalam undang-undang ini yang dimaksud dengan:
        1. Ketenagakerjaan adalah segala hal.
        Pasal 2
        (1) Perjanjian kerja dibuat sesuai ketentuan dalam
        Pasal 3
        ayat (1) huruf a.
        (2) Lainnya
        Pasal 3
        (1) Setiap pekerja berhak.
        """
    )
    assert [a.number for a in articles] == ["1", "2", "3"]
    assert articles[0].context == {"bab": "BAB I", "bab_title": "KETENTUAN UMUM"}
    assert "Pasal 3 ayat (1) huruf a." in articles[1].ayat[0].text  # wrapped reference kept
    assert len(warnings) == 1 and "not taken as a heading" in warnings[0]  # logged for review


def test_heading_after_line_without_period():
    articles, _ = parse(
        "Pasal 1\n(1) Diatur\n(2) Jabatan diatur dengan Keputusan Menteri\n"
        "Pasal 2\n(1) Pemberi kerja."
    )
    assert [a.number for a in articles] == ["1", "2"]


AMENDING = """
BAB IV
KETENAGAKERJAAN
Pasal 80
Beberapa ketentuan diubah.
Pasal 81
Beberapa ketentuan dalam Undang-Undang Nomor 13 Tahun 2003 diubah sebagai berikut:
1. Ketentuan Pasal 59 diubah sehingga berbunyi sebagai berikut:
Pasal 59
(1) Perjanjian kerja waktu tertentu.
(2) Tidak untuk pekerjaan tetap.
Pasal 64 dihapus.
3. Di antara Pasal 61 dan Pasal 62 disisipkan 1 (satu) pasal, yakni Pasal 61A sehingga
berbunyi sebagai berikut:
Pasal 614
Dalam hal PKWT berakhir, pengusaha wajib memberikan kompensasi.
4. Pasal 65 dihapus. 5. Pasal 66 dihapus.
Pasal 82
Beberapa ketentuan lain diubah.
"""


def test_amending_article_points_and_embedded_articles():
    articles, warnings = parse(AMENDING, first_any=True, instrument="uu-11-2020")
    assert [a.number for a in articles] == ["80", "81", "82"]
    points = articles[1].points
    assert [p.number for p in points] == [1, 2, 3, 4, 5]
    assert points[0].source_id == "uu-11-2020/pasal-81/angka-1"
    assert [e.number for e in points[0].articles] == ["59"]
    assert [a.number for a in points[0].articles[0].ayat] == ["1", "2"]
    assert points[1].number_inferred and points[1].instruction == "Pasal 64 dihapus."
    assert [e.number for e in points[2].articles] == ["61A"]  # '614' repaired from 'yakni'
    assert points[4].instruction == "Pasal 66 dihapus."  # merged line split
    assert any("relabelled" in w for w in warnings)


def test_skipped_point_numbers_are_recovered():
    articles, warnings = parse(
        "Pasal 1\nDiubah sebagai berikut:\n1. Pasal 2 dihapus.\n3. Pasal 4 dihapus.\n"
        "4. Ketentuan Pasal 5 diubah sehingga berbunyi sebagai berikut:\nPasal 5\nTeks."
    )
    assert [p.number for p in articles[0].points] == [1, 3, 4]
    assert any("2–2 not found" in w for w in warnings)


def test_lowercase_continuation_is_not_a_new_point():
    articles, _ = parse(
        "Pasal I\nDiubah sebagai berikut:\n"
        "1. Ketentuan ayat (1) Pasal 25 diubah dan\n"
        "ketentuan Pasal 25 ayat (4) dihapus, sehingga berbunyi sebagai berikut:\n"
        "Pasal 25\n(1) Upah.\nPasal II\nMulai berlaku.",
        roman=True,
    )
    assert [a.number for a in articles] == ["I", "II"]
    assert len(articles[0].points) == 1


def test_roman_own_articles_with_arabic_embedded():
    articles, _ = parse(
        "Pasal I\nBeberapa ketentuan diubah sebagai berikut:\n"
        "Ketentuan Pasal 26 diubah sehingga berbunyi sebagai berikut:\n"
        "Pasal26\n(1) Penyesuaian.\nPasal II\nPeraturan Pemerintah ini mulai berlaku.",
        roman=True,
    )
    assert [a.number for a in articles] == ["I", "II"]
    point = articles[0].points[0]
    assert point.number_inferred and [e.number for e in point.articles] == ["26"]


def test_repair_only_uses_list_after_yakni():
    embedded = [
        EmbeddedArticle(label="Pasal 9O", number="9O", page_start=1, page_end=1),
        EmbeddedArticle(label="Pasal 90A", number="90A", page_start=1, page_end=1),
    ]
    instruction = (
        "Di antara Pasal 9O dan Pasal 91 disisipkan 2 (dua) pasal, yakni Pasal 90A dan 90B"
    )
    repair_inserted_labels(instruction, embedded, "t", [])
    assert [e.number for e in embedded] == ["9O", "90A"]  # list incomplete: leave as parsed


# ---------------------------------------------------------------- parts and rulings


def test_split_parts_with_ocr_closing_and_penjelasan():
    doc = lines(
        "Pasal 1\nTeks.\norang mengetahuinya, memerintahkar,\nDitetapkan di Jakarta\n"
        "PENJET,ASAN\nATAS\nI. UMUM\nUmum.\nII. PASAL DEMI PASAL\nPasal 1\nCukup jelas."
    )
    body, closing, penjelasan = split_parts(doc)
    assert [ln.text for ln in body] == ["Pasal 1", "Teks."]
    assert closing[1].text == "Ditetapkan di Jakarta"
    assert penjelasan[0].text == "PENJET,ASAN"


def test_amar_numbered_and_bulleted():
    numbered = lines(
        "Mengadili:\n1. Mengabulkan permohonan;\n2. Menyatakan pasal\nini;\nDemikian diputus"
    )
    amar, _ = parse_amar(numbered, "t", [])
    assert [(a.number, a.text) for a in amar] == [
        (1, "Mengabulkan permohonan;"),
        (2, "Menyatakan pasal ini;"),
    ]
    bullets = lines(
        "Mengadili,\nMenyatakan:\n• Permohonan dikabulkan;\n• Menolak lainnya;\nDemikian diputus"
    )
    amar, _ = parse_amar(bullets, "t", [])
    assert [a.text for a in amar] == ["Permohonan dikabulkan;", "Menolak lainnya;"]
