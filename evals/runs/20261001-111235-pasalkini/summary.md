# Evaluation run: 20261001-111235-pasalkini

**Pipeline:** `pasalkini`: Phase 5 pipeline: the model classifies the question and rules read its date; date-aware hybrid search plus the articles the question names; the answer quotes its sources word for word and code checks every citation (one repair, then abstain); severance and PKWT compensation are computed in code.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `3a63d25e50`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 78 items, sha256 `988e70202fdf`
- Mode: retrieval and answers

> **Provisional.** 0 of 78 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 0% (0/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 78 | 0.77 | 93% (62/67) | 0% (0/57) | 0% (0/57) | 91% (61/67) | 0% (0/68) | 100% (78/78) | 6.7 |
| adversarial | 5 | 0.67 | 67% (2/3) | 0% (0/1) | 0% (0/1) | 67% (2/3) | 0% (0/3) | 100% (5/5) | 6.3 |
| calculation | 5 | 1.00 | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 9.9 |
| date_extraction | 7 | 0.74 | 100% (7/7) | 0% (0/7) | 0% (0/7) | 100% (7/7) | 0% (0/7) | 100% (7/7) | 8.1 |
| should_abstain | 8 | n/a | n/a | n/a | n/a | n/a | n/a | 100% (8/8) | 0.4 |
| stable_rule | 5 | 1.00 | 100% (5/5) | 0% (0/2) | 0% (0/2) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 6.5 |
| status | 4 | 0.83 | 100% (4/4) | n/a | n/a | 100% (4/4) | 0% (0/4) | 100% (4/4) | 8.5 |
| temporal_trap | 40 | 0.71 | 90% (35/39) | 0% (0/40) | 0% (0/40) | 87% (34/39) | 0% (0/40) | 100% (40/40) | 6.7 |
| what_changed | 4 | 0.92 | 100% (4/4) | 0% (0/2) | 0% (0/2) | 100% (4/4) | 0% (0/4) | 100% (4/4) | 7.3 |
| split: dev | 42 | 0.77 | 92% (34/37) | 0% (0/33) | 0% (0/33) | 89% (33/37) | 0% (0/38) | 100% (42/42) | 6.2 |
| split: test | 36 | 0.78 | 93% (28/30) | 0% (0/24) | 0% (0/24) | 93% (28/30) | 0% (0/30) | 100% (36/36) | 7.4 |

Answer pipeline:

| Group | Abstained correctly | Intent correct | Date from question correct | Citations pass first try | Repaired | Citations dropped |
|---|---|---|---|---|---|---|
| All | 100% (78/78) | 100% (71/71) | 100% (10/10) | 88% (60/68) | 12% (8/68) | 6% (4/68) |
| adversarial | 100% (5/5) | 100% (5/5) | n/a | 100% (3/3) | 0% (0/3) | 0% (0/3) |
| calculation | 100% (5/5) | 100% (5/5) | 100% (3/3) | 100% (5/5) | 0% (0/5) | 0% (0/5) |
| date_extraction | 100% (7/7) | n/a | 100% (7/7) | 100% (7/7) | 0% (0/7) | 0% (0/7) |
| should_abstain | 100% (8/8) | 100% (8/8) | n/a | n/a | n/a | n/a |
| stable_rule | 100% (5/5) | 100% (5/5) | n/a | 80% (4/5) | 20% (1/5) | 0% (0/5) |
| status | 100% (4/4) | 100% (4/4) | n/a | 100% (4/4) | 0% (0/4) | 0% (0/4) |
| temporal_trap | 100% (40/40) | 100% (40/40) | n/a | 82% (33/40) | 18% (7/40) | 10% (4/40) |
| what_changed | 100% (4/4) | 100% (4/4) | n/a | 100% (4/4) | 0% (0/4) | 0% (0/4) |
| split: dev | 100% (42/42) | 100% (38/38) | 100% (5/5) | 95% (36/38) | 5% (2/38) | 3% (1/38) |
| split: test | 100% (36/36) | 100% (33/33) | 100% (5/5) | 80% (24/30) | 20% (6/30) | 10% (3/30) |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
- For this pipeline, *top 5* means the first 5 chunks of the context, which puts the articles the question names before the search results; *Median answer s* is the whole pipeline. Citations are counted after verification.
- *Abstained correctly*: refused or abstained exactly when the key says it should.
- *Citations pass first try*: the first answer passed every citation check; *Repaired*: a second answer was asked for; *Citations dropped*: the final answer still had citations that failed and were not shown.
