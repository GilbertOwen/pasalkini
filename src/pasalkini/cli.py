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
    from pasalkini.corpus import load_corpus
    from pasalkini.pipelines import CONFIGS
    from pasalkini.retrieve.dense import DenseIndex

    config = CONFIGS[args.config]
    chunks = load_corpus()
    index = DenseIndex.build(config.embed_model, chunks, config.num_ctx)
    print(
        f"Index: {len(chunks)} chunks with {config.embed_model} "
        f"({index.newly_embedded} embedded now, the rest from cache), "
        f"fingerprint {index.fingerprint}"
    )


def cmd_eval(args: argparse.Namespace) -> None:
    from pasalkini.evals.runner import run

    mode = "retrieval only" if args.retrieval_only else "retrieval and answers"
    print(f"Evaluating '{args.config}' ({mode})...")
    run_dir = run(args.config, retrieval_only=args.retrieval_only)
    print(f"Run saved to {run_dir.relative_to(run_dir.parents[2])}")
    print((run_dir / "summary.md").read_text(encoding="utf-8"))


def cmd_rescore(args: argparse.Namespace) -> None:
    from pasalkini.evals.runner import RUNS_DIR, rescore

    runs = sorted(p for p in RUNS_DIR.iterdir() if p.is_dir())
    run_dir = RUNS_DIR / args.run if args.run else runs[-1]
    rescore(run_dir)
    print((run_dir / "summary.md").read_text(encoding="utf-8"))


def cmd_ask(args: argparse.Namespace) -> None:
    from datetime import date

    from pasalkini.answer.generate import generate
    from pasalkini.corpus import load_corpus
    from pasalkini.pipelines import CONFIGS
    from pasalkini.retrieve.dense import DenseIndex

    config = CONFIGS[args.config]
    index = DenseIndex.build(config.embed_model, load_corpus(), config.num_ctx)
    hits = index.search(index.embed_query(args.question, config.query_instruction), config.top_k)
    as_of = date.fromisoformat(args.date) if args.date else None
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
    )
    print("Informasi hukum, bukan nasihat hukum. Dijawab oleh AI.\n")
    if result.answer:
        print(result.answer.answer)
        print("\nSumber:", ", ".join(result.answer.citations) or "(tidak ada)")
    else:
        print(result.raw)
    print(f"\nDiambil ({config.name}, tanpa filter tanggal):")
    for chunk, score in hits:
        print(f"  {score:.3f}  {chunk.source_id:<40} {chunk.title}")
    print(f"\n{result.seconds:.1f} s, {result.prompt_tokens} + {result.output_tokens} tokens")


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

    rescore = sub.add_parser("rescore", help="recompute a saved run against the current keys")
    rescore.add_argument("run", nargs="?", help="run folder name (default: the latest)")

    ask = sub.add_parser("ask", help="ask one question")
    ask.add_argument("question")
    ask.add_argument("--date", help="the date that decides which law applies (YYYY-MM-DD)")
    ask.add_argument("--config", default="baseline", choices=sorted(CONFIGS))

    args = parser.parse_args()
    handlers = {
        "download": cmd_download,
        "parse": cmd_parse,
        "spotcheck": cmd_spotcheck,
        "index": cmd_index,
        "eval": cmd_eval,
        "rescore": cmd_rescore,
        "ask": cmd_ask,
    }
    handlers.get(args.command, cmd_status)(args)


if __name__ == "__main__":
    main()
