# Evaluation run: 20261001-105736-baseline

**Pipeline:** `baseline`: Plain RAG: dense search over every version of every article with dates ignored; qwen3.5:4b answers from the top 5 chunks.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `b80bc1ed76`
- Corpus: 596 chunks, fingerprint `4232c9324eb12fe8`
- Dataset: 78 items, sha256 `988e70202fdf`
- Mode: retrieval and answers

> **Provisional.** 0 of 78 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 68% (27/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 78 | 0.64 | 85% (57/67) | 88% (50/57) | 65% (37/57) | 64% (43/67) | 3% (2/71) | 97% (76/78) | 3.1 |
| adversarial | 5 | 0.67 | 67% (2/3) | 0% (0/1) | 0% (0/1) | 67% (2/3) | 0% (0/5) | 100% (5/5) | 2.5 |
| calculation | 5 | 0.90 | 100% (5/5) | 60% (3/5) | 40% (2/5) | 80% (4/5) | 0% (0/4) | 80% (4/5) | 10.3 |
| date_extraction | 7 | 0.60 | 86% (6/7) | 86% (6/7) | 71% (5/7) | 86% (6/7) | 0% (0/7) | 100% (7/7) | 4.2 |
| should_abstain | 8 | n/a | n/a | n/a | n/a | n/a | 0% (0/3) | 100% (8/8) | 3.3 |
| stable_rule | 5 | 1.00 | 100% (5/5) | 100% (2/2) | 100% (2/2) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 2.4 |
| status | 4 | 0.25 | 75% (3/4) | n/a | n/a | 50% (2/4) | 0% (0/4) | 100% (4/4) | 3.6 |
| temporal_trap | 40 | 0.61 | 82% (32/39) | 95% (38/40) | 68% (27/40) | 54% (21/39) | 5% (2/39) | 98% (39/40) | 3.1 |
| what_changed | 4 | 0.52 | 100% (4/4) | 50% (1/2) | 50% (1/2) | 75% (3/4) | 0% (0/4) | 100% (4/4) | 3.4 |
| split: dev | 42 | 0.61 | 84% (31/37) | 91% (30/33) | 70% (23/33) | 78% (29/37) | 5% (2/40) | 100% (42/42) | 3.0 |
| split: test | 36 | 0.67 | 87% (26/30) | 83% (20/24) | 58% (14/24) | 47% (14/30) | 0% (0/31) | 94% (34/36) | 3.3 |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
