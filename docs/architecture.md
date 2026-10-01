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
                 ─► calculate ─► the model reads the facts; tools/pesangon.py computes
                 ─► context: articles the question names, the calculator's articles, then
                    dense + BM25 search over the versions that applied on the date
                    (every version up to it for status and history questions)
                 ─► history or status question ─► code states the article's timeline
                 ─► qwen3.5:4b answers in JSON with a quote per citation
                 ─► code finds each quote in the context (near matches allowed, never a
                    different number) in a text that applied on the date
                    ─► fails: one repair with the problems listed
                    ─► shows the citations that passed, in the source's words; none left: abstains
                 ─► notes on cited articles that changed after the date
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
| Code checks every citation | `answer/verify.py` | A small model tidies what it copies and mixes up IDs; the check finds the passage, refuses a changed number, and shows the source's own words |
| Code states what it knows exactly | `answer/context.py`, `tools/pesangon.py` | An article's timeline and a severance amount come from the temporal model and the rules; the model explains them |
| A fixed pipeline, not an agent | `answer/pipeline.py` | A 4B model follows a fixed flow more reliably; an agent loop has to beat it on the evals first |

## Checks that keep it honest

- Parser: UU 13/2003 parses to exactly 193 articles; Pasal 81 points are continuous in both Cipta Kerja texts; MK 168's citations of Perppu point numbers match where the parser placed each article.
- Temporal model: property tests (a new event never changes the law before its date; versions never overlap or leave gaps) and fact tests against the primary texts.
- Answers: the pipeline is tested end to end with a scripted model (every path: verified, repaired, abstained, refused, history, calculator).
- Evaluation: every label must match a chunk in the corpus; runs record the config, git commit, model digests and dataset fingerprint; `rescore` re-scores a run when keys change.

## Storage

| What | Where | In git |
|---|---|---|
| Official PDFs | `data/raw/` | no (re-download with `pasalkini download`) |
| Parsed documents | `data/processed/<id>.json` | no |
| Events and versions | `data/processed/pasalkini.db` | no |
| Embedding cache | `data/processed/index/` | no |
| Source list, manual events, review sheet | `sources/` | yes |
| Evaluation runs | `evals/runs/<run>/` | summary, config and grading sheet only |
