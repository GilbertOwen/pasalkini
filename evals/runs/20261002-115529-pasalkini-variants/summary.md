# Evaluation run: 20261002-115529-pasalkini-variants

**Pipeline:** `pasalkini`: The answer pipeline: the model classifies the question and rules read its date; date-aware hybrid search plus the articles the question names; the model picks quotes, code checks them, and the model answers from those passages alone; code states an article's status, severance and PKWT compensation, and what a court ruling changed.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `d469ab4f3f` (uncommitted changes)
- Corpus: 848 chunks, fingerprint `03d906b40281a940`
- Dataset: variants, 78 items, sha256 `8d8fb1acf68b`
- Mode: retrieval and answers

> **Provisional.** 0 of 78 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 2% (1/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 78 | 0.82 | 96% (64/67) | 5% (3/57) | 4% (2/57) | 87% (58/67) | 0% (0/66) | 100% (78/78) | 5.8 |
| adversarial | 5 | 1.00 | 100% (3/3) | 100% (1/1) | 0% (0/1) | 67% (2/3) | 0% (0/3) | 100% (5/5) | 4.1 |
| calculation | 5 | 1.00 | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 2.1 |
| date_extraction | 7 | 0.90 | 100% (7/7) | 14% (1/7) | 14% (1/7) | 100% (7/7) | 0% (0/7) | 100% (7/7) | 5.2 |
| should_abstain | 8 | n/a | n/a | n/a | n/a | n/a | 0% (0/1) | 100% (8/8) | 0.6 |
| stable_rule | 5 | 0.90 | 100% (5/5) | 0% (0/2) | 0% (0/2) | 80% (4/5) | 0% (0/5) | 100% (5/5) | 7.1 |
| status | 4 | 0.88 | 100% (4/4) | n/a | n/a | 100% (4/4) | 0% (0/4) | 100% (4/4) | 0.5 |
| temporal_trap | 40 | 0.79 | 95% (37/39) | 2% (1/40) | 2% (1/40) | 85% (33/39) | 0% (0/37) | 100% (40/40) | 6.8 |
| what_changed | 4 | 0.45 | 75% (3/4) | 0% (0/2) | 0% (0/2) | 75% (3/4) | 0% (0/4) | 100% (4/4) | 8.5 |
| split: dev | 42 | 0.85 | 95% (35/37) | 0% (0/33) | 0% (0/33) | 92% (34/37) | 0% (0/38) | 100% (42/42) | 6.6 |
| split: test | 36 | 0.78 | 97% (29/30) | 12% (3/24) | 8% (2/24) | 80% (24/30) | 0% (0/28) | 100% (36/36) | 5.2 |

Answer pipeline:

| Group | Abstained correctly | Intent correct | Date from question correct | Citations pass first try | Repaired | Citations dropped | Answer grounded first try | Answer shown ungrounded | Cut-off pick read | Read again in full |
|---|---|---|---|---|---|---|---|---|---|---|
| All | 96% (75/78) | 96% (68/71) | 100% (10/10) | 97% (56/58) | 3% (2/58) | 2% (1/58) | 90% (52/58) | 3% (2/58) | 0% (0/58) | 5% (3/58) |
| adversarial | 100% (5/5) | 80% (4/5) | n/a | 100% (3/3) | 0% (0/3) | 0% (0/3) | 67% (2/3) | 0% (0/3) | 0% (0/3) | 0% (0/3) |
| calculation | 100% (5/5) | 100% (5/5) | 100% (3/3) | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| date_extraction | 100% (7/7) | n/a | 100% (7/7) | 100% (5/5) | 0% (0/5) | 0% (0/5) | 60% (3/5) | 40% (2/5) | 0% (0/5) | 0% (0/5) |
| should_abstain | 88% (7/8) | 88% (7/8) | n/a | 100% (1/1) | 0% (0/1) | 0% (0/1) | 100% (1/1) | 0% (0/1) | 0% (0/1) | 0% (0/1) |
| stable_rule | 100% (5/5) | 100% (5/5) | n/a | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) | 0% (0/5) | 0% (0/5) |
| status | 100% (4/4) | 100% (4/4) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| temporal_trap | 95% (38/40) | 98% (39/40) | n/a | 95% (38/40) | 5% (2/40) | 2% (1/40) | 92% (37/40) | 0% (0/40) | 0% (0/40) | 8% (3/40) |
| what_changed | 100% (4/4) | 100% (4/4) | n/a | 100% (4/4) | 0% (0/4) | 0% (0/4) | 100% (4/4) | 0% (0/4) | 0% (0/4) | 0% (0/4) |
| split: dev | 95% (40/42) | 97% (37/38) | 100% (5/5) | 97% (33/34) | 3% (1/34) | 0% (0/34) | 91% (31/34) | 3% (1/34) | 0% (0/34) | 9% (3/34) |
| split: test | 97% (35/36) | 94% (31/33) | 100% (5/5) | 96% (23/24) | 4% (1/24) | 4% (1/24) | 88% (21/24) | 4% (1/24) | 0% (0/24) | 0% (0/24) |

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
- For this pipeline, *top 5* means the first 5 chunks of the context, which puts the articles the question names before the search results; *Median answer s* is the whole pipeline. Citations are counted after verification.
- *Abstained correctly*: refused or abstained exactly when the key says it should.
- *Citations pass first try*: every quote the model first selected was found in the source it named, in a version that applied on the date; *Repaired*: a second selection was asked for; *Citations dropped*: quotes of the final selection that still failed and were not used.
- *Answer grounded first try*: the first answer mentioned no number or article that it was not given (and, for history questions, no date); otherwise it was rewritten once. *Answer shown ungrounded*: the answer shown still does, and says so in a note.
- *Cut-off pick read*: the reply that picks quotes ran out of room, and its quotes were read from their start. *Read again in full*: the answer said that no rule exists, and was asked again with the quoted articles in full.
