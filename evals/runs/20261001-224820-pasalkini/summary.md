# Evaluation run: 20261001-224820-pasalkini

**Pipeline:** `pasalkini`: Phase 5 pipeline: the model classifies the question and rules read its date; date-aware hybrid search plus the articles the question names; the answer quotes its sources word for word and code checks every citation (one repair, then abstain); severance and PKWT compensation are computed in code.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `3efb83ef1d`
- Corpus: 848 chunks, fingerprint `03d906b40281a940`
- Dataset: 78 items, sha256 `988e70202fdf`
- Mode: retrieval and answers

> **Provisional.** 0 of 78 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 0% (0/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 78 | 0.87 | 100% (67/67) | 0% (0/57) | 0% (0/57) | 93% (62/67) | 0% (0/66) | 100% (78/78) | 5.2 |
| adversarial | 5 | 1.00 | 100% (3/3) | 0% (0/1) | 0% (0/1) | 100% (3/3) | 0% (0/3) | 100% (5/5) | 4.0 |
| calculation | 5 | 1.00 | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 2.1 |
| date_extraction | 7 | 0.90 | 100% (7/7) | 0% (0/7) | 0% (0/7) | 100% (7/7) | 0% (0/7) | 100% (7/7) | 5.2 |
| should_abstain | 8 | n/a | n/a | n/a | n/a | n/a | 0% (0/1) | 100% (8/8) | 0.6 |
| stable_rule | 5 | 1.00 | 100% (5/5) | 0% (0/2) | 0% (0/2) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 5.2 |
| status | 4 | 0.83 | 100% (4/4) | n/a | n/a | 100% (4/4) | 0% (0/4) | 100% (4/4) | 0.5 |
| temporal_trap | 40 | 0.84 | 100% (39/39) | 0% (0/40) | 0% (0/40) | 90% (35/39) | 0% (0/37) | 100% (40/40) | 6.0 |
| what_changed | 4 | 0.75 | 100% (4/4) | 0% (0/2) | 0% (0/2) | 75% (3/4) | 0% (0/4) | 100% (4/4) | 8.3 |
| split: dev | 42 | 0.91 | 100% (37/37) | 0% (0/33) | 0% (0/33) | 97% (36/37) | 0% (0/38) | 100% (42/42) | 5.6 |
| split: test | 36 | 0.83 | 100% (30/30) | 0% (0/24) | 0% (0/24) | 87% (26/30) | 0% (0/28) | 100% (36/36) | 5.0 |

Answer pipeline:

| Group | Abstained correctly | Intent correct | Date from question correct | Citations pass first try | Repaired | Citations dropped | Answer grounded first try | Answer shown ungrounded |
|---|---|---|---|---|---|---|---|---|
| All | 96% (75/78) | 99% (70/71) | 100% (10/10) | 100% (58/58) | 0% (0/58) | 0% (0/58) | 93% (53/57) | 2% (1/57) |
| adversarial | 100% (5/5) | 100% (5/5) | n/a | 100% (3/3) | 0% (0/3) | 0% (0/3) | 100% (3/3) | 0% (0/3) |
| calculation | 100% (5/5) | 100% (5/5) | 100% (3/3) | n/a | n/a | n/a | n/a | n/a |
| date_extraction | 100% (7/7) | n/a | 100% (7/7) | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) |
| should_abstain | 88% (7/8) | 88% (7/8) | n/a | 100% (1/1) | 0% (0/1) | 0% (0/1) | 100% (1/1) | 0% (0/1) |
| stable_rule | 100% (5/5) | 100% (5/5) | n/a | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) |
| status | 100% (4/4) | 100% (4/4) | n/a | n/a | n/a | n/a | n/a | n/a |
| temporal_trap | 95% (38/40) | 100% (40/40) | n/a | 100% (40/40) | 0% (0/40) | 0% (0/40) | 90% (35/39) | 3% (1/39) |
| what_changed | 100% (4/4) | 100% (4/4) | n/a | 100% (4/4) | 0% (0/4) | 0% (0/4) | 100% (4/4) | 0% (0/4) |
| split: dev | 98% (41/42) | 97% (37/38) | 100% (5/5) | 100% (34/34) | 0% (0/34) | 0% (0/34) | 88% (29/33) | 3% (1/33) |
| split: test | 94% (34/36) | 100% (33/33) | 100% (5/5) | 100% (24/24) | 0% (0/24) | 0% (0/24) | 100% (24/24) | 0% (0/24) |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
- For this pipeline, *top 5* means the first 5 chunks of the context, which puts the articles the question names before the search results; *Median answer s* is the whole pipeline. Citations are counted after verification.
- *Abstained correctly*: refused or abstained exactly when the key says it should.
- *Citations pass first try*: every quote the model first selected was found in the source it named, in a version that applied on the date; *Repaired*: a second selection was asked for; *Citations dropped*: quotes of the final selection that still failed and were not used.
- *Answer grounded first try*: the first answer mentioned no number or article that it was not given (and, for history questions, no date); otherwise it was rewritten once. *Answer shown ungrounded*: the answer shown still does, and says so in a note.
