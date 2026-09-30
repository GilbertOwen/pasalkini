from datetime import date

import numpy as np

from pasalkini.retrieve.dense import DenseIndex
from pasalkini.retrieve.temporal import extract_date, retrieve
from pasalkini.temporal.corpus import DatedChunk


def test_extract_date_from_indonesian_text():
    assert extract_date("Saya di-PHK bulan Maret 2019 setelah 4 tahun") == date(2019, 3, 15)
    assert extract_date("Kontrak ditandatangani 5 Januari 2022") == date(2022, 1, 5)
    assert extract_date("Apa aturan pada tahun 2020?") == date(2020, 7, 1)
    assert extract_date("Apakah Pasal 90 UU 13/2003 masih berlaku?") is None


def chunk(source_id: str, start: str, end: str | None) -> DatedChunk:
    return DatedChunk(
        source_id=source_id,
        instrument_id=source_id.split("/")[0],
        title=source_id,
        text=source_id,
        page=0,
        provision_id="uu-1/pasal-1",
        status="in_force",
        valid_from=date.fromisoformat(start),
        valid_to=date.fromisoformat(end) if end else None,
    )


OLD = chunk("uu-1/pasal-1", "2003-03-25", "2020-11-02")
NEW = chunk("uu-2/pasal-9/angka-1", "2020-11-02", None)
FUTURE = chunk("pp-3/pasal-4", "2030-01-01", None)
INDEX = DenseIndex(
    model="test",
    chunks=[OLD, NEW, FUTURE],
    vectors=np.array([[1.0, 0.0], [0.9, 0.1], [0.95, 0.05]], dtype=np.float32),
    fingerprint="test",
)
QUERY = np.array([1.0, 0.0], dtype=np.float32)


def ids(retrieval) -> list[str]:
    return [c.source_id for c, _ in retrieval.hits]


def test_date_filter_keeps_only_what_applied_on_the_date():
    r = retrieve(
        INDEX,
        QUERY,
        "Berapa lama?",
        5,
        date_hint=date(2019, 6, 1),
        date_filter=True,
        history_cues=True,
    )
    assert ids(r) == ["uu-1/pasal-1"] and r.mode == "as_of"
    r = retrieve(
        INDEX,
        QUERY,
        "Berapa lama?",
        5,
        date_hint=date(2022, 6, 1),
        date_filter=True,
        history_cues=True,
    )
    assert ids(r) == ["uu-2/pasal-9/angka-1"]


def test_history_question_sees_old_versions_but_not_future_ones():
    r = retrieve(
        INDEX,
        QUERY,
        "Apa yang berubah?",
        5,
        date_hint=date(2022, 6, 1),
        date_filter=True,
        history_cues=True,
    )
    assert set(ids(r)) == {"uu-1/pasal-1", "uu-2/pasal-9/angka-1"} and r.mode == "history"


def test_date_read_from_the_question_when_no_date_picker():
    r = retrieve(
        INDEX,
        QUERY,
        "Saya di-PHK Maret 2019",
        5,
        date_hint=None,
        date_filter=True,
        history_cues=True,
    )
    assert r.as_of == date(2019, 3, 15) and ids(r) == ["uu-1/pasal-1"]


def test_without_filter_everything_is_ranked():
    r = retrieve(
        INDEX,
        QUERY,
        "Berapa lama?",
        5,
        date_hint=date(2019, 6, 1),
        date_filter=False,
        history_cues=False,
    )
    assert ids(r) == ["uu-1/pasal-1", "pp-3/pasal-4", "uu-2/pasal-9/angka-1"] and r.mode == "plain"
