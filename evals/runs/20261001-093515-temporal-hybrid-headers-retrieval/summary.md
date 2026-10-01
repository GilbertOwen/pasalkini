# Evaluation run: 20261001-093515-temporal-hybrid-headers-retrieval

**Pipeline:** `temporal-hybrid-headers`: Ablation: temporal with hybrid search and embedded titles.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84)
- Git commit: `cb34bf009f`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 61 items, sha256 `2480ce86a1e3`
- Mode: retrieval only

> **Provisional.** 0 of 61 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 61 | 0.70 | 91% (51/56) | 0% (0/50) | n/a | n/a | n/a | n/a | n/a |
| adversarial | 2 | 0.00 | 0% (0/1) | n/a | n/a | n/a | n/a | n/a | n/a |
| calculation | 2 | 1.00 | 100% (2/2) | 0% (0/2) | n/a | n/a | n/a | n/a | n/a |
| date_extraction | 5 | 0.63 | 100% (5/5) | 0% (0/5) | n/a | n/a | n/a | n/a | n/a |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| stable_rule | 3 | 1.00 | 100% (3/3) | 0% (0/2) | n/a | n/a | n/a | n/a | n/a |
| status | 4 | 0.54 | 100% (4/4) | n/a | n/a | n/a | n/a | n/a | n/a |
| temporal_trap | 40 | 0.70 | 90% (35/39) | 0% (0/40) | n/a | n/a | n/a | n/a | n/a |
| what_changed | 2 | 0.90 | 100% (2/2) | 0% (0/1) | n/a | n/a | n/a | n/a | n/a |
| split: dev | 42 | 0.72 | 92% (34/37) | 0% (0/33) | n/a | n/a | n/a | n/a | n/a |
| split: test | 19 | 0.67 | 89% (17/19) | 0% (0/17) | n/a | n/a | n/a | n/a | n/a |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
