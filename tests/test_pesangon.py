"""Severance calculator: cases computed by hand from the article texts."""

from datetime import date

import pytest

from pasalkini.corpus import load_corpus
from pasalkini.evals.metrics import matches
from pasalkini.paths import PROCESSED_DIR
from pasalkini.tools.pesangon import (
    CalculatorError,
    completed_months,
    hitung_kompensasi_pkwt,
    hitung_pesangon,
    rules,
)


def amounts(result) -> dict[str, int | None]:
    return {line.component: line.amount for line in result.lines}


def test_completed_months_counts_whole_months_only():
    assert completed_months(date(2018, 3, 1), date(2023, 6, 1)) == 63
    assert completed_months(date(2018, 3, 15), date(2023, 6, 14)) == 62


def test_calc_001_closure_after_two_years_of_losses_in_2023():
    """PP 35/2021 Pasal 44(1): 0,5 x 6 months + 1 x 2 months, at Rp6.000.000."""
    r = hitung_pesangon(date(2018, 3, 1), date(2023, 6, 1), 6_000_000, "tutup_rugi_2_tahun")
    assert (r.regime, r.service) == ("pp-35-2021", "5 tahun 3 bulan")
    got = amounts(r)
    assert got["Uang pesangon"] == 18_000_000
    assert got["Uang penghargaan masa kerja"] == 12_000_000
    assert r.total == 30_000_000 and not r.minimum


def test_efficiency_closure_in_2019_uses_uu_13_2003_and_the_15_percent():
    """UU 13/2003 Pasal 164(3): 2 x 5 months + 1 x 2 months + 15% of both, at Rp5.000.000."""
    r = hitung_pesangon(date(2015, 3, 15), date(2019, 3, 15), 5_000_000, "tutup_efisiensi")
    got = amounts(r)
    assert r.regime == "uu-13-2003" and r.minimum
    assert got["Uang pesangon"] == 50_000_000
    assert got["Uang penghargaan masa kerja"] == 10_000_000
    assert got["UPH: penggantian perumahan serta pengobatan dan perawatan"] == 9_000_000
    assert any("MK 19/PUU-IX/2011" in n for n in r.notes)


def test_after_mk_168_severance_is_a_minimum():
    r = hitung_pesangon(date(2015, 1, 1), date(2025, 6, 1), 5_000_000, "efisiensi_karena_rugi")
    assert r.minimum and any("MK 168" in n for n in r.notes)
    assert "UPH: penggantian perumahan serta pengobatan dan perawatan" not in amounts(r)


def test_resignation_gets_rights_and_separation_pay_only():
    r = hitung_pesangon(date(2019, 1, 1), date(2022, 6, 1), 5_000_000, "mengundurkan_diri")
    got = amounts(r)
    assert "Uang pesangon" not in got and got["Uang pisah"] is None and r.total == 0


def test_unused_leave_uses_the_daily_wage_approximation():
    r = hitung_pesangon(date(2019, 1, 1), date(2022, 6, 1), 4_200_000, "pensiun", sisa_cuti_hari=5)
    assert amounts(r)["UPH: cuti tahunan yang belum diambil"] == 1_000_000  # 4.2m / 21 x 5


def test_gap_between_cipta_kerja_and_pp_35_is_refused():
    r = hitung_pesangon(date(2015, 1, 1), date(2020, 12, 1), 5_000_000, "pailit")
    assert r.regime == "celah-2020" and r.unsupported and not r.lines


def test_micro_and_small_business_amounts_are_by_agreement():
    r = hitung_pesangon(
        date(2015, 1, 1), date(2022, 6, 1), 3_000_000, "pailit", usaha_mikro_kecil=True
    )
    assert "Pasal 59" in r.unsupported


def test_unknown_reason_lists_the_valid_ones():
    with pytest.raises(CalculatorError, match="pilihan: "):
        hitung_pesangon(date(2015, 1, 1), date(2022, 6, 1), 3_000_000, "dipecat")


@pytest.mark.parametrize(
    ("start", "end", "wage", "expected"),
    [
        (date(2021, 9, 15), date(2022, 3, 15), 4_000_000, 2_000_000),  # calc-002
        (date(2020, 7, 15), date(2021, 7, 15), 4_500_000, 4_500_000),  # date-004
        (date(2021, 1, 1), date(2022, 7, 1), 4_000_000, 6_000_000),  # 18 months
    ],
)
def test_pkwt_compensation(start, end, wage, expected):
    r = hitung_kompensasi_pkwt(start, end, wage)
    assert r.total == expected


def test_no_pkwt_compensation_before_cipta_kerja():
    r = hitung_kompensasi_pkwt(date(2018, 1, 1), date(2019, 6, 1), 4_000_000)
    assert r.total == 0 and "Pasal 62" in r.notes[0]


def test_every_rule_cites_an_article_in_the_corpus():
    if not (PROCESSED_DIR / "uu-13-2003.json").exists():
        pytest.skip("corpus not parsed")
    chunk_ids = [c.source_id for c in load_corpus()]
    for regime in rules()["regimes"]:
        cited = [regime.get("tables_basis")] + [
            r["basis"] for r in regime.get("reasons", {}).values()
        ]
        for source_id in filter(None, cited):
            assert any(matches(c, source_id) for c in chunk_ids), source_id
