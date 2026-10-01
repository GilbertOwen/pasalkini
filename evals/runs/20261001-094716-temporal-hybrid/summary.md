# Evaluation run: 20261001-094716-temporal-hybrid

**Pipeline:** `temporal-hybrid`: Ablation: temporal with dense + BM25 fused by RRF.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `e0dce25a91`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 61 items, sha256 `2480ce86a1e3`
- Mode: retrieval and answers

> **Provisional.** 0 of 61 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 0% (0/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 61 | 0.71 | 91% (51/56) | 0% (0/50) | 0% (0/50) | 82% (46/56) | 5% (3/59) | 98% (60/61) | 3.6 |
| adversarial | 2 | 0.00 | 0% (0/1) | n/a | n/a | 0% (0/1) | 0% (0/2) | 100% (2/2) | 8.1 |
| calculation | 2 | 1.00 | 100% (2/2) | 0% (0/2) | 0% (0/2) | 50% (1/2) | 0% (0/1) | 50% (1/2) | 22.3 |
| date_extraction | 5 | 0.77 | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 3.6 |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | 0% (0/2) | 100% (3/3) | 4.7 |
| stable_rule | 3 | 1.00 | 100% (3/3) | 0% (0/2) | 0% (0/2) | 100% (3/3) | 0% (0/3) | 100% (3/3) | 2.6 |
| status | 4 | 0.38 | 100% (4/4) | n/a | n/a | 75% (3/4) | 25% (1/4) | 100% (4/4) | 2.5 |
| temporal_trap | 40 | 0.71 | 90% (35/39) | 0% (0/40) | 0% (0/40) | 82% (32/39) | 2% (1/40) | 100% (40/40) | 3.4 |
| what_changed | 2 | 0.90 | 100% (2/2) | 0% (0/1) | 0% (0/1) | 100% (2/2) | 50% (1/2) | 100% (2/2) | 18.0 |
| split: dev | 42 | 0.73 | 92% (34/37) | 0% (0/33) | 0% (0/33) | 84% (31/37) | 5% (2/40) | 98% (41/42) | 3.6 |
| split: test | 19 | 0.67 | 89% (17/19) | 0% (0/17) | 0% (0/17) | 79% (15/19) | 5% (1/19) | 100% (19/19) | 4.5 |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
