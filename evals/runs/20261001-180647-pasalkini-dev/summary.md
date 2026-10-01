# Evaluation run: 20261001-180647-pasalkini-dev

**Pipeline:** `pasalkini`: Phase 5 pipeline: the model classifies the question and rules read its date; date-aware hybrid search plus the articles the question names; the answer quotes its sources word for word and code checks every citation (one repair, then abstain); severance and PKWT compensation are computed in code.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `9517ad5249` (uncommitted changes)
- Corpus: 848 chunks, fingerprint `03d906b40281a940`
- Dataset: 42 items, sha256 `988e70202fdf`
- Mode: retrieval and answers, dev split only

> **Provisional.** 0 of 42 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 0% (0/24) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 42 | 0.91 | 100% (37/37) | 0% (0/33) | 0% (0/33) | 92% (34/37) | 0% (0/34) | 100% (42/42) | 5.5 |
| adversarial | 2 | 1.00 | 100% (1/1) | n/a | n/a | 0% (0/1) | n/a | 100% (2/2) | 3.8 |
| calculation | 2 | 1.00 | 100% (2/2) | 0% (0/2) | 0% (0/2) | 100% (2/2) | 0% (0/2) | 100% (2/2) | 22.1 |
| date_extraction | 4 | 0.92 | 100% (4/4) | 0% (0/4) | 0% (0/4) | 100% (4/4) | 0% (0/4) | 100% (4/4) | 9.0 |
| should_abstain | 3 | n/a | n/a | n/a | n/a | n/a | n/a | 100% (3/3) | 0.6 |
| stable_rule | 3 | 1.00 | 100% (3/3) | 0% (0/2) | 0% (0/2) | 100% (3/3) | 0% (0/3) | 100% (3/3) | 5.2 |
| status | 2 | 0.92 | 100% (2/2) | n/a | n/a | 100% (2/2) | 0% (0/2) | 100% (2/2) | 6.6 |
| temporal_trap | 24 | 0.88 | 100% (23/23) | 0% (0/24) | 0% (0/24) | 91% (21/23) | 0% (0/21) | 100% (24/24) | 5.5 |
| what_changed | 2 | 1.00 | 100% (2/2) | 0% (0/1) | 0% (0/1) | 100% (2/2) | 0% (0/2) | 100% (2/2) | 10.9 |
| split: dev | 42 | 0.91 | 100% (37/37) | 0% (0/33) | 0% (0/33) | 92% (34/37) | 0% (0/34) | 100% (42/42) | 5.5 |
| split: test | 0 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Answer pipeline:

| Group | Abstained correctly | Intent correct | Date from question correct | Citations pass first try | Repaired | Citations dropped | Answer grounded first try | Answer shown ungrounded |
|---|---|---|---|---|---|---|---|---|
| All | 90% (38/42) | 100% (38/38) | 100% (5/5) | 95% (36/38) | 5% (2/38) | 0% (0/38) | 92% (33/36) | 3% (1/36) |
| adversarial | 50% (1/2) | 100% (2/2) | n/a | 100% (1/1) | 0% (0/1) | 0% (0/1) | n/a | n/a |
| calculation | 100% (2/2) | 100% (2/2) | 100% (1/1) | 50% (1/2) | 50% (1/2) | 0% (0/2) | 100% (2/2) | 0% (0/2) |
| date_extraction | 100% (4/4) | n/a | 100% (4/4) | 100% (4/4) | 0% (0/4) | 0% (0/4) | 100% (4/4) | 0% (0/4) |
| should_abstain | 100% (3/3) | 100% (3/3) | n/a | n/a | n/a | n/a | n/a | n/a |
| stable_rule | 100% (3/3) | 100% (3/3) | n/a | 100% (3/3) | 0% (0/3) | 0% (0/3) | 100% (3/3) | 0% (0/3) |
| status | 100% (2/2) | 100% (2/2) | n/a | 100% (2/2) | 0% (0/2) | 0% (0/2) | 50% (1/2) | 50% (1/2) |
| temporal_trap | 88% (21/24) | 100% (24/24) | n/a | 96% (23/24) | 4% (1/24) | 0% (0/24) | 96% (22/23) | 0% (0/23) |
| what_changed | 100% (2/2) | 100% (2/2) | n/a | 100% (2/2) | 0% (0/2) | 0% (0/2) | 50% (1/2) | 0% (0/2) |
| split: dev | 90% (38/42) | 100% (38/38) | 100% (5/5) | 95% (36/38) | 5% (2/38) | 0% (0/38) | 92% (33/36) | 3% (1/36) |
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
