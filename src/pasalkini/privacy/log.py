"""The question log: one line per question in data/logs/YYYY-MM-DD.jsonl, kept for 30 days.

The caller redacts before writing (pasalkini.privacy.redact). A line holds what is needed to see
how the app is used and where it fails: when, the redacted question, the date that decided the
law, the kind of question, whether it was answered, the sources cited and the time each stage
took. It does not hold the answer's text, the caller's address or anything about the browser.

One file per day, so that deleting what is older than the retention period is deleting files.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from pasalkini.paths import DATA_DIR

LOGS_DIR = DATA_DIR / "logs"
RETENTION_DAYS = 30


class QuestionLog:
    def __init__(self, directory: Path = LOGS_DIR, retention_days: int = RETENTION_DAYS) -> None:
        self.directory = directory
        self.retention_days = retention_days
        self.purged_on: date | None = None

    def path(self, day: date) -> Path:
        return self.directory / f"{day.isoformat()}.jsonl"

    def purge(self, today: date) -> list[Path]:
        """Delete the files of days more than `retention_days` ago. Files not named for a day
        are left alone."""
        oldest_kept = today - timedelta(days=self.retention_days)
        deleted = []
        for path in sorted(self.directory.glob("*.jsonl")):
            try:
                day = date.fromisoformat(path.stem)
            except ValueError:
                continue
            if day < oldest_kept:
                path.unlink()
                deleted.append(path)
        self.purged_on = today
        return deleted

    def write(self, entry: dict, now: datetime | None = None) -> None:
        now = now or datetime.now()
        if self.purged_on != now.date():  # at the first question of each day
            self.directory.mkdir(parents=True, exist_ok=True)
            self.purge(now.date())
        line = json.dumps({"at": now.isoformat(timespec="seconds"), **entry}, ensure_ascii=False)
        with self.path(now.date()).open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def read(self, day: date) -> list[dict]:
        path = self.path(day)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
