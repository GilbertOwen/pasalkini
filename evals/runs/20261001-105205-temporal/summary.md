# Evaluation run: 20261001-105205-temporal

**Pipeline:** `temporal`: Date-aware RAG: one chunk per article version; only versions that applied on the question's date are ranked (all versions up to it for questions about change or status).

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `b80bc1ed76`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 78 items, sha256 `988e70202fdf`
- Mode: retrieval and answers

> **Provisional.** 0 of 78 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 0% (0/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 78 | 0.72 | 94% (63/67) | 0% (0/57) | 0% (0/56) | 88% (58/66) | 7% (5/68) | 100% (77/77) | 3.3 |
| adversarial | 5 | 0.67 | 67% (2/3) | 0% (0/1) | 0% (0/1) | 67% (2/3) | 25% (1/4) | 100% (5/5) | 2.8 |
| calculation | 5 | 1.00 | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 6.7 |
| date_extraction | 7 | 0.74 | 100% (7/7) | 0% (0/7) | 0% (0/7) | 100% (7/7) | 14% (1/7) | 100% (7/7) | 4.6 |
| should_abstain | 8 | n/a | n/a | n/a | n/a | n/a | 33% (1/3) | 100% (8/8) | 2.6 |
| stable_rule | 5 | 1.00 | 100% (5/5) | 0% (0/2) | 0% (0/2) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 2.1 |
| status | 4 | 0.25 | 75% (3/4) | n/a | n/a | 50% (2/4) | 0% (0/3) | 100% (4/4) | 3.3 |
| temporal_trap | 40 | 0.73 | 95% (37/39) | 0% (0/40) | 0% (0/40) | 87% (34/39) | 3% (1/38) | 100% (40/40) | 3.1 |
| what_changed | 4 | 0.43 | 100% (4/4) | 0% (0/2) | 0% (0/1) | 100% (3/3) | 33% (1/3) | 100% (3/3) | 4.1 |
| split: dev | 42 | 0.68 | 92% (34/37) | 0% (0/33) | 0% (0/32) | 86% (31/36) | 6% (2/36) | 100% (41/41) | 2.8 |
| split: test | 36 | 0.77 | 97% (29/30) | 0% (0/24) | 0% (0/24) | 90% (27/30) | 9% (3/32) | 100% (36/36) | 3.4 |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
