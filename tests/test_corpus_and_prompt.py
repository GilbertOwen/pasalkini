from datetime import date

from pasalkini.answer.generate import build_user_message
from pasalkini.corpus import Chunk, chunks_of
from pasalkini.ingest.models import (
    AmarPoint,
    AmendmentPoint,
    Article,
    Ayat,
    EmbeddedArticle,
    ParsedDocument,
)
from pasalkini.sources import Instrument


def instrument(**changes) -> Instrument:
    fields = {
        "id": "uu-11-2020",
        "kind": "UU",
        "number": "11",
        "year": 2020,
        "title": "Cipta Kerja",
        "status": "active",
        "parse_scope": "Bab IV",
        "urls": {"bpk": "https://peraturan.bpk.go.id/Details/1"},
        "pdf_url": "https://peraturan.go.id/files/x.pdf",
        "text_layer": "typeset",
    }
    return Instrument(**(fields | changes))


def test_one_chunk_per_article_or_amendment_point():
    doc = ParsedDocument(
        instrument_id="uu-11-2020",
        text_layer="typeset",
        files={},
        articles=[
            Article(
                source_id="uu-11-2020/pasal-80",
                label="Pasal 80",
                number="80",
                intro="Dalam rangka penguatan perlindungan.",
                page_start=1,
                page_end=1,
            ),
            Article(
                source_id="uu-11-2020/pasal-81",
                label="Pasal 81",
                number="81",
                intro="Beberapa ketentuan diubah sebagai berikut:",
                points=[
                    AmendmentPoint(
                        source_id="uu-11-2020/pasal-81/angka-15",
                        number=15,
                        instruction="Ketentuan Pasal 59 diubah sehingga berbunyi sebagai berikut:",
                        articles=[
                            EmbeddedArticle(
                                label="Pasal 59",
                                number="59",
                                ayat=[Ayat(number="1", text="PKWT hanya dapat dibuat.")],
                                page_start=2,
                                page_end=2,
                            )
                        ],
                        page_start=2,
                        page_end=2,
                    )
                ],
                page_start=2,
                page_end=2,
            ),
        ],
    )
    chunks = chunks_of(doc, instrument())
    assert [c.source_id for c in chunks] == ["uu-11-2020/pasal-80", "uu-11-2020/pasal-81/angka-15"]
    assert chunks[1].title == "UU 11/2020 Pasal 81 angka 15"
    assert chunks[1].text.endswith("Pasal 59\n(1) PKWT hanya dapat dibuat.")


def test_mk_ruling_points_become_chunks():
    doc = ParsedDocument(
        instrument_id="mk-168-puu-xxi-2023",
        text_layer="typeset",
        files={},
        amar=[AmarPoint(number=1, text="Mengabulkan permohonan untuk sebagian;")],
    )
    mk = instrument(id="mk-168-puu-xxi-2023", kind="PUTUSAN_MK", number="168/PUU-XXI/2023")
    [chunk] = chunks_of(doc, mk)
    assert (chunk.source_id, chunk.title) == (
        "mk-168-puu-xxi-2023/amar-1",
        "Putusan MK 168/PUU-XXI/2023 amar 1",
    )


def test_prompt_states_the_date_only_when_it_comes_from_the_date_picker():
    chunk = Chunk("uu-13-2003/pasal-59", "uu-13-2003", "UU 13/2003 Pasal 59", "Teks pasal.", 1)
    with_date, _ = build_user_message("Pertanyaan?", date(2019, 6, 1), [chunk], 2500)
    without, _ = build_user_message("Pertanyaan?", None, [chunk], 2500)
    assert with_date.startswith("Tanggal yang relevan: 2019-06-01")
    assert "Tanggal" not in without
    assert "[uu-13-2003/pasal-59] UU 13/2003 Pasal 59\nTeks pasal." in without


def test_long_chunks_are_cut_in_the_prompt():
    chunk = Chunk("x/pasal-1", "x", "X Pasal 1", "a" * 50, 1)
    message, truncated = build_user_message("Q?", None, [chunk], 10)
    assert truncated == 1 and "a" * 10 + " …" in message and "a" * 11 not in message
