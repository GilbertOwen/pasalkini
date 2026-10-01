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

ONLINE (per question)

question (+ date) ─► date: picker, or read from the question, or today
                 ─► history question? ('berubah', 'masih berlaku')
                 ─► search version chunks that applied on the date (all versions up to it for history)
                 ─► qwen3.5:4b answers in JSON, citing source IDs        [Phase 5: verify quotes, retry, abstain]
                 ─► severance / PKWT compensation computed in code (tools/pesangon.py)
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

## Checks that keep it honest

- Parser: UU 13/2003 parses to exactly 193 articles; Pasal 81 points are continuous in both Cipta Kerja texts; MK 168's citations of Perppu point numbers match where the parser placed each article.
- Temporal model: property tests (a new event never changes the law before its date; versions never overlap or leave gaps) and fact tests against the primary texts.
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
