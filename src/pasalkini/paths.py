"""Well-known locations inside the repository."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SOURCES_DIR = ROOT / "sources"
MANIFEST_PATH = SOURCES_DIR / "manifest.yaml"
TOPICS_PATH = SOURCES_DIR / "topics.yaml"

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

EVALS_DIR = ROOT / "evals"
GOLDEN_PATH = EVALS_DIR / "datasets" / "golden.jsonl"
