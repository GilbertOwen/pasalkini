"""An automatic judge for answers, and a measure of how far to trust it.

The judge is the same small local model that writes the answers, so it is not asked for a
grade. It is asked small questions, one per point of the answer key, and code turns its replies
into a grade:

  correct  the key's main point is in the answer and nothing in the answer goes against the key
  partly   the main point is there, and something else goes against the key
  wrong    the main point is contradicted or missing

Refusals are graded by code: an answer is right to abstain exactly when the key says it should.

A judge is only worth what its agreement with a person's grades is worth. agreement() compares
its grades with grades given by reading the answers (grades-*.csv in a run folder) and reports
plain agreement, Cohen's kappa and the confusion table.
"""

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from pasalkini.answer.llm import ChatOptions, chat_json
from pasalkini.answer.understand import Chat
from pasalkini.evals.compare import load_run
from pasalkini.evals.metrics import ItemResult, table
from pasalkini.evals.schema import EvalItem, load_golden
from pasalkini.pipelines import CONFIGS
from pasalkini.temporal.query import format_date

GRADES = ("correct", "partly", "wrong")
MAX_ANSWER_CHARS = 3000
# Key points that say what an answer must not do ('Tidak menyebut batas 5 tahun'), as against
# points whose content is a 'no' ('Tidak wajib: ...', 'Tidak berhak uang pesangon').
FORBIDS = re.compile(
    r"^(?:Jawaban\s+)?[Tt]idak\s+(?:boleh\s+)?(?:menyebut|menjawab|memakai|menggunakan|"
    r"menambahkan|mengutip|mengikuti|menjanjikan|menyatakan|menebak|memberi)\b"
)
# Notes for whoever reads the key, which a good answer may leave out.
OPTIONAL = re.compile(r"^(?:Catatan|Per \w+ \d{4}|Per \d|Status perlu)")

JUDGE_PROMPT = """Kamu memeriksa JAWABAN sebuah asisten informasi hukum ketenagakerjaan \
terhadap KUNCI yang ditulis ahli. KUNCI benar untuk TANGGAL itu. Jangan memakai pengetahuanmu \
sendiri: bandingkan JAWABAN dengan KUNCI saja.

Tulis JSON dengan isian berikut:
- poin: untuk setiap butir di POIN KUNCI, nomor butir dan statusnya:
  "ada" jika JAWABAN menyatakan isi butir itu (boleh dengan kata lain, boleh tidak lengkap);
  "bertentangan" jika JAWABAN menyatakan hal yang berlawanan dengan butir itu (angka lain, \
kesimpulan lain, ya menjadi tidak);
  "tidak_disebut" jika JAWABAN tidak membahas butir itu.
- larangan: untuk setiap butir di LARANGAN, nomor butir dan dilanggar: true jika JAWABAN \
melakukan hal yang dilarang butir itu, false jika tidak.
- keliru: satu kalimat dari JAWABAN yang berlawanan dengan KUNCI, disalin persis, atau null \
jika tidak ada. Nomor pasal atau nama peraturan yang berbeda dari KUNCI termasuk keliru.
Bagian "Sumber" dan "Hitungan (oleh program)" adalah bagian dari JAWABAN."""


class Point(BaseModel):
    nomor: int
    status: Literal["ada", "bertentangan", "tidak_disebut"]


class Ban(BaseModel):
    nomor: int
    dilanggar: bool


class Verdict(BaseModel):
    poin: list[Point]
    larangan: list[Ban] = []
    keliru: str | None = None


class Judged(BaseModel):
    id: str
    grade: Literal["correct", "partly", "wrong"]
    by: Literal["code", "model"]
    reason: str = ""


def split_key(item: EvalItem) -> tuple[list[str], list[str]]:
    """The key's points an answer should state, and the things it must not do. Notes for the
    reader of the key ('Catatan ...') are neither."""
    points = [p for p in item.expected_points if not FORBIDS.match(p) and not OPTIONAL.match(p)]
    bans = [p for p in item.expected_points if FORBIDS.match(p)]
    return points, bans


def judge_message(item: EvalItem, answer: str) -> str:
    points, bans = split_key(item)
    parts = [
        f"TANGGAL: {format_date(item.as_of)}",
        f"PERTANYAAN: {item.question}",
        "POIN KUNCI:\n" + "\n".join(f"{n}. {p}" for n, p in enumerate(points, start=1)),
    ]
    if bans:
        parts.append("LARANGAN:\n" + "\n".join(f"{n}. {p}" for n, p in enumerate(bans, start=1)))
    parts.append("JAWABAN:\n" + answer[:MAX_ANSWER_CHARS])
    return "\n\n".join(parts)


def grade_of(verdict: Verdict) -> tuple[str, str]:
    """The grade the verdict amounts to, and why. The key's first point is its main point."""
    status = {point.nomor: point.status for point in verdict.poin}
    main = status.get(1, "tidak_disebut")
    against = [f"poin {n} bertentangan" for n, s in sorted(status.items()) if s == "bertentangan"]
    against += [f"larangan {ban.nomor} dilanggar" for ban in verdict.larangan if ban.dilanggar]
    if verdict.keliru:
        against.append(f"keliru: {verdict.keliru[:120]}")
    if main == "bertentangan":
        return "wrong", "; ".join(against)
    if main == "tidak_disebut":
        stated = any(s == "ada" for s in status.values())
        return ("partly" if stated else "wrong"), "poin utama tidak disebut"
    return ("partly", "; ".join(against)) if against else ("correct", "")


def judge_item(item: EvalItem, result: ItemResult, chat: Chat, options: ChatOptions) -> Judged:
    """Refusals by code; everything else by the model's verdict on the key's points."""
    # Plain RAG has no way to abstain (abstained is None): there the model has to look.
    if result.abstained is not None and (item.should_abstain or result.abstained):
        right = result.abstained == item.should_abstain
        grade = "correct" if right else "wrong"
        reason = "menolak dengan tepat" if right else "menolak atau menjawab di luar kunci"
        return Judged(id=item.id, grade=grade, by="code", reason=reason)
    if not split_key(item)[0]:
        return Judged(id=item.id, grade="wrong", by="code", reason="kunci tanpa poin")
    messages = [
        {"role": "system", "content": JUDGE_PROMPT},
        {"role": "user", "content": judge_message(item, result.answer or "")},
    ]
    reply = chat(options, messages, Verdict)
    if reply.parsed is None:
        return Judged(id=item.id, grade="wrong", by="model", reason="putusan juri tidak terbaca")
    grade, reason = grade_of(reply.parsed)
    return Judged(id=item.id, grade=grade, by="model", reason=reason)


def judge_run(run_dir: Path, split: str | None = None, chat: Chat = chat_json) -> Path:
    """Judge every answer of a saved run (or of one split) and write judge.csv beside it."""
    config = CONFIGS["pasalkini"]
    options = ChatOptions(config.chat_model, 0.0, config.seed, config.num_ctx, 500, False)
    items = {item.id: item for item in load_golden()}
    _, results = load_run(run_dir)
    chosen = [r for r in results if split is None or r.split == split]
    path = run_dir / ("judge.csv" if split is None else f"judge-{split}.csv")
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "split", "grade", "by", "reason"])
        for n, result in enumerate(chosen, start=1):
            judged = judge_item(items[result.id], result, chat, options)
            writer.writerow([judged.id, result.split, judged.grade, judged.by, judged.reason])
            f.flush()
            print(f"  [{n:>3}/{len(chosen)}] {judged.id:<18} {judged.grade}", flush=True)
    return path


def read_grades(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as f:
        return {row["id"]: row["grade"] for row in csv.DictReader(f) if row["grade"] in GRADES}


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa: agreement beyond what the two graders' habits would give by chance."""
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    first, second = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(first[g] * second[g] for g in GRADES) / (n * n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def agreement(reference: dict[str, str], judged: dict[str, str]) -> list[str]:
    """Markdown lines: how the judge's grades compare with the reference grades."""
    shared = sorted(set(reference) & set(judged))
    pairs = [(reference[i], judged[i]) for i in shared]
    if not pairs:
        return ["No answers graded by both."]
    exact = sum(a == b for a, b in pairs)
    right = sum((a == "correct") == (b == "correct") for a, b in pairs)
    k = kappa(pairs)
    counts = Counter(pairs)
    rows = [[g, *(str(counts[(g, j)]) for j in GRADES)] for g in GRADES]
    lines = [
        f"- Answers graded by both: {len(pairs)}",
        f"- Same grade: {100 * exact / len(pairs):.0f}% ({exact}/{len(pairs)})",
        f"- Same on correct or not: {100 * right / len(pairs):.0f}% ({right}/{len(pairs)})",
        f"- Cohen's kappa: {'n/a' if k is None else f'{k:.2f}'}",
        "",
        *table(["Reference \\ judge", *GRADES], rows),
    ]
    return lines


def totals(grades: dict[str, str]) -> str:
    counts = Counter(grades.values())
    return " / ".join(f"{counts[g]} {g}" for g in GRADES)
