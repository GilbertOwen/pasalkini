# Architecture

PasalKini answers a labor-law question with the law that applied on a given date. This page shows how the pieces fit; `PLAN.md` explains why the project exists and what comes next.

## Data flow

```
OFFLINE (when a legal instrument is added or changes)

sources/manifest.yaml ──► download ──► extract ──► parse ──────────────► data/processed/<id>.json
  (official URLs,          (robots.txt,  (PyMuPDF,    (numbering-order      articles, ayat, amendment
   dates, parse hints)      3 s apart,    headers,     state machine,       points, MK rulings,
                            SHA-256)      stamps)      OCR repair)          penjelasan, closing
                                                                                  │
sources/events-manual.yaml ───────────────────────────────┐                      ▼
                                                           ├──► extract events ──► replay by date ──► data/processed/pasalkini.db
sources/events-review.csv (human verdicts) ───────────────┘    (enact, amend,      (versions with      (event, version)
                                                                insert, delete,     valid_from/to and
                                                                interpret, revoke)  status)

ONLINE (per question, answer/pipeline.py)

question (+ date) ─► date: read from the question, else the date picker, else today          rules
                 ─► kind: explain | status | history | calculate | out of scope             qwen3.5:4b, JSON
                 ─► out of scope ─► refusal and referral (no search)
                 ─► a calculation, or a dismissal whose payments are asked about
                    ─► the model reads the facts; tools/pesangon.py computes                 code
                 ─► context: articles the question names, the severance tables for a
                    severance question, the calculator's articles, then dense + BM25
                    search over the versions that applied on the date
                    (every version up to it for status and history questions)
                 ─► status of a named article ─► answered from the temporal model            code
                 ─► an amount that was asked for ─► answered from the calculator             code
                 ─► otherwise:
                    1. the model picks quotes from the context                               qwen3.5:4b, JSON
                    2. code finds each quote (near matches allowed, never a different        code
                       number) in a text that applied on the date; one repair
                    3. code lays out the passages: the quoted lines, the line that opens
                       their ayat, lines that refer back to them, and what the
                       Constitutional Court ruled about them
                    4. the model answers from the passages alone: first the words it         qwen3.5:4b, JSON
                       answers from, then any limit on them, then the answer
                       (a question about change: one summary of the old wording, one of
                       the current)
                    5. code checks the answer's numbers, articles and dates against          code
                       what it was given; one rewrite
                 ─► no answer in the passages ─► the model picks again, once
                 ─► still none ─► articles that began after the date are searched:
                    "not yet in force on that date", or abstain and show what was found
                 ─► notes by code: rulings on the cited articles, what changed after the date
```

## Key ideas

| Idea | Where | Why |
|---|---|---|
| Source IDs say where wording was published (`perppu-2-2022/pasal-81/angka-15`) | everywhere | Evaluation labels written before the temporal model existed stay valid after it |
| Parse by numbering order | `ingest/parse.py` | OCR breaks markers; knowing what comes next repairs `(21` → (2), `Pasal 8O` → 80, `L7.` → 17 |
| Events are the source of truth | `temporal/events.py`, `temporal/build.py` | A new law is more events, not hand edits; versions can always be rebuilt |
| Three statuses: in force, conditional, repealed | `temporal/model.py` | MK conditional rulings and "sepanjang tidak bertentangan" clauses are real legal states |
| Revocation restores replaced wording | `temporal/build.py` | Perppu 2/2022 revoked UU 11/2020 (Pasal 185) while restating its amendments |
| Filter by date before ranking | `retrieve/temporal.py` | A version that did not apply cannot be retrieved, so it cannot be cited |
| Arithmetic in code | `tools/pesangon.py` | Exact, testable, and each rule names its article |
| Code checks every quote | `answer/verify.py` | A small model tidies what it copies and mixes up IDs; the check finds the passage, refuses a changed number, and shows the source's own words |
| Pick the passages first, then answer from them alone | `answer/pipeline.py` | Answering over seven articles at once, the model mixed details between them and misread long ones. Correct answers on the development questions went from 23 to 33-36 of 42 |
| What code can state, the model does not write | `answer/context.py`, `tools/pesangon.py`, `temporal/rulings.py` | An article's status, a severance amount and the effect of a court ruling come from the temporal model, the rules and the ruling's fixed formula. The model's own versions of these were where the mistakes were |
| The answer's sentences are checked too | `answer/verify.py: ungrounded` | Every number and article the answer mentions must be in what it was given; after an opening by code, sentences that fail are left out |
| A fixed pipeline, not an agent | `answer/pipeline.py`, `answer/agent.py` | Measured: letting the 4B model choose its own searches and tools cites an expected source in 81% of answers against 91%, and is slower (`docs/eval-results.md`) |

## Checks that keep it honest

- Parser: UU 13/2003 parses to exactly 193 articles; Pasal 81 points are continuous in both Cipta Kerja texts; MK 168's citations of Perppu point numbers match where the parser placed each article.
- Temporal model: property tests (a new event never changes the law before its date; versions never overlap or leave gaps) and fact tests against the primary texts.
- Answers: the pipeline is tested end to end with a scripted model (every path: picked, repaired, rewritten, picked again, abstained, refused, status and amount by code, old and current wording, later law).
- Evaluation: every label must match a chunk in the corpus; runs record the config, git commit, model digests and dataset fingerprint, and start from a freshly loaded model; `rescore` re-scores a run when keys change.
- Correctness: answers are graded by reading (`grades-*.csv`), and the automatic judge is used only as far as it agrees with that reading (`pasalkini agreement`).

## Storage

| What | Where | In git |
|---|---|---|
| Official PDFs | `data/raw/` | no (re-download with `pasalkini download`) |
| Parsed documents | `data/processed/<id>.json` | no |
| Events and versions | `data/processed/pasalkini.db` | no |
| Embedding cache | `data/processed/index/` | no |
| Source list, manual events, review sheet | `sources/` | yes |
| Evaluation runs | `evals/runs/<run>/` | summary, config, grading sheet, grades by reading, the judge's grades (not the answers themselves) |
