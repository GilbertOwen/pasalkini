# Dataset card (draft): PasalKini temporal labor-law questions

> **Not published, and not ready to be.** All 78 answer keys and all 78 rewordings were drafted by an AI and none has been checked by a person (`review: needed`). Publishing this as a benchmark before that review would hand other people unverified legal claims as ground truth. This card is written now so that the review has a target.

## What it is

Questions about Indonesian labor law (hukum ketenagakerjaan), each tied to **a date**. The same question has different right answers on different dates, because the law changed: UU 13/2003, UU 11/2020, Perppu 2/2022 and UU 6/2023, their government regulations, and Constitutional Court rulings.

It tests one thing most legal question sets do not: whether a system answers with the law that applied **on the date asked about**, and whether it avoids citing wording that had not started or had already ended.

| File | Lines | Contents |
|---|---|---|
| `evals/datasets/golden.jsonl` | 78 | The questions, with dates, expected sources, forbidden sources and answer points |
| `evals/datasets/variants.jsonl` | 78 | One rewording of each question; everything else is taken from the original |

Language: Bahasa Indonesia (questions and answer points). Field names and notes are in English.

## An example pair

```json
{"id": "pkwt-001-a", "pair_id": "pkwt-001", "as_of": "2019-06-01", "category": "temporal_trap",
 "question": "Berapa lama maksimal jangka waktu kontrak kerja (PKWT) yang didasarkan atas jangka waktu, termasuk perpanjangannya?",
 "expected_sources": ["uu-13-2003/pasal-59"],
 "must_not_cite": ["uu-11-2020", "perppu-2-2022", "uu-6-2023", "pp-35-2021", "mk-168-puu-xxi-2023"],
 "expected_points": ["PKWT berdasarkan jangka waktu paling lama 2 tahun dan hanya boleh diperpanjang 1 kali untuk paling lama 1 tahun, ...", "..."]}
{"id": "pkwt-001-b", "pair_id": "pkwt-001", "as_of": "2022-06-01", "category": "temporal_trap",
 "question": "(the same question)",
 "expected_sources": ["uu-11-2020", "pp-35-2021", "mk-91-puu-xviii-2020"],
 "must_not_cite": ["uu-6-2023", "mk-168-puu-xxi-2023", "perppu-2-2022", "uu-13-2003/pasal-59"],
 "expected_points": ["PP 35/2021 Pasal 8: PKWT berdasarkan jangka waktu paling lama 5 tahun, ...", "..."]}
```

## Fields

| Field | Meaning |
|---|---|
| `id`, `pair_id` | A question, and the group of the same question asked about different dates. A pair is never split between `dev` and `test` |
| `question` | As a person would ask it |
| `as_of` | The date that decides which law applies. For `date_extraction` items the date is only in the question text and the system has to read it there |
| `category` | See below |
| `topic` | `pesangon`, `phk`, `pkwt`, `upah`, `istirahat-cuti`, `waktu-kerja-lembur`, `alih-daya`, `pkwtt-percobaan` |
| `expected_sources` | Source IDs a right answer rests on. `uu-13-2003/pasal-59` is an article; `perppu-2-2022/pasal-81/angka-15` is the amending point that carries an article's new wording; `mk-168-puu-xxi-2023/amar-4` is one point of a ruling. An instrument ID alone (`uu-11-2020`) means any part of it |
| `must_not_cite` | Sources that did not apply on `as_of`: not yet in force, or already replaced |
| `expected_points` | Short facts a right answer contains, and things it must not say |
| `should_abstain` | The right response is a refusal (another field of law, or a request to act as a lawyer) |
| `split` | `dev` (42) to work from, `test` (36) to hold back |
| `source`, `review`, `notes` | Who wrote the key, whether a person has checked it, and what it was drafted from |

`variants.jsonl` has `id` (the original's with `-v`), `variant_of`, `style` (`istilah`, `santai`, `cerita`, `susunan`) and `question`.

## What is in it

| Category | Items | What it tests |
|---|---|---|
| `temporal_trap` | 40 | The same question on dates with different law |
| `should_abstain` | 8 | Tax, criminal, family law; "be my lawyer" |
| `date_extraction` | 7 | The date is in the question ("Agustus 2019", "Maret 2019 lalu") |
| `stable_rule` | 5 | Rules that did not change: a system should not invent a change |
| `calculation` | 5 | Severance and PKWT compensation with a wage and length of service |
| `adversarial` | 5 | Instructions inside the question ("abaikan aturan ...") |
| `status` | 4 | Is a named article still in force? |
| `what_changed` | 4 | What changed between the old rule and the new |

Dates asked about: 2019 (18), 2020 (1), 2021 (4), 2022 (15), 2023 (6), 2024 (7), 2025 (8), 2026 (19).

## Sources

Only official publications: peraturan.go.id, the BPK regulation database (peraturan.bpk.go.id) and mkri.id. Laws, regulations and court decisions carry no copyright in Indonesia (UU 28/2014 Pasal 42). The texts themselves are not part of this dataset; source IDs refer to articles and amending points of:

UU 13/2003; UU 11/2020; Perppu 2/2022 and UU 6/2023; PP 35/2021, PP 36/2021, PP 51/2023, PP 49/2025; Permenaker 7/2026; MK 19/PUU-IX/2011, MK 91/PUU-XVIII/2020, MK 168/PUU-XXI/2023.

No question comes from a real person. All were written for this project.

## How to score with it

- **Stale citation rate**: share of answers whose sources include a `must_not_cite` label. A label matches a source ID that equals it or starts with it plus `/`.
- **Expected source cited**: any `expected_sources` label among the answer's sources.
- **Abstention**: refused exactly when `should_abstain`.
- **Correctness**: read the answer against `expected_points`. In this project that was done by an AI on the `dev` split, with three grades (correct, partly, wrong), and by an automatic judge on `test`.

Reference numbers for one system are in `docs/eval-results.md`.

## Known limits

- **Unreviewed.** The first 20 keys were drafted from secondary sources, the rest from the parsed primary texts. Each item's `notes` says which and how confident the draft is.
- **Small**: 78 questions, 8 topics, one country's labor law, the changes of 2020 to 2025.
- **Clean wording.** The originals are short and formal. The rewordings help, but they are one each, and written by the same AI.
- **Dated.** Items with `as_of` 2026-09-30 (`status-*`, `abstain-*`, `adversarial-*`) describe the law before the new labor law expected in October 2026 and must be re-checked when it takes effect.
- **Document-level labels** on some items (`uu-11-2020`) are looser than article-level ones.
- Older Constitutional Court rulings on UU 13/2003 are not modelled, so some keys treat those articles as in force until 2020.

## Before this can be published

1. A person with legal training checks every key against the official text and sets `review: done`.
2. The same for the rewordings: does each still ask what its original asks?
3. A licence is chosen (the plan suggests CC BY 4.0 for the questions and keys).
4. The owner of the project decides to publish. Until then this stays in a private repository.
