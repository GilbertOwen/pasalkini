"""Answers already given, so that the same question about the same date is not answered twice.

A cached answer is reused only when nothing it was made from has changed. The key holds:
- the question, with case and spacing folded;
- the date that decides the law, and whether it came from the question, the date picker or today;
- the corpus fingerprint, and the last day on which law in the corpus took effect: an answer
  about a past date says what changed afterwards, and that grows when a later wording begins;
- the chat model and its settings;
- a fingerprint of the package's code and rules, so that a changed prompt or check is a new key.

The key is a hash: the question itself is not stored. The service neither stores nor looks up a
question in which personal data was found.
"""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from functools import cache
from pathlib import Path

from pasalkini.paths import DATA_DIR, TOPICS_PATH

CACHE_PATH = DATA_DIR / "cache" / "answers.db"
MAX_ENTRIES = 5000  # the oldest go first; an answer is a few kilobytes
PACKAGE_DIR = Path(__file__).parent
SCHEMA = "CREATE TABLE IF NOT EXISTS answer (key TEXT PRIMARY KEY, created TEXT, payload TEXT)"


@cache
def code_fingerprint() -> str:
    """Changes whenever a source file, a rules file or the abbreviations list changes."""
    digest = hashlib.sha256()
    files = sorted([*PACKAGE_DIR.rglob("*.py"), *PACKAGE_DIR.rglob("*.yaml"), TOPICS_PATH])
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def answer_key(
    question: str,
    as_of: date,
    as_of_source: str,
    corpus: str,
    law_as_of: date | None,
    model: str,
    code: str,
) -> str:
    parts = [
        " ".join(question.lower().split()),
        as_of.isoformat(),
        as_of_source,
        corpus,
        law_as_of.isoformat() if law_as_of else "",
        model,
        code,
    ]
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()


class AnswerCache:
    def __init__(self, path: Path = CACHE_PATH, max_entries: int = MAX_ENTRIES) -> None:
        self.path = path
        self.max_entries = max_entries
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """One connection per call, committed and closed: an open one keeps the file locked on
        Windows."""
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, key: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM answer WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, payload: dict) -> None:
        created = datetime.now().isoformat(timespec="seconds")
        text = json.dumps(payload, ensure_ascii=False)
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO answer VALUES (?, ?, ?)", (key, created, text))
            db.execute(
                "DELETE FROM answer WHERE key NOT IN "
                "(SELECT key FROM answer ORDER BY created DESC, rowid DESC LIMIT ?)",
                (self.max_entries,),
            )

    def __len__(self) -> int:
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM answer").fetchone()[0]

    def clear(self) -> int:
        with self.connect() as db:
            return db.execute("DELETE FROM answer").rowcount
