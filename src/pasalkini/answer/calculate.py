"""The calculator as a tool. The model reads the facts from the question; code does the maths.

The model returns the kind of payment, the length of service or contract, and the dismissal
reason, constrained to the reason codes of the rules in force on the date. The wage is read by a
pattern when the question states exactly one amount, since small models garble long numbers.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, create_model

from pasalkini.answer.llm import ChatOptions
from pasalkini.answer.understand import Chat
from pasalkini.tools.pesangon import (
    CalculatorError,
    Result,
    hitung_kompensasi_pkwt,
    hitung_pesangon,
    reasons_on,
)

RUPIAH = re.compile(
    r"Rp\.?\s*(\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?(?:\s*(juta|ribu))?", re.IGNORECASE
)

FACTS_PROMPT = """Baca fakta dari pertanyaan untuk kalkulator pesangon PasalKini. Jangan \
menghitung apa pun.
- jenis: pesangon untuk pemutusan hubungan kerja (PHK); kompensasi_pkwt untuk kontrak kerja \
waktu tertentu (PKWT) yang berakhir.
- lama_tahun dan lama_bulan: lama bekerja, atau lama kontrak untuk PKWT ("5 tahun 3 bulan" → 5 \
dan 3; "18 bulan" → 0 dan 18). Isi 0 jika tidak disebut.
- upah_bulanan: upah sebulan dalam rupiah, angka saja. Isi 0 jika tidak disebut.
- alasan: untuk pesangon, kode alasan PHK dari daftar di bawah yang paling sesuai dengan \
pertanyaan. Kosongkan untuk kompensasi_pkwt, atau jika tidak ada yang sesuai."""


@dataclass
class Calculation:
    kind: str | None = None
    wage: int | None = None
    months: int | None = None
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
        lines = [
            f"Upah sebulan: {rupiah_text(self.wage)}; masa kerja: {result.service}; "
            f"aturan: {result.regime}."
        ]
        if result.reason:
            lines.append(f"Alasan PHK yang dipakai: {result.reason}.")
        for line in result.lines:
            amount = rupiah_text(line.amount) if line.amount is not None else "tidak dihitung"
            lines.append(f"- {line.component}: {line.formula} = {amount} (dasar: {line.basis})")
        if any(line.amount for line in result.lines):
            least = "paling sedikit " if result.minimum else ""
            lines.append(f"Jumlah yang dihitung: {least}{rupiah_text(result.total)}")
        lines += [f"Catatan: {note}" for note in result.notes]
        lines.append(
            "Periksa bahwa upah, masa kerja dan alasan di atas sesuai dengan keadaan Anda: "
            "semuanya dibaca dari pertanyaan."
        )
        return "\n".join(lines)


def rupiah_text(amount: int | None) -> str:
    return "Rp" + f"{amount or 0:,}".replace(",", ".")


def wages_in(question: str) -> list[int]:
    amounts = []
    for match in RUPIAH.finditer(question):
        value = int(match.group(1).replace(".", ""))
        unit = (match.group(2) or "").lower()
        value *= {"juta": 1_000_000, "ribu": 1_000}.get(unit, 1)
        amounts.append(value)
    return list(dict.fromkeys(amounts))


def months_before(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 - months
    return date(index // 12, index % 12 + 1, min(day.day, 28))


def facts_schema(reasons: list[str]) -> type[BaseModel]:
    """Plain integers, with no ranges in the schema: range keywords are not supported by every
    JSON-grammar backend. calculate() checks the values instead."""
    reason_type = Literal[tuple(reasons)] if reasons else str
    return create_model(
        "FaktaHitungan",
        jenis=(Literal["pesangon", "kompensasi_pkwt"], ...),
        lama_tahun=(int, ...),
        lama_bulan=(int, ...),
        upah_bulanan=(int, ...),
        alasan=(reason_type | None, None),
    )


def calculate(question: str, end: date, chat: Chat, options: ChatOptions) -> Calculation:
    """`end` is the date of the dismissal or of the contract's end: the question's date."""
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
    calculation.wage = wages[0] if len(wages) == 1 else facts.upah_bulanan
    calculation.months = facts.lama_tahun * 12 + facts.lama_bulan
    missing = [
        what
        for what, absent in [
            ("upah sebulan", calculation.wage <= 0),
            ("lama bekerja atau lama kontrak", not 0 < calculation.months <= 720),
            ("alasan PHK", facts.jenis == "pesangon" and not facts.alasan and reasons),
        ]
        if absent
    ]
    if missing:
        calculation.error = "pertanyaan tidak menyebut " + " dan ".join(missing) + "."
        return calculation
    start = months_before(end, calculation.months)
    try:
        if facts.jenis == "kompensasi_pkwt":
            calculation.result = hitung_kompensasi_pkwt(start, end, calculation.wage)
        else:
            calculation.result = hitung_pesangon(start, end, calculation.wage, facts.alasan or "")
    except CalculatorError as error:
        calculation.error = str(error)
    return calculation
