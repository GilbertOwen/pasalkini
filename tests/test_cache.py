"""The answer cache: an answer is reused only while nothing it was made from has changed."""

from datetime import date

from pasalkini.cache import AnswerCache, answer_key, code_fingerprint

BASE = {
    "question": "Berapa jam lembur maksimal?",
    "as_of": date(2019, 6, 1),
    "as_of_source": "pemilih_tanggal",
    "corpus": "abc",
    "law_as_of": date(2026, 4, 1),
    "model": "qwen3.5:4b",
    "code": "c0de",
}


def test_case_and_spacing_of_the_question_do_not_matter():
    again = {**BASE, "question": "  berapa jam   LEMBUR maksimal? "}
    assert answer_key(**BASE) == answer_key(**again)


def test_anything_an_answer_is_made_from_changes_the_key():
    changes = {
        "question": "Berapa jam lembur maksimal seminggu?",
        "as_of": date(2021, 6, 1),
        "as_of_source": "pertanyaan",
        "corpus": "abd",
        "law_as_of": date(2026, 10, 6),  # a new law has taken effect
        "model": "qwen3.5:9b",
        "code": "c0df",
    }
    keys = {answer_key(**{**BASE, name: value}) for name, value in changes.items()}
    assert len(keys) == len(changes) and answer_key(**BASE) not in keys


def test_the_code_fingerprint_is_stable_within_a_run():
    assert code_fingerprint() == code_fingerprint() and len(code_fingerprint()) == 16


def test_answers_are_stored_and_found_again(tmp_path):
    cache = AnswerCache(tmp_path / "cache" / "answers.db")
    assert cache.get("k") is None and len(cache) == 0
    cache.put("k", {"answer": "Paling banyak 3 jam sehari.", "citations": []})
    assert cache.get("k") == {"answer": "Paling banyak 3 jam sehari.", "citations": []}
    cache.put("k", {"answer": "baru"})
    assert cache.get("k") == {"answer": "baru"} and len(cache) == 1
    # A second instance on the same file sees it: the cache outlives the process.
    assert AnswerCache(tmp_path / "cache" / "answers.db").get("k") == {"answer": "baru"}
    assert cache.clear() == 1 and len(cache) == 0


def test_the_oldest_answers_go_first_when_the_cache_is_full(tmp_path):
    cache = AnswerCache(tmp_path / "answers.db", max_entries=3)
    for n in range(5):
        cache.put(f"k{n}", {"n": n})
    assert len(cache) == 3
    assert [cache.get(f"k{n}") for n in range(5)] == [None, None, {"n": 2}, {"n": 3}, {"n": 4}]
