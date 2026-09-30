# Evaluation datasets

`golden.jsonl` holds one test question per line. The schema lives in `src/pasalkini/evals/schema.py`, and `uv run pytest` checks every line.

## How to review a draft item

1. Read the articles named in `notes` in the official PDF, for the law that applied on `as_of`.
2. Fill `expected_sources` with source IDs, for example `uu-13-2003/pasal-59` or `perppu-2-2022/pasal-81/angka-15`. An instrument id on its own (`uu-11-2020`) means "anything from that instrument".
3. Add the wording of other versions of the same article to `must_not_cite`.
4. Write `expected_points`: short facts a correct answer must contain, in Bahasa Indonesia.
5. Set `"source": "human"` and `"review": "done"`. The tests will then require the fields above.

## Current state

61 items, all `review: needed`. A key becomes `done` only after a person has checked it against the official text; marking unchecked keys as done would turn possible errors into passing tests.

- The first 20 have keys drafted by an AI on 2026-09-30 from secondary sources (see `review-notes-2026-09-30.md`).
- The 41 added on 2026-10-01 have keys drafted from the parsed primary texts, with exact article, amendment-point or MK ruling IDs. Each item's `notes` gives its confidence.
- On 2026-10-01, `must_not_cite` of nine earlier items was extended with superseded wording: the original UU 13/2003 text of articles replaced on 2 November 2020, and UU 11/2020 itself for dates after it was revoked on 30 December 2022.

Items dated 2026-09-30 (`status-*`, `abstain-*`, `adversarial-*`) must be re-checked when the new labor law takes effect.

`uv run pytest` checks that every article-, point- or ruling-level label matches a chunk of the parsed corpus. After changing keys, `uv run pasalkini rescore` recomputes the latest run without generating new answers.

## Kinds of forbidden sources

A `must_not_cite` label can mean either of two things:

- **Not yet in force** on `as_of`: a later instrument, such as `pp-35-2021` for a 2019 question.
- **No longer in force**: wording that was replaced, such as `uu-13-2003/pasal-59` for a 2022 question (amended by UU 11/2020), or `uu-11-2020` after 30 December 2022.

## Rules

- Keep the two or three items of a `pair_id` in the same split.
- Never tune prompts or retrieval on `split: test`.
- `as_of` is the date that decides which law applies: the dismissal date, the contract signing date, and so on.
