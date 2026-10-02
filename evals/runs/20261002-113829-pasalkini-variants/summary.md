# Evaluation run: 20261002-113829-pasalkini-variants

**Pipeline:** `pasalkini`: The answer pipeline: the model classifies the question and rules read its date; date-aware hybrid search plus the articles the question names; the model picks quotes, code checks them, and the model answers from those passages alone; code states an article's status, severance and PKWT compensation, and what a court ruling changed.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `cc6ef6a589` (uncommitted changes)
- Corpus: 848 chunks, fingerprint `03d906b40281a940`
- Dataset: variants, 78 items, sha256 `8d8fb1acf68b`
- Mode: retrieval and answers

> **Provisional.** 0 of 78 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 2% (1/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 78 | 0.77 | 94% (63/67) | 5% (3/57) | 4% (2/57) | 81% (54/67) | 0% (0/65) | 97% (76/78) | 5.7 |
| adversarial | 5 | 1.00 | 100% (3/3) | 100% (1/1) | 0% (0/1) | 67% (2/3) | 0% (0/3) | 100% (5/5) | 5.3 |
| calculation | 5 | 1.00 | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 2.2 |
| date_extraction | 7 | 0.90 | 100% (7/7) | 14% (1/7) | 14% (1/7) | 100% (7/7) | 0% (0/7) | 100% (7/7) | 5.6 |
| should_abstain | 8 | n/a | n/a | n/a | n/a | n/a | 0% (0/1) | 100% (8/8) | 0.6 |
| stable_rule | 5 | 0.90 | 100% (5/5) | 0% (0/2) | 0% (0/2) | 80% (4/5) | 0% (0/5) | 100% (5/5) | 7.9 |
| status | 4 | 0.42 | 100% (4/4) | n/a | n/a | 100% (4/4) | 0% (0/4) | 100% (4/4) | 0.5 |
| temporal_trap | 40 | 0.76 | 92% (36/39) | 2% (1/40) | 2% (1/40) | 77% (30/39) | 0% (0/36) | 95% (38/40) | 6.0 |
| what_changed | 4 | 0.37 | 75% (3/4) | 0% (0/2) | 0% (0/2) | 50% (2/4) | 0% (0/4) | 100% (4/4) | 10.4 |
| split: dev | 42 | 0.77 | 89% (33/37) | 0% (0/33) | 0% (0/33) | 81% (30/37) | 0% (0/37) | 95% (40/42) | 6.0 |
| split: test | 36 | 0.77 | 100% (30/30) | 12% (3/24) | 8% (2/24) | 80% (24/30) | 0% (0/28) | 100% (36/36) | 5.4 |

Answer pipeline:

| Group | Abstained correctly | Intent correct | Date from question correct | Citations pass first try | Repaired | Citations dropped | Answer grounded first try | Answer shown ungrounded |
|---|---|---|---|---|---|---|---|---|
| All | 95% (74/78) | 96% (68/71) | 100% (10/10) | 95% (56/59) | 5% (3/59) | 2% (1/59) | 91% (52/57) | 2% (1/57) |
| adversarial | 100% (5/5) | 80% (4/5) | n/a | 100% (3/3) | 0% (0/3) | 0% (0/3) | 100% (3/3) | 0% (0/3) |
| calculation | 100% (5/5) | 100% (5/5) | 100% (3/3) | n/a | n/a | n/a | n/a | n/a |
| date_extraction | 100% (7/7) | n/a | 100% (7/7) | 100% (5/5) | 0% (0/5) | 0% (0/5) | 80% (4/5) | 20% (1/5) |
| should_abstain | 88% (7/8) | 88% (7/8) | n/a | 100% (1/1) | 0% (0/1) | 0% (0/1) | 100% (1/1) | 0% (0/1) |
| stable_rule | 100% (5/5) | 100% (5/5) | n/a | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) |
| status | 100% (4/4) | 100% (4/4) | n/a | 100% (1/1) | 0% (0/1) | 0% (0/1) | 100% (1/1) | 0% (0/1) |
| temporal_trap | 92% (37/40) | 98% (39/40) | n/a | 92% (37/40) | 8% (3/40) | 2% (1/40) | 89% (34/38) | 0% (0/38) |
| what_changed | 100% (4/4) | 100% (4/4) | n/a | 100% (4/4) | 0% (0/4) | 0% (0/4) | 100% (4/4) | 0% (0/4) |
| split: dev | 93% (39/42) | 97% (37/38) | 100% (5/5) | 94% (33/35) | 6% (2/35) | 0% (0/35) | 88% (29/33) | 3% (1/33) |
| split: test | 97% (35/36) | 94% (31/33) | 100% (5/5) | 96% (23/24) | 4% (1/24) | 4% (1/24) | 96% (23/24) | 0% (0/24) |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
- For this pipeline, *top 5* means the first 5 chunks of the context, which puts the articles the question names before the search results; *Median answer s* is the whole pipeline. Citations are counted after verification.
- *Abstained correctly*: refused or abstained exactly when the key says it should.
- *Citations pass first try*: every quote the model first selected was found in the source it named, in a version that applied on the date; *Repaired*: a second selection was asked for; *Citations dropped*: quotes of the final selection that still failed and were not used.
- *Answer grounded first try*: the first answer mentioned no number or article that it was not given (and, for history questions, no date); otherwise it was rewritten once. *Answer shown ungrounded*: the answer shown still does, and says so in a note.
