# Evaluation run: 20261001-095213-versions

**Pipeline:** `versions`: Ablation: one chunk per article version with its validity in the title, but no date filter.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `e0dce25a91`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 61 items, sha256 `2480ce86a1e3`
- Mode: retrieval and answers

> **Provisional.** 0 of 61 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 70% (28/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 61 | 0.49 | 73% (41/56) | 86% (43/50) | 66% (33/50) | 61% (34/56) | 14% (8/57) | 100% (61/61) | 3.5 |
| adversarial | 2 | 0.00 | 0% (0/1) | n/a | n/a | 0% (0/1) | n/a | 100% (2/2) | 2.3 |
| calculation | 2 | 0.75 | 100% (2/2) | 50% (1/2) | 50% (1/2) | 100% (2/2) | 0% (0/2) | 100% (2/2) | 11.9 |
| date_extraction | 5 | 0.43 | 80% (4/5) | 80% (4/5) | 20% (1/5) | 80% (4/5) | 20% (1/5) | 100% (5/5) | 5.3 |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | 0% (0/2) | 100% (3/3) | 3.4 |
| stable_rule | 3 | 1.00 | 100% (3/3) | 100% (2/2) | 100% (2/2) | 67% (2/3) | 0% (0/3) | 100% (3/3) | 2.9 |
| status | 4 | 0.25 | 75% (3/4) | n/a | n/a | 50% (2/4) | 0% (0/3) | 100% (4/4) | 3.5 |
| temporal_trap | 40 | 0.50 | 69% (27/39) | 88% (35/40) | 70% (28/40) | 56% (22/39) | 15% (6/40) | 100% (40/40) | 3.7 |
| what_changed | 2 | 0.27 | 100% (2/2) | 100% (1/1) | 100% (1/1) | 100% (2/2) | 50% (1/2) | 100% (2/2) | 10.5 |
| split: dev | 42 | 0.44 | 70% (26/37) | 85% (28/33) | 73% (24/33) | 62% (23/37) | 16% (6/38) | 100% (42/42) | 3.4 |
| split: test | 19 | 0.60 | 79% (15/19) | 88% (15/17) | 53% (9/17) | 58% (11/19) | 11% (2/19) | 100% (19/19) | 3.7 |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
