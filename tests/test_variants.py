"""The reworded questions (evals/datasets/variants.jsonl): each asks what its original asks, and
what code reads from a question (its date, the articles it names, the wage) is still read."""

from datetime import date

import pytest

from pasalkini.answer.calculate import wages_in
from pasalkini.answer.understand import decide_date, named_provisions
from pasalkini.evals.schema import (
    GoldenFileError,
    load_all,
    load_golden,
    load_items,
    load_variants,
    read_variants,
)
from pasalkini.privacy.redact import redact

TODAY = date(2026, 10, 2)
GOLDEN = {item.id: item for item in load_golden()}
VARIANTS = load_variants()
PAIRS = [(GOLDEN[v.variant_of], item) for v, item in zip(read_variants(), VARIANTS, strict=True)]


def test_every_question_has_exactly_one_variant():
    originals = [v.variant_of for v in read_variants()]
    assert sorted(originals) == sorted(GOLDEN)
    ids = [item.id for item in VARIANTS]
    assert len(set(ids)) == len(ids) and not set(ids) & set(GOLDEN)
    assert set(load_all()) == set(GOLDEN) | set(ids)
    assert load_items("variants") == VARIANTS and load_items("golden") == list(GOLDEN.values())


def test_only_the_wording_is_new():
    for original, variant in PAIRS:
        assert variant.question != original.question
        same = variant.model_copy(
            update={"id": original.id, "question": original.question, "notes": original.notes}
        )
        assert same == original, variant.id
        assert variant.notes.endswith(f"of {original.id}.")


@pytest.mark.parametrize(("original", "variant"), PAIRS, ids=[v.id for _, v in PAIRS])
def test_the_date_the_law_is_taken_from_is_unchanged(original, variant):
    """A date written in the question must still be read from it, and a variant of a question
    without one must not bring one in: it would override the date picker."""
    hint = None if original.date_in_question else original.as_of
    as_of, source = decide_date(variant.question, hint, TODAY)
    assert as_of == original.as_of
    assert (source == "pertanyaan") == original.date_in_question


@pytest.mark.parametrize(("original", "variant"), PAIRS, ids=[v.id for _, v in PAIRS])
def test_what_code_reads_from_the_question_is_unchanged(original, variant):
    assert named_provisions(variant.question) == named_provisions(original.question)
    assert wages_in(variant.question) == wages_in(original.question)
    assert redact(variant.question).clean


def test_a_variant_of_an_unknown_question_is_an_error(tmp_path):
    path = tmp_path / "variants.jsonl"
    path.write_text(
        '{"id": "x-v", "variant_of": "tidak-ada", "style": "santai", '
        '"question": "Berapa jam lembur maksimal sehari?"}\n',
        encoding="utf-8",
    )
    with pytest.raises(GoldenFileError, match="x-v is a variant of an unknown item"):
        load_variants(path)
    with pytest.raises(ValueError, match="unknown dataset"):
        load_items("lain")
