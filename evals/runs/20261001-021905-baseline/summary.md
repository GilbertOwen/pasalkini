# Evaluation run: 20261001-021905-baseline

**Pipeline:** `baseline`: Plain RAG: dense search over every version of every article with dates ignored; qwen3.5:4b answers from the top 5 chunks.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `44755f5c4f` (uncommitted changes)
- Corpus: 596 chunks, fingerprint `4232c9324eb12fe8`
- Dataset: 20 items, sha256 `28f7b25db22d`
- Mode: retrieval and answers
- Rescored 2026-10-01T02:29:04 against dataset sha256 `28f7b25db22d` (0 keys reviewed)

> **Provisional.** 0 of 20 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 50% (5/10) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 20 | 0.61 | 94% (17/18) | 64% (9/14) | 50% (7/14) | 78% (14/18) | 10% (2/20) | 100% (20/20) | 6.3 |
| adversarial | 1 | n/a | n/a | n/a | n/a | n/a | 0% (0/1) | 100% (1/1) | 29.2 |
| calculation | 1 | 1.00 | 100% (1/1) | 0% (0/1) | 0% (0/1) | 100% (1/1) | 0% (0/1) | 100% (1/1) | 71.5 |
| date_extraction | 2 | 0.50 | 100% (2/2) | 50% (1/2) | 50% (1/2) | 100% (2/2) | 0% (0/2) | 100% (2/2) | 48.7 |
| should_abstain | 1 | n/a | n/a | n/a | n/a | n/a | 0% (0/1) | 100% (1/1) | 75.1 |
| stable_rule | 1 | 1.00 | 100% (1/1) | n/a | n/a | 100% (1/1) | 0% (0/1) | 100% (1/1) | 3.1 |
| status | 2 | 0.25 | 100% (2/2) | n/a | n/a | 50% (1/2) | 0% (0/2) | 100% (2/2) | 5.4 |
| temporal_trap | 11 | 0.65 | 91% (10/11) | 70% (7/10) | 50% (5/10) | 73% (8/11) | 18% (2/11) | 100% (11/11) | 5.6 |
| what_changed | 1 | 0.40 | 100% (1/1) | 100% (1/1) | 100% (1/1) | 100% (1/1) | 0% (0/1) | 100% (1/1) | 22.3 |
| split: dev | 14 | 0.67 | 100% (12/12) | 78% (7/9) | 56% (5/9) | 92% (11/12) | 14% (2/14) | 100% (14/14) | 7.2 |
| split: test | 6 | 0.50 | 83% (5/6) | 40% (2/5) | 40% (2/5) | 50% (3/6) | 0% (0/6) | 100% (6/6) | 4.8 |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
