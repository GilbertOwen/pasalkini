# Why RAG quotes outdated law, and what it took to stop it

*Draft, 2 October 2026. Not published. Every number here is from `docs/eval-results.md`; the answer keys behind them are AI drafts that no person has checked yet.*

## The problem

Ask how long a fixed-term employment contract (PKWT) may run in Indonesia and the right answer depends on the day you mean:

- in June 2019: two years, extended once for one year (UU 13/2003 Pasal 59);
- in June 2022: five years in total (PP 35/2021 Pasal 8);
- in June 2025: five years in total, now by a Constitutional Court ruling (MK 168/PUU-XXI/2023).

Indonesian labor law has been changed several times since 2020 (UU 11/2020, Perppu 2/2022, UU 6/2023, a Constitutional Court ruling in 2024), and a new labor law is in parliament. All of those texts are about the same thing and use nearly the same words. A retrieval system ranks by similarity, so the 2003 wording, the 2020 wording and the 2022 wording of one article score the same. Which one reaches the model is close to chance. The model then answers with confidence, and cites a real article.

PasalKini is a small assistant built to answer a labor-law question **for a date**. It runs on a laptop GPU (6 GB) with a 4B model. This is what building it showed.

## 1. Measure it first

78 questions, each with a date, the sources a right answer rests on, and the sources it must not cite. Half are pairs: the same question asked about two or three dates.

| Pipeline | Answer cites law that did not apply on the date |
|---|---|
| Plain RAG | 65% (37 of 57) |
| Every chunk labelled with its validity dates, no filter | 65% (37 of 57) |
| Only versions that applied on the date are searched | 0% |

Two things in that table. Plain RAG cites outdated law in two answers out of three on these questions. And **telling the model the dates does nothing**: with "berlaku 25 Maret 2003 s.d. 1 November 2020" written on every chunk, the rate stayed at 65%, and the model invented source IDs more often. What works is not giving it the text.

## 2. Model time, then filter before you search

The law changes by events: an article is amended, inserted or deleted; a court conditions it; a law is revoked and its predecessor's wording comes back. PasalKini extracts those events from the amending laws themselves and replays them in date order. The result is every article's versions, each with the days it applied: 809 versions from 12 instruments.

A question is then searched only among the versions that applied on its date. A version that did not apply cannot be retrieved, so it cannot be cited. That is the whole trick, and it is not a prompt.

## 3. Citing the right source is not being right

With the date filter and a check that every quote exists in its source, the system cited an expected source in 89% of the development questions. Reading the 42 answers against their keys, **55% were fully correct**. The mistakes sat next to correct citations: a wrong law name, a wrong date of change, "twice the basic wage" for "twice the schedule", a sentence misread.

Two changes moved that to 33–36 of 42:

- **Pick the passages first, then answer from them alone.** One call chooses quotes, code checks them, a second call writes one to three sentences from those passages only, starting from the words it answers from.
- **What code can state, the model does not write.** Whether a named article still applies and since when, a severance amount, what a court ruling changed: all of these come from the temporal model or the calculator. After a calculation, the model's sentences about amounts are simply not shown. They had been wrong in four runs in four different ways, and no prompt fixed that.

## 4. The test set flatters you

On questions it was never tuned on, graded by an automatic judge, the same system got 24 of 36. Then the app ran, and questions typed by hand did worse again: with "kontrak kerja waktu tertentu" in place of "PKWT", it answered that there is no maximum.

So every question got a second wording, measured apart. Reworded, the development questions fell from 36 to 26 correct of 42. Six changes later they are at 34. On the held-out half the gain is 22 to 25 of 36: real, and small. That second number is the one to believe.

## 5. A guarantee that depends on the model is not a guarantee

The reworded questions found something worse than wrong answers. Two held-out answers cited an outdated wording: the first time since the date filter went in.

The date was right. But questions about an article's *status* ("is Pasal 59 still in force?") are searched in every wording up to the date, because the answer needs the old one, and **the model decides which questions are status questions**. It took three ordinary questions for status questions, and old wordings reached the answer. The filter was code. The choice of filter was not.

The fix is a rule in code: only a wording that applied on the date can be a source, whatever the model takes the question for. An older wording is listed apart, as what the law used to say. And there is now a test that forces the mistake: every ordinary development question is run with its kind set to the wrong one. Before, 7 of 60 such answers cited outdated law. After, none.

No ordinary test question had ever taken that path. It took a reworded, held-out question to find it, and a deliberate fault to prove it closed.

## What did not work

- **Thinking mode** on this model and GPU: 1 answer in 36 came back within the token budget, at 37 s each.
- **An agent** that chooses its own searches: cited an expected source in 82% against 91% for the fixed pipeline, and was slower.
- **Rewriting the question with the model** before the search: no gain.
- **Withholding answers of the form "no rule exists"**: made two answers worse and fixed none. Asking again with the whole article did work.

## Limits

- No person has checked an answer key or graded an answer. The keys, the reading and the judge are all AI work.
- 78 questions is small; one question is one to three points.
- A 4B model still misreads a passage it has in front of it. Two development answers are wrong that way in every run.
- A rule that was deleted is not found by a question that does not name it.
- The new labor law is not in the corpus.

## Takeaways

1. For law, similarity is not validity. Model time explicitly and filter before ranking.
2. Count stale citations and correct answers separately. A system can cite the right article and still be wrong.
3. Give the model less to do. Every sentence code could write was one the model stopped getting wrong.
4. Reword your test questions. Then hold half back and believe that half.
5. If a guarantee passes through a model's judgement, test it with the model wrong.

PasalKini gives legal information, not legal advice. Code: `github.com/GilbertOwen/pasalkini` (private for now).
