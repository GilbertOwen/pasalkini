"""Command-line entry point: `uv run pasalkini <command>`."""

import argparse
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


def main() -> None:
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

    args = parser.parse_args()
    handlers = {"download": cmd_download, "parse": cmd_parse, "spotcheck": cmd_spotcheck}
    handlers.get(args.command, cmd_status)(args)


if __name__ == "__main__":
    main()
