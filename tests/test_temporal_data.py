"""The temporal model built from the real documents, checked against facts read in the primary
texts. Skipped until `uv run pasalkini build` has run on this machine."""

from datetime import date

import pytest

from pasalkini.temporal.model import Version
from pasalkini.temporal.store import DB_PATH, load_versions


@pytest.fixture(scope="module")
def versions() -> list[Version]:
    if not DB_PATH.exists():
        pytest.skip("temporal model not built; run `uv run pasalkini build`")
    return load_versions()


def on(versions: list[Version], pid: str, day: str) -> Version | None:
    found = [v for v in versions if v.provision_id == pid and v.valid_on(date.fromisoformat(day))]
    assert len(found) <= 1, f"{pid} has overlapping versions on {day}"
    return found[0] if found else None


def test_no_article_has_overlapping_versions(versions):
    by_article: dict[str, list[Version]] = {}
    for v in versions:
        by_article.setdefault(v.provision_id, []).append(v)
    for pid, mine in by_article.items():
        mine.sort(key=lambda v: v.valid_from)
        for earlier, later in zip(mine, mine[1:], strict=False):
            assert earlier.valid_to is not None and earlier.valid_to <= later.valid_from, pid
        assert all(v.text.strip() for v in mine), f"{pid} has an empty version"


def test_overtime_limit_over_time(versions):
    """UU 13/2003 Pasal 78: 3 h/14 h, then 4 h/18 h from UU 11/2020, restated by the Perppu."""
    assert "3 (tiga) jam" in on(versions, "uu-13-2003/pasal-78", "2019-06-01").text
    v2021 = on(versions, "uu-13-2003/pasal-78", "2021-06-01")
    assert "4 (empat) jam" in v2021.text and v2021.source_id == "uu-11-2020/pasal-81/angka-22"
    assert on(versions, "uu-13-2003/pasal-78", "2023-06-01").source_id == (
        "perppu-2-2022/pasal-81/angka-24"
    )


def test_pasal_64_deleted_then_restated_then_conditional(versions):
    pid = "uu-13-2003/pasal-64"
    assert on(versions, pid, "2019-06-01").source_id == "uu-13-2003/pasal-64"
    deleted = on(versions, pid, "2021-06-01")
    assert deleted.status == "repealed" and deleted.source_id == "uu-11-2020/pasal-81/angka-18"
    restated = on(versions, pid, "2023-06-01")
    assert restated.status == "in_force" and restated.source_id == "perppu-2-2022/pasal-81/angka-18"
    assert "mk-168-puu-xxi-2023/amar-6" in on(versions, pid, "2025-06-01").rulings


def test_pkwt_compensation_exists_only_from_cipta_kerja(versions):
    pid = "uu-13-2003/pasal-61a"
    assert on(versions, pid, "2019-06-01") is None
    assert on(versions, pid, "2021-06-01").source_id == "uu-11-2020/pasal-81/angka-17"
    assert on(versions, pid, "2023-06-01").source_id == "perppu-2-2022/pasal-81/angka-17"


def test_pasal_164_ruling_then_deletion(versions):
    pid = "uu-13-2003/pasal-164"
    ruled = on(versions, pid, "2015-01-01")
    assert ruled.status == "conditional" and ruled.rulings[0].startswith("mk-19-puu-ix-2011")
    assert on(versions, pid, "2021-06-01").status == "repealed"
    assert on(versions, pid, "2023-06-01").source_id == "perppu-2-2022/pasal-81/angka-56"


def test_mk_168_rulings_attach_to_the_right_articles(versions):
    rest = on(versions, "uu-13-2003/pasal-79", "2025-06-01")
    assert {"mk-168-puu-xxi-2023/amar-7", "mk-168-puu-xxi-2023/amar-8"} <= set(rest.rulings)
    severance = on(versions, "uu-13-2003/pasal-156", "2025-06-01")
    assert "mk-168-puu-xxi-2023/amar-22" in severance.rulings
    assert "mk-168-puu-xxi-2023/amar-24" not in severance.rulings  # 'tidak dapat diterima'


def test_uu_11_2020_conditional_during_repair_period(versions):
    v = on(versions, "uu-13-2003/pasal-79", "2022-06-01")
    assert v.status == "conditional" and "mk-91-puu-xviii-2020" in v.rulings


def test_sectoral_minimum_wage_returns_in_pp_49_2025(versions):
    assert "sektoral" not in on(versions, "pp-36-2021/pasal-25", "2022-06-01").text
    v2026 = on(versions, "pp-36-2021/pasal-25", "2026-06-01")
    assert "sektoral provinsi" in v2026.text and v2026.source_id == "pp-49-2025/pasal-i/angka-6"


def test_unamended_article_has_one_version(versions):
    mine = [v for v in versions if v.provision_id == "uu-13-2003/pasal-1"]
    assert len(mine) == 1 and mine[0].valid_to is None
