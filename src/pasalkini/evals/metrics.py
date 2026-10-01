"""Per-item evaluation results and the metrics computed from them.

Labels are source IDs (see pasalkini.evals.schema). A label matches a chunk when it is the
chunk's ID or a prefix of it: 'uu-11-2020' matches 'uu-11-2020/pasal-81/angka-15'.
"""

import re
from datetime import date

from pydantic import BaseModel

from pasalkini.evals.schema import EvalItem

# A chunk ID such as 'uu-13-2003/pasal-59' or 'perppu-2-2022/pasal-81/angka-15'. Each segment
# starts with a word, so '13/2003' inside a title such as 'UU 13/2003 Pasal 59' is not an ID.
CHUNK_ID = re.compile(r"[a-z]+(?:-[a-z0-9]+)+(?:/[a-z]+-[a-z0-9]+)+")

# UU 6/2023 enacted Perppu 2/2022 without changing its wording, and the parser stores that wording
# once, under the Perppu's IDs. A Perppu chunk therefore carries UU 6/2023 text, so it satisfies
# an expected 'uu-6-2023' label. The alias is not applied to must_not_cite: the two instruments
# took effect on different dates.
TEXT_ALIASES: dict[str, tuple[str, ...]] = {"uu-6-2023": ("perppu-2-2022",)}


def matches(source_id: str, label: str) -> bool:
    return source_id == label or source_id.startswith(label + "/")


def matches_expected(source_id: str, label: str) -> bool:
    return matches(source_id, label) or any(
        matches(source_id, alias) for alias in TEXT_ALIASES.get(label, ())
    )


def recall(ids: list[str], expected: list[str]) -> float | None:
    """Share of expected labels matched by at least one of the ids."""
    if not expected:
        return None
    return sum(any(matches_expected(i, e) for i in ids) for e in expected) / len(expected)


def any_expected(ids: list[str], expected: list[str]) -> bool | None:
    if not expected:
        return None
    return any(matches_expected(i, e) for i in ids for e in expected)


def any_forbidden(ids: list[str], forbidden: list[str]) -> bool | None:
    if not forbidden:
        return None
    return any(matches(i, f) for i in ids for f in forbidden)


def extract_ids(citations: list[str]) -> list[str]:
    """Chunk IDs in whatever the model wrote: '[uu-13-2003/pasal-59]', '{…}', or JSON inside a
    string. IDs are kept in order, without duplicates."""
    found: list[str] = []
    for text in citations:
        for source_id in CHUNK_ID.findall(text.lower()):
            if source_id not in found:
                found.append(source_id)
    return found


class ItemResult(BaseModel):
    """What happened for one question. Raw fields are saved; score() fills in the metrics."""

    id: str
    category: str
    split: str
    reviewed: bool = False
    as_of: date
    question: str

    retrieved: list[tuple[str, float]]  # top 10 with cosine scores
    context_ids: list[str]  # the top-k chunks given to the model
    retrieval_ms: float
    as_of_used: date | None = None  # the date retrieval filtered on (None: no filter)
    retrieval_mode: str = "plain"  # plain | as_of | history
    answer: str | None = None
    citations_raw: list[str] = []  # exactly as the model wrote them
    json_ok: bool | None = None
    generation_s: float | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    truncated_chunks: int | None = None
    # Phase 5 pipeline only. For it, 'retrieved' is the context in order, with no scores.
    intent: str | None = None
    as_of_source: str | None = None  # pertanyaan | pemilih_tanggal | hari_ini
    abstained: bool | None = None
    first_pass_ok: bool | None = None  # the first selection of quotes passed every check
    retried: bool | None = None  # the selection was repaired
    dropped_citations: list[str] = []  # selected in the end but failed the checks
    first_problems: list[str] = []  # what the checks said about the first selection
    drafts_raw: list[str] = []  # every reply of the selection and answer calls, in order
    # From Phase 6 the answer is a second call, from the verified passages alone.
    lead: str | None = None  # the opening sentence written by code
    material: str | None = None  # what the answer call was given
    grounded_first: bool | None = None  # the first answer mentioned nothing it was not given
    rewritten: bool | None = None
    answer_problems: list[str] = []  # what the first answer mentioned that it was not given
    ungrounded: list[str] = []  # ... and what the shown answer still does
    later_sources: list[str] = []  # law that began after the date, shown as such and not cited
    agent_steps: list[str] | None = None  # agent only: the tools it used, in order
    calculation: str | None = None

    # Metrics, recomputed by score() from the fields above and the current answer keys.
    recall_at_5: float | None = None
    recall_at_10: float | None = None
    hit_at_5: bool | None = None
    stale_in_context: bool | None = None  # a must_not_cite source is among the top-k chunks
    citations: list[str] = []  # chunk IDs extracted from citations_raw
    invalid_citations: list[str] = []  # cited IDs that were not in the context
    cited_expected: bool | None = None
    stale_cited: bool | None = None  # the answer cites a must_not_cite source
    date_ok: bool | None = None  # the date read from the question is the key's date
    abstain_ok: bool | None = None  # abstained exactly when the key says it should
    intent_ok: bool | None = None


# The intent each category implies. Date-extraction questions mix explanations and
# calculations, so they are not scored on intent.
INTENT_BY_CATEGORY = {
    "stable_rule": "jelaskan",
    "temporal_trap": "jelaskan",
    "status": "status",
    "what_changed": "riwayat",
    "calculation": "hitung",
    "adversarial": "jelaskan",
}


def expected_intent(item: EvalItem) -> str | None:
    if item.should_abstain:
        return "di_luar_cakupan"
    return INTENT_BY_CATEGORY.get(item.category.value)


def score(result: ItemResult, item: EvalItem) -> ItemResult:
    """(Re)compute the metrics of one result against the item's current answer key."""
    ids = [source_id for source_id, _ in result.retrieved]
    result.reviewed = item.review == "done"
    result.category = item.category.value
    result.split = item.split
    result.recall_at_5 = recall(ids[:5], item.expected_sources)
    result.recall_at_10 = recall(ids[:10], item.expected_sources)
    result.hit_at_5 = any_expected(ids[:5], item.expected_sources)
    result.stale_in_context = any_forbidden(result.context_ids, item.must_not_cite)
    if item.date_in_question and result.as_of_used is not None:
        result.date_ok = result.as_of_used == item.as_of
    if result.json_ok is None:  # retrieval-only run
        return result
    result.citations = extract_ids(result.citations_raw)
    result.invalid_citations = [c for c in result.citations if c not in result.context_ids]
    result.cited_expected = any_expected(result.citations, item.expected_sources)
    result.stale_cited = any_forbidden(result.citations, item.must_not_cite)
    if result.abstained is not None:
        result.abstain_ok = result.abstained == item.should_abstain
        expected = expected_intent(item)
        if expected is not None and result.intent is not None:
            result.intent_ok = result.intent == expected
    return result


def percent(values: list[bool | None]) -> str:
    known = [v for v in values if v is not None]
    if not known:
        return "n/a"
    hits = sum(known)
    return f"{100 * hits / len(known):.0f}% ({hits}/{len(known)})"


def mean(values: list[float | None]) -> str:
    known = [v for v in values if v is not None]
    return f"{sum(known) / len(known):.2f}" if known else "n/a"


def median(values: list[float | None]) -> str:
    known = sorted(v for v in values if v is not None)
    return f"{known[len(known) // 2]:.1f}" if known else "n/a"


def summary_row(label: str, results: list[ItemResult]) -> list[str]:
    return [
        label,
        str(len(results)),
        mean([r.recall_at_5 for r in results]),
        percent([r.hit_at_5 for r in results]),
        percent([r.stale_in_context for r in results]),
        percent([r.stale_cited for r in results]),
        percent([r.cited_expected for r in results]),
        percent(
            [bool(r.invalid_citations) if r.json_ok and r.citations else None for r in results]
        ),
        percent([r.json_ok for r in results]),
        median([r.generation_s for r in results]),
    ]


SUMMARY_HEADER = [
    "Group",
    "Items",
    "Recall@5",
    "Hit@5",
    "Stale text in top 5",
    "Answer cites stale source",
    "Answer cites expected source",
    "Cites an ID not in context",
    "Valid JSON",
    "Median answer s",
]


def groups(results: list[ItemResult]) -> list[tuple[str, list[ItemResult]]]:
    found = [("All", results)]
    for category in sorted({r.category for r in results}):
        found.append((category, [r for r in results if r.category == category]))
    for split in ("dev", "test"):
        found.append((f"split: {split}", [r for r in results if r.split == split]))
    return found


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return lines + ["| " + " | ".join(row) + " |" for row in rows]


def summary_table(results: list[ItemResult]) -> list[str]:
    return table(SUMMARY_HEADER, [summary_row(label, group) for label, group in groups(results)])


PIPELINE_HEADER = [
    "Group",
    "Abstained correctly",
    "Intent correct",
    "Date from question correct",
    "Citations pass first try",
    "Repaired",
    "Citations dropped",
    "Answer grounded first try",
    "Answer shown ungrounded",
]


def pipeline_table(results: list[ItemResult]) -> list[str]:
    """Phase 5 checks: abstention, classification, and how often verification had to step in."""
    rows = []
    for label, group in groups(results):
        answered = [r for r in group if r.first_pass_ok is not None]
        written = [r for r in group if r.grounded_first is not None]
        rows.append(
            [
                label,
                percent([r.abstain_ok for r in group]),
                percent([r.intent_ok for r in group]),
                percent([r.date_ok for r in group]),
                percent([r.first_pass_ok for r in answered]),
                percent([r.retried for r in answered]),
                percent([bool(r.dropped_citations) for r in answered]),
                percent([r.grounded_first for r in written]),
                percent([bool(r.ungrounded) for r in written]),
            ]
        )
    return table(PIPELINE_HEADER, rows)
