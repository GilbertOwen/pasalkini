# Evaluation run: 20261002-105148-temporal-hybrid-variants-retrieval-dev

**Pipeline:** `temporal-hybrid`: Ablation: temporal with dense + BM25 fused by RRF.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84)
- Git commit: `00afd24aa0`
- Corpus: 848 chunks, fingerprint `03d906b40281a940`
- Dataset: variants, 42 items, sha256 `8d8fb1acf68b`
- Mode: retrieval only, dev split only

> **Provisional.** 0 of 42 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 42 | 0.62 | 81% (30/37) | 0% (0/33) | n/a | n/a | n/a | n/a | n/a |
| adversarial | 2 | 0.00 | 0% (0/1) | n/a | n/a | n/a | n/a | n/a | n/a |
| calculation | 2 | 0.75 | 100% (2/2) | 0% (0/2) | n/a | n/a | n/a | n/a | n/a |
| date_extraction | 4 | 0.71 | 100% (4/4) | 0% (0/4) | n/a | n/a | n/a | n/a | n/a |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| stable_rule | 3 | 1.00 | 100% (3/3) | 0% (0/2) | n/a | n/a | n/a | n/a | n/a |
| status | 2 | 0.42 | 100% (2/2) | n/a | n/a | n/a | n/a | n/a | n/a |
| temporal_trap | 24 | 0.62 | 78% (18/23) | 0% (0/24) | n/a | n/a | n/a | n/a | n/a |
| what_changed | 2 | 0.30 | 50% (1/2) | 0% (0/1) | n/a | n/a | n/a | n/a | n/a |
| split: dev | 42 | 0.62 | 81% (30/37) | 0% (0/33) | n/a | n/a | n/a | n/a | n/a |
| split: test | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
