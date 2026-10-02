"""What the pipeline does with an ordinary question when the model misreads its kind.

The model decides whether a question is about an article's status or about change, and such a
question is searched in every wording up to the date. So a misreading puts ended wordings in
front of the model. This run forces that misreading on every development question that asks
what the law says, originals and rewordings, and counts the answers that cite a source that did
not apply on the date. The count has to be zero: the date rule must not depend on the model.

Development split only. The held-out questions are not looked at here.
"""

from pasalkini.answer.llm import Reply, chat_json, unload
from pasalkini.answer.pipeline import Pipeline
from pasalkini.answer.understand import Chat, Classification
from pasalkini.evals.metrics import ItemResult, expected_intent
from pasalkini.evals.runner import evaluate_with_pipeline
from pasalkini.evals.schema import EvalItem, load_items
from pasalkini.pipelines import CONFIGS, load_chunks
from pasalkini.retrieve.dense import DenseIndex
from pasalkini.retrieve.lexical import BM25Index
from pasalkini.sources import load_topics

KINDS = ("status", "riwayat")


def forced(kind: str, chat: Chat = chat_json) -> Chat:
    """The chat model, except that every question is read as `kind`."""

    def call(options, messages, schema):
        if schema is Classification:
            parsed = Classification(intent=kind)
            return Reply(parsed, parsed.model_dump_json(), 0, 0, 0.0)
        return chat(options, messages, schema)

    return call


def ordinary_questions() -> list[EvalItem]:
    """Development questions that ask what the law says, from both sets."""
    return [
        item
        for dataset in ("golden", "variants")
        for item in load_items(dataset)
        if item.split == "dev"
        and not item.should_abstain
        and (expected_intent(item) == "jelaskan" or item.category.value == "date_extraction")
    ]


def totals(results: list[ItemResult]) -> dict[str, str]:
    def count(values: list[bool | None]) -> str:
        known = [value for value in values if value is not None]
        return f"{sum(known)}/{len(known)}"

    return {
        "questions": str(len(results)),
        "ended wording given to the model": count([r.stale_in_context for r in results]),
        "ended wording cited as a source": count([r.stale_cited for r in results]),
        "ended wording shown as such": str(sum(bool(r.earlier_sources) for r in results)),
        "expected source shown": count([r.cited_expected for r in results]),
        "abstained": str(sum(bool(r.abstained) for r in results)),
    }


def run(kind: str, config_name: str = "pasalkini") -> list[ItemResult]:
    config = CONFIGS[config_name]
    chunks = load_chunks(config)
    index = DenseIndex.build(config.embed_model, chunks, config.embed_num_ctx)
    lexical = BM25Index(chunks) if config.retriever != "dense" else None
    items = ordinary_questions()
    queries = index.embed_queries(
        [item.question for item in items],
        config.query_instruction,
        config.embed_num_ctx,
        unload=True,
    )
    pipeline = Pipeline(config, chunks, index, lexical, load_topics(), chat=forced(kind))
    unload(config.chat_model)
    results = []
    for n, (item, vector) in enumerate(zip(items, queries, strict=True), start=1):
        result = evaluate_with_pipeline(item, pipeline, vector)
        results.append(result)
        flag = " CITES AN ENDED WORDING" if result.stale_cited else ""
        print(f"  [{n:>2}/{len(items)}] {item.id:<20}{flag}", flush=True)
    return results
