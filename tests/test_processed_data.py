"""Checks on the real parsed documents in data/processed.

data/ is git-ignored, so these tests are skipped until `uv run pasalkini download` and
`uv run pasalkini parse` have run on this machine.
"""

import json
import re

import pytest

from pasalkini.corpus import load_corpus
from pasalkini.evals.metrics import matches
from pasalkini.evals.schema import load_golden
from pasalkini.ingest.models import ParsedDocument
from pasalkini.paths import PROCESSED_DIR
from pasalkini.sources import load_manifest

BASE_REGULATIONS = ["uu-13-2003", "pp-35-2021", "pp-36-2021", "permenaker-7-2026"]
AMENDED_BAB_IV = ["uu-11-2020", "perppu-2-2022"]


def load(instrument_id: str) -> ParsedDocument:
    path = PROCESSED_DIR / f"{instrument_id}.json"
    if not path.exists():
        pytest.skip(f"{path.name} not parsed yet; run `uv run pasalkini parse`")
    return ParsedDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))


def ayat_order_ok(numbers: list[str]) -> bool:
    last = 0
    for n in numbers:
        value = int(re.match(r"\d+", n).group())
        if value not in (last, last + 1) or (value == last and n == str(value)):
            return False
        last = value
    return True


def test_uu_13_2003_has_all_193_articles_with_penjelasan():
    doc = load("uu-13-2003")
    assert [a.number for a in doc.articles] == [str(n) for n in range(1, 194)]
    assert all(a.penjelasan for a in doc.articles)
    assert "25 Maret 2003" in doc.closing


def test_uu_13_2003_pasal_59_has_eight_ayat():
    pasal_59 = next(a for a in load("uu-13-2003").articles if a.number == "59")
    assert [a.number for a in pasal_59.ayat] == [str(n) for n in range(1, 9)]
    assert pasal_59.context["bab"] == "BAB IX"


@pytest.mark.parametrize("instrument_id", BASE_REGULATIONS)
def test_base_regulation_is_continuous_and_ends_with_entry_into_force(instrument_id):
    doc = load(instrument_id)
    numbers = [int(a.number) for a in doc.articles]
    assert numbers == list(range(1, len(numbers) + 1))
    assert "mulai berlaku" in doc.articles[-1].full_text()
    for article in doc.articles:
        assert article.full_text() or article.points, f"{article.label} is empty"
        assert ayat_order_ok([a.number for a in article.ayat]), f"{article.label} ayat order"


@pytest.mark.parametrize("instrument_id", AMENDED_BAB_IV)
def test_cipta_kerja_bab_iv(instrument_id):
    doc = load(instrument_id)
    assert [a.number for a in doc.articles] == ["80", "81", "82", "83", "84"]
    assert all(a.penjelasan for a in doc.articles)
    pasal_81 = doc.articles[1]
    numbers = [p.number for p in pasal_81.points]
    assert numbers == list(range(1, len(numbers) + 1)), "Pasal 81 points must be continuous"
    point_15 = pasal_81.points[14]
    assert "Pasal 59" in point_15.instruction
    assert [e.number for e in point_15.articles] == ["59"]
    inserted = {
        e.number for p in pasal_81.points for e in p.articles if "disisipkan" in p.instruction
    }
    assert {"61A", "151A", "154A", "157A", "191A"} <= inserted


def test_perppu_restores_pasal_64():
    """UU 11/2020 deleted Pasal 64; Perppu 2/2022 put it back with new wording."""
    uu11 = load("uu-11-2020").articles[1].points
    perppu = load("perppu-2-2022").articles[1].points
    assert any(p.instruction.startswith("Pasal 64 dihapus") for p in uu11)
    assert any("Ketentuan Pasal 64 diubah" in p.instruction for p in perppu)


def test_mk_168_ruling():
    doc = load("mk-168-puu-xxi-2023")
    assert len(doc.amar) == 25
    assert doc.amar[0].text.startswith("Mengabulkan permohonan para Pemohon untuk sebagian")
    assert any("Pasal 81 angka" in point.text for point in doc.amar)


def test_uu_6_2023_is_only_the_enacting_articles():
    assert [a.number for a in load("uu-6-2023").articles] == ["1", "2"]


def test_golden_source_ids_exist():
    """Every article-, point- or ruling-level label matches at least one chunk of the corpus."""
    load("uu-13-2003")  # skip when nothing has been parsed yet
    chunk_ids = [chunk.source_id for chunk in load_corpus()]
    manifest_ids = load_manifest().ids()
    for item in load_golden():
        for label in item.expected_sources + item.must_not_cite:
            if "/" not in label or label.split("/")[0] not in manifest_ids:
                continue
            assert any(matches(c, label) for c in chunk_ids), f"{item.id}: {label} matches no chunk"
