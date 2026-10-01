"""The retrieval gate: a check that runs in CI without Ollama or the downloaded data, and fails
when retrieval gets worse.

A fixture in git (evals/fixtures/retrieval.npz, about 2 MB) holds a snapshot of the dated corpus,
its embeddings, and the embeddings of the evaluation questions. The gate runs date-aware hybrid
retrieval (the `temporal-hybrid` configuration: the search of the answer pipeline without its
model calls) over the snapshot with the code as it is now, and compares the result with the one
recorded when the fixture was made:

- Recall@5 must not drop by more than TOLERANCE;
- no more questions may get a `must_not_cite` source among their top 5.

The fixture is remade with `uv run pasalkini fixture` (needs the local data and Ollama) when the
corpus changes, or when questions, dates or source labels of the evaluation set change. The gate
fails with that instruction when its snapshot no longer matches the answer keys: a stale
comparison is not a pass.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import numpy as np

from pasalkini.evals.metrics import ItemResult, score
from pasalkini.evals.schema import EvalItem, load_golden
from pasalkini.paths import EVALS_DIR
from pasalkini.pipelines import CONFIGS, PipelineConfig, load_chunks
from pasalkini.retrieve.dense import DenseIndex
from pasalkini.retrieve.lexical import BM25Index
from pasalkini.retrieve.search import make_search
from pasalkini.retrieve.temporal import retrieve
from pasalkini.temporal.corpus import DatedChunk

FIXTURE_PATH = EVALS_DIR / "fixtures" / "retrieval.npz"
CONFIG_NAME = "temporal-hybrid"
TOLERANCE = 0.01  # one expected source more or less among about 70 questions is 0.007 to 0.014


@dataclass
class Fixture:
    chunks: list[DatedChunk]
    chunk_vectors: np.ndarray
    queries: dict[str, np.ndarray]  # by question ID
    meta: dict


def keys_fingerprint(items: list[EvalItem]) -> str:
    """Changes when what the gate measures against changes: a question, its date, or its source
    labels. Marking a key as reviewed does not change it."""
    digest = hashlib.sha256()
    for item in sorted(items, key=lambda i: i.id):
        fields = [
            item.id,
            item.question,
            item.as_of.isoformat(),
            item.date_in_question,
            item.expected_sources,
            item.must_not_cite,
        ]
        digest.update(json.dumps(fields, ensure_ascii=False).encode("utf-8"))
    return digest.hexdigest()[:16]


def measure(
    items: list[EvalItem],
    chunks: list[DatedChunk],
    chunk_vectors: np.ndarray,
    queries: dict[str, np.ndarray],
    config: PipelineConfig,
    today: date,
) -> dict:
    """Retrieval over the snapshot with the code as it is now."""
    index = DenseIndex(config.embed_model, chunks, chunk_vectors, fingerprint="fixture")
    lexical = BM25Index(chunks) if config.retriever != "dense" else None
    results = []
    for item in items:
        if item.id not in queries:
            continue
        search = make_search(
            config.retriever,
            max(10, config.top_k),
            index,
            queries[item.id],
            lexical,
            item.question,
        )
        retrieval = retrieve(
            search,
            item.question,
            date_hint=None if item.date_in_question else item.as_of,
            date_filter=config.date_filter,
            history_cues=config.history_cues,
            today=today,
        )
        result = ItemResult(
            id=item.id,
            category=item.category.value,
            split=item.split,
            as_of=item.as_of,
            question=item.question,
            retrieved=[(chunk.source_id, round(s, 4)) for chunk, s in retrieval.hits],
            context_ids=[chunk.source_id for chunk, _ in retrieval.hits[: config.top_k]],
            retrieval_ms=0.0,
            as_of_used=retrieval.as_of,
            retrieval_mode=retrieval.mode,
        )
        results.append(score(result, item))
    recalls = [r.recall_at_5 for r in results if r.recall_at_5 is not None]
    return {
        "questions": len(results),
        "with_expected_sources": len(recalls),
        "recall_at_5": round(sum(recalls) / len(recalls), 4) if recalls else None,
        "hit_at_5": sum(bool(r.hit_at_5) for r in results),
        "stale_in_top_5": sum(bool(r.stale_in_context) for r in results),
    }


def build_fixture(path: Path = FIXTURE_PATH) -> dict:
    """Snapshot the corpus and the questions as they are now, and record what retrieval scores
    on them. Embeds the questions, so it needs Ollama."""
    config = CONFIGS[CONFIG_NAME]
    items = load_golden()
    chunks = load_chunks(config)
    index = DenseIndex.build(
        config.embed_model, chunks, config.embed_num_ctx, with_titles=config.chunk_headers
    )
    embedded = index.embed_queries(
        [item.question for item in items],
        config.query_instruction,
        config.embed_num_ctx,
        unload=True,
    )
    return write_fixture(
        path, items, chunks, index.vectors, embedded, index.fingerprint, date.today()
    )


def write_fixture(
    path: Path,
    items: list[EvalItem],
    chunks: list[DatedChunk],
    chunk_vectors: np.ndarray,
    query_vectors: np.ndarray,
    corpus_fingerprint: str,
    today: date,
) -> dict:
    config = CONFIGS[CONFIG_NAME]
    # Half precision halves the file. The baseline is measured on the stored vectors, so the
    # gate compares like with like.
    chunk_vectors = chunk_vectors.astype(np.float16)
    query_vectors = query_vectors.astype(np.float16)
    queries = {item.id: query_vectors[n].astype(np.float32) for n, item in enumerate(items)}
    meta = {
        "config": CONFIG_NAME,
        "embed_model": config.embed_model,
        "corpus_fingerprint": corpus_fingerprint,
        "keys_fingerprint": keys_fingerprint(items),
        "today": today.isoformat(),
        "question_ids": [item.id for item in items],
        "baseline": measure(
            items, chunks, chunk_vectors.astype(np.float32), queries, config, today
        ),
    }
    listed = [
        {
            **asdict(chunk),
            "valid_from": chunk.valid_from.isoformat(),
            "valid_to": chunk.valid_to.isoformat() if chunk.valid_to else None,
        }
        for chunk in chunks
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        chunk_vectors=chunk_vectors,
        query_vectors=query_vectors,
        chunks=np.array(json.dumps(listed, ensure_ascii=False)),
        meta=np.array(json.dumps(meta, ensure_ascii=False)),
    )
    return meta


def load_fixture(path: Path = FIXTURE_PATH) -> Fixture:
    with np.load(path) as data:
        meta = json.loads(str(data["meta"]))
        listed = json.loads(str(data["chunks"]))
        chunk_vectors = data["chunk_vectors"].astype(np.float32)
        query_vectors = data["query_vectors"].astype(np.float32)
    chunks = [
        DatedChunk(
            **{
                **fields,
                "valid_from": date.fromisoformat(fields["valid_from"]),
                "valid_to": date.fromisoformat(fields["valid_to"]) if fields["valid_to"] else None,
                "rulings": tuple(fields["rulings"]),
            }
        )
        for fields in listed
    ]
    queries = dict(zip(meta["question_ids"], query_vectors, strict=True))
    return Fixture(chunks, chunk_vectors, queries, meta)


def check(path: Path = FIXTURE_PATH, items: list[EvalItem] | None = None) -> tuple[bool, list[str]]:
    """Whether retrieval is still as good as when the fixture was made, and what was measured."""
    if not path.exists():
        return False, [f"No fixture at {path}. Make one with `uv run pasalkini fixture`."]
    fixture = load_fixture(path)
    items = items if items is not None else load_golden()
    meta, baseline = fixture.meta, fixture.meta["baseline"]
    if keys_fingerprint(items) != meta["keys_fingerprint"]:
        return False, [
            "The evaluation questions or their source labels changed after the fixture was made "
            f"({meta['today']}), so its baseline no longer applies.",
            "Remake it with `uv run pasalkini fixture` and commit evals/fixtures/retrieval.npz.",
        ]
    now = measure(
        items,
        fixture.chunks,
        fixture.chunk_vectors,
        fixture.queries,
        CONFIGS[meta["config"]],
        date.fromisoformat(meta["today"]),
    )
    lines = [
        f"Retrieval gate ({meta['config']}; {len(fixture.chunks)} chunks, corpus "
        f"{meta['corpus_fingerprint']}, fixture of {meta['today']}):",
        f"  Recall@5          {now['recall_at_5']:.4f}  (baseline {baseline['recall_at_5']:.4f}, "
        f"may drop by {TOLERANCE})",
        f"  Hit@5             {now['hit_at_5']}/{now['with_expected_sources']}  "
        f"(baseline {baseline['hit_at_5']})",
        f"  Stale text in top 5   {now['stale_in_top_5']}  "
        f"(baseline {baseline['stale_in_top_5']}, may not rise)",
    ]
    problems = []
    if now["recall_at_5"] < baseline["recall_at_5"] - TOLERANCE:
        problems.append("FAILED: Recall@5 dropped.")
    if now["stale_in_top_5"] > baseline["stale_in_top_5"]:
        problems.append("FAILED: more questions get text that did not apply on their date.")
    return not problems, lines + (problems or ["Passed."])
