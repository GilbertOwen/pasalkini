from datetime import date

from pasalkini.evals.metrics import (
    ItemResult,
    extract_ids,
    matches,
    matches_expected,
    recall,
    score,
)
from pasalkini.evals.schema import EvalItem


def test_extract_ids_from_what_models_actually_write():
    raw = [
        "[pp-35-2021/pasal-8]",
        "{uu-13-2003/pasal-164}",
        '{"id": "[uu-11-2020/pasal-81/angka-66]", "text": "UU 11/2020 Pasal 81 angka 66"}',
        "UU 13/2003 Pasal 59",  # a title, not an ID
        "pp-35-2021/pasal-8",  # duplicate
    ]
    assert extract_ids(raw) == [
        "pp-35-2021/pasal-8",
        "uu-13-2003/pasal-164",
        "uu-11-2020/pasal-81/angka-66",
    ]


def test_label_matching_is_by_prefix_on_whole_segments():
    assert matches("uu-11-2020/pasal-81/angka-15", "uu-11-2020")
    assert matches("uu-13-2003/pasal-59", "uu-13-2003/pasal-59")
    assert not matches("uu-13-2003/pasal-59", "uu-13-2003/pasal-5")
    assert not matches("uu-13-2003", "uu-13-2003/pasal-59")


def test_uu_6_2023_text_lives_under_the_perppu():
    assert matches_expected("perppu-2-2022/pasal-81/angka-15", "uu-6-2023")
    assert not matches("perppu-2-2022/pasal-81/angka-15", "uu-6-2023")  # not for must_not_cite


def test_recall_counts_each_expected_label_once():
    ids = ["uu-13-2003/pasal-59", "uu-13-2003/pasal-60"]
    assert recall(ids, ["uu-13-2003/pasal-59", "pp-35-2021"]) == 0.5
    assert recall(ids, []) is None


def item(**changes) -> EvalItem:
    fields = {
        "id": "t-1",
        "question": "Berapa lama maksimal kontrak kerja?",
        "as_of": "2019-06-01",
        "category": "temporal_trap",
        "pair_id": "t",
        "topic": "pkwt",
        "expected_sources": ["uu-13-2003/pasal-59"],
        "must_not_cite": ["pp-35-2021"],
        "source": "draft",
        "split": "dev",
        "review": "needed",
    }
    return EvalItem(**(fields | changes))


def result(**changes) -> ItemResult:
    fields = {
        "id": "t-1",
        "category": "temporal_trap",
        "split": "dev",
        "as_of": date(2019, 6, 1),
        "question": "q",
        "retrieved": [("pp-35-2021/pasal-8", 0.8), ("uu-13-2003/pasal-59", 0.7)],
        "context_ids": ["pp-35-2021/pasal-8", "uu-13-2003/pasal-59"],
        "retrieval_ms": 10.0,
    }
    return ItemResult(**(fields | changes))


def test_score_flags_a_stale_citation():
    scored = score(result(json_ok=True, citations_raw=["[pp-35-2021/pasal-8]"]), item())
    assert scored.hit_at_5 and scored.stale_in_context
    assert scored.citations == ["pp-35-2021/pasal-8"]
    assert scored.stale_cited is True and scored.cited_expected is False
    assert scored.invalid_citations == []


def test_score_flags_an_invented_id():
    scored = score(result(json_ok=True, citations_raw=["pp-35-2021/pasal-43/angka-1"]), item())
    assert scored.invalid_citations == ["pp-35-2021/pasal-43/angka-1"]


def test_retrieval_only_result_has_no_citation_metrics():
    scored = score(result(), item())
    assert scored.stale_in_context is True and scored.stale_cited is None
