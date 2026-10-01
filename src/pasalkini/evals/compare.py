"""Compare saved evaluation runs side by side, scored against the current answer keys."""

import json
from pathlib import Path

from pasalkini.evals.metrics import (
    ItemResult,
    any_expected,
    groups,
    matches_expected,
    median,
    percent,
    score,
    table,
)
from pasalkini.evals.schema import load_golden


def reciprocal_rank(result: ItemResult, expected: list[str]) -> float | None:
    """1/rank of the first retrieved chunk that matches an expected label (top 10), else 0."""
    if not expected:
        return None
    for rank, (source_id, _) in enumerate(result.retrieved[:10], start=1):
        if any(matches_expected(source_id, label) for label in expected):
            return 1.0 / rank
    return 0.0


def load_run(run_dir: Path) -> tuple[dict, list[ItemResult]]:
    meta = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    items = {item.id: item for item in load_golden()}
    results = []
    for line in (run_dir / "outputs.jsonl").read_text(encoding="utf-8").splitlines():
        result = ItemResult.model_validate_json(line)
        if not result.citations_raw and result.citations:  # saved before citations_raw existed
            result.citations_raw = result.citations
        if result.id in items:
            results.append(score(result, items[result.id]))
    return meta, results


def _mean(values: list[float | None]) -> str:
    known = [v for v in values if v is not None]
    return f"{sum(known) / len(known):.2f}" if known else "n/a"


COLUMNS = [
    "Run",
    "Items",
    "Recall@5",
    "MRR@10",
    "Stale text in top 5",
    "Answer cites stale source",
    "Answer cites expected source",
    "Cites an ID not in context",
    "Abstained correctly",
    "Median s per question",
]


def compare(run_dirs: list[Path], split: str | None = None, category: str | None = None) -> str:
    items = {item.id: item for item in load_golden()}
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for run_dir in run_dirs:
        meta, results = load_run(run_dir)
        chosen = [
            r
            for r in results
            if (split is None or r.split == split) and (category is None or r.category == category)
        ]
        answered = [r for r in chosen if r.json_ok is not None]
        row = [
            meta["config"]["name"],
            str(len(chosen)),
            _mean([r.recall_at_5 for r in chosen]),
            _mean([reciprocal_rank(r, items[r.id].expected_sources) for r in chosen]),
            percent([r.stale_in_context for r in chosen]),
            percent([r.stale_cited for r in answered]) if answered else "n/a",
            percent([r.cited_expected for r in answered]) if answered else "n/a",
            percent([bool(r.invalid_citations) if r.citations else None for r in answered])
            if answered
            else "n/a",
            percent([r.abstain_ok for r in answered]),
            median([r.generation_s for r in answered]),
        ]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


FUNNEL_HEADER = [
    "Group",
    "Answerable",
    "Expected source in context",
    "... and cited",
    "Lost in retrieval",
    "Lost in the answer",
]


def funnel(run_dir: Path) -> str:
    """Where questions that have an expected source are lost: the source never reached the
    context (retrieval), or it did and the answer did not cite it (the answer step, which
    includes wrong abstentions)."""
    items = {item.id: item for item in load_golden()}
    _, results = load_run(run_dir)
    rows = []
    for label, group in groups(results):
        answerable = [
            r
            for r in group
            if items[r.id].expected_sources
            and not items[r.id].should_abstain
            and r.json_ok is not None
        ]
        if not answerable:
            continue
        found = [r for r in answerable if any_expected(r.context_ids, items[r.id].expected_sources)]
        cited = [r for r in found if r.cited_expected]
        n = len(answerable)
        rows.append(
            [
                label,
                str(n),
                f"{100 * len(found) / n:.0f}% ({len(found)}/{n})",
                f"{100 * len(cited) / n:.0f}% ({len(cited)}/{n})",
                str(n - len(found)),
                str(len(found) - len(cited)),
            ]
        )
    return "\n".join(table(FUNNEL_HEADER, rows))
