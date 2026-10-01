from pasalkini.corpus import Chunk
from pasalkini.retrieve.hybrid import expand_query, reciprocal_rank_fusion
from pasalkini.retrieve.lexical import BM25Index, keyword_title, tokenize
from pasalkini.sources import Topics


def chunk(source_id: str, text: str, title: str = "") -> Chunk:
    return Chunk(source_id, source_id.split("/")[0], title or source_id, text, 1)


def test_tokenize_stems_affixes_and_drops_stopwords():
    tokens = tokenize("Pemutusan hubungan kerja yang diputuskan oleh pengusaha")
    assert "yang" not in tokens and "oleh" not in tokens
    assert tokens.count("putus") == 2  # 'pemutusan' and 'diputuskan'


def test_bm25_finds_the_article_with_the_matching_words():
    chunks = [
        chunk("uu-1/pasal-78", "waktu kerja lembur paling banyak 3 jam dalam 1 hari"),
        chunk("uu-1/pasal-79", "istirahat mingguan 1 hari untuk 6 hari kerja"),
        chunk("uu-1/pasal-156", "uang pesangon dan uang penghargaan masa kerja"),
    ]
    hits = BM25Index(chunks).search("berapa jam lembur maksimal", 2)
    assert hits[0][0].source_id == "uu-1/pasal-78"


def test_bm25_respects_the_filter():
    chunks = [chunk("uu-1/pasal-78", "lembur 3 jam"), chunk("uu-2/pasal-9/angka-1", "lembur 4 jam")]
    hits = BM25Index(chunks).search("lembur", 5, allowed=lambda c: c.source_id.startswith("uu-2"))
    assert [c.source_id for c, _ in hits] == ["uu-2/pasal-9/angka-1"]


def test_keyword_title_drops_validity_dates():
    title = "UU 13/2003 Pasal 59 (berlaku 25 Maret 2003 s.d. 1 November 2020; bersyarat)"
    assert keyword_title(title) == "UU 13/2003 Pasal 59"
    assert keyword_title("Putusan MK 168/PUU-XXI/2023 amar 7 (diucapkan 31 Oktober 2024)") == (
        "Putusan MK 168/PUU-XXI/2023 amar 7"
    )


def test_rrf_rewards_chunks_found_by_both_rankings():
    a, b, c = chunk("x/pasal-1", "a"), chunk("x/pasal-2", "b"), chunk("x/pasal-3", "c")
    fused = reciprocal_rank_fusion([[(a, 0.9), (b, 0.8)], [(b, 12.0), (c, 3.0)]], 3)
    assert [ch.source_id for ch, _ in fused] == ["x/pasal-2", "x/pasal-1", "x/pasal-3"]


def test_expand_query_adds_the_legal_term():
    topics = Topics.model_validate(
        {
            "topics": [
                {
                    "id": "phk",
                    "name": "Pemutusan hubungan kerja (PHK)",
                    "description": "d",
                    "synonyms": ["dipecat", "di-phk"],
                },
                {"id": "pkwt", "name": "PKWT", "description": "d", "synonyms": ["kontrak"]},
            ]
        }
    )
    assert expand_query("Saya dipecat kemarin", topics).endswith("Pemutusan hubungan kerja (PHK)")
    assert expand_query("Berapa lama cuti?", topics) == "Berapa lama cuti?"
