# Evaluation run: 20261001-093630-temporal

**Pipeline:** `temporal`: Date-aware RAG: one chunk per article version; only versions that applied on the question's date are ranked (all versions up to it for questions about change or status).

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `cb34bf009f`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 61 items, sha256 `2480ce86a1e3`
- Mode: retrieval and answers

> **Provisional.** 0 of 61 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 0% (0/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 61 | 0.69 | 93% (52/56) | 0% (0/50) | 0% (0/49) | 85% (47/55) | 6% (3/54) | 100% (60/60) | 3.5 |
| adversarial | 2 | 0.00 | 0% (0/1) | n/a | n/a | 0% (0/1) | 0% (0/1) | 100% (2/2) | 4.9 |
| calculation | 2 | 1.00 | 100% (2/2) | 0% (0/2) | 0% (0/2) | 100% (2/2) | 0% (0/2) | 100% (2/2) | 14.1 |
| date_extraction | 5 | 0.70 | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 20% (1/5) | 100% (5/5) | 5.0 |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | 0% (0/1) | 100% (3/3) | 5.7 |
| stable_rule | 3 | 1.00 | 100% (3/3) | 0% (0/2) | 0% (0/2) | 100% (3/3) | 0% (0/3) | 100% (3/3) | 2.4 |
| status | 4 | 0.25 | 75% (3/4) | n/a | n/a | 50% (2/4) | 0% (0/3) | 100% (4/4) | 4.1 |
| temporal_trap | 40 | 0.73 | 95% (37/39) | 0% (0/40) | 0% (0/40) | 87% (34/39) | 3% (1/38) | 100% (40/40) | 3.3 |
| what_changed | 2 | 0.37 | 100% (2/2) | 0% (0/1) | n/a | 100% (1/1) | 100% (1/1) | 100% (1/1) | 4.1 |
| split: dev | 42 | 0.68 | 92% (34/37) | 0% (0/33) | 0% (0/32) | 86% (31/36) | 6% (2/36) | 100% (41/41) | 3.2 |
| split: test | 19 | 0.71 | 95% (18/19) | 0% (0/17) | 0% (0/17) | 84% (16/19) | 6% (1/18) | 100% (19/19) | 4.0 |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
