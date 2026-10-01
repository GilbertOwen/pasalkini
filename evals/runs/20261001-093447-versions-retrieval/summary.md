# Evaluation run: 20261001-093447-versions-retrieval

**Pipeline:** `versions`: Ablation: one chunk per article version with its validity in the title, but no date filter.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84)
- Git commit: `cb34bf009f`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 61 items, sha256 `2480ce86a1e3`
- Mode: retrieval only

> **Provisional.** 0 of 61 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 61 | 0.49 | 73% (41/56) | 86% (43/50) | n/a | n/a | n/a | n/a | n/a |
| adversarial | 2 | 0.00 | 0% (0/1) | n/a | n/a | n/a | n/a | n/a | n/a |
| calculation | 2 | 0.75 | 100% (2/2) | 50% (1/2) | n/a | n/a | n/a | n/a | n/a |
| date_extraction | 5 | 0.43 | 80% (4/5) | 80% (4/5) | n/a | n/a | n/a | n/a | n/a |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| stable_rule | 3 | 1.00 | 100% (3/3) | 100% (2/2) | n/a | n/a | n/a | n/a | n/a |
| status | 4 | 0.25 | 75% (3/4) | n/a | n/a | n/a | n/a | n/a | n/a |
| temporal_trap | 40 | 0.50 | 69% (27/39) | 88% (35/40) | n/a | n/a | n/a | n/a | n/a |
| what_changed | 2 | 0.27 | 100% (2/2) | 100% (1/1) | n/a | n/a | n/a | n/a | n/a |
| split: dev | 42 | 0.44 | 70% (26/37) | 85% (28/33) | n/a | n/a | n/a | n/a | n/a |
| split: test | 19 | 0.60 | 79% (15/19) | 88% (15/17) | n/a | n/a | n/a | n/a | n/a |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
