# Evaluation datasets

`golden.jsonl` holds one test question per line. The schema lives in `src/pasalkini/evals/schema.py`, and `uv run pytest` checks every line.

## How to review a draft item

1. Read the articles named in `notes` in the official PDF, for the law that applied on `as_of`.
2. Fill `expected_sources` with source IDs, for example `uu-13-2003/pasal-59` or `perppu-2-2022/pasal-81/angka-15`. An instrument id on its own (`uu-11-2020`) means "anything from that instrument".
3. Add the wording of other versions of the same article to `must_not_cite`.
4. Write `expected_points`: short facts a correct answer must contain, in Bahasa Indonesia.
5. Set `"source": "human"` and `"review": "done"`. The tests will then require the fields above.

## Current state

All 20 items have answer keys drafted by an AI on 2026-09-30 from secondary sources (see `review-notes-2026-09-30.md` and each item's `notes` for its confidence). They are still `review: needed`. A key becomes `done` only after a person has checked it against the official text; marking unchecked keys as done would turn possible errors into passing tests.

Items dated 2026-09-30 (`status-*`, `abstain-001`, `adversarial-001`) must be re-checked when the new labor law takes effect.

## Rules

- Keep the two or three items of a `pair_id` in the same split.
- Never tune prompts or retrieval on `split: test`.
- `as_of` is the date that decides which law applies: the dismissal date, the contract signing date, and so on.
