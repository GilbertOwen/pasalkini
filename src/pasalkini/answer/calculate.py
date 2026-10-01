"""The calculator as a tool. The model reads the facts from the question; code does the maths.

The model returns the kind of payment, the length of service or contract, and the dismissal
reason, constrained to the reason codes of the rules in force on the date. Two facts are checked
against the question itself:
- the wage is read by a pattern when the question states exactly one amount, since small models
  garble long numbers;
- the reason must come with the words of the question that state it. A reason the model cannot
  point to is one it made up.

A question rarely states everything. The result is as exact as the facts allow: the multipliers
for the reason; months of wage when the length of service is known; rupiah when the wage is too.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, create_model

from pasalkini.answer.llm import ChatOptions
from pasalkini.answer.understand import Chat
from pasalkini.tools.pesangon import (
    CalculatorError,
    Line,
    Result,
    fmt,
    hitung_kompensasi_pkwt,
    hitung_pesangon,
    reasons_on,
)

RUPIAH = re.compile(
    r"Rp\.?\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?(?:\s*(juta|ribu))?", re.IGNORECASE
)
# When a question that is not classified as a calculation still gets the calculator: it asks
# about severance money, or about rights after a dismissal. Without a wage the calculator
# answers with multipliers or months of wage, which is what such questions ask for.
SEVERANCE = re.compile(
    r"pesangon|penghargaan masa kerja|\bUPMK\b|penggantian hak|\bUPH\b|uang pisah", re.IGNORECASE
)
DISMISSAL = re.compile(
    r"\b(?:PHK|pemutusan hubungan kerja|diberhentikan|dipecat|mengundurkan diri|resign|pensiun)\b",
    re.IGNORECASE,
)
ASKS_RIGHTS = re.compile(r"\b(?:hak|berhak|berapa)\b", re.IGNORECASE)
PKWT_COMPENSATION = re.compile(r"uang kompensasi", re.IGNORECASE)
DURATION = re.compile(r"\d+\s*(?:bulan|tahun)", re.IGNORECASE)

FACTS_PROMPT = """Baca fakta dari pertanyaan untuk kalkulator pesangon PasalKini. Jangan \
menghitung apa pun.
- jenis: pesangon untuk pemutusan hubungan kerja (PHK), termasuk mengundurkan diri dan pensiun; \
kompensasi_pkwt untuk kontrak kerja waktu tertentu (PKWT) yang berakhir.
- lama_tahun dan lama_bulan: lama bekerja, atau lama kontrak untuk PKWT ("5 tahun 3 bulan" → 5 \
dan 3; "18 bulan" → 0 dan 18). Isi 0 jika tidak disebut.
- upah_bulanan: upah sebulan dalam rupiah, angka saja. Isi 0 jika tidak disebut.
- bukti_alasan: kata-kata dari pertanyaan yang menyebut alasan PHK, disalin persis (misalnya \
"perusahaan tutup karena rugi" atau "mengundurkan diri"). Isi null jika pertanyaan tidak menyebut \
alasan PHK.
- alasan: untuk pesangon, kode alasan PHK dari daftar di bawah yang paling sesuai dengan \
bukti_alasan. Isi null untuk kompensasi_pkwt, jika bukti_alasan null, atau jika tidak ada kode \
yang sesuai."""


def about_severance(question: str) -> bool:
    """The question is about severance money, or about rights after a dismissal."""
    return bool(
        SEVERANCE.search(question) or (DISMISSAL.search(question) and ASKS_RIGHTS.search(question))
    )


def may_calculate(question: str) -> bool:
    """Worth asking the calculator even though the question was not classified as a
    calculation: a dismissal whose payments are asked about, or a contract of a stated length
    whose compensation is."""
    dismissal = DISMISSAL.search(question) and about_severance(question)
    contract = PKWT_COMPENSATION.search(question) and DURATION.search(question)
    return bool(dismissal or contract)


@dataclass
class Calculation:
    kind: str | None = None
    wage: int | None = None  # None: the question does not state it
    months: int | None = None  # length of service or contract; None: not stated
    evidence: str | None = None  # the question's words for the dismissal reason
    result: Result | None = None
    error: str | None = None  # facts missing or not understood
    facts: dict = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def sources(self) -> list[str]:
        """Source IDs of the articles each amount rests on."""
        if self.result is None:
            return []
        bases = [b.strip() for line in self.result.lines for b in line.basis.split(";")]
        return list(dict.fromkeys(b for b in bases if b))

    def text(self) -> str:
        if self.error:
            return f"Tidak dihitung: {self.error}"
        result = self.result
        if result.unsupported:
            return f"Tidak dihitung: {result.unsupported}"
        wage = rupiah_text(self.wage) if self.wage else "tidak disebut"
        lines = [f"Upah sebulan: {wage}; masa kerja: {result.service}; aturan: {result.regime}."]
        if result.reason:
            read_from = f', dibaca dari "{self.evidence}"' if self.evidence else ""
            lines.append(f"Alasan PHK yang dipakai: {result.reason}{read_from}.")
        for line in result.lines:
            lines.append(f"- {line.component}: {line.formula}{outcome(line)} (dasar: {line.basis})")
        least = "paling sedikit " if result.minimum else ""
        if any(line.amount for line in result.lines):
            lines.append(f"Jumlah yang dihitung: {least}{rupiah_text(result.total)}")
        elif result.total_months:
            lines.append(f"Jumlah yang dihitung: {least}{fmt(result.total_months)} bulan upah")
        if result.variants:
            lines.append("Alasan lain dalam pasal yang sama:")
            lines += [f"- {variant}" for variant in result.variants]
        lines += [f"Catatan: {note}" for note in result.notes]
        lines.append(
            "Periksa bahwa upah, masa kerja dan alasan di atas sesuai dengan keadaan Anda: "
            "semuanya dibaca dari pertanyaan."
        )
        return "\n".join(lines)

    def summary(self) -> str | None:
        """The result in one or two sentences, to open the answer with. None when there is
        nothing to state."""
        result = self.result
        if self.error or result is None or result.unsupported or not result.lines:
            return None
        least = "paling sedikit " if result.minimum else ""
        counted = [line for line in result.lines if line.amount is not None or line.months]
        if self.kind == "kompensasi_pkwt":
            line = result.lines[0]
            value = outcome(line)[2:]
            if not value:
                return None
            return f"Menurut hitungan program, uang kompensasi PKWT-nya{value} ({line.formula})."
        opening = f"Menurut hitungan program untuk PHK dengan alasan “{result.reason_label}”"
        if counted:
            rupiah = any(line.amount is not None for line in counted)
            total = (
                rupiah_text(result.total) if rupiah else f"{fmt(result.total_months)} bulan upah"
            )
            parts = ", ".join(f"{short(line)}{outcome(line)[2:]}" for line in counted)
            rest = "uang penggantian hak lain yang tidak dapat dihitung dari pertanyaan"
            return f"{opening}: {least}{total} ({parts}), belum termasuk {rest}."
        pesangon, upmk = result.multipliers["pesangon"], result.multipliers["upmk"]
        if not pesangon and not upmk:
            also = " dan uang pisah" if result.separation_pay else ""
            return (
                f"{opening}: tidak ada uang pesangon dan uang penghargaan masa kerja; yang "
                f"menjadi hak adalah uang penggantian hak{also}."
            )
        sentence = (
            f"{opening}: uang pesangon {fmt(pesangon)} kali ketentuan dan uang penghargaan masa "
            f"kerja {fmt(upmk)} kali ketentuan, ditambah uang penggantian hak."
        )
        if result.variants:
            sentence += (
                " Untuk alasan lain dalam pasal yang sama: " + "; ".join(result.variants) + "."
            )
        return sentence


def short(line: Line) -> str:
    """'uang pesangon' from 'Uang pesangon'; 'penggantian perumahan ...' from 'UPH: ...'."""
    name = line.component.split(": ")[-1]
    return name[0].lower() + name[1:]


def outcome(line: Line) -> str:
    """' = Rp18.000.000', ' = 10 bulan upah', or nothing when only the multiplier is known."""
    if line.amount is not None:
        return f" = {rupiah_text(line.amount)}"
    if line.months is not None and line.months != Decimal("0"):
        return f" = {fmt(line.months)} bulan upah"
    return ""


def rupiah_text(amount: int | None) -> str:
    return "Rp" + f"{amount or 0:,}".replace(",", ".")


def wages_in(question: str) -> list[int]:
    amounts = []
    for match in RUPIAH.finditer(question):
        whole, decimals, unit = match.groups()
        scale = {"juta": 1_000_000, "ribu": 1_000}.get((unit or "").lower(), 1)
        value = Decimal(whole.replace(".", ""))
        if decimals and scale > 1:  # 'Rp4,5 juta'; the ',00' of 'Rp4.500.000,00' is cents
            value += Decimal(f"0.{decimals}")
        amounts.append(int(value * scale))
    return list(dict.fromkeys(amounts))


def months_before(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 - months
    return date(index // 12, index % 12 + 1, min(day.day, 28))


def said_in(evidence: str | None, question: str) -> str | None:
    """The evidence as the question has it, or None when the question does not say it."""
    words = re.findall(r"\w+", (evidence or "").lower())
    if not words:
        return None
    pattern = r"\W+".join(re.escape(word) for word in words)
    match = re.search(pattern, question, re.IGNORECASE)
    return match.group() if match else None


def facts_schema(reasons: list[str]) -> type[BaseModel]:
    """Plain integers, with no ranges in the schema: range keywords are not supported by every
    JSON-grammar backend. calculate() checks the values instead. The evidence comes before the
    reason code, so that the model copies the words first and picks the code for them."""
    reason_type = Literal[tuple(reasons)] if reasons else str
    return create_model(
        "FaktaHitungan",
        jenis=(Literal["pesangon", "kompensasi_pkwt"], ...),
        lama_tahun=(int, ...),
        lama_bulan=(int, ...),
        upah_bulanan=(int, ...),
        bukti_alasan=(str | None, None),
        alasan=(reason_type | None, None),
    )


def calculate(
    question: str, end: date, chat: Chat, options: ChatOptions, *, strict: bool = True
) -> Calculation:
    """`end` is the date of the dismissal or of the contract's end: the question's date.

    strict: the question asks for a calculation, so a reason the model chose is used even when
    it cannot point to the words. Otherwise such a reason is dropped."""
    # The schema constrains the output but the model never sees it, so the codes and what
    # they mean go in the prompt. Without them the model's own words were forced into the
    # nearest code: 'perusahaan tutup' came out as 'pensiun'.
    labels = reasons_on(end)
    reasons = sorted(labels)
    listed = "\n".join(f"- {code}: {labels[code]}" for code in reasons)
    system = FACTS_PROMPT + (f"\n\nKode alasan PHK:\n{listed}" if reasons else "")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]
    reply = chat(options, messages, facts_schema(reasons))
    calculation = Calculation(seconds=reply.seconds)
    if reply.parsed is None:
        calculation.error = "fakta untuk menghitung tidak terbaca dari pertanyaan."
        return calculation
    facts = reply.parsed
    calculation.facts = facts.model_dump()
    calculation.kind = facts.jenis
    wages = wages_in(question)
    stated = wages[0] if len(wages) == 1 else facts.upah_bulanan
    calculation.wage = stated if stated > 0 else None
    length = facts.lama_tahun * 12 + facts.lama_bulan
    calculation.months = length if 0 < length <= 720 else None
    calculation.evidence = said_in(facts.bukti_alasan, question)
    reason = facts.alasan if strict or calculation.evidence else None
    start = months_before(end, calculation.months) if calculation.months else None
    try:
        if facts.jenis == "kompensasi_pkwt":
            if start is None:
                calculation.error = "pertanyaan tidak menyebut lama kontrak."
            else:
                calculation.result = hitung_kompensasi_pkwt(start, end, calculation.wage)
        elif reasons and not reason:
            calculation.error = "alasan PHK tidak terbaca dari pertanyaan."
        else:
            calculation.result = hitung_pesangon(start, end, calculation.wage, reason or "")
    except CalculatorError as error:
        calculation.error = str(error)
    return calculation
