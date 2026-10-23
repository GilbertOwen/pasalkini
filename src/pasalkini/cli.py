"""Command-line entry point: `uv run pasalkini <command>`."""

import argparse
import sys
from collections import Counter

from pasalkini import __version__
from pasalkini.evals.schema import load_golden
from pasalkini.sources import load_manifest, load_topics


def cmd_status(_: argparse.Namespace) -> None:
    manifest = load_manifest()
    topics = load_topics()
    golden = load_golden()

    print(f"PasalKini {__version__}\n")

    print(f"Manifest: {len(manifest.instruments)} instruments")
    for instrument in manifest.instruments:
        dates = "dates verified" if instrument.dates_verified else "dates TODO"
        print(f"  {instrument.id:<32} {instrument.status:<8} {dates}")

    print(f"\nTopics: {len(topics.topics)}")

    reviewed = sum(item.review == "done" for item in golden)
    print(f"\nEvaluation set: {len(golden)} questions, {reviewed} reviewed")
    for category, count in sorted(Counter(item.category.value for item in golden).items()):
        print(f"  {category:<16} {count}")
    splits = Counter(item.split for item in golden)
    print(f"  split: dev {splits['dev']}, test {splits['test']}")


def cmd_download(args: argparse.Namespace) -> None:
    from pasalkini.ingest.download import download_all

    print("Downloading (one request every few seconds)...")
    results = download_all(only=args.only, force=args.force)
    counts = Counter(r.status for r in results)
    print("Done: " + ", ".join(f"{n} {status}" for status, n in sorted(counts.items())))


def cmd_parse(args: argparse.Namespace) -> None:
    from pasalkini.ingest.pipeline import REPORT_PATH, run

    print("Parsing...")
    run(only=args.only)
    if not args.only:
        print(f"Report: {REPORT_PATH.relative_to(REPORT_PATH.parents[1])}")


def cmd_spotcheck(args: argparse.Namespace) -> None:
    from pasalkini.ingest.review import SPOT_CHECK_PATH, write_spot_check

    write_spot_check(n=args.n)
    print(f"Wrote {SPOT_CHECK_PATH.relative_to(SPOT_CHECK_PATH.parents[1])}")


def cmd_index(args: argparse.Namespace) -> None:
    from pasalkini.pipelines import CONFIGS, load_chunks
    from pasalkini.retrieve.dense import DenseIndex

    config = CONFIGS[args.config]
    chunks = load_chunks(config)
    index = DenseIndex.build(
        config.embed_model, chunks, config.embed_num_ctx, with_titles=config.chunk_headers
    )
    print(
        f"Index: {len(chunks)} chunks with {config.embed_model} "
        f"({index.newly_embedded} embedded now, the rest from cache), "
        f"fingerprint {index.fingerprint}"
    )


def cmd_eval(args: argparse.Namespace) -> None:
    from pasalkini.evals.runner import run

    mode = "retrieval only" if args.retrieval_only else "retrieval and answers"
    print(f"Evaluating '{args.config}' on {args.dataset} ({mode})...")
    run_dir = run(
        args.config, retrieval_only=args.retrieval_only, split=args.split, dataset=args.dataset
    )
    print(f"Run saved to {run_dir.relative_to(run_dir.parents[2])}")
    print((run_dir / "summary.md").read_text(encoding="utf-8"))


def cmd_build(_: argparse.Namespace) -> None:
    from collections import Counter as Count

    from pasalkini.temporal.store import REPORT_PATH, build

    events, versions, warnings = build()
    ops = Count(e.op for e in events)
    statuses = Count(v.status for v in versions)
    print(f"Events: {len(events)} ({', '.join(f'{k} {v}' for k, v in sorted(ops.items()))})")
    print(
        f"Versions: {len(versions)} for {len({v.provision_id for v in versions})} articles "
        f"({', '.join(f'{k} {v}' for k, v in sorted(statuses.items()))})"
    )
    print(f"Warnings: {len(warnings)} (see {REPORT_PATH.relative_to(REPORT_PATH.parents[1])})")


def cmd_law(args: argparse.Namespace) -> None:
    from datetime import date

    from pasalkini.temporal.query import consolidate, format_date, validity
    from pasalkini.temporal.store import load_versions

    as_of = date.fromisoformat(args.date)
    articles = consolidate(load_versions(), args.instrument, as_of)
    if args.pasal:
        wanted = {f"{args.instrument}/pasal-{p.lower()}" for p in args.pasal}
        articles = [v for v in articles if v.provision_id in wanted]
    print(f"{args.instrument} per {format_date(as_of)}: {len(articles)} pasal\n")
    for v in articles:
        status = " [BERSYARAT]" if v.status == "conditional" else ""
        print(f"{v.label}{status}  ({validity(v)}; teks dari {v.source_id})")
        print(v.text)
        for ruling in v.rulings:
            print(f"  -> lihat {ruling}")
        print()


def cmd_history(args: argparse.Namespace) -> None:
    from pasalkini.temporal.query import history, validity, word_diff
    from pasalkini.temporal.store import load_versions

    versions = history(load_versions(), args.provision)
    if not versions:
        print(f"No versions for {args.provision}")
        return
    previous = None
    for v in versions:
        print(f"== {v.label} [{v.status}] {validity(v)}")
        print(
            f"   teks dari {v.source_id}"
            + (f"; putusan: {', '.join(v.rulings)}" if v.rulings else "")
        )
        if previous is None or not args.diff:
            print(v.text)
        elif previous.text != v.text:
            print(word_diff(previous.text, v.text))
        else:
            print("(bunyi sama dengan versi sebelumnya)")
        print()
        previous = v


def cmd_compare(args: argparse.Namespace) -> None:
    from pasalkini.evals.compare import compare
    from pasalkini.evals.runner import RUNS_DIR

    table = compare([RUNS_DIR / r for r in args.runs], split=args.split, category=args.category)
    print(table)


def cmd_funnel(args: argparse.Namespace) -> None:
    from pasalkini.evals.compare import funnel
    from pasalkini.evals.runner import RUNS_DIR

    runs = sorted(p for p in RUNS_DIR.iterdir() if p.is_dir())
    print(funnel(RUNS_DIR / args.run if args.run else runs[-1]))


def cmd_rescore(args: argparse.Namespace) -> None:
    from pasalkini.evals.runner import RUNS_DIR, rescore

    runs = sorted(p for p in RUNS_DIR.iterdir() if p.is_dir())
    run_dir = RUNS_DIR / args.run if args.run else runs[-1]
    rescore(run_dir)
    print((run_dir / "summary.md").read_text(encoding="utf-8"))


def cmd_judge(args: argparse.Namespace) -> None:
    from pasalkini.evals.judge import judge_run, read_grades, totals
    from pasalkini.evals.runner import RUNS_DIR

    path = judge_run(RUNS_DIR / args.run, split=args.split)
    print(
        f"Judge's grades saved to {path.relative_to(path.parents[3])}: {totals(read_grades(path))}"
    )


def cmd_agreement(args: argparse.Namespace) -> None:
    from pasalkini.evals.judge import agreement, read_grades, totals
    from pasalkini.evals.runner import RUNS_DIR

    for name in args.runs:
        run_dir = RUNS_DIR / name
        judged = {}
        for path in sorted(run_dir.glob("judge*.csv")):
            judged.update(read_grades(path))
        for path in sorted(run_dir.glob("grades-*.csv")):
            reference = read_grades(path)
            print(f"\n{name}: {path.name} ({totals(reference)}) against the judge")
            print("\n".join(agreement(reference, judged)))


def cmd_rulings(_: argparse.Namespace) -> None:
    from pasalkini.answer.context import instrument_label
    from pasalkini.temporal.corpus import load_dated_corpus
    from pasalkini.temporal.rulings import reading

    for chunk in load_dated_corpus():
        if "/amar-" in chunk.source_id:
            print(chunk.source_id)
            print("  " + reading(chunk.text, instrument_label(chunk.source_id)))
            print()


def cmd_ask(args: argparse.Namespace) -> None:
    from datetime import date

    from pasalkini.answer.generate import generate
    from pasalkini.pipelines import CONFIGS, load_chunks
    from pasalkini.retrieve.dense import DenseIndex
    from pasalkini.retrieve.hybrid import expand_query
    from pasalkini.retrieve.lexical import BM25Index
    from pasalkini.retrieve.search import make_search
    from pasalkini.retrieve.temporal import retrieve
    from pasalkini.sources import load_topics

    config = CONFIGS[args.config]
    chunks = load_chunks(config)
    index = DenseIndex.build(
        config.embed_model, chunks, config.embed_num_ctx, with_titles=config.chunk_headers
    )
    lexical = BM25Index(chunks) if config.retriever != "dense" else None
    if config.answer_mode != "baseline":
        ask_pipeline(args, config, chunks, index, lexical)
        return
    text = expand_query(args.question, load_topics()) if config.rewrite_query else args.question
    query_vector = index.embed_query(text, config.query_instruction, config.embed_num_ctx)
    search = make_search(config.retriever, config.top_k, index, query_vector, lexical, text)
    date_hint = date.fromisoformat(args.date) if args.date else None
    retrieval = retrieve(
        search,
        args.question,
        date_hint=date_hint,
        date_filter=config.date_filter,
        history_cues=config.history_cues,
    )
    hits = retrieval.hits
    as_of = retrieval.as_of if config.date_filter else date_hint
    result = generate(
        config.chat_model,
        args.question,
        as_of,
        [chunk for chunk, _ in hits],
        max_chars=config.max_chars_per_chunk,
        think=config.think,
        temperature=config.temperature,
        seed=config.seed,
        num_ctx=config.num_ctx,
        max_tokens=config.max_answer_tokens,
    )
    print("Informasi hukum, bukan nasihat hukum. Dijawab oleh AI.\n")
    if result.answer:
        print(result.answer.answer)
        print("\nSumber:", ", ".join(result.answer.citations) or "(tidak ada)")
    else:
        print(result.raw)
    if retrieval.as_of and config.date_filter:
        print(f"\nDiambil ({config.name}, per {retrieval.as_of}, mode {retrieval.mode}):")
    else:
        print(f"\nDiambil ({config.name}, tanpa filter tanggal):")
    for chunk, score in hits:
        print(f"  {score:.3f}  {chunk.source_id:<40} {chunk.title}")
    print(f"\n{result.seconds:.1f} s, {result.prompt_tokens} + {result.output_tokens} tokens")


def ask_pipeline(args: argparse.Namespace, config, chunks, index, lexical) -> None:
    from datetime import date

    from pasalkini.answer.agent import Agent
    from pasalkini.answer.pipeline import Pipeline
    from pasalkini.sources import load_topics

    # The embedding model runs on the CPU here: the 6 GB GPU cannot hold it next to the chat
    # model, and on the CPU it can stay loaded between questions.
    query_vector = index.embed_query(
        args.question, config.query_instruction, config.embed_num_ctx, on_cpu=True
    )
    date_hint = date.fromisoformat(args.date) if args.date else None
    kind = Agent if config.answer_mode == "agent" else Pipeline
    pipeline = kind(config, chunks, index, lexical, load_topics())
    outcome = pipeline.run(args.question, date_hint, query_vector)
    u = outcome.understanding
    print("Informasi hukum, bukan nasihat hukum. Dijawab oleh AI.\n")
    print(outcome.display())
    print(
        f"\nTanggal {u.as_of} ({u.as_of_source}); jenis pertanyaan {u.intent} ({u.method}); "
        f"keyakinan {outcome.confidence}"
    )
    print("Konteks:")
    for chunk in outcome.context:
        print(f"  {chunk.source_id:<40} {chunk.title}")
    if outcome.steps:
        print("Langkah agen: " + ", ".join(outcome.steps))
    if outcome.retried:
        print("Kutipan dipilih ulang setelah pemeriksaan: " + "; ".join(outcome.first_problems))
    if outcome.rewritten:
        print("Jawaban ditulis ulang setelah pemeriksaan: " + "; ".join(outcome.answer_problems))
    print(", ".join(f"{step} {seconds:.1f} s" for step, seconds in outcome.seconds.items()))


def cmd_fixture(_: argparse.Namespace) -> None:
    from pasalkini.evals.gate import FIXTURE_PATH, build_fixture

    meta = build_fixture()
    size = FIXTURE_PATH.stat().st_size / 1e6
    print(f"Wrote {FIXTURE_PATH.relative_to(FIXTURE_PATH.parents[2])} ({size:.1f} MB)")
    print(f"Baseline: {meta['baseline']}")
    print("Commit it: the retrieval gate in CI compares against this file.")


def cmd_gate(_: argparse.Namespace) -> None:
    from pasalkini.evals.gate import check

    passed, lines = check()
    print("\n".join(lines))
    if not passed:
        raise SystemExit(1)


def cmd_misread(args: argparse.Namespace) -> None:
    from pasalkini.evals.misread import run, totals

    print(f"Every ordinary development question, read as '{args.kind}':")
    results = run(args.kind)
    for name, value in totals(results).items():
        print(f"{name}: {value}")
    if any(result.stale_cited for result in results):
        raise SystemExit(1)


def cmd_setup(args: argparse.Namespace) -> None:
    """Everything between a fresh clone and a running app: download, parse, build, index."""
    print("1/4 Download: the official PDFs (skipped where already downloaded)")
    cmd_download(argparse.Namespace(only=None, force=False))
    print("2/4 Parse: PDFs to articles, amendment points and MK rulings")
    cmd_parse(argparse.Namespace(only=None))
    print("3/4 Build: events and article versions with the dates they applied")
    cmd_build(args)
    print("4/4 Index: embed the article versions (needs Ollama; cached afterwards)")
    cmd_index(argparse.Namespace(config="pasalkini"))
    print("\nReady. Start the app with: uv run pasalkini serve")


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    from pasalkini.api.main import create_app
    from pasalkini.service import Service

    config = {"qwen": "pasalkini", "gemini": "pasalkini-gemini"}[args.model]
    app = create_app(Service.load(config))
    print(f"PasalKini: http://{args.host}:{args.port}  (API: /docs, UI: /ui)")
    if args.model == "gemini":
        print("Answers are written by Gemini over the internet; embeddings stay on this machine.")
    uvicorn.run(app, host=args.host, port=args.port)


def main() -> None:
    # Windows consoles default to a legacy code page when output is piped.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="pasalkini")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="show manifest and evaluation-set status (default)")

    download = sub.add_parser("download", help="download the PDFs in the manifest")
    download.add_argument("--only", nargs="+", metavar="ID", help="only these instrument ids")
    download.add_argument("--force", action="store_true", help="download even if unchanged")

    parse = sub.add_parser("parse", help="extract and parse the downloaded PDFs")
    parse.add_argument("--only", nargs="+", metavar="ID", help="only these instrument ids")

    spot = sub.add_parser("spotcheck", help="write docs/spot-check.md for checking against PDFs")
    spot.add_argument("--n", type=int, default=30, help="number of articles (default 30)")

    from pasalkini.pipelines import CONFIGS

    index = sub.add_parser("index", help="embed the parsed corpus (cached)")
    index.add_argument("--config", default="baseline", choices=sorted(CONFIGS))

    evaluate = sub.add_parser("eval", help="run a pipeline over the evaluation set")
    evaluate.add_argument("config", nargs="?", default="baseline", choices=sorted(CONFIGS))
    evaluate.add_argument("--retrieval-only", action="store_true", help="skip answer generation")
    evaluate.add_argument("--split", choices=["dev", "test"], help="only this split")
    evaluate.add_argument(
        "--dataset",
        default="golden",
        choices=["golden", "variants"],
        help="golden: the 78 questions (default); variants: the same questions reworded",
    )

    sub.add_parser("build", help="build the temporal model (events and article versions)")
    sub.add_parser("rulings", help="MK ruling points as the answer step reads them, for review")

    law = sub.add_parser("law", help="an instrument as it stood on a date")
    law.add_argument("instrument", help="e.g. uu-13-2003")
    law.add_argument("--date", required=True, help="YYYY-MM-DD")
    law.add_argument("--pasal", nargs="+", help="only these articles, e.g. 59 61A")

    hist = sub.add_parser("history", help="every version of one article")
    hist.add_argument("provision", help="e.g. uu-13-2003/pasal-79")
    hist.add_argument("--diff", action="store_true", help="show word-level changes")

    comp = sub.add_parser("compare", help="compare saved runs side by side")
    comp.add_argument("runs", nargs="+", help="run folder names under evals/runs")
    comp.add_argument("--split", choices=["dev", "test"], help="only this split")
    comp.add_argument("--category", help="only this category, e.g. temporal_trap")

    lost = sub.add_parser("funnel", help="where answerable questions are lost")
    lost.add_argument("run", nargs="?", help="run folder name (default: the latest)")

    rescore = sub.add_parser("rescore", help="recompute a saved run against the current keys")
    rescore.add_argument("run", nargs="?", help="run folder name (default: the latest)")

    judge = sub.add_parser("judge", help="grade a saved run's answers with the local model")
    judge.add_argument("run", help="run folder name under evals/runs")
    judge.add_argument("--split", choices=["dev", "test"], help="only this split")

    agree = sub.add_parser("agreement", help="compare the judge with grades given by reading")
    agree.add_argument("runs", nargs="+", help="run folder names under evals/runs")

    ask = sub.add_parser("ask", help="ask one question")
    ask.add_argument("question")
    ask.add_argument("--date", help="the date that decides which law applies (YYYY-MM-DD)")
    ask.add_argument("--config", default="pasalkini", choices=sorted(CONFIGS))

    sub.add_parser("gate", help="the CI check: retrieval on the committed snapshot (no Ollama)")
    sub.add_parser("fixture", help="remake the snapshot the gate compares against")
    misread = sub.add_parser(
        "misread", help="force a wrong reading of the question's kind; count stale citations"
    )
    misread.add_argument("kind", choices=["status", "riwayat"])
    sub.add_parser("setup", help="download, parse, build and index: from a fresh clone to ready")
    serve = sub.add_parser("serve", help="run the app: the API and the four screens")
    # 127.0.0.1: reachable from this machine only. The app has no login and no rate limit.
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--model",
        choices=["qwen", "gemini"],
        default="qwen",
        help="who writes the answers: qwen3.5:4b on this machine (default) or Gemini "
        "(needs GEMINI_API_KEY; the redacted question and the quoted law are sent to Google)",
    )

    args = parser.parse_args()
    handlers = {
        "gate": cmd_gate,
        "misread": cmd_misread,
        "fixture": cmd_fixture,
        "setup": cmd_setup,
        "serve": cmd_serve,
        "download": cmd_download,
        "parse": cmd_parse,
        "spotcheck": cmd_spotcheck,
        "index": cmd_index,
        "eval": cmd_eval,
        "rescore": cmd_rescore,
        "judge": cmd_judge,
        "agreement": cmd_agreement,
        "funnel": cmd_funnel,
        "compare": cmd_compare,
        "build": cmd_build,
        "rulings": cmd_rulings,
        "law": cmd_law,
        "history": cmd_history,
        "ask": cmd_ask,
    }
    handlers.get(args.command, cmd_status)(args)


if __name__ == "__main__":
    main()
