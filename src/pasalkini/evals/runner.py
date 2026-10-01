"""Run a pipeline configuration over the evaluation set and save everything needed to reproduce it.

evals/runs/<timestamp>-<config>/
  config.json     configuration, git commit, model digests, dataset and corpus fingerprints
  outputs.jsonl   every retrieval and answer, with timings (not committed)
  summary.md      metrics tables (committed)
  grading.csv     one row per answer for hand grading (committed)
"""

import csv
import hashlib
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

import ollama

from pasalkini.answer.generate import generate
from pasalkini.evals.metrics import ItemResult, percent, score, summary_table
from pasalkini.evals.schema import EvalItem, load_golden
from pasalkini.paths import EVALS_DIR, GOLDEN_PATH, ROOT
from pasalkini.pipelines import CONFIGS, PipelineConfig, load_chunks
from pasalkini.retrieve.dense import DenseIndex
from pasalkini.retrieve.hybrid import expand_query
from pasalkini.retrieve.lexical import BM25Index
from pasalkini.retrieve.search import Search, make_search
from pasalkini.retrieve.temporal import retrieve
from pasalkini.sources import load_topics

RUNS_DIR = EVALS_DIR / "runs"


def git_state() -> dict:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout.strip()

    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def model_digests(names: list[str]) -> dict[str, str]:
    available = {m.model: m.digest for m in ollama.list().models}
    return {name: available.get(name, "not installed") for name in names}


def evaluate_item(
    item: EvalItem, config: PipelineConfig, search: Search, retrieval_only: bool
) -> ItemResult:
    # The date picker supplies the date unless the date is only in the question text, in which
    # case the pipeline has to read it from there.
    date_hint = None if item.date_in_question else item.as_of
    started = time.perf_counter()
    retrieval = retrieve(
        search,
        item.question,
        date_hint=date_hint,
        date_filter=config.date_filter,
        history_cues=config.history_cues,
    )
    hits = retrieval.hits
    retrieval_ms = (time.perf_counter() - started) * 1000

    context = [chunk for chunk, _ in hits[: config.top_k]]
    result = ItemResult(
        id=item.id,
        category=item.category.value,
        split=item.split,
        as_of=item.as_of,
        question=item.question,
        retrieved=[(chunk.source_id, round(similarity, 4)) for chunk, similarity in hits],
        context_ids=[chunk.source_id for chunk in context],
        retrieval_ms=round(retrieval_ms, 1),
        as_of_used=retrieval.as_of,
        retrieval_mode=retrieval.mode,
    )
    if retrieval_only:
        return score(result, item)

    # A date-aware pipeline tells the model the date it used; the baseline passes on only the
    # date picker's date.
    as_of = retrieval.as_of if config.date_filter else date_hint
    generation = generate(
        config.chat_model,
        item.question,
        as_of,
        context,
        max_chars=config.max_chars_per_chunk,
        think=config.think,
        temperature=config.temperature,
        seed=config.seed,
        num_ctx=config.num_ctx,
        max_tokens=config.max_answer_tokens,
    )
    result.answer = generation.answer.answer if generation.answer else generation.raw
    result.citations_raw = generation.answer.citations if generation.answer else []
    result.json_ok = generation.answer is not None
    result.generation_s = round(generation.seconds, 2)
    result.prompt_tokens = generation.prompt_tokens
    result.output_tokens = generation.output_tokens
    result.truncated_chunks = generation.truncated_chunks
    return score(result, item)


def write_summary(run_dir: Path, meta: dict, results: list[ItemResult]) -> None:
    config = meta["config"]
    reviewed = sum(r.reviewed for r in results)
    traps = [r for r in results if r.category == "temporal_trap"]
    models = ", ".join(f"`{name}` ({digest[:12]})" for name, digest in meta["models"].items())
    commit = f"`{meta['git']['commit'][:10]}`"
    if meta["git"]["dirty"]:
        commit += " (uncommitted changes)"
    corpus, dataset = meta["corpus"], meta["dataset"]
    mode = "retrieval only" if meta["retrieval_only"] else "retrieval and answers"
    lines = [
        f"# Evaluation run: {run_dir.name}",
        "",
        f"**Pipeline:** `{config['name']}`: {config['description']}",
        "",
        f"- Models: {models}",
        f"- Git commit: {commit}",
        f"- Corpus: {corpus['chunks']} chunks, fingerprint `{corpus['fingerprint']}`",
        f"- Dataset: {dataset['items']} items, sha256 `{dataset['sha256'][:12]}`",
        f"- Mode: {mode}",
    ]
    if "rescored" in meta:
        rescored = meta["rescored"]
        lines.append(
            f"- Rescored {rescored['at']} against dataset sha256 "
            f"`{rescored['dataset_sha256'][:12]}` ({rescored['reviewed']} keys reviewed)"
        )
    lines.append("")
    if reviewed < len(results):
        lines += [
            f"> **Provisional.** {reviewed} of {len(results)} answer keys have been checked by a "
            "person. The rest are drafts, so these numbers can move when the keys are reviewed.",
            "",
        ]
    if not meta["retrieval_only"] and traps:
        stale = percent([r.stale_cited for r in traps])
        lines += [
            f"**Headline:** on temporal-trap questions, the answer cited a source that did not "
            f"apply on the question's date in {stale} of the questions that have forbidden "
            "sources labelled.",
            "",
        ]
    lines += summary_table(results)
    lines += [
        "",
        "Definitions:",
        "",
        "- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level "
        "label is found by any chunk from that document).",
        "- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.",
        "- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.",
        "- *Cites an ID not in context*: the model invented or altered a source ID.",
        "",
    ]
    (run_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def write_grading_sheet(run_dir: Path, results: list[ItemResult]) -> None:
    with (run_dir / "grading.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "split",
                "category",
                "as_of",
                "question",
                "answer",
                "citations",
                "grade",
                "notes",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r.id,
                    r.split,
                    r.category,
                    r.as_of,
                    r.question,
                    r.answer,
                    " ".join(r.citations),
                    "",
                    "",
                ]
            )


def run(config_name: str, retrieval_only: bool = False) -> Path:
    config = CONFIGS[config_name]
    items = load_golden()
    chunks = load_chunks(config)
    if not chunks:
        raise SystemExit("No parsed documents. Run `uv run pasalkini parse` first.")
    index = DenseIndex.build(
        config.embed_model, chunks, config.embed_num_ctx, with_titles=config.chunk_headers
    )
    lexical = BM25Index(chunks) if config.retriever != "dense" else None
    topics = load_topics()
    texts = [
        expand_query(item.question, topics) if config.rewrite_query else item.question
        for item in items
    ]
    # Embed every question first, then free the embedding model's memory: on a 6 GB GPU the
    # embedding and chat models swap in and out if they are used alternately.
    queries = index.embed_queries(
        texts, config.query_instruction, config.embed_num_ctx, unload=not retrieval_only
    )

    started_at = datetime.now()
    suffix = "-retrieval" if retrieval_only else ""
    run_dir = RUNS_DIR / f"{started_at:%Y%m%d-%H%M%S}-{config.name}{suffix}"
    run_dir.mkdir(parents=True)

    results = []
    for n, item in enumerate(items, start=1):
        search = make_search(
            config.retriever,
            max(10, config.top_k),
            index,
            queries[n - 1],
            lexical,
            texts[n - 1],
        )
        result = evaluate_item(item, config, search, retrieval_only)
        results.append(result)
        stale = "stale-cited" if result.stale_cited else ""
        print(
            f"  [{n:>3}/{len(items)}] {item.id:<18} recall@5={result.recall_at_5} {stale}",
            flush=True,
        )

    models = [config.embed_model] + ([] if retrieval_only else [config.chat_model])
    meta = {
        "config": config.model_dump(),
        "retrieval_only": retrieval_only,
        "git": git_state(),
        "models": model_digests(models),
        "corpus": {
            "chunks": len(chunks),
            "fingerprint": index.fingerprint,
            "newly_embedded": index.newly_embedded,
        },
        "dataset": {
            "items": len(items),
            "reviewed": sum(i.review == "done" for i in items),
            "sha256": hashlib.sha256(GOLDEN_PATH.read_bytes()).hexdigest(),
        },
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    (run_dir / "config.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    with (run_dir / "outputs.jsonl").open("w", encoding="utf-8") as f:
        for result in results:
            f.write(result.model_dump_json() + "\n")
    write_summary(run_dir, meta, results)
    if not retrieval_only:
        write_grading_sheet(run_dir, results)
    return run_dir


def rescore(run_dir: Path) -> Path:
    """Recompute a saved run's metrics against the current answer keys, without new answers.

    Use it after reviewing or correcting answer keys. grading.csv is left alone, since it may
    already hold hand grades.
    """
    meta = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    items = {item.id: item for item in load_golden()}
    results = []
    for line in (run_dir / "outputs.jsonl").read_text(encoding="utf-8").splitlines():
        result = ItemResult.model_validate_json(line)
        if not result.citations_raw and result.citations:  # saved before citations_raw existed
            result.citations_raw = result.citations
        if result.id in items:
            results.append(score(result, items[result.id]))
    meta["rescored"] = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "dataset_sha256": hashlib.sha256(GOLDEN_PATH.read_bytes()).hexdigest(),
        "reviewed": sum(i.review == "done" for i in items.values()),
        "items_scored": len(results),
    }
    (run_dir / "config.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    with (run_dir / "outputs.jsonl").open("w", encoding="utf-8") as f:
        for result in results:
            f.write(result.model_dump_json() + "\n")
    write_summary(run_dir, meta, results)
    return run_dir
