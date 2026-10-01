# Evaluation run: 20261001-094201-baseline

**Pipeline:** `baseline`: Plain RAG: dense search over every version of every article with dates ignored; qwen3.5:4b answers from the top 5 chunks.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `e0dce25a91`
- Corpus: 596 chunks, fingerprint `4232c9324eb12fe8`
- Dataset: 61 items, sha256 `2480ce86a1e3`
- Mode: retrieval and answers

> **Provisional.** 0 of 61 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 68% (27/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 61 | 0.61 | 84% (47/56) | 92% (46/50) | 70% (35/50) | 62% (35/56) | 3% (2/58) | 98% (60/61) | 4.1 |
| adversarial | 2 | 0.00 | 0% (0/1) | n/a | n/a | 0% (0/1) | 0% (0/2) | 100% (2/2) | 6.1 |
| calculation | 2 | 1.00 | 100% (2/2) | 50% (1/2) | 50% (1/2) | 100% (2/2) | 0% (0/2) | 100% (2/2) | 15.0 |
| date_extraction | 5 | 0.63 | 100% (5/5) | 80% (4/5) | 80% (4/5) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 5.8 |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | 0% (0/1) | 100% (3/3) | 4.2 |
| stable_rule | 3 | 1.00 | 100% (3/3) | 100% (2/2) | 100% (2/2) | 100% (3/3) | 0% (0/3) | 100% (3/3) | 3.6 |
| status | 4 | 0.25 | 75% (3/4) | n/a | n/a | 50% (2/4) | 0% (0/4) | 100% (4/4) | 4.6 |
| temporal_trap | 40 | 0.61 | 82% (32/39) | 95% (38/40) | 68% (27/40) | 54% (21/39) | 5% (2/39) | 98% (39/40) | 4.1 |
| what_changed | 2 | 0.53 | 100% (2/2) | 100% (1/1) | 100% (1/1) | 100% (2/2) | 0% (0/2) | 100% (2/2) | 14.3 |
| split: dev | 42 | 0.61 | 84% (31/37) | 91% (30/33) | 70% (23/33) | 78% (29/37) | 5% (2/40) | 100% (42/42) | 3.9 |
| split: test | 19 | 0.61 | 84% (16/19) | 94% (16/17) | 71% (12/17) | 32% (6/19) | 0% (0/18) | 95% (18/19) | 4.5 |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
