"""The question log: one file per day, deleted after the retention period."""

from datetime import date, datetime

from pasalkini.privacy.log import QuestionLog


def test_a_line_is_appended_to_the_days_file(tmp_path):
    log = QuestionLog(tmp_path)
    log.write({"question": "Berapa jam lembur?"}, now=datetime(2026, 10, 1, 9, 30, 5))
    log.write({"question": "Apa itu PKWT?"}, now=datetime(2026, 10, 1, 9, 31))
    log.write({"question": "Besoknya"}, now=datetime(2026, 10, 2, 8, 0))
    first, second = log.read(date(2026, 10, 1))
    assert first == {"at": "2026-10-01T09:30:05", "question": "Berapa jam lembur?"}
    assert second["question"] == "Apa itu PKWT?"
    assert [entry["question"] for entry in log.read(date(2026, 10, 2))] == ["Besoknya"]
    assert log.read(date(2026, 10, 3)) == []


def test_files_older_than_the_retention_period_are_deleted(tmp_path):
    log = QuestionLog(tmp_path, retention_days=30)
    for day in ("2026-08-31", "2026-09-01", "2026-09-30"):
        (tmp_path / f"{day}.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "catatan.jsonl").write_text("{}\n", encoding="utf-8")  # not named for a day
    deleted = log.purge(date(2026, 10, 1))
    assert [path.name for path in deleted] == ["2026-08-31.jsonl"]
    left = sorted(path.name for path in tmp_path.iterdir())
    assert left == ["2026-09-01.jsonl", "2026-09-30.jsonl", "catatan.jsonl"]


def test_old_files_go_with_the_first_question_of_a_day(tmp_path):
    log = QuestionLog(tmp_path, retention_days=30)
    (tmp_path / "2026-08-01.jsonl").write_text("{}\n", encoding="utf-8")
    log.write({"question": "a"}, now=datetime(2026, 10, 1, 9, 0))
    assert not (tmp_path / "2026-08-01.jsonl").exists()
    # Not on every write: a file that turns up later in the day waits for the next day.
    (tmp_path / "2026-08-02.jsonl").write_text("{}\n", encoding="utf-8")
    log.write({"question": "b"}, now=datetime(2026, 10, 1, 9, 5))
    assert (tmp_path / "2026-08-02.jsonl").exists()
    log.write({"question": "c"}, now=datetime(2026, 10, 2, 9, 0))
    assert not (tmp_path / "2026-08-02.jsonl").exists()
