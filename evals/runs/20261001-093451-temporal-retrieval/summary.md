# Evaluation run: 20261001-093451-temporal-retrieval

**Pipeline:** `temporal`: Date-aware RAG: one chunk per article version; only versions that applied on the question's date are ranked (all versions up to it for questions about change or status).

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84)
- Git commit: `cb34bf009f`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 61 items, sha256 `2480ce86a1e3`
- Mode: retrieval only

> **Provisional.** 0 of 61 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 61 | 0.69 | 93% (52/56) | 0% (0/50) | n/a | n/a | n/a | n/a | n/a |
| adversarial | 2 | 0.00 | 0% (0/1) | n/a | n/a | n/a | n/a | n/a | n/a |
| calculation | 2 | 1.00 | 100% (2/2) | 0% (0/2) | n/a | n/a | n/a | n/a | n/a |
| date_extraction | 5 | 0.70 | 100% (5/5) | 0% (0/5) | n/a | n/a | n/a | n/a | n/a |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| stable_rule | 3 | 1.00 | 100% (3/3) | 0% (0/2) | n/a | n/a | n/a | n/a | n/a |
| status | 4 | 0.25 | 75% (3/4) | n/a | n/a | n/a | n/a | n/a | n/a |
| temporal_trap | 40 | 0.73 | 95% (37/39) | 0% (0/40) | n/a | n/a | n/a | n/a | n/a |
| what_changed | 2 | 0.37 | 100% (2/2) | 0% (0/1) | n/a | n/a | n/a | n/a | n/a |
| split: dev | 42 | 0.68 | 92% (34/37) | 0% (0/33) | n/a | n/a | n/a | n/a | n/a |
| split: test | 19 | 0.71 | 95% (18/19) | 0% (0/17) | n/a | n/a | n/a | n/a | n/a |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
