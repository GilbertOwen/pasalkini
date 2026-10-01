"""Severance (pesangon, UPMK, UPH) and PKWT compensation under the rules in force on a date.

The rules are data (rules/pesangon.yaml), versioned by date and tied to the articles they come
from. Amounts use Decimal and are rounded to whole rupiah.

The answer is as exact as the facts allow: with only the dismissal reason, the multipliers
("2 x ketentuan"); with the length of service as well, months of wage ("10 bulan upah"); with
the wage too, rupiah.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path

import yaml

RULES_PATH = Path(__file__).parent / "rules" / "pesangon.yaml"
PKWT_COMPENSATION_FROM = date(2021, 2, 2)  # PP 35/2021 Pasal 15-16
CIPTA_KERJA_FROM = date(2020, 11, 2)  # UU 11/2020 inserted Pasal 61A
PERPPU_FROM = date(2022, 12, 30)


class CalculatorError(ValueError):
    pass


@dataclass
class Line:
    component: str
    formula: str
    amount: int | None  # rupiah; None when it depends on facts the calculator does not have
    basis: str  # source ID of the article
    months: Decimal | None = None  # months of wage, when the length of service is known


@dataclass
class Result:
    regime: str
    service: str  # '5 tahun 3 bulan'
    reason: str = ""  # the dismissal reason the amounts rest on, in plain words, with its article
    reason_label: str = ""  # ... without the article
    multipliers: dict[str, Decimal] = field(default_factory=dict)  # pesangon and upmk, x the tables
    separation_pay: bool = False  # uang pisah, set by contract or company rules
    lines: list[Line] = field(default_factory=list)
    minimum: bool = False  # the amounts are minimums ('paling sedikit')
    notes: list[str] = field(default_factory=list)
    unsupported: str | None = None
    variants: list[str] = field(default_factory=list)  # other reasons under the same article

    @property
    def total(self) -> int:
        return sum(line.amount or 0 for line in self.lines)

    @property
    def total_months(self) -> Decimal:
        return sum((line.months for line in self.lines if line.months is not None), Decimal("0"))


@cache
def rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))


def completed_months(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month - (end.day < start.day)


def from_table(table: list[list[int]], years: int) -> int:
    """Months of wage for completed years of service, from a [from_years, months] table."""
    return max(months for from_years, months in table if years >= from_years)


def rupiah(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def fmt(multiplier: float | Decimal) -> str:
    return f"{float(multiplier):g}".replace(".", ",")


def regime_on(day: date) -> dict | None:
    for regime in rules()["regimes"]:
        start = regime["valid_from"]
        end = regime.get("valid_to")
        if start <= day and (end is None or day < end):
            return regime
    return None


def table_articles(day: date) -> list[str]:
    """The articles that set out the severance tables on the date: Pasal 156 of the labor law, in
    whatever wording applied, and the regulation that repeats the tables."""
    found = [rules()["law_article"]]
    regime = regime_on(day)
    if regime and regime.get("tables_basis") not in (None, *found):
        found.append(regime["tables_basis"])
    return found


def reasons_on(day: date) -> dict[str, str]:
    """Dismissal reason codes of the rules in force on the date, with their descriptions."""
    regime = regime_on(day)
    if regime is None or "reasons" not in regime:
        return {}
    return {code: reason["label"] for code, reason in regime["reasons"].items()}


def hitung_pesangon(
    tanggal_mulai: date | None,
    tanggal_phk: date,
    upah_bulanan: int | None,
    alasan: str,
    *,
    sisa_cuti_hari: int = 0,
    hari_kerja_per_minggu: int = 5,
    usaha_mikro_kecil: bool = False,
) -> Result:
    """Severance for a dismissal on `tanggal_phk`. `upah_bulanan` is basic wage plus fixed
    allowances. Pass None for the start date or the wage when it is not known: the result then
    gives multipliers or months of wage instead of rupiah."""
    if tanggal_mulai is not None and tanggal_phk < tanggal_mulai:
        raise CalculatorError("tanggal PHK sebelum tanggal mulai bekerja")
    if upah_bulanan is not None and upah_bulanan <= 0:
        raise CalculatorError("upah bulanan harus lebih dari 0")
    if hari_kerja_per_minggu not in (5, 6):
        raise CalculatorError("hari kerja per minggu harus 5 atau 6")

    years = None
    result = Result(regime="", service="tidak disebut")
    if tanggal_mulai is not None:
        months = completed_months(tanggal_mulai, tanggal_phk)
        years = months // 12
        result.service = f"{years} tahun {months % 12} bulan"
    regime = regime_on(tanggal_phk)
    if regime is None:
        result.unsupported = "Tanggal PHK di luar cakupan PasalKini (sebelum UU 13/2003)."
        return result
    result.regime = regime["id"]
    if "unsupported" in regime:
        result.unsupported = " ".join(regime["unsupported"].split())
        return result
    if usaha_mikro_kecil and regime["id"] == "pp-35-2021":
        result.unsupported = (
            "Untuk usaha mikro dan usaha kecil, besaran uang pesangon, UPMK, UPH dan uang pisah "
            "ditentukan berdasarkan kesepakatan (PP 35/2021 Pasal 59)."
        )
        return result
    reasons = regime["reasons"]
    if alasan not in reasons:
        raise CalculatorError(
            f"alasan '{alasan}' tidak dikenal; pilihan: {', '.join(sorted(reasons))}"
        )
    reason = reasons[alasan]
    result.reason = f"{reason['label']} ({reason['basis']})"
    result.reason_label = reason["label"]
    result.multipliers = {key: Decimal(str(reason[key])) for key in ("pesangon", "upmk")}
    result.separation_pay = bool(reason.get("uang_pisah"))
    result.variants = [
        f"{other['label']}: uang pesangon {fmt(other['pesangon'])} x, "
        f"UPMK {fmt(other['upmk'])} x ketentuan"
        for code, other in reasons.items()
        if code != alasan and other["basis"] == reason["basis"]
    ]
    wage = Decimal(upah_bulanan) if upah_bulanan is not None else None
    table_basis = regime["tables_basis"]

    total_months = Decimal("0")
    pays = any(result.multipliers.values())
    if not pays:
        result.lines.append(
            Line(
                "Uang pesangon dan uang penghargaan masa kerja",
                "tidak ada untuk alasan ini",
                None,
                reason["basis"],
            )
        )
    for component, key in [("Uang pesangon", "pesangon"), ("Uang penghargaan masa kerja", "upmk")]:
        if not reason[key]:
            continue
        multiplier = Decimal(str(reason[key]))
        basis = f"{reason['basis']}; {table_basis}"
        if years is None:
            formula = f"{fmt(multiplier)} x ketentuan tabel masa kerja"
            result.lines.append(Line(component, formula, None, basis))
            continue
        table = from_table(rules()["tables"][key], years)
        in_months = multiplier * table
        total_months += in_months
        amount = rupiah(in_months * wage) if wage is not None else None
        formula = f"{fmt(multiplier)} x {table} bulan upah"
        result.lines.append(Line(component, formula, amount, basis, in_months))
    if regime["housing_medical_pct"] and pays and (years is None or total_months):
        pct = regime["housing_medical_pct"]
        in_months = total_months * pct / 100 if years is not None else None
        result.lines.append(
            Line(
                "UPH: penggantian perumahan serta pengobatan dan perawatan",
                f"{pct}% x (uang pesangon + UPMK)",
                rupiah(in_months * wage) if wage is not None and in_months is not None else None,
                table_basis,
                in_months,
            )
        )
    if sisa_cuti_hari and wage is not None:
        divisor = 21 if hari_kerja_per_minggu == 5 else 25
        result.lines.append(
            Line(
                "UPH: cuti tahunan yang belum diambil",
                f"{sisa_cuti_hari} hari x upah sebulan/{divisor}",
                rupiah(wage / divisor * sisa_cuti_hari),
                f"{table_basis}; pp-36-2021/pasal-17",
            )
        )
        result.notes.append(
            "Upah sehari dihitung dengan pendekatan PP 36/2021 Pasal 17 (upah sebulan dibagi 21 "
            "untuk 5 hari kerja atau 25 untuk 6 hari kerja)."
        )
    result.lines.append(
        Line("UPH: ongkos pulang ke tempat diterima bekerja", "jika berlaku", None, table_basis)
    )
    if reason.get("uang_pisah"):
        result.lines.append(
            Line("Uang pisah", "diatur dalam PK, PP atau PKB", None, reason["basis"])
        )

    minimum_from = regime.get("minimum_from")
    result.minimum = regime["pesangon_is_minimum"] or bool(
        minimum_from and tanggal_phk >= minimum_from
    )
    if result.minimum and minimum_from and tanggal_phk >= minimum_from:
        result.notes.append(
            "Sejak Putusan MK 168/PUU-XXI/2023 (31 Oktober 2024), besaran uang pesangon adalah "
            "jumlah paling sedikit."
        )
    elif result.minimum:
        result.notes.append("UU 13/2003 Pasal 156 ayat (2): besaran uang pesangon paling sedikit.")
    if reason.get("note"):
        result.notes.append(" ".join(reason["note"].split()))
    if regime["id"] == "pp-35-2021" and tanggal_phk >= PERPPU_FROM:
        result.notes.append(
            "Sejak 30 Desember 2022 PP 35/2021 berlaku sepanjang tidak bertentangan dengan Perppu "
            "2/2022 yang ditetapkan menjadi UU 6/2023 (Perppu Pasal 184 huruf b)."
        )
    result.notes.append(
        "Upah = upah pokok dan tunjangan tetap. Hasil ini perkiraan, bukan nasihat hukum."
    )
    return result


def hitung_kompensasi_pkwt(
    tanggal_mulai: date,
    tanggal_berakhir: date,
    upah_bulanan: int | None,
    *,
    usaha_mikro_kecil: bool = False,
) -> Result:
    """Compensation when a fixed-term contract (PKWT) ends (PP 35/2021 Pasal 15-16)."""
    if tanggal_berakhir < tanggal_mulai:
        raise CalculatorError("tanggal berakhir sebelum tanggal mulai")
    months = completed_months(tanggal_mulai, tanggal_berakhir)
    result = Result(regime="", service=f"{months // 12} tahun {months % 12} bulan")
    if tanggal_berakhir < CIPTA_KERJA_FROM:
        result.regime = "uu-13-2003"
        result.notes.append(
            "UU 13/2003 tidak mengenal uang kompensasi saat PKWT berakhir. Jika PKWT diakhiri "
            "sebelum waktunya, pihak yang mengakhiri membayar ganti rugi sebesar upah sampai "
            "batas waktu perjanjian (UU 13/2003 Pasal 62)."
        )
        return result
    if tanggal_berakhir < PKWT_COMPENSATION_FROM:
        result.regime = "celah-2020"
        result.unsupported = (
            "UU 11/2020 Pasal 61A sudah mewajibkan uang kompensasi, tetapi besarannya baru diatur "
            "PP 35/2021 yang berlaku 2 Februari 2021. Perlu dicek manual."
        )
        return result
    result.regime = "pp-35-2021"
    if usaha_mikro_kecil:
        result.unsupported = (
            "Untuk usaha mikro dan usaha kecil, besaran uang kompensasi berdasarkan kesepakatan "
            "(PP 35/2021 Pasal 16 ayat (6))."
        )
        return result
    if months < 1:
        result.notes.append(
            "Belum berhak: uang kompensasi diberikan untuk masa kerja paling sedikit 1 bulan "
            "terus-menerus (PP 35/2021 Pasal 15 ayat (3))."
        )
        return result
    in_months = Decimal(months) / 12
    amount = rupiah(in_months * Decimal(upah_bulanan)) if upah_bulanan is not None else None
    result.lines.append(
        Line(
            "Uang kompensasi PKWT",
            f"{months}/12 x 1 bulan upah",
            amount,
            "pp-35-2021/pasal-16; pp-35-2021/pasal-15",
            in_months,
        )
    )
    result.notes.append("Upah = upah pokok dan tunjangan tetap (PP 35/2021 Pasal 16 ayat (2)).")
    return result
