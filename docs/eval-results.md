# Evaluation results

Status on 2026-10-01, at the end of Phase 6 (`PLAN.md`).

## Read this first

- **The answer keys are drafts.** All 78 were written by an AI from the parsed legal texts and none has been checked by a person yet. Numbers can move when they are.
- **The set is small.** 78 questions: 42 for development and 36 held out. One question is 1 to 3 percentage points.
- **Two kinds of numbers.** Sections 1 and 5 count *sources*: which texts reached the model and which it cited. Section 2 asks whether the *answer is right*, which needs someone to read it.
- **The reading was done by the AI assistant that built the system** (Claude), against the draft keys, on the development questions only. It is a reference to work with, not a verdict: a person still has to grade a run (`grading.csv` in each run folder).
- **Held-out answers were not read one by one.** They are graded by an automatic judge whose agreement with the reading is measured in section 3. Only totals are looked at.
- Everything runs locally: `qwen3.5:4b` and `qwen3-embedding:0.6b` on a laptop RTX 3060 (6 GB).

## 1. Does the answer cite law that did not apply on the date?

All 78 questions. 57 name sources that must not be cited; 67 have an expected source.

| Pipeline | Stale text given to the model | Answer cites a stale source | Answer cites an expected source | Cites an ID it was not given | Median s |
|---|---|---|---|---|---|
| `baseline`: plain RAG, dates ignored | 88% (50/57) | 65% (37/57) | 64% (43/67) | 3% (2/71) | 3.1 |
| `versions`: each chunk labelled with its validity dates, no filter | 82% (47/57) | 65% (37/57) | 66% (44/67) | 16% (11/69) | 3.1 |
| `temporal`: only versions that applied on the date are searched | 0% (0/57) | 0% (0/56) | 88% (58/66) | 7% (5/68) | 3.3 |
| `temporal-hybrid`: the same, dense + BM25 | 0% (0/57) | 0% (0/57) | 84% (56/67) | 7% (5/70) | 3.0 |
| `pasalkini`, Phase 5: one answer call with quotes | 0% (0/57) | 0% (0/57) | 91% (61/67) | 0% (0/68) | 6.7 |
| `pasalkini`, Phase 6: quotes picked first, then the answer | 0% (0/57) | 0% (0/57) | 91% (61/67) | 0% (0/65) | 5.1 |

Runs: 10:46 to 11:21 (commit `b80bc1e`; Phase 5 at `3a63d25`) and 23:07 (`20261001-230756-pasalkini`, commit `ca9d2a0`).

- **Labels are not enough.** Telling the model when each text applied (`versions`) left stale citations where they were, at 65%, and it cited IDs it was not given more often (16%). Removing outdated text before the search is what works.
- On the 36 held-out questions: stale citations 58% (14/24) for `baseline` and 0% (0/24) for every date-filtered pipeline. An expected source is cited in 47% (14/30) for `baseline`, 93% (28/30) for Phase 5 and 87% (26/30) for Phase 6.

## 2. Is the answer right?

### The rubric

One grade per answer, read against its key and the legal text:

- **correct**: the main answer is right and nothing stated is legally wrong for the date;
- **partly**: the main answer is right, but a false or misleading statement comes with it, or a limit is missing that changes the conclusion for many readers;
- **wrong**: the main answer is wrong, or the system declined a question it should answer.

A question that should be refused is correct when it is refused.

### Development questions, read one by one

| Pipeline | Correct | Partly | Wrong |
|---|---|---|---|
| `baseline` (plain RAG) | 17 | 12 | 13 |
| `pasalkini`, Phase 5 | 23 | 14 | 5 |
| `pasalkini`, Phase 6 | **33 to 36** | 4 to 6 | 2 to 3 |

42 questions each; grades in `grades-claude.csv` in the run folders. The Phase 6 row is three full runs (33 / 6 / 3, 35 / 5 / 2 and 36 / 4 / 2): the wording of answers varies from run to run, and a grade can move with it.

- **Plain RAG is wrong mostly because of the date.** 13 of its 25 imperfect answers apply law that did not apply (5 years of PKWT in 2019; suspension of the minimum wage in 2022).
- **Phase 5 cited the right source in 89% of these questions and said the right thing in 55%.** Its mistakes sat next to correct citations: a wrong article or law name ("Pasal 40 UU 13/2003" for PP 35/2021), a wrong date of change, "2 kali upah pokok" for twice the schedule, a sentence misread (1 rest day for a 5-day week from a text that says 2).
- The citation check of Phase 5 could not see any of this: it checks quotes, not the answer's own sentences.

### What Phase 6 changed, and what each change did

Every change came from reading the wrong and partly-right answers of the run before it. Grades are for the 42 development questions.

| Step | Correct / partly / wrong | What changed |
|---|---|---|
| Phase 5 | 23 / 14 / 5 | One call: answer with quotes, over up to seven articles |
| 1 | 30 / 5 / 7 | Two calls: pick quotes (checked), then answer from those passages only, copying the words it answers from before answering. Code opens the answer where it knows it (status of a named article, the calculator's result). Checks on the answer's own numbers and articles |
| 2 | 33 / 3 / 6 | Status of a named article and amounts that were asked for are written by code alone. "Not yet in force" answers from law that began later. The first wording added for "what changed" questions |
| 3 | 33 / 5 / 4 | The model picks again when the answer step finds no answer. "What changed" answered as two summaries, old wording and current, each checked against its own passage |
| 4 | 33 / 6 / 3 | Abbreviations spelled out for the model (`PKWTT` was read as `PKWT`) |
| 5 | 36 / 4 / 2 | After an opening written by code, the model's sentences are shown only if they pass the checks; after a calculation, none that restates an amount, a multiplier or an article |

Step 5 is two changes, measured on two full runs: 35 / 5 / 2, then 36 / 4 / 2. Wording varies from run to run (section 6), and a grade can move with it: read "33 to 36 of 42", not "36".

The pattern in these steps: **what code can state, the model should not write.** The model's sentences after a calculation went wrong in four runs in four different ways ("0,5 kali upah sebulan", "Peraturan Presiden 35/2021", "tabel Pasal 40 ayat (2)" for long-service pay, "2 kali upah per bulan kerja"). No prompt fixed that. Leaving those sentences out did.

### Still wrong

| Question | Grade | What happens |
|---|---|---|
| Long leave after 6 years, in 2019 | wrong | The passage says the leave is taken in the seventh and eighth year by workers with 6 years of service, at certain companies. The model answers no, "because 6 years is not yet enough". It copies the right words as its basis and still concludes wrongly, in every run |
| JKP for a dismissed worker, in 2019 | wrong | The programme began in 2020. The model takes "social security" in Pasal 99 to include it. When it declines instead, code finds the later article and says it was not yet in force; when it answers, nothing catches it |
| Long leave, in 2025 | partly | MK 168 struck the word "dapat". The model now reads the sentence without it and no longer calls the leave optional, but does not say that certain companies must give it. The note by code under the answer does |
| What changed in outsourcing | partly | The old and the current wording of Pasal 66 are summarised correctly; the main change (two schemes became one, the limit to supporting work went) is in articles the model did not pick |
| Suspension of the minimum wage, 2019 and 2022 | partly | Right conclusions; one names Pasal 89 as the source of conditions it does not contain, the other argues from the duty to pay wages on time |

### Held-out questions

The 36 held-out answers are graded by the judge of section 3. Its "correct" is generous (it calls half of the partly-right answers correct), so compare rows, not columns.

| Pipeline | Correct | Partly | Wrong |
|---|---|---|---|
| `baseline` | 11 | 7 | 18 |
| `pasalkini`, Phase 5 | 23 | 4 | 9 |
| `pasalkini`, Phase 6 | 24 | 5 | 7 |

- The gain over plain RAG holds on questions the system was never tuned on.
- The gain of Phase 6 over Phase 5 is clear on the development questions and small here: one more correct and two fewer wrong, which is within what this judge can tell apart. The first full run of Phase 6 gave 25 / 5 / 6.
- **Phase 6 declines 2 held-out questions that Phase 5 answered.** In both, the answer step found no answer in the passages picked, and picking again did not help. They count as wrong above. The system then shows the passages it found instead of an answer.

A person's grades on the held-out answers are what would settle this. `evals/runs/20261001-230756-pasalkini/grading.csv` is the sheet.

## 3. The judge

`uv run pasalkini judge <run>` and `uv run pasalkini agreement <run>` (`evals/judge.py`).

The judge is the same local 4B model. It is not asked for a grade. It is asked, for each point of the key, whether the answer states it, contradicts it or leaves it out; for each "must not" in the key, whether the answer does it; and for one sentence of the answer that goes against the key. Code turns that into a grade. Refusals are graded by code.

Agreement with the reading, on 252 answers (six runs of 42 development questions):

| | |
|---|---|
| Same grade | 81% (204/252) |
| Same on "correct or not" | 85% (215/252) |
| Same on "wrong or not" | 93% (235/252) |
| Cohen's kappa | 0.59 |

| Reading \ judge | correct | partly | wrong |
|---|---|---|---|
| correct | 158 | 8 | 6 |
| partly | 23 | 14 | 7 |
| wrong | 0 | 4 | 32 |

- **It never called a wrong answer correct** (0 of 36), and found 32 of the 36.
- **It misses subtle errors.** 23 of 44 partly-right answers passed as correct: a wrong article number or a wrong date next to a right main answer is not in the key, so the judge has nothing to hold it against.
- When it says "wrong" it is right 32 times in 45; the rest are partly-right (7) or correct (6) answers.

So: usable to count wrong answers and to compare pipelines, not to certify that an answer is right. The reference grades are themselves an AI's reading; the plan was to calibrate against a person's grades, which do not exist yet.

## 4. Thinking on or off

`qwen3.5:4b` can reason before it answers (`think`). Phase 5 found that with the whole context in the prompt, thinking used its entire budget of 2,500 tokens without producing an answer. Phase 6 made the answer call short (600 to 900 tokens in), so it was tried again on the 36 answer-step prompts of the first development run:

| | Thinking off | Thinking on (budget 2,500 tokens) |
|---|---|---|
| Calls that returned an answer | 36 of 36 | **1 of 36** |
| Seconds per call | about 2 | 37 median, 64 mean |

Thinking is not usable for this model on this hardware with JSON-constrained output. What Phase 6 uses instead is cheaper: the answer's JSON starts with the words it answers from (`dasar`) and any limit on them (`batasan`), about 60 extra tokens. That was enough for the question about rest days in a 5-day week, which the model had answered "1 day" from a sentence that says "1 day for a 6-day week or 2 days for a 5-day week".

Not done from the plan's model comparison, because each needs a decision: a smaller model for classifying questions (a download) and an API model on synthetic questions (a key and a cost).

## 5. The Phase 6 pipeline in numbers

Run `20261001-230756-pasalkini`, all 78 questions.

| Check | All | Development | Held out |
|---|---|---|---|
| Refused or abstained exactly when it should | 97% (76/78) | 42/42 | 34/36 |
| Kind of question classified correctly | 100% (71/71) | 38/38 | 33/33 |
| Date read from the question | 100% (10/10) | 5/5 | 5/5 |
| Expected source reaches the context | 100% (67/67) | 37/37 | 30/30 |
| ... and is cited | 91% (61/67) | 35/37 | 26/30 |
| First pick of quotes passes every check | 98% (56/57) | 32/33 | 24/24 |
| First answer mentions nothing it was not given | 98% (55/56) | 32/32 | 23/24 |

How the 78 answers were made:

| | Questions | Median seconds |
|---|---|---|
| Model picks quotes, model answers | 48 | 5.3 |
| Code opens (calculator or status), model continues | 6 | 10.4 |
| Code alone (named article's status, an amount asked for) | 11 | 1.9 |
| Refused as out of scope | 10 | 0.4 |
| "Not yet in force on that date", from later law | 1 | 5.5 |
| Declined: no answer found in the passages | 2 | 9.7 |

- Median 5.1 s a question, 90% under 9.4 s, the slowest 15 s. Phase 5 took 6.7 s. Two short calls are faster than one long one, and 21 questions need no call to pick quotes or to write.
- **Retrieval no longer loses questions.** Phase 5 lost 5 of the 67 answerable questions before the answer step. A question about severance now always gets the articles that hold the severance tables, and the expected source reaches the context in all 67.
- **The answer step loses more.** 6 questions do not cite an expected source (Phase 5: 1): two declined, one answered as "not yet in force" (which cites nothing as applicable law), three answered from other articles. Picking quotes first is stricter than answering in one go: what is not picked cannot be used.

## 6. The same run twice

Temperature is 0 and the seed is fixed. Two runs still differ.

- Run `20261001-224820-pasalkini` answered a development question it had refused in every run before: "Berapa pajak penghasilan (PPh 21) yang dipotong dari uang pesangon saya?" was classified as a calculation. Same prompt, same code, same model instance as the run eight minutes earlier. Asked again four times it stayed a calculation. After unloading and reloading the model it was out of scope again, four times of four. In that run 29 of the 42 development answers differed in wording from the run before, and 8 of 78 cited different sources.
- The cause was not found. Loading the embedding model next to the chat model does not reproduce it.
- Since then every evaluation run unloads the chat model first (`answer/llm.py: unload`). The two runs made that way cite the same sources for all 78 questions and differ in the wording of 8 answers, 6 of them answers that open with a calculation, whose handling changed between the two runs.

What this means for reading the tables: a difference of one or two questions between two runs is noise, and a label that sits on a boundary (a tax question about severance) can flip. Four full runs of Phase 6 gave 61, 62, 61 and 61 of 67 for an expected source cited, and 76, 75, 76 and 76 of 78 for refusals.

## 7. Retrieval

Development split, 42 questions, retrieval only (runs of 2026-10-01 09:34, commit `cb34bf0`).

| Configuration | Recall@5 | MRR@10 | Stale text in top 5 |
|---|---|---|---|
| `baseline` (dense, dates ignored) | 0.61 | 0.56 | 91% (30/33) |
| `versions` (dated chunks, no filter) | 0.44 | 0.48 | 85% (28/33) |
| `temporal` (dense, date filter) | 0.68 | 0.77 | 0% |
| `temporal` + query rewriting | 0.71 | 0.77 | 0% |
| `temporal` + titles embedded with the text | 0.68 | 0.77 | 0% |
| `temporal-bm25` | 0.67 | 0.77 | 0% |
| `temporal-hybrid` (dense + BM25, RRF) | **0.73** | 0.81 | 0% |
| `temporal-hybrid` + query rewriting | 0.70 | 0.79 | 0% |
| `temporal-hybrid` + embedded titles | 0.72 | **0.82** | 0% |
| `temporal-hybrid` + both | 0.71 | 0.77 | 0% |

- The date filter is the large effect. It removes stale text, and MRR rises from 0.56 to 0.77 because outdated versions of the right article no longer take the top ranks.
- Hybrid search was chosen on these numbers. The held-out questions do not confirm it: on the 36 test questions dense search has Recall@5 0.77 and MRR 0.90, hybrid 0.73 and 0.82. The choice is a weak one.
- The search itself is unchanged in Phase 6. The pipeline's *context* has Recall@5 0.87 and MRR 0.91 on the 78 questions (Phase 5: 0.77 and 0.84) because articles are added to it by rule: those the question names, those the calculator used, and the severance tables.
- The planned target, Recall@5 ≥ 0.90 from search alone, is not met. Untried because each needs a download of about 2 GB: a reranker (`bge-reranker-v2-m3`) and `bge-m3` embeddings.

## 8. From Phase 5, kept for the record

### A fixed pipeline or an agent?

Same date rules, same answer step, same checks, but the model chooses what to look up: one action per step (search with its own query, an article's history, the calculator, answer, refuse), at most four steps. Measured twice on the 78 questions: with the Phase 5 answer step (run `20261001-164725-pasalkini-agent`, commit `fe3bf89`) and with the Phase 6 one (run `20261001-231812-pasalkini-agent`, commit `1eeebef`).

| | Pipeline, Phase 5 | Agent, Phase 5 | Pipeline, Phase 6 | Agent, Phase 6 |
|---|---|---|---|---|
| Answer cites a stale source | 0% (0/57) | 0% (0/57) | 0% (0/57) | 0% (0/57) |
| Answer cites an expected source | 91% (61/67) | 81% (54/67) | 91% (61/67) | 82% (55/67) |
| ... on the 36 held-out questions | 93% (28/30) | 77% (23/30) | 87% (26/30) | 73% (22/30) |
| Expected source reaches the context | 93% (62/67) | 85% (57/67) | 100% (67/67) | 88% (59/67) |
| Refuses or abstains exactly when it should | 100% (78/78) | 92% (72/78) | 97% (76/78) | 91% (71/78) |
| Median seconds per question | 6.7 | 9.5 | 5.1 | 7.4 |

- The agent made 2.0 tool calls a question both times (latest run: 139 searches, 9 calculator runs, 8 history look-ups; 12 questions used no tool).
- Its own search queries find the expected source less often than searching with the question: in the latest run it lost 8 questions in retrieval, the pipeline none.
- It opened an article's history on 5 of the 8 status and what-changed questions. Without it the agent sees only the current wording. In a trial on the development question about overtime it searched four times, never opened the history, and answered that nothing fundamental had changed (the limit went from 3 to 4 hours a day).
- All 7 of its abstention errors in the latest run were questions it declined though it should answer, two of them adversarial. It refused all 8 out-of-scope questions.
- Stale citations stay at 0% either way: the date filter sits inside the search tool, where the model cannot skip it.
- The agent's answers were not read and graded.

For a 4B model on this task the fixed pipeline is better on every count that differs, and takes about 30% less time. The agent stays in the code as a comparison (`uv run pasalkini eval pasalkini-agent`), not as the default.

### The citation check, before and after

The first version of the check wanted the quote word for word. On the 61-question run of 10:21 (commit `0a7276e`), 65% of first answers passed (37/57), 35% were sent back and 21% ended with a citation dropped. Reading every failure on the development split showed the model was rarely inventing text:

- it tidied what it copied: resolved a cross-reference ("sebagaimana dimaksud dalam ayat (1)" became "atas kemauan sendiri"), dropped a list marker, added a full stop, or repaired a word the PDF extraction had broken (the source says "sebagai be-rikut");
- it put a right quote under a wrong ID (`uu-13-2003/pasal-81` for text in `perppu-2-2022/pasal-81/angka-25`);
- it cited the ruling that conditions an article by the ID shown in the article's notes.

The check now locates the quote (word for word, or 80% of its words in order within a stretch about twice its length, and every number), shows the source's own words, and files the citation under the chunk that has them. Phase 6 added two cases found the same way: a locator the model writes in front of a quoted item ("(2) d. istirahat panjang ..."), and a closing bracket scanned as a letter ("ayat (2l."). First picks now pass in 98% of questions.

## 9. Known gaps

- **No person has graded anything.** The answer keys, the reading of the development answers and the judge are all AI work.
- The model's reasoning: two development answers are wrong with the right passage in front of it (section 2). A larger model is the obvious thing to try; it does not fit the 6 GB GPU together with anything else.
- Two held-out questions are declined that Phase 5 answered.
- "Not yet in force" answers rest on PasalKini's sources, which hold 12 instruments. A rule that existed earlier in a regulation outside the corpus would be reported as starting later. The answer says so in a note.
- Rulings of the Constitutional Court are read out by rule from their fixed formulas (`temporal/rulings.py`). The 21 points of MK 168 and the 2 of MK 19 were checked against the rule's output; a ruling worded differently is quoted, not interpreted.
- Search alone: Recall@5 0.73 to 0.77.
- Older MK rulings on UU 13/2003 are not in the model, so some articles show as in force until 2020.
- The new labor law (DPR plenary planned for 6 October 2026) is not in the corpus.
- The evaluation set is 78 questions, not the 150 planned, and has no questions about the new law.
