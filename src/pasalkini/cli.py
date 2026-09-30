"""Command-line entry point. For now it reports the state of the project's data files."""

from collections import Counter

from pasalkini import __version__
from pasalkini.evals.schema import load_golden
from pasalkini.sources import load_manifest, load_topics


def main() -> None:
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


if __name__ == "__main__":
    main()
