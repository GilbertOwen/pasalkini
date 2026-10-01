# Evaluation run: 20261001-222602-pasalkini-dev

**Pipeline:** `pasalkini`: Phase 5 pipeline: the model classifies the question and rules read its date; date-aware hybrid search plus the articles the question names; the answer quotes its sources word for word and code checks every citation (one repair, then abstain); severance and PKWT compensation are computed in code.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `2789497796`
- Corpus: 848 chunks, fingerprint `03d906b40281a940`
- Dataset: 42 items, sha256 `988e70202fdf`
- Mode: retrieval and answers, dev split only

> **Provisional.** 0 of 42 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 0% (0/24) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 42 | 0.91 | 100% (37/37) | 0% (0/33) | 0% (0/33) | 92% (34/37) | 0% (0/36) | 100% (42/42) | 5.2 |
| adversarial | 2 | 1.00 | 100% (1/1) | n/a | n/a | 100% (1/1) | 0% (0/1) | 100% (2/2) | 7.8 |
| calculation | 2 | 1.00 | 100% (2/2) | 0% (0/2) | 0% (0/2) | 100% (2/2) | 0% (0/2) | 100% (2/2) | 2.3 |
| date_extraction | 4 | 0.92 | 100% (4/4) | 0% (0/4) | 0% (0/4) | 100% (4/4) | 0% (0/4) | 100% (4/4) | 8.8 |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | n/a | 100% (3/3) | 0.5 |
| stable_rule | 3 | 1.00 | 100% (3/3) | 0% (0/2) | 0% (0/2) | 67% (2/3) | 0% (0/2) | 100% (3/3) | 5.5 |
| status | 2 | 0.92 | 100% (2/2) | n/a | n/a | 100% (2/2) | 0% (0/2) | 100% (2/2) | 0.5 |
| temporal_trap | 24 | 0.88 | 100% (23/23) | 0% (0/24) | 0% (0/24) | 91% (21/23) | 0% (0/23) | 100% (24/24) | 5.7 |
| what_changed | 2 | 1.00 | 100% (2/2) | 0% (0/1) | 0% (0/1) | 100% (2/2) | 0% (0/2) | 100% (2/2) | 6.4 |
| split: dev | 42 | 0.91 | 100% (37/37) | 0% (0/33) | 0% (0/33) | 92% (34/37) | 0% (0/36) | 100% (42/42) | 5.2 |
| split: test | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Answer pipeline:

| Group | Abstained correctly | Intent correct | Date from question correct | Citations pass first try | Repaired | Citations dropped | Answer grounded first try | Answer shown ungrounded |
|---|---|---|---|---|---|---|---|---|
| All | 98% (41/42) | 100% (38/38) | 100% (5/5) | 94% (31/33) | 9% (3/33) | 3% (1/33) | 100% (33/33) | 0% (0/33) |
| adversarial | 100% (2/2) | 100% (2/2) | n/a | 100% (1/1) | 0% (0/1) | 0% (0/1) | 100% (1/1) | 0% (0/1) |
| calculation | 100% (2/2) | 100% (2/2) | 100% (1/1) | n/a | n/a | n/a | n/a | n/a |
| date_extraction | 100% (4/4) | n/a | 100% (4/4) | 100% (3/3) | 0% (0/3) | 0% (0/3) | 100% (3/3) | 0% (0/3) |
| should_abstain | 100% (3/3) | 100% (3/3) | n/a | n/a | n/a | n/a | n/a | n/a |
| stable_rule | 67% (2/3) | 100% (3/3) | n/a | 100% (3/3) | 33% (1/3) | 0% (0/3) | 100% (3/3) | 0% (0/3) |
| status | 100% (2/2) | 100% (2/2) | n/a | n/a | n/a | n/a | n/a | n/a |
| temporal_trap | 100% (24/24) | 100% (24/24) | n/a | 92% (22/24) | 8% (2/24) | 4% (1/24) | 100% (24/24) | 0% (0/24) |
| what_changed | 100% (2/2) | 100% (2/2) | n/a | 100% (2/2) | 0% (0/2) | 0% (0/2) | 100% (2/2) | 0% (0/2) |
| split: dev | 98% (41/42) | 100% (38/38) | 100% (5/5) | 94% (31/33) | 9% (3/33) | 3% (1/33) | 100% (33/33) | 0% (0/33) |
| split: test | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
- For this pipeline, *top 5* means the first 5 chunks of the context, which puts the articles the question names before the search results; *Median answer s* is the whole pipeline. Citations are counted after verification.
- *Abstained correctly*: refused or abstained exactly when the key says it should.
- *Citations pass first try*: every quote the model first selected was found in the source it named, in a version that applied on the date; *Repaired*: a second selection was asked for; *Citations dropped*: quotes of the final selection that still failed and were not used.
- *Answer grounded first try*: the first answer mentioned no number or article that it was not given (and, for history questions, no date); otherwise it was rewritten once. *Answer shown ungrounded*: the answer shown still does, and says so in a note.
