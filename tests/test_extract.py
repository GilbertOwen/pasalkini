from pasalkini.ingest.extract import clean_page


def test_removes_running_header_page_number_and_stamp():
    page = "PRESIDEN\nREPUBLIK INDONESIA\n- 21 -\nPasal 52\n(1) Perjanjian kerja\nSK No 031791 A\n"
    assert clean_page(page) == ["Pasal 52", "(1) Perjanjian kerja"]


def test_removes_ocr_header_variants_and_ln_header():
    page = "PRESIDEi{\nREP1JBLIK INDONESIA\n-9 -\nPasal 10\n"
    assert clean_page(page) == ["Pasal 10"]
    assert clean_page("2021, No.45\n-9-\nPasal 11\n") == ["Pasal 11"]


def test_removes_catchword_at_bottom_of_page():
    page = "Pasal 54\n(2) Ketentuan dalam perjanjian kerja.\n(3) Perjanjian ...\n"
    assert clean_page(page) == ["Pasal 54", "(2) Ketentuan dalam perjanjian kerja."]
    assert clean_page("Pasal 1\nteks\n(5) Pemerintah. . .\n") == ["Pasal 1", "teks"]


def test_removes_bare_page_number_only_at_top():
    assert clean_page("57\nMenimbang bahwa\n", page_number=57) == ["Menimbang bahwa"]
    page = "Menimbang bahwa\nsatu\ndua\ntiga\nangka\n57\n"
    assert clean_page(page, page_number=57)[-1] == "57"


def test_keeps_a_stamp_like_sentence():
    assert clean_page("SK No 26 7278 A\nPasal 3\n") == ["Pasal 3"]
    assert clean_page("SK Nomor 5 tentang upah\n") == ["SK Nomor 5 tentang upah"]


def test_removes_peraturan_go_id_footer():
    assert clean_page("Pasal 89 dihapus. www.peraturan.go.id\n") == ["Pasal 89 dihapus."]
