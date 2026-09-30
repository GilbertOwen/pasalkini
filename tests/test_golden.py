from collections import defaultdict

import pytest
from pydantic import ValidationError

from pasalkini.evals.schema import Category, EvalItem, load_golden
from pasalkini.sources import load_manifest, load_topics

ITEMS = load_golden()


@pytest.fixture(scope="module")
def manifest():
    return load_manifest()


def test_ids_are_unique():
    ids = [item.id for item in ITEMS]
    assert len(ids) == len(set(ids))


def test_at_least_ten_temporal_traps():
    traps = [item for item in ITEMS if item.category is Category.TEMPORAL_TRAP]
    assert len(traps) >= 10


def test_pairs_ask_the_same_question_at_different_dates():
    pairs = defaultdict(list)
    for item in ITEMS:
        if item.pair_id:
            pairs[item.pair_id].append(item)
    assert pairs, "no pairs found"
    for pair_id, members in pairs.items():
        assert len(members) >= 2, f"{pair_id} has only one item"
        assert len({m.question for m in members}) == 1, f"{pair_id}: questions differ"
        assert len({m.as_of for m in members}) == len(members), f"{pair_id}: repeated as_of"
        assert len({m.split for m in members}) == 1, f"{pair_id}: members in different splits"


def test_topics_exist():
    topic_ids = load_topics().ids()
    for item in ITEMS:
        assert item.topic is None or item.topic in topic_ids, f"{item.id}: unknown topic"


def test_cited_instruments_exist(manifest):
    for item in ITEMS:
        unknown = item.cited_instruments() - manifest.ids()
        assert not unknown, f"{item.id}: unknown instruments {sorted(unknown)}"


def test_no_expected_source_that_did_not_exist_yet(manifest):
    """An instrument can't be expected before it took effect.

    Uses verified dates when they exist. Otherwise falls back to the year in the number, which
    catches less: Perppu 2/2022 dates from 30 December 2022, so the year alone can't exclude it
    for mid-2022 questions. MK case numbers carry the filing year, so they are skipped until
    their dates are verified.
    """
    for item in ITEMS:
        for instrument_id in {sid.split("/")[0] for sid in item.expected_sources}:
            instrument = manifest.get(instrument_id)
            if instrument.dates_verified:
                assert instrument.in_force_on <= item.as_of, (
                    f"{item.id}: {instrument_id} took effect on {instrument.in_force_on}"
                )
            elif instrument.year is not None and instrument.kind != "PUTUSAN_MK":
                assert instrument.year <= item.as_of.year, (
                    f"{item.id}: {instrument_id} is from {instrument.year}"
                )


def test_test_split_is_roughly_a_third():
    share = sum(item.split == "test" for item in ITEMS) / len(ITEMS)
    assert 0.2 <= share <= 0.4


@pytest.mark.parametrize("item", ITEMS, ids=lambda item: item.id)
def test_item_reviewed(item):
    if item.review == "needed":
        pytest.skip("needs human review")
    assert item.expected_points


def test_reviewed_item_requires_answers():
    with pytest.raises(ValidationError):
        EvalItem(
            id="x-1",
            question="Pertanyaan contoh yang cukup panjang?",
            as_of="2020-01-01",
            category="stable_rule",
            topic="pkwt",
            source="human",
            split="dev",
            review="done",
        )


def test_abstain_category_must_abstain():
    with pytest.raises(ValidationError):
        EvalItem(
            id="x-2",
            question="Pertanyaan contoh yang cukup panjang?",
            as_of="2020-01-01",
            category="should_abstain",
            topic=None,
            should_abstain=False,
            source="draft",
            split="dev",
            review="needed",
        )


def test_expected_and_forbidden_must_not_overlap():
    with pytest.raises(ValidationError):
        EvalItem(
            id="x-3",
            question="Pertanyaan contoh yang cukup panjang?",
            as_of="2020-01-01",
            category="stable_rule",
            topic="pkwt",
            expected_sources=["uu-13-2003/pasal-59"],
            must_not_cite=["uu-13-2003/pasal-59"],
            source="draft",
            split="dev",
            review="needed",
        )
