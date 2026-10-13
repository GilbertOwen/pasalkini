"""What the screens show: built from the service's answers, with everything escaped."""

from datetime import date

from test_answer_pipeline import COMPENSATION, PICKS_OLD, SAID, ScriptedChat, picks
from test_service import IN_2019, QUESTION, make_service

from pasalkini.ui.app import build, chips, day_of
from pasalkini.ui.render import (
    answer_html,
    calculation_html,
    diff_html,
    history_html,
    law_html,
    legal,
    provision_html,
    rupiah,
    version_label,
    versions_html,
)


def test_an_answer_shows_the_date_the_answer_and_what_it_rests_on(tmp_path):
    shown = answer_html(make_service(tmp_path).ask(QUESTION, IN_2019))
    # The date the answer is for leads, on its own line.
    assert '<span class="pk-date">1 Juni 2019</span>' in shown
    assert '<span class="pk-asof-source">(tanggal dari pemilih tanggal)</span>' in shown
    assert f'<div class="pk-said">{SAID}</div>' in shown
    assert "<h4>Sumber</h4>" in shown and "<blockquote>paling banyak 3 (tiga) jam" in shown
    assert "<h4>Perubahan sesudah tanggal itu</h4><ul><li>UU 13/2003 Pasal 78: diubah" in shown
    assert "Keyakinan: tinggi. Jenis pertanyaan: penjelasan aturan." in shown
    assert "Informasi hukum, bukan nasihat hukum." in shown
    assert "Kutipan terdekat" not in shown and "Aturan yang berlaku kemudian" not in shown


def test_a_refusal_shows_no_date_and_no_confidence(tmp_path):
    service = make_service(tmp_path, ScriptedChat(intent="di_luar_cakupan"))
    shown = answer_html(service.ask("Bagaimana pembagian harta gono-gini?"))
    assert "Menurut hukum yang berlaku" not in shown and "Keyakinan" not in shown
    assert "Sebaiknya tanyakan ke: instansi yang berwenang" in shown
    assert "Jenis pertanyaan: di luar cakupan." in shown


def test_a_cached_answer_says_so(tmp_path):
    service = make_service(tmp_path)
    service.ask(QUESTION, IN_2019)
    assert "dari simpanan" in answer_html(service.ask(QUESTION, IN_2019))


def test_text_from_a_question_or_a_document_is_escaped():
    assert legal("upah < UMP & <script>alert(1)</script>") == (
        '<div class="pk-legal">upah &lt; UMP &amp; &lt;script&gt;alert(1)&lt;/script&gt;</div>'
    )
    assert "<b>" not in diff_html("<b>lama</b>", "<b>baru</b>")


def test_each_cited_article_can_be_opened_as_it_stood_on_the_date(tmp_path):
    service = make_service(tmp_path)
    payload = service.ask(QUESTION, IN_2019)
    assert chips(payload) == [("UU 13/2003 Pasal 78", "uu-13-2003/pasal-78@2019-06-01")]
    shown = provision_html(service.provision("uu-13-2003/pasal-78", IN_2019))
    assert "paling banyak 3 (tiga) jam" in shown and "menurut keadaan pada 1 Juni 2019" in shown


def test_law_that_began_later_is_opened_as_it_stood_when_it_began(tmp_path):
    later = picks((COMPENSATION.source_id, "uang kompensasi diberikan dengan ketentuan"))
    service = make_service(tmp_path, ScriptedChat(selections=[picks(), later]))
    payload = service.ask("Apakah pekerja kontrak berhak uang kompensasi?", IN_2019)
    assert chips(payload) == [
        ("PP 35/2021 Pasal 16 (berlaku sejak 2 Februari 2021)", "pp-35-2021/pasal-16@2021-02-02")
    ]
    shown = answer_html(payload)
    assert "<h4>Aturan yang berlaku kemudian</h4>" in shown and "<h4>Sumber</h4>" not in shown
    early = provision_html(service.provision("pp-35-2021/pasal-16", IN_2019))
    assert "belum berlaku pada 1 Juni 2019" in early
    assert "tidak ada dalam sumber PasalKini" in provision_html(None)


def test_a_wording_that_had_ended_is_listed_apart_and_opened_as_it_stood(tmp_path):
    service = make_service(tmp_path, ScriptedChat(intent="status"))
    payload = service.ask("Apakah Pasal 78 UU 13/2003 masih berlaku?", None)
    assert [p["source_id"] for p in payload["citations"]] == ["uu-11-2020/pasal-81/angka-22"]
    assert [p["source_id"] for p in payload["earlier"]] == ["uu-13-2003/pasal-78"]
    shown = answer_html(payload)
    # Folded, after the sources: it is the record, not the answer.
    heading = '<details class="pk-fold"><summary>Bunyi sebelumnya (tidak berlaku lagi pada'
    assert shown.index("<h4>Sumber</h4>") < shown.index(heading)
    assert shown.index(heading) < shown.index("paling banyak 3 (tiga) jam")
    assert shown.index("<h4>Sumber</h4>") < shown.index("Riwayat pasal (oleh program)")
    # The article can be opened in both wordings: today's, and the first as it stood in 2003.
    assert chips(payload) == [
        ("UU 13/2003 Pasal 78", "uu-13-2003/pasal-78@2026-10-01"),
        (
            "UU 13/2003 Pasal 78 (bunyi sebelumnya, sejak 25 Maret 2003)",
            "uu-13-2003/pasal-78@2003-03-25",
        ),
    ]


def test_a_conditional_article_is_marked(tmp_path):
    found = make_service(tmp_path).provision("uu-13-2003/pasal-78", date(2022, 1, 1))
    assert '<span class="pk-badge pk-conditional">berlaku bersyarat</span>' in provision_html(found)


def test_an_articles_history_lists_every_version_once(tmp_path):
    found = make_service(tmp_path).history("uu-13-2003/pasal-78")
    shown = history_html(found, date(2026, 10, 1))
    assert "<h3>UU 13/2003 Pasal 78</h3>" in shown
    # One stretch of the bar per version, coloured by status, the first from 2003 to 2020.
    assert shown.count('class="pk-stretch') == 3
    assert '<span class="pk-stretch pk-conditional"' in shown
    assert 'style="left:0.00%;width:74.87%"' in shown
    # The timeline as code states it, one period per row, its source ID set apart.
    assert '<span class="pk-when">25 Maret 2003 s.d. 1 November 2020</span>' in shown
    assert '<code class="pk-id">uu-13-2003/pasal-78</code>' in shown
    full = versions_html(found)
    assert full.count("paling banyak 3 (tiga) jam") == 1
    assert full.count("paling lama 4 (empat) jam") == 1  # the third version repeats the second
    assert "Bunyi sama dengan versi sebelumnya" in full
    labels = [version_label(n, v) for n, v in enumerate(found["versions"], start=1)]
    assert labels == [
        "1. berlaku 25 Maret 2003 s.d. 1 November 2020 · UU 13/2003",
        "2. berlaku 2 November 2020 s.d. 24 November 2021 · UU 11/2020",
        "3. berlaku sejak 25 November 2021 · UU 11/2020 · berlaku bersyarat",
    ]


def test_changes_between_two_versions_are_marked_word_by_word():
    shown = diff_html("paling banyak 3 (tiga) jam", "paling lama 4 (empat) jam")
    assert shown.endswith(
        '<div class="pk-legal pk-diff">paling <del>banyak 3 (tiga)</del> '
        "<ins>lama 4 (empat)</ins> jam</div>"
    )
    assert "Dicoret: dihapus dari versi lama" in shown


def test_a_law_on_a_date_says_how_much_of_it_is_amended(tmp_path):
    service = make_service(tmp_path)
    shown = law_html(service.law("uu-13-2003", date(2022, 1, 1)))
    assert (
        "UU 13/2003 menurut bunyi yang berlaku pada 1 Januari 2022: 2 pasal, 1 di antaranya"
        in shown
    )
    assert "1 berlaku bersyarat" in shown and "<h4>Pasal 79</h4>" in shown
    assert "Tidak ada pasal PP 35/2021" in law_html(service.law("pp-35-2021", IN_2019))
    assert "tidak ada dalam sumber PasalKini" in law_html(None)


def test_a_calculation_is_a_table_with_the_basis_of_each_line(tmp_path):
    service = make_service(tmp_path)
    result = service.pkwt_compensation(date(2022, 1, 1), date(2023, 7, 1), 6_000_000)
    shown = calculation_html(result, 6_000_000)
    assert "<td>Uang kompensasi PKWT</td><td>18/12 x 1 bulan upah</td>" in shown
    assert '<td class="pk-amount">Rp9.000.000</td>' in shown
    assert "PP 35/2021 Pasal 16; pp-35-2021/pasal-15" in shown
    # The total comes first, as the date does in an answer.
    assert shown.index('<span class="pk-date">Rp9.000.000</span>') < shown.index("<table")
    assert "Menurut PP 35/2021, dengan masa kerja" in shown
    assert "bukan oleh AI" in shown and "pada 1 Juli 2023" in shown
    without_wage = service.pkwt_compensation(date(2022, 1, 1), date(2023, 7, 1), None)
    assert '<span class="pk-date">1,5 bulan upah</span>' in calculation_html(without_wage, None)
    too_early = service.pkwt_compensation(date(2020, 11, 5), date(2021, 1, 5), 6_000_000)
    assert "Perlu dicek manual" in calculation_html(too_early, 6_000_000)


def test_amounts_and_dates_from_the_form():
    assert rupiah(37_500_000) == "Rp37.500.000" and rupiah(None) == "–"
    assert day_of("2019-06-01") == day_of("2019-06-01 00:00:00") == date(2019, 6, 1)
    assert day_of("") is None and day_of(None) is None and day_of("kemarin") is None


def test_the_screens_are_built_from_the_service(tmp_path):
    blocks = build(make_service(tmp_path, ScriptedChat(selections=[PICKS_OLD])))
    labels = {getattr(block, "label", None) for block in blocks.blocks.values()}
    assert {"Tanya", "Riwayat Pasal", "Konsolidasi", "Kalkulator Pesangon"} <= labels
    assert {"Pertanyaan", "Alasan PHK", "Versi lama", "Tanggal PHK"} <= labels
