# Evaluation run: 20261001-102137-pasalkini

**Pipeline:** `pasalkini`: Phase 5 pipeline: the model classifies the question and rules read its date; date-aware hybrid search plus the articles the question names; the answer quotes its sources word for word and code checks every citation (one repair, then abstain); severance and PKWT compensation are computed in code.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `0a7276e8f3`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 61 items, sha256 `3672ae62e836`
- Mode: retrieval and answers

> **Provisional.** 0 of 61 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 0% (0/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 61 | 0.75 | 91% (51/56) | 0% (0/50) | 0% (0/50) | 86% (48/56) | 0% (0/56) | 100% (61/61) | 7.2 |
| adversarial | 2 | 0.00 | 0% (0/1) | n/a | n/a | 0% (0/1) | 0% (0/1) | 100% (2/2) | 11.0 |
| calculation | 2 | 1.00 | 100% (2/2) | 0% (0/2) | 0% (0/2) | 100% (2/2) | 0% (0/2) | 100% (2/2) | 11.3 |
| date_extraction | 5 | 0.77 | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 8.2 |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | n/a | 100% (3/3) | 0.6 |
| stable_rule | 3 | 1.00 | 100% (3/3) | 0% (0/2) | 0% (0/2) | 67% (2/3) | 0% (0/3) | 100% (3/3) | 7.1 |
| status | 4 | 0.83 | 100% (4/4) | n/a | n/a | 100% (4/4) | 0% (0/4) | 100% (4/4) | 18.4 |
| temporal_trap | 40 | 0.71 | 90% (35/39) | 0% (0/40) | 0% (0/40) | 85% (33/39) | 0% (0/39) | 100% (40/40) | 7.1 |
| what_changed | 2 | 1.00 | 100% (2/2) | 0% (0/1) | 0% (0/1) | 100% (2/2) | 0% (0/2) | 100% (2/2) | 8.0 |
| split: dev | 42 | 0.77 | 92% (34/37) | 0% (0/33) | 0% (0/33) | 89% (33/37) | 0% (0/38) | 100% (42/42) | 7.1 |
| split: test | 19 | 0.70 | 89% (17/19) | 0% (0/17) | 0% (0/17) | 79% (15/19) | 0% (0/18) | 100% (19/19) | 7.8 |

Answer pipeline:

| Group | Abstained correctly | Intent correct | Date from question correct | Citations pass first try | Repaired | Citations dropped |
|---|---|---|---|---|---|---|
| All | 98% (60/61) | 100% (56/56) | 100% (6/6) | 65% (37/57) | 35% (20/57) | 21% (12/57) |
| adversarial | 100% (2/2) | 100% (2/2) | n/a | 0% (0/1) | 100% (1/1) | 100% (1/1) |
| calculation | 100% (2/2) | 100% (2/2) | 100% (1/1) | 100% (2/2) | 0% (0/2) | 0% (0/2) |
| date_extraction | 100% (5/5) | n/a | 100% (5/5) | 60% (3/5) | 40% (2/5) | 40% (2/5) |
| should_abstain | 100% (3/3) | 100% (3/3) | n/a | n/a | n/a | n/a |
| stable_rule | 100% (3/3) | 100% (3/3) | n/a | 67% (2/3) | 33% (1/3) | 33% (1/3) |
| status | 100% (4/4) | 100% (4/4) | n/a | 50% (2/4) | 50% (2/4) | 0% (0/4) |
| temporal_trap | 98% (39/40) | 100% (40/40) | n/a | 65% (26/40) | 35% (14/40) | 20% (8/40) |
| what_changed | 100% (2/2) | 100% (2/2) | n/a | 100% (2/2) | 0% (0/2) | 0% (0/2) |
| split: dev | 100% (42/42) | 100% (38/38) | 100% (5/5) | 71% (27/38) | 29% (11/38) | 16% (6/38) |
| split: test | 95% (18/19) | 100% (18/18) | 100% (1/1) | 53% (10/19) | 47% (9/19) | 32% (6/19) |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
- For this pipeline, *top 5* means the first 5 chunks of the context, which puts the articles the question names before the search results; *Median answer s* is the whole pipeline. Citations are counted after verification.
- *Abstained correctly*: refused or abstained exactly when the key says it should.
- *Citations pass first try*: the first answer passed every citation check; *Repaired*: a second answer was asked for; *Citations dropped*: the final answer still had citations that failed and were not shown.
