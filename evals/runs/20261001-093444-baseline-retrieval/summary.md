# Evaluation run: 20261001-093444-baseline-retrieval

**Pipeline:** `baseline`: Plain RAG: dense search over every version of every article with dates ignored; qwen3.5:4b answers from the top 5 chunks.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84)
- Git commit: `cb34bf009f`
- Corpus: 596 chunks, fingerprint `4232c9324eb12fe8`
- Dataset: 61 items, sha256 `2480ce86a1e3`
- Mode: retrieval only

> **Provisional.** 0 of 61 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 61 | 0.61 | 84% (47/56) | 92% (46/50) | n/a | n/a | n/a | n/a | n/a |
| adversarial | 2 | 0.00 | 0% (0/1) | n/a | n/a | n/a | n/a | n/a | n/a |
| calculation | 2 | 1.00 | 100% (2/2) | 50% (1/2) | n/a | n/a | n/a | n/a | n/a |
| date_extraction | 5 | 0.63 | 100% (5/5) | 80% (4/5) | n/a | n/a | n/a | n/a | n/a |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| stable_rule | 3 | 1.00 | 100% (3/3) | 100% (2/2) | n/a | n/a | n/a | n/a | n/a |
| status | 4 | 0.25 | 75% (3/4) | n/a | n/a | n/a | n/a | n/a | n/a |
| temporal_trap | 40 | 0.61 | 82% (32/39) | 95% (38/40) | n/a | n/a | n/a | n/a | n/a |
| what_changed | 2 | 0.53 | 100% (2/2) | 100% (1/1) | n/a | n/a | n/a | n/a | n/a |
| split: dev | 42 | 0.61 | 84% (31/37) | 91% (30/33) | n/a | n/a | n/a | n/a | n/a |
| split: test | 19 | 0.61 | 84% (16/19) | 94% (16/17) | n/a | n/a | n/a | n/a | n/a |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
