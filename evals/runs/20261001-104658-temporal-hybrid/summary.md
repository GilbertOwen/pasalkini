# Evaluation run: 20261001-104658-temporal-hybrid

**Pipeline:** `temporal-hybrid`: Ablation: temporal with dense + BM25 fused by RRF.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `b80bc1ed76`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 78 items, sha256 `988e70202fdf`
- Mode: retrieval and answers

> **Provisional.** 0 of 78 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 0% (0/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 78 | 0.73 | 93% (62/67) | 0% (0/57) | 0% (0/57) | 84% (56/67) | 7% (5/70) | 97% (76/78) | 3.0 |
| adversarial | 5 | 0.67 | 67% (2/3) | 0% (0/1) | 0% (0/1) | 67% (2/3) | 0% (0/4) | 100% (5/5) | 3.1 |
| calculation | 5 | 0.90 | 100% (5/5) | 0% (0/5) | 0% (0/5) | 60% (3/5) | 0% (0/3) | 60% (3/5) | 10.0 |
| date_extraction | 7 | 0.74 | 100% (7/7) | 0% (0/7) | 0% (0/7) | 100% (7/7) | 0% (0/7) | 100% (7/7) | 2.8 |
| should_abstain | 8 | n/a | n/a | n/a | n/a | n/a | 33% (1/3) | 100% (8/8) | 3.3 |
| stable_rule | 5 | 1.00 | 100% (5/5) | 0% (0/2) | 0% (0/2) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 2.6 |
| status | 4 | 0.38 | 100% (4/4) | n/a | n/a | 75% (3/4) | 25% (1/4) | 100% (4/4) | 2.1 |
| temporal_trap | 40 | 0.71 | 90% (35/39) | 0% (0/40) | 0% (0/40) | 82% (32/39) | 2% (1/40) | 100% (40/40) | 2.7 |
| what_changed | 4 | 0.78 | 100% (4/4) | 0% (0/2) | 0% (0/2) | 100% (4/4) | 50% (2/4) | 100% (4/4) | 6.4 |
| split: dev | 42 | 0.73 | 92% (34/37) | 0% (0/33) | 0% (0/33) | 84% (31/37) | 5% (2/40) | 98% (41/42) | 2.8 |
| split: test | 36 | 0.73 | 93% (28/30) | 0% (0/24) | 0% (0/24) | 83% (25/30) | 10% (3/30) | 97% (35/36) | 3.1 |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
