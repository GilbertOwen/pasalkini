"""Persist events and versions: SQLite for queries, a CSV for human review of events.

sources/events-review.csv is committed. Each rebuild keeps the review verdicts already in it;
events marked 'rejected' are left out of the build.
"""

import csv
import json
import sqlite3
from datetime import date
from pathlib import Path

from pasalkini.paths import PROCESSED_DIR, ROOT, SOURCES_DIR
from pasalkini.sources import load_manifest
from pasalkini.temporal.build import build_versions
from pasalkini.temporal.events import extract_events
from pasalkini.temporal.model import Event, Version

DB_PATH = PROCESSED_DIR / "pasalkini.db"
REVIEW_PATH = SOURCES_DIR / "events-review.csv"
REPORT_PATH = ROOT / "docs" / "temporal-report.md"
REVIEW_FIELDS = [
    "event_id",
    "op",
    "target",
    "effective_on",
    "source_id",
    "note",
    "review",
    "comment",
]

SCHEMA = """
CREATE TABLE event (
  id TEXT PRIMARY KEY, op TEXT NOT NULL, effective_on DATE NOT NULL, source_id TEXT NOT NULL,
  target TEXT NOT NULL, label TEXT, text TEXT, note TEXT, review TEXT NOT NULL
);
CREATE TABLE version (
  version_id TEXT PRIMARY KEY, provision_id TEXT NOT NULL, label TEXT NOT NULL,
  source_id TEXT NOT NULL, text TEXT NOT NULL, valid_from DATE NOT NULL, valid_to DATE,
  status TEXT NOT NULL, rulings TEXT NOT NULL, notes TEXT NOT NULL
);
CREATE INDEX version_provision ON version (provision_id, valid_from);
"""


def load_reviews() -> dict[str, dict]:
    if not REVIEW_PATH.exists():
        return {}
    with REVIEW_PATH.open(encoding="utf-8-sig", newline="") as f:
        return {row["event_id"]: row for row in csv.DictReader(f)}


def write_reviews(events: list[Event], reviews: dict[str, dict]) -> None:
    with REVIEW_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for e in sorted(events, key=lambda e: (e.effective_on, e.source_id, e.target)):
            old = reviews.get(e.id, {})
            writer.writerow(
                {
                    "event_id": e.id,
                    "op": e.op,
                    "target": e.target,
                    "effective_on": e.effective_on.isoformat(),
                    "source_id": e.source_id,
                    "note": " ".join(e.note.split())[:160],
                    "review": old.get("review") or "pending",
                    "comment": old.get("comment", ""),
                }
            )


def write_db(events: list[Event], versions: list[Version], reviews: dict[str, dict]) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.unlink(missing_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(SCHEMA)
        db.executemany(
            "INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    e.id,
                    e.op,
                    e.effective_on.isoformat(),
                    e.source_id,
                    e.target,
                    e.label,
                    e.text,
                    e.note,
                    reviews.get(e.id, {}).get("review") or "pending",
                )
                for e in events
            ],
        )
        db.executemany(
            "INSERT INTO version VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    v.version_id,
                    v.provision_id,
                    v.label,
                    v.source_id,
                    v.text,
                    v.valid_from.isoformat(),
                    v.valid_to.isoformat() if v.valid_to else None,
                    v.status,
                    json.dumps(v.rulings),
                    json.dumps(v.notes, ensure_ascii=False),
                )
                for v in versions
            ],
        )


def load_versions(path: Path = DB_PATH) -> list[Version]:
    if not path.exists():
        raise SystemExit("No temporal model yet. Run `uv run pasalkini build` first.")
    with sqlite3.connect(path) as db:
        rows = db.execute(
            "SELECT version_id, provision_id, label, source_id, text, valid_from, valid_to, "
            "status, rulings, notes FROM version ORDER BY provision_id, valid_from"
        ).fetchall()
    return [
        Version(
            version_id=r[0],
            provision_id=r[1],
            label=r[2],
            source_id=r[3],
            text=r[4],
            valid_from=date.fromisoformat(r[5]),
            valid_to=date.fromisoformat(r[6]) if r[6] else None,
            status=r[7],
            rulings=json.loads(r[8]),
            notes=json.loads(r[9]),
        )
        for r in rows
    ]


def write_report(events: list[Event], versions: list[Version], warnings: list[str]) -> None:
    by_op: dict[str, int] = {}
    for e in events:
        by_op[e.op] = by_op.get(e.op, 0) + 1
    by_status: dict[str, int] = {}
    for v in versions:
        by_status[v.status] = by_status.get(v.status, 0) + 1
    provisions = {v.provision_id for v in versions}
    lines = [
        "# Temporal model report",
        "",
        "Generated by `uv run pasalkini build` from `data/processed/*.json` and "
        "`sources/events-manual.yaml`.",
        "",
        f"- Events: {len(events)} ("
        + ", ".join(f"{op} {n}" for op, n in sorted(by_op.items()))
        + ")",
        f"- Versions: {len(versions)} for {len(provisions)} articles ("
        + ", ".join(f"{s} {n}" for s, n in sorted(by_status.items()))
        + ")",
        "",
        "Every extracted event is listed in `sources/events-review.csv` for review; events "
        "marked `rejected` there are left out.",
        "",
        "## Warnings",
        "",
    ]
    lines += [f"- {w}" for w in warnings] or ["None."]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build() -> tuple[list[Event], list[Version], list[str]]:
    events, warnings = extract_events(load_manifest())
    reviews = load_reviews()
    kept = [e for e in events if reviews.get(e.id, {}).get("review") != "rejected"]
    versions, build_warnings = build_versions(kept)
    warnings += build_warnings
    write_reviews(events, reviews)
    write_db(events, versions, reviews)
    write_report(events, versions, warnings)
    return events, versions, warnings
