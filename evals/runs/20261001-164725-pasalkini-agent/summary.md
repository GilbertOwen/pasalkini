# Evaluation run: 20261001-164725-pasalkini-agent

**Pipeline:** `pasalkini-agent`: Agent: rules read the date; the model picks one tool per step (search with its own query, an article's history, the calculator), at most four steps, then the same answer step and citation check as pasalkini.

- Models: `qwen3-embedding:0.6b` (ac6da0dfba84), `qwen3.5:4b` (2a654d98e6fb)
- Git commit: `fe3bf89053`
- Corpus: 848 chunks, fingerprint `4187af9e33b47fd8`
- Dataset: 78 items, sha256 `988e70202fdf`
- Mode: retrieval and answers

> **Provisional.** 0 of 78 answer keys have been checked by a person. The rest are drafts, so these numbers can move when the keys are reviewed.

**Headline:** on temporal-trap questions, the answer cited a source that did not apply on the question's date in 0% (0/40) of the questions that have forbidden sources labelled.

| Group | Items | Recall@5 | Hit@5 | Stale text in top 5 | Answer cites stale source | Answer cites expected source | Cites an ID not in context | Valid JSON | Median answer s |
|---|---|---|---|---|---|---|---|---|---|
| All | 78 | 0.66 | 81% (54/67) | 0% (0/57) | 0% (0/57) | 81% (54/67) | 0% (0/62) | 100% (78/78) | 9.5 |
| adversarial | 5 | 0.33 | 33% (1/3) | 0% (0/1) | 0% (0/1) | 33% (1/3) | 0% (0/1) | 100% (5/5) | 0.5 |
| calculation | 5 | 0.90 | 100% (5/5) | 0% (0/5) | 0% (0/5) | 100% (5/5) | 0% (0/5) | 100% (5/5) | 11.0 |
| date_extraction | 7 | 0.55 | 71% (5/7) | 0% (0/7) | 0% (0/7) | 71% (5/7) | 0% (0/5) | 100% (7/7) | 9.5 |
| should_abstain | 8 | n/a | n/a | n/a | n/a | n/a | n/a | 100% (8/8) | 0.5 |
| stable_rule | 5 | 0.80 | 80% (4/5) | 0% (0/2) | 0% (0/2) | 80% (4/5) | 0% (0/4) | 100% (5/5) | 6.9 |
| status | 4 | 0.62 | 100% (4/4) | n/a | n/a | 100% (4/4) | 0% (0/4) | 100% (4/4) | 12.8 |
| temporal_trap | 40 | 0.68 | 85% (33/39) | 0% (0/40) | 0% (0/40) | 85% (33/39) | 0% (0/40) | 100% (40/40) | 10.2 |
| what_changed | 4 | 0.37 | 50% (2/4) | 0% (0/2) | 0% (0/2) | 50% (2/4) | 0% (0/3) | 100% (4/4) | 11.9 |
| split: dev | 42 | 0.70 | 86% (32/37) | 0% (0/33) | 0% (0/33) | 84% (31/37) | 0% (0/36) | 100% (42/42) | 9.6 |
| split: test | 36 | 0.61 | 73% (22/30) | 0% (0/24) | 0% (0/24) | 77% (23/30) | 0% (0/26) | 100% (36/36) | 9.4 |

Answer pipeline:

| Group | Abstained correctly | Intent correct | Date from question correct | Citations pass first try | Repaired | Citations dropped |
|---|---|---|---|---|---|---|
| All | 92% (72/78) | 90% (64/71) | 100% (10/10) | 90% (56/62) | 10% (6/62) | 3% (2/62) |
| adversarial | 60% (3/5) | 60% (3/5) | n/a | 100% (1/1) | 0% (0/1) | 0% (0/1) |
| calculation | 100% (5/5) | 100% (5/5) | 100% (3/3) | 100% (5/5) | 0% (0/5) | 0% (0/5) |
| date_extraction | 71% (5/7) | n/a | 100% (7/7) | 100% (5/5) | 0% (0/5) | 0% (0/5) |
| should_abstain | 100% (8/8) | 100% (8/8) | n/a | n/a | n/a | n/a |
| stable_rule | 80% (4/5) | 80% (4/5) | n/a | 100% (4/4) | 0% (0/4) | 0% (0/4) |
| status | 100% (4/4) | 100% (4/4) | n/a | 75% (3/4) | 25% (1/4) | 0% (0/4) |
| temporal_trap | 100% (40/40) | 100% (40/40) | n/a | 88% (35/40) | 12% (5/40) | 5% (2/40) |
| what_changed | 75% (3/4) | 0% (0/4) | n/a | 100% (3/3) | 0% (0/3) | 0% (0/3) |
| split: dev | 95% (40/42) | 92% (35/38) | 100% (5/5) | 94% (34/36) | 6% (2/36) | 0% (0/36) |
| split: test | 89% (32/36) | 88% (29/33) | 100% (5/5) | 85% (22/26) | 15% (4/26) | 8% (2/26) |

Agent: 2.0 tool calls a question on average (cari 140, hitung 8, riwayat 7); 12 of 78 questions used no tool.

Definitions:

- *Recall@5*: share of expected sources found in the top 5 chunks (a document-level label is found by any chunk from that document).
- *Stale text in top 5*: a `must_not_cite` source is among the chunks given to the model.
- *Answer cites stale source*: the answer's citations include a `must_not_cite` source.
- *Cites an ID not in context*: the model invented or altered a source ID.
- For this pipeline, *top 5* means the first 5 chunks of the context, which puts the articles the question names before the search results; *Median answer s* is the whole pipeline. Citations are counted after verification.
- *Abstained correctly*: refused or abstained exactly when the key says it should.
- *Citations pass first try*: the first answer passed every citation check; *Repaired*: a second answer was asked for; *Citations dropped*: the final answer still had citations that failed and were not shown.
