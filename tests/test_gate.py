"""The retrieval gate: passes on its own baseline, fails on a drop, and refuses a stale fixture."""

import json
from datetime import date

import numpy as np
import pytest

from pasalkini.evals.gate import FIXTURE_PATH, check, keys_fingerprint, load_fixture, write_fixture
from pasalkini.evals.schema import EvalItem
from pasalkini.temporal.corpus import DatedChunk

TODAY = date(2026, 10, 2)


def chunk(source_id: str, text: str, start: str, end: str | None = None) -> DatedChunk:
    return DatedChunk(
        source_id=source_id,
        instrument_id=source_id.split("/")[0],
        title=source_id,
        text=text,
        page=0,
        provision_id="uu-13-2003/pasal-78",
        status="in_force",
        valid_from=date.fromisoformat(start),
        valid_to=date.fromisoformat(end) if end else None,
    )


def item(item_id: str, as_of: str, expected: list[str], forbidden: list[str], **fields) -> EvalItem:
    return EvalItem(
        id=item_id,
        question="Berapa jam lembur maksimal dalam sehari?",
        as_of=date.fromisoformat(as_of),
        category="stable_rule",
        topic=None,
        expected_sources=expected,
        must_not_cite=forbidden,
        source="draft",
        split="dev",
        review="needed",
        **fields,
    )


OLD = chunk("uu-13-2003/pasal-78", "lembur paling banyak 3 jam sehari", "2003-03-25", "2020-11-02")
NEW = chunk("uu-11-2020/pasal-81/angka-22", "lembur paling lama 4 jam sehari", "2020-11-02")
REST = chunk("uu-13-2003/pasal-79", "istirahat mingguan 1 hari", "2003-03-25")
CHUNKS = [OLD, NEW, REST]
CHUNK_VECTORS = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]], dtype=np.float32)
ITEMS = [
    item("lembur-2019", "2019-06-01", [OLD.source_id], [NEW.source_id]),
    item("lembur-2021", "2021-06-01", [NEW.source_id], [OLD.source_id]),
]
QUERY_VECTORS = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float32)


def fixture_at(tmp_path, items=ITEMS, **meta_changes):
    path = tmp_path / "retrieval.npz"
    write_fixture(path, items, CHUNKS, CHUNK_VECTORS, QUERY_VECTORS, "test", TODAY)
    if meta_changes:
        with np.load(path) as data:
            arrays = {name: data[name] for name in data.files}
        meta = json.loads(str(arrays["meta"]))
        meta["baseline"].update(meta_changes)
        arrays["meta"] = np.array(json.dumps(meta))
        np.savez_compressed(path, **arrays)
    return path


def test_the_snapshot_keeps_the_corpus_and_what_retrieval_scored_on_it(tmp_path):
    fixture = load_fixture(fixture_at(tmp_path))
    assert fixture.chunks == CHUNKS and set(fixture.queries) == {"lembur-2019", "lembur-2021"}
    # Each question finds the wording of its own date, and never the other one.
    assert fixture.meta["baseline"] == {
        "questions": 2,
        "with_expected_sources": 2,
        "recall_at_5": 1.0,
        "hit_at_5": 2,
        "stale_in_top_5": 0,
    }


def test_the_gate_passes_on_its_own_baseline(tmp_path):
    passed, lines = check(fixture_at(tmp_path), ITEMS)
    assert passed and lines[-1] == "Passed."
    assert "Recall@5          1.0000  (baseline 1.0000" in lines[1]


def test_a_drop_in_recall_fails_the_gate(tmp_path):
    # As if retrieval had found both expected sources when the fixture was made, and now one.
    forgotten = [ITEMS[0], item("lembur-2021", "2021-06-01", [REST.source_id + "/x"], [])]
    path = fixture_at(tmp_path, forgotten, recall_at_5=1.0)
    passed, lines = check(path, forgotten)
    assert not passed and "FAILED: Recall@5 dropped." in lines
    within = fixture_at(tmp_path, forgotten, recall_at_5=0.505)  # inside the tolerance
    assert check(within, forgotten)[0]


def test_text_that_did_not_apply_on_the_date_fails_the_gate(tmp_path):
    passed, lines = check(fixture_at(tmp_path, stale_in_top_5=-1), ITEMS)
    assert not passed
    assert "FAILED: more questions get text that did not apply on their date." in lines


def test_changed_answer_keys_ask_for_a_new_fixture(tmp_path):
    path = fixture_at(tmp_path)
    relabelled = [ITEMS[0], item("lembur-2021", "2021-06-01", [REST.source_id], [])]
    passed, lines = check(path, relabelled)
    assert not passed and "uv run pasalkini fixture" in lines[-1]
    # Marking a key as reviewed is not a change to what the gate measures.
    reviewed = [ITEMS[0], ITEMS[1].model_copy(update={"notes": "checked against the PDF"})]
    assert keys_fingerprint(reviewed) == keys_fingerprint(ITEMS)
    assert check(path, reviewed)[0]


def test_a_missing_fixture_is_not_a_pass(tmp_path):
    passed, lines = check(tmp_path / "none.npz", ITEMS)
    assert not passed and "uv run pasalkini fixture" in lines[0]


def test_the_committed_fixture_matches_the_answer_keys_and_passes():
    if not FIXTURE_PATH.exists():
        pytest.skip("no fixture yet; make one with `uv run pasalkini fixture`")
    passed, lines = check()
    assert passed, "\n".join(lines)
