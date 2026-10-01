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
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import httpx
import numpy as np
import ollama

from pasalkini.answer.agent import Agent
from pasalkini.answer.generate import generate
from pasalkini.answer.pipeline import Pipeline
from pasalkini.evals.metrics import ItemResult, percent, pipeline_table, score, summary_table
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

    # Run folders are outputs, not code: without the exclusion every run would look dirty.
    status = git("status", "--porcelain", "--", ".", ":(exclude)evals/runs")
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(status)}


def model_digests(names: list[str]) -> dict[str, str]:
    available = {m.model: m.digest for m in ollama.list().models}
    return {name: available.get(name, "not installed") for name in names}


def with_retry[T](item_id: str, call: Callable[[], T]) -> tuple[T | None, str | None]:
    """One retry: a request can hang or fail once (a laptop sleep, the GPU still holding the
    embedding model). A second failure is returned as an error and the run goes on."""
    failure = None
    for attempt in (1, 2):
        try:
            return call(), None
        except (httpx.HTTPError, ollama.ResponseError, ConnectionError) as error:
            print(f"    {item_id}: attempt {attempt} failed: {error!r}", flush=True)
            failure = f"ERROR: {error!r}"
    return None, failure


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
    generation, failure = with_retry(
        item.id,
        lambda: generate(
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
        ),
    )
    if generation is None:
        result.answer = failure
        return score(result, item)
    result.answer = generation.answer.answer if generation.answer else generation.raw
    result.citations_raw = generation.answer.citations if generation.answer else []
    result.json_ok = generation.answer is not None
    result.generation_s = round(generation.seconds, 2)
    result.prompt_tokens = generation.prompt_tokens
    result.output_tokens = generation.output_tokens
    result.truncated_chunks = generation.truncated_chunks
    return score(result, item)


def evaluate_with_pipeline(
    item: EvalItem, pipeline: Pipeline, query_vector: np.ndarray
) -> ItemResult:
    """The Phase 5 pipeline on one question. 'retrieved' is the context the model saw, in order:
    the pipeline adds named articles and calculator sources to the search results."""
    date_hint = None if item.date_in_question else item.as_of
    outcome, failure = with_retry(
        item.id, lambda: pipeline.run(item.question, date_hint, query_vector)
    )
    result = ItemResult(
        id=item.id,
        category=item.category.value,
        split=item.split,
        as_of=item.as_of,
        question=item.question,
        retrieved=[],
        context_ids=[],
        retrieval_ms=0.0,
    )
    if outcome is None:
        result.answer, result.json_ok = failure, False
        return score(result, item)
    u = outcome.understanding
    context_ids = [chunk.source_id for chunk in outcome.context]
    result.retrieved = [(source_id, 0.0) for source_id in context_ids]
    result.context_ids = context_ids
    result.retrieval_ms = round(outcome.seconds.get("retrieve", 0.0) * 1000, 1)
    result.as_of_used = u.as_of
    result.retrieval_mode = "history" if u.history else "as_of"
    result.answer = outcome.display()
    result.citations_raw = [c.source_id for c in outcome.citations]
    result.json_ok = outcome.json_ok if outcome.replies else True  # a refusal makes no call
    result.generation_s = outcome.seconds.get("total")
    result.prompt_tokens = sum(reply.prompt_tokens for reply in outcome.replies)
    result.output_tokens = sum(reply.output_tokens for reply in outcome.replies)
    result.intent = u.intent
    result.as_of_source = u.as_of_source
    result.abstained = outcome.abstained
    result.first_pass_ok = not outcome.first_problems if outcome.selections else None
    result.retried = outcome.retried if outcome.selections else None
    result.dropped_citations = outcome.dropped
    result.first_problems = outcome.first_problems
    result.drafts_raw = [reply.raw for reply in outcome.replies]
    result.lead = outcome.lead
    result.material = outcome.material or None
    result.grounded_first = not outcome.answer_problems if outcome.drafts else None
    result.rewritten = outcome.rewritten if outcome.drafts else None
    result.answer_problems = outcome.answer_problems
    result.ungrounded = outcome.ungrounded
    result.later_sources = [passage.source_id for passage in outcome.later]
    if isinstance(pipeline, Agent):
        result.agent_steps = outcome.steps
    result.calculation = outcome.calculation.text() if outcome.calculation else None
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
        f"- Mode: {mode}" + (f", {meta['split']} split only" if meta.get("split") else ""),
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
    pipeline = any(r.abstained is not None for r in results)
    if pipeline:
        lines += ["", "Answer pipeline:", "", *pipeline_table(results)]
    stepped = [r.agent_steps for r in results if r.agent_steps is not None]
    if stepped:
        used = Counter(tool for steps in stepped for tool in steps)
        tools = ", ".join(f"{tool} {n}" for tool, n in used.most_common())
        lines += [
            "",
            f"Agent: {sum(map(len, stepped)) / len(stepped):.1f} tool calls a question on "
            f"average ({tools}); {sum(not steps for steps in stepped)} of {len(stepped)} "
            "questions used no tool.",
        ]
    lines += [
        "",
        "Definitions:",
        "",
        "- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level "
        "label is found by any chunk from that document).",
        "- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.",
        "- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.",
        "- *Cites an ID not in context*: the model invented or altered a source ID.",
    ]
    if pipeline:
        lines += [
            "- For this pipeline, *top 5* means the first 5 chunks of the context, which puts the "
            "articles the question names before the search results; *Median answer s* is the "
            "whole pipeline. Citations are counted after verification.",
            "- *Abstained correctly*: refused or abstained exactly when the key says it should.",
            "- *Citations pass first try*: every quote the model first selected was found in "
            "the source it named, in a version that applied on the date; *Repaired*: a second "
            "selection was asked for; *Citations dropped*: quotes of the final selection that "
            "still failed and were not used.",
            "- *Answer grounded first try*: the first answer mentioned no number or article "
            "that it was not given (and, for history questions, no date); otherwise it was "
            "rewritten once. *Answer shown ungrounded*: the answer shown still does, and says "
            "so in a note.",
        ]
    lines.append("")
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


def run(config_name: str, retrieval_only: bool = False, split: str | None = None) -> Path:
    config = CONFIGS[config_name]
    verified = config.answer_mode != "baseline"
    if verified and retrieval_only:
        raise SystemExit(
            f"{config.name} asks the chat model what kind of question it is before searching, "
            "so it has no retrieval-only mode. Use temporal-hybrid for retrieval alone."
        )
    items = [item for item in load_golden() if split is None or item.split == split]
    # Fingerprint what was loaded: the file may be edited while a long run is going.
    dataset_sha = hashlib.sha256(GOLDEN_PATH.read_bytes()).hexdigest()
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
    pipeline = None
    if verified:
        kind = Agent if config.answer_mode == "agent" else Pipeline
        pipeline = kind(config, chunks, index, lexical, topics)

    git = git_state()  # the code this run executes is the code on disk now, not at the end
    started_at = datetime.now()
    suffix = ("-retrieval" if retrieval_only else "") + (f"-{split}" if split else "")
    run_dir = RUNS_DIR / f"{started_at:%Y%m%d-%H%M%S}-{config.name}{suffix}"
    run_dir.mkdir(parents=True)

    results = []
    # Written as it goes, so a run that dies part way still leaves its answers.
    with (run_dir / "outputs.jsonl").open("w", encoding="utf-8") as outputs:
        for n, item in enumerate(items, start=1):
            if pipeline is not None:
                result = evaluate_with_pipeline(item, pipeline, queries[n - 1])
            else:
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
            outputs.write(result.model_dump_json() + "\n")
            outputs.flush()
            flags = [
                flag
                for flag, on in [
                    ("stale-cited", result.stale_cited),
                    (f"intent={result.intent}", result.intent_ok is False),
                    ("abstained", result.abstained),
                    ("repaired", result.retried),
                ]
                if on
            ]
            print(
                f"  [{n:>3}/{len(items)}] {item.id:<18} recall@5={result.recall_at_5} "
                + " ".join(flags),
                flush=True,
            )

    models = [config.embed_model] + ([] if retrieval_only else [config.chat_model])
    meta = {
        "config": config.model_dump(),
        "retrieval_only": retrieval_only,
        "split": split,
        "git": git,
        "models": model_digests(models),
        "corpus": {
            "chunks": len(chunks),
            "fingerprint": index.fingerprint,
            "newly_embedded": index.newly_embedded,
        },
        "dataset": {
            "items": len(items),
            "reviewed": sum(i.review == "done" for i in items),
            "sha256": dataset_sha,
        },
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    (run_dir / "config.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
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
