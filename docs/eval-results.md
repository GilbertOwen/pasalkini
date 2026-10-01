# Evaluation results

Status on 2026-10-01, at the end of Phase 5. This page is rewritten as the evaluation grows (Phase 6 of `PLAN.md`).

## Read this first

- **The answer keys are drafts.** All 78 were written by an AI from the parsed legal texts and none has been checked by a person yet. Numbers can move when they are.
- **The set is small.** 78 questions: 42 for development and 36 held out. One question is 1 to 3 percentage points.
- **The metrics are about sources, not sentences.** They say which texts reached the model and which it cited. Whether the answer's own sentences are right needs hand grading (`grading.csv` in each run folder), which has not been done.
- Everything runs locally: `qwen3.5:4b` and `qwen3-embedding:0.6b` on a laptop RTX 3060 (6 GB).

## 1. Does the answer cite law that did not apply on the date?

All 78 questions, runs of 2026-10-01 10:46 to 11:21 (commit `b80bc1e`; `pasalkini` at `3a63d25`). 57 questions name sources that must not be cited; 67 have an expected source.

| Pipeline | Stale text given to the model | Answer cites a stale source | Answer cites an expected source | Cites an ID it was not given | Median s |
|---|---|---|---|---|---|
| `baseline`: plain RAG, dates ignored | 88% (50/57) | 65% (37/57) | 64% (43/67) | 3% (2/71) | 3.1 |
| `versions`: each chunk labelled with its validity dates, no filter | 82% (47/57) | 65% (37/57) | 66% (44/67) | 16% (11/69) | 3.1 |
| `temporal`: only versions that applied on the date are searched | 0% (0/57) | 0% (0/56) | 88% (58/66) | 7% (5/68) | 3.3 |
| `temporal-hybrid`: the same, dense + BM25 | 0% (0/57) | 0% (0/57) | 84% (56/67) | 7% (5/70) | 3.0 |
| `pasalkini`: the Phase 5 pipeline | 0% (0/57) | 0% (0/57) | 91% (61/67) | 0% (0/68) | 6.7 |

- **Labels are not enough.** Telling the model when each text applied (`versions`) left stale citations where they were, at 65%, and it cited IDs it was not given more often (16%). Removing outdated text before the search is what works.
- On the 36 held-out questions: stale citations 58% (14/24) for `baseline` and 0% (0/24) for `temporal`, `temporal-hybrid` and `pasalkini`; an expected source cited in 47% (14/30), 90% (27/30), 83% (25/30) and 93% (28/30).

## 2. Retrieval

Development split, 42 questions, retrieval only (runs of 2026-10-01 09:34, commit `cb34bf0`).

| Configuration | Recall@5 | MRR@10 | Stale text in top 5 |
|---|---|---|---|
| `baseline` (dense, dates ignored) | 0.61 | 0.56 | 91% (30/33) |
| `versions` (dated chunks, no filter) | 0.44 | 0.48 | 85% (28/33) |
| `temporal` (dense, date filter) | 0.68 | 0.77 | 0% |
| `temporal` + query rewriting | 0.71 | 0.77 | 0% |
| `temporal` + titles embedded with the text | 0.68 | 0.77 | 0% |
| `temporal-bm25` | 0.67 | 0.77 | 0% |
| `temporal-hybrid` (dense + BM25, RRF) | **0.73** | 0.81 | 0% |
| `temporal-hybrid` + query rewriting | 0.70 | 0.79 | 0% |
| `temporal-hybrid` + embedded titles | 0.72 | **0.82** | 0% |
| `temporal-hybrid` + both | 0.71 | 0.77 | 0% |

- The date filter is the large effect. It removes stale text, and MRR rises from 0.56 to 0.77 because outdated versions of the right article no longer take the top ranks.
- Hybrid search was chosen on these numbers. The held-out questions do not confirm it: on the 36 test questions dense search has Recall@5 0.77 and MRR 0.90, hybrid 0.73 and 0.82. The choice is a weak one.
- The planned target, Recall@5 ≥ 0.90, is not met. Untried because each needs a download of about 2 GB: a reranker (`bge-reranker-v2-m3`) and `bge-m3` embeddings.

## 3. The answer pipeline (Phase 5)

Run `20261001-111235-pasalkini`, all 78 questions.

| Check | All | Development | Held out |
|---|---|---|---|
| Refused or abstained exactly when it should | 100% (78/78) | 42/42 | 36/36 |
| Kind of question classified correctly | 100% (71/71) | 38/38 | 33/33 |
| Date read from the question | 100% (10/10) | 5/5 | 5/5 |
| First answer passes every citation check | 88% (60/68) | 95% (36/38) | 80% (24/30) |
| Sent back once for repair | 12% (8/68) | 2 | 6 |
| Final answer still had a citation dropped | 6% (4/68) | 1 | 3 |

- The held-out column is the one to trust for refusals and the calculator: the out-of-scope list in the classifier prompt was tuned on the development split, and the 17 questions that make refusals, calculations and injected instructions testable were written afterwards and not looked at one by one.
- Citations shown to the user are valid by construction: only citations that passed the check are shown, in the source's own words.
- The pipeline takes about twice as long as plain RAG (6.7 s against 3.1 s): one extra call to classify the question, longer answers with quotes, and a second answer in 12% of cases.
- **How much these numbers move by themselves.** The run before this one (10:38, commit `b80bc1e`) differed only by a prompt rule about conditional MK rulings and a display fix, neither aimed at citations. It had an expected source cited in 62/67 and 61/68 first answers passing. A difference of one or two questions between configurations means nothing at this size.

### Where answerable questions are lost

`uv run pasalkini funnel <run>`. Of the 67 questions that have an expected source:

| Pipeline | Expected source in the context | ... and cited | Lost in retrieval | Lost in the answer |
|---|---|---|---|---|
| `baseline` | 85% (57/67) | 64% (43/67) | 10 | 14 |
| `temporal-hybrid` | 93% (62/67) | 84% (56/67) | 5 | 6 |
| `pasalkini` | 93% (62/67) | 91% (61/67) | 5 | 1 |

The answer step now uses nearly every expected source it is given (61 of 62). What is left to win is in retrieval: 5 questions, 4 of them temporal traps (for example "is the severance table a minimum or a fixed amount?", whose answer sits in the long table of Pasal 156).

### A fixed pipeline or an agent?

Run `20261001-164725-pasalkini-agent` (commit `fe3bf89`). Same date rules, same answer step, same citation check, but the model chooses what to look up: one action per step (search with its own query, an article's history, the calculator, answer, refuse), at most four steps.

| | `pasalkini` (pipeline) | `pasalkini-agent` |
|---|---|---|
| Answer cites a stale source | 0% (0/57) | 0% (0/57) |
| Answer cites an expected source | 91% (61/67) | 81% (54/67) |
| ... on the 36 held-out questions | 93% (28/30) | 77% (23/30) |
| Expected source reaches the context | 93% (62/67) | 85% (57/67) |
| Refuses or abstains exactly when it should | 100% (78/78) | 92% (72/78) |
| First answer passes the citation check | 88% (60/68) | 90% (56/62) |
| Median seconds per question | 6.7 | 9.5 |

- The agent made 2.0 tool calls a question on average: 140 searches, 8 calculator runs and 7 history look-ups. 12 questions used no tool.
- Its own search queries found the expected source less often than searching with the question: it lost 10 questions in retrieval, the pipeline 5.
- It opened an article's history on 5 of the 8 status and what-changed questions. Without it the agent sees only the current wording. In a trial on the development question about overtime it searched four times, never opened the history, and answered that nothing fundamental had changed (the limit went from 3 to 4 hours a day).
- All 6 of its abstention errors were refusals or abstentions on questions it should have answered, two of them adversarial questions. It refused all 8 out-of-scope questions.
- Stale citations stay at 0% either way: the date filter sits inside the search tool, where the model cannot skip it.

For a 4B model on this task the fixed pipeline is better on every count that differs, and takes about 30% less time. The agent stays in the code as a comparison (`uv run pasalkini eval pasalkini-agent`), not as the default.

### The citation check, before and after

The first version of the check wanted the quote word for word. On the 61-question run of 10:21 (commit `0a7276e`), 65% of first answers passed (37/57), 35% were sent back and 21% ended with a citation dropped. Reading every failure on the development split showed the model was rarely inventing text:

- it tidied what it copied: resolved a cross-reference ("sebagaimana dimaksud dalam ayat (1)" became "atas kemauan sendiri"), dropped a list marker, added a full stop, or repaired a word the PDF extraction had broken (the source says "sebagai be-rikut");
- it put a right quote under a wrong ID (`uu-13-2003/pasal-81` for text in `perppu-2-2022/pasal-81/angka-25`);
- it cited the ruling that conditions an article by the ID shown in the article's notes.

The check now locates the quote (word for word, or 80% of its words in order within a stretch about twice its length, and every number), shows the source's own words, and files the citation under the chunk that has them. Replaying the same saved first drafts through it, with no model calls: development 27/38 → 35/38, held out 10/19 → 12/19. On fresh runs: 88% to 90% pass first time.

## 4. What the checks do not catch

Seen while reading development answers:

- **Right citation, wrong sentence.** "Pasal 90 dihapus sejak 30 Desember 2022" for an article deleted since 2 November 2020: the model took the start of the current wording as the date of the change. Code now states the deletion date in the timeline. Re-enacted wordings still need a diff between versions (`BACKLOG.md`).
- **A conditional ruling read as a repeal.** Asked whether Pasal 64 still applies, the model wrote that ayat (2) "tidak memiliki kekuatan hukum mengikat" and left out "sepanjang tidak dimaknai ...". The prompt now explains such rulings and the answer keeps the condition, but its paraphrase of the Court's reading is still loose. The timeline stated by code and the quoted ruling are the reliable part.
- **Overclaiming.** "Kewajiban membayar pesangon bersifat mutlak" in the answer to a prompt-injection question. The citations under it were fine.
- **A wrong fact read from the question** goes straight into an exact calculation. The first calculator run chose the reason `pensiun` for a company that closed after two years of losses and returned Rp63 million instead of Rp18 million, because the model never sees the JSON schema that lists the reason codes. The codes and their meanings are now in the prompt, and the result states the reason, wage and length of service it used so the user can check them.

## 5. Known gaps

- Hand grading has not been done, so there is no number yet for whether answers are right, only for what they cite.
- Retrieval: Recall@5 0.77 on the pipeline's context; the 5 lost questions above.
- Older MK rulings on UU 13/2003 are not in the model, so some articles show as in force until 2020.
- The new labor law (DPR plenary planned for 6 October 2026) is not in the corpus.
