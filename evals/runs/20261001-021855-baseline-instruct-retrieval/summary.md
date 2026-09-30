# Evaluation run: 20261001-021855-baseline-instruct-retrieval

**Pipeline:** `baseline-instruct`: As baseline, with the Qwen3-Embedding query instruction.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84)
- Git commit: `44755f5c4f` (uncommitted changes)
- Corpus: 596 chunks, fingerprint `4232c9324eb12fe8`
- Dataset: 20 items, sha256 `28f7b25db22d`
- Mode: retrieval only

> **Provisional.** 0 of 20 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 20 | 0.52 | 89% (16/18) | 86% (12/14) | n/a | n/a | n/a | n/a | n/a |
| adversarial | 1 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| calculation | 1 | 0.50 | 100% (1/1) | 0% (0/1) | n/a | n/a | n/a | n/a | n/a |
| date_extraction | 2 | 0.33 | 50% (1/2) | 100% (2/2) | n/a | n/a | n/a | n/a | n/a |
| should_abstain | 1 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| stable_rule | 1 | 1.00 | 100% (1/1) | n/a | n/a | n/a | n/a | n/a | n/a |
| status | 2 | 0.42 | 100% (2/2) | n/a | n/a | n/a | n/a | n/a | n/a |
| temporal_trap | 11 | 0.56 | 91% (10/11) | 90% (9/10) | n/a | n/a | n/a | n/a | n/a |
| what_changed | 1 | 0.20 | 100% (1/1) | 100% (1/1) | n/a | n/a | n/a | n/a | n/a |
| split: dev | 14 | 0.48 | 83% (10/12) | 78% (7/9) | n/a | n/a | n/a | n/a | n/a |
| split: test | 6 | 0.61 | 100% (6/6) | 100% (5/5) | n/a | n/a | n/a | n/a | n/a |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
