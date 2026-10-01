# Evaluation run: 20261001-110246-versions

**Pipeline:** `versions`: Ablation: one chunk per article version with its validity in the title, but no date filter.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `b80bc1ed76`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 78 items, sha256 `988e70202fdf`
- Mode: retrieval and answers

> **Provisional.** 0 of 78 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 70% (28/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 78 | 0.53 | 76% (51/67) | 82% (47/57) | 65% (37/57) | 66% (44/67) | 16% (11/69) | 100% (78/78) | 3.1 |
| adversarial | 5 | 0.67 | 67% (2/3) | 0% (0/1) | 0% (0/1) | 67% (2/3) | 0% (0/2) | 100% (5/5) | 2.0 |
| calculation | 5 | 0.70 | 100% (5/5) | 60% (3/5) | 60% (3/5) | 100% (5/5) | 20% (1/5) | 100% (5/5) | 9.0 |
| date_extraction | 7 | 0.45 | 71% (5/7) | 86% (6/7) | 43% (3/7) | 71% (5/7) | 43% (3/7) | 100% (7/7) | 4.2 |
| should_abstain | 8 | n/a | n/a | n/a | n/a | n/a | 0% (0/3) | 100% (8/8) | 2.6 |
| stable_rule | 5 | 1.00 | 100% (5/5) | 100% (2/2) | 100% (2/2) | 80% (4/5) | 0% (0/5) | 100% (5/5) | 2.1 |
| status | 4 | 0.25 | 75% (3/4) | n/a | n/a | 50% (2/4) | 0% (0/3) | 100% (4/4) | 3.1 |
| temporal_trap | 40 | 0.50 | 69% (27/39) | 88% (35/40) | 70% (28/40) | 56% (22/39) | 15% (6/40) | 100% (40/40) | 3.4 |
| what_changed | 4 | 0.38 | 100% (4/4) | 50% (1/2) | 50% (1/2) | 100% (4/4) | 25% (1/4) | 100% (4/4) | 4.5 |
| split: dev | 42 | 0.44 | 70% (26/37) | 85% (28/33) | 73% (24/33) | 62% (23/37) | 16% (6/38) | 100% (42/42) | 3.1 |
| split: test | 36 | 0.64 | 83% (25/30) | 79% (19/24) | 54% (13/24) | 70% (21/30) | 16% (5/31) | 100% (36/36) | 3.3 |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
